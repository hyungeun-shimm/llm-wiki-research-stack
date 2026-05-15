"""Scout PubMed for project-relevant candidate papers.

This script reads a Project_Brief, queries NCBI E-utilities, and writes
candidate metadata JSON files without downloading PDFs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from scout_common import any_query_matches, query_tokens, read_project_inputs


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def build_query(brief: dict) -> str:
    clauses = []
    for term in brief["must_include"][:12]:
        tokens = query_tokens(term)
        if re.search(r"\s+AND\s+", term, flags=re.I) and tokens:
            clauses.append("(" + " AND ".join(f'"{token}"[Title/Abstract]' for token in tokens) + ")")
        elif re.search(r"\s+OR\s+", term, flags=re.I) and tokens:
            clauses.append("(" + " OR ".join(f'"{token}"[Title/Abstract]' for token in tokens) + ")")
        else:
            clauses.append(f'"{term.strip().strip("\"")}"[Title/Abstract]')
    includes = " OR ".join(clauses) or "all[sb]"
    excludes = " ".join(f'NOT "{term}"[Title/Abstract]' for term in brief["must_exclude"])
    years = re.findall(r"\b(?:19|20)\d{2}\b", brief["year_range"])
    year_clause = ""
    if len(years) >= 2:
        year_clause = f' AND ("{years[0]}"[Date - Publication] : "{years[-1]}"[Date - Publication])'
    return f"({includes}) {excludes}{year_clause}".strip()


def esearch(query: str, max_results: int) -> list[str]:
    import requests

    params = {"db": "pubmed", "retmode": "json", "term": query, "retmax": max_results, "sort": "pub date"}
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    else:
        print("NCBI_API_KEY not set; using public rate limits.", file=sys.stderr)
    response = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return payload.get("esearchresult", {}).get("idlist", [])


def efetch(pmids: list[str]) -> list[dict]:
    import requests

    if not pmids:
        return []
    params = {"db": "pubmed", "retmode": "xml", "id": ",".join(pmids)}
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    response = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params=params, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    papers: list[dict] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", default="")
        title = " ".join((article.findtext(".//ArticleTitle", default="")).split())
        abstract_parts = [node.text.strip() for node in article.findall(".//Abstract/AbstractText") if node.text]
        abstract = " ".join(abstract_parts)
        year = article.findtext(".//PubDate/Year", default="")
        doi = None
        for ident in article.findall(".//ArticleId"):
            if ident.attrib.get("IdType") == "doi" and ident.text:
                doi = ident.text.strip()
                break
        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName", default="")
            fore = author.findtext("ForeName", default="")
            name = " ".join(part for part in [fore, last] if part).strip()
            if name:
                authors.append(name)
        papers.append(
            {
                "title": title,
                "authors": authors,
                "year": int(year) if year.isdigit() else None,
                "abstract": abstract,
                "doi": doi,
                "source": "pubmed",
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "paper_id": pmid,
            }
        )
    return papers


def keep_candidate(title: str, abstract: str, excludes: Iterable[str]) -> bool:
    haystack = f"{title} {abstract}".lower()
    return not any_query_matches(list(excludes), haystack)


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
        path = out_dir / f"pubmed-{safe_id}.json"
        path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to Project_Brief.md")
    parser.add_argument("--out", required=True, help="Output directory for candidate JSON files")
    parser.add_argument("--max-results", type=int, default=25, help="Maximum PubMed records to fetch")
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
    pmids = esearch(build_query(brief), args.max_results)
    papers = efetch(pmids)
    filtered = [paper for paper in papers if keep_candidate(paper["title"], paper["abstract"], brief["must_exclude"])]
    written = write_candidates(Path(args.out).expanduser().resolve(), filtered)
    print(f"Wrote {written} PubMed candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
