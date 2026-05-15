"""Extract text from a PDF for wiki ingest.

This is an ingest-only helper for the LLM-Wiki workflow.
It prints extracted text to stdout or writes it to a file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def extract_text(pdf_path: Path, max_pages: int, max_chars: int) -> str:
    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover - dependency check
        raise SystemExit("Missing dependency: pypdf") from exc

    reader = pypdf.PdfReader(str(pdf_path))
    chunks: list[str] = []
    total = 0
    for page in reader.pages[:max_pages]:
        text = page.extract_text() or ""
        if not text:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        snippet = text[:remaining]
        chunks.append(snippet)
        total += len(snippet)
        if total >= max_chars:
            break
    return "\n".join(chunks).strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--pages", type=int, default=15, help="Maximum number of pages to read")
    parser.add_argument("--chars", type=int, default=12000, help="Maximum number of characters to emit")
    parser.add_argument("--output", help="Optional path to write extracted text")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    text = extract_text(pdf_path, args.pages, args.chars)
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
