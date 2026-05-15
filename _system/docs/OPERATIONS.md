# Operations Guide

This system has two explicit phases.

- `Use phase`: default mode. The Four Rules apply strictly. Answers, synthesis, drafting, and review come only from `sources/`, `wiki/`, and, when necessary, the PDFs already archived in `papers/`.
- `Build phase`: activated only when you intentionally scout, triage, or ingest. External academic APIs are allowed here, but their output goes to project staging folders until you approve the next step.

## Division of Labor

- `Claude Code`: best for Synthesizer and Drafter work. Use it when the task is writing-heavy, synthesis-heavy, or position-sensitive.
- `Codex CLI`: best for Scout invocation, Triage, and Ingester work. Use it when the task is mechanical, repetitive, or throughput-heavy.
- Both tools share the same markdown files. Do not pass context manually between them. The wiki is the shared context.
- Either tool can perform any role in a pinch if one environment is more convenient.

## Dashboard

Start the interactive dashboard server from the repository root:

```bash
python3 scripts/dashboard_server.py --port 8765
```

Then open:

```text
http://localhost:8765/_system/dashboard/index.html
```

The server exposes only allowlisted local actions, such as rebuilding the dashboard, opening project files, running scout scripts, creating approval boards, opening approval boards, and creating optional paper-in-prep files. It does not execute arbitrary shell text from the browser.

Claude Code and Codex prompts remain copy-only. Use the dashboard to copy those prompts into the appropriate tool.

## Weekly Workflow

1. On Monday, run `python3 scripts/scout_all.py --brief projects/{active}/Project_Brief.md --out projects/{active}/candidates/{YYYY-MM-DD}`.
2. Invoke Codex or Claude as the Triage agent to read `_consolidated.json` and write a dated triage report.
3. Build or open the triage approval board and mark each candidate as `Download PDF`, `Wiki-only ingest`, or `Skip`.
4. Review both In-scope and Borderline candidates. Out-of-scope papers can still be selected for wiki-only ingest if they are useful to the global corpus.
5. Download approved PDFs manually or via browser-control workflow into `papers/inbox/`.
6. Invoke Codex as the Ingester to move inbox PDFs into the permanent corpus and generate `sources/` plus `wiki/` pages.
7. Invoke Claude as the Synthesizer to update topic overviews in `wiki/overviews/`.
8. Invoke Claude as the Drafter to produce the week's project draft section in `projects/{active}/drafts/`.

## Per-Project Workflow

1. Copy [projects/_template/Project_Brief_TEMPLATE.md](projects/_template/Project_Brief_TEMPLATE.md) to `projects/{slug}/Project_Brief.md`.
2. Fill in every section. Vague briefs produce vague scouting, weak triage, and generic drafts.
3. Optionally copy `projects/_template/scout-queries_TEMPLATE.md` to `projects/{slug}/scout-queries.md`.
4. Add 5 to 10 papers you already know matter. Ingest those first so the system starts from a real core literature set.
5. Run scouting, triage, approval, ingest, synthesis, and drafting as separate steps.
6. Refresh the brief when the project claim or scope changes. The brief is the contract that keeps the roles aligned.
7. Add temporary or follow-up search campaigns to `scout-queries.md`, not `Project_Brief.md`.

## Paper-in-Prep Optional Layer

For `paper_in_prep` projects, `Project_Brief.md` remains the top-level project contract. Figure lists, experiment plans, data updates, and critique logs are optional working files that can be created later, edited often, or omitted when the project is still early.

Optional files:

- `figure-plan.md`: projected figures or panels, current evidence, status, and risks.
- `experiment-roadmap.md`: required vs optional experiments and the decision each experiment resolves.
- `data-updates/{YYYY-MM-DD}-{figure-panel}.md`: panel-level or figure-level experimental updates with a short legend.
- `critiques/critique-log.md`: anticipated reviewer concerns and mitigation status.

Create them only when useful:

```bash
cp -n projects/_template/figure-plan_TEMPLATE.md projects/{slug}/figure-plan.md
cp -n projects/_template/experiment-roadmap_TEMPLATE.md projects/{slug}/experiment-roadmap.md
mkdir -p projects/{slug}/data-updates projects/{slug}/critiques
cp -n projects/_template/critique-log_TEMPLATE.md projects/{slug}/critiques/critique-log.md
```

Add a data update when a panel or completed figure changes:

```bash
mkdir -p projects/{slug}/data-updates
cp -n projects/_template/data-updates_TEMPLATE.md projects/{slug}/data-updates/{YYYY-MM-DD}-fig1a.md
```

Then edit the copied file with the figure/panel, data path, brief legend, interpretation, concerns, and next step. The dashboard can count these files and estimate progress, but the dashboard is only a view. The brief remains the authority.

Use the Critic role when you want a reviewer-style pressure test:

```text
Read subagents/06-critic.md and act as the Critic agent for project {slug}. Use Project_Brief.md, optional figure/data/critique files if present, and only sources/wiki evidence. Write a dated critique report to projects/{slug}/critiques/.
```

## Direct Wiki Ingest

Sometimes you may want to add a paper to the LLM-Wiki for memory only, without scouting, triage, or a project. That is valid. Put the PDF in `papers/inbox/`, then invoke the Ingester directly:

```text
Read subagents/03-ingester.md and ingest the PDFs in papers/inbox/ directly into the LLM-Wiki. This is a direct wiki ingest: skip Scout and Triage, use no web search, and create papers/, sources/, wiki/, and index.md entries only from the provided PDFs and existing wiki context.
```

This is the clean path for papers you already have and already know you want in the curated corpus.

## Triage Approval Board

After Triage, build the human decision board:

```bash
python3 scripts/build_triage_approval_board.py --project projects/{slug}
```

The script writes:

- `projects/{slug}/triage-reports/{batch}_approval-board.md`
- `projects/{slug}/triage-reports/{batch}_approval-board.html`

Open the HTML file in a browser. It shows all buckets, including `Borderline` and `Out-of-scope`, with three human decisions:

- `Download PDF`: use for papers to download into `papers/inbox/` and ingest for the active project.
- `Wiki-only ingest`: use for papers that are not project-relevant but are worth adding to the global LLM-Wiki.
- `Skip`: no action.

The HTML stores checkbox state in browser localStorage and can export a markdown decision list. It does not download PDFs, call APIs, or modify the wiki.

The board also includes direct action buttons:

- `Open next selected link`: opens one selected DOI/PubMed link at a time. This is the safest mode for institution login and PDF download.
- `Open all selected links`: opens all selected links at once. Browsers may block some tabs as popups.
- `Copy Codex download prompt`: copies a prompt that can be pasted into Codex when browser/computer control is available.
- `Download JSON` and `Download Markdown`: saves the decision queue for later.

For a browser-assisted download queue, click `Download JSON` in the approval board, then run:

```bash
python3 scripts/open_pdf_decision_urls.py /path/to/{batch}_download-decisions.json --action both --open
```

This opens the selected DOI/PubMed links in the default browser and writes a queue markdown file next to the JSON. Save downloaded PDFs into `papers/inbox/`, then run Ingester.

## Search Campaigns

`Project_Brief.md` and `scout-queries.md` have different jobs.

- `Project_Brief.md`: stable project identity, triage criteria, output mode, and position statement.
- `scout-queries.md`: flexible search campaigns such as computational models, molecular mechanisms, or clinical translation.

You can add a new campaign to `scout-queries.md` at any time, even after previous scouting or triage has started. New scout runs will read both the brief's must-include keywords and the extra bullet queries from `scout-queries.md`.

Example:

```markdown
## 2026-05-10 — computational models

Purpose:
Find theory papers on timing rules and eligibility traces.

Queries:

- [ ] "cerebellum" AND "temporal credit assignment"
- [ ] "cerebellar learning" AND "eligibility trace"
- [ ] "vestibulo-ocular reflex" AND "learning model"
```

Then run:

```bash
python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)
```

If a triage run is already using today's candidate folder, do not write new candidates into the same folder. Use a campaign suffix instead:

```bash
python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)-computational
```

This keeps the current triage batch stable while letting you launch a new search campaign.

When `scout_all.py` finishes and at least one non-alert source succeeds, pending query lines are marked as done:

```markdown
- [x] "cerebellum" AND "temporal credit assignment"
```

Checked query lines are skipped by default in future scout runs. To rerun them intentionally, either change `[x]` back to `[ ]` or pass:

```bash
python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)-rerun --include-done-queries
```

To run only the search-campaign queries and not the stable brief keywords, pass:

```bash
python3 scripts/scout_all.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/$(date +%F)-campaign --queries-only
```

## API Keys

Store external credentials in `~/.research-system.env`, then load them before running scouts:

```bash
source ~/.research-system.env
```

Required or recommended variables:

- `NCBI_API_KEY`: optional but recommended for PubMed via NCBI E-utilities. Create an NCBI account, generate an API key in account settings, and place it in the env file.
- `S2_API_KEY`: required by this v1 bootstrap for Semantic Scholar scouting. Request a free key from the Semantic Scholar developer portal and place it in the env file.

Rules:

- Never commit `~/.research-system.env`.
- Never hard-code keys in scripts.
- If a script needs a key and it is missing, the script should fail immediately with the env var name.

## Gmail Forwarding for Google Scholar Alerts

`parse_gscholar_alert.py` is intentionally a local, on-demand parser.

Suggested setup:

1. In Gmail, create a filter for `from:scholaralerts-noreply@google.com`.
2. Route those messages to a dedicated label or mailbox used only for alerts.
3. Export or sync those messages as `.eml` files into a local folder such as `~/gscholar-alerts/`.
4. Run `python3 scripts/parse_gscholar_alert.py --brief projects/{slug}/Project_Brief.md --out projects/{slug}/candidates/{YYYY-MM-DD} --alerts-dir ~/gscholar-alerts`.
5. Treat the parsed alerts like any other Build-phase candidates. They still require triage and human approval.

## Mendeley Integration

Mendeley remains the reference manager for Word citations. The LLM-Wiki remains the curated memory of papers actually read and synthesized.

Use this division of labor:

- Mendeley stores broad reference metadata and supports MS Word citation insertion.
- LLM-Wiki stores a smaller, curated set of papers with source summaries, wiki pages, and overview synthesis.
- `_system/mendeley/watch/` is the safe bridge from LLM-Wiki back into Mendeley.

Do not rename, move, or manually clean files inside Mendeley's internal storage:

```text
$HOME/Library/Application Support/Mendeley Reference Manager/userfiles
```

That directory uses opaque Mendeley-managed filenames. Treat it as read-only.

Recommended watched folder:

```text
_system/mendeley/watch
```

In Mendeley Reference Manager, set this folder as the watched folder for future imports. When a paper is already curated in the wiki and should also appear in Mendeley, copy it there:

```bash
python3 scripts/sync_to_mendeley_watch.py --paper papers/{stem}.pdf
```

To review and reorganize the existing Mendeley library:

1. Export the Mendeley library as BibTeX to `_system/mendeley/export/library.bib`.
2. Run the audit:

```bash
python3 scripts/audit_mendeley_export.py --bib _system/mendeley/export/library.bib --pdf-root "$HOME/Library/Application Support/Mendeley Reference Manager/userfiles" --out _system/mendeley/review
```

3. Open `_system/mendeley/review/library_audit_summary.md` and `_system/mendeley/review/proposed_categories.csv`.
4. Use the proposed categories as a guide for Mendeley folders or tags.
5. Use `_system/mendeley/review/wiki_ingest_candidates.md` to choose a small initial batch for LLM-Wiki ingestion.

Avoid bulk-ingesting the entire Mendeley library into the wiki. Start with 5 to 15 central papers per project, then let scouting and triage expand the corpus deliberately.

To apply proposed broad collections directly to Mendeley, use the official API only. Do not edit Mendeley's local database or `userfiles`.

Requirements:

- Register a Mendeley API application in the developer portal.
- Obtain a user OAuth access token with library write access.
- Export the token in the current shell as `MENDELEY_ACCESS_TOKEN`.

Then run:

```bash
python3 scripts/mendeley_apply_collections.py --apply
```

This script is intentionally non-destructive: it can create missing broad folders and add matched documents to folders, but it does not delete documents, remove old folders, or move local PDFs.

## Notion Sync

Out of scope for v1. The wiki is local markdown. If and when you want a team-visible mirror, add a future `scripts/sync_to_notion.py` that publishes selected overview pages. The wiki remains the source of truth.

## Future

These are intentionally not built in v1:

- Notion sync
- Background scout daemon, cron, or GitHub Action
- QMD or vector search before the wiki actually needs it
- A web UI
- Auto-PDF download
- Auto-relevance scoring beyond the structured triage report
- Multi-user or shared-filesystem support

Until the wiki passes roughly 500 pages, plain `grep`, `index.md`, and the agent's built-in search are enough.
