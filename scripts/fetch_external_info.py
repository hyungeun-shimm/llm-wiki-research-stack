#!/usr/bin/env python3
"""Fetch external information from URLs for grant / job application context.

Saves to _system/docs/external-info/ (public path — NOT confidential).
User reviews the fetched content, then copies what they need to the project folder.

Supported info types:
  grant_info      — Grant program announcement, RFA, funding guidelines
  job_description — Job posting, position description
  dept_faculty    — Department faculty page (research interests, lab names)
  general         — Any URL, minimal processing

Usage:
    python3 scripts/fetch_external_info.py --url URL --type grant_info --slug my-project
    python3 scripts/fetch_external_info.py --url URL --type dept_faculty --slug job-app-stanford
    python3 scripts/fetch_external_info.py --url URL --type general --slug my-project --max-chars 8000
"""

from __future__ import annotations

import html
import re
import sys
import urllib.error
import urllib.request
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_INFO_DIR = ROOT / "_system" / "docs" / "external-info"

# Max characters of body text to keep (prevents huge files)
DEFAULT_MAX_CHARS = 12_000

# Sections we care about for each type (used for extraction hints)
GRANT_SECTION_HINTS = [
    "purpose", "objective", "eligibility", "funding", "priority", "aims",
    "mechanism", "deadline", "requirements", "budget", "page limit",
    "review criteria", "significance", "innovation", "approach",
    "letter of intent", "application", "due date",
]

FACULTY_HINTS = [
    "research interest", "lab", "laboratory", "professor", "associate",
    "assistant", "faculty", "ph.d", "phd", "neuroscience", "biology",
    "research focus", "current projects", "selected publications",
]

JOB_HINTS = [
    "qualifications", "responsibilities", "requirements", "duties",
    "preferred", "required", "apply", "application", "position",
    "tenure", "rank", "department", "salary", "benefits",
]


# ---------------------------------------------------------------------------
# HTML fetching and stripping
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_url(url: str, timeout: int = 30) -> tuple[str, str]:
    """Fetch URL. Returns (content_type, raw_text)."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "text/html")
            raw = resp.read()
            # Detect encoding
            encoding = "utf-8"
            ct_lower = content_type.lower()
            m = re.search(r"charset=([^\s;]+)", ct_lower)
            if m:
                encoding = m.group(1).strip()
            try:
                return content_type, raw.decode(encoding, errors="replace")
            except (LookupError, UnicodeDecodeError):
                return content_type, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTP {exc.code} fetching {url}: {exc.reason}")
    except urllib.error.URLError as exc:
        sys.exit(f"URL error fetching {url}: {exc.reason}")
    except Exception as exc:
        sys.exit(f"Fetch failed: {exc}")


def strip_html(raw: str) -> str:
    """Strip HTML tags and decode entities to plain text."""
    # Remove <script> and <style> blocks entirely
    raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<nav[^>]*>.*?</nav>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<footer[^>]*>.*?</footer>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<header[^>]*>.*?</header>", " ", raw, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings to markdown-style
    raw = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<h[4-6][^>]*>(.*?)</h[4-6]>", r"\n#### \1\n", raw, flags=re.DOTALL | re.IGNORECASE)

    # Convert <li> to bullets
    raw = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", raw, flags=re.DOTALL | re.IGNORECASE)

    # Convert <p> and <br> to newlines
    raw = re.sub(r"<p[^>]*>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</p>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<tr[^>]*>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<td[^>]*>", " | ", raw, flags=re.IGNORECASE)

    # Remove remaining tags
    raw = re.sub(r"<[^>]+>", " ", raw)

    # Decode HTML entities
    raw = html.unescape(raw)

    # Collapse whitespace
    raw = re.sub(r"\t", " ", raw)
    raw = re.sub(r" {3,}", "  ", raw)
    raw = re.sub(r"\n{4,}", "\n\n\n", raw)
    raw = "\n".join(line.rstrip() for line in raw.split("\n"))

    return raw.strip()


def extract_relevant_sections(text: str, hints: list[str], max_chars: int) -> str:
    """Keep paragraphs that mention hint keywords, plus a window around them."""
    if len(text) <= max_chars:
        return text

    lines = text.split("\n")
    scored: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        score = sum(1 for h in hints if h in line_lower)
        scored.append((score, line))

    # Keep high-scoring lines and their neighbors (context window ±3)
    keep = set()
    for i, (score, _) in enumerate(scored):
        if score > 0:
            for j in range(max(0, i - 3), min(len(scored), i + 4)):
                keep.add(j)

    if not keep:
        # No hint matches — just return the beginning
        return text[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"

    result_lines = []
    last_kept = -1
    for i, (_, line) in enumerate(scored):
        if i in keep:
            if last_kept != -1 and i > last_kept + 1:
                result_lines.append("\n[...]\n")
            result_lines.append(line)
            last_kept = i

    result = "\n".join(result_lines)
    if len(result) > max_chars:
        result = result[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
    return result


# ---------------------------------------------------------------------------
# Type-specific processors
# ---------------------------------------------------------------------------

def process_grant_info(text: str, max_chars: int) -> str:
    return (
        "## Grant Program Information\n\n"
        "_Relevant sections extracted. Review and verify against the original page._\n\n"
        + extract_relevant_sections(text, GRANT_SECTION_HINTS, max_chars)
    )


def process_job_description(text: str, max_chars: int) -> str:
    return (
        "## Job Posting\n\n"
        "_Relevant sections extracted. Review and verify against the original posting._\n\n"
        + extract_relevant_sections(text, JOB_HINTS, max_chars)
    )


def process_dept_faculty(text: str, max_chars: int) -> str:
    """Extract faculty names and research interests for synergy planning."""
    relevant = extract_relevant_sections(text, FACULTY_HINTS, max_chars)
    return (
        "## Department Faculty Research Map\n\n"
        "_Use this to identify potential collaborators and write department synergy sections._\n\n"
        "| Faculty Member | Research Focus | Synergy Potential |\n"
        "|---|---|---|\n"
        "| [Name] | [Topic from below] | [Fill in manually] |\n\n"
        "---\n\n"
        "### Raw Extracted Text\n\n"
        + relevant
    )


def process_general(text: str, max_chars: int) -> str:
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
    return "## Fetched Content\n\n" + text


PROCESSORS = {
    "grant_info": process_grant_info,
    "job_description": process_job_description,
    "dept_faculty": process_dept_faculty,
    "general": process_general,
}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_output(url: str, info_type: str, processed: str, slug: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"---\n"
        f"fetched: {today}\n"
        f"source_url: {url}\n"
        f"info_type: {info_type}\n"
        f"project_slug: {slug}\n"
        f"confidential_tier: external-ok\n"
        f"---\n\n"
        f"# External Info: {info_type.replace('_', ' ').title()}\n\n"
        f"> Fetched from: {url}  \n"
        f"> Date: {today}  \n"
        f"> Review this content and copy relevant parts to `projects/{slug}/` as needed.\n\n"
        f"---\n\n"
        f"{processed}\n\n"
        f"---\n\n"
        f"## How to Use\n\n"
        f"1. Review the content above\n"
        f"2. Copy the relevant sections to your project:\n"
        f"   - Grant info → `projects/{slug}/grant_info.md`\n"
        f"   - Job description → `projects/{slug}/job_description.md`\n"
        f"   - Faculty map → `projects/{slug}/notes/dept-faculty.md`\n"
        f"3. The local agent (Planner/Drafter) will automatically load these files\n"
    )


def save_output(content: str, slug: str, info_type: str) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    EXTERNAL_INFO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{slug}-{info_type}-{today}.md"
    out_path = EXTERNAL_INFO_DIR / filename
    # If file already exists, add a counter
    counter = 1
    while out_path.exists():
        filename = f"{slug}-{info_type}-{today}-{counter}.md"
        out_path = EXTERNAL_INFO_DIR / filename
        counter += 1
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = ArgumentParser(
        description=(
            "Fetch external info from a URL for grant/job application context. "
            "Saves to _system/docs/external-info/ (public, not confidential)."
        ),
    )
    parser.add_argument("--url", required=True, metavar="URL",
                        help="URL to fetch.")
    parser.add_argument(
        "--type", dest="info_type",
        choices=list(PROCESSORS),
        default="general",
        metavar="{grant_info|job_description|dept_faculty|general}",
        help="Type of info — controls extraction strategy. Default: general",
    )
    parser.add_argument("--slug", required=True, metavar="SLUG",
                        help="Project slug (used in filename and output path suggestions).")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, dest="max_chars",
                        help=f"Maximum characters to keep. Default: {DEFAULT_MAX_CHARS}")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Request timeout in seconds. Default: 30")
    args = parser.parse_args()

    print(f"Fetching: {args.url}")
    print(f"Type: {args.info_type}")

    content_type, raw = fetch_url(args.url, timeout=args.timeout)
    print(f"  Response: {len(raw):,} chars, content-type: {content_type[:60]}")

    # Strip HTML
    text = strip_html(raw)
    print(f"  After HTML strip: {len(text):,} chars")

    # Process by type
    processor = PROCESSORS[args.info_type]
    processed = processor(text, args.max_chars)
    print(f"  After extraction: {len(processed):,} chars")

    # Build and save output
    output = build_output(args.url, args.info_type, processed, args.slug)
    out_path = save_output(output, args.slug, args.info_type)

    rel = out_path.relative_to(ROOT)
    print(f"\n✓ Saved: {rel}")
    print("\nNext:")
    print(f"  Review: open {rel}")
    print(f"  Copy to project: cp {rel} projects/{args.slug}/grant_info.md")
    print(f"  (or job_description.md, or notes/dept-faculty.md)")


if __name__ == "__main__":
    main()
