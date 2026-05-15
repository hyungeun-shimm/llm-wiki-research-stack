# Viewing The LLM-Wiki In Obsidian

Obsidian is the recommended reader for this repository because it understands plain Markdown, `[[wikilinks]]`, backlinks, search, and graph view without changing the wiki format.

## First-Time Setup

Open this repository as one Obsidian vault:

```bash
open -a Obsidian "."
```

If Obsidian asks what to open, choose **Open folder as vault** and select:

```text
.
```

After the first setup, the dashboard's **Open Obsidian Vault** button should open the vault directly.

## What To Read First

Start with:

- `index.md` for the human-curated wiki index.
- `wiki/overviews/` for synthesis pages across multiple papers.
- `wiki/{category}/` for final wiki pages about individual papers or concepts.
- `sources/` only when you need the longer paper-level extraction and citation-truth frontmatter.

## Graph View

Use Obsidian's graph tools to see connections created by `[[wikilinks]]`.

Recommended filters:

```text
path:wiki
```

```text
path:wiki/overviews
```

```text
path:sources OR path:wiki
```

Use **Local Graph** from an overview page when you want to see the papers and concepts around one topic.

## How To Make The Graph Useful

The graph only becomes meaningful when wiki pages link to each other. The most valuable links are:

- Paper page to related paper page.
- Paper page to concept page.
- Overview page to every paper it synthesizes.
- Project note to relevant overview pages.

When asking Claude Code or Codex to synthesize, explicitly ask for `[[wikilinks]]` to existing wiki pages.

## Safety Notes

- Do not drag PDFs around inside Obsidian. The canonical PDF locations are managed by the ingest workflow.
- `sources/*.md` frontmatter is citation truth. Edit carefully.
- `projects/` and `explorations/` are working areas. Durable knowledge should be promoted into `wiki/` explicitly.
