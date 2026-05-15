"""Run all scout sources and write a consolidated candidate file."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scout_common import mark_scout_queries_done, read_project_inputs


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", help="Path to a scoutable brief file")
    parser.add_argument("--exploration", help="Exploration slug; reads explorations/idea-notes/{slug}.md")
    parser.add_argument("--out", help="Output directory for candidate JSON files")
    parser.add_argument("--alerts-dir", default="~/gscholar-alerts", help="Directory containing forwarded .eml alert files")
    parser.add_argument("--include-done-queries", action="store_true", help="Run checked-off scout-queries.md items too")
    parser.add_argument("--queries-only", action="store_true", help="Run only scout-queries.md items, excluding Project_Brief must-include terms")
    parser.add_argument("--no-mark-queries-done", action="store_true", help="Do not mark pending scout-queries.md items as done after this run")
    return parser


def default_candidate_dir(slug: str) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return ROOT / "explorations" / "active" / slug / "candidates" / today


def resolve_inputs(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.brief and args.exploration:
        raise SystemExit("Use either --brief or --exploration, not both.")
    if args.exploration:
        slug = args.exploration.strip()
        if not slug or "/" in slug or slug in {".", ".."}:
            raise SystemExit(f"Invalid exploration slug: {args.exploration!r}")
        brief_path = ROOT / "explorations" / "idea-notes" / f"{slug}.md"
        if not brief_path.exists():
            raise SystemExit(f"Exploration idea-note not found: {brief_path.relative_to(ROOT)}")
        out_dir = Path(args.out).expanduser().resolve() if args.out else default_candidate_dir(slug).resolve()
        return brief_path.resolve(), out_dir
    if not args.brief:
        raise SystemExit("Either --brief or --exploration is required.")
    if not args.out:
        raise SystemExit("--out is required when using --brief.")
    return Path(args.brief).expanduser().resolve(), Path(args.out).expanduser().resolve()


def run_script(script: Path, extra_args: list[str]) -> dict:
    command = [sys.executable, str(script), *extra_args]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return {
        "script": script.name,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def dedupe_key(record: dict) -> str:
    title = "".join(ch for ch in (record.get("title") or "").lower() if ch.isalnum())
    return (record.get("doi") or title).strip()


def consolidate(out_dir: Path) -> int:
    seen: set[str] = set()
    merged: list[dict] = []
    for path in sorted(out_dir.glob("*.json")):
        if path.name == "_consolidated.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        key = dedupe_key(record)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(record)
    consolidated_path = out_dir / "_consolidated.json"
    consolidated_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(merged)


def write_errors(out_dir: Path, errors: list[dict]) -> None:
    payload = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
    }
    (out_dir / "_scout_errors.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    base = Path(__file__).resolve().parent
    brief_path, out_dir = resolve_inputs(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    shared = ["--brief", str(brief_path), "--out", str(out_dir)]
    if args.include_done_queries:
        shared.append("--include-done-queries")
    if args.queries_only:
        shared.append("--queries-only")
    results = [
        run_script(base / "scout_arxiv.py", shared),
        run_script(base / "scout_biorxiv.py", shared),
        run_script(base / "scout_pubmed.py", shared),
        run_script(base / "scout_semantic_scholar.py", shared),
        run_script(base / "parse_gscholar_alert.py", [*shared, "--alerts-dir", args.alerts_dir]),
    ]
    count = consolidate(out_dir)
    print(f"Wrote consolidated candidate file with {count} unique records to {out_dir / '_consolidated.json'}")
    errors = [
        {
            "script": result["script"],
            "returncode": result["returncode"],
            "stderr": result["stderr"].strip(),
        }
        for result in results
        if result["returncode"] != 0
    ]
    if errors:
        write_errors(out_dir, errors)
        print(f"Completed with {len(errors)} scout source error(s). See {out_dir / '_scout_errors.json'}", file=sys.stderr)
    marked = 0
    successful_sources = {
        result["script"]
        for result in results
        if result["returncode"] == 0 and result["script"] != "parse_gscholar_alert.py"
    }
    if not args.no_mark_queries_done and successful_sources:
        pending_queries = read_project_inputs(brief_path, include_brief=False)["scout_queries"]
        marked = mark_scout_queries_done(brief_path.parent / "scout-queries.md", pending_queries)
        if marked:
            print(f"Marked {marked} scout-queries.md item(s) as done.")
    elif not args.no_mark_queries_done:
        print("No non-alert scout source succeeded; scout-queries.md items were not marked done.", file=sys.stderr)
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
