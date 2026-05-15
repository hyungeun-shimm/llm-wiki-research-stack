# LLM Wiki — Research Management System

A personal, paper-grounded research knowledge base for use with Claude Code, Codex CLI, and a local LLM. Implements the [Karpathy LLM Wiki pattern](https://gist.github.com/karpathy/1dd0294ef9567971c1e4348a90d69285):

```
Original PDF → sources/*.md (LLM summary) → wiki/{category}/*.md (final page)
```

The system combines three connected spaces:

| Space | Purpose | Main Folders |
|---|---|---|
| Library | Long-term memory of papers actually read and synthesized | `papers/`, `sources/`, `wiki/`, `wiki/overviews/` |
| Exploration | Open-ended brainstorming and idea incubation | `explorations/` |
| Project | Deliverable-driven work (grants, reviews, manuscripts) | `projects/` |

## Core Rules

- **No web search.** Every answer is grounded in PDFs you have ingested.
- **Library is built by cloud LLMs (Claude Code, Codex CLI).**
- **Confidential project work is local LLM only.** See `_system/docs/LOCAL_LLM.md`.

See [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md) for the full agent contracts.

## Quick Start

```bash
git clone <this-repo>
cd <repo>
pip install -r requirements.txt

# 1. Personal overrides
cp CLAUDE.local.md.example CLAUDE.local.md
# Edit CLAUDE.local.md — fill in your research categories and tool paths.

# 2. Create category folders
mkdir -p wiki/{topic-a,topic-b,methods,concepts,overviews,other}

# 3. Drop a PDF and ingest
cp /path/to/paper.pdf papers/inbox/
# In Claude Code: "ingest the PDFs in papers/inbox/"
```

## Setup

See [`SETUP.md`](SETUP.md) for prerequisites, local LLM setup, optional Mendeley integration, and dashboard configuration.

## Typical Flows

### Add Papers To The Wiki

```text
PDFs in papers/inbox/
→ Global wiki ingest (Ingester subagent)
→ papers/ + sources/ + wiki/
→ optional wiki/overviews/
```

### Develop A New Idea

```text
Discussion with Claude Code or Codex CLI
→ explorations/idea-notes/{idea}.md
→ Exploration_Brief_{idea}.md
→ Exploration Skeptic Review
→ active exploration if scout-ready
```

### Run A Confidential Project (local LLM)

```text
Project_Brief.md (in projects/{slug}/)
→ python3 scripts/local_agent.py --role drafter --project {slug}
→ Drafter / Argue / Demon / Rejection Simulator
```

## Dashboard

```bash
python3 scripts/dashboard_server.py --port 8765
# Visit http://localhost:8765/_system/dashboard/index.html
```

## Wiki Viewer (Obsidian)

Open the repo as an Obsidian Vault for graph view and wikilinks. Start at `index.md`. Details in `_system/docs/WIKI_VIEWING.md`.

## Design Credit

Pattern inspired by Andrej Karpathy's LLM Wiki gist. This implementation adds:
- Three-phase routing (Use / Build / Confidential)
- Cloud-vs-local LLM separation for unpublished content
- Subagent specialization (Scout, Triage, Ingester, Synthesizer, Drafter, Argue, Demon, Rejection Simulator)
- Exploration/Project boundary with manual promotion gates

## License

MIT (or your choice — fill in)
