"""Shared parsing helpers for project scout scripts.

`Project_Brief.md` defines the stable project scope. `scout-queries.md` is an
optional, editable search-campaign file that can add temporary or follow-up
queries without changing the project brief.
"""

from __future__ import annotations

import re
from pathlib import Path


PLACEHOLDERS = {
    "",
    "(empty = all)",
    "(papers must mention at least one)",
    "(papers mentioning these get auto-rejected)",
    "n.a",
    "na",
    "none",
    "not-specified",
    "not specified",
    "unspecified",
}


def extract_section(text: str, heading: str, level: int = 3) -> str:
    marks = "#" * level
    next_heading = r"^#{1,6}\s+"
    match = re.search(
        rf"^{marks}\s+{re.escape(heading)}\n+(.*?)(?={next_heading}|\Z)",
        text,
        flags=re.M | re.S,
    )
    return match.group(1).strip() if match else ""


def split_terms(block: str) -> list[str]:
    cleaned = re.sub(r"^[*-]\s*", "", block, flags=re.M)
    terms = []
    for part in re.split(r"[\n,;]+", cleaned):
        term = normalize_query(part)
        if usable_query(term):
            terms.append(term)
    return dedupe(terms)


def normalize_query(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^\d+\.\s*", "", value)
    value = value.strip().strip("`").strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def usable_query(value: str) -> bool:
    lowered = value.lower().strip().strip('"').strip("'")
    if lowered in PLACEHOLDERS:
        return False
    if lowered.startswith("(") and lowered.endswith(")"):
        return False
    if "project_brief.md" in lowered or lowered.startswith("use the papers listed"):
        return False
    return bool(lowered)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def read_scout_queries(path: Path) -> list[str]:
    if not path.exists():
        return []
    queries: list[str] = []
    collecting = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith("#"):
            collecting = "quer" in lowered
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z /-]*:", stripped):
            collecting = lowered.rstrip(":") == "queries"
            continue
        parsed = parse_query_bullet(stripped)
        if not parsed:
            continue
        if not collecting:
            continue
        query, done = parsed
        if done:
            continue
        if usable_query(query):
            queries.append(query)
    return dedupe(queries)


def parse_query_bullet(stripped: str) -> tuple[str, bool] | None:
    match = re.match(r"^[-*]\s+(?:\[([ xX])\]\s*)?(.*)$", stripped)
    if not match:
        return None
    mark = match.group(1)
    query = normalize_query(match.group(2))
    done = bool(mark and mark.lower() == "x")
    return query, done


def read_scout_queries_with_state(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    collecting = False
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith("#"):
            collecting = "quer" in lowered
            section = stripped.lstrip("#").strip()
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z /-]*:", stripped):
            collecting = lowered.rstrip(":") == "queries"
            continue
        parsed = parse_query_bullet(stripped)
        if not parsed or not collecting:
            continue
        query, done = parsed
        if usable_query(query):
            rows.append({"query": query, "done": done, "section": section})
    return rows


def mark_scout_queries_done(path: Path, executed_queries: list[str]) -> int:
    if not path.exists() or not executed_queries:
        return 0
    executed = {normalize_query(query).lower() for query in executed_queries}
    changed = 0
    collecting = False
    new_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith("#"):
            collecting = "quer" in lowered
            new_lines.append(line)
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z /-]*:", stripped):
            collecting = lowered.rstrip(":") == "queries"
            new_lines.append(line)
            continue
        parsed = parse_query_bullet(stripped)
        if not parsed or not collecting:
            new_lines.append(line)
            continue
        query, done = parsed
        if done or normalize_query(query).lower() not in executed:
            new_lines.append(line)
            continue
        indent = line[: len(line) - len(line.lstrip())]
        bullet = line.lstrip()[0]
        new_lines.append(f"{indent}{bullet} [x] {query}")
        changed += 1
    if changed:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return changed


def read_seed_refs(text: str) -> list[str]:
    block = extract_section(text, "5. Key Existing References", level=2)
    seeds = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            seed = normalize_query(stripped[2:].split(" — ", 1)[0])
            if usable_query(seed):
                seeds.append(seed)
    return dedupe(seeds)


def read_frontmatter_field(text: str, field: str) -> str | None:
    """Extract a single field's value from YAML frontmatter at the top of a markdown file."""
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    if len(lines) < 2:
        return None
    closing = None
    for idx, raw in enumerate(lines[1:], start=1):
        if raw.strip() == "---":
            closing = idx
            break
    if closing is None:
        return None
    prefix = f"{field}:".lower()
    for raw in lines[1:closing]:
        if raw.lower().lstrip().startswith(prefix):
            value = raw.split(":", 1)[1].strip()
            return value.strip('"').strip("'")
    return None


def assert_brief_is_scoutable(brief_path: Path, text: str) -> None:
    """Refuse to scout a brief whose confidential_tier is local-only.

    Scout is a Build-phase cloud activity. Confidential project briefs
    (`grant`, `paper_in_prep`, `review_article`) must not flow through
    cloud-touching scripts. The translation from a confidential project
    need to a public topic is the user's job — performed by opening or
    updating an `explorations/idea-notes/{topic}.md` and scouting that.
    """
    tier = read_frontmatter_field(text, "confidential_tier")
    if tier == "local-only":
        raise SystemExit(
            f"Refusing to scout {brief_path}: confidential_tier is local-only.\n"
            "Open or update an explorations/idea-notes/{topic}.md with "
            "public-facing keywords and run scout against that file instead."
        )
    project_type = read_frontmatter_field(text, "project_type")
    if project_type in {"grant", "paper_in_prep", "review_article"}:
        raise SystemExit(
            f"Refusing to scout {brief_path}: project_type={project_type!r}.\n"
            "Scout only runs on explorations or library_ingest projects. "
            "Translate this project's literature need into a public topic and "
            "scout via explorations/idea-notes/."
        )


def read_project_inputs(
    brief_path: Path,
    *,
    include_done_queries: bool = False,
    include_brief: bool = True,
) -> dict:
    text = brief_path.read_text(encoding="utf-8")
    assert_brief_is_scoutable(brief_path, text)
    include_terms = split_terms(extract_section(text, "Must-include keywords"))
    exclude_terms = split_terms(extract_section(text, "Must-exclude keywords"))
    scout_query_path = brief_path.parent / "scout-queries.md"
    if include_done_queries:
        scout_queries = [row["query"] for row in read_scout_queries_with_state(scout_query_path)]
    else:
        scout_queries = read_scout_queries(scout_query_path)
    return {
        "project_slug": project_slug(text, brief_path),
        "brief_must_include": include_terms,
        "scout_queries": scout_queries,
        "must_include": dedupe([*(include_terms if include_brief else []), *scout_queries]),
        "must_exclude": exclude_terms,
        "year_range": extract_section(text, "Year range"),
        "seed_refs": read_seed_refs(text),
    }


def project_slug(text: str, brief_path: Path) -> str:
    match = re.search(r"^project_slug:\s*(.+)$", text, flags=re.M)
    if not match:
        return brief_path.parent.name
    value = match.group(1).strip().strip('"').strip("'")
    return value or brief_path.parent.name


def query_tokens(query: str) -> list[str]:
    quoted = re.findall(r'"([^"]+)"', query)
    without_quoted = re.sub(r'"[^"]+"', " ", query)
    parts = re.split(r"\s+(?:AND|OR)\s+|[;,]", without_quoted, flags=re.I)
    tokens = [normalize_query(part) for part in [*quoted, *parts]]
    return [token for token in tokens if usable_query(token) and token.upper() not in {"AND", "OR", "NOT"}]


def query_matches(query: str, haystack: str) -> bool:
    haystack = haystack.lower()
    if re.search(r"\s+OR\s+", query, flags=re.I):
        return any(token.lower() in haystack for token in query_tokens(query))
    tokens = query_tokens(query)
    if re.search(r"\s+AND\s+", query, flags=re.I):
        return all(token.lower() in haystack for token in tokens)
    return normalize_query(query).strip('"').lower() in haystack


def any_query_matches(queries: list[str], haystack: str) -> bool:
    return any(query_matches(query, haystack) for query in queries)
