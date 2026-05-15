"""Scout Semantic Scholar for project-relevant candidate papers.

This script uses seed references from a Project_Brief to expand through
Semantic Scholar search plus citation/reference lookups.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from scout_common import read_project_inputs


def require_api_key() -> str:
    api_key = os.getenv("S2_API_KEY")
    if not api_key:
        raise SystemExit("Missing required environment variable: S2_API_KEY")
    return api_key


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def s2_get(path: str, params: dict) -> dict:
    import requests

    headers = {"x-api-key": require_api_key(), "User-Agent": "research-system/1.0"}
    url = f"https://api.semanticscholar.org/graph/v1{path}"
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_seed(seed: str) -> list[dict]:
    query = seed.replace("-", " ")
    payload = s2_get("/paper/search", {"query": query, "limit": 1, "fields": "paperId,title,year,abstract,authors,externalIds,url"})
    return payload.get("data", [])


def expand_paper(paper_id: str, relation: str, limit: int) -> list[dict]:
    payload = s2_get(f"/paper/{paper_id}/{relation}", {"limit": limit, "fields": "paperId,title,year,abstract,authors,externalIds,url"})
    data = []
    for item in payload.get("data", []):
        nested = item.get("citedPaper") or item.get("citingPaper") or {}
        if nested:
            data.append(nested)
    return data


def keyword_fallback(terms: list[str], limit: int) -> list[dict]:
    papers: list[dict] = []
    for term in terms[:5]:
        payload = s2_get("/paper/search", {"query": term, "limit": limit, "fields": "paperId,title,year,abstract,authors,externalIds,url"})
        papers.extend(payload.get("data", []))
    return papers


def to_candidate(paper: dict) -> dict:
    external_ids = paper.get("externalIds") or {}
    doi = external_ids.get("DOI")
    paper_id = paper.get("paperId") or doi or normalize_title(paper.get("title", "untitled"))
    return {
        "title": paper.get("title"),
        "authors": [author.get("name", "") for author in paper.get("authors", []) if author.get("name")],
        "year": paper.get("year"),
        "abstract": paper.get("abstract"),
        "doi": doi,
        "source": "semantic-scholar",
        "source_url": paper.get("url") or "",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "paper_id": paper_id,
    }


def write_candidates(out_dir: Path, papers: Iterable[dict]) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    written = 0
    for paper in papers:
        if not paper.get("title"):
            continue
        dedupe_key = paper.get("doi") or normalize_title(paper["title"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(paper["paper_id"]))
        path = out_dir / f"semantic-scholar-{safe_id}.json"
        path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to Project_Brief.md")
    parser.add_argument("--out", required=True, help="Output directory for candidate JSON files")
    parser.add_argument("--limit", type=int, default=10, help="Maximum citation/reference records per seed")
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
    for seed in brief["seed_refs"]:
        matches = search_seed(seed)
        if not matches:
            continue
        seed_paper = matches[0]
        paper_id = seed_paper.get("paperId")
        if not paper_id:
            continue
        candidates.append(to_candidate(seed_paper))
        candidates.extend(to_candidate(paper) for paper in expand_paper(paper_id, "citations", args.limit))
        candidates.extend(to_candidate(paper) for paper in expand_paper(paper_id, "references", args.limit))
    if not candidates:
        candidates.extend(to_candidate(paper) for paper in keyword_fallback(brief["must_include"], args.limit))
    written = write_candidates(Path(args.out).expanduser().resolve(), candidates)
    print(f"Wrote {written} Semantic Scholar candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
