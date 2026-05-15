#!/usr/bin/env python3
"""Serve the dashboard with a small allowlisted local command API.

This replaces the plain `python3 -m http.server` workflow when you want the
dashboard to run safe local actions directly. It intentionally does not expose
an arbitrary shell. The browser sends an action id plus a project slug, and this
server reconstructs the command from a local allowlist.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import re
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "_system" / "dashboard" / "run-logs"
PROJECTS = ROOT / "projects"
TEMPLATES = PROJECTS / "_template"
EXPLORATIONS = ROOT / "explorations"
PAPERS = ROOT / "papers"
SCOUTS = ROOT / "scouts"
WIKI   = ROOT / "wiki"
LOCAL_AGENT_ROLES = {
    "local-planner": "planner",
    "local-drafter": "drafter",
    "local-argue": "argue",
    "local-demon": "demon",
    "local-rejection-sim": "rejection-sim",
    "local-scout-brief": "scout-brief",
}


def slugify(text: str) -> str:
    """Turn an arbitrary topic string into a filesystem-safe slug."""
    keep = []
    for ch in text.lower().strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in {" ", "-", "_", "/"}:
            keep.append("-")
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "topic"


def scout_slug(topic: str, year_start: str = "", year_end: str = "") -> str:
    slug = slugify(topic)
    years = "-".join(part for part in [year_start.strip(), year_end.strip()] if part)
    if years:
        slug = f"{slug}-{slugify(years)}"
    return slug or "topic"


def require_simple_slug(slug: str, label: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
        raise DashboardError(f"Invalid {label}: {slug!r}")
    return slug


def read_project_type(project: Path) -> str | None:
    """Parse `project_type:` out of Project_Brief.md frontmatter, if present."""
    brief = project / "Project_Brief.md"
    if not brief.exists():
        return None
    try:
        with brief.open("r", encoding="utf-8") as handle:
            in_fm = False
            for line in handle:
                line = line.rstrip("\n")
                if line.strip() == "---":
                    if not in_fm:
                        in_fm = True
                        continue
                    break
                if in_fm and line.lower().startswith("project_type:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def require_library_ingest(project: Path) -> None:
    """Reject scout/triage actions on confidential projects."""
    ptype = read_project_type(project)
    if ptype != "library_ingest":
        raise DashboardError(
            f"Scout cannot run on a confidential project (type={ptype!r}). "
            f"Open or update an explorations/idea-notes/{{topic}}.md and run "
            f"Quick Scout (or scout-exploration) instead."
        )


def require_confidential_project(project: Path) -> None:
    """Allow local-agent launches only for confidential project folders."""
    ptype = read_project_type(project)
    if ptype == "library_ingest":
        raise DashboardError(
            "Local LLM roles are only for confidential projects. "
            "Use the public scout/ingest actions for library_ingest workspaces."
        )


class DashboardError(Exception):
    """User-facing dashboard command error."""


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def ensure_inside_root(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise DashboardError(f"Path escapes repository root: {path}") from exc
    return resolved


def project_path(slug: str | None) -> Path:
    if not slug:
        raise DashboardError("Missing project_slug.")
    # Try projects/{slug} first, then projects/published/{slug}.
    candidates = [PROJECTS / slug, PROJECTS / "published" / slug]
    for candidate in candidates:
        if candidate.is_dir():
            return ensure_inside_root(candidate)
    raise DashboardError(f"Project folder does not exist: projects/{slug} or projects/published/{slug}")


def is_published_project(project: Path) -> bool:
    """Return True if project lives under projects/published/."""
    try:
        rel_parts = project.relative_to(PROJECTS).parts
    except ValueError:
        return False
    return len(rel_parts) >= 2 and rel_parts[0] == "published"


def active_exploration_path(slug: str | None) -> Path:
    if not slug:
        raise DashboardError("Missing exploration_slug.")
    safe_slug = require_simple_slug(slug, "exploration_slug")
    path = ensure_inside_root(EXPLORATIONS / "active" / safe_slug)
    if not path.is_dir():
        raise DashboardError(f"Active exploration folder does not exist: explorations/active/{safe_slug}")
    return path


def scout_request_path(slug: str | None) -> Path:
    if not slug:
        raise DashboardError("Missing scout_slug.")
    safe_slug = require_simple_slug(slug, "scout_slug")
    path = ensure_inside_root(SCOUTS / safe_slug)
    if not path.is_dir():
        raise DashboardError(f"Scout request folder does not exist: scouts/{safe_slug}")
    return path


def latest_approval_board(project: Path) -> Path | None:
    triage = project / "triage-reports"
    if not triage.exists():
        return None
    boards = sorted(triage.glob("*_approval-board.html"), key=lambda p: p.stat().st_mtime)
    return boards[-1] if boards else None


def copy_if_missing(src: Path, dst: Path) -> str:
    ensure_inside_root(src)
    ensure_inside_root(dst)
    if dst.exists():
        return f"kept existing {rel(dst)}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"created {rel(dst)}"


def open_path(path: Path) -> dict[str, Any]:
    target = ensure_inside_root(path)
    return run_process(["open", str(target)], timeout=30)


_STAGE_LABELS_DASH = {
    "brief": "Project Brief",
    "figure-flow": "Figure Flow",
    "data-needed": "Data Needed",
    "figure-plan": "Figure Plan",
}


def open_local_agent(role: str, project: Path, section: str = "") -> dict[str, Any]:
    """Open an interactive local-agent session in Terminal without blocking the dashboard."""
    require_confidential_project(project)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    section_tag = f"-{section}" if section else ""
    launcher = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-local-agent-{role}{section_tag}-{project.name}.command"
    section_flag = f" --section {section}" if section else ""
    if section:
        stage_label = _STAGE_LABELS_DASH.get(section, f"section: {section}")
        section_note = f" — target: {stage_label}"
    else:
        section_note = ""
    command = (
        "#!/bin/zsh\n"
        f"cd {json.dumps(str(ROOT))}\n"
        f"echo 'Local LLM agent launcher — role: {role}{section_note}'\n"
        "echo 'Keep LM Studio Local Server running at http://localhost:1234/v1 before using this session.'\n"
        "echo ''\n"
        f"{json.dumps(sys.executable)} scripts/local_agent.py --role {role} --project {json.dumps(project.name)}{section_flag}\n"
        "echo ''\n"
        "echo 'Session ended. You can close this Terminal window.'\n"
        "read -k 1 -s '?Press any key to close...'\n"
    )
    launcher.write_text(command, encoding="utf-8")
    launcher.chmod(0o700)
    result = run_process(["open", "-a", "Terminal", str(launcher)], timeout=30)
    result["stdout"] = (
        f"Opened Terminal launcher for local {role}{section_note}: {rel(launcher)}\n"
        "LM Studio must have Local Server running before the agent can connect."
    )
    result["reload_suggested"] = False
    return result


def open_terminal_runner(label: str, command_line: str, success_note: str = "") -> dict[str, Any]:
    """Open a Terminal window that runs an arbitrary local command and stays open after."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-") or "task"
    launcher = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_label}.command"
    script = (
        "#!/bin/zsh\n"
        f"cd {json.dumps(str(ROOT))}\n"
        f"echo '{label}'\n"
        "echo 'LM Studio Local Server (http://localhost:1234/v1) must be running.'\n"
        "echo ''\n"
        f"{command_line}\n"
        "echo ''\n"
        f"echo '{success_note or 'Done.'}'\n"
        "read -k 1 -s '?Press any key to close...'\n"
    )
    launcher.write_text(script, encoding="utf-8")
    launcher.chmod(0o700)
    result = run_process(["open", "-a", "Terminal", str(launcher)], timeout=30)
    result["stdout"] = f"Opened Terminal: {rel(launcher)}\n{success_note}"
    result["reload_suggested"] = False
    return result


def open_schematic_generator(project: Path) -> dict[str, Any]:
    require_confidential_project(project)
    py = json.dumps(sys.executable)
    slug = json.dumps(project.name)
    cmd = f"{py} scripts/generate_schematic.py --project {slug}"
    return open_terminal_runner(
        label=f"Generate schematic — {project.name}",
        command_line=cmd,
        success_note=f"Schematic written to projects/{project.name}/schematics/.",
    )


def open_figure_mockups_generator(project: Path, panel: str = "") -> dict[str, Any]:
    require_confidential_project(project)
    py = json.dumps(sys.executable)
    slug = json.dumps(project.name)
    panel_flag = f" --panel {json.dumps(panel)}" if panel else ""
    cmd = f"{py} scripts/generate_figure_mockups.py --project {slug}{panel_flag}"
    return open_terminal_runner(
        label=f"Generate figure mockups — {project.name}",
        command_line=cmd,
        success_note=f"Mockups written to projects/{project.name}/figure-mockups/.",
    )


def run_process(args: list[str], timeout: int = 300) -> dict[str, Any]:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    ended = datetime.now().astimezone().isoformat(timespec="seconds")
    log_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{Path(args[0]).name}.log"
    log_path.write_text(
        "\n".join(
            [
                f"started: {started}",
                f"ended: {ended}",
                f"cwd: {ROOT}",
                f"command: {' '.join(args)}",
                f"exit_code: {proc.returncode}",
                "",
                "STDOUT",
                proc.stdout,
                "",
                "STDERR",
                proc.stderr,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "command": " ".join(args),
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-6000:],
        "log": rel(log_path),
    }


def rebuild_dashboard() -> dict[str, Any]:
    return run_process([sys.executable, "scripts/build_dashboard.py"], timeout=120)


def auto_download_queue(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if not isinstance(payload, dict):
        raise DashboardError("Missing download queue payload.")
    report_dir_value = str(params.get("report_dir") or "_system/downloads").strip()
    report_dir = ensure_inside_root(ROOT / report_dir_value)
    queue_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-download-queue.json"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_process(
        [
            sys.executable,
            "scripts/auto_download_selected_pdfs.py",
            rel(queue_path),
            "--out",
            "papers/inbox",
            "--report-dir",
            rel(report_dir),
            "--action",
            "download",
        ],
        timeout=900,
    )


def handle_action(action_id: str, project_slug: str | None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    params = params or {}

    # ---- Homework actions ----
    if action_id.startswith("homework-"):
        return handle_homework_action(action_id, params)

    # ---- Backup actions ----
    if action_id.startswith("backup-"):
        return handle_backup_action(action_id, params)

    # ---- Duplicate check ----
    if action_id == "check-duplicates":
        candidates_rel = str(params.get("candidates_dir") or "").strip()
        if not candidates_rel:
            raise DashboardError("Missing candidates_dir for check-duplicates.")
        candidates_dir = ensure_inside_root(ROOT / candidates_rel)
        if not candidates_dir.exists():
            raise DashboardError(f"Candidates directory not found: {candidates_rel}")
        return run_process(
            [sys.executable, "scripts/check_duplicates.py",
             "--candidates", str(candidates_dir)],
            timeout=60,
        )

    # ---- Project scout (for confidential projects — keywords only, output to scouts/) ----
    if action_id == "project-scout":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        keywords = str(params.get("keywords") or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug for project-scout.")
        if not keywords:
            raise DashboardError("Missing keywords for project-scout. Provide topic keywords.")
        # Output goes to scouts/project-{slug}/ (public area — cloud can triage)
        scout_out_dir = ROOT / "scouts" / f"project-{slug_val}" / "candidates" / today
        scout_out_dir.mkdir(parents=True, exist_ok=True)
        return run_process(
            [sys.executable, "scripts/scout_all.py",
             "--topic", keywords,
             "--out", str(scout_out_dir)],
            timeout=900,
        )

    if action_id == "rebuild-dashboard":
        result = rebuild_dashboard()
        result["reload_suggested"] = result["ok"]
        return result

    # ---- Create a new confidential project ----
    if action_id == "create-project":
        slug = str(params.get("slug") or "").strip()
        ptype = str(params.get("project_type") or "paper_in_prep").strip()
        title = str(params.get("title") or "Working title").strip()
        valid_types = {"paper_in_prep", "review_article", "grant", "job_application"}
        if not slug:
            raise DashboardError("Missing project slug.")
        slug = require_simple_slug(slug, "project_slug")
        if ptype not in valid_types:
            raise DashboardError(f"Invalid project_type: {ptype!r}. Must be one of: {', '.join(sorted(valid_types))}")
        project_dir = PROJECTS / slug
        if project_dir.exists():
            raise DashboardError(f"Project already exists: projects/{slug}/")
        # Create folder structure
        (project_dir / "Drafts").mkdir(parents=True, exist_ok=True)
        (project_dir / "critiques" / "argue").mkdir(parents=True, exist_ok=True)
        (project_dir / "critiques" / "demon").mkdir(parents=True, exist_ok=True)
        (project_dir / "rejection-sims").mkdir(parents=True, exist_ok=True)
        (project_dir / "notes").mkdir(parents=True, exist_ok=True)
        (project_dir / "data-updates").mkdir(parents=True, exist_ok=True)
        # Write Project_Brief.md from template with type and title pre-filled
        brief_src = TEMPLATES / "Project_Brief.md"
        brief_dst = project_dir / "Project_Brief.md"
        if brief_src.exists():
            brief_content = brief_src.read_text(encoding="utf-8")
            # Patch frontmatter fields
            brief_content = brief_content.replace(
                "project_slug: short-kebab-case-name", f"project_slug: {slug}"
            )
            brief_content = brief_content.replace(
                "project_type: grant | paper_in_prep | review_article",
                f"project_type: {ptype}",
            )
            brief_content = brief_content.replace(
                'title: "Working title"', f'title: "{title}"'
            )
            brief_dst.write_text(brief_content, encoding="utf-8")
        else:
            brief_dst.write_text(
                f"---\nproject_slug: {slug}\nproject_type: {ptype}\n"
                f'title: "{title}"\nconfidential_tier: local-only\nstatus: active\n---\n\n'
                "# Project Brief\n\n## 1. Central Question\n\n## 2. Hypotheses or Aims\n\n"
                "## 3. Position Statement\n\n## 4. Scope Boundaries\n\n"
                "## 5. Required Evidence\n\n## 6. Output Mode\n\n## 7. Known Risks\n",
                encoding="utf-8",
            )
        # Copy optional template files
        always_copy = [
            ("Evidence_Map.md", "Evidence_Map.md"),
            ("Roadmap.md", "Roadmap.md"),
            ("Decision_Log.md", "Decision_Log.md"),
        ]
        paper_prep_extras = [
            ("figure-flow.md", "figure-flow.md"),
            ("data-needed.md", "data-needed.md"),
            ("figure-plan_TEMPLATE.md", "figure-plan.md"),
            ("experiment-roadmap_TEMPLATE.md", "experiment-roadmap.md"),
        ]
        copy_list = always_copy + (paper_prep_extras if ptype == "paper_in_prep" else [])
        for tmpl_name, dst_name in copy_list:
            tmpl = TEMPLATES / tmpl_name
            if tmpl.exists() and not (project_dir / dst_name).exists():
                shutil.copy2(tmpl, project_dir / dst_name)
        rebuild_dashboard()
        extras_note = (
            "\n  ✓ figure-flow.md and data-needed.md created (discuss with Planner)"
            if ptype == "paper_in_prep" else ""
        )
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"create-project {slug} ({ptype})",
            "stdout": (
                f"Created projects/{slug}/\n"
                f"  type: {ptype}\n"
                f"  title: {title}{extras_note}\n"
                f"  Edit Project_Brief.md to fill in aims and scope.\n"
                f"  Then run: python3 scripts/pre_drafter.py --project {slug} --keywords '...'\n"
                f"  Then run: python3 scripts/local_agent.py --role planner --project {slug}"
            ),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    # ---- Run pre-drafter wiki analysis ----
    if action_id == "pre-drafter":
        keywords = str(params.get("keywords") or "").strip()
        ptype = str(params.get("project_type") or "paper_in_prep").strip()
        top = int(params.get("top") or 30)
        if not project_slug:
            raise DashboardError("Missing project_slug for pre-drafter.")
        project = project_path(project_slug)
        require_confidential_project(project)
        if not keywords:
            raise DashboardError("Missing keywords for pre-drafter. Provide topic keywords separated by commas.")
        return run_process(
            [
                sys.executable,
                "scripts/pre_drafter.py",
                "--project", project.name,
                "--keywords", keywords,
                "--type", ptype,
                "--top", str(top),
            ],
            timeout=120,
        )

    if action_id == "open-obsidian":
        return run_process(["open", "-a", "Obsidian", str(ROOT)], timeout=30)

    # Quick Scout — creates an ad-hoc paper scout request and runs scout against it.
    if action_id == "scout-quick":
        topic = str(params.get("topic") or "").strip()
        if not topic:
            raise DashboardError("Missing topic for scout-quick.")
        year_start = str(params.get("year_start") or "").strip()
        year_end = str(params.get("year_end") or "").strip()
        slug = scout_slug(topic, year_start, year_end)
        if not slug or slug == "topic":
            slug = f"quick-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        request_dir = SCOUTS / slug
        request_dir.mkdir(parents=True, exist_ok=True)
        brief = request_dir / "Scout_Brief.md"
        if not brief.exists():
            year_range = f"{year_start}-{year_end}" if year_start and year_end else (year_start or year_end or "last 5 years")
            keywords = str(params.get("keywords") or topic).strip()
            brief.write_text(
                "---\n"
                f"slug: {slug}\n"
                "type: paper_scout\n"
                "confidential_tier: external-ok\n"
                f"created: {today}\n"
                "---\n\n"
                f"# Paper scout: {topic}\n\n"
                "## Must-include keywords\n\n"
                f"- {keywords}\n\n"
                "## Must-exclude keywords\n\n"
                "## Year range\n\n"
                f"{year_range}\n\n"
                "## Preferred journals/preprint servers\n\n",
                encoding="utf-8",
            )
        out = request_dir / "candidates" / today
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--brief",
                f"scouts/{slug}/Scout_Brief.md",
                "--out",
                f"scouts/{slug}/candidates/{today}",
            ],
            timeout=900,
        )

    # Import a Scopus CSV export as a new candidate batch.
    if action_id == "import-scopus-csv":
        csv_content = str(params.get("csv_content") or "").strip()
        target_slug = str(params.get("target_slug") or "").strip()
        topic       = str(params.get("topic") or target_slug or "scopus-import").strip()
        keywords    = str(params.get("keywords") or topic).strip()
        year_start  = str(params.get("year_start") or "").strip()
        year_end    = str(params.get("year_end") or "").strip()

        if not csv_content:
            raise DashboardError("No CSV content received.")

        # Resolve or create the scout folder
        if target_slug:
            slug = target_slug
        else:
            slug = scout_slug(topic, year_start, year_end) or f"scopus-{today}"
        request_dir = ensure_inside_root(SCOUTS / slug)
        request_dir.mkdir(parents=True, exist_ok=True)

        # Write Scout_Brief.md if it doesn't exist
        brief = request_dir / "Scout_Brief.md"
        if not brief.exists():
            year_range = f"{year_start}-{year_end}" if year_start and year_end else (year_start or year_end or "")
            brief.write_text(
                "---\n"
                f"slug: {slug}\n"
                "type: paper_scout\n"
                "source: scopus\n"
                "confidential_tier: external-ok\n"
                f"created: {today}\n"
                "---\n\n"
                f"# Paper scout: {topic}\n\n"
                "## Must-include keywords\n\n"
                f"- {keywords}\n\n"
                "## Must-exclude keywords\n\n"
                "## Year range\n\n"
                f"{year_range}\n\n"
                "## Preferred journals/preprint servers\n\n",
                encoding="utf-8",
            )

        # Write CSV to a temp file, then parse it
        import tempfile
        tmp_csv = Path(tempfile.mktemp(suffix=".csv"))
        try:
            tmp_csv.write_text(csv_content, encoding="utf-8-sig")
            out_dir = request_dir / "candidates" / today
            out_dir.mkdir(parents=True, exist_ok=True)
            result = run_process(
                [sys.executable, "scripts/parse_scopus_csv.py", "--csv", str(tmp_csv), "--out", str(out_dir)],
                timeout=60,
            )
        finally:
            tmp_csv.unlink(missing_ok=True)

        if result.get("ok"):
            result["slug"] = slug
            result["stdout"] = (result.get("stdout") or "") + f"\n\nScout folder: scouts/{slug}"
        return result

    # Run scout against an existing exploration's idea-note.
    if action_id == "scout-exploration":
        slug = str(params.get("exploration_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing exploration_slug for scout-exploration.")
        slug = require_simple_slug(slug, "exploration_slug")
        note = EXPLORATIONS / "idea-notes" / f"{slug}.md"
        if not note.exists():
            raise DashboardError(f"Exploration idea-note not found: explorations/idea-notes/{slug}.md")
        active_dir = EXPLORATIONS / "active" / slug
        out = active_dir / "candidates" / today
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--exploration",
                slug,
            ],
            timeout=900,
        )

    if action_id == "approval-board-exploration":
        slug = str(params.get("exploration_slug") or project_slug or "").strip()
        active = active_exploration_path(slug)
        return run_process(
            [
                sys.executable,
                "scripts/build_triage_approval_board.py",
                "--project",
                f"explorations/active/{active.name}",
            ],
            timeout=120,
        )

    if action_id == "open-approval-board-exploration":
        slug = str(params.get("exploration_slug") or project_slug or "").strip()
        active = active_exploration_path(slug)
        board = latest_approval_board(active)
        if board is None:
            build = handle_action("approval-board-exploration", active.name)
            if not build["ok"]:
                return build
            board = latest_approval_board(active)
        if board is None:
            raise DashboardError("No exploration approval board exists after build.")
        return open_path(board)

    if action_id == "approval-board-scout":
        slug = str(params.get("scout_slug") or project_slug or "").strip()
        scout = scout_request_path(slug)
        return run_process(
            [
                sys.executable,
                "scripts/build_triage_approval_board.py",
                "--project",
                f"scouts/{scout.name}",
            ],
            timeout=120,
        )

    if action_id == "open-approval-board-scout":
        slug = str(params.get("scout_slug") or project_slug or "").strip()
        scout = scout_request_path(slug)
        board = latest_approval_board(scout)
        if board is None:
            build = handle_action("approval-board-scout", scout.name)
            if not build["ok"]:
                return build
            board = latest_approval_board(scout)
        if board is None:
            raise DashboardError("No scout approval board exists after build.")
        return open_path(board)

    if action_id == "verify-publish":
        # Step 1: validate the proof before moving anything. Returns ok=True only if proof checks out.
        slug = str(params.get("project_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing project_slug.")
        src = PROJECTS / slug
        if not src.is_dir() or src.parent.name == "published":
            raise DashboardError(f"Project folder not found or already published: projects/{slug}")
        preprint_url = str(params.get("preprint_url") or "").strip()
        acceptance_path = str(params.get("acceptance_letter_path") or "").strip()
        if not preprint_url and not acceptance_path:
            raise DashboardError("Provide a preprint URL or an acceptance-letter PDF path.")

        verification: dict[str, Any] = {"preprint_url_ok": False, "acceptance_letter_ok": False}

        # Validate preprint URL: pattern + HEAD request
        if preprint_url:
            allowed_hosts = (
                "biorxiv.org", "medrxiv.org", "arxiv.org",
                "ssrn.com", "osf.io", "researchsquare.com",
                "chemrxiv.org", "preprints.org", "doi.org", "psyarxiv.com",
            )
            if not re.match(r"^https?://", preprint_url):
                raise DashboardError("Preprint URL must start with http:// or https://")
            if not any(host in preprint_url.lower() for host in allowed_hosts):
                raise DashboardError(
                    f"URL host not on the preprint allowlist: {', '.join(allowed_hosts)}"
                )
            import urllib.request
            import urllib.error
            try:
                req = urllib.request.Request(preprint_url, method="HEAD",
                                              headers={"User-Agent": "Mozilla/5.0 LLM-Wiki-Dashboard"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        raise DashboardError(f"Preprint URL returned HTTP {resp.status}.")
                verification["preprint_url_ok"] = True
                verification["preprint_url"] = preprint_url
            except urllib.error.HTTPError as e:
                # Some preprint servers reject HEAD or block scrapers — try GET
                if e.code in (403, 405, 429, 501):
                    try:
                        req = urllib.request.Request(preprint_url,
                                                      headers={"User-Agent": "Mozilla/5.0 LLM-Wiki-Dashboard"})
                        with urllib.request.urlopen(req, timeout=20) as resp:
                            resp.read(2048)
                            verification["preprint_url_ok"] = True
                            verification["preprint_url"] = preprint_url
                    except urllib.error.HTTPError as ge:
                        if ge.code in (403, 429):
                            # Anti-scraping — host is on the allowlist so trust the pattern
                            verification["preprint_url_ok"] = True
                            verification["preprint_url"] = preprint_url
                            verification["preprint_url_note"] = f"Host blocks automated requests (HTTP {ge.code}); allowlist host trusted."
                        else:
                            raise DashboardError(f"Preprint URL returned HTTP {ge.code}.")
                    except urllib.error.URLError as ge:
                        raise DashboardError(f"Preprint URL fetch failed: {ge.reason}")
                else:
                    raise DashboardError(f"Preprint URL returned HTTP {e.code}.")
            except urllib.error.URLError as e:
                raise DashboardError(f"Could not reach preprint URL: {e.reason}")

        # Validate acceptance letter PDF
        if acceptance_path:
            letter = Path(acceptance_path).expanduser()
            if not letter.is_absolute():
                # interpret as relative to repo root
                letter = (ROOT / acceptance_path).resolve()
            if not letter.is_file():
                raise DashboardError(f"Acceptance letter not found: {acceptance_path}")
            if letter.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
                raise DashboardError("Acceptance letter must be a PDF or image file.")
            if letter.stat().st_size > 25 * 1024 * 1024:
                raise DashboardError("Acceptance letter exceeds 25 MB.")
            verification["acceptance_letter_ok"] = True
            verification["acceptance_letter_resolved"] = str(letter)

        return {
            "ok": True,
            "exit_code": 0,
            "command": "verify-publish",
            "stdout": "Verification passed. You can now publish.",
            "stderr": "",
            "log": "",
            "verification": verification,
        }

    if action_id == "publish-project":
        # Step 2: actually move the project after verification has succeeded.
        slug = str(params.get("project_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing project_slug.")
        # Re-run verification so this endpoint can't be called without proof.
        verify = handle_action("verify-publish", slug, params)
        if not verify["ok"]:
            return verify
        preprint_url = str(params.get("preprint_url") or "").strip()
        journal = str(params.get("journal") or "").strip()
        notes = str(params.get("notes") or "").strip()
        biorxiv_doi = ""
        m = re.search(r"10\.\d{4,9}/[^\s\"<>]+", preprint_url)
        if m:
            biorxiv_doi = m.group(0).rstrip(".)")

        cmd = [sys.executable, "scripts/publish_project.py", "--project", slug]
        if biorxiv_doi:
            cmd += ["--biorxiv-doi", biorxiv_doi]
        if preprint_url:
            cmd += ["--biorxiv-url", preprint_url]
        if journal:
            cmd += ["--journal", journal]
        if notes:
            cmd += ["--notes", notes]
        result = run_process(cmd, timeout=60)

        # Copy the acceptance letter into the published folder if provided
        verification = verify.get("verification", {})
        if result["ok"] and verification.get("acceptance_letter_ok"):
            src_letter = Path(verification["acceptance_letter_resolved"])
            published_dir = PROJECTS / "published" / slug
            if published_dir.is_dir():
                dst = published_dir / f"acceptance-letter{src_letter.suffix.lower()}"
                shutil.copy2(src_letter, dst)
                result["stdout"] = (result.get("stdout") or "") + \
                    f"\nAcceptance letter saved to {dst.relative_to(ROOT)}"

        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "start-revision":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing project_slug.")
        # Source must live under projects/published/
        if not (PROJECTS / "published" / slug).is_dir():
            raise DashboardError(f"Published project not found: projects/published/{slug}")
        tag = str(params.get("revision_tag") or "r1").strip() or "r1"
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,15}", tag):
            raise DashboardError("revision_tag must be 1-16 chars, lowercase alphanumeric/_/-.")
        cmd = [sys.executable, "scripts/start_revision.py", "--published", slug, "--revision-tag", tag]
        result = run_process(cmd, timeout=120)
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "local-generate-schematic":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        return open_schematic_generator(project)

    if action_id == "local-generate-figure-mockups":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        panel = str(params.get("panel") or "").strip()
        return open_figure_mockups_generator(project, panel=panel)

    if action_id == "open-schematics-folder":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        target = project / "schematics"
        target.mkdir(parents=True, exist_ok=True)
        return open_path(target)

    if action_id == "open-figure-mockups-folder":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        target = project / "figure-mockups"
        target.mkdir(parents=True, exist_ok=True)
        return open_path(target)

    if action_id == "save-triage-criteria":
        criteria_text = str(params.get("criteria") or "").strip()
        target_type = str(params.get("target_type") or "scout").strip()  # "scout" | "exploration"
        target_slug = str(params.get("target_slug") or "").strip()
        if not criteria_text:
            raise DashboardError("No criteria text provided.")
        if not target_slug:
            raise DashboardError("No target scout/exploration slug provided.")
        # Resolve the directory
        if target_type == "exploration":
            target_dir = ensure_inside_root(EXPLORATIONS / "active" / target_slug)
        else:
            target_dir = ensure_inside_root(SCOUTS / target_slug)
        if not target_dir.exists():
            raise DashboardError(f"Folder not found: {target_dir.relative_to(ROOT)}")
        criteria_path = target_dir / "Triage_Criteria.md"
        criteria_path.write_text(criteria_text, encoding="utf-8")
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"write {rel(criteria_path)}",
            "stdout": f"Saved to {rel(criteria_path)}",
            "stderr": "",
            "log": "",
            "criteria_path": rel(criteria_path),
        }

    if action_id == "save-synthesis-brief":
        slug        = str(params.get("slug") or "synthesis").strip().replace(" ", "-")
        keywords    = str(params.get("keywords") or "").strip()
        output_path = str(params.get("output_path") or f"wiki/overviews/{slug}.md").strip()
        output_type = str(params.get("output_type") or "overview").strip()
        if not keywords:
            raise DashboardError("No keywords provided.")
        if output_type == "exploration":
            brief_path = ensure_inside_root(EXPLORATIONS / "active" / slug / "synthesis-brief.md")
        else:
            brief_path = ensure_inside_root(WIKI / "overviews" / f"{slug}-synthesis-brief.md")
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(
            f"---\nslug: {slug}\noutput: {output_path}\nstatus: draft\n---\n\n"
            f"# Synthesis Brief: {slug}\n\n## Keywords / Topic\n\n{keywords}\n\n"
            f"## Scope\n\n<!-- What this overview should cover -->\n\n"
            f"## Key Questions\n\n<!-- What questions should the synthesis answer? -->\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"write {rel(brief_path)}",
            "stdout": f"Saved to {rel(brief_path)}",
            "stderr": "",
            "log": "",
        }

    if action_id == "open-inbox":
        inbox = PAPERS / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        return open_path(inbox)

    if action_id == "import-local-pdfs":
        mode = str(params.get("mode") or "copy").strip().lower()
        if mode not in {"copy", "move"}:
            raise DashboardError("Import mode must be copy or move.")
        return run_process(
            [
                sys.executable,
                "scripts/import_local_pdfs_to_inbox.py",
                "--mode",
                mode,
            ],
            timeout=300,
        )

    if action_id == "auto-download-queue":
        return auto_download_queue(params)

    # ---- Fetch external info from URL ----
    if action_id == "fetch-external-info":
        url = str(params.get("url") or "").strip()
        info_type = str(params.get("info_type") or "general").strip()
        slug = str(params.get("slug") or project_slug or "").strip()
        max_chars = int(params.get("max_chars") or 12000)
        valid_types = {"grant_info", "job_description", "dept_faculty", "general"}
        if not url:
            raise DashboardError("Missing url for fetch-external-info.")
        if not slug:
            raise DashboardError("Missing slug for fetch-external-info.")
        if info_type not in valid_types:
            info_type = "general"
        return run_process(
            [
                sys.executable,
                "scripts/fetch_external_info.py",
                "--url", url,
                "--type", info_type,
                "--slug", slug,
                "--max-chars", str(max_chars),
            ],
            timeout=60,
        )

    # ---- Copy external info file to project folder ----
    if action_id == "copy-info-to-project":
        source_rel = str(params.get("source") or "").strip()
        dest_name = str(params.get("dest_name") or "").strip()
        if not source_rel or not project_slug:
            raise DashboardError("Missing source or project_slug for copy-info-to-project.")
        if not dest_name:
            raise DashboardError("Missing dest_name for copy-info-to-project.")
        source = ensure_inside_root(ROOT / source_rel)
        if not source.exists():
            raise DashboardError(f"Source file not found: {source_rel}")
        project = project_path(project_slug)
        dest = project / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"copy {source_rel} → projects/{project_slug}/{dest_name}",
            "stdout": f"Copied to projects/{project_slug}/{dest_name}\nThe local agent will load this file automatically.",
            "stderr": "",
            "log": "",
            "reload_suggested": False,
        }

    # ---- Convert draft to .docx ----
    if action_id == "export-docx":
        draft_rel = str(params.get("draft_path") or "").strip()
        track = params.get("track_changes", True)
        if not draft_rel:
            raise DashboardError("Missing draft_path for export-docx.")
        draft_path = ensure_inside_root(ROOT / draft_rel)
        if not draft_path.exists():
            raise DashboardError(f"Draft not found: {draft_rel}")
        extra = ["--no-track-changes"] if not track else []
        return run_process(
            [sys.executable, "scripts/convert_to_docx.py", str(draft_path)] + extra,
            timeout=60,
        )

    # ---- Open user-drafts folder for a project ----
    if action_id == "open-user-drafts":
        if not project_slug:
            raise DashboardError("Missing project_slug.")
        project = project_path(project_slug)
        ud = project / "user-drafts"
        ud.mkdir(parents=True, exist_ok=True)
        return open_path(ud)

    # ---- Open or create figure-flow.md for a project ----
    if action_id == "open-figure-flow":
        if not project_slug:
            raise DashboardError("Missing project_slug.")
        project = project_path(project_slug)
        ff = project / "figure-flow.md"
        if not ff.exists():
            template = TEMPLATES / "figure-flow.md"
            if template.exists():
                shutil.copy(template, ff)
            else:
                ff.write_text(
                    "---\nconfidential_tier: local-only\n---\n\n"
                    "# Figure Flow\n\n",
                    encoding="utf-8",
                )
        return open_path(ff)

    # ---- Open or create data-needed.md for a project ----
    if action_id == "open-data-needed":
        if not project_slug:
            raise DashboardError("Missing project_slug.")
        project = project_path(project_slug)
        dn = project / "data-needed.md"
        if not dn.exists():
            template = TEMPLATES / "data-needed.md"
            if template.exists():
                shutil.copy(template, dn)
            else:
                dn.write_text(
                    "---\nconfidential_tier: local-only\n---\n\n"
                    "# Data Needed\n\n",
                    encoding="utf-8",
                )
        return open_path(dn)

    # ---- Promote exploration to active + create project ----
    if action_id == "promote-exploration-to-project":
        exploration_slug = require_simple_slug(
            str(params.get("exploration_slug") or project_slug or "").strip(), "exploration_slug"
        )
        p_slug = require_simple_slug(
            str(params.get("project_slug") or exploration_slug).strip(), "project_slug"
        )
        p_type = str(params.get("project_type") or "paper_in_prep").strip()
        p_title = str(params.get("project_title") or "Working title").strip()
        keywords = str(params.get("keywords") or "").strip()
        valid_types = {"paper_in_prep", "review_article", "grant", "job_application"}
        if p_type not in valid_types:
            p_type = "paper_in_prep"

        # 1. Create active exploration folder
        active_dir = ensure_inside_root(EXPLORATIONS / "active" / exploration_slug)
        for sub in ["candidates", "paper-briefs", "_pdfs"]:
            (active_dir / sub).mkdir(parents=True, exist_ok=True)
        brief_src = EXPLORATIONS / "ideas" / f"Exploration_Brief_{exploration_slug}.md"
        brief_dst = active_dir / "Exploration_Brief.md"
        if brief_src.exists() and not brief_dst.exists():
            shutil.copy2(brief_src, brief_dst)
        readme_src = EXPLORATIONS / "_template" / "Active_Exploration_README_TEMPLATE.md"
        if readme_src.exists() and not (active_dir / "README.md").exists():
            shutil.copy2(readme_src, active_dir / "README.md")
        for fname in ["scout-queries.md", "notes.md", "questions.md", "synthesis.md",
                      "promote-to-wiki.md", "promote-to-project.md"]:
            fpath = active_dir / fname
            if not fpath.exists():
                fpath.touch()

        # 2. Create confidential project
        project_dir = PROJECTS / p_slug
        stdout_lines = [f"✓ explorations/active/{exploration_slug}/"]
        if not project_dir.exists():
            (project_dir / "Drafts").mkdir(parents=True, exist_ok=True)
            for sub in [("critiques", "argue"), ("critiques", "demon"),
                        ("rejection-sims",), ("notes",), ("data-updates",)]:
                (project_dir / Path(*sub)).mkdir(parents=True, exist_ok=True)
            brief_tmpl = TEMPLATES / "Project_Brief.md"
            brief_out = project_dir / "Project_Brief.md"
            if brief_tmpl.exists():
                content = brief_tmpl.read_text(encoding="utf-8")
                content = content.replace("project_slug: short-kebab-case-name", f"project_slug: {p_slug}")
                content = content.replace(
                    "project_type: grant | paper_in_prep | review_article", f"project_type: {p_type}"
                )
                content = content.replace('title: "Working title"', f'title: "{p_title}"')
                brief_out.write_text(content, encoding="utf-8")
            for tmpl_name, dst_name in [
                ("Evidence_Map.md", "Evidence_Map.md"),
                ("Roadmap.md", "Roadmap.md"),
                ("Decision_Log.md", "Decision_Log.md"),
            ]:
                t = TEMPLATES / tmpl_name
                if t.exists() and not (project_dir / dst_name).exists():
                    shutil.copy2(t, project_dir / dst_name)
            # Link note back to exploration
            link_note = project_dir / "notes" / "from-exploration.md"
            link_note.write_text(
                f"---\ncreated_from_exploration: {exploration_slug}\n---\n\n"
                f"# Promoted from exploration: {exploration_slug}\n\n"
                f"- explorations/active/{exploration_slug}/notes.md\n"
                f"- explorations/active/{exploration_slug}/synthesis.md\n",
                encoding="utf-8",
            )
            stdout_lines.append(f"✓ projects/{p_slug}/ ({p_type})")
        else:
            stdout_lines.append(f"  projects/{p_slug}/ already exists — skipped creation")

        rebuild_dashboard()

        # 3. Run wiki relevance scan in Terminal if keywords provided
        if keywords:
            result = open_terminal_runner(
                label=f"Wiki relevance — {p_slug}",
                command_line=(
                    f"{json.dumps(sys.executable)} scripts/pre_drafter.py "
                    f"--project {json.dumps(p_slug)} --keywords {json.dumps(keywords)}"
                ),
                success_note=f"Wiki context written to projects/{p_slug}/wiki_context.md",
            )
            result["stdout"] = "\n".join(stdout_lines) + "\n\n" + (result.get("stdout") or "")
            result["reload_suggested"] = True
            return result

        return {
            "ok": True,
            "exit_code": 0,
            "command": f"promote-exploration-to-project {exploration_slug} → {p_slug}",
            "stdout": "\n".join(stdout_lines) + "\n\nNext: add keywords → re-run for wiki relevance scan.",
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    # ---- Open local agent on the project linked to an exploration ----
    if action_id == "local-exploration-synthesis":
        p_slug = str(params.get("project_slug") or project_slug or "").strip()
        if not p_slug:
            raise DashboardError("Provide project_slug (the slug used when promoting this exploration).")
        p_dir = ensure_inside_root(PROJECTS / require_simple_slug(p_slug, "project_slug"))
        if not p_dir.exists():
            raise DashboardError(
                f"Project not found: projects/{p_slug}/. "
                "Promote the exploration first using 'Promote to active exploration + create project'."
            )
        return open_local_agent("drafter", p_dir)

    # ---- Export sanitized scout brief to cloud-readable scouts/ area ----
    if action_id == "export-scout-brief":
        p_slug = require_simple_slug(str(project_slug or "").strip(), "project_slug")
        p_dir  = ensure_inside_root(PROJECTS / p_slug)
        if not p_dir.exists():
            raise DashboardError(f"Project not found: projects/{p_slug}/")
        draft = p_dir / "notes" / "scout-brief.md"
        if not draft.exists():
            raise DashboardError(
                f"No scout brief at projects/{p_slug}/notes/scout-brief.md. "
                "Run the local Scout-Brief agent first, then /save."
            )
        content = draft.read_text(encoding="utf-8")
        # Require simulation_passed: true in frontmatter
        if "simulation_passed: true" not in content:
            raise DashboardError(
                "Export blocked: scout-brief.md does not contain 'simulation_passed: true'. "
                "The identity-leak simulation must pass before the file can leave the confidential zone."
            )
        # Additional safety: reject if project slug appears literally in the body
        body_after_fm = content.split("---", 2)[-1] if content.startswith("---") else content
        if p_slug.lower() in body_after_fm.lower():
            raise DashboardError(
                f"Export blocked: the project slug '{p_slug}' appears in the brief body. "
                "Remove all direct project references before exporting."
            )
        scout_target = ensure_inside_root(SCOUTS / f"project-{p_slug}")
        scout_target.mkdir(parents=True, exist_ok=True)
        (scout_target / "candidates").mkdir(exist_ok=True)
        export_path = scout_target / "Scout_Brief.md"
        shutil.copy2(draft, export_path)
        rebuild_dashboard()
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"export-scout-brief → scouts/project-{p_slug}/Scout_Brief.md",
            "stdout": (
                f"Exported to scouts/project-{p_slug}/Scout_Brief.md\n"
                "Cloud agents (Codex CLI, Scout) can now use this file.\n"
                "Run Quick Scout using the 'From project scout brief' selector."
            ),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    if action_id == "delete-scout-brief":
        # Delete scouts/{s_slug}/Scout_Brief.md after it has been used for scouting.
        # Keeps the candidates/ folder (keyword history). s_slug comes in as project_slug param.
        s_slug = str(project_slug or "").strip()
        if not s_slug:
            s_slug = str(params.get("scout_slug") or "").strip()
        if not s_slug:
            raise DashboardError("Missing scout_slug for delete-scout-brief.")
        scout_dir = ensure_inside_root(SCOUTS / s_slug)
        brief_file = scout_dir / "Scout_Brief.md"
        if not brief_file.exists():
            return {"ok": True, "exit_code": 0, "command": f"delete-scout-brief {s_slug}",
                    "stdout": "Scout brief already gone (nothing to delete).", "stderr": "", "log": "", "reload_suggested": True}
        brief_file.unlink()
        rebuild_dashboard()
        return {"ok": True, "exit_code": 0, "command": f"delete-scout-brief {s_slug}",
                "stdout": f"Deleted scouts/{s_slug}/Scout_Brief.md.\nKeyword history preserved in candidates/.",
                "stderr": "", "log": "", "reload_suggested": True}

    project = project_path(project_slug)
    slug = project.name

    if action_id in LOCAL_AGENT_ROLES:
        section = str(params.get("section") or "").strip()
        return open_local_agent(LOCAL_AGENT_ROLES[action_id], project, section=section)

    if action_id == "brief":
        ptype = read_project_type(project)
        if ptype and ptype != "library_ingest":
            raise DashboardError(
                f"This project is confidential (type={ptype!r}). Open Project_Brief.md "
                f"manually in your editor — the dashboard does not surface confidential briefs."
            )
        return open_path(project / "Project_Brief.md")

    if action_id == "queries":
        require_library_ingest(project)
        queries = project / "scout-queries.md"
        if not queries.exists():
            queries.write_text("# Scout Queries\n\n", encoding="utf-8")
        return open_path(queries)

    if action_id == "scout":
        require_library_ingest(project)
        out = project / "candidates" / today
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--brief",
                f"projects/{slug}/Project_Brief.md",
                "--out",
                f"projects/{slug}/candidates/{today}",
            ],
            timeout=900,
        )

    if action_id == "scout-campaign":
        require_library_ingest(project)
        out = project / "candidates" / f"{today}-campaign"
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--brief",
                f"projects/{slug}/Project_Brief.md",
                "--out",
                f"projects/{slug}/candidates/{today}-campaign",
                "--queries-only",
            ],
            timeout=900,
        )

    if action_id == "approval-board":
        require_library_ingest(project)
        return run_process(
            [sys.executable, "scripts/build_triage_approval_board.py", "--project", f"projects/{slug}"],
            timeout=120,
        )

    if action_id == "open-approval-board":
        require_library_ingest(project)
        board = latest_approval_board(project)
        if board is None:
            build = handle_action("approval-board", slug)
            if not build["ok"]:
                return build
            board = latest_approval_board(project)
        if board is None:
            raise DashboardError("No approval board exists after build.")
        return open_path(board)

    if action_id == "prep-files":
        require_library_ingest(project)
        messages = []
        (project / "data-updates").mkdir(parents=True, exist_ok=True)
        (project / "critiques").mkdir(parents=True, exist_ok=True)
        messages.append(copy_if_missing(TEMPLATES / "figure-plan_TEMPLATE.md", project / "figure-plan.md"))
        messages.append(copy_if_missing(TEMPLATES / "experiment-roadmap_TEMPLATE.md", project / "experiment-roadmap.md"))
        messages.append(copy_if_missing(TEMPLATES / "critique-log_TEMPLATE.md", project / "critiques" / "critique-log.md"))
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"create optional paper-in-prep files for projects/{slug}",
            "stdout": "\n".join(messages),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    if action_id == "data-update":
        require_library_ingest(project)
        dst = project / "data-updates" / f"{today}-fig-panel.md"
        message = copy_if_missing(TEMPLATES / "data-updates_TEMPLATE.md", dst)
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"create data update for projects/{slug}",
            "stdout": message,
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    raise DashboardError(f"Action is copy-only or not allowlisted: {action_id}")


# ---------------------------------------------------------------------------
# Homework helpers
# ---------------------------------------------------------------------------

HOMEWORK_PATH = ROOT / "_system" / "docs" / "homework.json"


def _load_homework() -> dict:
    default: dict = {"frequency_days": 14, "current": None, "completed": [], "skipped": []}
    if not HOMEWORK_PATH.exists():
        return default
    try:
        return json.loads(HOMEWORK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_homework(data: dict) -> None:
    HOMEWORK_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOMEWORK_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _pick_random_wiki_paper(exclude_stems: set[str]) -> dict | None:
    """Pick a random wiki paper (not an overview) not in exclude_stems."""
    import random
    wiki_dir = ROOT / "wiki"
    candidates = []
    if wiki_dir.exists():
        for cat_dir in wiki_dir.iterdir():
            if not cat_dir.is_dir() or cat_dir.name == "overviews":
                continue
            for md in cat_dir.glob("*.md"):
                if md.stem not in exclude_stems:
                    fm_title = None
                    try:
                        text = md.read_text(encoding="utf-8")
                        for line in text.split("\n")[1:20]:
                            if line.lower().startswith("title:"):
                                fm_title = line.split(":", 1)[1].strip().strip('"').strip("'")
                                break
                    except OSError:
                        pass
                    candidates.append({
                        "stem": md.stem,
                        "title": fm_title or md.stem,
                        "category": cat_dir.name,
                    })
    if not candidates:
        return None
    return random.choice(candidates)


def handle_homework_action(action_id: str, params: dict) -> dict:
    """Handle homework-* actions. Returns a standard result dict."""
    from datetime import date, timedelta

    hw = _load_homework()

    if action_id == "homework-set-period":
        days = int(str(params.get("days") or 14))
        if days not in {7, 14, 30}:
            raise DashboardError(f"Invalid period: {days}. Must be 7, 14, or 30.")
        hw["frequency_days"] = days
        _save_homework(hw)
        rebuild_dashboard()
        return {"ok": True, "exit_code": 0, "command": f"Set homework period to {days} days",
                "stdout": f"Homework period updated to every {days} days.", "stderr": "", "log": "",
                "reload_suggested": True}

    if action_id in {"homework-complete", "homework-skip"}:
        current = hw.get("current")
        if current:
            record = {**current, "action": action_id.split("-")[1],
                      "action_date": date.today().isoformat()}
            key = "completed" if action_id == "homework-complete" else "skipped"
            hw.setdefault(key, []).append(record)
        # Assign next
        done_stems = {p["stem"] for p in hw.get("completed", [])} | \
                     {p["stem"] for p in hw.get("skipped", [])}
        new_paper = _pick_random_wiki_paper(done_stems)
        if new_paper is None:
            # All done — reset skipped pool
            hw["skipped"] = []
            done_stems = {p["stem"] for p in hw.get("completed", [])}
            new_paper = _pick_random_wiki_paper(done_stems)
        if new_paper:
            assigned = date.today()
            due = assigned + timedelta(days=hw.get("frequency_days", 14))
            hw["current"] = {
                **new_paper,
                "assigned_date": assigned.isoformat(),
                "due_date": due.isoformat(),
            }
        else:
            hw["current"] = None
        _save_homework(hw)
        rebuild_dashboard()
        verb = "marked complete" if action_id == "homework-complete" else "skipped"
        paper_name = new_paper["title"] if new_paper else "none"
        return {"ok": True, "exit_code": 0, "command": action_id,
                "stdout": f"Paper {verb}. Next assignment: {paper_name}", "stderr": "", "log": "",
                "reload_suggested": True}

    if action_id == "homework-assign":
        # Force-assign a random new paper
        done_stems = {p["stem"] for p in hw.get("completed", [])} | \
                     {p["stem"] for p in hw.get("skipped", [])}
        new_paper = _pick_random_wiki_paper(done_stems)
        if new_paper is None:
            raise DashboardError("No wiki papers available to assign.")
        from datetime import date, timedelta
        assigned = date.today()
        due = assigned + timedelta(days=hw.get("frequency_days", 14))
        hw["current"] = {
            **new_paper,
            "assigned_date": assigned.isoformat(),
            "due_date": due.isoformat(),
        }
        _save_homework(hw)
        rebuild_dashboard()
        return {"ok": True, "exit_code": 0, "command": "homework-assign",
                "stdout": f"Assigned: {new_paper['title']} (due {due.isoformat()})",
                "stderr": "", "log": "", "reload_suggested": True}

    if action_id == "homework-start-session":
        # Create session folder for current homework paper via homework_manager.py
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "homework_manager.py"), "start-session"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        if result.returncode != 0:
            raise DashboardError(result.stderr.strip() or "homework-start-session failed")
        out = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
        session_dir = out.get("session_dir", "")
        existed = out.get("existed", False)
        rebuild_dashboard()
        msg = f"Session folder {'already exists' if existed else 'created'}: {session_dir}"
        return {"ok": True, "exit_code": 0, "command": "homework-start-session",
                "stdout": msg, "stderr": "", "log": "", "reload_suggested": True,
                "session_dir": session_dir}

    if action_id == "homework-open-session":
        session_dir_name = str(params.get("session_dir") or "")
        if not session_dir_name:
            raise DashboardError("session_dir param required")
        session_path = ROOT / session_dir_name
        if not session_path.exists() or not session_path.is_dir():
            raise DashboardError(f"Session dir not found: {session_dir_name}")
        subprocess.Popen(["open", str(session_path)])
        return {"ok": True, "exit_code": 0, "command": f"open {session_path}",
                "stdout": f"Opened {session_dir_name}", "stderr": "", "log": ""}

    if action_id == "homework-open-idea-wiki":
        idea_wiki_path = ROOT / "homework" / "idea-wiki"
        idea_wiki_path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(idea_wiki_path)])
        return {"ok": True, "exit_code": 0, "command": f"open {idea_wiki_path}",
                "stdout": "Opened idea-wiki folder", "stderr": "", "log": ""}

    if action_id == "homework-save-idea":
        idea_title = str(params.get("idea_title") or "").strip()
        source_stem = str(params.get("source_stem") or "").strip()
        idea_slug = str(params.get("idea_slug") or "").strip()
        session_date = str(params.get("session_date") or "").strip()
        if not idea_title or not source_stem:
            raise DashboardError("idea_title and source_stem are required")
        cmd_args = [
            sys.executable, str(ROOT / "scripts" / "homework_manager.py"),
            "save-idea",
            "--idea-title", idea_title,
            "--source-stem", source_stem,
        ]
        if idea_slug:
            cmd_args += ["--idea-slug", idea_slug]
        if session_date:
            cmd_args += ["--session-date", session_date]
        result = subprocess.run(cmd_args, capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            raise DashboardError(result.stderr.strip() or "homework-save-idea failed")
        out = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
        rebuild_dashboard()
        wiki_msg = " + wiki backlink added" if out.get("wiki_linked") else ""
        return {"ok": True, "exit_code": 0, "command": "homework-save-idea",
                "stdout": f"Idea saved to {out.get('idea_entry', 'idea-wiki')}{wiki_msg}",
                "stderr": "", "log": "", "reload_suggested": True}

    raise DashboardError(f"Unknown homework action: {action_id}")


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

def handle_backup_action(action_id: str, params: dict) -> dict[str, Any]:
    """Handle backup-* actions (restic-based). Returns a standard result dict."""

    def _parse_json_stdout(result: dict) -> dict:
        """Attach parsed JSON from stdout into result['data']."""
        if result.get("stdout"):
            try:
                result["data"] = json.loads(result["stdout"])
            except json.JSONDecodeError:
                pass
        return result

    if action_id == "backup-detect-gdrive":
        return _parse_json_stdout(
            run_process([sys.executable, "scripts/backup_manager.py", "detect-gdrive"], timeout=30)
        )

    if action_id == "backup-set-path":
        path = str(params.get("path") or "").strip()
        if not path:
            raise DashboardError("Missing path for backup-set-path.")
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "set-path", "--path", path],
            timeout=30,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-init-repo":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "init-repo"],
            timeout=120,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-run":
        dry_run = bool(params.get("dry_run"))
        cmd = [sys.executable, "scripts/backup_manager.py", "run-backup"]
        if dry_run:
            cmd.append("--dry-run")
        result = run_process(cmd, timeout=1800)
        if result["ok"] and not dry_run:
            rebuild_dashboard()
            result["reload_suggested"] = True
        # Parse restic JSON summary out of stdout for dashboard display
        if result.get("stdout"):
            for line in result["stdout"].splitlines():
                try:
                    obj = json.loads(line)
                    if obj.get("message_type") == "summary":
                        result["summary"] = obj
                        break
                except json.JSONDecodeError:
                    continue
        return result

    if action_id == "backup-snapshots":
        limit = int(params.get("limit") or 20)
        return _parse_json_stdout(
            run_process(
                [sys.executable, "scripts/backup_manager.py", "snapshots",
                 "--limit", str(limit)],
                timeout=60,
            )
        )

    if action_id == "backup-prune":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "prune"],
            timeout=600,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-install-schedule":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "install-schedule"],
            timeout=60,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-uninstall-schedule":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "uninstall-schedule"],
            timeout=30,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-open-folder":
        state_result = run_process(
            [sys.executable, "scripts/backup_manager.py", "status"], timeout=15
        )
        gdrive_path = ""
        if state_result.get("stdout"):
            try:
                gdrive_path = json.loads(state_result["stdout"]).get("gdrive_path", "")
            except json.JSONDecodeError:
                pass
        if not gdrive_path:
            raise DashboardError("Google Drive path not configured. Set it first.")
        backup_folder = Path(gdrive_path) / "LLM-Wiki-restic"
        subprocess.Popen(["open", str(backup_folder)])
        return {
            "ok": True, "exit_code": 0,
            "command": f"open {backup_folder}",
            "stdout": f"Opened {backup_folder}", "stderr": "", "log": "",
        }

    raise DashboardError(f"Unknown backup action: {action_id}")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # Allowed origins: only the dashboard itself (127.0.0.1 and localhost, same port).
    # This prevents arbitrary websites from sending API requests to the local server.
    _ALLOWED_ORIGINS = {
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    }

    def _cors_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        # Also allow file:// (no Origin header) and same-origin requests
        if not origin or origin in self._ALLOWED_ORIGINS:
            return origin or "http://127.0.0.1:8765"
        return ""   # denied — end_headers will send no Allow-Origin

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        allowed = self._cors_origin()
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", ""}:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/_system/dashboard/index.html")
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self.write_json({
                "ok": True,
                "interactive": True,
                "repo": str(ROOT),
                "allowed_actions": [
                    "rebuild-dashboard",
                    "stop-dashboard-server",
                    "open-obsidian",
                    "brief",
                    "queries",
                    "scout",
                    "scout-campaign",
                    "scout-exploration",
                    "scout-quick",
                    "approval-board-exploration",
                    "open-approval-board-exploration",
                    "approval-board-scout",
                    "open-approval-board-scout",
                    "open-inbox",
                    "import-local-pdfs",
                    "auto-download-queue",
                    "create-project",
                    "pre-drafter",
                    "fetch-external-info",
                    "copy-info-to-project",
                    "export-docx",
                    "open-user-drafts",
                    "open-figure-flow",
                    "open-data-needed",
                    "check-duplicates",
                    "save-triage-criteria",
                    "save-synthesis-brief",
                    "import-scopus-csv",
                    "project-scout",
                    "homework-assign",
                    "homework-complete",
                    "homework-skip",
                    "homework-set-period",
                    "homework-start-session",
                    "homework-open-session",
                    "homework-open-idea-wiki",
                    "homework-save-idea",
                    "backup-detect-gdrive",
                    "backup-set-path",
                    "backup-init-repo",
                    "backup-run",
                    "backup-snapshots",
                    "backup-prune",
                    "backup-install-schedule",
                    "backup-uninstall-schedule",
                    "backup-open-folder",
                    "local-planner",
                    "local-drafter",
                    "local-argue",
                    "local-demon",
                    "local-rejection-sim",
                    "local-generate-schematic",
                    "local-generate-figure-mockups",
                    "open-schematics-folder",
                    "open-figure-mockups-folder",
                    "verify-publish",
                    "publish-project",
                    "start-revision",
                    "approval-board",
                    "open-approval-board",
                    "prep-files",
                    "data-update",
                    "promote-exploration-to-project",
                    "local-exploration-synthesis",
                    "local-scout-brief",
                    "export-scout-brief",
                    "delete-scout-brief",
                ],
            })
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            action_id = str(payload.get("action_id") or "")
            project_slug = payload.get("project_slug")
            params = payload.get("params") if isinstance(payload.get("params"), dict) else None
            if not action_id:
                raise DashboardError("Missing action_id.")
            if action_id == "stop-dashboard-server":
                self.write_json({
                    "ok": True,
                    "exit_code": 0,
                    "command": "stop dashboard server",
                    "stdout": "Dashboard server is stopping. Restart with: python3 scripts/dashboard_server.py --port 8765",
                    "stderr": "",
                    "log": "",
                })
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            result = handle_action(action_id, str(project_slug) if project_slug else None, params)
            self.write_json(result)
        except subprocess.TimeoutExpired as exc:
            self.write_json({
                "ok": False,
                "exit_code": 124,
                "command": " ".join(exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd),
                "stdout": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
                "stderr": f"Timed out after {exc.timeout} seconds.",
                "log": "",
            }, status=HTTPStatus.REQUEST_TIMEOUT)
        except (DashboardError, FileNotFoundError, json.JSONDecodeError) as exc:
            self.write_json({
                "ok": False,
                "exit_code": 1,
                "command": "",
                "stdout": "",
                "stderr": str(exc),
                "log": "",
            }, status=HTTPStatus.BAD_REQUEST)

    def write_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the research dashboard with a local allowlisted command API.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", default=8765, type=int, help="Bind port. Default: 8765")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard server running at http://{args.host}:{args.port}/_system/dashboard/index.html")
    print("Only allowlisted local actions can run; Ctrl-C stops the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
