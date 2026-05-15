"""Verify draft citations against source frontmatter and claim logs.

This harness defends against structural citation failures where a draft points
to a real source but assigns the wrong author, year, or unsupported claim. It
checks that every draft wikilink resolves to a real `sources/{stem}.md` file,
that optional `(Author Year)` inline citations agree with source frontmatter,
that claim-log rows are not orphaned, and that non-structural draft sentences
are covered by the claim log.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import quote


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", help="Path to a draft markdown file")
    parser.add_argument("claim_log", help="Path to the corresponding claim log markdown file")
    parser.add_argument("--strict-doi", action="store_true", help="Validate DOI metadata against Crossref and cache results")
    return parser


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def read_frontmatter(source_path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency check
        raise SystemExit("Missing dependency: pyyaml") from exc
    text = source_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?", text, flags=re.S)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def extract_stem(link_target: str) -> str:
    target = link_target.split("|", 1)[0].strip()
    if target.startswith("sources/"):
        target = target.split("/", 1)[1]
    return Path(target).name.removesuffix(".md")


def iter_wikilinks(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(1), match.start(), match.end()) for match in re.finditer(r"\[\[([^\]]+)\]\]", text)]


def first_author_lastname(authors: object) -> str:
    if isinstance(authors, list) and authors:
        raw = str(authors[0])
    else:
        raw = str(authors or "")
        raw = re.split(r",|;| and ", raw)[0]
    tokens = [token for token in re.split(r"\s+", raw.strip()) if token]
    return re.sub(r"[^A-Za-z'-]", "", tokens[-1]) if tokens else ""


def source_metadata(repo_root: Path, stem: str) -> tuple[Path, dict]:
    source_path = repo_root / "sources" / f"{stem}.md"
    return source_path, read_frontmatter(source_path) if source_path.exists() else {}


def split_sentences(draft_text: str) -> list[str]:
    sentences: list[str] = []
    for line in draft_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "[researcher_judgment_needed]":
            continue
        if stripped.startswith(("#", ">", "|", "- ", "* ")) or re.match(r"^\d+\.\s", stripped):
            continue
        for part in re.split(r"(?<=[.!?])\s+", stripped):
            cleaned = normalize_space(part)
            if cleaned and re.search(r"[A-Za-z0-9]", cleaned):
                sentences.append(cleaned)
    return sentences


def parse_claim_log_rows(claim_log_text: str) -> list[dict]:
    rows: list[dict] = []
    header: list[str] | None = None
    for line in claim_log_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
                continue
            if header is None:
                header = [cell.lower().replace(" ", "_") for cell in cells]
                continue
            data = {header[index]: cells[index] if index < len(cells) else "" for index in range(len(header))}
            claim = data.get("claim") or data.get("sentence") or data.get("text") or (cells[0] if cells else "")
            source_field = data.get("source") or data.get("sources") or data.get("wikilink") or data.get("citations") or stripped
            rows.append({"claim": normalize_space(claim), "stems": [extract_stem(link) for link, _, _ in iter_wikilinks(source_field)]})
            continue
        bullet = re.match(r"^(?:-|\*|\d+\.)\s*(.*?)\s*(?:::|—|-)\s*(\[\[[^\]]+\]\].*)$", stripped)
        if bullet:
            rows.append({"claim": normalize_space(bullet.group(1)), "stems": [extract_stem(link) for link, _, _ in iter_wikilinks(bullet.group(2))]})
    return rows


def sentence_citation_pairs(sentence: str) -> list[tuple[str, str]]:
    links = [extract_stem(link) for link, _, _ in iter_wikilinks(sentence)]
    citations = [match.group(1) for match in re.finditer(r"\(([^()]*\b\d{4}[a-z]?\b[^()]*)\)", sentence)]
    if not links or not citations:
        return []
    if len(links) == len(citations):
        return list(zip(links, citations))
    if len(links) == 1 and len(citations) == 1:
        return [(links[0], citations[0])]
    return []


def doi_cache_path() -> Path:
    return Path(tempfile.gettempdir()) / "verify_citations_crossref_cache.json"


def load_cache() -> dict:
    path = doi_cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict) -> None:
    doi_cache_path().write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def crossref_check(doi: str, expected_author: str, expected_year: str, cache: dict) -> str | None:
    if doi in cache:
        payload = cache[doi]
    else:
        import requests

        url = f"https://api.crossref.org/works/{quote(doi)}"
        response = requests.get(url, timeout=30, headers={"User-Agent": "research-system/1.0"})
        response.raise_for_status()
        payload = response.json().get("message", {})
        cache[doi] = payload
        save_cache(cache)
    authors = payload.get("author") or []
    family = authors[0].get("family", "") if authors else ""
    year_parts = payload.get("published-print", {}).get("date-parts") or payload.get("published-online", {}).get("date-parts") or [[]]
    year = str(year_parts[0][0]) if year_parts and year_parts[0] else ""
    if family.lower() != expected_author.lower() or year != expected_year:
        return f"DOI {doi} resolves to {family} {year}, expected {expected_author} {expected_year}"
    return None


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    draft_path = Path(args.draft).expanduser().resolve()
    claim_log_path = Path(args.claim_log).expanduser().resolve()
    draft_text = draft_path.read_text(encoding="utf-8")
    claim_log_text = claim_log_path.read_text(encoding="utf-8")
    draft_wikilinks = [extract_stem(link) for link, _, _ in iter_wikilinks(draft_text)]
    claim_rows = parse_claim_log_rows(claim_log_text)
    cache = load_cache() if args.strict_doi else {}
    errors: list[str] = []
    metadata_cache: dict[str, dict] = {}

    for stem in sorted(set(draft_wikilinks)):
        source_path, metadata = source_metadata(repo_root, stem)
        metadata_cache[stem] = metadata
        if not source_path.exists():
            errors.append(f"Missing source for wikilink: {stem}")
            continue
        for field in ("authors", "year", "doi"):
            if field not in metadata or metadata.get(field) in ("", None, []):
                errors.append(f"{source_path.name} missing frontmatter field: {field}")
        if args.strict_doi and metadata.get("doi") and metadata.get("authors") and metadata.get("year"):
            expected_author = first_author_lastname(metadata.get("authors"))
            mismatch = crossref_check(str(metadata['doi']), expected_author, str(metadata["year"]), cache)
            if mismatch:
                errors.append(mismatch)

    for sentence in split_sentences(draft_text):
        sentence_norm = normalize_space(sentence)
        if not any(sentence_norm in row["claim"] or row["claim"] in sentence_norm for row in claim_rows if row["claim"]):
            errors.append(f"Draft sentence missing from claim log: {sentence_norm}")

    normalized_draft = normalize_space(draft_text)
    for row in claim_rows:
        if row["claim"] and row["claim"] not in normalized_draft:
            errors.append(f"Orphaned claim-log row not found in draft: {row['claim']}")
        for stem in row["stems"]:
            source_path, _ = source_metadata(repo_root, stem)
            if not source_path.exists():
                errors.append(f"Claim log references missing source: {stem}")

    for sentence in split_sentences(draft_text):
        for stem, inline_citation in sentence_citation_pairs(sentence):
            metadata = metadata_cache.get(stem) or source_metadata(repo_root, stem)[1]
            author = first_author_lastname(metadata.get("authors"))
            year = str(metadata.get("year", ""))
            if author and year and f"{author} {year}".lower() not in inline_citation.lower():
                errors.append(f"Inline citation mismatch for {stem}: prose has ({inline_citation}), frontmatter says ({author} {year})")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"ERROR: {len(errors)} issue(s) found")
        return 1
    print(f"OK: verified {len(draft_wikilinks)} wikilink(s), {len(claim_rows)} claim-log row(s), and {len(split_sentences(draft_text))} sentence(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
