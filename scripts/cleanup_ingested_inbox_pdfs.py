#!/usr/bin/env python3
"""Remove inbox PDFs that already exist in the canonical papers corpus.

`papers/inbox/` is a temporary intake area. After a PDF has been ingested into
canonical `papers/{stem}.pdf`, keeping another copy in the inbox only creates
dashboard noise and risks accidental re-ingest.

By default, this script compares PDFs by SHA-256 hash and deletes only exact
matches. Use `--match-title` for the occasional case where the inbox PDF is a
different copy of the same paper and the filename title tokens match a
canonical PDF.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "papers"
INBOX = PAPERS / "inbox"
ARCHIVE_ROOT = INBOX / "_archived"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_pdfs() -> list[Path]:
    return sorted(path for path in PAPERS.glob("*.pdf") if path.is_file())


def inbox_pdfs(include_archived: bool) -> list[Path]:
    direct = sorted(path for path in INBOX.glob("*.pdf") if path.is_file())
    if not include_archived or not ARCHIVE_ROOT.exists():
        return direct
    archived = sorted(path for path in ARCHIVE_ROOT.rglob("*.pdf") if path.is_file())
    return [*direct, *archived]


def title_key(path: Path) -> str:
    stem = path.stem.lower()
    stem = re.sub(r"^1-s2-0-[a-z0-9]+-main$", "", stem)
    stem = re.sub(r"^(?:pmc)?\d+[a-z]?$", "", stem)
    stem = re.sub(r"^[a-z]+-\d{4}-", "", stem)
    stem = re.sub(r"^\d{4}-", "", stem)
    stem = re.sub(r"-(?:pmc|\d+)$", "", stem)
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    words = [word for word in stem.split("-") if word]
    return "-".join(words[:6])


def title_matches(inbox_pdf: Path, canonical: Path) -> bool:
    inbox_key = title_key(inbox_pdf)
    canonical_key = title_key(canonical)
    if not inbox_key or not canonical_key:
        return False
    return inbox_key.startswith(canonical_key) or canonical_key.startswith(inbox_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report matches without deleting files.")
    parser.add_argument(
        "--match-title",
        action="store_true",
        help="Also delete non-identical PDFs when filename title tokens match a canonical paper.",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Also clean duplicate PDFs already moved under papers/inbox/_archived/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not INBOX.exists():
        print("No papers/inbox/ directory found.")
        return 0

    canonical = canonical_pdfs()
    canonical_by_hash: dict[str, Path] = {}
    for pdf in canonical:
        canonical_by_hash.setdefault(sha256(pdf), pdf)

    matches: list[tuple[Path, Path, str]] = []
    for inbox_pdf in inbox_pdfs(include_archived=args.include_archived):
        matched = canonical_by_hash.get(sha256(inbox_pdf))
        if matched:
            matches.append((inbox_pdf, matched, "hash"))
            continue
        if args.match_title:
            title_match = next((pdf for pdf in canonical if title_matches(inbox_pdf, pdf)), None)
            if title_match:
                matches.append((inbox_pdf, title_match, "title"))

    if not matches:
        print("No already-ingested inbox PDFs matched canonical papers.")
        return 0

    for inbox_pdf, matched, reason in matches:
        action = "Would delete" if args.dry_run else "Deleted"
        print(f"{action}: {inbox_pdf.relative_to(ROOT)}")
        print(f"  matched canonical by {reason}: {matched.relative_to(ROOT)}")
        if not args.dry_run:
            inbox_pdf.unlink()

    print(f"{'Would delete' if args.dry_run else 'Deleted'} {len(matches)} already-ingested inbox PDF(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
