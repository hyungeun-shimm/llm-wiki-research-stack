---
confidential_tier: local-only
---

# Project Template

Copy this folder to `projects/{slug}/` when starting a new project. Then:

1. Decide the project type. Rename `Project_Brief.md` to itself (keep it) for `grant`, `paper_in_prep`, or `review_article`. For `library_ingest`, delete `Project_Brief.md` and rename `Project_Brief_library_ingest.md` → `Project_Brief.md`.
2. Fill in `Project_Brief.md` carefully. Vague briefs produce vague drafts.
3. Delete any unused optional files for your project type. Keep what fits.

## Folder map

| File / folder | Required for | Purpose |
|---|---|---|
| `Project_Brief.md` | all types | Project contract |
| `Roadmap.md` | confidential types | High-level timeline + milestones |
| `Decision_Log.md` | confidential types | Append-only record of why decisions were made |
| `Evidence_Map.md` | confidential types | Maps draft claims → wiki sources |
| `Drafts/` | confidential types | Drafter writes here |
| `critiques/argue/` | confidential types | Reviewer-#2-style critique logs |
| `critiques/demon/` | confidential types | Devil's-advocate critique logs |
| `rejection-sims/` | confidential types | Pre-mortem rejection scenarios |
| `notes/` | confidential types | Confidential brainstorming, unresolved questions |
| `figure-plan_TEMPLATE.md` | `paper_in_prep` only | Optional figure-level tracker |
| `experiment-roadmap_TEMPLATE.md` | `paper_in_prep` only | Optional experiment plan |
| `data-updates/` + `data-updates_TEMPLATE.md` | `paper_in_prep` only | Optional unpublished-data summaries |

## Confidentiality

All files in this template are `confidential_tier: local-only` by default. The local agent reads them; cloud agents refuse.

The single exception is `Project_Brief_library_ingest.md`, used only for `library_ingest` projects. That brief is cloud-readable because it contains only public scouting metadata.

## Scout

Confidential projects do **not** run scout. To request new literature, open or update an `explorations/idea-notes/{topic}.md` file with public keywords and run scout there. The translation from "what my grant needs" to "what's a public topic" is performed by the user, not by an LLM.
