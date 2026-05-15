# 05 · Data updates (Google Drive integration, canonical naming, archive, CHANGELOG)

## What it does
The `+ Data update` button on each project card opens a structured form that:
1. Lets you **pick a data file** via a native macOS file dialog (no manual path typing).
2. Moves the chosen file into the project's **`LLM_project_manager/`** folder under your Google Drive directory.
3. Renames the file to a **canonical, human-readable name** like `fig-1A_wt-vs-ko-baseline.csv`.
4. Saves a structured `.md` record in `projects/{slug}/data-updates/` with the user's interpretation and next-step text.
5. When updating an existing data record with a newer n, **compresses the previous file** into `LLM_project_manager/archive/`.
6. Appends an entry to `LLM_project_manager/CHANGELOG.md` (append-only).

## Google Drive convention
- Each project's `Project_Brief.md` carries a `gdrive_path` frontmatter field pointing to the project's Drive folder.
- Inside that folder, a dedicated **`LLM_project_manager/`** subfolder is auto-created on first use.
- The LLM has access only to files referenced inside `LLM_project_manager/` — your other Drive content is untouched.

If `gdrive_path` is not set, the data-update modal shows an inline **"Set Google Drive path…"** button that opens a folder picker and writes the field automatically.

## Canonical filename rules
| Figure / panel | Filename prefix |
|---|---|
| `Fig 1`, panel `A` | `fig-1A_{brief-slug}.ext` |
| `Fig 2`, no panel | `fig-2_{brief-slug}.ext` |
| figure starts with "prelim" | `prelim_{brief-slug}.ext` |
| no figure | `unspecified_{brief-slug}.ext` |

The brief description (3–6 words) is required and drives the `{brief-slug}` portion.

## Two modes
- **New data** — creates a new `.md` record and moves the file to its canonical name.
- **Adding to existing data** — pick an existing data-update from a dropdown. The new file replaces the canonical one, and the previous file is **compressed** to `LLM_project_manager/archive/{name}_{timestamp}.zip`. A new "Data Update — {timestamp}" section is appended to the existing `.md` (history within the file).

## What gets written

```text
{gdrive_path}/LLM_project_manager/
├── fig-1A_wt-vs-ko-baseline.csv           ← current canonical file
├── prelim_pilot-trace.png
├── unspecified_misc.csv
├── archive/
│   ├── fig-1A_wt-vs-ko-baseline_20260512-101522.zip   ← compressed previous version
│   └── …
└── CHANGELOG.md                            ← append-only history
```

And in the repo:
```text
projects/{slug}/data-updates/
└── 2026-05-15-fig-1a_wt-vs-ko-baseline.md  ← structured record
```

## Server API
| Action | Notes |
|---|---|
| `pick-data-path` | Opens a macOS `osascript` file/folder dialog; returns the absolute path. |
| `set-project-gdrive-path` | Writes/updates the `gdrive_path` frontmatter field. |
| `add-data-update` | Creates a new record (`mode: new`) or appends to an existing one (`mode: existing`). Handles file move + archive. |
| `list-project-figures` | Returns parsed `figure-plan.md` rows + existing data-updates (used by the dropdown). |

## Frontmatter fields written to the `.md`
```yaml
date: 2026-05-15
project_slug: my-project
figure: "Fig 1"
panel: "A"
status: analyzed
brief_description: "wt vs ko baseline"
data_path: "/Volumes/GoogleDrive/.../LLM_project_manager/fig-1A_wt-vs-ko-baseline.csv"
confidential_tier: local-only
```

## Why this design
- Single source of truth is the **`figure` field in the `.md` frontmatter** — physical filenames mirror it but are not authoritative.
- Compressed archive lets you roll back without bloating Drive storage.
- CHANGELOG provides reproducibility/audit trail without bloating individual files.
- LLM scope is strict: only `LLM_project_manager/` is touched.
