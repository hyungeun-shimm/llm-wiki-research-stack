#!/usr/bin/env python3
"""Resolve [[wikilinks]] citation placeholders to (Author, Year) inline format.

Scans a draft file for all [[category/stem]] and [[stem]] wikilinks, looks up
the corresponding sources/{stem}.md frontmatter, and replaces each placeholder
with (FirstAuthorLastName, Year).  Unresolvable links are left as-is and reported.

Usage:
    python3 scripts/resolve_citations.py projects/{slug}/Drafts/{section}-v1.draft.md
    python3 scripts/resolve_citations.py draft.md --output cited-draft.md
    python3 scripts/resolve_citations.py draft.md --inplace
    python3 scripts/resolve_citations.py draft.md --report-only
"""

from __future__ import annotations

import re
import sys
from argparse import ArgumentParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict[str, str]:
    """Return a flat {field: value} dict from YAML frontmatter (simple scalar values)."""
    result: dict[str, str] = {}
    if not text.startswith("---"):
        return result
    lines = text.split("\n")
    closing = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = idx
            break
    if closing is None:
        return result
    for line in lines[1:closing]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip().lower()] = value.strip().strip('"').strip("'")
    return result


def extract_first_author_last_name(authors_str: str) -> str:
    """Extract last name of first author.

    Expected format: "FirstName LastName, FirstName LastName, FirstName LastName"
    (space-separated name parts, authors separated by commas)
    """
    if not authors_str:
        return ""
    # Split by comma to get authors, take first
    first_author = authors_str.strip().split(",")[0].strip()
    # Last word of first author's name string
    parts = first_author.split()
    return parts[-1] if parts else first_author


# ---------------------------------------------------------------------------
# Sources lookup
# ---------------------------------------------------------------------------

def stem_from_link(link_text: str) -> str:
    """Extract the file stem from a wikilink path.

    [[topic-b/author-2006-some-title]] → author-2006-some-title
    [[boyden-2006-some-title]] → boyden-2006-some-title
    """
    # Remove any leading category prefix (everything before the last /)
    return link_text.strip().split("/")[-1].strip()


def resolve_link(link_text: str) -> tuple[str, bool]:
    """Resolve a wikilink text to a citation string.

    Returns (citation_string, was_resolved).
    citation_string = "(Author, Year)" on success, or the original [[...]] on failure.
    """
    stem = stem_from_link(link_text)
    source_path = SOURCES_DIR / f"{stem}.md"

    if not source_path.exists():
        return f"[[{link_text}]]", False

    try:
        text = source_path.read_text(encoding="utf-8")
    except OSError:
        return f"[[{link_text}]]", False

    fm = _parse_frontmatter(text)
    authors = fm.get("authors", "")
    year = fm.get("year", "")

    if not authors and not year:
        return f"[[{link_text}]]", False

    last_name = extract_first_author_last_name(authors)
    if last_name and year:
        return f"({last_name}, {year})", True
    elif last_name:
        return f"({last_name})", True
    elif year:
        return f"({year})", True
    return f"[[{link_text}]]", False


# ---------------------------------------------------------------------------
# Main resolution pass
# ---------------------------------------------------------------------------

WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")


def resolve_all(text: str) -> tuple[str, list[str], list[str]]:
    """Replace all [[wikilinks]] in text with (Author, Year) citations.

    Returns:
        resolved_text:   The text with placeholders replaced.
        resolved:        List of wikilinks that were successfully resolved.
        unresolved:      List of wikilinks that could not be resolved (kept as-is).
    """
    resolved: list[str] = []
    unresolved: list[str] = []

    def replacer(m: re.Match) -> str:
        link_text = m.group(1)
        citation, ok = resolve_link(link_text)
        if ok:
            resolved.append(link_text)
        else:
            unresolved.append(link_text)
        return citation

    resolved_text = WIKILINK_RE.sub(replacer, text)
    return resolved_text, resolved, unresolved


def resolve_file(
    input_path: Path,
    output_path: Path | None = None,
    inplace: bool = False,
    report_only: bool = False,
    verbose: bool = True,
) -> tuple[Path | None, list[str], list[str]]:
    """Resolve citations in a draft file.

    Returns (output_path, resolved_list, unresolved_list).
    output_path is None when report_only=True.
    """
    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    resolved_text, resolved, unresolved = resolve_all(text)

    if verbose:
        total = len(resolved) + len(unresolved)
        print(f"Wikilinks found: {total}  |  resolved: {len(resolved)}  |  unresolved: {len(unresolved)}")
        if resolved:
            print("\nResolved:")
            for r in resolved:
                print(f"  [[{r}]] → {resolve_link(r)[0]}")
        if unresolved:
            print("\nUnresolved (no matching sources/{stem}.md):")
            for u in unresolved:
                print(f"  [[{u}]]  — sources/{stem_from_link(u)}.md not found")

    if report_only:
        return None, resolved, unresolved

    if inplace:
        output_path = input_path
    elif output_path is None:
        # Default: add -cited suffix before the extension
        stem = input_path.stem
        suffix = input_path.suffix
        output_path = input_path.with_name(f"{stem}-cited{suffix}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(resolved_text, encoding="utf-8")

    if verbose:
        rel = output_path.relative_to(ROOT) if ROOT in output_path.parents else output_path
        print(f"\n✓ Saved: {rel}")

    return output_path, resolved, unresolved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = ArgumentParser(
        description=(
            "Resolve [[wikilinks]] in a draft to (Author, Year) citations. "
            "Looks up sources/{stem}.md frontmatter to extract first author and year."
        ),
    )
    parser.add_argument("input", metavar="DRAFT.md",
                        help="Path to the draft markdown file.")
    parser.add_argument("--output", metavar="OUTPUT.md",
                        help="Output path. Default: {stem}-cited.md in the same directory.")
    parser.add_argument("--inplace", action="store_true",
                        help="Edit the file in-place (overwrites input).")
    parser.add_argument("--report-only", action="store_true", dest="report_only",
                        help="Only report which links resolve — do not write output.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve() if args.output else None

    if args.inplace and args.output:
        sys.exit("Cannot use both --inplace and --output.")

    _, resolved, unresolved = resolve_file(
        input_path,
        output_path=output_path,
        inplace=args.inplace,
        report_only=args.report_only,
    )

    if unresolved:
        print(
            f"\nTip: For each unresolved link, either ingest the paper "
            f"(so sources/{{stem}}.md exists) or correct the wikilink spelling."
        )
        sys.exit(1)  # Non-zero exit so callers can detect unresolved links


if __name__ == "__main__":
    main()
