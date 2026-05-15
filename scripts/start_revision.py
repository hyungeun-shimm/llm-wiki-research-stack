#!/usr/bin/env python3
"""Start a revision project from a published project.

Creates projects/{slug}_revision/ as a fresh confidential workspace seeded
from projects/published/{slug}/. The revision project is local-only again
because the revision draft is unpublished.

Usage:
  python3 scripts/start_revision.py --published 2026-my-paper
  python3 scripts/start_revision.py --published 2026-my-paper --revision-tag r2
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
PUBLISHED = PROJECTS / "published"


def patch_brief_to_revision(brief_path: Path, original_slug: str, revision_slug: str,
                              revision_tag: str, started: str) -> None:
    """Flip the copied Project_Brief.md back to confidential and mark as revision."""
    if not brief_path.exists():
        return
    text = brief_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        end_idx = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end_idx is None:
            return
        fm_lines = lines[1:end_idx]
        rest = lines[end_idx + 1:]

        def upsert(key: str, value: str) -> None:
            new_line = f"{key}: {value}"
            for i, fl in enumerate(fm_lines):
                if fl.split(":", 1)[0].strip() == key:
                    fm_lines[i] = new_line
                    return
            fm_lines.append(new_line)

        upsert("confidential_tier", "local-only")
        upsert("status", "revision_in_progress")
        upsert("revises_published_project", original_slug)
        upsert("revision_tag", revision_tag)
        upsert("revision_started", started)
        # Remove publication metadata from the revision brief
        fm_lines = [fl for fl in fm_lines
                    if not fl.startswith(("published_date:", "biorxiv_doi:", "biorxiv_url:", "journal:"))]
        new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + "\n".join(rest)
        brief_path.write_text(new_text, encoding="utf-8")


def write_revision_readme(target: Path, original_slug: str, revision_tag: str, started: str) -> Path:
    readme = target / "REVISION.md"
    body = [
        "---",
        "confidential_tier: local-only",
        f"revises_published_project: {original_slug}",
        f"revision_tag: {revision_tag}",
        f"revision_started: {started}",
        "---",
        "",
        f"# Revision Project — {revision_tag}",
        "",
        f"This is a revision of the published project at `projects/published/{original_slug}/`.",
        "",
        "## Confidentiality",
        "",
        "Until the revision is also published, all content here is **confidential_tier: local-only**.",
        "Only the local LLM may read these files. Cloud agents must refuse.",
        "",
        "## Workflow",
        "",
        "- Original published version: `projects/published/" + original_slug + "/`",
        "- Drafts/, critiques/, and notes/ are reset for revision work but can reference the original.",
        "- When the revision is published, run `python3 scripts/publish_project.py --project " + target.name + "` to promote it.",
        "",
        "## Reviewer letter",
        "",
        "Create `reviewer-letter.md` here to draft your response to reviewers. The Argue agent can critique it before submission.",
    ]
    readme.write_text("\n".join(body) + "\n", encoding="utf-8")
    return readme


def reset_revision_subfolders(target: Path) -> None:
    """Clear staging folders so the revision starts clean. Original drafts remain visible
    through projects/published/{slug}/ for reference."""
    # Move existing Drafts to Drafts.original/ so the writer can reference but not overwrite.
    drafts = target / "Drafts"
    if drafts.exists() and any(drafts.iterdir()):
        archive = target / "Drafts.original"
        if not archive.exists():
            shutil.move(str(drafts), str(archive))
            drafts.mkdir(parents=True, exist_ok=True)
            (drafts / ".gitkeep").touch()
    # Clear critiques + rejection-sims (they were for the published version)
    for sub in ("critiques", "rejection-sims"):
        sub_path = target / sub
        if sub_path.exists():
            for child in sub_path.rglob("*"):
                if child.is_file():
                    child.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--published", required=True,
                        help="Slug of the published project (under projects/published/).")
    parser.add_argument("--revision-tag", default="r1", help="Short tag for this revision (default: r1).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src = PUBLISHED / args.published
    if not src.is_dir():
        raise SystemExit(f"Published project not found: projects/published/{args.published}")

    revision_slug = f"{args.published}_revision"
    if args.revision_tag and args.revision_tag != "r1":
        revision_slug = f"{args.published}_revision_{args.revision_tag}"
    target = PROJECTS / revision_slug
    if target.exists():
        raise SystemExit(f"Revision project already exists: projects/{revision_slug}")

    started = date.today().isoformat()

    if args.dry_run:
        print(json.dumps({
            "ok": True,
            "dry_run": True,
            "would_copy": f"{src.relative_to(ROOT)} -> {target.relative_to(ROOT)}",
            "revision_tag": args.revision_tag,
            "confidential_tier": "local-only",
        }, indent=2))
        return

    shutil.copytree(str(src), str(target))
    patch_brief_to_revision(target / "Project_Brief.md", args.published, revision_slug,
                              args.revision_tag, started)
    readme = write_revision_readme(target, args.published, args.revision_tag, started)
    reset_revision_subfolders(target)

    print(json.dumps({
        "ok": True,
        "revision_project": str(target.relative_to(ROOT)),
        "revision_readme": str(readme.relative_to(ROOT)),
        "confidential_tier": "local-only",
        "revises_published_project": args.published,
        "revision_started": started,
    }, indent=2))


if __name__ == "__main__":
    main()
