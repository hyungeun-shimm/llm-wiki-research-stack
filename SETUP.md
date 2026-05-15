# Setup Guide

## Prerequisites

- **Python 3.10+**
- **Claude Code** or **Codex CLI** (cloud agent for Library work)
- **LM Studio** + a local model (for Confidential phase) — optional but required for confidential drafting
- **Obsidian** — optional, for graph view of the wiki
- **Mendeley Reference Manager** — optional, for citation insertion in Word

## First-Time Setup

### 1. Clone and install dependencies

```bash
git clone <this-repo>
cd <repo>
pip install -r requirements.txt
```

### 2. Personal configuration

```bash
cp CLAUDE.local.md.example CLAUDE.local.md
```

Edit `CLAUDE.local.md` and fill in:
- Your research domain (one sentence)
- Your category list (replaces placeholder `topic-a`, `topic-b`, etc.)
- Your Mendeley path (if using Mendeley)
- Your local LLM endpoint (if using LM Studio)

`CLAUDE.local.md` is gitignored and overrides defaults in `CLAUDE.md`.

### 3. Create category folders

For each category you defined in `CLAUDE.local.md`:

```bash
mkdir -p wiki/{your-topic-1,your-topic-2,methods,concepts,overviews,other}
```

### 4. (Optional) Set up local LLM for Confidential phase

See `_system/docs/LOCAL_LLM.md`. Summary:

1. Install [LM Studio](https://lmstudio.ai/)
2. Download a capable local model (e.g., Qwen 2.5 32B, Llama 3.3 70B, or similar)
3. Start the Local Server in LM Studio (default `http://localhost:1234`)
4. Test with:
   ```bash
   python3 scripts/local_agent.py --role drafter --project example
   ```

### 5. (Optional) Mendeley integration

Set `mendeley_userfiles_path` in `CLAUDE.local.md` to your Mendeley `userfiles` directory. On macOS this is typically:

```
~/Library/Application Support/Mendeley Reference Manager/userfiles
```

The integration:
- Exports BibTeX from Mendeley to `_system/mendeley/export/library.bib` (manual)
- Syncs ingested wiki PDFs to `_system/mendeley/watch/` so Mendeley auto-imports them
- Never modifies Mendeley's internal storage

## Add Your First Paper

```bash
cp /path/to/some-paper.pdf papers/inbox/
```

Then in Claude Code:

> "Ingest the PDFs in papers/inbox/"

The Ingester subagent will:
1. Rename the PDF to `{author}-{year}-{first-5-title-words}.pdf` and move it to `papers/`
2. Extract text with `scripts/extract_pdf.py`
3. Create `sources/{stem}.md` (structured summary)
4. Create `wiki/{category}/{stem}.md` (final wiki page)
5. Update `index.md`
6. (Optional) Sync to Mendeley watch folder

## Add Many Papers

For a batch ingest campaign (e.g., "add all papers from Author X's lab"), create a library-ingest project:

```bash
mkdir -p projects/{your-slug}
cp projects/_template/Library_Ingest_Brief_TEMPLATE.md projects/{your-slug}/Project_Brief.md
```

Edit the brief with keywords, year range, and preferred sources. Then in Claude Code:

> "Scout for the {your-slug} project"

This runs Build phase (Scout → Triage → user approval → Ingest).

## Dashboard

```bash
python3 scripts/dashboard_server.py --port 8765
```

Visit `http://localhost:8765/_system/dashboard/index.html` for an interactive overview of the wiki, pending ingests, active explorations, and project status.

## Verify Setup

```bash
ls papers/ sources/ wiki/      # should show your ingested paper in all three
python3 scripts/verify_citations.py   # checks frontmatter consistency
```

## Common Issues

- **Claude Code refuses to read a project folder**: That folder is confidential. Use the local agent.
- **Ingester can't extract text from a scanned PDF**: Run OCR first (e.g., `ocrmypdf input.pdf output.pdf`).
- **Mendeley sync isn't running**: Check `mendeley_userfiles_path` in `CLAUDE.local.md`; the integration is silent if the path is unset.
