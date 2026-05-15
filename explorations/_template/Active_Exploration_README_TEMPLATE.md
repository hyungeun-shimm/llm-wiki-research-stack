# Active Exploration: {title}

This folder is for a scout-worthy but non-project exploration. It may contain temporary candidate metadata, paper briefs, and PDFs, but none of these are part of the permanent LLM-Wiki until explicitly promoted.

## Folder Contract

```text
Exploration_Brief.md
scout-queries.md
candidates/{YYYY-MM-DD}/
paper-briefs/
_pdfs/
notes.md
questions.md
synthesis.md
promote-to-wiki.md
promote-to-project.md
```

## What Each Working File Means

- `candidates/`: raw scout output. Metadata only. Do not store PDFs here.
- `paper-briefs/`: short provisional memos about candidate papers. These are not `sources/` files and are not citation-truth.
- `_pdfs/`: temporary PDFs for exploration only. These are not the permanent corpus.
- `notes.md`: running exploration notes and decisions.
- `questions.md`: open questions and uncertainty log.
- `synthesis.md`: exploration-local synthesis. Useful for thinking, but not a durable `wiki/overviews/` page.
- `promote-to-wiki.md`: list of selected PDFs or durable insights that should enter the Library.
- `promote-to-project.md`: notes for turning this exploration into a formal `projects/{slug}/` workspace.

## Promotion Rule

Do not move material into `papers/`, `sources/`, `wiki/`, or Mendeley automatically.

Only selected PDFs or durable insights are promoted.

## Paper Briefs

When a candidate paper looks interesting but is not ready for full wiki ingest, create:

```text
paper-briefs/{first-author}-{year}-{short-title}.md
```

Use `explorations/_template/Paper_Brief_TEMPLATE.md` as the format. A paper brief may summarize title/abstract metadata, temporary PDF notes, or why the paper might matter. It must clearly label what evidence is available.

## Local Synthesis

Use `synthesis.md` to summarize what this exploration currently suggests. This file can synthesize `Exploration_Brief.md`, `notes.md`, `questions.md`, `paper-briefs/`, candidate metadata, and already-ingested wiki pages.

Do not treat `synthesis.md` as permanent knowledge. If a point becomes durable and project-independent, add it to `promote-to-wiki.md` and then promote through the normal Library path.
