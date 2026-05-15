#!/usr/bin/env python3
"""Promote a confidential project to projects/published/.

When a paper is at least on bioRxiv, run this to move the project from
projects/{slug}/ to projects/published/{slug}/. The published folder is
treated as confidential_tier: external-ok, so cloud agents (Claude Code,
Codex CLI, Claude web via copy-paste prompts) may work on it.

Usage:
  python3 scripts/publish_project.py --project 2026-my-paper --biorxiv-doi 10.1101/2026.01.01.123456
  python3 scripts/publish_project.py --project 2026-my-paper --dry-run
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


def update_brief_frontmatter(brief_path: Path, biorxiv_doi: str, biorxiv_url: str,
                              journal: str, published_date: str) -> None:
    """Update Project_Brief.md frontmatter: flip confidential_tier and add publication metadata."""
    if not brief_path.exists():
        return
    text = brief_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        # No frontmatter — prepend one
        fm_block = [
            "---",
            "confidential_tier: external-ok",
            "status: published",
            f"published_date: {published_date}",
        ]
        if biorxiv_doi:
            fm_block.append(f"biorxiv_doi: {biorxiv_doi}")
        if biorxiv_url:
            fm_block.append(f"biorxiv_url: {biorxiv_url}")
        if journal:
            fm_block.append(f"journal: {journal}")
        fm_block.append("---")
        brief_path.write_text("\n".join(fm_block) + "\n\n" + text, encoding="utf-8")
        return

    # Has frontmatter — patch keys
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return

    fm_lines = lines[1:end_idx]
    rest = lines[end_idx + 1:]

    def upsert(fm: list[str], key: str, value: str) -> list[str]:
        new_line = f"{key}: {value}"
        for i, fl in enumerate(fm):
            if fl.split(":", 1)[0].strip() == key:
                fm[i] = new_line
                return fm
        fm.append(new_line)
        return fm

    fm_lines = upsert(fm_lines, "confidential_tier", "external-ok")
    fm_lines = upsert(fm_lines, "status", "published")
    fm_lines = upsert(fm_lines, "published_date", published_date)
    if biorxiv_doi:
        fm_lines = upsert(fm_lines, "biorxiv_doi", biorxiv_doi)
    if biorxiv_url:
        fm_lines = upsert(fm_lines, "biorxiv_url", biorxiv_url)
    if journal:
        fm_lines = upsert(fm_lines, "journal", journal)

    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + "\n".join(rest)
    brief_path.write_text(new_text, encoding="utf-8")


def write_publication_record(target: Path, biorxiv_doi: str, biorxiv_url: str,
                              journal: str, notes: str, published_date: str) -> Path:
    """Create projects/published/{slug}/PUBLICATION.md with public-record metadata."""
    rec = target / "PUBLICATION.md"
    body = [
        "---",
        f"published_date: {published_date}",
        f"biorxiv_doi: {biorxiv_doi}" if biorxiv_doi else "biorxiv_doi: \"\"",
        f"biorxiv_url: {biorxiv_url}" if biorxiv_url else "biorxiv_url: \"\"",
        f"journal: {journal}" if journal else "journal: \"\"",
        "confidential_tier: external-ok",
        "---",
        "",
        "# Publication Record",
        "",
        f"- **Published date:** {published_date}",
    ]
    if biorxiv_doi:
        body.append(f"- **bioRxiv DOI:** [{biorxiv_doi}](https://doi.org/{biorxiv_doi})")
    if biorxiv_url:
        body.append(f"- **bioRxiv URL:** {biorxiv_url}")
    if journal:
        body.append(f"- **Journal / Venue:** {journal}")
    body.append("")
    body.append("## Notes")
    body.append(notes or "Project moved from confidential to published layer. Cloud LLMs may now read this folder.")
    body.append("")
    body.append("## How to start a revision")
    body.append("")
    body.append("Run `python3 scripts/start_revision.py --published " + target.name + "` to create a confidential revision project at `projects/" + target.name + "_revision/`.")
    rec.write_text("\n".join(body) + "\n", encoding="utf-8")
    return rec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Slug of the confidential project to promote.")
    parser.add_argument("--biorxiv-doi", default="", help="bioRxiv DOI (e.g. 10.1101/2026.01.01.123456).")
    parser.add_argument("--biorxiv-url", default="", help="bioRxiv URL.")
    parser.add_argument("--journal", default="", help="Journal name (optional).")
    parser.add_argument("--notes", default="", help="Free-text notes for PUBLICATION.md.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src = PROJECTS / args.project
    if not src.is_dir():
        raise SystemExit(f"Source project not found: projects/{args.project}")
    if src.parent.name == "published":
        raise SystemExit("Project is already inside projects/published/.")

    PUBLISHED.mkdir(parents=True, exist_ok=True)
    target = PUBLISHED / args.project
    if target.exists():
        raise SystemExit(f"Target already exists: {target.relative_to(ROOT)}")

    published_date = date.today().isoformat()

    if args.dry_run:
        print(json.dumps({
            "ok": True,
            "dry_run": True,
            "would_move": f"{src.relative_to(ROOT)} -> {target.relative_to(ROOT)}",
            "would_flip_tier": "local-only -> external-ok",
            "published_date": published_date,
        }, indent=2))
        return

    shutil.move(str(src), str(target))
    update_brief_frontmatter(target / "Project_Brief.md", args.biorxiv_doi,
                              args.biorxiv_url, args.journal, published_date)
    rec_path = write_publication_record(target, args.biorxiv_doi, args.biorxiv_url,
                                          args.journal, args.notes, published_date)

    print(json.dumps({
        "ok": True,
        "moved_to": str(target.relative_to(ROOT)),
        "publication_record": str(rec_path.relative_to(ROOT)),
        "confidential_tier": "external-ok",
        "published_date": published_date,
    }, indent=2))


if __name__ == "__main__":
    main()
