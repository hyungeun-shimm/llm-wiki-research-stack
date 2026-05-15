"""Parse a Scopus CSV export and write candidate JSON files.

Usage:
    python3 scripts/parse_scopus_csv.py --csv path/to/scopus.csv --out scouts/{slug}/candidates/{date}/

Column mapping handles Scopus default export column names (full and abbreviated).
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Scopus exports columns under slightly different names depending on export settings.
# Map each canonical field to the list of Scopus column headers it might appear under.
COLUMN_MAP = {
    "title":    ["Title", "Document Title"],
    "authors":  ["Authors", "Author(s)", "Author Names"],
    "year":     ["Year", "Publication Year", "Cover Date"],
    "doi":      ["DOI"],
    "abstract": ["Abstract"],
    "source":   ["Source title", "Source Title", "Publication Name"],
    "eid":      ["EID"],
    "pubmed_id":["PubMed ID", "PMID"],
    "link":     ["Link", "URL"],
    "doc_type": ["Document Type"],
    "keywords": ["Author Keywords", "Index Keywords", "Keywords"],
}

REQUIRED_COLUMNS = {"title"}  # minimum to be useful; others degrade gracefully


def _find_col(header_row: list[str], candidates: list[str]) -> str | None:
    """Return the first candidate column name that exists in header_row (case-insensitive)."""
    lower = {h.strip().lower(): h.strip() for h in header_row}
    for c in candidates:
        if c.strip().lower() in lower:
            return lower[c.strip().lower()]
    return None


def _resolve_cols(header_row: list[str]) -> dict[str, str | None]:
    return {field: _find_col(header_row, names) for field, names in COLUMN_MAP.items()}


def _parse_year(raw: str) -> int | None:
    if not raw:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    return int(m.group()) if m else None


def _split_authors(raw: str) -> list[str]:
    if not raw:
        return []
    # Scopus: "Smith J., Jones A., Brown K." — split on semicolon or comma+space
    parts = re.split(r";\s*", raw.strip())
    if len(parts) == 1:
        # Try comma splitting but be careful not to split "Smith, J."
        parts = re.split(r",\s+(?=[A-Z])", raw.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_scopus_csv(csv_path: Path) -> list[dict]:
    """Parse Scopus CSV and return list of candidate dicts."""
    candidates = []

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            sys.exit(f"CSV file is empty: {csv_path}")

        cols = _resolve_cols(header)

        missing = [f for f in REQUIRED_COLUMNS if cols.get(f) is None]
        if missing:
            sys.exit(
                f"Required Scopus CSV column(s) not found: {missing}\n"
                f"Found columns: {header[:10]}..."
            )

        def get(row_dict: dict, field: str) -> str:
            col = cols.get(field)
            return row_dict.get(col, "").strip() if col else ""

        for i, row in enumerate(reader):
            if not any(cell.strip() for cell in row):
                continue  # skip blank lines

            row_dict = dict(zip(header, row))

            title = get(row_dict, "title")
            if not title:
                continue

            doi_raw = get(row_dict, "doi").strip().lstrip("https://doi.org/").lstrip("http://dx.doi.org/")
            eid     = get(row_dict, "eid")
            pmid    = get(row_dict, "pubmed_id")
            link    = get(row_dict, "link") or (f"https://doi.org/{doi_raw}" if doi_raw else "")

            # Construct a stable paper_id: prefer DOI, then EID, then index
            paper_id = doi_raw or eid or f"scopus-row-{i+1}"

            candidates.append({
                "title":        title,
                "authors":      _split_authors(get(row_dict, "authors")),
                "year":         _parse_year(get(row_dict, "year")),
                "abstract":     get(row_dict, "abstract"),
                "doi":          doi_raw or None,
                "source":       "scopus",
                "source_url":   link,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "paper_id":     paper_id,
                "journal":      get(row_dict, "source"),
                "keywords":     get(row_dict, "keywords"),
                "pubmed_id":    pmid or None,
                "eid":          eid or None,
            })

    return candidates


def write_candidates(candidates: list[dict], out_dir: Path) -> tuple[int, Path]:
    """Write individual JSON files and consolidated JSON. Returns (count, consolidated_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, cand in enumerate(candidates):
        slug = re.sub(r"[^a-z0-9]+", "-", (cand.get("doi") or cand["paper_id"]).lower()).strip("-")
        fname = f"scopus-{slug[:60]}.json"
        (out_dir / fname).write_text(json.dumps(cand, indent=2, ensure_ascii=False), encoding="utf-8")

    consolidated = out_dir / "_consolidated.json"
    existing: list[dict] = []
    if consolidated.exists():
        try:
            existing = json.loads(consolidated.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []

    # Deduplicate by DOI then by normalized title
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()

    def _norm_title(t: str) -> str:
        return re.sub(r"[^a-z0-9]", "", t.lower())

    merged = []
    for c in existing + candidates:
        doi = (c.get("doi") or "").lower()
        nt  = _norm_title(c.get("title", ""))
        if doi and doi in seen_dois:
            continue
        if nt and nt in seen_titles:
            continue
        if doi:
            seen_dois.add(doi)
        if nt:
            seen_titles.add(nt)
        merged.append(c)

    consolidated.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(candidates), consolidated


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Scopus CSV export into candidate JSON files.")
    parser.add_argument("--csv",  required=True, help="Path to the Scopus CSV export file")
    parser.add_argument("--out",  required=True, help="Output directory for candidate JSON files")
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    out_dir  = Path(args.out).expanduser().resolve()

    if not csv_path.exists():
        sys.exit(f"CSV file not found: {csv_path}")

    candidates = parse_scopus_csv(csv_path)
    count, consolidated = write_candidates(candidates, out_dir)

    print(f"Parsed {count} candidates from {csv_path.name}")
    print(f"Consolidated → {consolidated}")


if __name__ == "__main__":
    main()
