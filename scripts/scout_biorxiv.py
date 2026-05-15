"""Scout bioRxiv and medRxiv for project-relevant candidate papers.

This script reads a Project_Brief, pulls recent records from the bioRxiv API,
filters them locally, and writes candidate metadata JSON files.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from scout_common import any_query_matches, read_project_inputs


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def fetch_server(server: str, start_date: date, end_date: date, max_pages: int) -> list[dict]:
    import requests

    base = "https://api.biorxiv.org/details"
    items: list[dict] = []
    for page in range(max_pages):
        cursor = page * 100
        url = f"{base}/{server}/{start_date.isoformat()}/{end_date.isoformat()}/{cursor}/json"
        response = requests.get(url, timeout=30, headers={"User-Agent": "research-system/1.0"})
        response.raise_for_status()
        payload = response.json()
        items.extend(payload.get("collection", []))
        if len(payload.get("collection", [])) < 100:
            break
    return items


def keep_candidate(item: dict, includes: Iterable[str], excludes: Iterable[str]) -> bool:
    haystack = " ".join([item.get("title", ""), item.get("abstract", ""), item.get("category", "")]).lower()
    if includes and not any_query_matches(list(includes), haystack):
        return False
    if any_query_matches(list(excludes), haystack):
        return False
    return True


def to_candidate(item: dict) -> dict:
    doi = item.get("doi")
    authors = [author.strip() for author in item.get("authors", "").split(";") if author.strip()]
    year = int(item.get("date", "")[:4]) if item.get("date", "")[:4].isdigit() else None
    paper_id = doi or normalize_title(item.get("title", "untitled"))
    return {
        "title": item.get("title"),
        "authors": authors,
        "year": year,
        "abstract": item.get("abstract"),
        "doi": doi or None,
        "source": item.get("server", "biorxiv"),
        "source_url": f"https://doi.org/{doi}" if doi else "",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "paper_id": paper_id,
    }


def write_candidates(out_dir: Path, papers: Iterable[dict]) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    written = 0
    for paper in papers:
        dedupe_key = paper.get("doi") or normalize_title(paper["title"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(paper["paper_id"]))
        path = out_dir / f"{paper['source']}-{safe_id}.json"
        path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to Project_Brief.md")
    parser.add_argument("--out", required=True, help="Output directory for candidate JSON files")
    parser.add_argument("--days", type=int, default=120, help="How many recent days to search")
    parser.add_argument("--max-pages", type=int, default=3, help="Maximum 100-record pages per server")
    parser.add_argument("--include-done-queries", action="store_true", help="Also run checked-off scout-queries.md items")
    parser.add_argument("--queries-only", action="store_true", help="Run scout-queries.md items without Project_Brief must-include terms")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    brief = read_project_inputs(
        Path(args.brief).expanduser().resolve(),
        include_done_queries=args.include_done_queries,
        include_brief=not args.queries_only,
    )
    end_date = date.today()
    start_date = end_date - timedelta(days=args.days)
    raw_items = fetch_server("biorxiv", start_date, end_date, args.max_pages)
    raw_items += fetch_server("medrxiv", start_date, end_date, args.max_pages)
    filtered = [to_candidate(item) for item in raw_items if keep_candidate(item, brief["must_include"], brief["must_exclude"])]
    written = write_candidates(Path(args.out).expanduser().resolve(), filtered)
    print(f"Wrote {written} bioRxiv/medRxiv candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
