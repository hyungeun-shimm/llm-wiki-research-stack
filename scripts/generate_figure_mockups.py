#!/usr/bin/env python3
"""Generate predicted/mock figure panels from figure-plan.md using local LLM.

Reads the 'Projected Figures' table in projects/{slug}/figure-plan.md.
For each panel row, asks LM Studio to generate matplotlib code that
produces a mock figure with realistically-shaped placeholder data.
Executes the code and saves the PNG to projects/{slug}/figure-mockups/.

Uses LM Studio at http://localhost:1234/v1 (Confidential phase).

Usage:
  python3 scripts/generate_figure_mockups.py --project 2026-my-paper
  python3 scripts/generate_figure_mockups.py --project 2026-my-paper --panel "Fig 1A"
  python3 scripts/generate_figure_mockups.py --project 2026-my-paper --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_MODEL = "qwen3.5-27b-instruct-mlx"


def parse_projected_figures_table(text: str) -> list[dict]:
    """Extract panel rows from the 'Projected Figures' markdown table."""
    panels: list[dict] = []
    in_section = False
    headers: list[str] = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.startswith("## "):
            in_section = "Projected Figures" in line
            headers = []
            continue
        if not in_section:
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if not headers:
            headers = [
                c.lower().replace(" ", "_").replace("/", "_").replace("?", "")
                for c in cells
            ]
            continue
        row = {headers[i]: cells[i] if i < len(cells) else "" for i in range(len(headers))}
        panel = row.get("figure_panel", "") or row.get("figure", "")
        if panel and panel.lower().startswith("fig"):
            row["_panel_name"] = panel
            panels.append(row)
    return panels


def safe_filename(panel_name: str) -> str:
    """Convert 'Fig 1A' to 'fig-1a'."""
    s = panel_name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "panel"


def build_panel_prompt(panel: dict, output_path: str) -> str:
    name = panel.get("_panel_name", "")
    claim = panel.get("working_claim", "")
    evidence = panel.get("planned_evidence_or_data", "")
    status = panel.get("status", "planned")
    notes = panel.get("notes", "")

    return f"""Generate Python matplotlib code that creates a MOCK predicted figure for this planned panel of a scientific paper.

PANEL: {name}
WORKING CLAIM: {claim}
PLANNED DATA: {evidence}
STATUS: {status}
NOTES: {notes}

REQUIREMENTS:
- Use only matplotlib and numpy (no seaborn, no pandas)
- Generate REALISTIC-SHAPED placeholder data that illustrates what the actual result is expected to look like (the shape, direction, and rough magnitude of the predicted effect)
- Include clear axis labels, units if implied, a title showing the panel name, and a legend if there are multiple groups
- figsize=(5.5, 4) and dpi=120
- Use a clean style: set plt.rcParams['axes.spines.top'] = False; plt.rcParams['axes.spines.right'] = False
- Color palette: primary navy '#1E2761', secondary teal '#1C7293', amber '#F59E0B', green '#16A34A', grey '#6B7280'. Pick 2–3 colors that make biological/scientific sense for the data type.
- Add a subtle "PREDICTED — MOCK DATA" annotation in the corner using fig.text(0.99, 0.01, ..., ha='right', va='bottom', fontsize=8, color='#9CA3AF', style='italic')
- Save with: fig.savefig(r'{output_path}', dpi=120, bbox_inches='tight'); plt.close(fig)

OUTPUT: Python code only, inside a ```python code block. No prose, no explanation, no preamble. The code must be self-contained and runnable as-is."""


def call_lm_studio(prompt: str, model: str) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 2500,
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


def extract_python_code(text: str) -> str:
    m = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--panel", default="", help="Generate only this panel (e.g. 'Fig 1A').")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true",
                        help="Save generated .py files but do not execute them.")
    args = parser.parse_args()

    project_dir = ROOT / "projects" / args.project
    figure_plan = project_dir / "figure-plan.md"
    if not figure_plan.exists():
        raise SystemExit(f"figure-plan.md not found in {project_dir.relative_to(ROOT)}")

    text = figure_plan.read_text(encoding="utf-8")
    panels = parse_projected_figures_table(text)
    if not panels:
        raise SystemExit("No panels found in 'Projected Figures' table.")

    if args.panel:
        target = args.panel.strip().lower()
        panels = [p for p in panels if p["_panel_name"].lower() == target]
        if not panels:
            raise SystemExit(f"Panel {args.panel!r} not found in figure-plan.md.")

    mockup_dir = project_dir / "figure-mockups"
    mockup_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for panel in panels:
        name = panel["_panel_name"]
        slug = safe_filename(name)
        py_path = mockup_dir / f"{slug}.py"
        png_path = mockup_dir / f"{slug}.png"

        print(f"  [{name}] requesting code from LM Studio...", file=sys.stderr)
        prompt = build_panel_prompt(panel, str(png_path))
        try:
            response = call_lm_studio(prompt, args.model)
            code = extract_python_code(response)
        except SystemExit:
            raise
        except Exception as e:
            results.append({"panel": name, "status": "error", "error": str(e)[:200]})
            continue

        py_path.write_text(code, encoding="utf-8")

        if args.dry_run:
            results.append({
                "panel": name,
                "status": "code-saved",
                "py": str(py_path.relative_to(ROOT)),
            })
            continue

        print(f"  [{name}] executing...", file=sys.stderr)
        try:
            run = subprocess.run(
                [sys.executable, str(py_path)],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT),
            )
        except subprocess.TimeoutExpired:
            results.append({"panel": name, "status": "timeout"})
            continue

        if run.returncode == 0 and png_path.exists():
            results.append({
                "panel": name, "status": "ok",
                "png": str(png_path.relative_to(ROOT)),
                "py": str(py_path.relative_to(ROOT)),
            })
        else:
            results.append({
                "panel": name, "status": "exec-error",
                "py": str(py_path.relative_to(ROOT)),
                "error": (run.stderr or run.stdout)[:400],
            })

    print(json.dumps({
        "ok": True,
        "project": args.project,
        "results": results,
        "summary": {
            "total": len(results),
            "succeeded": sum(1 for r in results if r["status"] == "ok"),
            "failed": sum(1 for r in results if r["status"] not in {"ok", "code-saved"}),
        },
    }, indent=2))


if __name__ == "__main__":
    main()
