"""Open selected paper URLs from a triage approval-board decision JSON.

This is the bridge between the human approval board and browser-assisted PDF
download. It reads the JSON file produced by the approval board's
`Download JSON` button, filters papers marked `download_pdf` and/or
`wiki_only_ingest`, writes a small queue markdown file next to the JSON, and
optionally opens the selected DOI/PubMed URLs in the default browser.

It does not bypass paywalls, download PDFs by itself, or modify the wiki.
Download PDFs only when you have legitimate access, then save them into
`papers/inbox/` for Ingester.
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path


def selected(decisions: list[dict], action: str) -> list[dict]:
    rows = []
    for item in decisions:
        flags = item.get("action", {})
        if action in {"download", "both"} and flags.get("download_pdf"):
            rows.append(item)
            continue
        if action in {"wiki", "both"} and flags.get("wiki_only_ingest"):
            rows.append(item)
    return rows


def item_url(item: dict) -> str:
    if item.get("url"):
        return item["url"]
    if item.get("doi"):
        return f"https://doi.org/{item['doi']}"
    return item.get("source_url", "")


def write_queue(path: Path, payload: dict, rows: list[dict]) -> Path:
    queue_path = path.with_name(path.stem + "_queue.md")
    lines = [
        f"# PDF Download Queue: {payload.get('project', '')} / {payload.get('batch', '')}",
        "",
        "Download selected PDFs into `papers/inbox/`.",
        "Use legitimate institutional, open-access, or author-provided access only.",
        "",
    ]
    for item in rows:
        flags = item.get("action", {})
        action_labels = []
        if flags.get("download_pdf"):
            action_labels.append("download_pdf")
        if flags.get("wiki_only_ingest"):
            action_labels.append("wiki_only_ingest")
        lines.extend(
            [
                f"## {item.get('title', 'Untitled')}",
                "",
                f"- action: {', '.join(action_labels)}",
                f"- bucket: {item.get('bucket', '')}",
                f"- year: {item.get('year', '')}",
                f"- source: {item.get('source', '')} {item.get('paper_id', '')}",
                f"- doi: {item.get('doi', '')}",
                f"- url: {item_url(item)}",
                f"- reason: {item.get('reason', '')}",
                f"- notes: {item.get('notes', '')}",
                "",
            ]
        )
    queue_path.write_text("\n".join(lines), encoding="utf-8")
    return queue_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions_json", help="JSON file downloaded from the approval board")
    parser.add_argument(
        "--action",
        choices=["download", "wiki", "both"],
        default="both",
        help="Which selected decisions to include",
    )
    parser.add_argument("--open", action="store_true", help="Open selected URLs in the default browser")
    parser.add_argument("--limit", type=int, default=0, help="Open at most N URLs when using --open")
    args = parser.parse_args()

    path = Path(args.decisions_json).expanduser()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [item for item in selected(payload.get("decisions", []), args.action) if item_url(item)]
    queue_path = write_queue(path, payload, rows)

    print(f"Wrote {queue_path}")
    print(f"{len(rows)} selected URL(s)")
    for item in rows:
        print(f"- {item.get('title', 'Untitled')} :: {item_url(item)}")

    if args.open:
        limit = args.limit or len(rows)
        for item in rows[:limit]:
            webbrowser.open_new_tab(item_url(item))
        print(f"Opened {min(limit, len(rows))} URL(s) in the default browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
