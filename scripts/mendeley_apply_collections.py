#!/usr/bin/env python3
"""Apply proposed broad collections to a Mendeley library via the official API.

This script makes real Mendeley cloud-library changes only when `--apply` is
provided. It never touches Mendeley's local `userfiles` directory and never
deletes documents or removes them from old folders. The only write operations
are:

- create missing broad folders
- add matched documents to those folders

Authentication is read from `MENDELEY_ACCESS_TOKEN`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.mendeley.com"

CATEGORY_TO_FOLDER = {
    "topic-a": "01. Topic A (customize in CLAUDE.local.md)",
    "topic-b": "02. Topic B (customize in CLAUDE.local.md)",
    "topic-c": "03. Topic C (customize in CLAUDE.local.md)",
    "topic-d": "04. Topic D (customize in CLAUDE.local.md)",
    "pain-somatosensory": "05. Pain and somatosensory processing",
    "sexual-dimorphism": "06. Sexual dimorphism and hormone effects",
    "thalamo-basal-ganglia": "07. Thalamo-cortical and basal ganglia circuits",
    "memory-affect-social": "08. Memory, affect, and social behavior",
    "methods-tools": "09. Methods, tools, and datasets",
    "reviews-protocols": "10. Reviews, protocols, and broad concepts",
    "biotech-translational": "11. Biotech and translational",
    "neurodegenerative-disease": "99. Other / needs review",
    "other": "99. Other / needs review",
}


@dataclass
class ApiResponse:
    status: int
    headers: dict[str, str]
    body: object | None


def normalize_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value)
    return value.strip().strip(".;,")


def normalize_title(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_link_next(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        match = re.search(r"<([^>]+)>", section)
        if match:
            return match.group(1)
    return None


class MendeleyClient:
    def __init__(self, token: str, pause: float = 0.05) -> None:
        self.token = token
        self.pause = pause

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        accept: str,
        content_type: str | None = None,
        payload: dict | None = None,
        ok: set[int] | None = None,
    ) -> ApiResponse:
        ok = ok or {200, 201, 204}
        url = path_or_url if path_or_url.startswith("http") else f"{API_BASE}{path_or_url}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = content_type or accept
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        time.sleep(self.pause)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body_text = response.read().decode("utf-8", errors="replace")
                body = json.loads(body_text) if body_text else None
                return ApiResponse(response.status, dict(response.headers), body)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(body_text) if body_text else None
            except json.JSONDecodeError:
                body = body_text
            if exc.code in ok:
                return ApiResponse(exc.code, dict(exc.headers), body)
            raise RuntimeError(f"HTTP {exc.code} for {method} {url}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error for {method} {url}: {exc}") from exc

    def paged_get(self, path: str, *, accept: str) -> list[dict]:
        rows: list[dict] = []
        next_url: str | None = path
        while next_url:
            response = self.request("GET", next_url, accept=accept)
            if isinstance(response.body, list):
                rows.extend(response.body)
            else:
                raise RuntimeError(f"Expected list response for {path}, got {type(response.body).__name__}")
            next_url = parse_link_next(response.headers.get("Link"))
        return rows

    def list_documents(self) -> list[dict]:
        return self.paged_get(
            "/documents?view=all&limit=500",
            accept="application/vnd.mendeley-document.1+json",
        )

    def list_folders(self) -> list[dict]:
        return self.paged_get(
            "/folders?limit=500",
            accept="application/vnd.mendeley-folder.1+json",
        )

    def create_folder(self, name: str) -> dict:
        response = self.request(
            "POST",
            "/folders",
            accept="application/vnd.mendeley-folder.1+json",
            content_type="application/vnd.mendeley-folder.1+json",
            payload={"name": name},
            ok={201},
        )
        if not isinstance(response.body, dict):
            raise RuntimeError(f"Unexpected create-folder response for {name}: {response.body}")
        return response.body

    def add_document_to_folder(self, folder_id: str, document_id: str) -> str:
        try:
            self.request(
                "POST",
                f"/folders/{folder_id}/documents",
                accept="application/vnd.mendeley-document.1+json",
                content_type="application/vnd.mendeley-document.1+json",
                payload={"id": document_id},
                ok={201},
            )
            return "added"
        except RuntimeError as exc:
            message = str(exc).lower()
            if "409" in message or "already" in message:
                return "already-present"
            return f"error: {exc}"


def load_proposals(path: Path, limit: int | None) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: int(row.get("priority_score") or 0), reverse=True)
    if limit:
        rows = rows[:limit]
    return rows


def identifiers_to_dois(identifiers: object) -> list[str]:
    dois: list[str] = []
    if isinstance(identifiers, dict):
        doi = normalize_doi(str(identifiers.get("doi", "")))
        if doi:
            dois.append(doi)
    elif isinstance(identifiers, list):
        for item in identifiers:
            if isinstance(item, dict):
                value = normalize_doi(str(item.get("doi") or item.get("value") or ""))
                kind = str(item.get("type") or item.get("identifier_type") or "").lower()
                if value and (not kind or kind == "doi"):
                    dois.append(value)
    return sorted(set(dois))


def index_documents(documents: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    by_doi: dict[str, list[dict]] = {}
    by_title: dict[str, list[dict]] = {}
    for doc in documents:
        for doi in identifiers_to_dois(doc.get("identifiers")):
            by_doi.setdefault(doi, []).append(doc)
        title = normalize_title(str(doc.get("title", "")))
        if title:
            by_title.setdefault(title, []).append(doc)
    return by_doi, by_title


def find_matches(row: dict[str, str], by_doi: dict[str, list[dict]], by_title: dict[str, list[dict]]) -> tuple[list[dict], str]:
    doi = normalize_doi(row.get("doi", ""))
    if doi and doi in by_doi:
        return by_doi[doi], "doi"
    title = normalize_title(row.get("title", ""))
    if title and title in by_title:
        return by_title[title], "title"
    return [], "none"


def existing_folder_map(folders: list[dict]) -> dict[str, dict]:
    return {str(folder.get("name", "")): folder for folder in folders if folder.get("name")}


def ensure_folders(client: MendeleyClient, apply: bool, existing: dict[str, dict]) -> tuple[dict[str, str], list[str]]:
    folder_ids: dict[str, str] = {}
    created: list[str] = []
    for name in CATEGORY_TO_FOLDER.values():
        if name in existing:
            folder_ids[name] = str(existing[name]["id"])
            continue
        if not apply:
            folder_ids[name] = f"would-create:{name}"
            created.append(name)
            continue
        folder = client.create_folder(name)
        folder_ids[name] = str(folder["id"])
        created.append(name)
    return folder_ids, created


def write_report(out_dir: Path, rows: list[dict[str, str]], summary: dict[str, object]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = out_dir / f"mendeley_apply_collections_{stamp}.csv"
    md_path = out_dir / f"mendeley_apply_collections_{stamp}.md"
    fieldnames = [
        "status", "match_type", "folder", "document_id", "doi", "title",
        "key", "primary_category", "note",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Mendeley Apply Collections Report",
        "",
        f"- Generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- Mode: {'APPLY' if summary['apply'] else 'DRY RUN'}",
        f"- Proposals considered: {summary['proposal_count']}",
        f"- Mendeley documents fetched: {summary['document_count']}",
        f"- Folders created or would create: {summary['folders_created']}",
        f"- Added: {summary['added']}",
        f"- Already present: {summary['already_present']}",
        f"- Missing matches: {summary['missing']}",
        f"- Errors: {summary['errors']}",
        "",
        f"Detailed CSV: `{csv_path.name}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add Mendeley documents to broad collections based on _system/mendeley/review/proposed_categories.csv."
    )
    parser.add_argument("--proposals", type=Path, default=ROOT / "_system" / "mendeley" / "review" / "proposed_categories.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "_system" / "mendeley" / "review")
    parser.add_argument("--limit", type=int, help="Apply only the top N proposals by priority score.")
    parser.add_argument("--apply", action="store_true", help="Actually create folders and add documents. Without this, no writes occur.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    proposals_path = args.proposals.expanduser().resolve()
    if not proposals_path.exists():
        print(f"ERROR: proposals file not found: {proposals_path}", file=sys.stderr)
        return 1
    token = os.environ.get("MENDELEY_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: MENDELEY_ACCESS_TOKEN is not set. Cannot modify Mendeley via the official API.", file=sys.stderr)
        print("Set it in your shell first, then rerun with --apply.", file=sys.stderr)
        return 1

    proposals = load_proposals(proposals_path, args.limit)
    client = MendeleyClient(token)
    documents = client.list_documents()
    folders = existing_folder_map(client.list_folders())
    folder_ids, created_folders = ensure_folders(client, args.apply, folders)
    by_doi, by_title = index_documents(documents)

    seen_pairs: set[tuple[str, str]] = set()
    report_rows: list[dict[str, str]] = []
    counts = {
        "added": 0,
        "already_present": 0,
        "missing": 0,
        "errors": 0,
    }

    for row in proposals:
        category = row.get("primary_category", "")
        folder_name = CATEGORY_TO_FOLDER.get(category, CATEGORY_TO_FOLDER["other"])
        folder_id = folder_ids[folder_name]
        matches, match_type = find_matches(row, by_doi, by_title)
        if not matches:
            counts["missing"] += 1
            report_rows.append({
                "status": "missing-match",
                "match_type": match_type,
                "folder": folder_name,
                "document_id": "",
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "key": row.get("key", ""),
                "primary_category": category,
                "note": "No DOI/title match in fetched Mendeley documents",
            })
            continue
        for doc in matches:
            doc_id = str(doc.get("id", ""))
            if not doc_id:
                continue
            pair = (folder_id, doc_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            if args.apply:
                status = client.add_document_to_folder(folder_id, doc_id)
            else:
                status = "would-add"
            if status == "added" or status == "would-add":
                counts["added"] += 1
            elif status == "already-present":
                counts["already_present"] += 1
            else:
                counts["errors"] += 1
            report_rows.append({
                "status": status,
                "match_type": match_type,
                "folder": folder_name,
                "document_id": doc_id,
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "key": row.get("key", ""),
                "primary_category": category,
                "note": "",
            })

    report = write_report(
        args.out.expanduser().resolve(),
        report_rows,
        {
            "apply": args.apply,
            "proposal_count": len(proposals),
            "document_count": len(documents),
            "folders_created": len(created_folders),
            **counts,
        },
    )
    print(f"Wrote {report}")
    print(
        f"{'Applied' if args.apply else 'Planned'} {counts['added']} folder assignment(s); "
        f"{counts['already_present']} already present; {counts['missing']} missing; {counts['errors']} errors."
    )
    return 1 if counts["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
