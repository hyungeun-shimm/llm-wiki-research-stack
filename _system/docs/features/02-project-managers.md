# 02 · Project managers

## What it does
- Assign **multiple** managers to each project, each with a **name + email**.
- A badge in the **bottom-right of every project card** shows manager names.
- Clicking the badge opens a **popup** with one row per manager: a checkbox, the name, and a clickable email (opens `mailto:`).
- For multi-manager projects the popup adds a **"Select all"** toggle and an **"Email selected managers"** button that opens a single `mailto:` with all checked addresses comma-joined.
- Editing managers is gated by **admin mode** (see [03-admin-mode-pin.md](03-admin-mode-pin.md)). When admin is unlocked, an `✎` button appears next to the badge.

## Storage
Managers live in each project's `Project_Brief.md` frontmatter:

```yaml
managers:
  - name: "Alice Lee"
    email: "alice@example.com"
  - name: "Bob Park"
    email: "bob@example.com"
```

## Server API
| Action | Notes |
|---|---|
| `update-managers` | Rewrites the `managers:` block. **PIN-protected** — requires `admin_pin` in params. |

## Where in the code
- `scripts/build_dashboard.py` — `normalize_managers()` reads frontmatter and exposes it in `dashboard.json` as `project.managers`.
- `scripts/dashboard_server.py` — `update-managers` action + `_write_managers_frontmatter` helper.
- `_system/dashboard/app.js` — `buildManagerBadge`, `openManagerPopover`, `openManagerEditor`.
- `_system/dashboard/styles.css` — `.manager-badge-wrap`, `.manager-popover`, etc.

## User flow
1. Unlock admin mode (top bar).
2. Click `✎` on a project card.
3. Add rows (name + email), `Save`.
4. Dashboard rebuilds; the badge appears at the card's bottom-right.
5. Later, click the badge → check who you want → `📧 Email selected managers`.
