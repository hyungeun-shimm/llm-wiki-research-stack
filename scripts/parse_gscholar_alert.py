"""Parse forwarded Google Scholar alert emails into candidate metadata.

This is a local skeleton that reads `.eml` files, extracts paper-like links,
applies brief keyword filtering, and writes candidate JSON files.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from html import unescape
from pathlib import Path

from scout_common import any_query_matches, read_project_inputs


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def extract_html(message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                return part.get_content()
    if message.get_content_type() == "text/html":
        return message.get_content()
    return ""


def parse_candidates(eml_path: Path) -> list[dict]:
    message = BytesParser(policy=policy.default).parsebytes(eml_path.read_bytes())
    html = extract_html(message)
    items = []
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
        href = unescape(match.group(1))
        title = re.sub(r"<.*?>", "", unescape(match.group(2))).strip()
        if not title or "scholar.google" in title.lower():
            continue
        snippet_match = re.search(re.escape(match.group(0)) + r"(.*?)</tr>", html, flags=re.S)
        snippet = re.sub(r"<.*?>", " ", unescape(snippet_match.group(1))) if snippet_match else ""
        year_match = re.search(r"\b(19|20)\d{2}\b", snippet)
        items.append(
            {
                "title": title,
                "authors": [],
                "year": int(year_match.group(0)) if year_match else None,
                "abstract": " ".join(snippet.split()) or None,
                "doi": None,
                "source": "google-scholar-alert",
                "source_url": href,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "paper_id": normalize_title(title)[:60],
            }
        )
    return items


def keep_candidate(candidate: dict, brief: dict) -> bool:
    haystack = " ".join(filter(None, [candidate.get("title", ""), candidate.get("abstract", "")])).lower()
    if brief["must_include"] and not any_query_matches(brief["must_include"], haystack):
        return False
    if any_query_matches(brief["must_exclude"], haystack):
        return False
    return True


def write_candidates(out_dir: Path, papers: list[dict]) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    seen: set[str] = set()
    for paper in papers:
        dedupe_key = normalize_title(paper["title"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        path = out_dir / f"google-scholar-alert-{paper['paper_id']}.json"
        path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to Project_Brief.md")
    parser.add_argument("--out", required=True, help="Output directory for candidate JSON files")
    parser.add_argument("--alerts-dir", default="~/gscholar-alerts", help="Directory containing forwarded .eml alert files")
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
    alerts_dir = Path(args.alerts_dir).expanduser().resolve()
    alerts_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[dict] = []
    for eml_path in sorted(alerts_dir.glob("*.eml")):
        candidates.extend(paper for paper in parse_candidates(eml_path) if keep_candidate(paper, brief))
    written = write_candidates(Path(args.out).expanduser().resolve(), candidates)
    print(f"Wrote {written} Google Scholar alert candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
