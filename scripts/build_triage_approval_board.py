"""Build a local interactive approval board for triaged paper candidates.

The board is a human gate between Triage and PDF download. It lets the user
review candidates in one local HTML page and mark only the papers to skip.
Non-skipped rows are treated as the PDF download queue.

The script does not call external APIs, download PDFs, or modify the wiki. It
only reads candidate JSONs plus an optional machine-readable triage JSON and
writes a markdown checklist and local HTML board into the project's
`triage-reports/` folder.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUCKET_ORDER = ["in-scope", "borderline", "out-of-scope", "untriaged"]
BUCKET_LABELS = {
    "in-scope": "In-scope (high confidence)",
    "borderline": "Borderline (needs human review)",
    "out-of-scope": "Out-of-scope",
    "untriaged": "Untriaged candidates",
}


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def newest_batch(project: Path) -> str:
    candidates = project / "candidates"
    batches = sorted(path for path in candidates.iterdir() if path.is_dir())
    if not batches:
        raise SystemExit(f"No candidate batches found in {relative(candidates)}")
    return batches[-1].name


def normalize_bucket(value: str | None) -> str:
    bucket = (value or "untriaged").strip().lower()
    bucket = bucket.replace("_", "-")
    if bucket in {"in", "in-scope", "inscope", "in scope"}:
        return "in-scope"
    if bucket in {"borderline", "border-line"}:
        return "borderline"
    if bucket in {"out", "out-of-scope", "outscope", "out of scope"}:
        return "out-of-scope"
    return "untriaged"


def load_candidate_items(batch_dir: Path) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for path in sorted(batch_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        paper_id = str(data.get("paper_id") or data.get("id") or path.stem)
        key = data.get("doi") or f"{data.get('source', 'unknown')}:{paper_id}" or data.get("title", path.stem)
        items[str(key)] = {
            "bucket": "untriaged",
            "title": data.get("title", ""),
            "authors": data.get("authors", []),
            "year": data.get("year", ""),
            "source": data.get("source", ""),
            "paper_id": paper_id,
            "doi": data.get("doi", ""),
            "source_url": data.get("source_url", ""),
            "reason": "Not triaged yet.",
            "abstract": data.get("abstract", ""),
        }
    return items


def load_triage_items(project: Path, batch: str) -> dict[str, dict]:
    triage_json = project / "triage-reports" / f"{batch}.json"
    if not triage_json.exists():
        return {}
    data = json.loads(triage_json.read_text(encoding="utf-8"))
    rows = data.get("items", data if isinstance(data, list) else [])
    items: dict[str, dict] = {}
    for row in rows:
        paper_id = str(row.get("paper_id") or row.get("id") or "")
        key = row.get("doi") or f"{row.get('source', 'unknown')}:{paper_id}" or row.get("title", "")
        items[str(key)] = {
            "bucket": normalize_bucket(row.get("bucket")),
            "title": row.get("title", ""),
            "authors": row.get("authors", []),
            "year": row.get("year", ""),
            "source": row.get("source", ""),
            "paper_id": paper_id,
            "doi": row.get("doi", ""),
            "source_url": row.get("source_url", ""),
            "reason": row.get("reason", ""),
            "abstract": row.get("abstract", ""),
        }
    return items


def item_keys(item: dict) -> list[str]:
    keys = []
    for value in (
        item.get("doi"),
        item.get("source_url"),
        item.get("url"),
        f"{item.get('source', '')}:{item.get('paper_id', '')}" if item.get("source") or item.get("paper_id") else "",
        item.get("title"),
    ):
        if value and str(value) not in keys:
            keys.append(str(value))
    return keys


def load_auto_download_results(project: Path, batch: str) -> dict[str, dict]:
    results_path = project / "triage-reports" / f"{batch}_auto-download-results.json"
    if not results_path.exists():
        return {}
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    results: dict[str, dict] = {}
    for row in rows:
        for key in item_keys(row):
            results[key] = row
    return results


def attach_download_status(project: Path, batch: str, items: list[dict]) -> list[dict]:
    results = load_auto_download_results(project, batch)
    for item in items:
        match = None
        for key in item_keys(item):
            if key in results:
                match = results[key]
                break
        if match:
            item["download_status"] = match.get("status", "attempted")
            item["download_pdf_path"] = match.get("pdf_path", "")
            item["download_reason"] = match.get("reason", "")
        else:
            item["download_status"] = "not_attempted"
            item["download_pdf_path"] = ""
            item["download_reason"] = ""
    return items


def merge_items(candidate_items: dict[str, dict], triage_items: dict[str, dict]) -> list[dict]:
    merged = candidate_items.copy()
    for key, triage_item in triage_items.items():
        base = merged.get(key, {})
        merged[key] = {**base, **triage_item}
    return sorted(
        merged.values(),
        key=lambda item: (
            BUCKET_ORDER.index(normalize_bucket(item.get("bucket")))
            if normalize_bucket(item.get("bucket")) in BUCKET_ORDER
            else len(BUCKET_ORDER),
            str(item.get("year", "")),
            item.get("title", ""),
        ),
    )


def link_for(item: dict) -> str:
    if item.get("doi"):
        return f"https://doi.org/{item['doi']}"
    return item.get("source_url") or ""


def md_escape(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_markdown(path: Path, project: Path, batch: str, items: list[dict]) -> None:
    items = attach_download_status(project, batch, items)
    lines = [
        f"# Triage Approval Board: {project.name} / {batch}",
        "",
        "Use this file after Triage. Non-skipped rows are treated as the PDF download queue.",
        "",
        "- `[ ] Skip`: no action.",
        "",
    ]
    for bucket in BUCKET_ORDER:
        bucket_items = [item for item in items if normalize_bucket(item.get("bucket")) == bucket]
        if not bucket_items:
            continue
        lines.extend(
            [
                f"## {BUCKET_LABELS[bucket]}",
                "",
                "| Skip | Auto status | Title | Year | Source | DOI / URL | Reason | Notes |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for item in bucket_items:
            url = link_for(item)
            title = md_escape(item.get("title"))
            link = f"[link]({url})" if url else ""
            lines.append(
                f"| [ ] | {md_escape(item.get('download_status'))} | "
                f"{title} | {md_escape(item.get('year'))} | {md_escape(item.get('source'))} | "
                f"{md_escape(item.get('doi')) or link} | {md_escape(item.get('reason'))} |  |"
            )
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def js_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_html(path: Path, project: Path, batch: str, items: list[dict]) -> None:
    items = attach_download_status(project, batch, items)
    payload = [
        {
            "bucket": normalize_bucket(item.get("bucket")),
            "bucket_label": BUCKET_LABELS.get(normalize_bucket(item.get("bucket")), "Untriaged candidates"),
            "title": item.get("title", ""),
            "authors": item.get("authors", []),
            "year": item.get("year", ""),
            "source": item.get("source", ""),
            "paper_id": item.get("paper_id", ""),
            "doi": item.get("doi", ""),
            "source_url": item.get("source_url", ""),
            "url": link_for(item),
            "reason": item.get("reason", ""),
            "abstract": item.get("abstract", ""),
            "download_status": item.get("download_status", "not_attempted"),
            "download_pdf_path": item.get("download_pdf_path", ""),
            "download_reason": item.get("download_reason", ""),
        }
        for item in items
    ]
    report_dir = relative(project / "triage-reports")
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Triage Approval Board</title>
  <style>
    :root {{ --bg:#f6f7f9; --surface:#fff; --ink:#1d2430; --muted:#667085; --line:#d9dee7; --accent:#0f766e; --blue:#2563eb; --warn:#b45309; --danger:#b42318; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; padding:24px; background:var(--bg); color:var(--ink); font-family:"Avenir Next","Segoe UI",sans-serif; }}
    header, section {{ max-width:1180px; margin:0 auto 18px; }}
    header {{ display:flex; justify-content:space-between; gap:16px; align-items:end; border-bottom:1px solid var(--line); padding-bottom:18px; }}
    h1 {{ margin:0; font-size:1.8rem; }}
    h2 {{ margin:22px 0 10px; font-size:1.1rem; }}
    p {{ color:var(--muted); line-height:1.5; }}
    .controls, .item {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; box-shadow:0 8px 24px rgba(16,24,40,.08); }}
    .controls {{ padding:14px; display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
    button, select {{ min-height:36px; border:1px solid var(--line); border-radius:8px; background:#fff; font:inherit; padding:7px 10px; }}
    button.primary {{ background:var(--accent); border-color:var(--accent); color:#fff; font-weight:700; }}
    #board-status {{ color:var(--muted); font-size:.86rem; white-space:pre-wrap; flex:1 1 100%; }}
    .grid {{ display:grid; gap:10px; }}
    .item {{ padding:14px; }}
    .item[data-bucket="in-scope"] {{ border-left:5px solid var(--accent); }}
    .item[data-bucket="borderline"] {{ border-left:5px solid var(--warn); }}
    .item[data-bucket="out-of-scope"] {{ border-left:5px solid var(--danger); }}
    .item-head {{ display:flex; justify-content:space-between; gap:12px; align-items:start; }}
    .title {{ font-weight:800; font-size:1rem; }}
    .meta {{ color:var(--muted); font-size:.86rem; margin-top:5px; }}
    .reason {{ margin:10px 0; color:var(--ink); }}
    .abstract {{ color:var(--muted); font-size:.9rem; line-height:1.45; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; padding-top:10px; border-top:1px solid var(--line); }}
    label {{ display:inline-flex; gap:6px; align-items:center; font-weight:700; }}
    input[type="text"] {{ flex:1 1 260px; min-height:34px; border:1px solid var(--line); border-radius:7px; padding:7px; font:inherit; }}
    .pill {{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 8px; font-size:.72rem; font-weight:800; text-transform:uppercase; background:#eef2f7; }}
    .status-pill {{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 8px; font-size:.72rem; font-weight:800; text-transform:uppercase; margin-top:7px; }}
    .status-downloaded {{ background:#dff5f1; color:var(--accent); }}
    .status-login_or_manual_required, .status-unresolved {{ background:#fff2d6; color:var(--warn); }}
    .status-not_attempted {{ background:#eef2f7; color:var(--muted); }}
    .steps {{ max-width:1180px; margin:0 auto 18px; padding:14px; background:#fff; border:1px solid var(--line); border-radius:10px; box-shadow:0 8px 24px rgba(16,24,40,.08); }}
    .steps ol {{ margin:8px 0 0; color:var(--muted); line-height:1.55; }}
    .link {{ color:var(--blue); text-decoration:none; font-weight:700; }}
    textarea {{ width:100%; min-height:210px; border:1px solid var(--line); border-radius:8px; padding:10px; font-family:"IBM Plex Mono",monospace; }}
  </style>
</head>
<body>
  <header>
    <div>
      <p>Triage Approval Board</p>
      <h1>{html.escape(project.name)} / {html.escape(batch)}</h1>
      <p>Generated {html.escape(generated)}. Non-skipped papers are included in the PDF queue. Skip choices are stored in this browser's localStorage.</p>
    </div>
  </header>
  <section class="steps">
    <h2>How auto-download works</h2>
    <ol>
      <li>Review the list and check `Skip` only for papers you do not want.</li>
      <li>Click `Run auto-download` to save accessible PDFs into `papers/inbox/`.</li>
      <li>If the server is not running, use `Download queue JSON` as a fallback and run `scripts/auto_download_selected_pdfs.py` manually.</li>
      <li>Rebuild/open this board again. Downloaded papers show `downloaded`; blocked papers show `manual required` or `unresolved`.</li>
    </ol>
  </section>
  <section class="controls">
    <select id="bucket-filter">
      <option value="all">All buckets</option>
      <option value="in-scope">In-scope</option>
      <option value="borderline">Borderline</option>
      <option value="out-of-scope">Out-of-scope</option>
      <option value="untriaged">Untriaged</option>
    </select>
    <select id="status-filter">
      <option value="all">All statuses</option>
      <option value="downloaded">Downloaded</option>
      <option value="manual">Manual required</option>
      <option value="not_attempted">Not attempted</option>
    </select>
    <button id="clear-all" type="button">Clear skips</button>
    <button id="run-auto-download" class="primary" type="button">Run auto-download</button>
    <button id="download-json" type="button">Download queue JSON</button>
    <span id="board-status"></span>
  </section>
  <section id="items" class="grid"></section>
  <section>
    <h2>Queue preview</h2>
    <p>This is the current non-skipped download queue. Downloaded PDFs go into <code>papers/inbox/</code> before normal ingest.</p>
    <textarea id="export-box" readonly></textarea>
  </section>
  <script>
    const items = {js_json(payload)};
    const storageKey = "triage-board:" + {js_json(project.name)} + ":" + {js_json(batch)};
    const state = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
    const root = document.getElementById("items");
    const exportBox = document.getElementById("export-box");
    const bucketFilter = document.getElementById("bucket-filter");
    const statusFilter = document.getElementById("status-filter");
    const boardStatus = document.getElementById("board-status");
    function keyFor(item, index) {{
      return item.doi || `${{item.source}}:${{item.paper_id}}` || `${{index}}`;
    }}

    function save() {{
      localStorage.setItem(storageKey, JSON.stringify(state));
    }}

    function render() {{
      root.replaceChildren();
      const filter = bucketFilter.value;
      const statusValue = statusFilter.value;
      items.forEach((item, index) => {{
        if (filter !== "all" && item.bucket !== filter) return;
        if (statusValue === "downloaded" && item.download_status !== "downloaded") return;
        if (statusValue === "manual" && !["login_or_manual_required", "unresolved"].includes(item.download_status)) return;
        if (statusValue === "not_attempted" && item.download_status !== "not_attempted") return;
        const key = keyFor(item, index);
        state[key] ||= {{ skip:false, notes:"" }};
        const card = document.createElement("article");
        card.className = "item";
        card.dataset.bucket = item.bucket;
        const link = item.url ? `<a class="link" href="${{item.url}}" target="_blank" rel="noreferrer">open source</a>` : "";
        const statusClass = `status-${{item.download_status || "not_attempted"}}`;
        const statusText = (item.download_status || "not_attempted").replaceAll("_", " ");
        const statusDetail = item.download_pdf_path
          ? `<div class="meta">Saved: ${{escapeHtml(item.download_pdf_path)}}</div>`
          : (item.download_reason ? `<div class="meta">Reason: ${{escapeHtml(item.download_reason)}}</div>` : "");
        card.innerHTML = `
          <div class="item-head">
            <div>
              <div class="title">${{escapeHtml(item.title)}}</div>
              <div class="meta">${{escapeHtml(String(item.year || ""))}} · ${{escapeHtml(item.source || "")}} · ${{escapeHtml(item.doi || item.paper_id || "")}} ${{link}}</div>
              <span class="status-pill ${{statusClass}}">${{escapeHtml(statusText)}}</span>
              ${{statusDetail}}
            </div>
            <span class="pill">${{escapeHtml(item.bucket_label)}}</span>
          </div>
          <p class="reason">${{escapeHtml(item.reason || "")}}</p>
          <details><summary>Abstract</summary><p class="abstract">${{escapeHtml(item.abstract || "No abstract available.")}}</p></details>
          <div class="actions">
            <label><input type="checkbox" data-field="skip" ${{state[key].skip ? "checked" : ""}}> Skip</label>
            <input type="text" data-field="notes" placeholder="Notes" value="${{escapeAttr(state[key].notes || "")}}">
          </div>
        `;
        card.querySelectorAll("input").forEach((input) => {{
          input.addEventListener("change", () => {{
            const field = input.dataset.field;
            if (input.type === "checkbox") state[key][field] = input.checked;
            if (input.type === "text") state[key][field] = input.value;
            save();
            updateExport();
          }});
        }});
        root.append(card);
      }});
      updateExport();
    }}

    function updateExport() {{
      exportBox.value = buildMarkdownExport();
    }}

    function selectedDecisionRows() {{
      const rows = [];
      for (const [index, item] of items.entries()) {{
        const key = keyFor(item, index);
        const choice = state[key] || {{}};
        if (choice.skip) continue;
        rows.push({{
          action: {{
            download_pdf: true,
            wiki_only_ingest: false,
            skip: false,
          }},
          notes: choice.notes || "",
          bucket: item.bucket,
          title: item.title,
          authors: item.authors || [],
          year: item.year || "",
          source: item.source || "",
          paper_id: item.paper_id || "",
          doi: item.doi || "",
          source_url: item.source_url || "",
          url: item.url || "",
          reason: item.reason || "",
        }});
      }}
      return rows;
    }}

    function buildDecisionJson() {{
      return JSON.stringify({{
        project: {js_json(project.name)},
        batch: {js_json(batch)},
        exported_at: new Date().toISOString(),
        mode: "download_non_skipped",
        decisions: selectedDecisionRows(),
      }}, null, 2);
    }}

    function buildMarkdownExport() {{
      const lines = [`# PDF Download Queue: {project.name} / {batch}`, ""];
      for (const item of selectedDecisionRows()) {{
        lines.push(`- [ ] download_pdf — ${{item.title}} (${{item.year || "n.d."}})`);
        lines.push(`  - bucket: ${{item.bucket}}`);
        lines.push(`  - source: ${{item.source || ""}} ${{item.doi || item.paper_id || ""}}`);
        if (item.url) lines.push(`  - url: ${{item.url}}`);
        if (item.notes) lines.push(`  - notes: ${{item.notes}}`);
      }}
      return lines.join("\\n");
    }}

    function downloadFile(filename, text, type) {{
      const blob = new Blob([text], {{ type }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.append(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}

    async function copyToClipboard(value) {{
      try {{
        await navigator.clipboard.writeText(value);
      }} catch (error) {{
        const scratch = document.createElement("textarea");
        scratch.value = value;
        scratch.setAttribute("readonly", "");
        scratch.style.position = "fixed";
        scratch.style.left = "-9999px";
        document.body.append(scratch);
        scratch.select();
        document.execCommand("copy");
        scratch.remove();
      }}
    }}

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, (char) => ({{ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\\"":"&quot;", "'":"&#39;" }}[char]));
    }}

    function escapeAttr(value) {{
      return escapeHtml(value).replace(/`/g, "&#96;");
    }}

    async function runAutoDownload() {{
      boardStatus.textContent = "Running auto-download...";
      const response = await fetch("http://127.0.0.1:8765/api/run", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          action_id: "auto-download-queue",
          params: {{
            payload: JSON.parse(buildDecisionJson()),
            report_dir: {js_json(report_dir)},
          }},
        }}),
      }});
      const result = await response.json();
      const chunks = [
        result.ok ? "Done." : "Failed.",
        result.command ? `Command: ${{result.command}}` : "",
        result.stdout ? `Output:\\n${{result.stdout}}` : "",
        result.stderr ? `Errors:\\n${{result.stderr}}` : "",
        result.log ? `Log: ${{result.log}}` : "",
      ].filter(Boolean);
      boardStatus.textContent = chunks.join("\\n\\n");
    }}

    bucketFilter.addEventListener("change", render);
    statusFilter.addEventListener("change", render);
    document.getElementById("clear-all").addEventListener("click", () => {{
      localStorage.removeItem(storageKey);
      Object.keys(state).forEach((key) => delete state[key]);
      render();
    }});
    document.getElementById("run-auto-download").addEventListener("click", async () => {{
      try {{
        await runAutoDownload();
      }} catch (error) {{
        boardStatus.textContent = "Auto-download failed. Make sure http://127.0.0.1:8765/_system/dashboard/index.html is running, or use Download queue JSON as the fallback.";
      }}
    }});
    document.getElementById("download-json").addEventListener("click", () => {{
      downloadFile("{batch}_download-queue.json", buildDecisionJson(), "application/json");
      boardStatus.textContent = "Downloaded queue JSON";
    }});
    render();
  </script>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def build(project: Path, batch: str) -> tuple[Path, Path]:
    batch_dir = project / "candidates" / batch
    if not batch_dir.exists():
        raise SystemExit(f"Candidate batch not found: {relative(batch_dir)}")
    reports_dir = project / "triage-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    items = merge_items(load_candidate_items(batch_dir), load_triage_items(project, batch))
    if not items:
        raise SystemExit(f"No candidate JSON files found in {relative(batch_dir)}")
    md_path = reports_dir / f"{batch}_approval-board.md"
    html_path = reports_dir / f"{batch}_approval-board.html"
    write_markdown(md_path, project, batch, items)
    write_html(html_path, project, batch, items)
    return md_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project directory, e.g. projects/my-project")
    parser.add_argument("--batch", help="Candidate batch name. Defaults to newest candidates/{batch}/ folder.")
    args = parser.parse_args()
    project = Path(args.project).expanduser()
    if not project.is_absolute():
        project = ROOT / project
    if not project.exists():
        raise SystemExit(f"Project directory not found: {relative(project)}")
    batch = args.batch or newest_batch(project)
    md_path, html_path = build(project, batch)
    print(f"Wrote {relative(md_path)}")
    print(f"Wrote {relative(html_path)}")
    print(f"Open in browser: file://{html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
