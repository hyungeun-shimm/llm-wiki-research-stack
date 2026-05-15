# 01 · Layout refresh

## What changed
- **Snapshot** panel (Source Pages / Overviews / Inbox PDFs / Idea Notes / Projects / Local Draft Checks) moved to the **top row, full width**.
- **Active workspaces** sits below it as a **full-width column** — one project card per row, instead of being squeezed next to Snapshot.
- Inside each project card the 10 count chips are now arranged in a **single horizontal flex row** with auto-sized chips, so wide screens never wrap.

## Why
The previous 2-column layout pushed cards into a narrow column. As project count grew, the page scrolled excessively. The new arrangement gives each card the full screen width.

## Implementation
- `_system/dashboard/index.html` — replaced `top-double-row` 2-column grid with two stacked `top-stack-panel` sections.
- `_system/dashboard/styles.css` — new `.summary-grid--row` (auto-fit minmax 110px), `.project-grid--row` (one column), `.counts-grid` flex nowrap.

## No new API
This is purely a layout change. No server endpoints involved.
