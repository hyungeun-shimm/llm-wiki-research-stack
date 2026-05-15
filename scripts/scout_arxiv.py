"""Scout arXiv for project-relevant candidate papers.

This script reads a Project_Brief, queries the arXiv API, and writes
candidate metadata JSON files without downloading PDFs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from xml.etree import ElementTree as ET

from scout_common import read_project_inputs


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def keep_candidate(title: str, abstract: str, excludes: Iterable[str]) -> bool:
    haystack = f"{title} {abstract}".lower()
    return not any(term.lower() in haystack for term in excludes)


def arxiv_search_query(term: str) -> str:
    parts = re.split(r"\s+(AND|OR)\s+", term, flags=re.I)
    if len(parts) == 1:
        return f'all:"{term.strip().strip("\"")}"'
    out = []
    for part in parts:
        if part.upper() in {"AND", "OR"}:
            out.append(part.upper())
        elif part.strip():
            out.append(f'all:"{part.strip().strip("\"")}"')
    return " ".join(out)


def query_arxiv(term: str, max_results: int, retries: int, delay: float) -> list[dict]:
    import requests

    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": arxiv_search_query(term),
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(delay)
        response = requests.get(url, params=params, timeout=30, headers={"User-Agent": "research-system/1.0"})
        if response.status_code != 429:
            break
        retry_after = response.headers.get("Retry-After")
        wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else max(delay, 10.0)
        print(
            f"arXiv rate-limited query {term!r}; waiting {wait_seconds:g}s before retry {attempt + 1}/{retries}.",
            file=sys.stderr,
        )
        time.sleep(wait_seconds)
    assert response is not None
    if response.status_code == 429:
        raise RuntimeError(f"arXiv rate limit persisted for query {term!r}; try again later.")
    response.raise_for_status()
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(response.text)
    entries: list[dict] = []
    for entry in root.findall("atom:entry", ns):
        paper_id = entry.findtext("atom:id", default="", namespaces=ns).rsplit("/", 1)[-1]
        doi = entry.findtext("arxiv:doi", default="", namespaces=ns)
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ns)).split())
        abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=ns)).split())
        published = entry.findtext("atom:published", default="", namespaces=ns)
        authors = [node.findtext("atom:name", default="", namespaces=ns) for node in entry.findall("atom:author", ns)]
        entries.append(
            {
                "title": title,
                "authors": authors,
                "year": int(published[:4]) if published[:4].isdigit() else None,
                "abstract": abstract,
                "doi": doi or None,
                "source": "arxiv",
                "source_url": f"https://arxiv.org/abs/{quote(paper_id)}",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "paper_id": paper_id,
            }
        )
    return entries


def write_candidates(out_dir: Path, papers: Iterable[dict]) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    written = 0
    for paper in papers:
        dedupe_key = paper.get("doi") or normalize_title(paper["title"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", paper["paper_id"])
        path = out_dir / f"arxiv-{safe_id}.json"
        path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to Project_Brief.md")
    parser.add_argument("--out", required=True, help="Output directory for candidate JSON files")
    parser.add_argument("--max-results", type=int, default=10, help="Results per query term")
    parser.add_argument("--retries", type=int, default=3, help="Retries for arXiv rate limits")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds to pause between arXiv queries")
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
    candidates: list[dict] = []
    for index, term in enumerate(brief["must_include"][:8]):
        if index:
            time.sleep(args.delay)
        try:
            candidates.extend(query_arxiv(term, args.max_results, args.retries, args.delay))
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    filtered = [paper for paper in candidates if keep_candidate(paper["title"], paper["abstract"], brief["must_exclude"])]
    written = write_candidates(Path(args.out).expanduser().resolve(), filtered)
    print(f"Wrote {written} arXiv candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
