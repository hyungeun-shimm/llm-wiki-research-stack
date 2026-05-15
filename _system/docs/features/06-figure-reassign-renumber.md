# 06 · Figure reassign and bulk renumber

## Why
As a project evolves, figures get re-organised:
- **Case A** — a dataset originally collected for `Fig 1` ends up belonging to `Fig 2`.
- **Case B** — the entire figure ordering is shuffled (`Fig 2 ↔ Fig 3`).
- **Promotion** — `unspecified_xxx` data gets assigned to `Fig 1`.

The system tracks both cases without losing history.

## Single source of truth
The **`figure` field in each data-update's frontmatter** is authoritative. Physical filenames in `LLM_project_manager/` are kept in sync but are display-only.

## Reassign (one data-update at a time)
1. Open the **data updates** count-chip popup.
2. Click the **`Reassign…`** button on the desired row.
3. Enter new figure (e.g. `Fig 2`), optional new panel, and a reason.
4. The server:
   - rewrites the `.md` frontmatter (`figure`, `panel`, `data_path`),
   - renames the canonical file in `LLM_project_manager/` (`unspecified_foo.csv` → `fig-2A_foo.csv`),
   - appends a `REASSIGN` line to `CHANGELOG.md`,
   - re-runs `build_dashboard.py`.

## Bulk renumber (whole-project shifts)
1. Click **`Renumber figures`** on a project card.
2. Add one or more `from → to` mappings (e.g. `Fig 2 → Fig 3`, `Fig 3 → Fig 2`).
3. Provide a reason (recorded in CHANGELOG).
4. Server applies the mapping to **every** matching data-update + renames their files + updates `figure-plan.md` rows. A 2-pass rename via temporary names handles swap-style cases safely.

## Server API
| Action | Notes |
|---|---|
| `reassign-data-update` | params: `update_rel_path`, `new_figure`, `new_panel`, `reason` |
| `renumber-figures` | params: `mapping`, `reason` |

## CHANGELOG examples
```
2026-05-15 14:32  REASSIGN  data-updates/2026-05-12-unspecified-foo.md  figure: "" → "Fig 1/A"  reason: "moved to main result"; file renamed unspecified_foo.csv → fig-1A_foo.csv
2026-05-16 09:10  RENUMBER  2026-05-12-fig-2a_wt-ko.md: "Fig 2" → "Fig 3"  reason: "reordered for clarity"
2026-05-16 09:10  RENUMBER  figure-plan.md: 4 row(s) updated
```

## What this does NOT do
- It does **not** modify files outside `LLM_project_manager/`.
- It does **not** auto-move other (non-canonical) copies of the data you may have in Drive.
- It does **not** edit historic data-update files retroactively — only frontmatter and file names are touched; the body text remains as you wrote it.
