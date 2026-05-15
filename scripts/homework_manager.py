#!/usr/bin/env python3
"""Homework session and idea-wiki manager.

Actions:
  start-session   Create dated session folder with templates for current homework paper.
  save-idea       Save a new idea to homework/idea-wiki/ and back-link the wiki page.
  list-sessions   Print a JSON summary of all session folders.
  update-idea-status  Change status field in an existing idea-wiki entry.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOMEWORK_DIR = ROOT / "homework"
IDEA_WIKI_DIR = HOMEWORK_DIR / "idea-wiki"
TEMPLATE_DIR = HOMEWORK_DIR / "_template"
HOMEWORK_JSON = ROOT / "_system" / "docs" / "homework.json"
WIKI_DIR = ROOT / "wiki"


# ── helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    keep = []
    for ch in text.lower().strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in {" ", "-", "_"}:
            keep.append("-")
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "idea"


def load_homework() -> dict:
    default: dict = {"frequency_days": 14, "current": None, "completed": [], "skipped": []}
    if not HOMEWORK_JSON.exists():
        return default
    try:
        return json.loads(HOMEWORK_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def session_dir_name(session_date: str, stem: str) -> str:
    """e.g. 2026-05-13-zeeuw-2020-diversity-and-dynamism"""
    short_stem = "-".join(stem.split("-")[:6])  # keep stem readable but not huge
    return f"{session_date}-{short_stem}"


def fill_template(template_text: str, replacements: dict[str, str]) -> str:
    result = template_text
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


# ── start-session ─────────────────────────────────────────────────────────────

def cmd_start_session(args: argparse.Namespace) -> None:
    hw = load_homework()
    current = hw.get("current")
    if not current:
        print("ERROR: No homework paper currently assigned.", file=sys.stderr)
        sys.exit(1)

    stem: str = current["stem"]
    title: str = current.get("title", stem)
    category: str = current.get("category", "")
    session_date: str = current.get("assigned_date", date.today().isoformat())
    due_date: str = current.get("due_date", "")

    dir_name = session_dir_name(session_date, stem)
    session_dir = HOMEWORK_DIR / dir_name
    if session_dir.exists():
        print(f"Session folder already exists: {session_dir}")
        print(json.dumps({"session_dir": str(session_dir.relative_to(ROOT)), "existed": True}))
        return

    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "images").mkdir(exist_ok=True)

    replacements = {
        "STEM": stem,
        "TITLE": title,
        "CATEGORY": category,
        "YYYY-MM-DD": session_date,
        "DUE-DATE": due_date,
    }
    # notes.md
    for template_name in ("notes.md", "discussion-log.md", "ideas.md"):
        tmpl = TEMPLATE_DIR / template_name
        if tmpl.exists():
            content = fill_template(tmpl.read_text(encoding="utf-8"), {
                "STEM": stem, "TITLE": title, "CATEGORY": category,
                "YYYY-MM-DD": session_date,
            })
            # Fix the due_date line in notes.md
            if template_name == "notes.md":
                content = content.replace("due_date: \"YYYY-MM-DD\"", f"due_date: \"{due_date}\"")
            (session_dir / template_name).write_text(content, encoding="utf-8")

    result = {
        "session_dir": str(session_dir.relative_to(ROOT)),
        "session_date": session_date,
        "stem": stem,
        "title": title,
        "existed": False,
    }
    print(json.dumps(result))


# ── save-idea ────────────────────────────────────────────────────────────────

def cmd_save_idea(args: argparse.Namespace) -> None:
    idea_title: str = args.idea_title
    idea_slug: str = args.idea_slug or slugify(idea_title)
    source_stem: str = args.source_stem
    session_date: str = args.session_date or date.today().isoformat()

    # Find category from wiki
    category = _find_category_for_stem(source_stem)
    source_wiki = f"{category}/{source_stem}" if category else source_stem

    # Create idea-wiki entry
    IDEA_WIKI_DIR.mkdir(parents=True, exist_ok=True)
    entry_filename = f"{session_date}-{idea_slug}.md"
    entry_path = IDEA_WIKI_DIR / entry_filename

    tmpl = TEMPLATE_DIR / "idea-wiki-entry.md"
    if tmpl.exists():
        content = tmpl.read_text(encoding="utf-8")
        content = content.replace("IDEA TITLE", idea_title)
        content = content.replace("\"STEM\"", f"\"{source_stem}\"")
        content = content.replace("\"CATEGORY/STEM\"", f"\"{source_wiki}\"")
        content = content.replace("\"YYYY-MM-DD\"", f"\"{session_date}\"")
        content = content.replace("YYYY-MM-DD: Idea captured", f"{session_date}: Idea captured")
        content = content.replace("[[CATEGORY/STEM]]", f"[[{source_wiki}]]")
        content = content.replace("Homework session: YYYY-MM-DD", f"Homework session: {session_date}")
    else:
        content = _default_idea_entry(idea_title, source_stem, source_wiki, session_date)

    entry_path.write_text(content, encoding="utf-8")

    # Update idea-wiki index.md
    _update_idea_index(idea_title, entry_filename, source_stem, session_date)

    # Back-link in wiki page
    wiki_linked = _add_wiki_backlink(source_stem, category, idea_title, entry_filename, session_date)

    result = {
        "idea_entry": str(entry_path.relative_to(ROOT)),
        "wiki_linked": wiki_linked,
        "source_stem": source_stem,
        "category": category,
    }
    print(json.dumps(result))


def _find_category_for_stem(stem: str) -> str:
    if WIKI_DIR.exists():
        for cat_dir in WIKI_DIR.iterdir():
            if not cat_dir.is_dir():
                continue
            if (cat_dir / f"{stem}.md").exists():
                return cat_dir.name
    return "other"


def _update_idea_index(idea_title: str, entry_filename: str, source_stem: str, session_date: str) -> None:
    index_path = IDEA_WIKI_DIR / "index.md"
    if not index_path.exists():
        return
    content = index_path.read_text(encoding="utf-8")
    link = f"[[idea-wiki/{entry_filename[:-3]}]]"
    new_row = f"| {session_date} | {link} | {source_stem} | `seed` | — |"
    content = content.replace("<!-- ideas-table-end -->", f"{new_row}\n<!-- ideas-table-end -->")
    index_path.write_text(content, encoding="utf-8")


def _add_wiki_backlink(stem: str, category: str, idea_title: str, entry_filename: str, session_date: str) -> bool:
    """Append a homework-notes backlink to wiki/{category}/{stem}.md."""
    wiki_path = WIKI_DIR / category / f"{stem}.md"
    if not wiki_path.exists():
        return False

    content = wiki_path.read_text(encoding="utf-8")
    idea_link = f"[[homework/idea-wiki/{entry_filename[:-3]}]]"
    new_line = f"- {session_date}: {idea_link} — \"{idea_title}\""

    if "## Homework Notes" in content:
        # Insert before the closing marker or at end of section
        if "<!-- homework-ideas-end -->" in content:
            content = content.replace(
                "<!-- homework-ideas-end -->",
                f"{new_line}\n<!-- homework-ideas-end -->"
            )
        else:
            # Append to the section
            content = content + f"\n{new_line}"
    else:
        # Add the section at the end
        section = (
            "\n\n## Homework Notes\n\n"
            "<!-- homework-ideas-start -->\n"
            f"{new_line}\n"
            "<!-- homework-ideas-end -->"
        )
        content = content.rstrip() + section + "\n"

    wiki_path.write_text(content, encoding="utf-8")
    return True


def _default_idea_entry(title: str, stem: str, source_wiki: str, session_date: str) -> str:
    return f"""---
title: "{title}"
source_paper_stem: "{stem}"
source_wiki: "{source_wiki}"
homework_session: "{session_date}"
date: "{session_date}"
status: seed
linked_exploration: null
linked_project: null
tags: []
---

# {title}

## The Idea

## What Sparked It

## Why It Might Matter

## Open Questions

## Status Notes

- {session_date}: Idea captured from reading session.

---

*Source: [[{source_wiki}]] | Homework session: {session_date}*
"""


# ── list-sessions ─────────────────────────────────────────────────────────────

def cmd_list_sessions(args: argparse.Namespace) -> None:
    sessions = _gather_sessions()
    print(json.dumps(sessions, indent=2))


def _gather_sessions() -> list[dict]:
    sessions = []
    if not HOMEWORK_DIR.exists():
        return sessions
    for d in sorted(HOMEWORK_DIR.iterdir(), reverse=True):
        if not d.is_dir() or d.name.startswith("_") or d.name == "idea-wiki":
            continue
        # Parse date from dir name: YYYY-MM-DD-stem
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", d.name)
        if not m:
            continue
        session_date, stem_part = m.group(1), m.group(2)
        notes_exists = (d / "notes.md").exists()
        discussion_exists = (d / "discussion-log.md").exists()
        ideas_exists = (d / "ideas.md").exists()
        # Count idea-wiki entries from this session
        idea_count = len(list(IDEA_WIKI_DIR.glob(f"{session_date}-*.md"))) if IDEA_WIKI_DIR.exists() else 0
        # Read title from notes.md frontmatter
        title = stem_part
        if notes_exists:
            try:
                text = (d / "notes.md").read_text(encoding="utf-8")
                for line in text.split("\n")[1:10]:
                    if line.lower().startswith("paper_title:"):
                        title = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
            except OSError:
                pass
        sessions.append({
            "dir": str(d.relative_to(ROOT)),
            "dir_name": d.name,
            "session_date": session_date,
            "title": title,
            "has_notes": notes_exists,
            "has_discussion": discussion_exists,
            "has_ideas": ideas_exists,
            "idea_count": idea_count,
        })
    return sessions


# ── update-idea-status ────────────────────────────────────────────────────────

def cmd_update_idea_status(args: argparse.Namespace) -> None:
    entry = IDEA_WIKI_DIR / args.filename
    if not entry.exists():
        print(f"ERROR: {entry} not found", file=sys.stderr)
        sys.exit(1)

    content = entry.read_text(encoding="utf-8")
    # Update status in frontmatter
    new_status = args.status
    content = re.sub(r"^status: \S+", f"status: {new_status}", content, flags=re.MULTILINE)

    if args.linked_exploration:
        content = re.sub(
            r"^linked_exploration: .+",
            f"linked_exploration: \"{args.linked_exploration}\"",
            content, flags=re.MULTILINE
        )
    if args.linked_project:
        content = re.sub(
            r"^linked_project: .+",
            f"linked_project: \"{args.linked_project}\"",
            content, flags=re.MULTILINE
        )

    entry.write_text(content, encoding="utf-8")
    print(json.dumps({"updated": str(entry.relative_to(ROOT)), "status": new_status}))


# ── gather-idea-wiki ─────────────────────────────────────────────────────────

def cmd_gather_idea_wiki(args: argparse.Namespace) -> None:
    ideas = []
    if IDEA_WIKI_DIR.exists():
        for md in sorted(IDEA_WIKI_DIR.glob("*.md"), reverse=True):
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
                                    "linked_exploration", "linked_project", "homework_session"):
                            if line.lower().startswith(f"{key}:"):
                                entry[key] = line.split(":", 1)[1].strip().strip('"').strip("'")
            except OSError:
                pass
            ideas.append(entry)
    print(json.dumps(ideas, indent=2))


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Homework session and idea-wiki manager.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("start-session", help="Create session folder for current homework paper.")

    p_idea = sub.add_parser("save-idea", help="Save an idea to idea-wiki and back-link wiki page.")
    p_idea.add_argument("--idea-title", required=True, help="Short descriptive title for the idea.")
    p_idea.add_argument("--idea-slug", default="", help="URL-safe slug (auto-generated if omitted).")
    p_idea.add_argument("--source-stem", required=True, help="Paper stem (e.g. zeeuw-2020-diversity-and-dynamism-in-the).")
    p_idea.add_argument("--session-date", default="", help="Session date YYYY-MM-DD (defaults to today).")

    sub.add_parser("list-sessions", help="List all homework sessions as JSON.")

    p_status = sub.add_parser("update-idea-status", help="Update status of an idea-wiki entry.")
    p_status.add_argument("--filename", required=True, help="Idea-wiki filename (e.g. 2026-05-13-my-idea.md).")
    p_status.add_argument("--status", required=True, choices=["seed", "developing", "promoted", "archived"])
    p_status.add_argument("--linked-exploration", default="", help="Exploration slug if promoted.")
    p_status.add_argument("--linked-project", default="", help="Project slug if promoted.")

    sub.add_parser("gather-idea-wiki", help="Print idea-wiki entries as JSON.")

    args = parser.parse_args()
    dispatch = {
        "start-session": cmd_start_session,
        "save-idea": cmd_save_idea,
        "list-sessions": cmd_list_sessions,
        "update-idea-status": cmd_update_idea_status,
        "gather-idea-wiki": cmd_gather_idea_wiki,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
