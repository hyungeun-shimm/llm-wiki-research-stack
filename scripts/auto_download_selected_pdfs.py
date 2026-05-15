"""Automatically download accessible PDFs from an approval-board decision JSON.

This script reads the JSON produced by the triage approval board and attempts
to download PDFs for papers marked `download_pdf` or `wiki_only_ingest`.

It only uses ordinary publisher/DOI/PubMed URLs and saves files that are served
as PDFs. It does not bypass paywalls, solve CAPTCHAs, scrape credentials, or use
unauthorized access. Papers that require institutional login or manual handling
are written to an unresolved queue for browser-assisted follow-up.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urljoin

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "papers" / "inbox"
USER_AGENT = "Mozilla/5.0 research-system-pdf-downloader/1.0"


class PdfLinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "meta":
            name = (attr.get("name") or attr.get("property") or "").lower()
            if name in {"citation_pdf_url", "dc.identifier", "bepress_citation_pdf_url"} and attr.get("content"):
                self.links.append(urljoin(self.base_url, attr["content"]))
        if tag.lower() in {"a", "link"}:
            href = attr.get("href")
            if not href:
                return
            text = " ".join([href, attr.get("type", ""), attr.get("title", ""), attr.get("aria-label", "")]).lower()
            if ".pdf" in text or "pdf" in text or "application/pdf" in text:
                self.links.append(urljoin(self.base_url, href))


@dataclass
class DownloadResult:
    title: str
    doi: str
    source_url: str
    action: str
    status: str
    pdf_path: str = ""
    attempted_urls: list[str] | None = None
    reason: str = ""


def slugify(value: str, max_len: int = 90) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:max_len].strip("-") or "paper"


def selected_rows(payload: dict, action: str) -> list[dict]:
    rows: list[dict] = []
    for item in payload.get("decisions", []):
        flags = item.get("action", {})
        if action in {"download", "both"} and flags.get("download_pdf"):
            rows.append(item)
            continue
        if action in {"wiki", "both"} and flags.get("wiki_only_ingest"):
            rows.append(item)
    return rows


def known_pdf_candidates(doi: str, url: str) -> list[str]:
    if not doi:
        return [url] if url else []
    encoded = quote(doi, safe="/.:")
    candidates = [
        f"https://doi.org/{encoded}",
        url,
    ]
    if doi.startswith("10.1007/"):
        candidates.append(f"https://link.springer.com/content/pdf/{encoded}.pdf")
    if doi.startswith("10.1371/"):
        candidates.append(f"https://journals.plos.org/ploscompbiol/article/file?id={encoded}&type=printable")
    if doi.startswith("10.3389/"):
        candidates.extend(
            [
                f"https://www.frontiersin.org/articles/{encoded}/pdf",
                f"https://www.frontiersin.org/journals/cellular-neuroscience/articles/{encoded}/pdf",
            ]
        )
    if doi.startswith("10.1152/"):
        candidates.append(f"https://journals.physiology.org/doi/pdf/{encoded}")
    if doi.startswith("10.1523/"):
        candidates.append(f"https://www.jneurosci.org/doi/pdf/{encoded}")
    if doi.startswith("10.1002/"):
        candidates.extend(
            [
                f"https://onlinelibrary.wiley.com/doi/pdf/{encoded}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{encoded}",
            ]
        )
    match = re.match(r"10\.64898/(\d{4}\.\d{2}\.\d{2}\.\d+)(v\d+)?", doi)
    if match:
        version = match.group(2) or "v1"
        candidates.append(f"https://www.biorxiv.org/content/10.1101/{match.group(1)}{version}.full.pdf")
        candidates.append(f"https://www.medrxiv.org/content/10.1101/{match.group(1)}{version}.full.pdf")
    return dedupe([candidate for candidate in candidates if candidate])


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def looks_like_pdf(response: requests.Response, content: bytes) -> bool:
    ctype = response.headers.get("content-type", "").lower()
    if "application/pdf" in ctype:
        return True
    return content[:5] == b"%PDF-"


def fetch(session: requests.Session, url: str, timeout: int = 25) -> requests.Response:
    return session.get(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": USER_AGENT})


def looks_like_login_or_paywall(html_text: str) -> bool:
    text = html_text[:200_000].lower()
    markers = [
        "institutional login",
        "sign in through your institution",
        "log in through your institution",
        "access through your institution",
        "shibboleth",
        "openathens",
        "single sign-on",
        "purchase access",
        "get access",
        "subscribe to",
        "rent this article",
        "login required",
        "sign in to access",
    ]
    return any(marker in text for marker in markers)


def discover_pdf_links(session: requests.Session, url: str) -> list[str]:
    try:
        response = fetch(session, url)
    except requests.RequestException:
        return []
    ctype = response.headers.get("content-type", "").lower()
    if "text/html" not in ctype and "<html" not in response.text[:500].lower():
        return []
    parser = PdfLinkParser(str(response.url))
    parser.feed(response.text[:800_000])
    return dedupe(parser.links)


def download_one(session: requests.Session, item: dict, out_dir: Path) -> DownloadResult:
    doi = item.get("doi", "")
    title = item.get("title", "Untitled")
    url = item.get("url") or item.get("source_url") or (f"https://doi.org/{doi}" if doi else "")
    action_flags = item.get("action", {})
    action = ",".join(
        label for label, enabled in {
            "download_pdf": action_flags.get("download_pdf"),
            "wiki_only_ingest": action_flags.get("wiki_only_ingest"),
        }.items() if enabled
    )
    attempted: list[str] = []
    candidates = known_pdf_candidates(doi, url)
    candidates.extend(discover_pdf_links(session, url) if url else [])
    candidates = dedupe(candidates)
    manual_required = False

    filename = f"{item.get('year') or 'unknown'}-{slugify(title)}.pdf"
    dest = out_dir / filename
    suffix = 2
    while dest.exists():
        dest = out_dir / f"{Path(filename).stem}-{suffix}.pdf"
        suffix += 1

    for candidate in candidates:
        attempted.append(candidate)
        try:
            response = fetch(session, candidate)
        except requests.RequestException as exc:
            last_error = str(exc)
            continue
        content = response.content
        if response.status_code >= 400:
            last_error = f"HTTP {response.status_code}"
            if response.status_code in {401, 403}:
                manual_required = True
            continue
        if looks_like_pdf(response, content) and len(content) > 10_000:
            out_dir.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return DownloadResult(
                title=title,
                doi=doi,
                source_url=url,
                action=action,
                status="downloaded",
                pdf_path=str(dest),
                attempted_urls=attempted,
            )
        # If DOI resolved to an HTML page, parse it once for PDF links.
        ctype = response.headers.get("content-type", "").lower()
        if "text/html" in ctype or content[:200].lower().find(b"<html") != -1:
            if looks_like_login_or_paywall(response.text):
                manual_required = True
            parser = PdfLinkParser(str(response.url))
            try:
                parser.feed(response.text[:800_000])
            except UnicodeDecodeError:
                pass
            for discovered in parser.links:
                if discovered not in candidates:
                    candidates.append(discovered)
        last_error = f"not a PDF ({response.headers.get('content-type', 'unknown content-type')})"
        time.sleep(0.2)

    return DownloadResult(
        title=title,
        doi=doi,
        source_url=url,
        action=action,
        status="login_or_manual_required" if manual_required else "unresolved",
        attempted_urls=attempted,
        reason=last_error if "last_error" in locals() else "no PDF candidate found",
    )


def default_report_dir(payload: dict, decisions_path: Path) -> Path:
    project = payload.get("project")
    if project:
        project_reports = ROOT / "projects" / project / "triage-reports"
        if project_reports.exists():
            return project_reports
    if decisions_path.parent.exists() and str(decisions_path.parent).startswith(str(ROOT)):
        return decisions_path.parent
    return ROOT / "_system" / "downloads"


def write_reports(
    results: list[DownloadResult],
    decisions_path: Path,
    payload: dict,
    report_dir: Path | None = None,
) -> tuple[Path, Path]:
    report_root = report_dir or default_report_dir(payload, decisions_path)
    report_root.mkdir(parents=True, exist_ok=True)
    batch = payload.get("batch") or decisions_path.stem
    json_path = report_root / f"{batch}_auto-download-results.json"
    md_path = report_root / f"{batch}_auto-download-results.md"
    json_path.write_text(json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False) + "\n")
    lines = ["# Auto PDF Download Results", ""]
    lines.extend(
        [
            f"- project: {payload.get('project', '')}",
            f"- batch: {payload.get('batch', '')}",
            f"- downloaded: {sum(1 for result in results if result.status == 'downloaded')}",
            f"- login_or_manual_required: {sum(1 for result in results if result.status == 'login_or_manual_required')}",
            f"- unresolved: {sum(1 for result in results if result.status == 'unresolved')}",
            "",
        ]
    )
    for result in results:
        lines.extend(
            [
                f"## {result.status.upper()}: {result.title}",
                "",
                f"- doi: {result.doi}",
                f"- action: {result.action}",
                f"- pdf_path: {result.pdf_path}",
                f"- source_url: {result.source_url}",
                f"- reason: {result.reason}",
                "- attempted_urls:",
                *[f"  - {url}" for url in (result.attempted_urls or [])],
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions_json", help="Decision JSON downloaded from the approval board")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Directory for downloaded PDFs")
    parser.add_argument("--report-dir", help="Directory for download reports. Defaults to the project's triage-reports/")
    parser.add_argument("--action", choices=["download", "wiki", "both"], default="both")
    args = parser.parse_args()

    decisions_path = Path(args.decisions_json).expanduser()
    payload = json.loads(decisions_path.read_text(encoding="utf-8"))
    rows = selected_rows(payload, args.action)
    if not rows:
        print("No selected rows found.")
        return 0

    session = requests.Session()
    out_dir = Path(args.out).expanduser()
    results: list[DownloadResult] = []
    for index, item in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {item.get('title', 'Untitled')}", flush=True)
        result = download_one(session, item, out_dir)
        print(f"  -> {result.status} {result.pdf_path or result.reason}", flush=True)
        results.append(result)

    report_dir = Path(args.report_dir).expanduser() if args.report_dir else None
    if report_dir and not report_dir.is_absolute():
        report_dir = ROOT / report_dir
    json_path, md_path = write_reports(results, decisions_path, payload, report_dir)
    downloaded = sum(1 for result in results if result.status == "downloaded")
    login_or_manual = sum(1 for result in results if result.status == "login_or_manual_required")
    unresolved = len(results) - downloaded - login_or_manual
    print(f"Downloaded: {downloaded}")
    print(f"Login/manual required: {login_or_manual}")
    print(f"Unresolved: {unresolved}")
    print(f"Results JSON: {json_path}")
    print(f"Results MD: {md_path}")
    return 0 if downloaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
