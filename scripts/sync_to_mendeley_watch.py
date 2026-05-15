#!/usr/bin/env python3
"""Copy selected LLM-Wiki PDFs into the Mendeley watched folder.

The LLM-Wiki keeps canonical PDFs in `papers/`. Mendeley keeps its own internal
copies under an opaque `userfiles` directory. This script never touches that
internal directory. It only copies selected canonical PDFs into `_system/mendeley/watch/`
so Mendeley Reference Manager can import them through a watched folder.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "papers"
DEFAULT_WATCH = ROOT / "_system" / "mendeley" / "watch"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy selected PDFs from papers/ into the local Mendeley watched folder."
    )
    parser.add_argument(
        "--paper",
        action="append",
        type=Path,
        default=[],
        help="A PDF to copy. May be supplied multiple times.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Copy all canonical PDFs directly under papers/. Excludes inbox/ and under-review/.",
    )
    parser.add_argument(
        "--watch-dir",
        type=Path,
        default=DEFAULT_WATCH,
        help="Mendeley watched folder. Default: _system/mendeley/watch/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing files.",
    )
    return parser.parse_args(argv)


def canonical_pdfs() -> list[Path]:
    return sorted(path for path in PAPERS.glob("*.pdf") if path.is_file())


def resolve_paper(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = (ROOT / expanded).resolve()
    else:
        expanded = expanded.resolve()
    return expanded


def validate_pdf(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF: {path}")
    try:
        path.relative_to(PAPERS)
    except ValueError:
        raise ValueError(f"PDF must live under {PAPERS}: {path}") from None
    if "under-review" in path.parts:
        raise ValueError(f"Refusing to copy confidential under-review PDF: {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    watch_dir = args.watch_dir.expanduser()
    if not watch_dir.is_absolute():
        watch_dir = (ROOT / watch_dir).resolve()
    else:
        watch_dir = watch_dir.resolve()

    selected = [resolve_paper(path) for path in args.paper]
    if args.all:
        selected.extend(canonical_pdfs())
    unique = []
    seen = set()
    for path in selected:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    if not unique:
        print("ERROR: provide --paper path/to/file.pdf or --all", file=sys.stderr)
        return 1

    try:
        for path in unique:
            validate_pdf(path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        watch_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src in unique:
        dest = watch_dir / src.name
        action = "would copy" if args.dry_run else "copied"
        print(f"{action}: {src} -> {dest}")
        if not args.dry_run:
            shutil.copy2(src, dest)
        copied += 1

    print(f"{'Would copy' if args.dry_run else 'Copied'} {copied} PDF(s) to {watch_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
