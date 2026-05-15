#!/usr/bin/env python3
"""Import user-selected local PDFs into papers/inbox/.

This is a dashboard helper. It opens the macOS file picker, lets the user choose
one or more PDFs, then copies or moves them into the temporary ingest inbox.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "papers" / "inbox"


def choose_pdfs() -> list[Path]:
    script = """
set chosenFiles to choose file with prompt "Select PDF files to import into papers/inbox/" of type {"pdf", "PDF"} with multiple selections allowed
set outputText to ""
repeat with chosenFile in chosenFiles
    set outputText to outputText & POSIX path of chosenFile & linefeed
end repeat
return outputText
"""
    proc = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("No files selected.")
    return [Path(line).expanduser() for line in proc.stdout.splitlines() if line.strip()]


def unique_destination(src: Path) -> Path:
    dest = INBOX / src.name
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    index = 2
    while True:
        candidate = INBOX / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def import_pdf(src: Path, mode: str) -> Path:
    if not src.exists() or not src.is_file():
        raise ValueError(f"Not a file: {src}")
    if src.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF: {src}")
    INBOX.mkdir(parents=True, exist_ok=True)
    dest = unique_destination(src)
    if mode == "move":
        shutil.move(str(src), str(dest))
    else:
        shutil.copy2(src, dest)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["copy", "move"], default="copy")
    args = parser.parse_args()

    selected = choose_pdfs()
    imported: list[Path] = []
    skipped: list[str] = []
    for src in selected:
        try:
            imported.append(import_pdf(src, args.mode))
        except ValueError as exc:
            skipped.append(str(exc))

    print(f"Mode: {args.mode}")
    print(f"Imported: {len(imported)}")
    for path in imported:
        print(f"- {path.relative_to(ROOT)}")
    if skipped:
        print("Skipped:")
        for message in skipped:
            print(f"- {message}")
    return 0 if imported else 1


if __name__ == "__main__":
    raise SystemExit(main())
