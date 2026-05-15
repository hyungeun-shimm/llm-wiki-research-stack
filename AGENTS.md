# AGENTS — Research Knowledge Stack

A personal knowledge base for research papers, following [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/1dd0294ef9567971c1e4348a90d69285). Set your domain (neuroscience, ML, materials, etc.) in `CLAUDE.local.md` if you want:

```
Original PDF → sources/*.md (LLM summary) → wiki/{category}/*.md (final page)
```

**Language policy**: All wiki content is in English. Conversation can be in any language.

---
## THE FOUR RULES (do not violate)

These rules are the core of the system. They prevent hallucination and keep every claim traceable.
1. **No web search.** Never use `WebSearch` or `WebFetch` to fill gaps. The point of this wiki is that every answer is grounded in papers we actually have.
2. **Answer from the wiki first.** Use `sources/` and `wiki/` as the only sources of truth.
3. **If the wiki is insufficient, re-read the PDF.** Go to `papers/{author}-{year}-{words}.pdf` and extract more detail with `pypdf`. Then update the wiki.
4. **If the wiki has no paper on the topic, say so.** Tell the user *"I don't have a paper on this — please give me the PDF."* Do not improvise.
These rules apply to **every** response, including overview pages: cite only papers that exist in the wiki.

---
## Phase Rules

There are three explicit operating phases. The first two run on cloud-hosted LLMs (Claude Code, Codex CLI). The third runs on a local LLM only.

- `Use phase` is the default for cloud agents. The Four Rules apply strictly. Q&A, synthesis, and overview writing must rely only on `sources/`, `wiki/`, and, when needed, PDFs already stored in `papers/`.
- `Build phase` is for scouting, triage, and ingest. It activates only when the user explicitly runs a scout script, asks to scout an exploration or library-ingest project, asks for triage, or asks to ingest a paper.
  - External academic APIs are allowed only in Build phase, and only for acquiring candidate metadata before human approval.
  - Build-phase outputs go to staging locations such as `explorations/active/{slug}/candidates/` or `projects/{slug}/candidates/` (library_ingest projects only). They do not become part of the permanent wiki until ingestion is completed.
  - Once a PDF is approved and placed into `papers/`, ingest follows the standard source-summary-to-wiki flow.
- `Confidential phase` covers all work on unpublished content: grant proposals, paper_in_prep manuscripts, review articles in preparation, under-review revisions, preliminary data summaries, internal critiques, and any project notes containing unpublished hypotheses. Confidential phase runs on a local LLM only (see "Tool Routing" below). Cloud agents must refuse to read paths covered by this phase.

## Library, Exploration, and Project Boundaries

This system has three connected but distinct spaces. They differ in which LLM is allowed to read them.

- `Library` is the long-term memory: `papers/` (except `papers/under-review/`), `sources/`, `wiki/`, `wiki/overviews/`, and `index.md`. Cloud LLMs read and write this layer.
- `Exploration` is the public-facing incubator: `explorations/idea-notes/`, `explorations/ideas/`, `explorations/active/{slug}/` (except `_pdfs/` and any file marked `confidential_tier: local-only`). Cloud LLMs read and write this layer. Explorations are scientific topics, literature mapping, and pre-project ideation — never grant aims or unpublished data.
- `Scout` is an ad-hoc paper-search staging area: `scouts/{slug}/Scout_Brief.md`, `candidates/`, and `triage-reports/`. Use it for ordinary paper scout requests that are not idea notes and not projects.
- `Project` is the confidential deliverable workspace: `projects/{slug}/` for grants, paper_in_prep manuscripts, and review articles. **Local LLM only.** The single exception is `library_ingest` projects (see Project Rules), which contain only public scouting metadata and are readable by cloud LLMs.

Core rules:

```text
Library, public Exploration content, and ad-hoc Scout content → cloud LLMs may read.
Confidential Project content → local LLM only.
Library is built by cloud agents. Projects consume the Library and are written by the local agent.
```

Promotion gates (manual, never automatic):

- PDF promotion: selected PDF → `papers/inbox/` → Ingester → `papers/`, `sources/`, `wiki/`
- Insight promotion: durable, project-independent synthesis → `wiki/overviews/`
- Exploration → Project promotion: an exploration with a confidential deliverable seeds a new project folder, but the project itself never feeds back into the wiki without manual redaction.

Do not put brainstorming notes, project strategy, triage opinions, or draft-specific arguments directly into `wiki/`. Keep the wiki clean and durable.

## Active Project

If the user references a project by name:

- For `library_ingest` projects: locate `projects/{slug}/Project_Brief.md` and treat it as the operating context.
- For all other project types (`grant`, `paper_in_prep`, `review_article`): **do not read `projects/{slug}/` from cloud agents.** Reply that confidential project work must run through the local agent (`python3 scripts/local_agent.py --role {drafter|argue|demon|rejection-sim} --project {slug}`). Continue to help with public-facing work in `wiki/`, `sources/`, or `explorations/`.

## Active Exploration

If the user references an exploration by name, first look for:

- `explorations/idea-notes/{slug}.md`
- `explorations/ideas/Exploration_Brief_{slug}.md`
- `explorations/active/{slug}/Exploration_Brief.md`

Treat exploration work as open-ended unless it has been explicitly promoted to a project. Exploration notes may cite or summarize wiki material, but they are not authoritative library pages.

Within `explorations/active/{slug}/`, use `paper-briefs/` for provisional candidate-paper notes and `synthesis.md` for exploration-local synthesis. These files are working memory only. They are not `sources/`, not `wiki/overviews/`, and not citation-truth.

## Subagent Loading

When the user invokes a role, load the corresponding `subagents/0X-{role}.md` file. Roles split by execution environment:

| Role | File | Runs on | Reads |
|---|---|---|---|
| Scout | `subagents/01-scout.md` | Cloud | `explorations/idea-notes/`, library_ingest briefs |
| Triage | `subagents/02-triage.md` | Cloud | candidates JSON + abstracts |
| Ingester | `subagents/03-ingester.md` | Cloud | `papers/inbox/`, writes `papers/`, `sources/`, `wiki/` |
| Synthesizer | `subagents/04-synthesizer.md` | Cloud | `sources/`, `wiki/`, public explorations → writes `wiki/overviews/` |
| Exploration Skeptic | `subagents/07-exploration-skeptic.md` | Cloud | public explorations |
| Drafter | `subagents/05-drafter.md` | **Local** | confidential `projects/{slug}/`, reads `sources/` and `wiki/` for citation |
| Argue (reviewer #2) | `subagents/06-argue.md` | **Local** | confidential project drafts |
| Demon (devil's advocate) | `subagents/08-demon.md` | **Local** | confidential project drafts |
| Rejection Simulator | `subagents/09-rejection-sim.md` | **Local** | confidential project drafts + funder/journal context |

Cloud agents that encounter a confidential path (see Confidential Material) halt and redirect to the local agent.

## Tool Usage

- `scripts/scout_arxiv.py`, `scripts/scout_biorxiv.py`, `scripts/scout_pubmed.py`, `scripts/scout_semantic_scholar.py`, `scripts/parse_gscholar_alert.py`, and `scripts/scout_all.py` are Build-phase tools only. They accept `--exploration {slug}` (reads `explorations/idea-notes/{slug}.md`) or `--project {slug}` (only for `library_ingest` projects). They refuse to read confidential project briefs.
- `scripts/extract_pdf.py` is for ingest only.
- `scripts/cleanup_ingested_inbox_pdfs.py` is a post-ingest cleanup helper. It compares `papers/inbox/*.pdf` against canonical `papers/*.pdf` by file hash and deletes exact inbox duplicates after successful ingest, leaving `papers/{stem}.pdf` as the only canonical copy. Use `--match-title` only for manually reviewed same-paper copies whose hash differs.
- `scripts/audit_mendeley_export.py` is a local metadata audit tool. It may read a Mendeley BibTeX export and PDF inventory but must not modify Mendeley.
- `scripts/sync_to_mendeley_watch.py` is a local bridge that copies selected canonical PDFs from `papers/` into `_system/mendeley/watch/`.
- `scripts/dashboard_server.py` serves the local dashboard and exposes only allowlisted local actions. It must not be expanded into arbitrary shell execution.
- Everything else in the repository belongs to Use-phase work unless the user explicitly initiates Build-phase operations.

## Tool Routing

This system runs across three execution environments. The first two are cloud LLMs (Claude Code, Codex CLI); the third is a local LLM (LM Studio + Qwen3.5 27B or equivalent, see `_system/docs/LOCAL_LLM.md`).

### Claude Code's Profile (Cloud — Writing + Reasoning)

Run these tasks in Claude Code:

- Synthesizer work: cross-paper synthesis on the public corpus → `wiki/overviews/`
- Public-facing brainstorming in `explorations/`
- Strategic conversations about wiki structure, ingest priorities, library scope
- Debugging confusing or low-quality agent outputs
- Careful editorial revision of already-published or public-facing prose

### Codex CLI's Profile (Cloud — Mechanical + Throughput)

Run these tasks in Codex CLI:

- Scout invocations and batching API-query scripts
- Triage of candidate JSON files against scout queries
- Ingester work: PDF processing, file moves, frontmatter generation, and index updates
- File-system maintenance, bulk renaming, and frontmatter cleanup
- Running verification scripts such as `scripts/verify_citations.py`
- Anything involving more than 3 sequential file reads or shell commands

### Local LLM Profile (Confidential phase only)

Run these tasks on the local LLM (see `_system/docs/LOCAL_LLM.md`):

- Drafter work on grants, proposals, paper_in_prep manuscripts, review articles, and under-review revisions
- Argue (reviewer-#2 critique) on confidential drafts
- Demon (devil's-advocate / desk-reject critique) on confidential drafts
- Rejection Simulator (pre-mortem on funder/journal rejection scenarios)
- Any conversation whose context contains text from `confidential_tier: local-only` files

Entry point:

    python3 scripts/local_agent.py --role {drafter|argue|demon|rejection-sim} --project {slug}

### Switching Between Cloud Tools (Soft Default)

If a cloud task fits the other cloud tool's profile better, reply:

> "This task fits the other tool's profile better. Switch to {Codex CLI | Claude Code} and run: {exact command or prompt}. The shared state is in this folder, so no context transfer is needed."

This is a default routing rule. If the user explicitly says "do it here anyway," proceed in the current tool.

### Hard Refusal for Confidential Paths

The soft rule above does not apply to confidential paths. When a cloud agent (Claude Code or Codex CLI) is asked to read, summarize, edit, or echo content from a `confidential_tier: local-only` path, it must refuse with:

> "This path is `confidential_tier: local-only` (see Confidential Material in AGENTS.md). I cannot process it from a cloud-hosted LLM. Run `python3 scripts/local_agent.py --role {role} --project {slug}` to handle it locally. I can help with related public-facing work in `wiki/`, `sources/`, or `explorations/`."

The refusal stands even if the user says "do it here anyway." This is the only hard refusal in the routing system.

## Repository Structure

```
your-llm-wiki/
├── CLAUDE.md
├── AGENTS.md
├── _system/
│   ├── dashboard/
│   ├── docs/
│   │   └── LOCAL_LLM.md            # local-LLM setup (Confidential phase)
│   ├── mendeley/
│   └── reference-examples/         # design-reference only; never re-ingested
├── index.md
├── papers/
│   ├── inbox/
│   ├── under-review/                # confidential_tier: local-only
│   └── {author}-{year}-{title-5-words}.pdf
├── sources/
│   └── {author}-{year}-{title-5-words}.md
├── wiki/
│   ├── overviews/
│   └── {category}/
├── explorations/
│   ├── index.md
│   ├── _template/
│   ├── idea-notes/
│   ├── ideas/
│   │   └── Exploration_Brief_{idea}.md
│   ├── active/
│   │   └── {exploration-slug}/
│   │       ├── Exploration_Brief.md
│   │       ├── scout-queries.md
│   │       ├── candidates/
│   │       ├── paper-briefs/
│   │       ├── _pdfs/              # confidential_tier: local-only
│   │       ├── notes.md
│   │       ├── questions.md
│   │       ├── promote-to-wiki.md
│   │       └── promote-to-project.md
│   └── archive/
├── projects/
│   ├── _active.md
│   ├── _template/                  # confidential project layout
│   └── {project-slug}/             # confidential_tier: local-only (unless library_ingest)
│       ├── Project_Brief.md
│       ├── Roadmap.md
│       ├── Decision_Log.md
│       ├── Evidence_Map.md
│       ├── Drafts/
│       ├── critiques/
│       │   ├── argue/
│       │   └── demon/
│       ├── rejection-sims/
│       └── notes/
├── subagents/
└── scripts/
```

## Confidential Material

Confidential material is any text that has not yet been published, not yet released as a preprint, or is under peer review. The policy below controls **which LLM may read it**, not just where it may be written.

### Confidential paths (default `confidential_tier: local-only`)

- `papers/under-review/**`
- `projects/**` *except* projects with `project_type: library_ingest` in their `Project_Brief.md` frontmatter
- `explorations/active/*/_pdfs/**`
- Any file whose own frontmatter declares `confidential_tier: local-only`

### Public paths (default `confidential_tier: external-ok`)

- `papers/` (except `under-review/`)
- `sources/`, `wiki/`, `wiki/overviews/`, `index.md`
- `explorations/idea-notes/`, `explorations/ideas/`, `explorations/active/{slug}/Exploration_Brief.md`, `scout-queries.md`, `synthesis.md`, `promote-to-*.md`
- `projects/{slug}/` when `project_type: library_ingest`
- `_system/reference-examples/` (reserved as design reference; never re-ingested into the wiki)

### Rules

- Cloud-hosted agents must not read, summarize, quote, embed, or echo the contents of confidential paths. On encountering one, the agent halts and follows the Hard Refusal text in Tool Routing.
- `source_collection` describes a paper's origin. `confidential_tier` describes who can process it. The two fields are independent.
- `papers/under-review/` never produces a `sources/` or `wiki/` page. No cross-links.
- The default tier of a path is determined by the lists above. A frontmatter field overrides the default for that one file.
- Promotion from a confidential path into the public layer requires a manual, user-edited redaction step. Automatic promotion is forbidden.

## File Naming Convention

All three tiers (PDF, source, wiki) share the same stem:

```
{first-author-lastname}-{year}-{first-5-title-words}.{ext}
```

- Lowercase, special chars stripped, spaces → `-`
- Year is 4 digits
- Consortium papers: use consortium name (e.g. `1000-genomes-project-2015-...`)

Example: `smith-2024-attention-is-all-you-need.pdf`

## Categories

Start broad. Split only when a category becomes crowded or mixes incompatible paper types. Define your own — these are suggestions:

| Category | Includes |
|---|---|
| `core-topic-a` | Papers central to your first major research question |
| `core-topic-b` | Papers central to your second major research question |
| `methods` | Techniques and tools you use, explained generically |
| `concepts` | Theory and methodology papers, generalizable |
| `overviews` | Synthesis pages spanning multiple papers |
| `other` | Cross-cutting / parking lot |

Tip: classify by method or mechanism, not by the paper's disease/application label alone. Customize the table in `CLAUDE.local.md` for your domain.

---
## Adding a New Paper

### Step 1 — Copy PDF to `papers/` and extract text

Use `scripts/extract_pdf.py`:

```bash
python3 scripts/extract_pdf.py /path/to/paper.pdf
```

### Step 2 — Write `sources/{stem}.md`

```yaml
---
title: "Paper Title"
authors: Author List
year: YYYY
doi: DOI
category: [your-category]
pdf_path: /full/path/to/papers/{stem}.pdf
pdf_filename: {stem}.pdf
source_collection: external
---

## One-line Summary
## 1. Document Information
## 2. Key Contributions
## 3. Methodology and Architecture
## 4. Key Results and Benchmarks
## 5. Limitations and Future Work
## 6. Related Work
## 7. Glossary
```

### Step 3 — Write `wiki/{category}/{stem}.md`

```yaml
---
title: "Paper Title"
authors: Author list
year: YYYY
doi: DOI
source: {stem}.md
category: [your-category]
pdf_path: /full/path/to/papers/{stem}.pdf
pdf_filename: {stem}.pdf
source_collection: external
tags: []
---

## Summary
## Key Contributions
## Methodology and Architecture
## Results
## Related Papers
- [[category/page]] — relationship
```

### Step 4 — Update `index.md`

Add a one-line entry under the right category.

---

## PDF Management Rules

- **Always copy, never symlink.** `cp` from external locations into `papers/`.
- `pdf_path` always points inside `papers/`. Never use `~/Downloads/` or other external paths.
- `pdf_filename` must match `basename(pdf_path)`.
- `papers/inbox/` is a temporary intake area.
- After successful ingest, exact duplicate inbox copies should be deleted with `python3 scripts/cleanup_ingested_inbox_pdfs.py` so the dashboard no longer reports them as waiting and duplicate ingest is avoided.
- `papers/under-review/` stays segregated from the corpus.

## Mendeley Rules

- Mendeley is the reference manager for Word citation insertion.
- The LLM-Wiki is the curated memory for papers actually read and synthesized.
- Treat `~/Library/Application Support/Mendeley Reference Manager/userfiles` as read-only Mendeley internal storage.
- Never rename, move, or clean PDFs inside Mendeley's internal `userfiles` directory.
- Use `_system/mendeley/export/library.bib` as a private metadata export for audits.
- Use `_system/mendeley/review/` for generated reclassification reports.
- Use `_system/mendeley/watch/` as the future watched folder for importing selected wiki PDFs into Mendeley.
- After ingesting a paper into `papers/{stem}.pdf`, copy it to Mendeley only by running `python3 scripts/sync_to_mendeley_watch.py --paper papers/{stem}.pdf`.
- Do not bulk-ingest the whole Mendeley library into the wiki. Select high-value papers deliberately.

## Project Rules

Every project is one of two kinds, declared by `project_type` in `Project_Brief.md` frontmatter.

### Confidential projects (`project_type: grant`, `paper_in_prep`, or `review_article`)

- Folder is `confidential_tier: local-only` by default. Only the local agent reads it.
- Standard layout (provided by `projects/_template/`):
  - `Project_Brief.md` — the project contract (hypotheses, aims, scope)
  - `Roadmap.md` — high-level timeline and milestones
  - `Decision_Log.md` — why decisions were made and what was rejected
  - `Evidence_Map.md` — which claims in the draft are supported by which wiki sources
  - `Drafts/` — manuscript or proposal drafts (local agent writes here)
  - `critiques/argue/` — reviewer-#2-style critiques
  - `critiques/demon/` — devil's-advocate critiques
  - `rejection-sims/` — pre-mortem rejection simulations
  - `notes/` — confidential brainstorming, unresolved questions
- `Project_Brief.md` is the project contract. If it is vague, drafting quality will collapse.
- Scouts do **not** run from a confidential project. Ordinary paper scout requests use `scouts/{slug}/Scout_Brief.md`. Use `explorations/idea-notes/{slug}.md` only when the user is intentionally developing an idea or exploration. The translation from project need to public topic is performed by the user, not by any LLM.
- Drafts are private working outputs and do not propagate to `wiki/` without a manual redaction step.

### Library Ingest Projects (`project_type: library_ingest`)

Use this type when the goal is solely to add a batch of papers to the permanent wiki — no manuscript, no grant, no deliverable.

- Folder is `confidential_tier: external-ok`. Cloud agents read it.
- The brief needs only: a goal, must-include/must-exclude keywords, year range, and preferred sources.
- No `Drafts/`, `critiques/`, `Decision_Log.md`, or `Evidence_Map.md`.
- Scouts run in Build phase as normal; approved PDFs move through `papers/inbox/` → Ingester → `papers/` + `sources/` + `wiki/`.
- Once all target PDFs are ingested, set `status: closed` in the frontmatter. The folder can be kept for provenance but is otherwise inert.
- A closed `library_ingest` project is not an active workspace. Do not treat it as a project context for Q&A or drafting.
- If the user says "add papers from [author/lab/topic] to the wiki," create a `library_ingest` project under `projects/{slug}/` rather than a full project brief.

## Exploration Rules

Explorations are public-facing by default (`confidential_tier: external-ok`). They map literature, incubate ideas, and feed scout campaigns. They do not hold unpublished hypotheses — those belong in confidential projects.

- Use `explorations/idea-notes/` for lightweight discussion summaries.
- Do not store full conversation transcripts. Add only evolving summaries and dated updates.
- Promote an idea note to `explorations/ideas/Exploration_Brief_{idea}.md` only when the idea has a focused question, searchable terms, and possible wiki or project value.
- Run Exploration Skeptic Review before making an active exploration folder or running scouts.
- `explorations/active/{slug}/_pdfs/` holds temporary PDFs that have not yet been ingested. This subfolder is `confidential_tier: local-only` by default — until a preprint has been read and judged safe to discuss with cloud LLMs, treat it as confidential.
- Use `explorations/active/{slug}/paper-briefs/` for temporary notes about candidate papers. A paper brief may summarize abstract metadata or temporary PDF notes, but it must clearly label the available evidence and must not be treated as an ingested source.
- Use `explorations/active/{slug}/synthesis.md` for provisional exploration-local synthesis. It can help decide what to promote, but durable synthesis belongs in `wiki/overviews/`.
- To preserve an exploration PDF, copy the selected PDF into `papers/inbox/` and run global wiki ingest.
- To preserve exploration insight, record it in `promote-to-wiki.md`, then create or update the appropriate `wiki/overviews/` page only after the supporting papers are ingested.
- To turn an exploration into a deliverable, create a project folder and copy the useful exploration summaries into `projects/{slug}/notes/`. Once they enter a confidential project, those summaries become local-only.

## Knowledge Compounding

The most valuable pages are not individual paper summaries. They are `wiki/overviews/` pages that synthesize across papers. When a question is answered well, save the answer:

> "Save this as an overview page in `wiki/overviews/`"

Each conversation should produce new or improved wiki pages. Over time the wiki becomes a searchable, cross-referenced knowledge graph that future conversations draw from.

## Browsing with Obsidian

For visual navigation, the user can install [Obsidian](https://obsidian.md/) and open the wiki folder as a Vault. Native support for `[[wikilinks]]`, graph view, and full-text search. Recommend this whenever the user asks how to browse the wiki.

Use `_system/docs/WIKI_VIEWING.md` for the local setup guide. The dashboard has a Wiki Viewer section with an Obsidian open button, graph filters, and first-time setup command.

---
## Design Principles

- **3-tier**: Raw PDF (immutable) → sources/*.md → wiki/**/*.md
- **Library-as-evidence-layer**: the wiki is not the deliverable; it is the evidence substrate that confidential projects consume
- **Confidentiality is a routing constraint**: unpublished content is processed by a local LLM only, regardless of which tool the user happens to be sitting in
- **The user is the only translator**: confidential project needs become public scout queries only by manual user rewriting, never by LLM extraction
- **English only** in wiki content
- **Obsidian compatible**: `[[wikilinks]]`, plain markdown
- **Consistent YAML** in every file
- **Human approval before PDF download** in Build phase
- **No web search in Use phase**: rule #1 above

When in doubt, follow rule #1 and the active project's brief (if local) or the relevant exploration (if cloud).
