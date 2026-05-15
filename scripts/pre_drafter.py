#!/usr/bin/env python3
"""Pre-drafter wiki analyzer — cloud-safe, runs before the local LLM session.

Scans all wiki/ and sources/ pages for relevance to a project topic and writes
a ranked evidence summary to projects/{slug}/wiki_context.md.

This script reads ONLY PUBLIC wiki content (wiki/, sources/).
It never reads Project_Brief.md or any confidential project file.
The output is loaded automatically by local_agent.py planner and drafter roles.

Usage:
    python3 scripts/pre_drafter.py --project SLUG --keywords "keyword1, keyword2"
    python3 scripts/pre_drafter.py --project SLUG --type review_article --keywords "..."
    python3 scripts/pre_drafter.py --project SLUG --keywords "..." --top 25
    python3 scripts/pre_drafter.py --project SLUG --keywords "..." --min-score 3
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
SOURCES = ROOT / "sources"
PROJECTS = ROOT / "projects"


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body) from a markdown string."""
    fm: dict[str, str] = {}
    if not text.startswith("---"):
        return fm, text
    lines = text.split("\n")
    closing = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = idx
            break
    if closing is None:
        return fm, text
    for line in lines[1:closing]:
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip().lower()] = val.strip().strip('"').strip("'")
    body = "\n".join(lines[closing + 1:]).strip()
    return fm, body


def score_page(title: str, body: str, fm: dict[str, str], keywords: list[str]) -> int:
    """Return a relevance score based on keyword hits. Higher = more relevant."""
    if not keywords:
        return 0
    title_lower = title.lower()
    body_lower = body.lower()
    fm_text = " ".join(fm.values()).lower()
    score = 0
    for kw in keywords:
        kw = kw.lower().strip()
        if not kw:
            continue
        # Title match: strongest signal
        if kw in title_lower:
            score += 6
        # Tags and category match
        if kw in fm.get("tags", "").lower() or kw in fm.get("category", "").lower():
            score += 4
        # Frontmatter summary / one-line-summary
        for field in ("summary", "one-line summary", "one_line_summary"):
            if kw in fm.get(field, "").lower():
                score += 3
        # Body match: count occurrences (capped)
        hits = min(body_lower.count(kw), 5)
        score += hits
    return score


def extract_summary(body: str, max_chars: int = 350) -> str:
    """Extract the first meaningful sentence or paragraph from the body."""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and len(stripped) > 50:
            if len(stripped) > max_chars:
                return stripped[:max_chars] + "..."
            return stripped
    clean = body.strip()
    return clean[:max_chars] + ("..." if len(clean) > max_chars else "")


# ---------------------------------------------------------------------------
# Wiki and source scanning
# ---------------------------------------------------------------------------

def scan_wiki_pages(keywords: list[str]) -> list[dict]:
    """Scan wiki/ folder for relevant pages."""
    pages = []
    for path in sorted(WIKI.rglob("*.md")):
        if path.name in {"index.md", "README.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = strip_frontmatter(text)
        title = fm.get("title", path.stem.replace("-", " ").title())
        score = score_page(title, body, fm, keywords)
        if score == 0:
            continue
        category = path.parent.name
        rel_path = str(path.relative_to(ROOT))
        pages.append({
            "path": rel_path,
            "stem": path.stem,
            "category": category,
            "title": title,
            "authors": fm.get("authors", ""),
            "year": fm.get("year", ""),
            "doi": fm.get("doi", ""),
            "tags": fm.get("tags", ""),
            "summary": extract_summary(body),
            "score": score,
            "source_type": "wiki",
        })
    return pages


def scan_source_pages(keywords: list[str]) -> list[dict]:
    """Scan sources/ for relevant pages (richer summaries than wiki pages)."""
    pages = []
    for path in sorted(SOURCES.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = strip_frontmatter(text)
        title = fm.get("title", path.stem.replace("-", " ").title())
        score = score_page(title, body, fm, keywords)
        if score == 0:
            continue
        rel_path = str(path.relative_to(ROOT))
        pages.append({
            "path": rel_path,
            "stem": path.stem,
            "category": fm.get("category", "other"),
            "title": title,
            "authors": fm.get("authors", ""),
            "year": fm.get("year", ""),
            "doi": fm.get("doi", ""),
            "tags": fm.get("tags", ""),
            "summary": extract_summary(body),
            "score": score,
            "source_type": "source",
        })
    return pages


def dedup_pages(pages: list[dict]) -> list[dict]:
    """Deduplicate: when wiki and source share a stem, keep higher score (usually wiki)."""
    best: dict[str, dict] = {}
    for p in pages:
        stem = p["stem"]
        existing = best.get(stem)
        if existing is None or p["score"] > existing["score"]:
            best[stem] = p
    return sorted(best.values(), key=lambda x: -x["score"])


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _page_entry(p: dict, rank: int) -> str:
    meta_parts = []
    if p.get("authors"):
        # Truncate long author lists
        authors = p["authors"]
        meta_parts.append(authors[:80] + ("..." if len(authors) > 80 else ""))
    if p.get("year"):
        meta_parts.append(p["year"])
    meta_str = " | ".join(meta_parts) if meta_parts else "—"
    tags_str = f"\n- **Tags**: `{p['tags']}`" if p.get("tags") else ""
    link_stem = p["stem"]
    link_cat = p.get("category", "other")
    wiki_link = f"[[{link_cat}/{link_stem}]]" if p["source_type"] == "wiki" else f"`{p['path']}`"
    return (
        f"### {rank}. {p['title']} (score: {p['score']})\n\n"
        f"- **Wiki link**: {wiki_link}\n"
        f"- **Authors/Year**: {meta_str}{tags_str}\n"
        f"- **Excerpt**: _{p['summary']}_\n\n"
    )


def _build_standard_report(pages: list[dict], top: int) -> str:
    """Ranked list for paper_in_prep — grouped by category."""
    top_pages = pages[:top]
    by_cat: dict[str, list[dict]] = {}
    for p in top_pages:
        by_cat.setdefault(p["category"], []).append(p)

    sections = [f"## Top {len(top_pages)} Relevant Wiki Pages\n\n"]
    rank = 1
    for cat in sorted(by_cat, key=lambda c: -max(p["score"] for p in by_cat[c])):
        sections.append(f"### Category: `{cat}`\n\n")
        for p in by_cat[cat]:
            sections.append(_page_entry(p, rank))
            rank += 1

    # Quick-paste wiki links
    sections.append("---\n\n## Quick Wiki Links for Evidence_Map.md\n\n")
    for p in top_pages:
        if p["source_type"] == "wiki":
            sections.append(f"- [[{p['category']}/{p['stem']}]] — {p['title']} ({p.get('year', '')})\n")

    return "".join(sections)


def _build_review_report(pages: list[dict], top: int) -> str:
    """For review articles: thematic grouping + scaffolding suggestion."""
    top_pages = pages[:top]
    by_cat: dict[str, list[dict]] = {}
    for p in top_pages:
        by_cat.setdefault(p["category"], []).append(p)

    sections = [
        "## Thematic Evidence Map — Review Article\n\n",
        "_Use this to plan section/subtopic groupings before the local Planner session._\n\n",
    ]

    rank = 1
    # Sort categories by total score
    for cat in sorted(by_cat, key=lambda c: -sum(p["score"] for p in by_cat[c])):
        cat_pages = by_cat[cat]
        cat_score = sum(p["score"] for p in cat_pages)
        sections.append(
            f"## Theme: **{cat.replace('-', ' ').title()}** "
            f"({len(cat_pages)} paper{'s' if len(cat_pages) != 1 else ''}, "
            f"total relevance: {cat_score})\n\n"
        )
        for p in cat_pages:
            sections.append(_page_entry(p, rank))
            rank += 1

    sections.append("---\n\n## Suggested Section Scaffolding\n\n")
    sections.append("_Discuss and refine with the local Planner before drafting._\n\n")
    for i, (cat, cat_pages) in enumerate(
        sorted(by_cat.items(), key=lambda x: -len(x[1])), start=1
    ):
        sections.append(
            f"{i}. **{cat.replace('-', ' ').title()}** "
            f"— {len(cat_pages)} paper{'s' if len(cat_pages) != 1 else ''} available\n"
        )

    return "".join(sections)


def _build_grant_report(pages: list[dict], top: int) -> str:
    """For grants: evidence ranked, plus evidence-gap template."""
    top_pages = pages[:top]
    sections = [
        "## Wiki Evidence — Grant Application\n\n",
        f"Found {len(top_pages)} relevant pages. Use this to populate Evidence_Map.md "
        "and identify coverage gaps before writing Specific Aims.\n\n",
    ]

    rank = 1
    for p in top_pages:
        sections.append(_page_entry(p, rank))
        rank += 1

    sections.append("---\n\n## Evidence Gap Audit\n\n")
    sections.append(
        "Review the pages above against your Specific Aims. "
        "Fill in any claims that are NOT supported by the list above.\n\n"
        "| Claim / Aim | Supporting Page | Status |\n"
        "|---|---|---|\n"
        "| Aim 1 — [fill] | [[category/stem]] | ✓ covered / ✗ gap |\n"
        "| Aim 2 — [fill] | | ✗ gap — needs new data or paper |\n"
    )

    return "".join(sections)


def _build_job_report(pages: list[dict], top: int) -> str:
    """For job applications: evidence supporting research narrative + synergy context."""
    top_pages = pages[:top]
    by_cat: dict[str, list[dict]] = {}
    for p in top_pages:
        by_cat.setdefault(p["category"], []).append(p)

    sections = [
        "## Wiki Evidence — Job Application Research Statement\n\n",
        "Use this to build the research narrative: past work → current project → future directions.\n\n",
    ]

    rank = 1
    for cat in sorted(by_cat, key=lambda c: -sum(p["score"] for p in by_cat[c])):
        sections.append(f"### Research Area: `{cat.replace('-', ' ').title()}`\n\n")
        for p in by_cat[cat]:
            sections.append(_page_entry(p, rank))
            rank += 1

    sections.append("---\n\n## Research Narrative Scaffolding\n\n")
    sections.append(
        "1. **Past work** — What have you established?\n"
        "   - Key papers: [list from above]\n\n"
        "2. **Current project** — What are you doing now?\n"
        "   - Builds on: [list wiki sources]\n\n"
        "3. **Future directions** — What will you do at the new institution?\n"
        "   - New collaborations: [add department faculty synergies]\n\n"
        "4. **Department synergies** — Who could you collaborate with?\n"
        "   - _Run `fetch-dept-faculty` from dashboard to compile a faculty research map_\n"
    )

    return "".join(sections)


def build_report(pages: list[dict], keywords: list[str], project_type: str, top: int) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    kw_str = ", ".join(keywords)
    total = len(pages)
    shown = min(top, total)

    header = (
        "---\n"
        f"generated: {today}\n"
        f'keywords: "{kw_str}"\n'
        f"project_type: {project_type}\n"
        f"total_candidates: {total}\n"
        f"shown: {shown}\n"
        "confidential_tier: local-only\n"
        "---\n\n"
        "# Wiki Evidence Context\n\n"
        f"> Auto-generated by `scripts/pre_drafter.py` on {today}.  \n"
        f"> Keywords: **{kw_str}**  \n"
        "> Reads public wiki/sources only. Safe for local agent to load.\n\n"
        f"**{total} relevant pages found. Showing top {shown} by relevance.**\n\n"
        "---\n\n"
    )

    if not pages:
        return header + "_No matching pages found. Check your keywords and re-run._\n"

    dispatch = {
        "paper_in_prep": _build_standard_report,
        "review_article": _build_review_report,
        "grant": _build_grant_report,
        "job_application": _build_job_report,
    }
    builder = dispatch.get(project_type, _build_standard_report)
    return header + builder(pages, top)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = ArgumentParser(
        description=(
            "Scan public wiki/sources for project-relevant pages. "
            "Writes projects/{slug}/wiki_context.md for local agent consumption."
        ),
    )
    parser.add_argument("--project", required=True, metavar="SLUG",
                        help="Project folder name under projects/.")
    parser.add_argument("--keywords", required=True, metavar="KEYWORDS",
                        help="Comma-separated topic keywords (public description of the project).")
    parser.add_argument(
        "--type", dest="project_type",
        choices=["paper_in_prep", "review_article", "grant", "job_application"],
        default="paper_in_prep",
        help="Project type — controls report structure. Default: paper_in_prep",
    )
    parser.add_argument("--top", type=int, default=30,
                        help="Max pages to include in the report. Default: 30")
    parser.add_argument("--min-score", type=int, default=1, dest="min_score",
                        help="Minimum relevance score to include a page. Default: 1")
    args = parser.parse_args()

    # Validate project folder exists
    project_dir = (PROJECTS / args.project).resolve()
    try:
        project_dir.relative_to(PROJECTS)
    except ValueError:
        sys.exit(f"Invalid project slug: {args.project!r}")
    if not project_dir.is_dir():
        sys.exit(f"Project folder not found: projects/{args.project}/")

    # Parse keywords
    keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
    if not keywords:
        sys.exit("No keywords provided. Example: --keywords 'your-topic, method, key-term'")

    print(f"Scanning wiki and sources for: {', '.join(keywords)}")
    print(f"Project type: {args.project_type}")

    # Scan
    wiki_pages = scan_wiki_pages(keywords)
    source_pages = scan_source_pages(keywords)
    all_pages = dedup_pages(wiki_pages + source_pages)
    all_pages = [p for p in all_pages if p["score"] >= args.min_score]

    print(
        f"  {len(wiki_pages)} wiki pages, {len(source_pages)} source pages → "
        f"{len(all_pages)} unique above threshold (min-score={args.min_score})"
    )

    # Build and write report
    report = build_report(all_pages, keywords, args.project_type, args.top)
    output_path = project_dir / "wiki_context.md"
    output_path.write_text(report, encoding="utf-8")

    print(f"\n✓ Written: projects/{args.project}/wiki_context.md")
    print(f"  {min(args.top, len(all_pages))} pages included.")
    print()
    print("Next steps:")
    print(f"  1. Review the file: open projects/{args.project}/wiki_context.md")
    print(f"  2. Start planner:   python3 scripts/local_agent.py --role planner  --project {args.project}")
    print(f"  3. Start drafter:   python3 scripts/local_agent.py --role drafter  --project {args.project}")


if __name__ == "__main__":
    main()
