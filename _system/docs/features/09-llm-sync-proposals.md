# 09 · LLM sync proposals (Phase 3)

## What it does
Two new **local-LLM** roles read recent data-updates / meeting notes and **propose discrete mechanical changes** to the project's planning artifacts (`figure-plan.md`, `experiment-roadmap.md`, `Decision_Log.md`). The LLM never edits files directly — it writes a **proposal** that the user reviews and applies item by item.

## New roles
| Role | Reads | Subagent prompt |
|---|---|---|
| `data-sync` | Recent `data-updates/*.md` + planning artifacts | `subagents/12-data-sync.md` |
| `meeting-sync` | Recent `meetings/*.md` + planning artifacts | `subagents/13-meeting-sync.md` |

Both roles run via `python3 scripts/local_agent.py --role {role} --project {slug}` against LM Studio on `http://localhost:1234`. They are confidential-only (cloud agents are blocked).

## Triggering from the dashboard
Each project card has two buttons:
- **`🤖 Sync data`** — launches `data-sync` in Terminal.
- **`🤖 Sync meetings`** — launches `meeting-sync` in Terminal.

When the role finishes, a proposal file is saved under `projects/{slug}/sync-proposals/{role}-v{N}-{date}.md`.

## Reviewing proposals
Click **`Proposals`** on a project card. The modal shows each proposal as a card with:
- Action count + timestamp.
- A checkbox per action with a one-line summary.
- `Open file` to inspect the raw proposal markdown.
- `Toggle all` and **`Apply selected`** to commit.

## Action vocabulary
The LLM emits a single fenced ```` ```json ```` block; each action object has an `id` plus one of:

| `action` | What `Apply` does |
|---|---|
| `figure_plan_status_update` | Set the Status cell for the matching Figure/Panel row in `figure-plan.md`. |
| `experiment_roadmap_status_update` | Set the Status cell in `experiment-roadmap.md`. |
| `figure_plan_add_row` | Append a new row to `figure-plan.md`. |
| `experiment_roadmap_add_row` | Append a new row to `experiment-roadmap.md`. |
| `decision_log_append` | Append a dated bullet to `Decision_Log.md` (append-only). |
| `note` | Informational only — never applied automatically. |

Every action carries `source_files` so you can trace why the LLM proposed it.

## After Apply
The server appends an audit section to the proposal `.md`:

```markdown
## Applied — 2026-05-15T15:42:11

- Applied: p1 figure_plan_status_update (changed=True), p3 decision_log_append
- Skipped: p2 figure_plan_status_update (no row matched 'Fig 9')
```

## Why this design
- **No silent edits.** Every change is preceded by an LLM proposal and a user click.
- **No invention.** Subagent prompts require `source_files` citations; ungrounded suggestions become `note` actions that are never auto-applied.
- **Mechanical apply.** The server uses regex / YAML edits, not the LLM, to mutate planning files. This means an Apply cannot itself hallucinate.
- **Confidential-by-construction.** Local LLM only; no project content leaves your machine.

## Server API
| Action | Notes |
|---|---|
| `local-data-sync` / `local-meeting-sync` | Open a Terminal session running the role. |
| `list-sync-proposals` | Returns all proposal files + parsed action arrays for a project. |
| `apply-sync-proposal` | params: `proposal_rel_path`, `selected_ids`. Applies each selected action mechanically; logs result to the proposal. |

## Files involved
- `subagents/12-data-sync.md`, `subagents/13-meeting-sync.md` — LLM system prompts.
- `scripts/local_agent.py` — `ROLE_TO_SUBAGENT`, `load_context`, `output_path` branches for the two new roles.
- `scripts/dashboard_server.py` — `list-sync-proposals`, `apply-sync-proposal` and the per-action handlers.
- `_system/dashboard/app.js` — `launchLocalSync`, `openProposalsModal`, `summarizeAction`.
