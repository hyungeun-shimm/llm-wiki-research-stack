#!/usr/bin/env python3
"""Local LLM agent for Confidential-phase project work.

Connects to LM Studio's OpenAI-compatible API at localhost:1234 and runs
one of four confidential roles against a named project folder.  All project
content stays on-device; nothing is sent to a cloud endpoint.

Usage:
    # Drafter — write a section
    python3 scripts/local_agent.py --role drafter --project {slug}
    python3 scripts/local_agent.py --role drafter --project {slug} --section introduction

    # Planner — pre-draft strategic discussion (logs versioned automatically)
    python3 scripts/local_agent.py --role planner --project {slug}

    # Argue / Demon — critique ANY project stage
    python3 scripts/local_agent.py --role argue  --project {slug}                       # full review
    python3 scripts/local_agent.py --role argue  --project {slug} --section brief       # critique Project Brief
    python3 scripts/local_agent.py --role argue  --project {slug} --section figure-flow # critique narrative arc
    python3 scripts/local_agent.py --role argue  --project {slug} --section data-needed # critique experiment plan
    python3 scripts/local_agent.py --role argue  --project {slug} --section introduction# critique intro draft
    python3 scripts/local_agent.py --role demon  --project {slug} --section brief       # devil's advocate on brief
    python3 scripts/local_agent.py --role demon  --project {slug} --section figure-flow # attack the story arc

    # Rejection Simulator
    python3 scripts/local_agent.py --role rejection-sim --project {slug}

Special commands during a session:
    /save [section]     Save the last assistant response to the project output file.
                        Drafter: supply a section name (e.g. /save introduction).
                        Planner: saves to notes/planning-{date}.md.
    /update-brief       Save last response as a proposed Project_Brief update to
                        notes/brief-proposal-{date}.md. Review and integrate manually.
    /export-docx        Convert the last saved draft to .docx with Track Changes ON.
                        Citations resolved to (Author, Year) automatically.
                        Use after /save to get a Word-ready file.
    /export-docx-no-tc  Same as /export-docx but WITHOUT Track Changes.
                        Use for figure-flow, data-needed, and planning documents.
    /resolve-citations  Resolve [[wikilinks]] in the last saved file to (Author, Year).
                        Writes a -cited.md file alongside the original.
    /compare            Generate a side-by-side comparison of the AI draft vs
                        user-drafts/{section}.md skeleton (if it exists).
    /context            List which files are loaded and their sizes.
    /new                Clear conversation history (keeps system prompt + context).
    /quit or /exit      End the session.
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: pip install httpx")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
SUBAGENTS = ROOT / "subagents"

ROLE_TO_SUBAGENT: dict[str, str] = {
    "planner": "10-planner.md",
    "drafter": "05-drafter.md",
    "argue": "06-argue.md",
    "demon": "08-demon.md",
    "rejection-sim": "09-rejection-sim.md",
    "scout-brief": "11-scout-brief.md",
    "data-sync": "12-data-sync.md",
    "meeting-sync": "13-meeting-sync.md",
}

LM_STUDIO_BASE = "http://localhost:1234/v1"
CONTEXT_BUDGET = 28_000   # chars ≈ 7 K tokens; leaves room for system prompt
MAX_TOKENS_RESPONSE = 2048


# ---------------------------------------------------------------------------
# Frontmatter helpers (self-contained, no import from scout_common)
# ---------------------------------------------------------------------------

def _read_fm_field(text: str, field: str) -> str | None:
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    closing = None
    for idx, raw in enumerate(lines[1:], start=1):
        if raw.strip() == "---":
            closing = idx
            break
    if closing is None:
        return None
    prefix = f"{field}:".lower()
    for raw in lines[1:closing]:
        if raw.lower().lstrip().startswith(prefix):
            value = raw.split(":", 1)[1].strip()
            return value.strip('"').strip("'")
    return None


# ---------------------------------------------------------------------------
# Project validation
# ---------------------------------------------------------------------------

def verify_project(slug: str) -> Path:
    """Return project path or abort with a clear message."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", slug):
        sys.exit(f"Invalid project slug: {slug!r}")
    project = (PROJECTS / slug).resolve()
    try:
        project.relative_to(PROJECTS)
    except ValueError:
        sys.exit(f"Project path escapes projects/: {slug!r}")
    if not project.is_dir():
        sys.exit(f"Project folder not found: projects/{slug}/")

    brief = project / "Project_Brief.md"
    if not brief.exists():
        sys.exit(f"Project_Brief.md missing in projects/{slug}/")

    text = brief.read_text(encoding="utf-8")
    tier = _read_fm_field(text, "confidential_tier")
    ptype = _read_fm_field(text, "project_type")

    if ptype == "library_ingest":
        sys.exit(
            f"Refusing: projects/{slug} is a library_ingest project.\n"
            "Library-ingest projects are cloud-readable; they must not be loaded into the local agent.\n"
            "Use the cloud Ingester or Build-phase scripts for this project."
        )

    if tier and tier != "local-only":
        # Allow missing tier (default-confidential for project folders) but
        # reject explicit non-local labels to be safe.
        sys.exit(
            f"Refusing: projects/{slug}/Project_Brief.md has confidential_tier={tier!r}.\n"
            "Only 'local-only' projects run through this script.\n"
            "Add 'confidential_tier: local-only' to the frontmatter if this project is confidential."
        )

    return project


def verify_local_endpoint(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        sys.exit(
            f"Refusing non-local endpoint for confidential context: {base_url}\n"
            "Use LM Studio on http://localhost:1234/v1 or another localhost-only OpenAI-compatible server."
        )
    return base_url.rstrip("/")


# ---------------------------------------------------------------------------
# LM Studio connection
# ---------------------------------------------------------------------------

def check_server(base_url: str, requested_model: str | None = None) -> str:
    """Verify LM Studio is reachable. Returns the selected model name."""
    try:
        r = httpx.get(f"{base_url}/models", timeout=5)
        r.raise_for_status()
        data = r.json()
        models = data.get("data", [])
        model_ids = [model.get("id") for model in models if model.get("id")]
        if requested_model:
            if requested_model not in model_ids:
                available = ", ".join(model_ids) or "none"
                sys.exit(
                    f"Requested model not available: {requested_model}\n"
                    f"Available local models: {available}"
                )
            return requested_model
        if models:
            return models[0]["id"]
        return "local-model"
    except httpx.ConnectError:
        sys.exit(
            f"Cannot reach LM Studio at {base_url}.\n"
            "Open LM Studio → Local Server tab → click 'Start Server', then try again."
        )
    except Exception as exc:
        sys.exit(f"LM Studio connection error: {exc}")


# ---------------------------------------------------------------------------
# Context loading
# ---------------------------------------------------------------------------

class ContextFile:
    def __init__(self, label: str, path: Path, content: str) -> None:
        self.label = label
        self.path = path
        self.content = content

    @property
    def chars(self) -> int:
        return len(self.content)


def _load_file(label: str, path: Path) -> ContextFile | None:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        return ContextFile(label, path, content)
    except OSError:
        return None


def _latest_files(directory: Path, pattern: str, n: int = 3) -> list[Path]:
    if not directory.exists():
        return []
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:n]


def load_context(
    project: Path, role: str, context_budget: int = CONTEXT_BUDGET, section: str = ""
) -> list[ContextFile]:
    """Load role-appropriate project files within the context budget."""
    slug = project.name
    candidates: list[tuple[str, Path]] = []

    # ---- scout-brief: ONLY Project_Brief + wiki_context (no drafts, no critiques) ----
    # Strict isolation prevents the agent from accidentally leaking draft content.
    if role == "scout-brief":
        candidates.append(("Project_Brief.md", project / "Project_Brief.md"))
        candidates.append(("wiki_context.md", project / "wiki_context.md"))
        # If a previous draft exists, load it as reference only (no new content added)
        prev = project / "notes" / "scout-brief.md"
        if prev.exists():
            candidates.append(("notes/scout-brief.md [PREVIOUS DRAFT — revise or replace]", prev))
        # Inline budget fill (same logic as end of this function)
        loaded_sb: list[ContextFile] = []
        used_sb = 0
        for lbl, pth in candidates:
            cf = _load_file(lbl, pth)
            if cf is None:
                continue
            if used_sb + cf.chars > context_budget:
                break
            loaded_sb.append(cf)
            used_sb += cf.chars
        return loaded_sb

    # ---- sync roles: data-sync / meeting-sync ----
    if role in {"data-sync", "meeting-sync"}:
        candidates.append(("Project_Brief.md", project / "Project_Brief.md"))
        candidates.append(("Decision_Log.md", project / "Decision_Log.md"))
        candidates.append(("figure-plan.md", project / "figure-plan.md"))
        candidates.append(("experiment-roadmap.md", project / "experiment-roadmap.md"))
        if role == "data-sync":
            for p in _latest_files(project / "data-updates", "*.md", n=8):
                candidates.append((f"data-updates/{p.name}", p))
        else:
            for p in _latest_files(project / "meetings", "*.md", n=6):
                candidates.append((f"meetings/{p.name}", p))
        loaded_s: list[ContextFile] = []
        used_s = 0
        for lbl, pth in candidates:
            cf = _load_file(lbl, pth)
            if cf is None:
                continue
            if used_s + cf.chars > context_budget:
                break
            loaded_s.append(cf)
            used_s += cf.chars
        return loaded_s

    # ---- shared core files (all other roles) ----
    candidates.append(("Project_Brief.md", project / "Project_Brief.md"))
    candidates.append(("wiki_context.md", project / "wiki_context.md"))   # pre_drafter.py output
    candidates.append(("Evidence_Map.md", project / "Evidence_Map.md"))
    candidates.append(("Decision_Log.md", project / "Decision_Log.md"))
    candidates.append(("Roadmap.md", project / "Roadmap.md"))

    # ---- Section-specific user skeleton + previous draft (drafter / planner) ----
    if section and role in {"drafter", "planner", "argue", "demon"}:
        user_draft = project / "user-drafts" / f"{section}.md"
        if user_draft.exists():
            candidates.append((f"user-drafts/{section}.md [YOUR SKELETON]", user_draft))
        # Section-specific previous drafts
        section_drafts = sorted(
            (project / "Drafts").glob(f"{section}-v*.draft.md"),
            key=lambda p: p.stat().st_mtime, reverse=True
        ) if (project / "Drafts").exists() else []
        for p in section_drafts[:2]:
            candidates.append((f"Drafts/{p.name} [PREVIOUS DRAFT]", p))
        # Comparison file (for context)
        latest_compare = sorted(
            (project / "Drafts").glob(f"{section}-v*.comparison.md"),
            key=lambda p: p.stat().st_mtime, reverse=True
        ) if (project / "Drafts").exists() else []
        if latest_compare:
            candidates.append((f"Drafts/{latest_compare[0].name} [COMPARISON]", latest_compare[0]))

    # ---- Stage-specific extra load for argue/demon (pre-draft critique targets) ----
    if role in {"argue", "demon"} and section in _CRITIQUE_STAGES:
        # For pre-draft stages, always load the target file explicitly at the top
        stage_file_map = {
            "brief": project / "Project_Brief.md",       # already in core, but re-add for prominence
            "figure-flow": project / "figure-flow.md",
            "data-needed": project / "data-needed.md",
            "figure-plan": project / "figure-plan.md",
        }
        target_file = stage_file_map.get(section)
        if target_file and target_file.exists():
            candidates.append((f"[CRITIQUE TARGET] {target_file.name}", target_file))
        # Still load all drafts so the agent has full project context
        for p in _latest_files(project / "Drafts", "*.draft.md", n=3):
            candidates.append((f"Drafts/{p.name}", p))

    # ---- Drafts (argue, demon, rejection-sim always; drafter if revising) ----
    elif role in {"argue", "demon", "rejection-sim", "drafter"}:
        if not section or section not in _CRITIQUE_STAGES:
            if not section:  # Only load all drafts when no specific section is targeted
                for p in _latest_files(project / "Drafts", "*.draft.md", n=3):
                    candidates.append((f"Drafts/{p.name}", p))
            else:
                # Section-specific draft loading (already handled above for drafter;
                # for argue/demon with a section name, load matching drafts)
                section_drafts = sorted(
                    (project / "Drafts").glob(f"{section}-v*.draft.md"),
                    key=lambda p: p.stat().st_mtime, reverse=True
                ) if (project / "Drafts").exists() else []
                for p in section_drafts[:2]:
                    candidates.append((f"Drafts/{p.name} [CRITIQUE TARGET]", p))
                # Also load other recent drafts for broader context
                for p in _latest_files(project / "Drafts", "*.draft.md", n=2):
                    if p not in [x for _, x in candidates]:
                        candidates.append((f"Drafts/{p.name}", p))
        # also check drafts/ (lowercase) for backwards compat
        for p in _latest_files(project / "drafts", "*.md", n=2):
            if (project / "Drafts" / p.name) not in [Path(c[1]) for c in candidates]:
                candidates.append((f"drafts/{p.name}", p))

    # ---- Argue critique logs ----
    if role in {"argue", "demon", "rejection-sim", "drafter"}:
        for p in _latest_files(project / "critiques" / "argue", "*.md", n=2):
            candidates.append((f"critiques/argue/{p.name}", p))

    # ---- Demon critique logs ----
    if role in {"demon", "rejection-sim", "drafter"}:
        for p in _latest_files(project / "critiques" / "demon", "*.md", n=2):
            candidates.append((f"critiques/demon/{p.name}", p))

    # ---- Prior rejection-sims ----
    if role == "rejection-sim":
        for p in _latest_files(project / "rejection-sims", "*.md", n=2):
            candidates.append((f"rejection-sims/{p.name}", p))

    # ---- Optional planning files (paper_in_prep / grant / job_application) ----
    candidates.append(("figure-flow.md", project / "figure-flow.md"))
    candidates.append(("data-needed.md", project / "data-needed.md"))
    candidates.append(("figure-plan.md", project / "figure-plan.md"))
    candidates.append(("experiment-roadmap.md", project / "experiment-roadmap.md"))
    candidates.append(("grant_info.md", project / "grant_info.md"))        # grant guidelines
    candidates.append(("job_description.md", project / "job_description.md"))  # job posting
    candidates.append(("cv.md", project / "cv.md"))                        # CV for job apps
    if role in {"drafter", "argue", "demon"}:
        for p in _latest_files(project / "data-updates", "*.md", n=2):
            candidates.append((f"data-updates/{p.name}", p))
    # ---- Planning notes (planner, drafter) ----
    if role in {"planner", "drafter"}:
        for p in _latest_files(project / "notes", "planning-*.md", n=2):
            candidates.append((f"notes/{p.name}", p))

    # ---- Load within budget ----
    loaded: list[ContextFile] = []
    used = 0
    for label, path in candidates:
        cf = _load_file(label, path)
        if cf is None:
            continue
        if used + cf.chars > context_budget:
            print(f"  [context] Skipping {label}: would exceed budget "
                  f"({used + cf.chars:,} > {context_budget:,} chars). "
                  "Use /new and load fewer files if needed.", file=sys.stderr)
            continue
        loaded.append(cf)
        used += cf.chars

    return loaded


def format_context_block(files: list[ContextFile]) -> str:
    parts = ["# Project Context\n\nThe following files have been loaded from the project folder.\n"]
    for cf in files:
        parts.append(f"\n---\n## {cf.label}\n\n{cf.content.strip()}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def load_system_prompt(role: str) -> str:
    filename = ROLE_TO_SUBAGENT[role]
    path = SUBAGENTS / filename
    if not path.exists():
        sys.exit(f"Subagent definition not found: subagents/{filename}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

_PLANNER_SAVE_NAMES = {"planning", "figure-flow", "data-needed"}

# Stages that argue/demon can target (pre-draft artifacts + any section name)
_CRITIQUE_STAGES = {"brief", "figure-flow", "data-needed", "figure-plan"}


def _next_version(directory: Path, prefix: str, suffix: str) -> int:
    """Return the next version number for versioned files like {prefix}-v{N}-{date}{suffix}."""
    if not directory.exists():
        return 1
    existing = list(directory.glob(f"{prefix}-v*.md"))
    return len(existing) + 1


def output_path(project: Path, role: str, section: str = "") -> Path:
    today = datetime.now().strftime("%Y-%m-%d")

    if role == "planner":
        base = section if section in _PLANNER_SAVE_NAMES else "planning"
        n = _next_version(project / "notes", base, ".md")
        dest = project / "notes" / f"{base}-v{n}-{today}.md"

    elif role == "drafter":
        # Drafter uses a different versioning scheme (vN without date in prefix)
        name = f"{section or 'draft'}-{today}.draft.md"
        dest = project / "Drafts" / name

    elif role == "argue":
        stage_tag = f"-{section}" if section else ""
        n = _next_version(project / "critiques" / "argue", f"critique{stage_tag}", ".md")
        dest = project / "critiques" / "argue" / f"critique{stage_tag}-v{n}-{today}.md"

    elif role == "demon":
        stage_tag = f"-{section}" if section else ""
        n = _next_version(project / "critiques" / "demon", f"critique{stage_tag}", ".md")
        dest = project / "critiques" / "demon" / f"critique{stage_tag}-v{n}-{today}.md"

    elif role == "rejection-sim":
        n = _next_version(project / "rejection-sims", "rejection-sim", ".md")
        dest = project / "rejection-sims" / f"rejection-sim-v{n}-{today}.md"

    elif role == "scout-brief":
        # Always overwrites the single canonical draft so exports are deterministic
        dest = project / "notes" / "scout-brief.md"

    elif role in {"data-sync", "meeting-sync"}:
        prefix = role  # "data-sync" or "meeting-sync"
        n = _next_version(project / "sync-proposals", prefix, ".md")
        dest = project / "sync-proposals" / f"{prefix}-v{n}-{today}.md"

    else:
        dest = project / f"{role}-output-{today}.md"

    return dest


def brief_proposal_path(project: Path) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return project / "notes" / f"brief-proposal-{today}.md"


# ---------------------------------------------------------------------------
# LM Studio streaming
# ---------------------------------------------------------------------------

def stream_completion(
    messages: list[dict],
    model: str,
    base_url: str,
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS_RESPONSE,
) -> Iterator[str]:
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    with httpx.stream("POST", url, json=payload, timeout=None) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"]
                content = delta.get("content") or ""
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


# ---------------------------------------------------------------------------
# Session REPL
# ---------------------------------------------------------------------------

HELP_TEXT = textwrap.dedent("""\
    Commands:
      /save [section]       Save last assistant response to the project output file.
                            Drafter: supply a section name (e.g. /save introduction).
                            Planner: saves to notes/planning-{date}.md.
      /update-brief         Save last response as proposed Project_Brief update
                            → notes/brief-proposal-{date}.md. Integrate manually.
      /export-docx          Convert last saved draft to .docx (Track Changes ON).
                            Citations resolved to (Author, Year). Run AFTER /save.
      /export-docx-no-tc    Same as /export-docx WITHOUT Track Changes.
                            Use for figure-flow, data-needed, and planning docs.
      /resolve-citations    Resolve [[wikilinks]] in last saved file → (Author, Year).
                            Writes a -cited.md alongside the original.
      /compare              Show side-by-side: AI draft vs user-drafts/{section}.md.
                            Generates a comparison file.
      /context              Show loaded files and their sizes.
      /new                  Reset conversation history (keeps project context).
      /help                 Show this message.
      /quit  /exit          End the session.
      (empty line)          Also exits.
""")


_STAGE_LABELS = {
    "brief": "Project Brief",
    "figure-flow": "Figure Flow (narrative arc)",
    "data-needed": "Data Needed (experiment plan)",
    "figure-plan": "Figure Plan (status tracker)",
}


def _banner(role: str, slug: str, model: str, files: list[ContextFile],
            base_url: str = "", section: str = "") -> None:
    width = 72
    print("=" * width)
    if section:
        stage_label = _STAGE_LABELS.get(section, f"section: {section}")
        section_str = f"  target: {stage_label}"
    else:
        section_str = ""
    print(f"  Local Agent  |  role: {role}  |  project: {slug}")
    if section_str:
        print(f" {section_str}")
    print(f"  Model: {model}")
    print(f"  Endpoint: {base_url or LM_STUDIO_BASE}")
    print("-" * width)
    total = sum(f.chars for f in files)
    print(f"  Context loaded: {len(files)} file(s), {total:,} chars "
          f"(~{total // 4:,} tokens)")
    for cf in files:
        print(f"    • {cf.label}  ({cf.chars:,} chars)")
    print("-" * width)
    print("  Type /help for commands, /quit to exit.")
    print("=" * width)
    print()


def run_session(
    role: str,
    slug: str,
    base_url: str = LM_STUDIO_BASE,
    context_budget: int = CONTEXT_BUDGET,
    max_tokens: int = MAX_TOKENS_RESPONSE,
    model: str | None = None,
    section: str = "",
) -> None:
    # Validate
    project = verify_project(slug)

    # Server
    print("Checking LM Studio...", end=" ", flush=True)
    model = check_server(base_url, requested_model=model)
    print(f"OK  [{model}]")

    # Show section info
    if section and role == "drafter":
        user_draft = project / "user-drafts" / f"{section}.md"
        print(f"\nSection: {section}")
        if user_draft.exists():
            print(f"  ✓ Your skeleton: user-drafts/{section}.md ({user_draft.stat().st_size:,} bytes)")
            print(f"    → AI will write its own draft AND generate a comparison")
        else:
            print(f"  ℹ  No skeleton found at user-drafts/{section}.md")
            print(f"     Tip: Write your own rough draft first, save it there,")
            print(f"     then use /compare to see AI vs your version side by side.")
        print()

    # Load
    print("Loading project context...")
    files = load_context(project, role, context_budget=context_budget, section=section)
    if not files:
        print("Warning: No project files were loaded. Project_Brief.md may be missing.",
              file=sys.stderr)

    # System prompt
    system_prompt = load_system_prompt(role)

    # Context block
    context_block = format_context_block(files)

    # Stage-specific opening instruction (injected as first user message for argue/demon)
    def _stage_opening(role: str, section: str, slug: str) -> str:
        if role not in {"argue", "demon"}:
            return ""
        if not section:
            return (
                f"I've reviewed the full project context for **{slug}**. "
                f"Begin a comprehensive {role} review covering all loaded drafts, "
                f"the Project Brief, and supporting planning files."
            )
        label = _STAGE_LABELS.get(section, f"the **{section}** draft section")
        if section == "brief":
            return (
                f"**CRITIQUE TARGET: Project Brief**\n\n"
                f"Focus your {role} critique on `Project_Brief.md` for project **{slug}**. "
                f"Examine: aims coherence and independence, central question testability, "
                f"position statement clarity, scope boundaries, and novelty claims. "
                f"Treat the brief as an early-stage document — critique the conception, not the data."
            )
        elif section == "figure-flow":
            return (
                f"**CRITIQUE TARGET: Figure Flow (Narrative Arc)**\n\n"
                f"Focus your {role} critique on `figure-flow.md` for project **{slug}**. "
                f"Examine: whether the central claim is singular and testable; "
                f"whether each figure makes one clear scientific move; "
                f"whether the figure sequence is logically necessary (could any figure be removed?); "
                f"whether the transitions between figures are coherent; "
                f"and whether the narrative closes the loop opened in the first figure."
            )
        elif section == "data-needed":
            return (
                f"**CRITIQUE TARGET: Data Needed (Experimental Plan)**\n\n"
                f"Focus your {role} critique on `data-needed.md` for project **{slug}**. "
                f"Examine: whether the listed experiments are sufficient to support the claims; "
                f"whether any listed experiments are unnecessary (scope creep); "
                f"whether feasibility is realistic given the stated status; "
                f"and whether the high-priority experiments truly block the story."
            )
        elif section == "figure-plan":
            return (
                f"**CRITIQUE TARGET: Figure Plan**\n\n"
                f"Focus your {role} critique on `figure-plan.md` for project **{slug}**. "
                f"Examine: whether each figure panel has a defensible claim; "
                f"whether evidence mapped to each panel actually supports the panel's claim; "
                f"and whether the overall figure sequence builds to the central conclusion."
            )
        else:
            return (
                f"**CRITIQUE TARGET: {section} draft**\n\n"
                f"Focus your {role} critique on the `{section}` draft section for project **{slug}**. "
                f"Use the Project Brief position statement as the governing standard."
            )

    # Build initial message list
    stage_opening = _stage_opening(role, section, slug)

    def fresh_messages() -> list[dict]:
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context_block},
        ]
        if stage_opening:
            msgs.append({"role": "user", "content": stage_opening})
        msgs.append({"role": "assistant",
             "content": (
                 f"I've reviewed the project context for **{slug}**. "
                 f"I'm ready to assist in the **{role}** role. What would you like to work on?"
             )})
        return msgs

    messages = fresh_messages()
    last_assistant: str = ""
    last_saved_path: Path | None = None  # Track most recently saved file for /export-docx

    _banner(role, slug, model, files, base_url, section)

    # Enable readline history if available
    try:
        import readline  # noqa: F401
    except ImportError:
        pass

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            print("Session ended.")
            break

        # ---- special commands ----
        if user_input.lower() in {"/quit", "/exit"}:
            print("Session ended.")
            break

        if user_input.lower() == "/help":
            print(HELP_TEXT)
            continue

        if user_input.lower() == "/context":
            total = sum(f.chars for f in files)
            print(f"Loaded {len(files)} file(s), {total:,} chars (~{total // 4:,} tokens):")
            for cf in files:
                print(f"  • {cf.label}  ({cf.chars:,} chars)")
            continue

        if user_input.lower() == "/new":
            messages = fresh_messages()
            last_assistant = ""
            print("[Conversation history cleared. Project context retained.]")
            continue

        if user_input.lower().startswith("/save"):
            parts = user_input.split(maxsplit=1)
            # Use --section arg if no section given in /save command
            save_section = parts[1].strip() if len(parts) > 1 else section
            save_section = re.sub(r"[^\w-]", "-", save_section).lower().strip("-")
            if not last_assistant:
                print("Nothing to save — no assistant response yet.")
                continue
            # Version the output file
            base_name = save_section or "draft"
            if role == "drafter":
                # Find next version number
                existing = sorted(
                    (project / "Drafts").glob(f"{base_name}-v*.draft.md"),
                    key=lambda p: p.name,
                ) if (project / "Drafts").exists() else []
                version = len(existing) + 1
                dest = project / "Drafts" / f"{base_name}-v{version}.draft.md"
            else:
                dest = output_path(project, role, save_section)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(last_assistant, encoding="utf-8")
            last_saved_path = dest
            rel = dest.relative_to(ROOT)
            print(f"Saved → {rel}")
            if role == "drafter":
                print(f"  Run /export-docx to convert to Word (.docx with Track Changes)")
                print(f"  Run /compare to compare with your user-drafts/{save_section}.md")
            continue

        if user_input.lower() == "/update-brief":
            if not last_assistant:
                print("Nothing to save — no assistant response yet.")
                continue
            dest = brief_proposal_path(project)
            dest.parent.mkdir(parents=True, exist_ok=True)
            today = datetime.now().strftime("%Y-%m-%d")
            header = (
                f"# Project Brief Proposal — {today}\n\n"
                f"_Auto-saved by local_agent.py /update-brief from the {role} role._\n"
                "_Review this and manually integrate into Project_Brief.md._\n"
                "_Keep old versions in the '## Version History' section at the bottom of Project_Brief.md._\n\n"
                "---\n\n"
            )
            dest.write_text(header + last_assistant, encoding="utf-8")
            rel = dest.relative_to(ROOT)
            print(f"Brief proposal saved → {rel}")
            print("Next: open Project_Brief.md, paste the relevant sections, and add the old version to the end.")
            continue

        if user_input.lower() in {"/export-docx", "/export-docx-no-tc"}:
            no_tc = user_input.lower() == "/export-docx-no-tc"
            target = last_saved_path
            if target is None:
                # Try to find the latest draft for the current section
                pattern = f"{section}-v*.draft.md" if section else "*.draft.md"
                existing = sorted(
                    (project / "Drafts").glob(pattern),
                    key=lambda p: p.stat().st_mtime, reverse=True
                ) if (project / "Drafts").exists() else []
                # Also check notes/ for planner saves (figure-flow, data-needed, planning)
                if not existing:
                    existing = sorted(
                        (project / "notes").glob("*.md"),
                        key=lambda p: p.stat().st_mtime, reverse=True
                    ) if (project / "notes").exists() else []
                target = existing[0] if existing else None
            if target is None or not target.exists():
                print("No saved file found. Use /save [section] first.")
                continue
            try:
                from scripts.convert_to_docx import convert_md_to_docx
            except ImportError:
                sys.path.insert(0, str(ROOT / "scripts"))
                try:
                    from convert_to_docx import convert_md_to_docx
                except ImportError:
                    print("convert_to_docx.py not found. Run: pip install python-docx")
                    continue
            docx_path = target.with_suffix(".docx")
            try:
                out = convert_md_to_docx(
                    target, docx_path,
                    track_changes=not no_tc,
                    resolve_citations=True,
                )
                rel = out.relative_to(ROOT)
                print(f"Exported → {rel}")
                if not no_tc:
                    print("  Track Changes is ON. Open in Word and start editing.")
                    print("  Accept/reject changes: Review → Accept All / Reject All")
                else:
                    print("  Track Changes is OFF (plain Word doc).")
                    print("  Citations resolved to (Author, Year) where sources exist.")
            except Exception as exc:
                print(f"Export failed: {exc}")
            continue

        if user_input.lower() == "/resolve-citations":
            target = last_saved_path
            if target is None:
                print("No saved file found. Use /save [section] first.")
                continue
            if not target.exists():
                print(f"File not found: {target}")
                continue
            try:
                sys.path.insert(0, str(ROOT / "scripts"))
                from resolve_citations import resolve_file as _resolve_file  # type: ignore
            except ImportError:
                print("resolve_citations.py not found in scripts/.")
                continue
            cited_path = target.with_name(target.stem + "-cited" + target.suffix)
            try:
                out, resolved, unresolved = _resolve_file(
                    target, output_path=cited_path, verbose=True
                )
                if out:
                    rel = out.relative_to(ROOT)
                    print(f"Saved → {rel}")
                if unresolved:
                    print(f"\n  {len(unresolved)} unresolved link(s). "
                          "Ingest the paper or fix the wikilink spelling.")
            except Exception as exc:
                print(f"Citation resolution failed: {exc}")
            continue

        if user_input.lower() == "/compare":
            if not last_assistant and last_saved_path is None:
                print("No AI draft available. Generate a draft first, then /save [section].")
                continue
            # Find the AI draft
            ai_draft_text = last_assistant
            draft_label = "last assistant response"
            if last_saved_path and last_saved_path.exists():
                ai_draft_text = last_saved_path.read_text(encoding="utf-8")
                draft_label = last_saved_path.name
            # Find user skeleton
            sec = section or "draft"
            user_draft_path = project / "user-drafts" / f"{sec}.md"
            today = datetime.now().strftime("%Y-%m-%d")
            if user_draft_path.exists():
                user_text = user_draft_path.read_text(encoding="utf-8")
                compare_content = (
                    f"# Draft Comparison — {sec} — {today}\n\n"
                    f"_AI draft: {draft_label}_  \n"
                    f"_Your skeleton: user-drafts/{sec}.md_\n\n"
                    "---\n\n"
                    "## Your Skeleton\n\n"
                    f"{user_text.strip()}\n\n"
                    "---\n\n"
                    "## AI Draft\n\n"
                    f"{ai_draft_text.strip()}\n\n"
                    "---\n\n"
                    "## How to Use This Comparison\n\n"
                    "1. Read both versions critically\n"
                    "2. Ask the AI: 'Compare these two versions paragraph by paragraph. "
                    "Which is stronger and why? Suggest how to combine the best of both.'\n"
                    "3. Use /save after the AI's synthesis analysis\n"
                    "4. Use /export-docx to get the final version as a Word file\n"
                )
                existing = sorted(
                    (project / "Drafts").glob(f"{sec}-v*.comparison.md"),
                    key=lambda p: p.name,
                ) if (project / "Drafts").exists() else []
                version = len(existing) + 1
                compare_path = project / "Drafts" / f"{sec}-v{version}.comparison.md"
            else:
                compare_content = (
                    f"# Draft Comparison — {sec} — {today}\n\n"
                    "**No user skeleton found** at `user-drafts/{sec}.md`.\n\n"
                    "To enable comparison:\n"
                    f"1. Write your rough draft in `projects/{project.name}/user-drafts/{sec}.md`\n"
                    "2. Run `/compare` again\n\n"
                    "---\n\n"
                    "## AI Draft (for your reference)\n\n"
                    f"{ai_draft_text.strip()}\n"
                )
                compare_path = project / "Drafts" / f"{sec}-v1.comparison.md"
            compare_path.parent.mkdir(parents=True, exist_ok=True)
            compare_path.write_text(compare_content, encoding="utf-8")
            rel = compare_path.relative_to(ROOT)
            print(f"Comparison saved → {rel}")
            if user_draft_path.exists():
                print("  Ask: 'Compare these two versions paragraph by paragraph.'")
                print("  Then /save to capture the synthesis, /export-docx for Word.")
            else:
                print(f"  Write your skeleton: projects/{project.name}/user-drafts/{sec}.md")
                print("  Then run /compare again to get a real comparison.")
            continue

        # ---- normal turn ----
        messages.append({"role": "user", "content": user_input})
        print()
        print(f"{role.capitalize()}: ", end="", flush=True)

        response_parts: list[str] = []
        try:
            for chunk in stream_completion(messages, model, base_url, max_tokens=max_tokens):
                print(chunk, end="", flush=True)
                response_parts.append(chunk)
        except httpx.HTTPStatusError as exc:
            print(f"\n[HTTP error: {exc.response.status_code}]")
            detail = exc.response.text.strip()
            if detail:
                print(detail[:1000])
            messages.pop()  # drop the user turn that failed
            continue
        except httpx.ConnectError:
            print("\n[LM Studio disconnected. Restart the server and try again.]")
            break
        except KeyboardInterrupt:
            print("\n[Generation interrupted.]")
            # Keep whatever was generated
            pass

        last_assistant = "".join(response_parts)
        messages.append({"role": "assistant", "content": last_assistant})
        print("\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = ArgumentParser(
        description="Run a confidential-phase local LLM agent against a project folder.",
        formatter_class=lambda prog: __import__("argparse").RawDescriptionHelpFormatter(
            prog, max_help_position=30
        ),
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=list(ROLE_TO_SUBAGENT),
        metavar="{planner|drafter|argue|demon|rejection-sim}",
        help="Agent role to load.",
    )
    parser.add_argument(
        "--project",
        required=True,
        metavar="SLUG",
        help="Project folder name under projects/.",
    )
    parser.add_argument(
        "--base-url",
        default=LM_STUDIO_BASE,
        metavar="URL",
        help=f"LM Studio base URL. Default: {LM_STUDIO_BASE}",
    )
    parser.add_argument(
        "--context-budget",
        type=int,
        default=CONTEXT_BUDGET,
        metavar="CHARS",
        help=f"Maximum project-context characters to load. Default: {CONTEXT_BUDGET}",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=MAX_TOKENS_RESPONSE,
        metavar="TOKENS",
        help=f"Maximum response tokens per turn. Default: {MAX_TOKENS_RESPONSE}",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL_ID",
        help="Local model id from /v1/models. Example: google/gemma-4-e4b",
    )
    parser.add_argument(
        "--section",
        metavar="SECTION",
        default="",
        help=(
            "For drafter: section to draft "
            "(introduction, results, discussion, figure-legends, methods, "
            "specific-aims, approach, significance, innovation, research-statement). "
            "For argue/demon: critique target "
            "(brief, figure-flow, data-needed, figure-plan, or a section name). "
            "For planner: save topic (planning, figure-flow, data-needed)."
        ),
    )
    args = parser.parse_args()

    # Allow overriding the endpoint for testing
    base_url = verify_local_endpoint(args.base_url)
    section_slug = re.sub(r"[^\w-]", "-", args.section).lower().strip("-")
    run_session(
        args.role,
        args.project,
        base_url=base_url,
        context_budget=args.context_budget,
        max_tokens=args.max_tokens,
        model=args.model,
        section=section_slug,
    )


if __name__ == "__main__":
    main()
