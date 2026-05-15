#!/usr/bin/env python3
"""Generate a conceptual schematic figure for a paper_in_prep project.

The schematic is a single overarching SVG that shows the paper's direction
and framework. It always reads Project_Brief.md and, if present, also
reads introduction.md and results.md to anchor the schematic in real data.

Uses LM Studio at http://localhost:1234/v1 (Confidential phase).

Output: projects/{slug}/schematics/schematic-v{N}-{YYYY-MM-DD}.svg

Usage:
  python3 scripts/generate_schematic.py --project 2026-my-paper
  python3 scripts/generate_schematic.py --project 2026-my-paper --model qwen3.5-27b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_MODEL = "qwen3.5-27b-instruct-mlx"


def read_if_exists(path: Path, max_chars: int = 6000) -> str:
    """Read a file's text, truncated to max_chars."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        return text[:max_chars]
    except OSError:
        return ""


def next_version(directory: Path, prefix: str) -> int:
    if not directory.exists():
        return 1
    existing = list(directory.glob(f"{prefix}-v*-*.svg"))
    return len(existing) + 1


def build_prompt(brief: str, intro: str, results: str) -> str:
    """Construct the LLM prompt requesting SVG output."""
    stages_present = ["Project_Brief.md"]
    if intro: stages_present.append("Introduction draft")
    if results: stages_present.append("Results draft")
    stage_note = ", ".join(stages_present)

    has_data = "yes" if results else "no"

    return f"""You are designing a single overarching SCHEMATIC FIGURE for a scientific paper.

The schematic shows the paper's overall research direction at a glance — its central question, conceptual framework, key manipulations or comparisons, and predicted/observed relationships. It is the kind of figure that goes in the abstract or as Figure 1 to orient the reader.

You will receive the project sources below. Generate ONE SVG that:
- Visualizes the central hypothesis and the conceptual arc of the paper
- Uses simple geometric shapes (rectangles, circles, ellipses), arrows, and concise labels
- Shows relationships (cause→effect, condition→outcome, group comparisons) clearly
- Includes the paper's working title or central question as the schematic title
- Has 2–4 conceptual zones or columns that map onto the paper's logical flow
- Uses a clean academic palette: deep navy (#1E2761), teal (#1C7293), accent amber (#F59E0B), success green (#16A34A), background light (#F3F4F6), text dark (#111827)
- Available data status from drafts: {has_data} — if results data is present, subtly highlight or annotate which arrows/relationships are now backed by real data (use the green color for "observed", amber for "predicted")

SOURCES PROVIDED: {stage_note}

============================
## Project_Brief.md
{brief}

============================
## Introduction draft (if any)
{intro if intro else "(not yet drafted)"}

============================
## Results draft (if any)
{results if results else "(not yet available — schematic should show predictions only)"}
============================

OUTPUT REQUIREMENTS:
- Valid SVG, opens in any browser
- viewBox="0 0 1000 600"
- Use <defs> for arrow markers (one for "predicted/dashed", one for "observed/solid")
- All text uses font-family="Helvetica, Arial, sans-serif"
- Title at top (font-size 22, bold)
- A legend in the bottom-right corner indicating which arrows are predicted (amber dashed) vs observed (green solid) — only include legend if results draft was provided
- A small "SCHEMATIC v{{VERSION}}" watermark in bottom-left, font-size 10, fill="#9CA3AF"

Respond with the SVG code only, wrapped in a ```svg code block. No explanation text."""


def call_lm_studio(prompt: str, model: str) -> str:
    """Synchronously call LM Studio chat completion API."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4000,
    }
    req = urllib.request.Request(
        LM_STUDIO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        raise SystemExit(
            f"Failed to reach LM Studio at {LM_STUDIO_URL}. "
            f"Start the Local Server in LM Studio and try again. ({e})"
        )


def extract_svg(text: str) -> str:
    """Extract SVG content from the LLM response."""
    m = re.search(r"```(?:svg|xml)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
    else:
        candidate = text.strip()
    # Locate the actual <svg> root
    svg_start = candidate.find("<svg")
    if svg_start == -1:
        raise SystemExit("LLM response did not contain an <svg> root element.")
    svg_end = candidate.rfind("</svg>")
    if svg_end == -1:
        raise SystemExit("LLM response did not contain a closing </svg> tag.")
    return candidate[svg_start:svg_end + len("</svg>")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project slug (folder under projects/).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LM Studio model name.")
    parser.add_argument("--dry-run", action="store_true", help="Build prompt only; don't call LM Studio.")
    args = parser.parse_args()

    project_dir = ROOT / "projects" / args.project
    if not project_dir.exists():
        raise SystemExit(f"Project not found: {project_dir.relative_to(ROOT)}")

    brief_path = project_dir / "Project_Brief.md"
    if not brief_path.exists():
        raise SystemExit(f"Project_Brief.md not found in {project_dir.relative_to(ROOT)}")
    brief = read_if_exists(brief_path)

    # Look for introduction and results drafts (case-insensitive, with or without .draft suffix)
    drafts_dir = project_dir / "Drafts"
    intro = ""
    results = ""
    if drafts_dir.exists():
        for path in drafts_dir.glob("*.md"):
            name = path.stem.lower().replace(".draft", "")
            if name in ("introduction", "intro"):
                intro = read_if_exists(path)
            elif name in ("results", "result"):
                results = read_if_exists(path)

    schematics_dir = project_dir / "schematics"
    schematics_dir.mkdir(parents=True, exist_ok=True)
    version = next_version(schematics_dir, "schematic")
    out_path = schematics_dir / f"schematic-v{version}-{date.today().isoformat()}.svg"

    prompt = build_prompt(brief, intro, results)

    if args.dry_run:
        print(json.dumps({
            "ok": True,
            "dry_run": True,
            "intro_present": bool(intro),
            "results_present": bool(results),
            "would_write": str(out_path.relative_to(ROOT)),
            "prompt_length": len(prompt),
        }, indent=2))
        return

    print(f"  Generating schematic v{version} (intro={'y' if intro else 'n'}, results={'y' if results else 'n'})...",
          file=sys.stderr)
    response = call_lm_studio(prompt, args.model)
    svg = extract_svg(response)
    svg = svg.replace("{{VERSION}}", str(version))
    out_path.write_text(svg, encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "schematic": str(out_path.relative_to(ROOT)),
        "version": version,
        "intro_used": bool(intro),
        "results_used": bool(results),
    }, indent=2))


if __name__ == "__main__":
    main()
