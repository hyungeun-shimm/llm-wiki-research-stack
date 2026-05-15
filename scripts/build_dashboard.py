"""Build a read-only local dashboard from the research-system filesystem.

This script scans `projects/`, `papers/`, `sources/`, and `wiki/`, then writes
two generated files into `_system/dashboard/`:

- `_system/dashboard/dashboard.json` for inspection or downstream tooling
- `_system/dashboard/data.js` so `_system/dashboard/index.html` can be opened directly without
  needing a local web server
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "_system" / "dashboard"
ACTIVE_BOARD = ROOT / "projects" / "_active.md"
PREFERRED_CATEGORIES = {
    "core-topic-a",
    "core-topic-b",
    "methods",
    "concepts",
    "overviews",
    "other",
}
STATUS_SCORES = {
    "not_needed": None,
    "dropped": None,
    "planned": 0,
    "in_progress": 25,
    "data_collected": 50,
    "analyzed": 70,
    "drafted": 85,
    "complete": 100,
}


def iso_local(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_frontmatter(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency check
        raise SystemExit("Missing dependency: pyyaml") from exc
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            if first.strip() != "---":
                return {}
            for line in handle:
                if line.strip() == "---":
                    break
                lines.append(line)
    except OSError:
        return {}
    return yaml.safe_load("".join(lines)) or {}


def parse_active_board(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        if header is None:
            header = [cell.lower().replace(" ", "_") for cell in cells]
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
            continue
        row = {header[index]: cells[index] if index < len(cells) else "" for index in range(len(header))}
        project_name = row.get("project", "")
        if not project_name or project_name == "_(none yet)_":
            continue
        rows[project_name] = row
    return rows


def latest_mtime(path: Path) -> float:
    timestamps = [p.stat().st_mtime for p in path.rglob("*") if p.name != ".DS_Store"]
    if not timestamps:
        return path.stat().st_mtime
    return max(timestamps)


def count_files(path: Path, suffix: str, exclude_prefixes: tuple[str, ...] = ()) -> int:
    return sum(
        1
        for item in path.rglob(f"*{suffix}")
        if item.is_file() and not any(item.name.startswith(prefix) for prefix in exclude_prefixes)
    )


def parse_markdown_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        if header is None:
            header = [cell.lower().replace(" ", "_").replace("/", "_") for cell in cells]
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
            continue
        row = {header[index]: cells[index] if index < len(cells) else "" for index in range(len(header))}
        rows.append(row)
    return rows


def progress_from_rows(rows: list[dict[str, str]]) -> dict:
    scored: list[int] = []
    status_counts: dict[str, int] = {}
    for row in rows:
        raw_status = row.get("status", "").strip().lower().replace(" ", "_")
        if not raw_status:
            continue
        status_counts[raw_status] = status_counts.get(raw_status, 0) + 1
        score = STATUS_SCORES.get(raw_status, 0)
        if score is not None:
            scored.append(score)
    return {
        "percent": round(sum(scored) / len(scored)) if scored else 0,
        "tracked_items": len(scored),
        "status_counts": status_counts,
    }


def draft_verification_status(drafts_dir: Path) -> dict:
    if not drafts_dir.exists():
        return {
            "label": "No drafts yet",
            "state": "empty",
            "ready_for_verify": 0,
            "missing_claim_logs": 0,
            "final_drafts": 0,
        }
    staged = sorted(drafts_dir.glob("*.draft.md"))
    final_drafts = [
        path for path in drafts_dir.glob("*.md")
        if not path.name.endswith(".draft.md") and not path.name.endswith(".draft_claim_log.md")
    ]
    ready = 0
    missing = 0
    for draft in staged:
        expected_log = drafts_dir / draft.name.replace(".draft.md", ".draft_claim_log.md")
        if expected_log.exists():
            ready += 1
        else:
            missing += 1
    if missing:
        label = f"{missing} staged draft(s) missing claim logs"
        state = "blocked"
    elif ready:
        label = f"{ready} staged draft(s) ready for verification"
        state = "ready"
    elif final_drafts:
        label = f"{len(final_drafts)} final draft(s) present"
        state = "clean"
    else:
        label = "No drafts yet"
        state = "empty"
    return {
        "label": label,
        "state": state,
        "ready_for_verify": ready,
        "missing_claim_logs": missing,
        "final_drafts": len(final_drafts),
    }


def project_progress(
    brief_exists: bool,
    tracked: bool,
    scout_queries_exists: bool,
    candidate_jsons: int,
    triage_reports: int,
    draft_count: int,
) -> dict:
    stages = [
        {"name": "Brief", "complete": brief_exists},
        {"name": "Tracked", "complete": tracked},
        {"name": "Queries", "complete": scout_queries_exists},
        {"name": "Scout", "complete": candidate_jsons > 0},
        {"name": "Triage", "complete": triage_reports > 0},
        {"name": "Draft", "complete": draft_count > 0},
    ]
    completed = sum(1 for stage in stages if stage["complete"])
    next_stage = next((stage["name"] for stage in stages if not stage["complete"]), "Iterate")
    return {
        "percent": round((completed / len(stages)) * 100),
        "completed": completed,
        "total": len(stages),
        "next_stage": next_stage,
        "stages": stages,
    }


def normalize_managers(raw) -> list[dict]:
    """Coerce frontmatter `managers` into a list of {name, email} dicts.

    Accepts: list of dicts (`- name: X\n  email: Y`), list of strings
    (`"Name <email>"` or `"Name|email"`), or a single string.
    """
    if not raw:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            email = str(item.get("email") or "").strip()
        else:
            text = str(item).strip()
            if "<" in text and ">" in text:
                name = text.split("<", 1)[0].strip()
                email = text.split("<", 1)[1].rstrip(">").strip()
            elif "|" in text:
                name, _, email = text.partition("|")
                name, email = name.strip(), email.strip()
            elif "@" in text:
                name, email = text, text
            else:
                name, email = text, ""
        if name or email:
            out.append({"name": name or email, "email": email})
    return out


def project_stats(project_path: Path, active_rows: dict[str, dict], inbox_count: int) -> dict:
    slug = project_path.name
    brief_path = project_path / "Project_Brief.md"
    brief = read_frontmatter(brief_path) if brief_path.exists() else {}
    is_library_ingest = brief.get("project_type") == "library_ingest"
    if not is_library_ingest:
        drafts_upper = project_path / "Drafts"
        drafts_lower = project_path / "drafts"
        critique_root = project_path / "critiques"
        argue_dir = critique_root / "argue"
        demon_dir = critique_root / "demon"
        rejection_dir = project_path / "rejection-sims"
        notes_dir = project_path / "notes"
        data_updates_dir = project_path / "data-updates"
        brief_exists = brief_path.exists()
        evidence_exists = (project_path / "Evidence_Map.md").exists()
        decision_exists = (project_path / "Decision_Log.md").exists()
        roadmap_exists = (project_path / "Roadmap.md").exists()
        draft_files = (
            list(drafts_upper.glob("*.md")) if drafts_upper.exists() else []
        ) + (
            list(drafts_lower.glob("*.md")) if drafts_lower.exists() else []
        )
        argue_reports = list(argue_dir.glob("*.md")) if argue_dir.exists() else []
        demon_reports = list(demon_dir.glob("*.md")) if demon_dir.exists() else []
        rejection_reports = list(rejection_dir.glob("*.md")) if rejection_dir.exists() else []
        critique_reports = argue_reports + demon_reports + rejection_reports
        notes = count_files(notes_dir, ".md") if notes_dir.exists() else 0
        data_updates = count_files(data_updates_dir, ".md") if data_updates_dir.exists() else 0
        stages = [
            {"name": "Brief", "complete": brief_exists},
            {"name": "Evidence map", "complete": evidence_exists},
            {"name": "Decision log", "complete": decision_exists},
            {"name": "Roadmap", "complete": roadmap_exists},
            {"name": "Draft", "complete": bool(draft_files)},
            {"name": "Critique", "complete": bool(critique_reports)},
        ]
        completed = sum(1 for stage in stages if stage["complete"])
        next_stage = next((stage["name"] for stage in stages if not stage["complete"]), "Iterate")
        actual_type = brief.get("project_type") or "paper_in_prep"
        return {
            "slug": slug,
            "title": brief.get("title") or slug,
            "project_type": actual_type,
            "managers": normalize_managers(brief.get("managers")),
            "gdrive_path": str(brief.get("gdrive_path") or ""),
            "confidential": True,
            "status": "local-only",
            "deadline": "",
            "papers_field": "",
            "tracked": False,
            "last_touched": iso_local(project_path.stat().st_mtime),
            "progress": {
                "percent": round((completed / len(stages)) * 100),
                "completed": completed,
                "total": len(stages),
                "next_stage": next_stage,
                "stages": stages,
            },
            "draft_verification": {
                "label": "Confidential project: local-only",
                "state": "confidential",
                "ready_for_verify": 0,
                "missing_claim_logs": 0,
                "final_drafts": 0,
            },
            "counts": {
                "candidate_batches": 0,
                "candidate_jsons": 0,
                "triage_reports": 0,
                "approval_boards": 0,
                "staged_drafts": len([path for path in draft_files if path.name.endswith(".draft.md")]),
                "claim_logs": 0,
                "final_drafts": len([path for path in draft_files if not path.name.endswith(".draft.md")]),
                "notes": notes,
                "data_updates": data_updates,
                "critique_reports": len(critique_reports),
                "planned_figures": 0,
                "planned_experiments": 0,
            },
            "latest_approval_board": "",
            "paper_in_prep": {
                "figure_plan_exists": False,
                "experiment_roadmap_exists": False,
                "data_updates_dir_exists": False,
                "critiques_dir_exists": False,
                "figure_progress": {"percent": 0, "tracked_items": 0, "status_counts": {}},
                "experiment_progress": {"percent": 0, "tracked_items": 0, "status_counts": {}},
            },
            "next_step": f"Local-only: {next_stage}",
            "recommended_command": f"python3 scripts/local_agent.py --role drafter --project {slug}",
        }
    active = active_rows.get(slug, {})
    candidates_dir = project_path / "candidates"
    triage_dir = project_path / "triage-reports"
    drafts_dir = project_path / "drafts"
    notes_dir = project_path / "notes"
    scout_queries = project_path / "scout-queries.md"
    figure_plan = project_path / "figure-plan.md"
    experiment_roadmap = project_path / "experiment-roadmap.md"
    data_updates_dir = project_path / "data-updates"
    critiques_dir = project_path / "critiques"

    candidate_jsons = sum(1 for path in candidates_dir.rglob("*.json") if path.name != "_consolidated.json")
    candidate_batches = sum(1 for path in candidates_dir.iterdir() if path.is_dir()) if candidates_dir.exists() else 0
    triage_reports = count_files(triage_dir, ".md") if triage_dir.exists() else 0
    approval_boards = sorted(triage_dir.glob("*_approval-board.html")) if triage_dir.exists() else []
    staged_drafts = sum(1 for path in drafts_dir.glob("*.draft.md")) if drafts_dir.exists() else 0
    claim_logs = sum(1 for path in drafts_dir.glob("*.draft_claim_log.md")) if drafts_dir.exists() else 0
    final_drafts = sum(
        1
        for path in drafts_dir.glob("*.md")
        if not path.name.endswith(".draft.md") and not path.name.endswith(".draft_claim_log.md")
    ) if drafts_dir.exists() else 0
    notes = count_files(notes_dir, ".md") if notes_dir.exists() else 0
    data_updates = count_files(data_updates_dir, ".md") if data_updates_dir.exists() else 0
    critique_reports = count_files(critiques_dir, ".md") if critiques_dir.exists() else 0
    figure_rows = parse_markdown_table(figure_plan)
    experiment_rows = parse_markdown_table(experiment_roadmap)
    figure_progress = progress_from_rows(figure_rows)
    experiment_progress = progress_from_rows(experiment_rows)
    draft_status = draft_verification_status(drafts_dir)
    progress = project_progress(
        brief_path.exists(),
        slug in active_rows,
        scout_queries.exists(),
        candidate_jsons,
        triage_reports,
        staged_drafts + final_drafts,
    )

    if not brief_path.exists():
        next_step = "Create the project brief"
        command = f"cp projects/_template/Project_Brief_TEMPLATE.md projects/{slug}/Project_Brief.md"
    elif slug not in active_rows:
        next_step = "Add this project to projects/_active.md"
        command = "nano projects/_active.md"
    elif not scout_queries.exists():
        next_step = "Add or refine scout queries"
        command = f"nano projects/{slug}/scout-queries.md"
    elif candidate_jsons == 0 and triage_reports == 0:
        next_step = "Run the first scout batch"
        command = f"python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)"
    elif candidate_jsons > 0 and triage_reports == 0:
        next_step = "Triage the candidate batch"
        command = f"Use Codex CLI as Triage for {slug}"
    elif inbox_count > 0:
        next_step = "Ingest approved inbox PDFs"
        command = "Use Codex CLI as Ingester for papers/inbox/"
    elif staged_drafts == 0 and final_drafts == 0:
        next_step = "Review library-ingest scope"
        command = f"python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)"
    else:
        next_step = "Review the latest draft and iterate"
        command = f"Open projects/{slug}/drafts/"

    return {
        "slug": slug,
        "title": brief.get("title") or slug,
        "project_type": active.get("type") or brief.get("project_type") or "unknown",
        "managers": normalize_managers(brief.get("managers")),
        "gdrive_path": str(brief.get("gdrive_path") or ""),
        "confidential": False,
        "status": active.get("status") or "untracked",
        "deadline": active.get("deadline") or str(brief.get("deadline") or ""),
        "papers_field": active.get("papers", ""),
        "tracked": slug in active_rows,
        "last_touched": iso_local(latest_mtime(project_path)),
        "progress": progress,
        "draft_verification": draft_status,
        "counts": {
            "candidate_batches": candidate_batches,
            "candidate_jsons": candidate_jsons,
            "triage_reports": triage_reports,
            "approval_boards": len(approval_boards),
            "staged_drafts": staged_drafts,
            "claim_logs": claim_logs,
            "final_drafts": final_drafts,
            "notes": notes,
            "data_updates": data_updates,
            "critique_reports": critique_reports,
            "planned_figures": len(figure_rows),
            "planned_experiments": len(experiment_rows),
        },
        "latest_approval_board": relative(approval_boards[-1]) if approval_boards else "",
        "paper_in_prep": {
            "figure_plan_exists": figure_plan.exists(),
            "experiment_roadmap_exists": experiment_roadmap.exists(),
            "data_updates_dir_exists": data_updates_dir.exists(),
            "critiques_dir_exists": critiques_dir.exists(),
            "figure_progress": figure_progress,
            "experiment_progress": experiment_progress,
        },
        "next_step": next_step,
        "recommended_command": command,
    }


def category_stats() -> list[dict]:
    rows: list[dict] = []
    wiki_dir = ROOT / "wiki"
    for category_dir in sorted(path for path in wiki_dir.iterdir() if path.is_dir() and not path.name.startswith(".")):
        count = sum(1 for path in category_dir.glob("*.md"))
        if count > 0:  # only include categories that actually have wiki files
            rows.append(
                {
                    "name": category_dir.name,
                    "page_count": count,
                    "legacy": category_dir.name not in PREFERRED_CATEGORIES,
                }
            )
    return rows


def corpus_counts() -> dict:
    papers_dir = ROOT / "papers"
    pdfs = []
    inbox = papers_dir / "inbox"
    under_review = papers_dir / "under-review"
    for path in papers_dir.rglob("*.pdf"):
        if inbox in path.parents or under_review in path.parents:
            continue
        pdfs.append(path)
    return {
        "corpus_pdfs": len(pdfs),
        "inbox_pdfs": sum(1 for path in inbox.glob("*.pdf")),
        "under_review_pdfs": sum(1 for path in under_review.glob("*.pdf")),
        "source_pages": sum(1 for path in (ROOT / "sources").glob("*.md")),
        "overview_pages": sum(1 for path in (ROOT / "wiki" / "overviews").glob("*.md")),
    }


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        row_count = sum(1 for _ in handle)
    return max(row_count - 1, 0)


def mendeley_status() -> dict:
    export_bib = ROOT / "_system" / "mendeley" / "export" / "library.bib"
    review_dir = ROOT / "_system" / "mendeley" / "review"
    watch_dir = ROOT / "_system" / "mendeley" / "watch"
    pdf_inventory = review_dir / "pdf_inventory.csv"
    duplicates = review_dir / "duplicate_candidates.csv"
    proposed = review_dir / "proposed_categories.csv"
    return {
        "export_bib": relative(export_bib),
        "export_exists": export_bib.exists(),
        "review_summary": relative(review_dir / "library_audit_summary.md"),
        "watch_dir": str(watch_dir),
        "entry_count": count_csv_rows(proposed),
        "pdf_count": count_csv_rows(pdf_inventory),
        "duplicate_count": count_csv_rows(duplicates),
        "commands": [
            {
                "tool": "Codex CLI / Terminal",
                "title": "Re-run Mendeley library audit",
                "detail": "Use after exporting a fresh BibTeX file from Mendeley to _system/mendeley/export/library.bib.",
                "button_label": "Copy audit command",
                "command": "python3 scripts/audit_mendeley_export.py --bib _system/mendeley/export/library.bib --pdf-root \"$HOME/Library/Application Support/Mendeley Reference Manager/userfiles\" --out _system/mendeley/review",
            },
            {
                "tool": "Codex CLI / Terminal",
                "title": "Start local Mendeley OAuth callback page",
                "detail": "Run this first, then keep the Terminal window open while authorizing Mendeley.",
                "button_label": "Copy server command",
                "command": "python3 -m http.server 8765",
            },
            {
                "tool": "Codex CLI / Terminal",
                "title": "Generate Mendeley authorization URL",
                "detail": "Replace YOUR_CLIENT_ID with the application ID from dev.mendeley.com/myapps.html.",
                "button_label": "Copy auth URL command",
                "command": "python3 scripts/mendeley_auth_url.py --client-id YOUR_CLIENT_ID",
            },
            {
                "tool": "Codex CLI / Terminal",
                "title": "Apply proposed Mendeley collections",
                "detail": "Requires MENDELEY_ACCESS_TOKEN. This creates/adds broad collection memberships; it does not delete old collections.",
                "button_label": "Copy apply command",
                "command": "python3 scripts/mendeley_apply_collections.py --apply",
            },
            {
                "tool": "Codex CLI / Terminal",
                "title": "Copy one wiki PDF into Mendeley watched folder",
                "detail": "Replace {stem} with an ingested paper filename from papers/. Mendeley should watch _system/mendeley/watch/.",
                "button_label": "Copy sync command",
                "command": "python3 scripts/sync_to_mendeley_watch.py --paper papers/{stem}.pdf",
            },
        ],
    }


def markdown_title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except UnicodeDecodeError:
        return path.stem
    return path.stem


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n?", "", text, flags=re.S).strip()


def compact_snippet(text: str, limit: int = 360) -> str:
    text = strip_frontmatter(text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def markdown_section(text: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, flags=re.M | re.S | re.I)
    if not match:
        return ""
    return match.group(1).strip()


def scout_history_index() -> list[dict]:
    scout_dir = ROOT / "scouts"
    if not scout_dir.exists():
        return []
    items: list[dict] = []
    for path in sorted(scout_dir.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        brief = path / "Scout_Brief.md"
        if not brief.exists():
            continue
        text = brief.read_text(encoding="utf-8", errors="replace")
        frontmatter = read_frontmatter(brief) if text.startswith("---") else {}
        title = str(frontmatter.get("title") or markdown_title(brief))
        keywords = markdown_section(text, "Must-include keywords")
        exclude = markdown_section(text, "Must-exclude keywords")
        year_range = markdown_section(text, "Year range")
        candidates_dir = path / "candidates"
        batches = (
            sorted(batch.name for batch in candidates_dir.iterdir() if batch.is_dir() and not batch.name.startswith("."))
            if candidates_dir.exists()
            else []
        )
        items.append(
            {
                "slug": path.name,
                "title": title,
                "path": relative(path),
                "brief_path": relative(brief),
                "keywords": compact_snippet(keywords, limit=220),
                "exclude": compact_snippet(exclude, limit=140),
                "year_range": compact_snippet(year_range, limit=80),
                "candidate_batch_count": len(batches),
                "latest_candidate_batch": batches[-1] if batches else "",
                "updated": iso_local(latest_mtime(path)),
                "search_text": " ".join([path.name, title, keywords, exclude, year_range]).lower(),
            }
        )
    items.sort(key=lambda item: item["updated"], reverse=True)
    return items


def wiki_search_index() -> list[dict]:
    roots = [
        ROOT / "index.md",
        ROOT / "wiki",
        ROOT / "sources",
    ]
    items: list[dict] = []
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
        for path in paths:
            if not path.is_file() or path.name.startswith("."):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            frontmatter = read_frontmatter(path) if text.startswith("---") else {}
            rel_path = relative(path)
            if rel_path.startswith("sources/"):
                kind = "source"
            elif rel_path.startswith("wiki/overviews/"):
                kind = "overview"
            elif rel_path.startswith("wiki/"):
                kind = "wiki"
            else:
                kind = "index"
            items.append(
                {
                    "title": str(frontmatter.get("title") or markdown_title(path)),
                    "path": rel_path,
                    "kind": kind,
                    "year": str(frontmatter.get("year") or ""),
                    "category": ", ".join(frontmatter.get("category", []))
                    if isinstance(frontmatter.get("category"), list)
                    else str(frontmatter.get("category") or ""),
                    "snippet": compact_snippet(text),
                    "search_text": " ".join(
                        [
                            str(frontmatter.get("title") or markdown_title(path)),
                            rel_path,
                            str(frontmatter.get("authors") or ""),
                            str(frontmatter.get("year") or ""),
                            str(frontmatter.get("category") or ""),
                            compact_snippet(text, limit=1200),
                        ]
                    ).lower(),
                }
            )
    return items


def exploration_status() -> dict:
    root = ROOT / "explorations"
    idea_dir = root / "idea-notes"
    brief_dir = root / "ideas"
    active_dir = root / "active"
    archive_dir = root / "archive"
    scout_dir = ROOT / "scouts"

    items: list[dict] = []
    approval_targets: list[dict] = []
    status_counts: dict[str, int] = {}

    def latest_matching(path: Path, pattern: str) -> Path | None:
        if not path.exists():
            return None
        matches = sorted(path.glob(pattern), key=lambda item: item.stat().st_mtime)
        return matches[-1] if matches else None

    def add_item(path: Path, level: str) -> None:
        frontmatter = read_frontmatter(path) if path.exists() and path.suffix == ".md" else {}
        status = str(frontmatter.get("status") or "untracked")
        status_counts[status] = status_counts.get(status, 0) + 1
        items.append(
            {
                "title": str(frontmatter.get("title") or markdown_title(path)),
                "slug": str(frontmatter.get("idea_slug") or frontmatter.get("exploration_slug") or path.stem),
                "level": level,
                "status": status,
                "path": relative(path),
                "updated": str(frontmatter.get("updated") or iso_local(path.stat().st_mtime)),
            }
        )

    if idea_dir.exists():
        for path in sorted(idea_dir.glob("*.md")):
            if path.name != "README.md":
                add_item(path, "idea-note")

    if brief_dir.exists():
        for path in sorted(brief_dir.glob("Exploration_Brief_*.md")):
            add_item(path, "exploration-brief")

    if active_dir.exists():
        for path in sorted(active_dir.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            candidates_dir = path / "candidates"
            candidate_batches = (
                sorted(batch.name for batch in candidates_dir.iterdir() if batch.is_dir() and not batch.name.startswith("."))
                if candidates_dir.exists()
                else []
            )
            triage_dir = path / "triage-reports"
            triage_reports = sorted(triage_dir.glob("*.json")) if triage_dir.exists() else []
            latest_board = latest_matching(triage_dir, "*_approval-board.html")
            if candidate_batches or triage_reports or latest_board:
                _exp_brief = path / "Exploration_Brief.md"
                _exp_text  = _exp_brief.read_text(encoding="utf-8", errors="replace") if _exp_brief.exists() else ""
                _exp_kw    = compact_snippet(markdown_section(_exp_text, "Keywords"), limit=220) or \
                             compact_snippet(markdown_section(_exp_text, "Search terms"), limit=220)
                _exp_yr    = compact_snippet(markdown_section(_exp_text, "Year range"), limit=80)
                approval_targets.append(
                    {
                        "kind": "exploration",
                        "slug": path.name,
                        "title": path.name,
                        "topic": path.name,
                        "keywords": _exp_kw,
                        "year_range": _exp_yr,
                        "path": relative(path),
                        "latest_candidate_batch": candidate_batches[-1] if candidate_batches else "",
                        "candidate_batch_count": len(candidate_batches),
                        "triage_report_count": len(triage_reports),
                        "latest_approval_board": relative(latest_board) if latest_board else "",
                        "updated": iso_local(latest_mtime(path)),
                    }
                )
            brief = path / "Exploration_Brief.md"
            if brief.exists():
                add_item(brief, "active-exploration")
            else:
                status_counts["active-unbriefed"] = status_counts.get("active-unbriefed", 0) + 1
                items.append(
                    {
                        "title": path.name,
                        "slug": path.name,
                        "level": "active-exploration",
                        "status": "active-unbriefed",
                        "path": relative(path),
                        "updated": iso_local(latest_mtime(path)),
                    }
                )

    if scout_dir.exists():
        for path in sorted(scout_dir.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            candidates_dir = path / "candidates"
            candidate_batches = (
                sorted(batch.name for batch in candidates_dir.iterdir() if batch.is_dir() and not batch.name.startswith("."))
                if candidates_dir.exists()
                else []
            )
            triage_dir = path / "triage-reports"
            triage_reports = sorted(triage_dir.glob("*.json")) if triage_dir.exists() else []
            latest_board = latest_matching(triage_dir, "*_approval-board.html")
            if candidate_batches or triage_reports or latest_board:
                brief = path / "Scout_Brief.md"
                frontmatter = read_frontmatter(brief) if brief.exists() else {}
                brief_text = brief.read_text(encoding="utf-8", errors="replace") if brief.exists() else ""
                _title = str(frontmatter.get("title") or markdown_title(brief) if brief.exists() else path.name)
                _keywords  = compact_snippet(markdown_section(brief_text, "Must-include keywords"), limit=220)
                _exclude   = compact_snippet(markdown_section(brief_text, "Must-exclude keywords"), limit=140)
                _year_range = compact_snippet(markdown_section(brief_text, "Year range"), limit=80)
                approval_targets.append(
                    {
                        "kind": "paper-scout",
                        "slug": path.name,
                        "title": _title,
                        "topic": _title,
                        "keywords": _keywords,
                        "exclude": _exclude,
                        "year_range": _year_range,
                        "path": relative(path),
                        "latest_candidate_batch": candidate_batches[-1] if candidate_batches else "",
                        "candidate_batch_count": len(candidate_batches),
                        "triage_report_count": len(triage_reports),
                        "latest_approval_board": relative(latest_board) if latest_board else "",
                        "updated": iso_local(latest_mtime(path)),
                    }
                )

    items.sort(key=lambda item: item["updated"], reverse=True)
    approval_targets.sort(key=lambda item: item["updated"], reverse=True)
    return {
        "idea_notes": count_files(idea_dir, ".md", exclude_prefixes=("README",)) if idea_dir.exists() else 0,
        "briefs": count_files(brief_dir, ".md", exclude_prefixes=("README",)) if brief_dir.exists() else 0,
        "active": sum(1 for path in active_dir.iterdir() if path.is_dir() and not path.name.startswith(".")) if active_dir.exists() else 0,
        "archived": count_files(archive_dir, ".md", exclude_prefixes=("README",)) if archive_dir.exists() else 0,
        "status_counts": status_counts,
        "recent": items[:8],
        "approval_targets": approval_targets,
        "commands": [
            {
                "tool": "cloud-safe",
                "title": "Summarize discussion into idea note",
                "detail": "Use after a brainstorming conversation produces a useful but still lightweight idea.",
                "button_label": "Copy idea-note prompt",
                "command": "Summarize our latest discussion as an evolving idea note. Do not save the full transcript. Create or update explorations/idea-notes/IDEA_SLUG.md using explorations/_template/Idea_Note_TEMPLATE.md. Add only the new or changed ideas under today's date, keep a short Current Summary, and list open questions plus candidate papers to check if any.",
            },
            {
                "tool": "cloud-safe",
                "title": "Promote idea note to Exploration Brief",
                "detail": "Use when an idea has a focused question, searchable terms, and possible wiki or project value.",
                "button_label": "Copy promote prompt",
                "command": "Promote explorations/idea-notes/IDEA_SLUG.md to explorations/ideas/Exploration_Brief_IDEA_SLUG.md using explorations/_template/Exploration_Brief_TEMPLATE.md. Preserve the evolving summary, convert it into a focused starting question, search scope, seed ideas, candidate paper criteria, related wiki anchors, and stop/promote criteria. Do not scout yet.",
            },
            {
                "tool": "cloud-safe",
                "title": "Run Exploration Skeptic Review",
                "detail": "Use before scouting. It decides whether the idea is actually worth an active exploration.",
                "button_label": "Copy skeptic prompt",
                "command": "Read subagents/07-exploration-skeptic.md and act as the Exploration Skeptic for explorations/ideas/Exploration_Brief_IDEA_SLUG.md. Do not search the web and do not scout. Fill or update the Skeptic Review section with whether this is not-ready, brief-ready, scout-ready, or project-ready, plus why, risks, evidence that would change the decision, and a minimal scout plan only if scout-ready.",
            },
            {
                "tool": "Local LLM",
                "title": "Promote to active exploration + create project",
                "detail": "Creates the active exploration folder and a linked confidential project. Asks for project title and type, then runs wiki relevance scan automatically.",
                "button_label": "Promote + create project",
                "action_id": "promote-exploration-to-project",
                "runnable": True,
                "command": "mkdir -p explorations/active/IDEA_SLUG/{candidates,paper-briefs,_pdfs} && cp explorations/ideas/Exploration_Brief_IDEA_SLUG.md explorations/active/IDEA_SLUG/Exploration_Brief.md && touch explorations/active/IDEA_SLUG/scout-queries.md explorations/active/IDEA_SLUG/notes.md explorations/active/IDEA_SLUG/questions.md explorations/active/IDEA_SLUG/synthesis.md explorations/active/IDEA_SLUG/promote-to-wiki.md explorations/active/IDEA_SLUG/promote-to-project.md",
            },
            {
                "tool": "Local LLM",
                "title": "Write exploration-local synthesis",
                "detail": "Opens local agent (Drafter) on the project created from this exploration. LM Studio must be running.",
                "button_label": "Run local synthesis",
                "action_id": "local-exploration-synthesis",
                "runnable": True,
                "command": "python3 scripts/local_agent.py --role drafter --project PROJECT_SLUG",
            },
        ],
    }


def recent_files(limit: int = 12) -> list[dict]:
    interesting_roots = [
        ROOT / "explorations",
        ROOT / "sources",
        ROOT / "wiki",
        ROOT / "_system" / "dashboard",
        ROOT / "_system" / "mendeley" / "review",
    ]
    items = []
    for root in interesting_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.name.startswith(".") or path.name == ".DS_Store":
                continue
            if path.parts[-2:] == ("active", "_pdfs") or "_pdfs" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".json", ".js", ".html", ".css", ".pdf"}:
                continue
            items.append((path.stat().st_mtime, path))
    items.sort(reverse=True)
    return [{"path": relative(path), "modified_at": iso_local(ts)} for ts, path in items[:limit]]


def build_actions(projects: list[dict], totals: dict, active_rows: dict[str, dict]) -> list[dict]:
    actions: list[dict] = []
    public_projects = [project for project in projects if not project.get("confidential")]
    untracked = [project for project in public_projects if not project["tracked"]]
    public_active_rows = {slug: row for slug, row in active_rows.items() if any(project["slug"] == slug for project in public_projects)}
    if not public_active_rows and public_projects:
        actions.append(
            {
                "severity": "warning",
                "title": "Track public ingest workspaces in projects/_active.md",
                "detail": "Only library_ingest projects belong on this public dashboard board. Local-only projects stay out of it.",
                "command": "nano projects/_active.md",
            }
        )
    elif untracked:
        actions.append(
            {
                "severity": "warning",
                "title": "Add untracked projects to the active board",
                "detail": ", ".join(project["slug"] for project in untracked),
                "command": "nano projects/_active.md",
            }
        )
    if totals["source_pages"] == 0:
        actions.append(
            {
                "severity": "info",
                "title": "Ingest 1-3 seed papers first",
                "detail": "The wiki is still empty, so future scouting and drafting will be weak.",
                "command": "Use Codex CLI as Ingester on your first approved PDFs",
            }
        )
    if totals["inbox_pdfs"] > 0:
        actions.append(
            {
                "severity": "urgent",
                "title": "Ingest approved inbox PDFs",
                "detail": f"{totals['inbox_pdfs']} PDF(s) are waiting in papers/inbox/",
                "command": "Use Codex CLI as Ingester for papers/inbox/",
            }
        )
    for project in projects:
        if project.get("confidential"):
            continue
        if project["draft_verification"]["missing_claim_logs"]:
            actions.append(
                {
                    "severity": "urgent",
                    "title": f"Fix draft claim logs for {project['slug']}",
                    "detail": project["draft_verification"]["label"],
                    "command": f"Open projects/{project['slug']}/drafts/",
                }
            )
            break
        if project["draft_verification"]["ready_for_verify"]:
            actions.append(
                {
                    "severity": "urgent",
                    "title": f"Verify staged drafts for {project['slug']}",
                    "detail": project["draft_verification"]["label"],
                    "command": f"python3 scripts/verify_citations.py projects/{project['slug']}/drafts/X.draft.md projects/{project['slug']}/drafts/X.draft_claim_log.md",
                }
            )
            break
    for project in projects:
        if project.get("confidential"):
            continue
        if project["counts"]["candidate_jsons"] > 0 and project["counts"]["triage_reports"] == 0:
            actions.append(
                {
                    "severity": "info",
                    "title": f"Triage candidate batch for {project['slug']}",
                    "detail": f"{project['counts']['candidate_jsons']} candidate JSON file(s) are waiting.",
                    "command": f"Use Codex CLI as Triage for {project['slug']}",
                }
            )
            break
    if totals["source_pages"] >= 3 and totals["overview_pages"] == 0:
        actions.append(
            {
                "severity": "info",
                "title": "Create the first overview page",
                "detail": "You have enough ingested sources to start compounding knowledge.",
                "command": "Use a cloud-safe Synthesizer pass on the first topic cluster",
            }
        )
    return actions


def build_today(actions: list[dict], projects: list[dict]) -> list[dict]:
    priority_map = {"urgent": "P1", "warning": "P2", "info": "P3"}
    today = [
        {
            "priority": priority_map.get(action["severity"], "P3"),
            "title": action["title"],
            "context": action["detail"],
            "command": action["command"],
        }
        for action in actions
    ]
    for project in projects:
        if project["progress"]["next_stage"] == "Tracked" and any("projects/_active.md" in item["command"] for item in today):
            continue
        if project["progress"]["percent"] < 100 and not any(project["slug"] in item["title"] for item in today):
            today.append(
                {
                    "priority": "P3",
                    "title": f"Advance {project['slug']} to {project['progress']['next_stage']}",
                    "context": f"Workflow progress is {project['progress']['percent']}%.",
                    "command": project["recommended_command"],
                }
            )
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    return sorted(today, key=lambda item: priority_order[item["priority"]])[:6]


def build_command_templates(projects: list[dict]) -> list[dict]:
    if not projects:
        return [
            {
                "tool": "Codex CLI",
                "title": "Create a first project workspace",
                "detail": "Use this before the wiki has a real project.",
                "command": "mkdir -p projects/k01-exploratory/{candidates,triage-reports,drafts,notes} && cp projects/_template/Project_Brief_TEMPLATE.md projects/k01-exploratory/Project_Brief.md",
            }
        ]

    templates: list[dict] = []
    for project in projects:
        slug = project["slug"]
        if project.get("confidential"):
            templates.extend(
                [
                    {
                        "tool": "Local LLM",
                        "title": f"Run local Drafter for {slug}",
                        "detail": "Confidential project. Runs through LM Studio only.",
                        "command": f"python3 scripts/local_agent.py --role drafter --project {slug}",
                    },
                    {
                        "tool": "Local LLM",
                        "title": f"Run local Argue for {slug}",
                        "detail": "Confidential reviewer-style critique via local LLM.",
                        "command": f"python3 scripts/local_agent.py --role argue --project {slug}",
                    },
                    {
                        "tool": "Local LLM",
                        "title": f"Run local Demon for {slug}",
                        "detail": "Confidential devil's-advocate critique via local LLM.",
                        "command": f"python3 scripts/local_agent.py --role demon --project {slug}",
                    },
                    {
                        "tool": "Local LLM",
                        "title": f"Run local Rejection-Sim for {slug}",
                        "detail": "Confidential pre-submission rejection simulation via local LLM.",
                        "command": f"python3 scripts/local_agent.py --role rejection-sim --project {slug}",
                    },
                ]
            )
            continue
        templates.extend(
            [
                {
                    "tool": "Terminal",
                    "title": f"Open project brief for {slug}",
                    "detail": "Edit the project contract before scouting or drafting.",
                    "command": f"nano projects/{slug}/Project_Brief.md",
                },
                {
                    "tool": "Terminal",
                    "title": f"Create optional paper-in-prep files for {slug}",
                    "detail": "Use only when the project is ready for figure/data planning.",
                    "command": f"mkdir -p projects/{slug}/data-updates projects/{slug}/critiques && cp -n projects/_template/figure-plan_TEMPLATE.md projects/{slug}/figure-plan.md && cp -n projects/_template/experiment-roadmap_TEMPLATE.md projects/{slug}/experiment-roadmap.md && cp -n projects/_template/critique-log_TEMPLATE.md projects/{slug}/critiques/critique-log.md",
                },
                {
                    "tool": "Terminal",
                    "title": f"Edit scout queries for {slug}",
                    "detail": "Add follow-up search campaigns without changing Project_Brief.md.",
                    "command": f"nano projects/{slug}/scout-queries.md",
                },
                {
                    "tool": "Codex CLI",
                    "title": f"Scout papers for {slug}",
                    "detail": "Run after the project brief and scout queries are ready.",
                    "command": f"python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)",
                },
                {
                    "tool": "Codex CLI",
                    "title": f"Scout query campaign only for {slug}",
                    "detail": "Runs only unchecked scout-queries.md items.",
                    "command": f"python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)-campaign --queries-only",
                },
                {
                    "tool": "Codex CLI",
                    "title": f"Triage candidates for {slug}",
                    "detail": "Paste this into Codex after a candidate batch exists.",
                    "command": f"Read subagents/02-triage.md and act as the Triage agent for project {slug}. Use projects/{slug}/Project_Brief.md and the newest candidates folder. Write the triage report to projects/{slug}/triage-reports/.",
                },
                {
                    "tool": "Terminal",
                    "title": f"Build triage approval board for {slug}",
                    "detail": "Creates a local HTML checklist for download/wiki-only/skip decisions.",
                    "command": f"python3 scripts/build_triage_approval_board.py --project projects/{slug}",
                },
                {
                    "tool": "Terminal",
                    "title": f"Open selected paper links for {slug}",
                    "detail": "After approval board Download JSON, replace PATH_TO_DECISIONS_JSON with that file path.",
                    "command": "python3 scripts/open_pdf_decision_urls.py PATH_TO_DECISIONS_JSON --action both --open",
                },
                {
                    "tool": "Codex CLI",
                    "title": f"Ingest approved PDFs for {slug}",
                    "detail": "Use after you manually place approved PDFs in papers/inbox/.",
                    "command": f"Read subagents/03-ingester.md and act as the Ingester agent for project {slug}. Ingest approved PDFs from papers/inbox/ into papers/, sources/, wiki/, and index.md. Treat source frontmatter as citation truth and fail loudly if authors, year, or DOI cannot be resolved.",
                },
                {
                    "tool": "Codex CLI",
                    "title": "Global wiki ingest from inbox",
                    "detail": "Project-independent. Use when you already have PDFs and want them in the wiki without Scout, Triage, or Project_Brief.",
                    "command": "Read subagents/03-ingester.md and act as the Ingester agent in direct wiki ingest mode.\n\nDo not use any Project_Brief. Do not use Scout or Triage. Ingest only the PDFs currently placed in papers/inbox/ into the global LLM-Wiki.\n\nFor each PDF:\n- copy/rename it into papers/\n- create sources/{stem}.md with citation-truth frontmatter\n- create wiki/{category}/{stem}.md\n- choose the best category from AGENTS.md\n- update index.md\n\nUse only the PDF content. Do not use web search. If author, year, or DOI cannot be resolved, stop and list the unresolved papers instead of guessing.",
                },
                {
                    "tool": "cloud-safe",
                    "title": f"Synthesize overview for {slug}",
                    "detail": "Use after at least 3 related papers are ingested.",
                    "command": f"Read subagents/04-synthesizer.md and act as the Synthesizer agent for the public library-ingest topic {slug}. Use relevant sources/ and wiki/ pages only. Write or update the appropriate wiki/overviews/ page.",
                },
                {
                    "tool": "Codex CLI",
                    "title": f"Verify a draft for {slug}",
                    "detail": "Replace X with the draft basename before running.",
                    "command": f"python3 scripts/verify_citations.py projects/{slug}/drafts/X.draft.md projects/{slug}/drafts/X.draft_claim_log.md",
                },
            ]
        )
    return templates[:20]


HOMEWORK_PATH = ROOT / "_system" / "docs" / "homework.json"


def homework_status() -> dict:
    """Load homework config and compute days-remaining / overdue status."""
    default = {"frequency_days": 14, "current": None, "completed": [], "skipped": []}
    if not HOMEWORK_PATH.exists():
        return default
    try:
        data = json.loads(HOMEWORK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
    # Enrich with days_remaining if current paper exists
    current = data.get("current")
    if current and current.get("due_date"):
        from datetime import date
        try:
            due = date.fromisoformat(current["due_date"])
            today = date.today()
            data["days_remaining"] = (due - today).days
            data["overdue"] = data["days_remaining"] < 0
        except ValueError:
            data["days_remaining"] = None
            data["overdue"] = False
    else:
        data["days_remaining"] = None
        data["overdue"] = False
    # Attach wiki page list for random assignment (stems only, no overviews)
    wiki_dir = ROOT / "wiki"
    wiki_papers = []
    if wiki_dir.exists():
        for cat_dir in wiki_dir.iterdir():
            if not cat_dir.is_dir() or cat_dir.name == "overviews":
                continue
            for md in cat_dir.glob("*.md"):
                wiki_papers.append({
                    "stem": md.stem,
                    "category": cat_dir.name,
                    "path": str(md.relative_to(ROOT)),
                })
    data["wiki_papers"] = wiki_papers
    data["total_wiki_papers"] = len(wiki_papers)
    data["completed_count"] = len(data.get("completed", []))

    # Attach homework sessions and idea-wiki entries
    data["sessions"] = _gather_homework_sessions()
    data["idea_wiki"] = _gather_idea_wiki()
    return data


def _gather_homework_sessions() -> list[dict]:
    """List homework session folders (newest first)."""
    import re as _re
    hw_dir = ROOT / "homework"
    idea_wiki_dir = hw_dir / "idea-wiki"
    sessions = []
    if not hw_dir.exists():
        return sessions
    for d in sorted(hw_dir.iterdir(), reverse=True):
        if not d.is_dir() or d.name.startswith("_") or d.name == "idea-wiki":
            continue
        m = _re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", d.name)
        if not m:
            continue
        session_date = m.group(1)
        title = d.name  # fallback
        notes_path = d / "notes.md"
        if notes_path.exists():
            try:
                text = notes_path.read_text(encoding="utf-8")
                for line in text.split("\n")[1:10]:
                    if line.lower().startswith("paper_title:"):
                        title = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
            except OSError:
                pass
        idea_count = len(list(idea_wiki_dir.glob(f"{session_date}-*.md"))) if idea_wiki_dir.exists() else 0
        sessions.append({
            "dir": str(d.relative_to(ROOT)),
            "dir_name": d.name,
            "session_date": session_date,
            "title": title,
            "has_notes": notes_path.exists(),
            "has_discussion": (d / "discussion-log.md").exists(),
            "has_ideas": (d / "ideas.md").exists(),
            "idea_count": idea_count,
        })
    return sessions


def _gather_idea_wiki() -> list[dict]:
    """List idea-wiki entries (newest first)."""
    idea_dir = ROOT / "homework" / "idea-wiki"
    ideas = []
    if not idea_dir.exists():
        return ideas
    for md in sorted(idea_dir.glob("*.md"), reverse=True):
        if md.name == "index.md":
            continue
        entry: dict = {"filename": md.name, "path": str(md.relative_to(ROOT))}
        try:
            text = md.read_text(encoding="utf-8")
            in_fm = False
            for line in text.split("\n"):
                if line.strip() == "---":
                    in_fm = not in_fm
                    continue
                if in_fm:
                    for key in ("title", "source_paper_stem", "date", "status",
                                "linked_exploration", "linked_project"):
                        if line.lower().startswith(f"{key}:"):
                            entry[key] = line.split(":", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
        ideas.append(entry)
    return ideas


BACKUP_STATE_PATH = ROOT / "_system" / "docs" / "backup_state.json"
BACKUP_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.llmwiki.backup.plist"


def backup_status() -> dict:
    """Read backup_state.json and add derived fields for the dashboard (restic-based)."""
    default: dict = {
        "gdrive_path": "",
        "repo_initialized": False,
        "last_backup": None,
        "last_snapshot_id": None,
        "files_new": None,
        "data_added_bytes": None,
        "auto_backup_installed": False,
        "auto_backup_interval_hours": 24,
    }
    if not BACKUP_STATE_PATH.exists():
        data = dict(default)
    else:
        try:
            data = json.loads(BACKUP_STATE_PATH.read_text(encoding="utf-8"))
            for key, val in default.items():
                data.setdefault(key, val)
        except (json.JSONDecodeError, OSError):
            data = dict(default)

    last_backup = data.get("last_backup")
    days_since: int | None = None
    if last_backup:
        try:
            from datetime import timezone
            dt = datetime.fromisoformat(last_backup)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(tz=timezone.utc) - dt).days
        except ValueError:
            pass

    data["days_since_backup"] = days_since
    data["overdue"]           = days_since is None or days_since > 30
    data["plist_installed"]   = BACKUP_PLIST_PATH.exists()
    # Human-readable size
    added = data.get("data_added_bytes") or 0
    data["data_added_mb"] = round(added / 1_048_576, 2) if added else None

    return data


def build_payload() -> dict:
    active_rows = parse_active_board(ACTIVE_BOARD)
    totals = corpus_counts()
    explorations = exploration_status()
    project_dirs = sorted(
        path for path in (ROOT / "projects").iterdir()
        if path.is_dir() and path.name not in {"_template", "published"} and not path.name.startswith(".")
    )
    # Published projects live one level deeper under projects/published/
    published_root = ROOT / "projects" / "published"
    published_dirs = sorted(
        p for p in (published_root.iterdir() if published_root.is_dir() else [])
        if p.is_dir() and not p.name.startswith(".")
    )

    projects = []
    for path in project_dirs:
        proj = project_stats(path, active_rows, totals["inbox_pdfs"])
        proj["is_published"] = False
        projects.append(proj)
    for path in published_dirs:
        proj = project_stats(path, active_rows, totals["inbox_pdfs"])
        proj["is_published"] = True
        proj["slug"] = path.name  # ensure slug is just the leaf
        proj["confidential"] = False  # cloud agents allowed
        projects.append(proj)
    category_rows = category_stats()
    total_candidates = sum(project["counts"]["candidate_jsons"] for project in projects)
    total_triage = sum(project["counts"]["triage_reports"] for project in projects)
    total_staged_drafts = sum(project["counts"]["staged_drafts"] for project in projects)
    total_final_drafts = sum(project["counts"]["final_drafts"] for project in projects)
    total_ready_for_verify = sum(project["draft_verification"]["ready_for_verify"] for project in projects)
    total_missing_claim_logs = sum(project["draft_verification"]["missing_claim_logs"] for project in projects)
    total_data_updates = sum(project["counts"]["data_updates"] for project in projects)
    total_critique_reports = sum(project["counts"]["critique_reports"] for project in projects)
    total_planned_figures = sum(project["counts"]["planned_figures"] for project in projects)
    projects_with_figure_plans = [
        project for project in projects
        if project["paper_in_prep"]["figure_plan_exists"]
    ]
    actions = build_actions(projects, totals, active_rows)
    public_projects = [project for project in projects if not project.get("confidential")]
    totals.update(
        {
            "project_folders": len(projects),
            "tracked_projects": sum(1 for project in public_projects if project["tracked"]),
            "untracked_projects": sum(1 for project in public_projects if not project["tracked"]),
            "candidates": total_candidates,
            "triage_reports": total_triage,
            "staged_drafts": total_staged_drafts,
            "final_drafts": total_final_drafts,
            "drafts_ready_for_verification": total_ready_for_verify,
            "drafts_missing_claim_logs": total_missing_claim_logs,
            "data_updates": total_data_updates,
            "critique_reports": total_critique_reports,
            "planned_figures": total_planned_figures,
            "projects_with_figure_plans": len(projects_with_figure_plans),
            "idea_notes": explorations["idea_notes"],
            "exploration_briefs": explorations["briefs"],
            "active_explorations": explorations["active"],
            "average_figure_progress": round(
                sum(project["paper_in_prep"]["figure_progress"]["percent"] for project in projects_with_figure_plans)
                / len(projects_with_figure_plans)
            ) if projects_with_figure_plans else 0,
            "average_project_progress": round(
                sum(project["progress"]["percent"] for project in projects) / len(projects)
            ) if projects else 0,
        }
    )
    return {
        "meta": {
            "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            "repo_path": str(ROOT),
            "generator": "scripts/build_dashboard.py",
        },
        "totals": totals,
        "projects": projects,
        "mendeley": mendeley_status(),
        "explorations": explorations,
        "scout_history": scout_history_index(),
        "wiki_search": wiki_search_index(),
        "categories": category_rows,
        "homework": homework_status(),
        "backup": backup_status(),
        "actions": actions,
        "today": build_today(actions, projects),
        "commands": build_command_templates(projects),
        "warnings": [
            "The dashboard is read-only. Edit markdown and project files directly, then rebuild.",
            "Legacy wiki category folders remain visible until you intentionally prune or migrate them.",
        ],
    }


def write_outputs(payload: dict) -> None:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = DASHBOARD_DIR / "dashboard.json"
    data_js_path = DASHBOARD_DIR / "data.js"
    formatted = json.dumps(payload, indent=2, ensure_ascii=False)
    json_path.write_text(formatted + "\n", encoding="utf-8")
    data_js_path.write_text(f"window.DASHBOARD_DATA = {formatted};\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    print(f"Wrote {relative(DASHBOARD_DIR / 'dashboard.json')} and {relative(DASHBOARD_DIR / 'data.js')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
