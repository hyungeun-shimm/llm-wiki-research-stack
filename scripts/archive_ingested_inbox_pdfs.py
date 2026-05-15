#!/usr/bin/env python3
"""Compatibility wrapper for the old archive helper.

The current workflow deletes duplicate inbox PDFs after successful ingest. Use
`scripts/cleanup_ingested_inbox_pdfs.py` directly for the maintained command.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("Deprecated: use scripts/cleanup_ingested_inbox_pdfs.py instead.")
    command = [sys.executable, "scripts/cleanup_ingested_inbox_pdfs.py", *sys.argv[1:]]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
