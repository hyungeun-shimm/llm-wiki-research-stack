#!/usr/bin/env python3
"""
check_duplicates.py — Check candidate paper JSONs against the existing wiki library.

Usage:
    python3 scripts/check_duplicates.py --candidates scouts/{slug}/candidates/2026-05-13/
    python3 scripts/check_duplicates.py --candidates projects/{slug}/candidates/ --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"
PAPERS_DIR = ROOT / "papers"

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "its",
    "it", "this", "that", "these", "those", "we", "our", "their", "via",
    "into", "through", "during", "using", "between", "among", "under",
    "over", "within", "without", "than", "also", "both", "not", "no",
}


def normalize_doi(doi: str) -> str:
    """Normalize DOI to lowercase stripped string."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    # Strip URL prefixes
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi


def significant_words(text: str) -> set:
    """Extract significant words from text for Jaccard comparison."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def jaccard(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def read_frontmatter(md_path: Path) -> dict:
    """Extract YAML frontmatter fields from a markdown file (stdlib only)."""
    fields = {}
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fields

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fields

    in_front = False
    for i, line in enumerate(lines):
        if i == 0:
            in_front = True
            continue
        if line.strip() == "---":
            break
        if in_front:
            m = re.match(r'^(\w[\w_-]*):\s*"?([^"]*)"?\s*$', line)
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def build_library_index() -> tuple[set, list[dict]]:
    """
    Build index of existing papers.

    Returns:
        doi_set: set of normalized DOIs already in the library
        title_records: list of {"title": str, "words": set, "path": str}
    """
    doi_set: set[str] = set()
    title_records: list[dict] = []

    # --- sources/*.md ---
    for md_file in SOURCES_DIR.glob("*.md"):
        fm = read_frontmatter(md_file)
        doi = normalize_doi(fm.get("doi", ""))
        if doi:
            doi_set.add(doi)
        title = fm.get("title", "")
        if title:
            title_records.append({
                "title": title,
                "words": significant_words(title),
                "path": str(md_file.relative_to(ROOT)),
            })

    # --- papers/*.pdf stem parsing ---
    for pdf_file in PAPERS_DIR.glob("*.pdf"):
        stem = pdf_file.stem  # e.g. "pollard-2006-an-rna-gene-expressed-during"
        parts = stem.split("-")
        # Reconstruct approximate title words from stem (words after year)
        # stem format: {author}-{year}-{word1}-{word2}-...
        if len(parts) >= 3:
            year_idx = None
            for i, p in enumerate(parts):
                if re.fullmatch(r"\d{4}", p):
                    year_idx = i
                    break
            if year_idx is not None and year_idx + 1 < len(parts):
                title_words_from_stem = set(parts[year_idx + 1:])
                title_records.append({
                    "title": " ".join(parts[year_idx + 1:]),
                    "words": {w for w in title_words_from_stem if len(w) >= 3 and w not in STOPWORDS},
                    "path": str(pdf_file.relative_to(ROOT)),
                })

    return doi_set, title_records


def check_candidates(candidates_dir: Path, library_dois: set, library_titles: list[dict],
                     threshold: float = 0.75) -> list[dict]:
    """
    Check each candidate JSON against the library.

    Returns list of result dicts with keys:
        file, title, doi, status, match_type, matched_path, title_score
    """
    results = []
    candidate_files = sorted(candidates_dir.glob("*.json"))

    if not candidate_files:
        return results

    for cand_path in candidate_files:
        try:
            cand = json.loads(cand_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            results.append({
                "file": cand_path.name,
                "title": "",
                "doi": "",
                "status": "ERROR",
                "match_type": f"parse error: {e}",
                "matched_path": "",
                "title_score": 0.0,
            })
            continue

        cand_doi = normalize_doi(cand.get("doi", ""))
        cand_title = cand.get("title", "")
        cand_words = significant_words(cand_title)

        status = "NEW"
        match_type = ""
        matched_path = ""
        best_score = 0.0

        # 1. DOI match
        if cand_doi and cand_doi in library_dois:
            status = "DUPLICATE"
            match_type = "doi"
        else:
            # 2. Title similarity
            for rec in library_titles:
                score = jaccard(cand_words, rec["words"])
                if score > best_score:
                    best_score = score
                    if score >= threshold:
                        matched_path = rec["path"]

            if best_score >= threshold:
                status = "LIKELY_DUPLICATE"
                match_type = "title"

        results.append({
            "file": cand_path.name,
            "title": cand_title,
            "doi": cand.get("doi", ""),
            "status": status,
            "match_type": match_type,
            "matched_path": matched_path,
            "title_score": round(best_score, 3),
        })

    return results


def print_report(results: list[dict], candidates_dir: Path) -> None:
    """Print human-readable report."""
    counts = {"DUPLICATE": 0, "LIKELY_DUPLICATE": 0, "NEW": 0, "ERROR": 0}

    print(f"\nDuplicate check — candidates: {candidates_dir}\n")
    print(f"{'FILE':<40} {'STATUS':<20} {'DETAIL'}")
    print("-" * 90)

    for r in results:
        status = r["status"]
        counts[status] = counts.get(status, 0) + 1

        if status == "DUPLICATE":
            detail = f"doi match"
        elif status == "LIKELY_DUPLICATE":
            detail = f"title score={r['title_score']:.3f}  matched: {r['matched_path']}"
        elif status == "ERROR":
            detail = r["match_type"]
        else:
            detail = ""

        print(f"{r['file']:<40} {status:<20} {detail}")

    print("\n" + "=" * 90)
    print(f"Summary: {counts.get('DUPLICATE', 0)} DUPLICATE  |  "
          f"{counts.get('LIKELY_DUPLICATE', 0)} LIKELY_DUPLICATE  |  "
          f"{counts.get('NEW', 0)} NEW  |  "
          f"{counts.get('ERROR', 0)} ERROR")
    print(f"Total candidates checked: {len(results)}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check candidate paper JSONs against the existing wiki library."
    )
    parser.add_argument(
        "--candidates",
        required=True,
        type=Path,
        help="Path to directory containing candidate JSON files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON (for dashboard integration).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Jaccard title-similarity threshold for LIKELY_DUPLICATE (default: 0.75).",
    )
    args = parser.parse_args()

    candidates_dir = args.candidates
    if not candidates_dir.is_dir():
        print(f"ERROR: --candidates path is not a directory: {candidates_dir}", file=sys.stderr)
        sys.exit(1)

    # Build library index
    library_dois, library_titles = build_library_index()

    # Check candidates
    results = check_candidates(candidates_dir, library_dois, library_titles, args.threshold)

    if not results:
        msg = f"No candidate JSON files found in: {candidates_dir}"
        if args.output_json:
            print(json.dumps({"error": msg, "results": [], "summary": {}}))
        else:
            print(msg)
        sys.exit(0)

    if args.output_json:
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        output = {
            "candidates_dir": str(candidates_dir),
            "threshold": args.threshold,
            "summary": {
                "total": len(results),
                "DUPLICATE": counts.get("DUPLICATE", 0),
                "LIKELY_DUPLICATE": counts.get("LIKELY_DUPLICATE", 0),
                "NEW": counts.get("NEW", 0),
                "ERROR": counts.get("ERROR", 0),
            },
            "results": results,
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(results, candidates_dir)


if __name__ == "__main__":
    main()
