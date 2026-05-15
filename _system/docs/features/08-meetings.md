# 08 · Meeting system

## What it does
Each project can schedule meetings directly from the dashboard. When a meeting is created the system:
- Writes a structured **`.md`** record with frontmatter (type, datetime, attendees, …).
- Writes a standard **`.ics`** calendar invite (RFC-5545) next to the `.md`.
- Adds the event to **macOS Calendar.app** via AppleScript.
- Opens the **default mail app** with a `mailto:` to all attendees (subject + body pre-filled).

Meetings live under `projects/{slug}/meetings/`.

## Meeting types
Default types: `table`, `progress`, `collaborator`.
You can add custom types from the modal (`+ New type`). They are persisted in `_system/admin/meeting_types.json` and apply to **all** projects.

## Creating a meeting
1. Click **`+ Meeting`** on a project card.
2. Pick a type (or add a new one), title, datetime, duration, optional location.
3. Tick which attendees should be included. Project managers are auto-listed; add extras inline if needed.
4. Options at the bottom:
   - **Add to macOS Calendar** (default ON) — uses AppleScript on the default writable calendar.
   - **Open mail app with invite info** (default ON) — opens `mailto:` with the meeting summary in the body. The `.ics` file also opens in Finder/Calendar so you can manually attach it to the email if desired (the `mailto:` protocol cannot attach files itself).

## Viewing meetings
Click **`Meetings`** on a project card. The modal lists meetings sorted by date (newest first), each with type, time, duration, attendee count, and location.

Each row has:
- **Click the title** → opens the meeting `.md` in your default editor.
- **`+ Note`** button → append-only note modal.
- **`.ics`** button → re-opens the calendar invite (Calendar.app re-adds it).

## Adding notes
Notes are **append-only**. The note modal collects markdown + optional author and appends a section to the meeting `.md`:

```markdown
### Note — 2026-05-14 15:30 (Alice)

- Decision: drop Fig 3 panel B.
- Action: rerun control with new mouse line.
```

The file itself becomes the audit log — old notes are never edited.

## File layout
```
projects/{slug}/meetings/
├── 2026-06-01-1400-progress-q2-checkin.md     ← record + notes history
├── 2026-06-01-1400-progress-q2-checkin.ics    ← calendar invite
├── 2026-06-08-1100-collaborator-shared-data.md
└── 2026-06-08-1100-collaborator-shared-data.ics
```

## Server API
| Action | Notes |
|---|---|
| `list-meeting-types` | Returns the current type list. |
| `add-meeting-type` | Appends a new type (validated: 2–32 chars, `[A-Za-z0-9_-]`). |
| `create-meeting` | Writes `.md` + `.ics`; optionally adds to Calendar.app; returns a `mailto:` URL the UI opens. |
| `list-meetings` | Returns parsed meetings for a project. |
| `add-meeting-note` | Appends a `### Note — {timestamp}` section to a meeting file. |

## ICS notes
- Generated locally; nothing leaves your machine.
- Attendees are written as `ATTENDEE;CN="Name";RSVP=TRUE:MAILTO:email`.
- "Floating local time" — no timezone Z suffix — so the event lands at the same wall-clock time regardless of the recipient's tz.

## AppleScript notes
- Uses the **first writable calendar** as the target. Change this in `_calendar_app_add` if you want a specific calendar.
- Requires macOS Calendar permission on first run.

## Solo vs collaborator use
- **Solo use today**: leave attendees empty; the `.ics` and Calendar.app entry still go through. Mailto is harmless even with no recipients (it just opens the mail app to a blank compose window).
- **Future collaborator use**: add collaborators as project managers (or as ad-hoc attendees). The same flow then sends them a real calendar invite via your mail app.
