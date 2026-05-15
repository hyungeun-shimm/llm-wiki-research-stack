# 07 · Archive viewer and restore

## What it does
Every time a data file is replaced by a newer version (n+ scenario in [05-data-updates.md](05-data-updates.md)), the previous file is **compressed** into `LLM_project_manager/archive/`. This view lets you list those archives and restore one back into the working folder.

## How to access
1. On any project card, click **`📦 Archive`**.
2. The modal lists every zip in `LLM_project_manager/archive/`, newest first.
3. Each row shows filename, size (KB), modification time, and a **`Restore`** button.

## Restore behaviour
- The zip is extracted back into `LLM_project_manager/`.
- If a file with the original name **already exists**, the restored file is suffixed with `_restored_{timestamp}` to avoid clobbering current data.
- A `RESTORE` line is appended to `CHANGELOG.md`.

## Server API
| Action | Notes |
|---|---|
| `list-archive` | Returns the list of zip files in the project's archive folder. |
| `restore-archive` | params: `zip_path`. Refuses any path outside the project's archive folder. |

## Archive format
Each `.zip` contains:
- The original data file at its original name.
- An `_archive_meta.txt` with: `original: ...`, `reason: ...`, `archived_at: ...`.

## When you should restore
Use this if a new data version turned out to be wrong (analysis error, file copy mistake, etc.). The restore brings back the old file alongside the current one so you can compare or swap manually.
