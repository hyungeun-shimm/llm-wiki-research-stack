#!/usr/bin/env python3
"""Audit a Mendeley BibTeX export and propose a cleaner research taxonomy.

This script is intentionally read-only with respect to Mendeley. It parses a
BibTeX export, scans an optional Mendeley PDF storage root, and writes local
review reports that help decide what should be reorganized in Mendeley and what
is worth curating into the LLM-Wiki.

It does not rename PDFs, edit the Mendeley database, download papers, or ingest
anything into `papers/`, `sources/`, or `wiki/`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CATEGORY_RULES = {
    "topic-a": [  # customize for your research area
        "your-keyword-1", "your-keyword-2", "your-keyword-3",
        "your-keyword-4", "your-keyword-5", "your-keyword-6",
        "your-keyword-7", "your-keyword-8", "your-keyword-9",
        "your-keyword-10", "your-keyword-11", "your-keyword-12",
    ],
    "topic-b": [  # customize for your research area
        "your-keyword-1", "your-keyword-2", "your-keyword-3",
        "your-keyword-4", "your-keyword-5", "your-keyword-6",
        "your-keyword-7", "your-keyword-8", "your-keyword-9",
        "your-keyword-10", "your-keyword-11", "your-keyword-12",
    ],
    "topic-c": [  # customize for your research area
        "your-keyword-1", "your-keyword-2", "your-keyword-3",
        "your-keyword-4", "your-keyword-5", "your-keyword-6",
        "your-keyword-7", "your-keyword-8",
    ],
    "topic-d": [  # customize for your research area
        "your-keyword-1", "your-keyword-2", "your-keyword-3",
        "your-keyword-4", "your-keyword-5", "your-keyword-6",
        "your-keyword-7", "your-keyword-8",
    ],
    "topic-e": [  # customize for your research area
        "your-keyword-1", "your-keyword-2", "your-keyword-3",
        "your-keyword-4", "your-keyword-5", "your-keyword-6",
        "your-keyword-7", "your-keyword-8",
    ],
    "sexual-dimorphism": [
        "sexual dimorphism", "sex difference", "sex differences", "female",
        "male", "estrogen", "estradiol", "ovarian", "testosterone",
    ],
    "neurodegenerative-disease": [
        "parkinson", "huntington", "neurodegenerative", "degeneration",
        "alzheimer", "ataxia", "spino-ataxia",
    ],
    "thalamo-basal-ganglia": [
        "thalam", "striat", "basal ganglia", "pallid", "substantia nigra",
        "cortico-striatal", "cortico-thalamo",
    ],
    "memory-affect-social": [
        "memory", "learning", "emotional", "emotion", "anxiety", "fear",
        "social", "sociability", "autism", "hippocamp",
    ],
    "methods-tools": [
        "optogen", "chemogen", "trap", "fs-trap", "single-cell",
        "single cell", "sequencing", "aav", "cre", "viral", "two-photon",
        "calcium imaging", "patch-clamp", "electrophysiology",
        "transcriptomic", "connectomic", "rna-seq",
    ],
    "reviews-protocols": [
        "review", "systematic review", "meta-analysis", "protocol",
        "perspective", "primer", "tutorial", "nature reviews",
    ],
    "biotech-translational": [
        "therapeutic", "therapy", "treatment", "clinical trial", "drug",
        "antibody", "biomarker", "pharmacology", "translational",
    ],
}


TAG_RULES = {
    "system:topic-a": ["your-keyword-1", "your-keyword-2", "your-keyword-3", "your-keyword-4"],
    "system:topic-b": ["your-keyword-1", "your-keyword-2", "your-keyword-3", "your-keyword-4"],
    "system:cortex": ["cortex", "cortical"],
    "system:thalamus": ["thalam"],
    "system:basal-ganglia": ["striat", "basal ganglia", "pallid"],
    "system:hippocampus": ["hippocamp"],
    "system:glia": ["astrocy", "microglia", "oligodendro", "bergmann"],
    "disease:topic-c": ["your-keyword-1", "your-keyword-2", "your-keyword-3", "your-keyword-4"],
    "disease:topic-d": ["your-keyword-1", "your-keyword-2", "your-keyword-3"],
    "disease:pain": ["pain", "nocicept", "allodynia", "hyperalgesia"],
    "disease:neurodegeneration": ["parkinson", "huntington", "alzheimer", "ataxia"],
    "disease:autism": ["autism", "fmrp", "fragile x"],
    "mechanism:plasticity": ["plasticity", "ltp", "ltd", "potentiation", "depression"],
    "mechanism:topic-c": ["your-keyword-1", "your-keyword-2"],
    "mechanism:inflammation": ["inflammation", "cytokine", "tnf", "il-1", "microglia"],
    "mechanism:motor-learning": ["motor learning", "adaptation", "vor", "eyeblink"],
    "mechanism:computation": ["computation", "coding", "model", "prediction", "error"],
    "method:optogenetics": ["optogen"],
    "method:single-cell": ["single-cell", "single cell", "rna-seq", "transcriptomic"],
    "method:viral-tools": ["aav", "viral", "cre", "flp", "trap"],
    "method:imaging": ["imaging", "two-photon", "calcium imaging"],
    "method:ephys": ["patch-clamp", "electrophysiology", "recording"],
    "format:review": ["review", "perspective", "primer", "meta-analysis"],
}


REQUIRED_FIELDS = ["title", "author", "year", "doi", "abstract"]
BOUNDARY_TERMS = {
    "aav", "cre", "flp", "il-1", "ltd", "ltp", "tbi", "tnf", "vor",
}


def clean_value(value: str) -> str:
    value = value.replace("\\r", " ").replace("\\n", " ")
    value = value.replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip().strip(",")


def parse_braced_value(text: str, start: int) -> tuple[str, int]:
    depth = 0
    out: list[str] = []
    i = start
    while i < len(text):
        char = text[i]
        if char == "{":
            depth += 1
            if depth > 1:
                out.append(char)
        elif char == "}":
            depth -= 1
            if depth == 0:
                return "".join(out), i + 1
            out.append(char)
        else:
            out.append(char)
        i += 1
    raise ValueError("Unclosed braced BibTeX value")


def parse_quoted_value(text: str, start: int) -> tuple[str, int]:
    out: list[str] = []
    i = start + 1
    escaped = False
    while i < len(text):
        char = text[i]
        if escaped:
            out.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
            out.append(char)
        elif char == '"':
            return "".join(out), i + 1
        else:
            out.append(char)
        i += 1
    raise ValueError("Unclosed quoted BibTeX value")


def parse_bib_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1
        match = re.match(r"([A-Za-z0-9_\-:]+)\s*=", text[i:])
        if not match:
            break
        name = match.group(1).lower()
        i += match.end()
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        if text[i] == "{":
            value, i = parse_braced_value(text, i)
        elif text[i] == '"':
            value, i = parse_quoted_value(text, i)
        else:
            start = i
            while i < len(text) and text[i] not in ",\n\r":
                i += 1
            value = text[start:i]
        fields[name] = clean_value(value)
    return fields


def iter_bib_entries(content: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    pos = 0
    while True:
        at = content.find("@", pos)
        if at == -1:
            break
        open_pos = content.find("{", at)
        if open_pos == -1:
            break
        entry_type = content[at + 1 : open_pos].strip().lower()
        try:
            body, next_pos = parse_braced_value(content, open_pos)
        except ValueError:
            break
        comma = body.find(",")
        if comma == -1:
            pos = next_pos
            continue
        key = body[:comma].strip()
        fields = parse_bib_fields(body[comma + 1 :])
        fields["entry_type"] = entry_type
        fields["key"] = key
        entries.append(fields)
        pos = next_pos
    return entries


def normalize_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value)
    value = value.strip().strip(".;,")
    return value


def normalize_title(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def author_short(value: str) -> str:
    first = (value or "").split(" and ")[0].strip()
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


def text_blob(entry: dict[str, str]) -> str:
    pieces = [
        entry.get("title", ""),
        entry.get("abstract", ""),
        entry.get("keywords", ""),
        entry.get("journal", ""),
        entry.get("booktitle", ""),
    ]
    return " ".join(pieces).lower()


def term_matches(blob: str, term: str) -> bool:
    if term in BOUNDARY_TERMS or (len(term) <= 4 and re.fullmatch(r"[a-z0-9-]+", term)):
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        return re.search(pattern, blob) is not None
    return term in blob


def score_terms(blob: str, terms: list[str]) -> int:
    score = 0
    for term in terms:
        if term_matches(blob, term):
            score += 2 if " " in term else 1
    return score


def classify(entry: dict[str, str]) -> tuple[str, list[str], list[str], int]:
    blob = text_blob(entry)
    scores = {
        category: score_terms(blob, terms)
        for category, terms in CATEGORY_RULES.items()
    }
    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        best_category = "other"
    secondary = [
        category for category, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if category != best_category and score >= 2
    ][:4]
    tags = [
        tag for tag, terms in TAG_RULES.items()
        if score_terms(blob, terms) > 0
    ][:12]
    priority = best_score
    if normalize_doi(entry.get("doi", "")):
        priority += 2
    if entry.get("abstract"):
        priority += 2
    if "format:review" in tags:
        priority += 1
    year = parse_year(entry.get("year", ""))
    if year >= 2018:
        priority += 2
    elif year >= 2010:
        priority += 1
    if best_category in {
        "topic-a", "topic-b", "topic-c",
        "topic-d", "topic-e",
    }:
        priority += 3
    return best_category, secondary, tags, priority


def parse_year(value: str) -> int:
    match = re.search(r"(19|20)\d{2}", value or "")
    return int(match.group(0)) if match else 0


def find_pdf_paths(pdf_root: Path | None) -> list[Path]:
    if not pdf_root or not pdf_root.exists():
        return []
    return sorted(path for path in pdf_root.rglob("*.pdf") if path.is_file())


def find_file_fields(entries: list[dict[str, str]]) -> list[str]:
    names: set[str] = set()
    for entry in entries:
        for key in entry:
            lowered = key.lower()
            if lowered in {"file", "local-url", "pdf"} or lowered.startswith("bdsk-file"):
                names.add(key)
    return sorted(names)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        clean = [cell.replace("\n", " ").replace("|", "\\|") for cell in row]
        out.append("| " + " | ".join(clean) + " |")
    return "\n".join(out)


def build_reports(entries: list[dict[str, str]], pdf_paths: list[Path], out_dir: Path, bib: Path, pdf_root: Path | None) -> None:
    classified: list[dict[str, str]] = []
    missing_rows: list[dict[str, str]] = []
    by_doi: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    by_title: defaultdict[str, list[dict[str, str]]] = defaultdict(list)

    for entry in entries:
        primary, secondary, tags, priority = classify(entry)
        doi = normalize_doi(entry.get("doi", ""))
        title = entry.get("title", "")
        row = {
            "key": entry.get("key", ""),
            "title": title,
            "year": str(parse_year(entry.get("year", "")) or ""),
            "doi": doi,
            "primary_category": primary,
            "secondary_categories": "; ".join(secondary),
            "tags": "; ".join(tags),
            "priority_score": str(priority),
            "authors": entry.get("author", ""),
            "first_author": author_short(entry.get("author", "")),
            "journal": entry.get("journal", entry.get("booktitle", "")),
        }
        classified.append(row)
        missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
        if missing:
            missing_rows.append({
                "key": entry.get("key", ""),
                "title": title,
                "year": row["year"],
                "missing_fields": "; ".join(missing),
            })
        if doi:
            by_doi[doi].append(entry)
        normalized_title = normalize_title(title)
        if normalized_title:
            by_title[normalized_title].append(entry)

    classified.sort(key=lambda row: int(row["priority_score"]), reverse=True)

    write_csv(
        out_dir / "proposed_categories.csv",
        classified,
        [
            "key", "title", "year", "doi", "primary_category",
            "secondary_categories", "tags", "priority_score", "authors",
            "first_author", "journal",
        ],
    )
    write_csv(
        out_dir / "missing_metadata.csv",
        missing_rows,
        ["key", "title", "year", "missing_fields"],
    )

    duplicate_rows: list[dict[str, str]] = []
    for value, grouped in sorted(by_doi.items()):
        if len(grouped) > 1:
            duplicate_rows.append({
                "duplicate_type": "doi",
                "value": value,
                "keys": "; ".join(item.get("key", "") for item in grouped),
                "titles": "; ".join(item.get("title", "") for item in grouped),
            })
    for value, grouped in sorted(by_title.items()):
        if len(grouped) > 1:
            duplicate_rows.append({
                "duplicate_type": "title",
                "value": value[:120],
                "keys": "; ".join(item.get("key", "") for item in grouped),
                "titles": "; ".join(item.get("title", "") for item in grouped),
            })
    write_csv(
        out_dir / "duplicate_candidates.csv",
        duplicate_rows,
        ["duplicate_type", "value", "keys", "titles"],
    )

    pdf_rows = [
        {
            "path": str(path),
            "filename": path.name,
            "size_bytes": str(path.stat().st_size),
        }
        for path in pdf_paths
    ]
    write_csv(out_dir / "pdf_inventory.csv", pdf_rows, ["path", "filename", "size_bytes"])

    write_ingest_candidates(out_dir / "wiki_ingest_candidates.md", classified)
    write_summary(
        out_dir / "library_audit_summary.md",
        entries,
        classified,
        missing_rows,
        duplicate_rows,
        pdf_paths,
        bib,
        pdf_root,
        find_file_fields(entries),
    )


def write_ingest_candidates(path: Path, classified: list[dict[str, str]]) -> None:
    top = classified[:60]
    rows = []
    for row in top:
        citation = f"{row['first_author']} {row['year']}".strip()
        reason_parts = [row["primary_category"]]
        if row["secondary_categories"]:
            reason_parts.append(row["secondary_categories"])
        if row["tags"]:
            reason_parts.append(row["tags"])
        rows.append([
            row["priority_score"],
            citation,
            row["title"][:120],
            row["doi"],
            "; ".join(reason_parts)[:180],
        ])
    content = [
        "# Wiki Ingest Candidates",
        "",
        "These are metadata-based suggestions from the Mendeley export.",
        "They are not yet part of the LLM-Wiki. Ingest only papers you approve and can provide as PDFs.",
        "",
        markdown_table(rows, ["Score", "Citation", "Title", "DOI", "Why it surfaced"]),
        "",
        "Recommended next step: choose 5 to 15 high-value papers, put their PDFs in `papers/inbox/`, then invoke the Ingester.",
    ]
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def write_summary(
    path: Path,
    entries: list[dict[str, str]],
    classified: list[dict[str, str]],
    missing_rows: list[dict[str, str]],
    duplicate_rows: list[dict[str, str]],
    pdf_paths: list[Path],
    bib: Path,
    pdf_root: Path | None,
    file_fields: list[str],
) -> None:
    category_counts = Counter(row["primary_category"] for row in classified)
    tag_counts: Counter[str] = Counter()
    for row in classified:
        for tag in row["tags"].split("; "):
            if tag:
                tag_counts[tag] += 1

    category_rows = [[category, str(count)] for category, count in category_counts.most_common()]
    tag_rows = [[tag, str(count)] for tag, count in tag_counts.most_common(20)]
    top_rows = [
        [
            row["priority_score"],
            f"{row['first_author']} {row['year']}".strip(),
            row["title"][:100],
            row["primary_category"],
        ]
        for row in classified[:20]
    ]

    if file_fields:
        pdf_note = (
            "The BibTeX export contains local file-like fields: "
            + ", ".join(file_fields)
            + ". A future matching script can use these."
        )
    else:
        pdf_note = (
            "No local PDF path fields were detected in the BibTeX export. "
            "Mendeley's `userfiles` PDFs use UUID filenames, so they should not be bulk-renamed or matched by filename."
        )

    content = [
        "# Mendeley Library Audit Summary",
        "",
        f"- Generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- BibTeX export: `{bib}`",
        f"- Entries parsed: {len(entries)}",
        f"- PDF root scanned: `{pdf_root}`" if pdf_root else "- PDF root scanned: not provided",
        f"- PDFs found under root: {len(pdf_paths)}",
        f"- Entries missing at least one required field: {len(missing_rows)}",
        f"- Potential duplicates: {len(duplicate_rows)}",
        "",
        "## PDF Linking Finding",
        "",
        pdf_note,
        "",
        "Recommendation: treat Mendeley's internal `userfiles` directory as read-only. Use `_system/mendeley/watch/` as the clean watched folder for new imports from the wiki.",
        "",
        "## Proposed Top-Level Mendeley Groups",
        "",
        "- `01. Topic A (customize)`",
        "- `02. Topic B (customize)`",
        "- `03. Topic C (customize)`",
        "- `04. Topic D (customize)`",
        "- `05. Topic E (customize)`",
        "- `Sexual dimorphism and hormone effects`",
        "- `Thalamo-cortical and basal ganglia circuits`",
        "- `Memory, affect, and social behavior`",
        "- `Methods, tools, and datasets`",
        "- `Reviews, protocols, and broad concepts`",
        "",
        "Use tags for disease/mechanism/method overlays rather than deeply nested folders.",
        "",
        "## Primary Category Counts",
        "",
        markdown_table(category_rows, ["Category", "Count"]) if category_rows else "_No entries classified._",
        "",
        "## Most Common Proposed Tags",
        "",
        markdown_table(tag_rows, ["Tag", "Count"]) if tag_rows else "_No tags detected._",
        "",
        "## Top Wiki-Ingest Candidates",
        "",
        markdown_table(top_rows, ["Score", "Citation", "Title", "Primary category"]) if top_rows else "_No candidates._",
        "",
        "## Generated Files",
        "",
        "- `proposed_categories.csv`: one proposed category/tag row per Mendeley entry",
        "- `wiki_ingest_candidates.md`: shortlist for LLM-Wiki ingestion",
        "- `duplicate_candidates.csv`: DOI/title duplicate candidates",
        "- `missing_metadata.csv`: references missing title, author, year, DOI, or abstract",
        "- `pdf_inventory.csv`: PDFs found under the provided PDF root",
    ]
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a Mendeley BibTeX export and propose categories for Mendeley plus LLM-Wiki ingestion."
    )
    parser.add_argument("--bib", required=True, type=Path, help="Path to Mendeley BibTeX export, e.g. _system/mendeley/export/library.bib")
    parser.add_argument("--pdf-root", type=Path, help="Optional Mendeley PDF storage root to inventory without modifying")
    parser.add_argument("--out", default=ROOT / "_system" / "mendeley" / "review", type=Path, help="Output directory for generated audit reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    bib = args.bib.expanduser().resolve()
    if not bib.exists():
        print(f"ERROR: BibTeX export not found: {bib}", file=sys.stderr)
        return 1
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    content = bib.read_text(encoding="utf-8", errors="replace")
    entries = iter_bib_entries(content)
    if not entries:
        print(f"ERROR: No BibTeX entries parsed from {bib}", file=sys.stderr)
        return 1
    pdf_root = args.pdf_root.expanduser().resolve() if args.pdf_root else None
    pdf_paths = find_pdf_paths(pdf_root)
    build_reports(entries, pdf_paths, out_dir, bib, pdf_root)
    print(f"Parsed {len(entries)} entries.")
    print(f"Found {len(pdf_paths)} PDFs under {pdf_root}." if pdf_root else "No PDF root scanned.")
    print(f"Wrote reports to {out_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
