# 04 · Count-chip file list popup

## What it does
Every count chip on a project card (candidate jsons, triage reports, draft files, claim logs, notes, data updates, …) is now **clickable**. Clicking opens a popup listing the actual files in the corresponding folder. Each file row opens the file in its default macOS app when clicked.

## Bucket mapping
| Chip label | Folder / file | Behaviour |
|---|---|---|
| candidate jsons | `projects/{slug}/candidates/**/*.json` | excludes `_consolidated.json` |
| triage reports | `projects/{slug}/triage-reports/**/*.md` | |
| approval boards | `projects/{slug}/triage-reports/*_approval-board.html` | |
| draft files | `projects/{slug}/drafts/*.md` (and `Drafts/`) | excludes `.draft_claim_log.md` |
| claim logs | `projects/{slug}/drafts/*.draft_claim_log.md` | |
| candidate batches | sub-directories of `candidates/` | shows directory + file count |
| notes | `projects/{slug}/notes/*.md` | |
| figure rows | `projects/{slug}/figure-plan.md` | single-file: opens the plan itself |
| data updates | `projects/{slug}/data-updates/*.md` | each row also has a `Reassign…` button |
| critique/logs | `projects/{slug}/critiques/**/*.md` | |
| meetings | `projects/{slug}/meetings/*.md` | hidden chip — used internally |

## Server API
| Action | Notes |
|---|---|
| `list-bucket-files` | params: `bucket`, `project_slug`. Returns `{items: [{name, rel_path, kind, mtime, size?}, ...]}` |
| `open-relative-path` | params: `rel_path`. Validates path is inside repo root, calls `open` (macOS) |

## Where in the code
- Server: `BUCKET_DEFS`, `_list_bucket` in `scripts/dashboard_server.py`.
- UI: `openBucketFiles` in `_system/dashboard/app.js`.

## Why
Before this change, count chips were purely informational; users had to open a file browser separately. Now every chip is a 1-click drill-down into the underlying files.
