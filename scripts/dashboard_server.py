#!/usr/bin/env python3
"""Serve the dashboard with a small allowlisted local command API.

This replaces the plain `python3 -m http.server` workflow when you want the
dashboard to run safe local actions directly. It intentionally does not expose
an arbitrary shell. The browser sends an action id plus a project slug, and this
server reconstructs the command from a local allowlist.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import shutil
import smtplib
import subprocess
import sys
import re
import threading
from datetime import datetime, timedelta
from email.message import EmailMessage
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "_system" / "dashboard" / "run-logs"
PROJECTS = ROOT / "projects"
TEMPLATES = PROJECTS / "_template"
EXPLORATIONS = ROOT / "explorations"
PAPERS = ROOT / "papers"
SCOUTS = ROOT / "scouts"
WIKI   = ROOT / "wiki"
LOCAL_AGENT_ROLES = {
    "local-planner": "planner",
    "local-drafter": "drafter",
    "local-argue": "argue",
    "local-demon": "demon",
    "local-rejection-sim": "rejection-sim",
    "local-scout-brief": "scout-brief",
    "local-data-sync": "data-sync",
    "local-meeting-sync": "meeting-sync",
}


def slugify(text: str) -> str:
    """Turn an arbitrary topic string into a filesystem-safe slug."""
    keep = []
    for ch in text.lower().strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in {" ", "-", "_", "/"}:
            keep.append("-")
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "topic"


def scout_slug(topic: str, year_start: str = "", year_end: str = "") -> str:
    slug = slugify(topic)
    years = "-".join(part for part in [year_start.strip(), year_end.strip()] if part)
    if years:
        slug = f"{slug}-{slugify(years)}"
    return slug or "topic"


def require_simple_slug(slug: str, label: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
        raise DashboardError(f"Invalid {label}: {slug!r}")
    return slug


def read_project_type(project: Path) -> str | None:
    """Parse `project_type:` out of Project_Brief.md frontmatter, if present."""
    brief = project / "Project_Brief.md"
    if not brief.exists():
        return None
    try:
        with brief.open("r", encoding="utf-8") as handle:
            in_fm = False
            for line in handle:
                line = line.rstrip("\n")
                if line.strip() == "---":
                    if not in_fm:
                        in_fm = True
                        continue
                    break
                if in_fm and line.lower().startswith("project_type:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def _write_managers_frontmatter(brief_path: Path, managers: list[dict[str, str]]) -> str:
    """Replace the `managers:` block in a Project_Brief.md frontmatter.

    Preserves all other frontmatter fields and body text. If no `managers:` key
    exists, inserts one at the end of the frontmatter block.
    """
    raw = brief_path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise DashboardError("Project_Brief.md has no YAML frontmatter to update.")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise DashboardError("Malformed frontmatter in Project_Brief.md.")
    fm_text = parts[1]
    body = parts[2]
    fm_lines = fm_text.splitlines()
    # Drop existing `managers:` and any indented list rows under it.
    new_lines: list[str] = []
    skipping = False
    for line in fm_lines:
        stripped = line.lstrip()
        if not skipping and line.startswith("managers:"):
            skipping = True
            continue
        if skipping:
            if line.startswith((" ", "\t", "-")) and stripped:
                continue
            skipping = False
        new_lines.append(line)
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()
    if managers:
        new_lines.append("managers:")
        for m in managers:
            name = (m.get("name") or "").replace('"', '\\"')
            email = (m.get("email") or "").replace('"', '\\"')
            new_lines.append(f'  - name: "{name}"')
            new_lines.append(f'    email: "{email}"')
    rebuilt = "---\n" + "\n".join(new_lines) + "\n---" + body
    brief_path.write_text(rebuilt, encoding="utf-8")
    return f"Updated managers in {brief_path.relative_to(ROOT)} ({len(managers)} entr{'y' if len(managers) == 1 else 'ies'})."


def require_library_ingest(project: Path) -> None:
    """Reject scout/triage actions on confidential projects."""
    ptype = read_project_type(project)
    if ptype != "library_ingest":
        raise DashboardError(
            f"Scout cannot run on a confidential project (type={ptype!r}). "
            f"Open or update an explorations/idea-notes/{{topic}}.md and run "
            f"Quick Scout (or scout-exploration) instead."
        )


def require_confidential_project(project: Path) -> None:
    """Allow local-agent launches only for confidential project folders."""
    ptype = read_project_type(project)
    if ptype == "library_ingest":
        raise DashboardError(
            "Local LLM roles are only for confidential projects. "
            "Use the public scout/ingest actions for library_ingest workspaces."
        )


class DashboardError(Exception):
    """User-facing dashboard command error."""


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def ensure_inside_root(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise DashboardError(f"Path escapes repository root: {path}") from exc
    return resolved


def project_path(slug: str | None) -> Path:
    if not slug:
        raise DashboardError("Missing project_slug.")
    # Try projects/{slug} first, then projects/published/{slug}.
    candidates = [PROJECTS / slug, PROJECTS / "published" / slug]
    for candidate in candidates:
        if candidate.is_dir():
            return ensure_inside_root(candidate)
    raise DashboardError(f"Project folder does not exist: projects/{slug} or projects/published/{slug}")


def is_published_project(project: Path) -> bool:
    """Return True if project lives under projects/published/."""
    try:
        rel_parts = project.relative_to(PROJECTS).parts
    except ValueError:
        return False
    return len(rel_parts) >= 2 and rel_parts[0] == "published"


def active_exploration_path(slug: str | None) -> Path:
    if not slug:
        raise DashboardError("Missing exploration_slug.")
    safe_slug = require_simple_slug(slug, "exploration_slug")
    path = ensure_inside_root(EXPLORATIONS / "active" / safe_slug)
    if not path.is_dir():
        raise DashboardError(f"Active exploration folder does not exist: explorations/active/{safe_slug}")
    return path


def scout_request_path(slug: str | None) -> Path:
    if not slug:
        raise DashboardError("Missing scout_slug.")
    safe_slug = require_simple_slug(slug, "scout_slug")
    path = ensure_inside_root(SCOUTS / safe_slug)
    if not path.is_dir():
        raise DashboardError(f"Scout request folder does not exist: scouts/{safe_slug}")
    return path


def latest_approval_board(project: Path) -> Path | None:
    triage = project / "triage-reports"
    if not triage.exists():
        return None
    boards = sorted(triage.glob("*_approval-board.html"), key=lambda p: p.stat().st_mtime)
    return boards[-1] if boards else None


def copy_if_missing(src: Path, dst: Path) -> str:
    ensure_inside_root(src)
    ensure_inside_root(dst)
    if dst.exists():
        return f"kept existing {rel(dst)}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"created {rel(dst)}"


def open_path(path: Path) -> dict[str, Any]:
    target = ensure_inside_root(path)
    return run_process(["open", str(target)], timeout=30)


_STAGE_LABELS_DASH = {
    "brief": "Project Brief",
    "figure-flow": "Figure Flow",
    "data-needed": "Data Needed",
    "figure-plan": "Figure Plan",
}


def open_local_agent(role: str, project: Path, section: str = "") -> dict[str, Any]:
    """Open an interactive local-agent session in Terminal without blocking the dashboard."""
    require_confidential_project(project)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    section_tag = f"-{section}" if section else ""
    launcher = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-local-agent-{role}{section_tag}-{project.name}.command"
    section_flag = f" --section {section}" if section else ""
    if section:
        stage_label = _STAGE_LABELS_DASH.get(section, f"section: {section}")
        section_note = f" — target: {stage_label}"
    else:
        section_note = ""
    command = (
        "#!/bin/zsh\n"
        f"cd {json.dumps(str(ROOT))}\n"
        f"echo 'Local LLM agent launcher — role: {role}{section_note}'\n"
        "echo 'Keep LM Studio Local Server running at http://localhost:1234/v1 before using this session.'\n"
        "echo ''\n"
        f"{json.dumps(sys.executable)} scripts/local_agent.py --role {role} --project {json.dumps(project.name)}{section_flag}\n"
        "echo ''\n"
        "echo 'Session ended. You can close this Terminal window.'\n"
        "read -k 1 -s '?Press any key to close...'\n"
    )
    launcher.write_text(command, encoding="utf-8")
    launcher.chmod(0o700)
    result = run_process(["open", "-a", "Terminal", str(launcher)], timeout=30)
    result["stdout"] = (
        f"Opened Terminal launcher for local {role}{section_note}: {rel(launcher)}\n"
        "LM Studio must have Local Server running before the agent can connect."
    )
    result["reload_suggested"] = False
    return result


def open_terminal_runner(label: str, command_line: str, success_note: str = "") -> dict[str, Any]:
    """Open a Terminal window that runs an arbitrary local command and stays open after."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-") or "task"
    launcher = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_label}.command"
    script = (
        "#!/bin/zsh\n"
        f"cd {json.dumps(str(ROOT))}\n"
        f"echo '{label}'\n"
        "echo 'LM Studio Local Server (http://localhost:1234/v1) must be running.'\n"
        "echo ''\n"
        f"{command_line}\n"
        "echo ''\n"
        f"echo '{success_note or 'Done.'}'\n"
        "read -k 1 -s '?Press any key to close...'\n"
    )
    launcher.write_text(script, encoding="utf-8")
    launcher.chmod(0o700)
    result = run_process(["open", "-a", "Terminal", str(launcher)], timeout=30)
    result["stdout"] = f"Opened Terminal: {rel(launcher)}\n{success_note}"
    result["reload_suggested"] = False
    return result


def open_schematic_generator(project: Path) -> dict[str, Any]:
    require_confidential_project(project)
    py = json.dumps(sys.executable)
    slug = json.dumps(project.name)
    cmd = f"{py} scripts/generate_schematic.py --project {slug}"
    return open_terminal_runner(
        label=f"Generate schematic — {project.name}",
        command_line=cmd,
        success_note=f"Schematic written to projects/{project.name}/schematics/.",
    )


def open_figure_mockups_generator(project: Path, panel: str = "") -> dict[str, Any]:
    require_confidential_project(project)
    py = json.dumps(sys.executable)
    slug = json.dumps(project.name)
    panel_flag = f" --panel {json.dumps(panel)}" if panel else ""
    cmd = f"{py} scripts/generate_figure_mockups.py --project {slug}{panel_flag}"
    return open_terminal_runner(
        label=f"Generate figure mockups — {project.name}",
        command_line=cmd,
        success_note=f"Mockups written to projects/{project.name}/figure-mockups/.",
    )


def run_process(args: list[str], timeout: int = 300) -> dict[str, Any]:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    ended = datetime.now().astimezone().isoformat(timespec="seconds")
    log_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{Path(args[0]).name}.log"
    log_path.write_text(
        "\n".join(
            [
                f"started: {started}",
                f"ended: {ended}",
                f"cwd: {ROOT}",
                f"command: {' '.join(args)}",
                f"exit_code: {proc.returncode}",
                "",
                "STDOUT",
                proc.stdout,
                "",
                "STDERR",
                proc.stderr,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "command": " ".join(args),
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-6000:],
        "log": rel(log_path),
    }


def rebuild_dashboard() -> dict[str, Any]:
    return run_process([sys.executable, "scripts/build_dashboard.py"], timeout=120)


def auto_download_queue(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if not isinstance(payload, dict):
        raise DashboardError("Missing download queue payload.")
    report_dir_value = str(params.get("report_dir") or "_system/downloads").strip()
    report_dir = ensure_inside_root(ROOT / report_dir_value)
    queue_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-download-queue.json"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_process(
        [
            sys.executable,
            "scripts/auto_download_selected_pdfs.py",
            rel(queue_path),
            "--out",
            "papers/inbox",
            "--report-dir",
            rel(report_dir),
            "--action",
            "download",
        ],
        timeout=900,
    )


ADMIN_DIR = ROOT / "_system" / "admin"
ADMIN_CONFIG = ADMIN_DIR / "admin_config.json"
RESET_CODE_TTL_MIN = 15


def _load_admin_config() -> dict:
    if not ADMIN_CONFIG.exists():
        return {}
    try:
        return json.loads(ADMIN_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_admin_config(data: dict) -> None:
    ADMIN_DIR.mkdir(parents=True, exist_ok=True)
    ADMIN_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(ADMIN_CONFIG, 0o600)
    except OSError:
        pass


def _hash_pin(pin: str, salt: str) -> str:
    h = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return h.hex()


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _validate_pin(pin: str) -> str:
    pin = (pin or "").strip()
    if not re.fullmatch(r"\d{4,8}", pin):
        raise DashboardError("PIN must be 4–8 digits.")
    return pin


def _validate_email(email: str) -> str:
    email = (email or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise DashboardError(f"Invalid email address: {email!r}")
    return email


def _smtp_env() -> dict | None:
    host = os.environ.get("DASHBOARD_SMTP_HOST")
    user = os.environ.get("DASHBOARD_SMTP_USER")
    pwd = os.environ.get("DASHBOARD_SMTP_PASSWORD")
    if not (host and user and pwd):
        return None
    return {
        "host": host,
        "port": int(os.environ.get("DASHBOARD_SMTP_PORT") or 587),
        "user": user,
        "password": pwd,
        "from_addr": os.environ.get("DASHBOARD_SMTP_FROM") or user,
    }


def _send_reset_email(recipient: str, code: str) -> tuple[bool, str]:
    cfg = _smtp_env()
    if not cfg:
        msg = (
            f"[Dashboard] SMTP not configured. Reset code printed to server console: {code}\n"
            "Configure SMTP by setting DASHBOARD_SMTP_HOST / PORT / USER / PASSWORD / FROM env vars."
        )
        print(f"[admin-reset-pin] Recovery code for {recipient}: {code}")
        return False, msg
    try:
        em = EmailMessage()
        em["Subject"] = "Dashboard admin PIN reset code"
        em["From"] = cfg["from_addr"]
        em["To"] = recipient
        em.set_content(
            f"Your dashboard admin PIN reset code is: {code}\n\n"
            f"This code expires in {RESET_CODE_TTL_MIN} minutes.\n"
            "If you did not request this, you can ignore this email."
        )
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as smtp:
            smtp.starttls()
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(em)
        return True, f"Reset code sent to {_mask_email(recipient)}."
    except Exception as exc:  # noqa: BLE001
        print(f"[admin-reset-pin] SMTP send failed: {exc}. Code for {recipient}: {code}")
        return False, f"SMTP send failed: {exc}. Code printed to server console."


def handle_admin_action(action_id: str, params: dict) -> dict:
    cfg = _load_admin_config()
    is_configured = bool(cfg.get("pin_hash"))

    if action_id == "admin-status":
        return {
            "ok": True,
            "exit_code": 0,
            "command": "admin-status",
            "stdout": json.dumps({
                "configured": is_configured,
                "recovery_email_masked": _mask_email(cfg.get("recovery_email", "")),
                "smtp_configured": _smtp_env() is not None,
            }),
            "stderr": "",
            "log": "",
        }

    if action_id == "admin-setup":
        if is_configured and not params.get("force"):
            raise DashboardError("Admin already configured. Use reset-pin to change it.")
        pin = _validate_pin(str(params.get("pin") or ""))
        recovery_email = _validate_email(str(params.get("recovery_email") or ""))
        salt = secrets.token_hex(16)
        cfg = {
            "pin_hash": _hash_pin(pin, salt),
            "salt": salt,
            "recovery_email": recovery_email,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        _save_admin_config(cfg)
        return {
            "ok": True,
            "exit_code": 0,
            "command": "admin-setup",
            "stdout": f"Admin PIN configured. Recovery email: {_mask_email(recovery_email)}",
            "stderr": "",
            "log": "",
        }

    if action_id == "admin-verify":
        if not is_configured:
            raise DashboardError("Admin PIN is not configured yet.")
        pin = _validate_pin(str(params.get("pin") or ""))
        expected = cfg.get("pin_hash", "")
        if not hmac.compare_digest(_hash_pin(pin, cfg.get("salt", "")), expected):
            raise DashboardError("Incorrect PIN.")
        return {
            "ok": True,
            "exit_code": 0,
            "command": "admin-verify",
            "stdout": "PIN verified.",
            "stderr": "",
            "log": "",
        }

    if action_id == "admin-request-reset":
        if not is_configured:
            raise DashboardError("Admin PIN is not configured yet.")
        provided = _validate_email(str(params.get("recovery_email") or ""))
        stored = cfg.get("recovery_email", "")
        if provided.lower() != stored.lower():
            raise DashboardError("Recovery email does not match the configured address.")
        code = f"{secrets.randbelow(1000000):06d}"
        salt = cfg.get("salt") or secrets.token_hex(16)
        cfg["salt"] = salt
        cfg["reset_token"] = {
            "code_hash": _hash_pin(code, salt),
            "expires_at": (datetime.now() + timedelta(minutes=RESET_CODE_TTL_MIN)).isoformat(timespec="seconds"),
        }
        _save_admin_config(cfg)
        sent, message = _send_reset_email(stored, code)
        return {
            "ok": True,
            "exit_code": 0,
            "command": "admin-request-reset",
            "stdout": json.dumps({
                "sent_via_email": sent,
                "message": message,
                "ttl_minutes": RESET_CODE_TTL_MIN,
                "recovery_email_masked": _mask_email(stored),
            }),
            "stderr": "",
            "log": "",
        }

    if action_id == "admin-reset-pin":
        if not is_configured:
            raise DashboardError("Admin PIN is not configured yet.")
        token = cfg.get("reset_token") or {}
        if not token.get("code_hash"):
            raise DashboardError("No active reset code. Request a new one first.")
        try:
            expires = datetime.fromisoformat(token.get("expires_at", ""))
        except ValueError:
            raise DashboardError("Reset token is malformed. Request a new one.")
        if datetime.now() > expires:
            cfg.pop("reset_token", None)
            _save_admin_config(cfg)
            raise DashboardError("Reset code has expired. Request a new one.")
        code = (str(params.get("code") or "")).strip()
        new_pin = _validate_pin(str(params.get("new_pin") or ""))
        if not hmac.compare_digest(_hash_pin(code, cfg.get("salt", "")), token["code_hash"]):
            raise DashboardError("Incorrect reset code.")
        cfg["pin_hash"] = _hash_pin(new_pin, cfg["salt"])
        cfg.pop("reset_token", None)
        _save_admin_config(cfg)
        return {
            "ok": True,
            "exit_code": 0,
            "command": "admin-reset-pin",
            "stdout": "PIN reset successfully.",
            "stderr": "",
            "log": "",
        }

    raise DashboardError(f"Unknown admin action: {action_id}")


DEFAULT_MEETING_TYPES = ["table", "progress", "collaborator"]
MEETING_TYPES_FILE = ROOT / "_system" / "admin" / "meeting_types.json"


def _load_meeting_types() -> list[str]:
    if not MEETING_TYPES_FILE.exists():
        return list(DEFAULT_MEETING_TYPES)
    try:
        data = json.loads(MEETING_TYPES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(t).strip() for t in data if str(t).strip()]
    except (OSError, json.JSONDecodeError):
        pass
    return list(DEFAULT_MEETING_TYPES)


def _save_meeting_types(types: list[str]) -> None:
    MEETING_TYPES_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEETING_TYPES_FILE.write_text(json.dumps(types, indent=2), encoding="utf-8")


def _build_ics(meeting: dict) -> str:
    """Build a minimal RFC-5545 VCALENDAR/VEVENT string."""
    def _ics_dt(dt_str: str) -> str:
        # Accepts ISO 8601 local time; emit floating local time (no Z).
        d = datetime.fromisoformat(dt_str)
        return d.strftime("%Y%m%dT%H%M%S")
    def _esc(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    start = _ics_dt(meeting["datetime"])
    duration_min = int(meeting.get("duration_minutes") or 60)
    end_dt = datetime.fromisoformat(meeting["datetime"]) + timedelta(minutes=duration_min)
    end = end_dt.strftime("%Y%m%dT%H%M%S")
    uid = meeting["uid"]
    summary = f"[{meeting['type']}] {meeting['title']}"
    desc = (meeting.get("agenda") or "").strip()
    location = (meeting.get("location") or "").strip()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LLM-Wiki Dashboard//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{_esc(summary)}",
    ]
    if desc:
        lines.append(f"DESCRIPTION:{_esc(desc)}")
    if location:
        lines.append(f"LOCATION:{_esc(location)}")
    for att in meeting.get("attendees", []):
        email = (att.get("email") or "").strip()
        name = (att.get("name") or "").strip()
        if email:
            cn = f';CN="{_esc(name)}"' if name else ""
            lines.append(f"ATTENDEE{cn};RSVP=TRUE:MAILTO:{email}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def _calendar_app_add(meeting: dict) -> tuple[bool, str]:
    """Add the event to the default macOS Calendar via AppleScript. Returns (ok, message)."""
    try:
        start = datetime.fromisoformat(meeting["datetime"])
    except ValueError:
        return False, "Invalid datetime."
    duration_min = int(meeting.get("duration_minutes") or 60)
    end = start + timedelta(minutes=duration_min)
    summary = f"[{meeting['type']}] {meeting['title']}".replace('"', '\\"')
    desc = (meeting.get("agenda") or "").replace('"', '\\"').replace("\n", "\\n")
    location = (meeting.get("location") or "").replace('"', '\\"')
    fmt = "%Y-%m-%dT%H:%M:%S"
    script = f'''
on iso_to_date(iso)
  set y to text 1 thru 4 of iso as integer
  set mo to text 6 thru 7 of iso as integer
  set d to text 9 thru 10 of iso as integer
  set h to text 12 thru 13 of iso as integer
  set mi to text 15 thru 16 of iso as integer
  set s to text 18 thru 19 of iso as integer
  set theDate to current date
  set year of theDate to y
  set month of theDate to mo
  set day of theDate to d
  set hours of theDate to h
  set minutes of theDate to mi
  set seconds of theDate to s
  return theDate
end iso_to_date

tell application "Calendar"
  set defaultCal to first calendar whose writable is true
  tell defaultCal
    make new event with properties {{summary:"{summary}", start date:my iso_to_date("{start.strftime(fmt)}"), end date:my iso_to_date("{end.strftime(fmt)}"), description:"{desc}", location:"{location}"}}
  end tell
end tell
'''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out."
    if res.returncode != 0:
        return False, f"AppleScript failed: {res.stderr.strip() or res.stdout.strip()}"
    return True, "Event added to Calendar.app."


BUCKET_DEFS = {
    "candidate_jsons": {
        "label": "Candidate JSONs",
        "kind": "files",
        "root": "candidates",
        "glob": "**/*.json",
        "exclude_names": {"_consolidated.json"},
    },
    "triage_reports": {
        "label": "Triage reports",
        "kind": "files",
        "root": "triage-reports",
        "glob": "**/*.md",
    },
    "approval_boards": {
        "label": "Approval boards",
        "kind": "files",
        "root": "triage-reports",
        "glob": "*_approval-board.html",
    },
    "draft_files": {
        "label": "Draft files",
        "kind": "files",
        "root": "drafts",
        "glob": "*.md",
        "exclude_suffixes": (".draft_claim_log.md",),
        "alt_roots": ["Drafts"],
    },
    "claim_logs": {
        "label": "Claim logs",
        "kind": "files",
        "root": "drafts",
        "glob": "*.draft_claim_log.md",
        "alt_roots": ["Drafts"],
    },
    "candidate_batches": {
        "label": "Candidate batches",
        "kind": "dirs",
        "root": "candidates",
    },
    "notes": {
        "label": "Notes",
        "kind": "files",
        "root": "notes",
        "glob": "*.md",
    },
    "data_updates": {
        "label": "Data updates",
        "kind": "files",
        "root": "data-updates",
        "glob": "*.md",
    },
    "critique_reports": {
        "label": "Critique reports",
        "kind": "files",
        "root": "critiques",
        "glob": "**/*.md",
    },
    "figure_rows": {
        "label": "Figure plan",
        "kind": "single_file",
        "root": "figure-plan.md",
    },
    "meetings": {
        "label": "Meetings",
        "kind": "files",
        "root": "meetings",
        "glob": "*.md",
    },
}


def _list_bucket(project: Path, bucket_key: str) -> dict:
    spec = BUCKET_DEFS.get(bucket_key)
    if not spec:
        raise DashboardError(f"Unknown bucket: {bucket_key!r}")
    kind = spec["kind"]
    items: list[dict] = []
    if kind == "single_file":
        target = project / spec["root"]
        if target.exists():
            items.append({
                "name": target.name,
                "rel_path": str(target.relative_to(ROOT)),
                "kind": "file",
                "mtime": iso_local_ts(target.stat().st_mtime),
            })
        return {"bucket": bucket_key, "label": spec["label"], "items": items}
    roots = [project / spec["root"]] + [project / r for r in spec.get("alt_roots", [])]
    exclude_names = set(spec.get("exclude_names", set()))
    exclude_suffixes = tuple(spec.get("exclude_suffixes", ()))
    if kind == "dirs":
        for root in roots:
            if not root.exists():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                file_count = sum(1 for _ in child.rglob("*") if _.is_file())
                items.append({
                    "name": child.name,
                    "rel_path": str(child.relative_to(ROOT)),
                    "kind": "dir",
                    "file_count": file_count,
                    "mtime": iso_local_ts(child.stat().st_mtime),
                })
        return {"bucket": bucket_key, "label": spec["label"], "items": items}
    # files
    glob = spec.get("glob", "**/*")
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob(glob)):
            if not path.is_file():
                continue
            if path.name in exclude_names:
                continue
            if exclude_suffixes and path.name.endswith(exclude_suffixes):
                continue
            items.append({
                "name": path.name,
                "rel_path": str(path.relative_to(ROOT)),
                "kind": "file",
                "size": path.stat().st_size,
                "mtime": iso_local_ts(path.stat().st_mtime),
            })
    return {"bucket": bucket_key, "label": spec["label"], "items": items}


def iso_local_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _parse_figure_plan(path: Path) -> list[dict]:
    """Parse the markdown table in figure-plan.md and return its rows."""
    if not path.exists():
        return []
    header: list[str] | None = None
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower().replace("/", "_").replace(" ", "_") for c in cells]
            continue
        row = {header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))}
        if any(row.values()):
            rows.append(row)
    return rows


def _slug_fragment(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return text or "x"


def _figure_tag(figure: str, panel: str) -> str:
    """Build the filename prefix from figure/panel.

    Examples:
      ('Fig 1', 'A')      -> 'fig-1A'
      ('Fig 2', '')       -> 'fig-2'
      ('prelim', '')      -> 'prelim'
      ('', '')            -> 'unspecified'
    """
    f = (figure or "").strip().lower()
    p = (panel or "").strip()
    if not f:
        return "unspecified"
    if "prelim" in f:
        return "prelim"
    m = re.search(r"(\d+)", f)
    if m:
        return f"fig-{m.group(1)}{p.upper()}"
    return _slug_fragment(f)


def _gdrive_path_for_project(project: Path) -> str:
    """Return the gdrive_path frontmatter value, or '' if unset."""
    brief = project / "Project_Brief.md"
    if not brief.exists():
        return ""
    try:
        import yaml
        raw = brief.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            return ""
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return ""
        fm = yaml.safe_load(parts[1]) or {}
        return str(fm.get("gdrive_path") or "").strip()
    except Exception:
        return ""


def _llm_pm_folder(project: Path) -> Path:
    gp = _gdrive_path_for_project(project)
    if not gp:
        raise DashboardError(
            "Project has no `gdrive_path` set. Configure it first (Set Google Drive path)."
        )
    base = Path(gp).expanduser()
    if not base.exists():
        raise DashboardError(f"gdrive_path does not exist on disk: {base}")
    target = base / "LLM_project_manager"
    target.mkdir(parents=True, exist_ok=True)
    (target / "archive").mkdir(exist_ok=True)
    return target


def _append_changelog(folder: Path, line: str) -> None:
    cl = folder / "CHANGELOG.md"
    header = ""
    if not cl.exists():
        header = (
            "# LLM_project_manager — CHANGELOG\n\n"
            "Append-only log of data files managed via the dashboard. "
            "Do not edit past entries; reassignments and replacements add new lines.\n\n"
        )
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with cl.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.write(f"- {stamp}  {line}\n")


def _canonical_filename(folder: Path, tag: str, brief: str, suffix: str) -> Path:
    """Build a non-clobbering canonical filename: {tag}_{brief}[-N]{suffix}."""
    brief_slug = _slug_fragment(brief) or "data"
    base = f"{tag}_{brief_slug}"
    candidate = folder / f"{base}{suffix}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{base}-{n}{suffix}"
        n += 1
    return candidate


def _archive_file(folder: Path, src: Path, reason: str) -> Path:
    """Compress `src` (which lives inside folder) into folder/archive/{name}_{ts}.zip and delete src."""
    import zipfile
    archive_dir = folder / "archive"
    archive_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = archive_dir / f"{src.stem}_{ts}.zip"
    n = 2
    while zip_path.exists():
        zip_path = archive_dir / f"{src.stem}_{ts}-{n}.zip"
        n += 1
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(src, arcname=src.name)
        zf.writestr("_archive_meta.txt", f"original: {src.name}\nreason: {reason}\narchived_at: {datetime.now().isoformat(timespec='seconds')}\n")
    src.unlink()
    return zip_path


def _update_figure_plan_status(plan_path: Path, figure: str, panel: str, new_status: str) -> bool:
    """Set the Status cell for a matching `Figure/Panel` row. Returns True if changed."""
    if not plan_path.exists() or not new_status:
        return False
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    header: list[str] | None = None
    fig_idx = status_idx = -1
    target = f"{figure} {panel}".strip().lower() if panel else (figure or "").strip().lower()
    target_alt = (f"{figure}{panel}".strip().lower()) if panel else target
    changed = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            for j, h in enumerate(header):
                if "figure" in h:
                    fig_idx = j
                if "status" in h:
                    status_idx = j
            continue
        if fig_idx < 0 or status_idx < 0 or fig_idx >= len(cells) or status_idx >= len(cells):
            continue
        cell = cells[fig_idx].strip().lower().replace(" ", "")
        norm_target = target.replace(" ", "")
        if cell == norm_target or cell == target_alt.replace(" ", ""):
            cells[status_idx] = new_status
            lines[i] = "| " + " | ".join(cells) + " |"
            changed = True
            break
    if changed:
        plan_path.write_text("\n".join(lines) + ("\n" if not plan_path.read_text(encoding="utf-8").endswith("\n") else ""), encoding="utf-8")
    return changed


def _require_admin_unlocked(params: dict) -> None:
    """Verify the caller has admin privileges via PIN."""
    cfg = _load_admin_config()
    if not cfg.get("pin_hash"):
        raise DashboardError("Admin PIN is not configured. Open the dashboard and set it up first.")
    pin = (params or {}).get("admin_pin")
    if not pin:
        raise DashboardError("Admin PIN required.")
    pin = _validate_pin(str(pin))
    if not hmac.compare_digest(_hash_pin(pin, cfg.get("salt", "")), cfg.get("pin_hash", "")):
        raise DashboardError("Incorrect admin PIN.")


def handle_action(action_id: str, project_slug: str | None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    params = params or {}

    # ---- Admin (PIN) actions ----
    if action_id.startswith("admin-"):
        return handle_admin_action(action_id, params)

    # ---- Homework actions ----
    if action_id.startswith("homework-"):
        return handle_homework_action(action_id, params)

    # ---- Backup actions ----
    if action_id.startswith("backup-"):
        return handle_backup_action(action_id, params)

    # ---- Duplicate check ----
    if action_id == "check-duplicates":
        candidates_rel = str(params.get("candidates_dir") or "").strip()
        if not candidates_rel:
            raise DashboardError("Missing candidates_dir for check-duplicates.")
        candidates_dir = ensure_inside_root(ROOT / candidates_rel)
        if not candidates_dir.exists():
            raise DashboardError(f"Candidates directory not found: {candidates_rel}")
        return run_process(
            [sys.executable, "scripts/check_duplicates.py",
             "--candidates", str(candidates_dir)],
            timeout=60,
        )

    # ---- Project scout (for confidential projects — keywords only, output to scouts/) ----
    if action_id == "project-scout":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        keywords = str(params.get("keywords") or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug for project-scout.")
        if not keywords:
            raise DashboardError("Missing keywords for project-scout. Provide topic keywords.")
        # Output goes to scouts/project-{slug}/ (public area — cloud can triage)
        scout_out_dir = ROOT / "scouts" / f"project-{slug_val}" / "candidates" / today
        scout_out_dir.mkdir(parents=True, exist_ok=True)
        return run_process(
            [sys.executable, "scripts/scout_all.py",
             "--topic", keywords,
             "--out", str(scout_out_dir)],
            timeout=900,
        )

    if action_id == "rebuild-dashboard":
        result = rebuild_dashboard()
        result["reload_suggested"] = result["ok"]
        return result

    # ---- List files inside a project bucket ----
    if action_id == "list-bucket-files":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        bucket = str(params.get("bucket") or "").strip()
        if not slug_val or not bucket:
            raise DashboardError("Missing project_slug or bucket.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        result = _list_bucket(project, bucket)
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"list-bucket-files {slug_val}/{bucket}",
            "stdout": json.dumps(result),
            "stderr": "",
            "log": "",
        }

    # ---- Open a file or folder by its repo-relative path ----
    if action_id == "open-relative-path":
        rel = str(params.get("rel_path") or "").strip()
        if not rel:
            raise DashboardError("Missing rel_path.")
        target = ensure_inside_root(ROOT / rel)
        if not target.exists():
            raise DashboardError(f"Path not found: {rel}")
        return open_path(target)

    # ---- List figures parsed from figure-plan.md + existing data-updates ----
    if action_id == "list-project-figures":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        figures = _parse_figure_plan(project / "figure-plan.md")
        updates_dir = project / "data-updates"
        updates: list[dict] = []
        if updates_dir.exists():
            for path in sorted(updates_dir.glob("*.md")):
                fm = {}
                try:
                    text_block = path.read_text(encoding="utf-8")
                    if text_block.startswith("---"):
                        parts = text_block.split("---", 2)
                        if len(parts) >= 3:
                            import yaml
                            fm = yaml.safe_load(parts[1]) or {}
                except Exception:
                    fm = {}
                updates.append({
                    "name": path.name,
                    "rel_path": str(path.relative_to(ROOT)),
                    "figure": str(fm.get("figure") or ""),
                    "panel": str(fm.get("panel") or ""),
                    "status": str(fm.get("status") or ""),
                    "date": str(fm.get("date") or ""),
                    "data_path": str(fm.get("data_path") or ""),
                })
        brief = project / "Project_Brief.md"
        gdrive_path = ""
        if brief.exists():
            import yaml
            raw = brief.read_text(encoding="utf-8")
            if raw.startswith("---"):
                try:
                    fm_parts = raw.split("---", 2)
                    fm_data = yaml.safe_load(fm_parts[1]) or {}
                    gdrive_path = str(fm_data.get("gdrive_path") or "")
                except Exception:
                    gdrive_path = ""
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"list-project-figures {slug_val}",
            "stdout": json.dumps({
                "figures": figures,
                "updates": updates,
                "gdrive_path": gdrive_path,
            }),
            "stderr": "",
            "log": "",
        }

    # ---- Native file/folder picker (macOS osascript) ----
    if action_id == "pick-data-path":
        kind = str(params.get("kind") or "file").strip()  # "file" or "folder"
        default_dir = str(params.get("default_dir") or "").strip()
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if slug_val:
            slug_val = require_simple_slug(slug_val, "project_slug")
            project = project_path(slug_val)
            if not default_dir:
                gp = _gdrive_path_for_project(project)
                if gp:
                    pm = Path(gp).expanduser() / "LLM_project_manager"
                    default_dir = str(pm if pm.exists() else Path(gp).expanduser())
        if not default_dir:
            default_dir = str(Path.home())
        default_dir_q = default_dir.replace('"', '\\"')
        if kind == "folder":
            osascript = f'POSIX path of (choose folder with prompt "Select folder" default location POSIX file "{default_dir_q}")'
        else:
            osascript = f'POSIX path of (choose file with prompt "Select data file" default location POSIX file "{default_dir_q}")'
        try:
            res = subprocess.run(
                ["osascript", "-e", osascript],
                capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired:
            raise DashboardError("File picker timed out.")
        if res.returncode != 0:
            # User cancelled (returncode 1) or error
            if "User canceled" in (res.stderr or "") or res.returncode == 1:
                return {
                    "ok": True, "exit_code": 0,
                    "command": "pick-data-path (cancelled)",
                    "stdout": json.dumps({"cancelled": True}),
                    "stderr": "", "log": "",
                }
            raise DashboardError(f"Picker failed: {res.stderr.strip() or 'unknown error'}")
        picked = res.stdout.strip()
        return {
            "ok": True, "exit_code": 0,
            "command": f"pick-data-path -> {picked}",
            "stdout": json.dumps({"path": picked, "cancelled": False}),
            "stderr": "", "log": "",
        }

    # ---- Set / update the project's gdrive_path frontmatter ----
    if action_id == "set-project-gdrive-path":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        brief = project / "Project_Brief.md"
        if not brief.exists():
            raise DashboardError("Project_Brief.md not found.")
        new_path = str(params.get("gdrive_path") or "").strip()
        if not new_path:
            raise DashboardError("gdrive_path is empty.")
        if not Path(new_path).expanduser().exists():
            raise DashboardError(f"Path does not exist: {new_path}")
        # Rewrite frontmatter
        raw = brief.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            raise DashboardError("Project_Brief.md has no YAML frontmatter.")
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise DashboardError("Malformed frontmatter.")
        fm_lines = parts[1].splitlines()
        new_lines = [ln for ln in fm_lines if not ln.startswith("gdrive_path:")]
        while new_lines and not new_lines[-1].strip():
            new_lines.pop()
        new_lines.append(f'gdrive_path: "{new_path}"')
        rebuilt = "---\n" + "\n".join(new_lines) + "\n---" + parts[2]
        brief.write_text(rebuilt, encoding="utf-8")
        # Create the LLM_project_manager subfolder and changelog
        pm = Path(new_path).expanduser() / "LLM_project_manager"
        pm.mkdir(parents=True, exist_ok=True)
        (pm / "archive").mkdir(exist_ok=True)
        _append_changelog(pm, f"SETUP  gdrive_path set for project {slug_val}")
        rebuild_dashboard()
        return {
            "ok": True, "exit_code": 0,
            "command": f"set-project-gdrive-path {slug_val}",
            "stdout": f"Set gdrive_path = {new_path}\nCreated: {pm}",
            "stderr": "", "log": "",
            "reload_suggested": True,
        }

    # ---- Bulk renumber figures across all data-updates + figure-plan ----
    if action_id == "renumber-figures":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        raw_mapping = params.get("mapping")
        if not isinstance(raw_mapping, dict) or not raw_mapping:
            raise DashboardError("`mapping` must be a non-empty object like {'Fig 1': 'Fig 2'}.")
        mapping = {str(k).strip(): str(v).strip() for k, v in raw_mapping.items() if str(k).strip() and str(v).strip()}
        reason = str(params.get("reason") or "").strip() or "bulk renumber"
        pm_folder = _llm_pm_folder(project)
        # Pass 1: update .md frontmatter + collect file renames using temp suffix
        import yaml
        updates_dir = project / "data-updates"
        renames: list[tuple[Path, Path]] = []
        affected: list[str] = []
        if updates_dir.exists():
            for md_path in sorted(updates_dir.glob("*.md")):
                raw = md_path.read_text(encoding="utf-8")
                if not raw.startswith("---"):
                    continue
                parts = raw.split("---", 2)
                fm = yaml.safe_load(parts[1]) or {}
                fig = str(fm.get("figure") or "").strip()
                panel = str(fm.get("panel") or "").strip()
                if fig not in mapping:
                    continue
                old_tag = _figure_tag(fig, panel)
                new_fig = mapping[fig]
                new_tag = _figure_tag(new_fig, panel)
                fm["figure"] = new_fig
                old_path_str = str(fm.get("data_path") or "")
                if old_path_str:
                    old_file = Path(old_path_str).expanduser()
                    if old_file.exists() and old_file.parent.resolve() == pm_folder.resolve():
                        stem = old_file.stem
                        brief_slug = stem.split("_", 1)[1] if "_" in stem else stem
                        temp_name = pm_folder / f".__renumber_tmp_{md_path.stem}{old_file.suffix}"
                        old_file.rename(temp_name)
                        final = _canonical_filename(pm_folder, new_tag, brief_slug, old_file.suffix)
                        renames.append((temp_name, final))
                        fm["data_path"] = str(final)
                new_fm_text = "\n".join(
                    f"{k}: {json.dumps(v, ensure_ascii=False)}" if isinstance(v, str) else f"{k}: {v}"
                    for k, v in fm.items()
                )
                md_path.write_text("---\n" + new_fm_text + "\n---" + parts[2], encoding="utf-8")
                affected.append(f"{md_path.name}: \"{fig}\" → \"{new_fig}\"")
        # Pass 2: rename temp files to final names
        for tmp, final in renames:
            tmp.rename(final)
        # Update figure-plan.md
        plan = project / "figure-plan.md"
        plan_changes = 0
        if plan.exists():
            lines = plan.read_text(encoding="utf-8").splitlines()
            header: list[str] | None = None
            fig_idx = -1
            for i, raw_line in enumerate(lines):
                stripped = raw_line.strip()
                if not stripped.startswith("|"):
                    continue
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                    continue
                if header is None:
                    header = [c.lower() for c in cells]
                    for j, h in enumerate(header):
                        if "figure" in h:
                            fig_idx = j; break
                    continue
                if fig_idx < 0 or fig_idx >= len(cells):
                    continue
                cell = cells[fig_idx]
                for old_fig, new_fig in mapping.items():
                    if cell.lower().startswith(old_fig.lower()):
                        cells[fig_idx] = new_fig + cell[len(old_fig):]
                        lines[i] = "| " + " | ".join(cells) + " |"
                        plan_changes += 1
                        break
            if plan_changes:
                plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # CHANGELOG
        for line in affected:
            _append_changelog(pm_folder, f"RENUMBER  {line}  reason: \"{reason}\"")
        if plan_changes:
            _append_changelog(pm_folder, f"RENUMBER  figure-plan.md: {plan_changes} row(s) updated")
        rebuild_dashboard()
        return {
            "ok": True, "exit_code": 0,
            "command": f"renumber-figures {slug_val}",
            "stdout": json.dumps({
                "data_updates_changed": len(affected),
                "figure_plan_rows_changed": plan_changes,
                "affected": affected,
            }),
            "stderr": "", "log": "",
            "reload_suggested": True,
        }

    # ---- List archived data zips for a project ----
    if action_id == "list-archive":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        try:
            pm_folder = _llm_pm_folder(project)
        except DashboardError:
            return {
                "ok": True, "exit_code": 0,
                "command": "list-archive (no gdrive_path)",
                "stdout": json.dumps({"items": [], "configured": False}),
                "stderr": "", "log": "",
            }
        archive_dir = pm_folder / "archive"
        items = []
        if archive_dir.exists():
            for z in sorted(archive_dir.glob("*.zip"), reverse=True):
                items.append({
                    "name": z.name,
                    "abs_path": str(z),
                    "size": z.stat().st_size,
                    "mtime": iso_local_ts(z.stat().st_mtime),
                })
        return {
            "ok": True, "exit_code": 0,
            "command": f"list-archive {slug_val}",
            "stdout": json.dumps({"items": items, "configured": True}),
            "stderr": "", "log": "",
        }

    # ---- Restore an archived data file back to LLM_project_manager/ ----
    if action_id == "restore-archive":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        abs_zip = str(params.get("zip_path") or "").strip()
        if not (slug_val and abs_zip):
            raise DashboardError("Missing project_slug or zip_path.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        pm_folder = _llm_pm_folder(project)
        zip_path = Path(abs_zip).expanduser()
        if not zip_path.exists() or not zip_path.is_file():
            raise DashboardError(f"Archive not found: {abs_zip}")
        if zip_path.parent.resolve() != (pm_folder / "archive").resolve():
            raise DashboardError("Refusing to restore a zip outside this project's archive folder.")
        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [n for n in zf.namelist() if n != "_archive_meta.txt"]
            if not names:
                raise DashboardError("Archive is empty.")
            inner = names[0]
            target = pm_folder / inner
            if target.exists():
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                stem = Path(inner).stem
                suffix = Path(inner).suffix
                target = pm_folder / f"{stem}_restored_{ts}{suffix}"
            with zf.open(inner) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
        _append_changelog(pm_folder, f"RESTORE  {target.name}  from archive {zip_path.name}")
        return {
            "ok": True, "exit_code": 0,
            "command": f"restore-archive {zip_path.name}",
            "stdout": json.dumps({
                "restored_path": str(target),
                "name": target.name,
            }),
            "stderr": "", "log": "",
        }

    # ---- Meeting types config ----
    if action_id == "list-meeting-types":
        return {
            "ok": True, "exit_code": 0,
            "command": "list-meeting-types",
            "stdout": json.dumps({"types": _load_meeting_types()}),
            "stderr": "", "log": "",
        }
    if action_id == "add-meeting-type":
        name = str(params.get("name") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", name):
            raise DashboardError("Meeting type must be 2–32 chars (letters, digits, _, -).")
        types = _load_meeting_types()
        if name in types:
            return {
                "ok": True, "exit_code": 0,
                "command": f"add-meeting-type {name}",
                "stdout": json.dumps({"types": types, "added": False}),
                "stderr": "", "log": "",
            }
        types.append(name)
        _save_meeting_types(types)
        return {
            "ok": True, "exit_code": 0,
            "command": f"add-meeting-type {name}",
            "stdout": json.dumps({"types": types, "added": True}),
            "stderr": "", "log": "",
        }

    # ---- Create a new meeting (writes .md + .ics, adds to macOS Calendar) ----
    if action_id == "create-meeting":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        meeting_type = str(params.get("type") or "").strip()
        title = str(params.get("title") or "").strip() or f"{meeting_type} meeting"
        datetime_str = str(params.get("datetime") or "").strip()
        duration = int(params.get("duration_minutes") or 60)
        location = str(params.get("location") or "").strip()
        agenda = str(params.get("agenda") or "").strip()
        attendees_in = params.get("attendees") or []
        add_to_calendar = bool(params.get("add_to_calendar"))
        if meeting_type not in _load_meeting_types():
            raise DashboardError(f"Unknown meeting type: {meeting_type!r}. Add it first.")
        try:
            dt_obj = datetime.fromisoformat(datetime_str)
        except ValueError:
            raise DashboardError("Invalid datetime (expected ISO format like 2026-06-01T14:00).")
        if duration < 5 or duration > 24 * 60:
            raise DashboardError("Duration must be 5–1440 minutes.")
        attendees: list[dict] = []
        if isinstance(attendees_in, list):
            for a in attendees_in:
                if not isinstance(a, dict):
                    continue
                name = str(a.get("name") or "").strip()
                email = str(a.get("email") or "").strip()
                if not (name or email):
                    continue
                if email and ("@" not in email or " " in email):
                    raise DashboardError(f"Invalid attendee email: {email!r}")
                attendees.append({"name": name or email, "email": email})
        meetings_dir = project / "meetings"
        meetings_dir.mkdir(parents=True, exist_ok=True)
        date_part = dt_obj.strftime("%Y-%m-%d-%H%M")
        stem_base = f"{date_part}-{meeting_type}-{_slug_fragment(title)}"
        stem = stem_base
        n = 2
        while (meetings_dir / f"{stem}.md").exists():
            stem = f"{stem_base}-{n}"
            n += 1
        md_path = meetings_dir / f"{stem}.md"
        ics_path = meetings_dir / f"{stem}.ics"
        uid = f"{stem}-{secrets.token_hex(4)}@llm-wiki.local"
        def _yaml_str(s: str) -> str:
            return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
        attendees_yaml = ""
        if attendees:
            attendees_yaml = "attendees:\n" + "".join(
                f"  - name: {_yaml_str(a['name'])}\n    email: {_yaml_str(a['email'])}\n"
                for a in attendees
            )
        body = (
            "---\n"
            f"type: {meeting_type}\n"
            f"title: {_yaml_str(title)}\n"
            f"datetime: {dt_obj.isoformat(timespec='minutes')}\n"
            f"duration_minutes: {duration}\n"
            f"location: {_yaml_str(location)}\n"
            f"uid: {uid}\n"
            f"project_slug: {slug_val}\n"
            f"{attendees_yaml}"
            f"ics_path: {_yaml_str(str(ics_path.relative_to(ROOT)))}\n"
            "confidential_tier: local-only\n"
            "---\n\n"
            f"# {title}\n\n"
            f"_Type:_ **{meeting_type}**  ·  _When:_ {dt_obj.strftime('%Y-%m-%d %H:%M')}  ·  _Duration:_ {duration} min"
            f"{('  ·  _Where:_ ' + location) if location else ''}\n\n"
            "## Agenda\n\n"
            f"{agenda or '_(none provided)_'}\n\n"
            "## Notes (history — append-only)\n\n"
            "_No notes yet. Use \"+ Add note\" from the dashboard._\n"
        )
        md_path.write_text(body, encoding="utf-8")
        meeting_obj = {
            "uid": uid,
            "type": meeting_type,
            "title": title,
            "datetime": dt_obj.isoformat(timespec="seconds"),
            "duration_minutes": duration,
            "location": location,
            "agenda": agenda,
            "attendees": attendees,
        }
        ics_path.write_text(_build_ics(meeting_obj), encoding="utf-8")
        cal_ok, cal_msg = (False, "Skipped (add_to_calendar=False)")
        if add_to_calendar:
            cal_ok, cal_msg = _calendar_app_add(meeting_obj)
        # Build a mailto URL the UI can open (with .ics attached only manually — mailto can't attach).
        recipients = ",".join(a["email"] for a in attendees if a.get("email"))
        mail_subject = f"[{meeting_type}] {title} — {dt_obj.strftime('%Y-%m-%d %H:%M')}"
        mail_body_parts = [
            f"Meeting: {title}",
            f"Type: {meeting_type}",
            f"When: {dt_obj.strftime('%Y-%m-%d %H:%M')} ({duration} min)",
        ]
        if location:
            mail_body_parts.append(f"Where: {location}")
        if agenda:
            mail_body_parts.append("")
            mail_body_parts.append("Agenda:")
            mail_body_parts.append(agenda)
        mail_body_parts += ["", f"Calendar invite (.ics) attached separately: {ics_path.name}"]
        mailto = ""
        if recipients:
            from urllib.parse import quote
            mailto = f"mailto:{recipients}?subject={quote(mail_subject)}&body={quote(chr(10).join(mail_body_parts))}"
        rebuild_dashboard()
        return {
            "ok": True, "exit_code": 0,
            "command": f"create-meeting {slug_val}/{stem}",
            "stdout": json.dumps({
                "rel_path": str(md_path.relative_to(ROOT)),
                "ics_rel_path": str(ics_path.relative_to(ROOT)),
                "calendar_added": cal_ok,
                "calendar_message": cal_msg,
                "mailto_url": mailto,
            }),
            "stderr": "", "log": "",
            "reload_suggested": True,
        }

    # ---- List meetings for a project ----
    if action_id == "list-meetings":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        meetings_dir = project / "meetings"
        items = []
        if meetings_dir.exists():
            import yaml
            for md_path in sorted(meetings_dir.glob("*.md")):
                try:
                    raw = md_path.read_text(encoding="utf-8")
                    fm = {}
                    if raw.startswith("---"):
                        parts = raw.split("---", 2)
                        if len(parts) >= 3:
                            fm = yaml.safe_load(parts[1]) or {}
                    items.append({
                        "name": md_path.name,
                        "rel_path": str(md_path.relative_to(ROOT)),
                        "type": str(fm.get("type") or ""),
                        "title": str(fm.get("title") or ""),
                        "datetime": str(fm.get("datetime") or ""),
                        "duration_minutes": int(fm.get("duration_minutes") or 60),
                        "location": str(fm.get("location") or ""),
                        "attendees": fm.get("attendees") or [],
                        "ics_rel_path": str(fm.get("ics_path") or ""),
                    })
                except Exception:
                    continue
        items.sort(key=lambda m: m["datetime"], reverse=True)
        return {
            "ok": True, "exit_code": 0,
            "command": f"list-meetings {slug_val}",
            "stdout": json.dumps({"items": items}),
            "stderr": "", "log": "",
        }

    # ---- Add a note to an existing meeting (append-only history) ----
    if action_id == "add-meeting-note":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        rel = str(params.get("meeting_rel_path") or "").strip()
        note_text = str(params.get("note") or "").strip()
        author = str(params.get("author") or "").strip()
        if not (slug_val and rel and note_text):
            raise DashboardError("Missing project_slug, meeting_rel_path, or note.")
        md_path = ensure_inside_root(ROOT / rel)
        if not md_path.exists():
            raise DashboardError(f"Meeting file not found: {rel}")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        section = f"\n\n### Note — {stamp}{(' (' + author + ')') if author else ''}\n\n{note_text}\n"
        with md_path.open("a", encoding="utf-8") as fh:
            fh.write(section)
        return {
            "ok": True, "exit_code": 0,
            "command": f"add-meeting-note {md_path.name}",
            "stdout": json.dumps({"rel_path": str(md_path.relative_to(ROOT)), "appended_at": stamp}),
            "stderr": "", "log": "",
            "reload_suggested": True,
        }

    # ---- List sync proposals (Phase 3) ----
    if action_id == "list-sync-proposals":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        spd = project / "sync-proposals"
        items = []
        if spd.exists():
            for md_path in sorted(spd.glob("*.md"), reverse=True):
                kind = "data-sync" if md_path.name.startswith("data-sync") else (
                    "meeting-sync" if md_path.name.startswith("meeting-sync") else "other")
                # Try to extract the JSON block
                raw = md_path.read_text(encoding="utf-8")
                actions_parsed = []
                m = re.search(r"```json\s*(\[[\s\S]*?\])\s*```", raw)
                if m:
                    try:
                        actions_parsed = json.loads(m.group(1))
                    except json.JSONDecodeError:
                        actions_parsed = []
                items.append({
                    "name": md_path.name,
                    "rel_path": str(md_path.relative_to(ROOT)),
                    "kind": kind,
                    "mtime": iso_local_ts(md_path.stat().st_mtime),
                    "action_count": len(actions_parsed) if isinstance(actions_parsed, list) else 0,
                    "actions": actions_parsed if isinstance(actions_parsed, list) else [],
                })
        return {
            "ok": True, "exit_code": 0,
            "command": f"list-sync-proposals {slug_val}",
            "stdout": json.dumps({"items": items}),
            "stderr": "", "log": "",
        }

    # ---- Apply selected items from a sync proposal ----
    if action_id == "apply-sync-proposal":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        rel = str(params.get("proposal_rel_path") or "").strip()
        selected_ids = params.get("selected_ids") or []
        if not (slug_val and rel and isinstance(selected_ids, list) and selected_ids):
            raise DashboardError("Missing project_slug, proposal_rel_path, or selected_ids.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        proposal_path = ensure_inside_root(ROOT / rel)
        if not proposal_path.exists():
            raise DashboardError(f"Proposal not found: {rel}")
        raw = proposal_path.read_text(encoding="utf-8")
        m = re.search(r"```json\s*(\[[\s\S]*?\])\s*```", raw)
        if not m:
            raise DashboardError("No JSON block in proposal.")
        try:
            all_items = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            raise DashboardError(f"Malformed JSON in proposal: {exc}")
        selected = [a for a in all_items if a.get("id") in selected_ids]
        if not selected:
            raise DashboardError("Selected items not found in proposal.")
        applied: list[str] = []
        skipped: list[str] = []
        today = datetime.now().strftime("%Y-%m-%d")
        figure_plan = project / "figure-plan.md"
        exp_roadmap = project / "experiment-roadmap.md"
        decision_log = project / "Decision_Log.md"
        for action in selected:
            kind = str(action.get("action") or "")
            aid = str(action.get("id") or "?")
            try:
                if kind == "figure_plan_status_update":
                    changed = _update_figure_plan_status(
                        figure_plan, str(action.get("figure") or ""),
                        str(action.get("panel") or ""), str(action.get("new_status") or ""),
                    )
                    (applied if changed else skipped).append(f"{aid} {kind} (changed={changed})")
                elif kind == "experiment_roadmap_status_update":
                    if not exp_roadmap.exists():
                        skipped.append(f"{aid} {kind} (no experiment-roadmap.md)")
                        continue
                    # Reuse the same row-matcher but for experiment column = first column.
                    target = str(action.get("experiment") or "").strip()
                    new_status = str(action.get("new_status") or "").strip()
                    lines = exp_roadmap.read_text(encoding="utf-8").splitlines()
                    header = None; first_col = -1; status_idx = -1
                    changed_local = False
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        if not stripped.startswith("|"):
                            continue
                        cells = [c.strip() for c in stripped.strip("|").split("|")]
                        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                            continue
                        if header is None:
                            header = [c.lower() for c in cells]
                            first_col = 0
                            for j, h in enumerate(header):
                                if "status" in h: status_idx = j
                            continue
                        if status_idx < 0 or first_col >= len(cells) or status_idx >= len(cells):
                            continue
                        if cells[first_col].lower() == target.lower():
                            cells[status_idx] = new_status
                            lines[i] = "| " + " | ".join(cells) + " |"
                            changed_local = True
                            break
                    if changed_local:
                        exp_roadmap.write_text("\n".join(lines) + "\n", encoding="utf-8")
                        applied.append(f"{aid} {kind}")
                    else:
                        skipped.append(f"{aid} {kind} (no row matched {target!r})")
                elif kind == "decision_log_append":
                    entry = str(action.get("entry") or "").strip()
                    if not entry:
                        skipped.append(f"{aid} {kind} (empty entry)")
                        continue
                    decision_log.parent.mkdir(parents=True, exist_ok=True)
                    if not decision_log.exists():
                        decision_log.write_text("---\nconfidential_tier: local-only\n---\n\n# Decision Log\n\n", encoding="utf-8")
                    with decision_log.open("a", encoding="utf-8") as fh:
                        fh.write(f"- **{today}** — {entry}  _(from sync proposal {proposal_path.name}, id {aid})_\n")
                    applied.append(f"{aid} {kind}")
                elif kind == "figure_plan_add_row":
                    if not figure_plan.exists():
                        skipped.append(f"{aid} {kind} (no figure-plan.md)")
                        continue
                    fig = str(action.get("figure") or "").strip()
                    panel = str(action.get("panel") or "").strip()
                    claim = str(action.get("claim") or "").strip()
                    row = f"| {fig}{(' ' + panel) if panel else ''} | {claim} |  | planned | unknown |  |  |"
                    with figure_plan.open("a", encoding="utf-8") as fh:
                        fh.write(row + "\n")
                    applied.append(f"{aid} {kind}")
                elif kind == "experiment_roadmap_add_row":
                    if not exp_roadmap.exists():
                        skipped.append(f"{aid} {kind} (no experiment-roadmap.md)")
                        continue
                    exp = str(action.get("experiment") or "").strip()
                    purpose = str(action.get("purpose") or "").strip()
                    row = f"| {exp} | {purpose} | planned |  |  |"
                    with exp_roadmap.open("a", encoding="utf-8") as fh:
                        fh.write(row + "\n")
                    applied.append(f"{aid} {kind}")
                elif kind == "note":
                    skipped.append(f"{aid} note (informational only)")
                else:
                    skipped.append(f"{aid} {kind} (unknown action)")
            except Exception as exc:
                skipped.append(f"{aid} {kind} (error: {exc})")
        # Mark proposal applied: append an "## Applied" section
        with proposal_path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"\n\n## Applied — {datetime.now().isoformat(timespec='seconds')}\n\n"
                f"- Applied: {', '.join(applied) if applied else '_(none)_'}\n"
                f"- Skipped: {', '.join(skipped) if skipped else '_(none)_'}\n"
            )
        rebuild_dashboard()
        return {
            "ok": True, "exit_code": 0,
            "command": f"apply-sync-proposal {proposal_path.name}",
            "stdout": json.dumps({"applied": applied, "skipped": skipped}),
            "stderr": "", "log": "",
            "reload_suggested": True,
        }

    # ---- Reassign a data-update to a different figure/panel ----
    if action_id == "reassign-data-update":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        rel = str(params.get("update_rel_path") or "").strip()
        new_figure = str(params.get("new_figure") or "").strip()
        new_panel = str(params.get("new_panel") or "").strip()
        reason = str(params.get("reason") or "").strip()
        if not (slug_val and rel and new_figure):
            raise DashboardError("Missing project_slug, update_rel_path, or new_figure.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        update_path = ensure_inside_root(ROOT / rel)
        if not update_path.exists():
            raise DashboardError(f"Update file not found: {rel}")
        # Read existing frontmatter
        import yaml
        raw = update_path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            raise DashboardError("Update file has no frontmatter.")
        parts = raw.split("---", 2)
        fm = yaml.safe_load(parts[1]) or {}
        old_fig = str(fm.get("figure") or "")
        old_panel = str(fm.get("panel") or "")
        old_data_path = str(fm.get("data_path") or "")
        # Rename the actual data file if it lives under LLM_project_manager/
        pm = _llm_pm_folder(project)
        new_tag = _figure_tag(new_figure, new_panel)
        new_data_path_str = old_data_path
        renamed_note = ""
        if old_data_path:
            old_file = Path(old_data_path).expanduser()
            if old_file.exists() and old_file.parent.resolve() == pm.resolve():
                # Derive the brief slug from existing filename (strip old tag prefix)
                stem = old_file.stem
                if "_" in stem:
                    brief_slug = stem.split("_", 1)[1]
                else:
                    brief_slug = stem
                new_file = _canonical_filename(pm, new_tag, brief_slug, old_file.suffix)
                old_file.rename(new_file)
                new_data_path_str = str(new_file)
                renamed_note = f"; file renamed {old_file.name} → {new_file.name}"
        fm["figure"] = new_figure
        fm["panel"] = new_panel
        fm["data_path"] = new_data_path_str
        new_fm = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" if isinstance(v, str) else f"{k}: {v}" for k, v in fm.items())
        rebuilt = "---\n" + new_fm + "\n---" + parts[2]
        update_path.write_text(rebuilt, encoding="utf-8")
        # Update figure-plan.md status row? Keep status unchanged. Just log.
        _update_figure_plan_status(project / "figure-plan.md", new_figure, new_panel, str(fm.get("status") or ""))
        _append_changelog(
            pm,
            f"REASSIGN  {update_path.relative_to(ROOT)}  figure: \"{old_fig}/{old_panel}\" → \"{new_figure}/{new_panel}\"  reason: \"{reason}\"{renamed_note}",
        )
        rebuild_dashboard()
        return {
            "ok": True, "exit_code": 0,
            "command": f"reassign-data-update {update_path.name}",
            "stdout": json.dumps({
                "rel_path": str(update_path.relative_to(ROOT)),
                "new_data_path": new_data_path_str,
                "renamed": bool(renamed_note),
            }),
            "stderr": "", "log": "",
            "reload_suggested": True,
        }

    # ---- Append a new data update under projects/{slug}/data-updates/ ----
    if action_id == "add-data-update":
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug for add-data-update.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        if not (project / "Project_Brief.md").exists():
            raise DashboardError(f"Project_Brief.md not found for {slug_val}.")
        figure = str(params.get("figure") or "").strip()
        panel = str(params.get("panel") or "").strip()
        status_val = str(params.get("status") or "").strip()
        brief_desc = str(params.get("brief_description") or "").strip()
        source_file = str(params.get("source_file") or "").strip()
        legend = str(params.get("legend") or "").strip()
        what_changed = str(params.get("what_changed") or "").strip()
        interpretation = str(params.get("interpretation") or "").strip()
        concerns = str(params.get("concerns") or "").strip()
        next_step = str(params.get("next_step") or "").strip()
        mode = str(params.get("mode") or "new").strip()
        existing_update_rel = str(params.get("existing_update_rel_path") or "").strip()
        valid_status = {"planned", "in_progress", "data_collected", "analyzed", "drafted", "complete", "dropped", ""}
        if status_val not in valid_status:
            raise DashboardError(f"Invalid status: {status_val!r}.")
        if not brief_desc:
            raise DashboardError("`brief_description` is required (3–6 words for the filename).")
        # Resolve LLM_project_manager folder (raises if gdrive_path missing)
        pm_folder = _llm_pm_folder(project)
        tag = _figure_tag(figure, panel)
        canonical = None
        archived_zip = None
        # Branch by mode
        if mode == "existing" and existing_update_rel:
            # Replace data file inside an existing data-update record.
            existing_path = ensure_inside_root(ROOT / existing_update_rel)
            if not existing_path.exists():
                raise DashboardError(f"Existing update not found: {existing_update_rel}")
            import yaml
            raw = existing_path.read_text(encoding="utf-8")
            if not raw.startswith("---"):
                raise DashboardError("Existing update has no frontmatter.")
            parts = raw.split("---", 2)
            fm = yaml.safe_load(parts[1]) or {}
            old_data_path = str(fm.get("data_path") or "")
            if not source_file:
                raise DashboardError("source_file is required when replacing an existing data file.")
            src = Path(source_file).expanduser()
            if not src.exists() or not src.is_file():
                raise DashboardError(f"Source file not found: {source_file}")
            # Archive the previous file if it lives under LLM_project_manager/
            if old_data_path:
                old_file = Path(old_data_path).expanduser()
                if old_file.exists() and old_file.parent.resolve() == pm_folder.resolve():
                    archived_zip = _archive_file(pm_folder, old_file, reason=f"replaced via data-update (n+); ref {existing_path.name}")
            # Move new file into canonical location (resolve to figure/panel from the record if user didn't change)
            target_figure = figure or str(fm.get("figure") or "")
            target_panel = panel or str(fm.get("panel") or "")
            tag = _figure_tag(target_figure, target_panel)
            canonical = _canonical_filename(pm_folder, tag, brief_desc, src.suffix)
            shutil.move(str(src), str(canonical))
            # Append a new note section to the existing .md (history within the file)
            today = datetime.now().strftime("%Y-%m-%d %H:%M")
            append_block = (
                f"\n\n## Data Update — {today}\n\n"
                f"- new data file: `{canonical.name}`\n"
                + (f"- previous archived as: `{archived_zip.relative_to(pm_folder)}`\n" if archived_zip else "")
                + (f"- what changed: {what_changed}\n" if what_changed else "")
                + (f"- interpretation: {interpretation}\n" if interpretation else "")
                + (f"- concerns: {concerns}\n" if concerns else "")
                + (f"- next step: {next_step}\n" if next_step else "")
            )
            # Update frontmatter fields
            fm["status"] = status_val or fm.get("status") or "in_progress"
            fm["data_path"] = str(canonical)
            fm["figure"] = target_figure
            fm["panel"] = target_panel
            new_fm_text = "\n".join(
                f"{k}: {json.dumps(v, ensure_ascii=False)}" if isinstance(v, str) else f"{k}: {v}"
                for k, v in fm.items()
            )
            rebuilt = "---\n" + new_fm_text + "\n---" + parts[2].rstrip() + append_block
            existing_path.write_text(rebuilt, encoding="utf-8")
            target_md = existing_path
            _append_changelog(
                pm_folder,
                f"UPDATE   {target_md.relative_to(ROOT)}  data_path → {canonical.name}"
                + (f"  archived: {archived_zip.name}" if archived_zip else ""),
            )
        else:
            # New data update: create a fresh .md, move the source file in.
            if not figure and not status_val.startswith("planned") and not (brief_desc and tag == "prelim"):
                # Allow blank figure → tag = unspecified
                pass
            updates_dir = project / "data-updates"
            updates_dir.mkdir(parents=True, exist_ok=True)
            today_date = datetime.now().strftime("%Y-%m-%d")
            stem_base = f"{today_date}-{tag}_{_slug_fragment(brief_desc)}"
            stem = stem_base
            n = 2
            while (updates_dir / f"{stem}.md").exists():
                stem = f"{stem_base}-{n}"
                n += 1
            target_md = updates_dir / f"{stem}.md"
            if source_file:
                src = Path(source_file).expanduser()
                if not src.exists() or not src.is_file():
                    raise DashboardError(f"Source file not found: {source_file}")
                canonical = _canonical_filename(pm_folder, tag, brief_desc, src.suffix)
                shutil.move(str(src), str(canonical))
            def _yaml_str(s: str) -> str:
                return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
            body = (
                "---\n"
                f"date: {today_date}\n"
                f"project_slug: {slug_val}\n"
                f"figure: {_yaml_str(figure)}\n"
                f"panel: {_yaml_str(panel)}\n"
                f"status: {status_val or 'in_progress'}\n"
                f"brief_description: {_yaml_str(brief_desc)}\n"
                f"data_path: {_yaml_str(str(canonical) if canonical else '')}\n"
                "confidential_tier: local-only\n"
                "---\n\n"
                f"# Data Update: {tag}_{_slug_fragment(brief_desc)}\n\n"
                "## Brief Legend\n\n"
                f"{legend or '_(none provided)_'}\n\n"
                "## What Changed\n\n"
                f"{what_changed or '_(none provided)_'}\n\n"
                "## Current Interpretation\n\n"
                f"{interpretation or '_(none provided)_'}\n\n"
                "## Concerns or Failure Modes\n\n"
                f"{concerns or '_(none provided)_'}\n\n"
                "## Next Step\n\n"
                f"{next_step or '_(none provided)_'}\n"
            )
            target_md.write_text(body, encoding="utf-8")
            _append_changelog(
                pm_folder,
                f"CREATE   {target_md.relative_to(ROOT)}"
                + (f"  data: {canonical.name}" if canonical else "  (no file moved)"),
            )
        plan_updated = False
        if status_val:
            plan_updated = _update_figure_plan_status(project / "figure-plan.md", figure, panel, status_val)
        rebuild_dashboard()
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"add-data-update {slug_val}/{target_md.name}",
            "stdout": json.dumps({
                "rel_path": str(target_md.relative_to(ROOT)),
                "data_file": str(canonical) if canonical else "",
                "archived_zip": str(archived_zip) if archived_zip else "",
                "figure_plan_status_updated": plan_updated,
            }),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    # ---- Update project managers (admin mode, PIN-protected) ----
    if action_id == "update-managers":
        _require_admin_unlocked(params)
        slug_val = str(params.get("project_slug") or project_slug or "").strip()
        if not slug_val:
            raise DashboardError("Missing project_slug for update-managers.")
        slug_val = require_simple_slug(slug_val, "project_slug")
        project = project_path(slug_val)
        brief = project / "Project_Brief.md"
        if not brief.exists():
            raise DashboardError(f"Project_Brief.md not found for {slug_val}.")
        raw_managers = params.get("managers")
        if not isinstance(raw_managers, list):
            raise DashboardError("`managers` must be a list of {name, email} objects.")
        cleaned: list[dict[str, str]] = []
        for entry in raw_managers:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            email = str(entry.get("email") or "").strip()
            if not name and not email:
                continue
            if email and ("@" not in email or " " in email):
                raise DashboardError(f"Invalid email: {email!r}")
            cleaned.append({"name": name or email, "email": email})
        result = _write_managers_frontmatter(brief, cleaned)
        rebuild_dashboard()
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"update-managers {slug_val}",
            "stdout": result,
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    # ---- Create a new confidential project ----
    if action_id == "create-project":
        slug = str(params.get("slug") or "").strip()
        ptype = str(params.get("project_type") or "paper_in_prep").strip()
        title = str(params.get("title") or "Working title").strip()
        valid_types = {"paper_in_prep", "review_article", "grant", "job_application"}
        if not slug:
            raise DashboardError("Missing project slug.")
        slug = require_simple_slug(slug, "project_slug")
        if ptype not in valid_types:
            raise DashboardError(f"Invalid project_type: {ptype!r}. Must be one of: {', '.join(sorted(valid_types))}")
        project_dir = PROJECTS / slug
        if project_dir.exists():
            raise DashboardError(f"Project already exists: projects/{slug}/")
        # Create folder structure
        (project_dir / "Drafts").mkdir(parents=True, exist_ok=True)
        (project_dir / "critiques" / "argue").mkdir(parents=True, exist_ok=True)
        (project_dir / "critiques" / "demon").mkdir(parents=True, exist_ok=True)
        (project_dir / "rejection-sims").mkdir(parents=True, exist_ok=True)
        (project_dir / "notes").mkdir(parents=True, exist_ok=True)
        (project_dir / "data-updates").mkdir(parents=True, exist_ok=True)
        # Write Project_Brief.md from template with type and title pre-filled
        brief_src = TEMPLATES / "Project_Brief.md"
        brief_dst = project_dir / "Project_Brief.md"
        if brief_src.exists():
            brief_content = brief_src.read_text(encoding="utf-8")
            # Patch frontmatter fields
            brief_content = brief_content.replace(
                "project_slug: short-kebab-case-name", f"project_slug: {slug}"
            )
            brief_content = brief_content.replace(
                "project_type: grant | paper_in_prep | review_article",
                f"project_type: {ptype}",
            )
            brief_content = brief_content.replace(
                'title: "Working title"', f'title: "{title}"'
            )
            brief_dst.write_text(brief_content, encoding="utf-8")
        else:
            brief_dst.write_text(
                f"---\nproject_slug: {slug}\nproject_type: {ptype}\n"
                f'title: "{title}"\nconfidential_tier: local-only\nstatus: active\n---\n\n'
                "# Project Brief\n\n## 1. Central Question\n\n## 2. Hypotheses or Aims\n\n"
                "## 3. Position Statement\n\n## 4. Scope Boundaries\n\n"
                "## 5. Required Evidence\n\n## 6. Output Mode\n\n## 7. Known Risks\n",
                encoding="utf-8",
            )
        # Copy optional template files
        always_copy = [
            ("Evidence_Map.md", "Evidence_Map.md"),
            ("Roadmap.md", "Roadmap.md"),
            ("Decision_Log.md", "Decision_Log.md"),
        ]
        paper_prep_extras = [
            ("figure-flow.md", "figure-flow.md"),
            ("data-needed.md", "data-needed.md"),
            ("figure-plan_TEMPLATE.md", "figure-plan.md"),
            ("experiment-roadmap_TEMPLATE.md", "experiment-roadmap.md"),
        ]
        copy_list = always_copy + (paper_prep_extras if ptype == "paper_in_prep" else [])
        for tmpl_name, dst_name in copy_list:
            tmpl = TEMPLATES / tmpl_name
            if tmpl.exists() and not (project_dir / dst_name).exists():
                shutil.copy2(tmpl, project_dir / dst_name)
        rebuild_dashboard()
        extras_note = (
            "\n  ✓ figure-flow.md and data-needed.md created (discuss with Planner)"
            if ptype == "paper_in_prep" else ""
        )
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"create-project {slug} ({ptype})",
            "stdout": (
                f"Created projects/{slug}/\n"
                f"  type: {ptype}\n"
                f"  title: {title}{extras_note}\n"
                f"  Edit Project_Brief.md to fill in aims and scope.\n"
                f"  Then run: python3 scripts/pre_drafter.py --project {slug} --keywords '...'\n"
                f"  Then run: python3 scripts/local_agent.py --role planner --project {slug}"
            ),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    # ---- Run pre-drafter wiki analysis ----
    if action_id == "pre-drafter":
        keywords = str(params.get("keywords") or "").strip()
        ptype = str(params.get("project_type") or "paper_in_prep").strip()
        top = int(params.get("top") or 30)
        if not project_slug:
            raise DashboardError("Missing project_slug for pre-drafter.")
        project = project_path(project_slug)
        require_confidential_project(project)
        if not keywords:
            raise DashboardError("Missing keywords for pre-drafter. Provide topic keywords separated by commas.")
        return run_process(
            [
                sys.executable,
                "scripts/pre_drafter.py",
                "--project", project.name,
                "--keywords", keywords,
                "--type", ptype,
                "--top", str(top),
            ],
            timeout=120,
        )

    if action_id == "open-obsidian":
        return run_process(["open", "-a", "Obsidian", str(ROOT)], timeout=30)

    # Quick Scout — creates an ad-hoc paper scout request and runs scout against it.
    if action_id == "scout-quick":
        topic = str(params.get("topic") or "").strip()
        if not topic:
            raise DashboardError("Missing topic for scout-quick.")
        year_start = str(params.get("year_start") or "").strip()
        year_end = str(params.get("year_end") or "").strip()
        slug = scout_slug(topic, year_start, year_end)
        if not slug or slug == "topic":
            slug = f"quick-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        request_dir = SCOUTS / slug
        request_dir.mkdir(parents=True, exist_ok=True)
        brief = request_dir / "Scout_Brief.md"
        if not brief.exists():
            year_range = f"{year_start}-{year_end}" if year_start and year_end else (year_start or year_end or "last 5 years")
            keywords = str(params.get("keywords") or topic).strip()
            brief.write_text(
                "---\n"
                f"slug: {slug}\n"
                "type: paper_scout\n"
                "confidential_tier: external-ok\n"
                f"created: {today}\n"
                "---\n\n"
                f"# Paper scout: {topic}\n\n"
                "## Must-include keywords\n\n"
                f"- {keywords}\n\n"
                "## Must-exclude keywords\n\n"
                "## Year range\n\n"
                f"{year_range}\n\n"
                "## Preferred journals/preprint servers\n\n",
                encoding="utf-8",
            )
        out = request_dir / "candidates" / today
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--brief",
                f"scouts/{slug}/Scout_Brief.md",
                "--out",
                f"scouts/{slug}/candidates/{today}",
            ],
            timeout=900,
        )

    # Import a Scopus CSV export as a new candidate batch.
    if action_id == "import-scopus-csv":
        csv_content = str(params.get("csv_content") or "").strip()
        target_slug = str(params.get("target_slug") or "").strip()
        topic       = str(params.get("topic") or target_slug or "scopus-import").strip()
        keywords    = str(params.get("keywords") or topic).strip()
        year_start  = str(params.get("year_start") or "").strip()
        year_end    = str(params.get("year_end") or "").strip()

        if not csv_content:
            raise DashboardError("No CSV content received.")

        # Resolve or create the scout folder
        if target_slug:
            slug = target_slug
        else:
            slug = scout_slug(topic, year_start, year_end) or f"scopus-{today}"
        request_dir = ensure_inside_root(SCOUTS / slug)
        request_dir.mkdir(parents=True, exist_ok=True)

        # Write Scout_Brief.md if it doesn't exist
        brief = request_dir / "Scout_Brief.md"
        if not brief.exists():
            year_range = f"{year_start}-{year_end}" if year_start and year_end else (year_start or year_end or "")
            brief.write_text(
                "---\n"
                f"slug: {slug}\n"
                "type: paper_scout\n"
                "source: scopus\n"
                "confidential_tier: external-ok\n"
                f"created: {today}\n"
                "---\n\n"
                f"# Paper scout: {topic}\n\n"
                "## Must-include keywords\n\n"
                f"- {keywords}\n\n"
                "## Must-exclude keywords\n\n"
                "## Year range\n\n"
                f"{year_range}\n\n"
                "## Preferred journals/preprint servers\n\n",
                encoding="utf-8",
            )

        # Write CSV to a temp file, then parse it
        import tempfile
        tmp_csv = Path(tempfile.mktemp(suffix=".csv"))
        try:
            tmp_csv.write_text(csv_content, encoding="utf-8-sig")
            out_dir = request_dir / "candidates" / today
            out_dir.mkdir(parents=True, exist_ok=True)
            result = run_process(
                [sys.executable, "scripts/parse_scopus_csv.py", "--csv", str(tmp_csv), "--out", str(out_dir)],
                timeout=60,
            )
        finally:
            tmp_csv.unlink(missing_ok=True)

        if result.get("ok"):
            result["slug"] = slug
            result["stdout"] = (result.get("stdout") or "") + f"\n\nScout folder: scouts/{slug}"
        return result

    # Run scout against an existing exploration's idea-note.
    if action_id == "scout-exploration":
        slug = str(params.get("exploration_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing exploration_slug for scout-exploration.")
        slug = require_simple_slug(slug, "exploration_slug")
        note = EXPLORATIONS / "idea-notes" / f"{slug}.md"
        if not note.exists():
            raise DashboardError(f"Exploration idea-note not found: explorations/idea-notes/{slug}.md")
        active_dir = EXPLORATIONS / "active" / slug
        out = active_dir / "candidates" / today
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--exploration",
                slug,
            ],
            timeout=900,
        )

    if action_id == "approval-board-exploration":
        slug = str(params.get("exploration_slug") or project_slug or "").strip()
        active = active_exploration_path(slug)
        return run_process(
            [
                sys.executable,
                "scripts/build_triage_approval_board.py",
                "--project",
                f"explorations/active/{active.name}",
            ],
            timeout=120,
        )

    if action_id == "open-approval-board-exploration":
        slug = str(params.get("exploration_slug") or project_slug or "").strip()
        active = active_exploration_path(slug)
        board = latest_approval_board(active)
        if board is None:
            build = handle_action("approval-board-exploration", active.name)
            if not build["ok"]:
                return build
            board = latest_approval_board(active)
        if board is None:
            raise DashboardError("No exploration approval board exists after build.")
        return open_path(board)

    if action_id == "approval-board-scout":
        slug = str(params.get("scout_slug") or project_slug or "").strip()
        scout = scout_request_path(slug)
        return run_process(
            [
                sys.executable,
                "scripts/build_triage_approval_board.py",
                "--project",
                f"scouts/{scout.name}",
            ],
            timeout=120,
        )

    if action_id == "open-approval-board-scout":
        slug = str(params.get("scout_slug") or project_slug or "").strip()
        scout = scout_request_path(slug)
        board = latest_approval_board(scout)
        if board is None:
            build = handle_action("approval-board-scout", scout.name)
            if not build["ok"]:
                return build
            board = latest_approval_board(scout)
        if board is None:
            raise DashboardError("No scout approval board exists after build.")
        return open_path(board)

    if action_id == "verify-publish":
        # Step 1: validate the proof before moving anything. Returns ok=True only if proof checks out.
        slug = str(params.get("project_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing project_slug.")
        src = PROJECTS / slug
        if not src.is_dir() or src.parent.name == "published":
            raise DashboardError(f"Project folder not found or already published: projects/{slug}")
        preprint_url = str(params.get("preprint_url") or "").strip()
        acceptance_path = str(params.get("acceptance_letter_path") or "").strip()
        if not preprint_url and not acceptance_path:
            raise DashboardError("Provide a preprint URL or an acceptance-letter PDF path.")

        verification: dict[str, Any] = {"preprint_url_ok": False, "acceptance_letter_ok": False}

        # Validate preprint URL: pattern + HEAD request
        if preprint_url:
            allowed_hosts = (
                "biorxiv.org", "medrxiv.org", "arxiv.org",
                "ssrn.com", "osf.io", "researchsquare.com",
                "chemrxiv.org", "preprints.org", "doi.org", "psyarxiv.com",
            )
            if not re.match(r"^https?://", preprint_url):
                raise DashboardError("Preprint URL must start with http:// or https://")
            if not any(host in preprint_url.lower() for host in allowed_hosts):
                raise DashboardError(
                    f"URL host not on the preprint allowlist: {', '.join(allowed_hosts)}"
                )
            import urllib.request
            import urllib.error
            try:
                req = urllib.request.Request(preprint_url, method="HEAD",
                                              headers={"User-Agent": "Mozilla/5.0 LLM-Wiki-Dashboard"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        raise DashboardError(f"Preprint URL returned HTTP {resp.status}.")
                verification["preprint_url_ok"] = True
                verification["preprint_url"] = preprint_url
            except urllib.error.HTTPError as e:
                # Some preprint servers reject HEAD or block scrapers — try GET
                if e.code in (403, 405, 429, 501):
                    try:
                        req = urllib.request.Request(preprint_url,
                                                      headers={"User-Agent": "Mozilla/5.0 LLM-Wiki-Dashboard"})
                        with urllib.request.urlopen(req, timeout=20) as resp:
                            resp.read(2048)
                            verification["preprint_url_ok"] = True
                            verification["preprint_url"] = preprint_url
                    except urllib.error.HTTPError as ge:
                        if ge.code in (403, 429):
                            # Anti-scraping — host is on the allowlist so trust the pattern
                            verification["preprint_url_ok"] = True
                            verification["preprint_url"] = preprint_url
                            verification["preprint_url_note"] = f"Host blocks automated requests (HTTP {ge.code}); allowlist host trusted."
                        else:
                            raise DashboardError(f"Preprint URL returned HTTP {ge.code}.")
                    except urllib.error.URLError as ge:
                        raise DashboardError(f"Preprint URL fetch failed: {ge.reason}")
                else:
                    raise DashboardError(f"Preprint URL returned HTTP {e.code}.")
            except urllib.error.URLError as e:
                raise DashboardError(f"Could not reach preprint URL: {e.reason}")

        # Validate acceptance letter PDF
        if acceptance_path:
            letter = Path(acceptance_path).expanduser()
            if not letter.is_absolute():
                # interpret as relative to repo root
                letter = (ROOT / acceptance_path).resolve()
            if not letter.is_file():
                raise DashboardError(f"Acceptance letter not found: {acceptance_path}")
            if letter.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
                raise DashboardError("Acceptance letter must be a PDF or image file.")
            if letter.stat().st_size > 25 * 1024 * 1024:
                raise DashboardError("Acceptance letter exceeds 25 MB.")
            verification["acceptance_letter_ok"] = True
            verification["acceptance_letter_resolved"] = str(letter)

        return {
            "ok": True,
            "exit_code": 0,
            "command": "verify-publish",
            "stdout": "Verification passed. You can now publish.",
            "stderr": "",
            "log": "",
            "verification": verification,
        }

    if action_id == "publish-project":
        # Step 2: actually move the project after verification has succeeded.
        slug = str(params.get("project_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing project_slug.")
        # Re-run verification so this endpoint can't be called without proof.
        verify = handle_action("verify-publish", slug, params)
        if not verify["ok"]:
            return verify
        preprint_url = str(params.get("preprint_url") or "").strip()
        journal = str(params.get("journal") or "").strip()
        notes = str(params.get("notes") or "").strip()
        biorxiv_doi = ""
        m = re.search(r"10\.\d{4,9}/[^\s\"<>]+", preprint_url)
        if m:
            biorxiv_doi = m.group(0).rstrip(".)")

        cmd = [sys.executable, "scripts/publish_project.py", "--project", slug]
        if biorxiv_doi:
            cmd += ["--biorxiv-doi", biorxiv_doi]
        if preprint_url:
            cmd += ["--biorxiv-url", preprint_url]
        if journal:
            cmd += ["--journal", journal]
        if notes:
            cmd += ["--notes", notes]
        result = run_process(cmd, timeout=60)

        # Copy the acceptance letter into the published folder if provided
        verification = verify.get("verification", {})
        if result["ok"] and verification.get("acceptance_letter_ok"):
            src_letter = Path(verification["acceptance_letter_resolved"])
            published_dir = PROJECTS / "published" / slug
            if published_dir.is_dir():
                dst = published_dir / f"acceptance-letter{src_letter.suffix.lower()}"
                shutil.copy2(src_letter, dst)
                result["stdout"] = (result.get("stdout") or "") + \
                    f"\nAcceptance letter saved to {dst.relative_to(ROOT)}"

        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "start-revision":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        if not slug:
            raise DashboardError("Missing project_slug.")
        # Source must live under projects/published/
        if not (PROJECTS / "published" / slug).is_dir():
            raise DashboardError(f"Published project not found: projects/published/{slug}")
        tag = str(params.get("revision_tag") or "r1").strip() or "r1"
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,15}", tag):
            raise DashboardError("revision_tag must be 1-16 chars, lowercase alphanumeric/_/-.")
        cmd = [sys.executable, "scripts/start_revision.py", "--published", slug, "--revision-tag", tag]
        result = run_process(cmd, timeout=120)
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "local-generate-schematic":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        return open_schematic_generator(project)

    if action_id == "local-generate-figure-mockups":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        panel = str(params.get("panel") or "").strip()
        return open_figure_mockups_generator(project, panel=panel)

    if action_id == "open-schematics-folder":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        target = project / "schematics"
        target.mkdir(parents=True, exist_ok=True)
        return open_path(target)

    if action_id == "open-figure-mockups-folder":
        slug = str(params.get("project_slug") or project_slug or "").strip()
        project = project_path(slug)
        target = project / "figure-mockups"
        target.mkdir(parents=True, exist_ok=True)
        return open_path(target)

    if action_id == "save-triage-criteria":
        criteria_text = str(params.get("criteria") or "").strip()
        target_type = str(params.get("target_type") or "scout").strip()  # "scout" | "exploration"
        target_slug = str(params.get("target_slug") or "").strip()
        if not criteria_text:
            raise DashboardError("No criteria text provided.")
        if not target_slug:
            raise DashboardError("No target scout/exploration slug provided.")
        # Resolve the directory
        if target_type == "exploration":
            target_dir = ensure_inside_root(EXPLORATIONS / "active" / target_slug)
        else:
            target_dir = ensure_inside_root(SCOUTS / target_slug)
        if not target_dir.exists():
            raise DashboardError(f"Folder not found: {target_dir.relative_to(ROOT)}")
        criteria_path = target_dir / "Triage_Criteria.md"
        criteria_path.write_text(criteria_text, encoding="utf-8")
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"write {rel(criteria_path)}",
            "stdout": f"Saved to {rel(criteria_path)}",
            "stderr": "",
            "log": "",
            "criteria_path": rel(criteria_path),
        }

    if action_id == "save-synthesis-brief":
        slug        = str(params.get("slug") or "synthesis").strip().replace(" ", "-")
        keywords    = str(params.get("keywords") or "").strip()
        output_path = str(params.get("output_path") or f"wiki/overviews/{slug}.md").strip()
        output_type = str(params.get("output_type") or "overview").strip()
        if not keywords:
            raise DashboardError("No keywords provided.")
        if output_type == "exploration":
            brief_path = ensure_inside_root(EXPLORATIONS / "active" / slug / "synthesis-brief.md")
        else:
            brief_path = ensure_inside_root(WIKI / "overviews" / f"{slug}-synthesis-brief.md")
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(
            f"---\nslug: {slug}\noutput: {output_path}\nstatus: draft\n---\n\n"
            f"# Synthesis Brief: {slug}\n\n## Keywords / Topic\n\n{keywords}\n\n"
            f"## Scope\n\n<!-- What this overview should cover -->\n\n"
            f"## Key Questions\n\n<!-- What questions should the synthesis answer? -->\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"write {rel(brief_path)}",
            "stdout": f"Saved to {rel(brief_path)}",
            "stderr": "",
            "log": "",
        }

    if action_id == "open-inbox":
        inbox = PAPERS / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        return open_path(inbox)

    if action_id == "import-local-pdfs":
        mode = str(params.get("mode") or "copy").strip().lower()
        if mode not in {"copy", "move"}:
            raise DashboardError("Import mode must be copy or move.")
        return run_process(
            [
                sys.executable,
                "scripts/import_local_pdfs_to_inbox.py",
                "--mode",
                mode,
            ],
            timeout=300,
        )

    if action_id == "auto-download-queue":
        return auto_download_queue(params)

    # ---- Fetch external info from URL ----
    if action_id == "fetch-external-info":
        url = str(params.get("url") or "").strip()
        info_type = str(params.get("info_type") or "general").strip()
        slug = str(params.get("slug") or project_slug or "").strip()
        max_chars = int(params.get("max_chars") or 12000)
        valid_types = {"grant_info", "job_description", "dept_faculty", "general"}
        if not url:
            raise DashboardError("Missing url for fetch-external-info.")
        if not slug:
            raise DashboardError("Missing slug for fetch-external-info.")
        if info_type not in valid_types:
            info_type = "general"
        return run_process(
            [
                sys.executable,
                "scripts/fetch_external_info.py",
                "--url", url,
                "--type", info_type,
                "--slug", slug,
                "--max-chars", str(max_chars),
            ],
            timeout=60,
        )

    # ---- Copy external info file to project folder ----
    if action_id == "copy-info-to-project":
        source_rel = str(params.get("source") or "").strip()
        dest_name = str(params.get("dest_name") or "").strip()
        if not source_rel or not project_slug:
            raise DashboardError("Missing source or project_slug for copy-info-to-project.")
        if not dest_name:
            raise DashboardError("Missing dest_name for copy-info-to-project.")
        source = ensure_inside_root(ROOT / source_rel)
        if not source.exists():
            raise DashboardError(f"Source file not found: {source_rel}")
        project = project_path(project_slug)
        dest = project / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"copy {source_rel} → projects/{project_slug}/{dest_name}",
            "stdout": f"Copied to projects/{project_slug}/{dest_name}\nThe local agent will load this file automatically.",
            "stderr": "",
            "log": "",
            "reload_suggested": False,
        }

    # ---- Convert draft to .docx ----
    if action_id == "export-docx":
        draft_rel = str(params.get("draft_path") or "").strip()
        track = params.get("track_changes", True)
        if not draft_rel:
            raise DashboardError("Missing draft_path for export-docx.")
        draft_path = ensure_inside_root(ROOT / draft_rel)
        if not draft_path.exists():
            raise DashboardError(f"Draft not found: {draft_rel}")
        extra = ["--no-track-changes"] if not track else []
        return run_process(
            [sys.executable, "scripts/convert_to_docx.py", str(draft_path)] + extra,
            timeout=60,
        )

    # ---- Open user-drafts folder for a project ----
    if action_id == "open-user-drafts":
        if not project_slug:
            raise DashboardError("Missing project_slug.")
        project = project_path(project_slug)
        ud = project / "user-drafts"
        ud.mkdir(parents=True, exist_ok=True)
        return open_path(ud)

    # ---- Open or create figure-flow.md for a project ----
    if action_id == "open-figure-flow":
        if not project_slug:
            raise DashboardError("Missing project_slug.")
        project = project_path(project_slug)
        ff = project / "figure-flow.md"
        if not ff.exists():
            template = TEMPLATES / "figure-flow.md"
            if template.exists():
                shutil.copy(template, ff)
            else:
                ff.write_text(
                    "---\nconfidential_tier: local-only\n---\n\n"
                    "# Figure Flow\n\n",
                    encoding="utf-8",
                )
        return open_path(ff)

    # ---- Open or create data-needed.md for a project ----
    if action_id == "open-data-needed":
        if not project_slug:
            raise DashboardError("Missing project_slug.")
        project = project_path(project_slug)
        dn = project / "data-needed.md"
        if not dn.exists():
            template = TEMPLATES / "data-needed.md"
            if template.exists():
                shutil.copy(template, dn)
            else:
                dn.write_text(
                    "---\nconfidential_tier: local-only\n---\n\n"
                    "# Data Needed\n\n",
                    encoding="utf-8",
                )
        return open_path(dn)

    # ---- Promote exploration to active + create project ----
    if action_id == "promote-exploration-to-project":
        exploration_slug = require_simple_slug(
            str(params.get("exploration_slug") or project_slug or "").strip(), "exploration_slug"
        )
        p_slug = require_simple_slug(
            str(params.get("project_slug") or exploration_slug).strip(), "project_slug"
        )
        p_type = str(params.get("project_type") or "paper_in_prep").strip()
        p_title = str(params.get("project_title") or "Working title").strip()
        keywords = str(params.get("keywords") or "").strip()
        valid_types = {"paper_in_prep", "review_article", "grant", "job_application"}
        if p_type not in valid_types:
            p_type = "paper_in_prep"

        # 1. Create active exploration folder
        active_dir = ensure_inside_root(EXPLORATIONS / "active" / exploration_slug)
        for sub in ["candidates", "paper-briefs", "_pdfs"]:
            (active_dir / sub).mkdir(parents=True, exist_ok=True)
        brief_src = EXPLORATIONS / "ideas" / f"Exploration_Brief_{exploration_slug}.md"
        brief_dst = active_dir / "Exploration_Brief.md"
        if brief_src.exists() and not brief_dst.exists():
            shutil.copy2(brief_src, brief_dst)
        readme_src = EXPLORATIONS / "_template" / "Active_Exploration_README_TEMPLATE.md"
        if readme_src.exists() and not (active_dir / "README.md").exists():
            shutil.copy2(readme_src, active_dir / "README.md")
        for fname in ["scout-queries.md", "notes.md", "questions.md", "synthesis.md",
                      "promote-to-wiki.md", "promote-to-project.md"]:
            fpath = active_dir / fname
            if not fpath.exists():
                fpath.touch()

        # 2. Create confidential project
        project_dir = PROJECTS / p_slug
        stdout_lines = [f"✓ explorations/active/{exploration_slug}/"]
        if not project_dir.exists():
            (project_dir / "Drafts").mkdir(parents=True, exist_ok=True)
            for sub in [("critiques", "argue"), ("critiques", "demon"),
                        ("rejection-sims",), ("notes",), ("data-updates",)]:
                (project_dir / Path(*sub)).mkdir(parents=True, exist_ok=True)
            brief_tmpl = TEMPLATES / "Project_Brief.md"
            brief_out = project_dir / "Project_Brief.md"
            if brief_tmpl.exists():
                content = brief_tmpl.read_text(encoding="utf-8")
                content = content.replace("project_slug: short-kebab-case-name", f"project_slug: {p_slug}")
                content = content.replace(
                    "project_type: grant | paper_in_prep | review_article", f"project_type: {p_type}"
                )
                content = content.replace('title: "Working title"', f'title: "{p_title}"')
                brief_out.write_text(content, encoding="utf-8")
            for tmpl_name, dst_name in [
                ("Evidence_Map.md", "Evidence_Map.md"),
                ("Roadmap.md", "Roadmap.md"),
                ("Decision_Log.md", "Decision_Log.md"),
            ]:
                t = TEMPLATES / tmpl_name
                if t.exists() and not (project_dir / dst_name).exists():
                    shutil.copy2(t, project_dir / dst_name)
            # Link note back to exploration
            link_note = project_dir / "notes" / "from-exploration.md"
            link_note.write_text(
                f"---\ncreated_from_exploration: {exploration_slug}\n---\n\n"
                f"# Promoted from exploration: {exploration_slug}\n\n"
                f"- explorations/active/{exploration_slug}/notes.md\n"
                f"- explorations/active/{exploration_slug}/synthesis.md\n",
                encoding="utf-8",
            )
            stdout_lines.append(f"✓ projects/{p_slug}/ ({p_type})")
        else:
            stdout_lines.append(f"  projects/{p_slug}/ already exists — skipped creation")

        rebuild_dashboard()

        # 3. Run wiki relevance scan in Terminal if keywords provided
        if keywords:
            result = open_terminal_runner(
                label=f"Wiki relevance — {p_slug}",
                command_line=(
                    f"{json.dumps(sys.executable)} scripts/pre_drafter.py "
                    f"--project {json.dumps(p_slug)} --keywords {json.dumps(keywords)}"
                ),
                success_note=f"Wiki context written to projects/{p_slug}/wiki_context.md",
            )
            result["stdout"] = "\n".join(stdout_lines) + "\n\n" + (result.get("stdout") or "")
            result["reload_suggested"] = True
            return result

        return {
            "ok": True,
            "exit_code": 0,
            "command": f"promote-exploration-to-project {exploration_slug} → {p_slug}",
            "stdout": "\n".join(stdout_lines) + "\n\nNext: add keywords → re-run for wiki relevance scan.",
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    # ---- Open local agent on the project linked to an exploration ----
    if action_id == "local-exploration-synthesis":
        p_slug = str(params.get("project_slug") or project_slug or "").strip()
        if not p_slug:
            raise DashboardError("Provide project_slug (the slug used when promoting this exploration).")
        p_dir = ensure_inside_root(PROJECTS / require_simple_slug(p_slug, "project_slug"))
        if not p_dir.exists():
            raise DashboardError(
                f"Project not found: projects/{p_slug}/. "
                "Promote the exploration first using 'Promote to active exploration + create project'."
            )
        return open_local_agent("drafter", p_dir)

    # ---- Export sanitized scout brief to cloud-readable scouts/ area ----
    if action_id == "export-scout-brief":
        p_slug = require_simple_slug(str(project_slug or "").strip(), "project_slug")
        p_dir  = ensure_inside_root(PROJECTS / p_slug)
        if not p_dir.exists():
            raise DashboardError(f"Project not found: projects/{p_slug}/")
        draft = p_dir / "notes" / "scout-brief.md"
        if not draft.exists():
            raise DashboardError(
                f"No scout brief at projects/{p_slug}/notes/scout-brief.md. "
                "Run the local Scout-Brief agent first, then /save."
            )
        content = draft.read_text(encoding="utf-8")
        # Require simulation_passed: true in frontmatter
        if "simulation_passed: true" not in content:
            raise DashboardError(
                "Export blocked: scout-brief.md does not contain 'simulation_passed: true'. "
                "The identity-leak simulation must pass before the file can leave the confidential zone."
            )
        # Additional safety: reject if project slug appears literally in the body
        body_after_fm = content.split("---", 2)[-1] if content.startswith("---") else content
        if p_slug.lower() in body_after_fm.lower():
            raise DashboardError(
                f"Export blocked: the project slug '{p_slug}' appears in the brief body. "
                "Remove all direct project references before exporting."
            )
        scout_target = ensure_inside_root(SCOUTS / f"project-{p_slug}")
        scout_target.mkdir(parents=True, exist_ok=True)
        (scout_target / "candidates").mkdir(exist_ok=True)
        export_path = scout_target / "Scout_Brief.md"
        shutil.copy2(draft, export_path)
        rebuild_dashboard()
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"export-scout-brief → scouts/project-{p_slug}/Scout_Brief.md",
            "stdout": (
                f"Exported to scouts/project-{p_slug}/Scout_Brief.md\n"
                "Cloud agents (Codex CLI, Scout) can now use this file.\n"
                "Run Quick Scout using the 'From project scout brief' selector."
            ),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    if action_id == "delete-scout-brief":
        # Delete scouts/{s_slug}/Scout_Brief.md after it has been used for scouting.
        # Keeps the candidates/ folder (keyword history). s_slug comes in as project_slug param.
        s_slug = str(project_slug or "").strip()
        if not s_slug:
            s_slug = str(params.get("scout_slug") or "").strip()
        if not s_slug:
            raise DashboardError("Missing scout_slug for delete-scout-brief.")
        scout_dir = ensure_inside_root(SCOUTS / s_slug)
        brief_file = scout_dir / "Scout_Brief.md"
        if not brief_file.exists():
            return {"ok": True, "exit_code": 0, "command": f"delete-scout-brief {s_slug}",
                    "stdout": "Scout brief already gone (nothing to delete).", "stderr": "", "log": "", "reload_suggested": True}
        brief_file.unlink()
        rebuild_dashboard()
        return {"ok": True, "exit_code": 0, "command": f"delete-scout-brief {s_slug}",
                "stdout": f"Deleted scouts/{s_slug}/Scout_Brief.md.\nKeyword history preserved in candidates/.",
                "stderr": "", "log": "", "reload_suggested": True}

    project = project_path(project_slug)
    slug = project.name

    if action_id in LOCAL_AGENT_ROLES:
        section = str(params.get("section") or "").strip()
        return open_local_agent(LOCAL_AGENT_ROLES[action_id], project, section=section)

    if action_id == "brief":
        ptype = read_project_type(project)
        if ptype and ptype != "library_ingest":
            raise DashboardError(
                f"This project is confidential (type={ptype!r}). Open Project_Brief.md "
                f"manually in your editor — the dashboard does not surface confidential briefs."
            )
        return open_path(project / "Project_Brief.md")

    if action_id == "queries":
        require_library_ingest(project)
        queries = project / "scout-queries.md"
        if not queries.exists():
            queries.write_text("# Scout Queries\n\n", encoding="utf-8")
        return open_path(queries)

    if action_id == "scout":
        require_library_ingest(project)
        out = project / "candidates" / today
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--brief",
                f"projects/{slug}/Project_Brief.md",
                "--out",
                f"projects/{slug}/candidates/{today}",
            ],
            timeout=900,
        )

    if action_id == "scout-campaign":
        require_library_ingest(project)
        out = project / "candidates" / f"{today}-campaign"
        out.mkdir(parents=True, exist_ok=True)
        return run_process(
            [
                sys.executable,
                "scripts/scout_all.py",
                "--brief",
                f"projects/{slug}/Project_Brief.md",
                "--out",
                f"projects/{slug}/candidates/{today}-campaign",
                "--queries-only",
            ],
            timeout=900,
        )

    if action_id == "approval-board":
        require_library_ingest(project)
        return run_process(
            [sys.executable, "scripts/build_triage_approval_board.py", "--project", f"projects/{slug}"],
            timeout=120,
        )

    if action_id == "open-approval-board":
        require_library_ingest(project)
        board = latest_approval_board(project)
        if board is None:
            build = handle_action("approval-board", slug)
            if not build["ok"]:
                return build
            board = latest_approval_board(project)
        if board is None:
            raise DashboardError("No approval board exists after build.")
        return open_path(board)

    if action_id == "prep-files":
        require_library_ingest(project)
        messages = []
        (project / "data-updates").mkdir(parents=True, exist_ok=True)
        (project / "critiques").mkdir(parents=True, exist_ok=True)
        messages.append(copy_if_missing(TEMPLATES / "figure-plan_TEMPLATE.md", project / "figure-plan.md"))
        messages.append(copy_if_missing(TEMPLATES / "experiment-roadmap_TEMPLATE.md", project / "experiment-roadmap.md"))
        messages.append(copy_if_missing(TEMPLATES / "critique-log_TEMPLATE.md", project / "critiques" / "critique-log.md"))
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"create optional paper-in-prep files for projects/{slug}",
            "stdout": "\n".join(messages),
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    if action_id == "data-update":
        require_library_ingest(project)
        dst = project / "data-updates" / f"{today}-fig-panel.md"
        message = copy_if_missing(TEMPLATES / "data-updates_TEMPLATE.md", dst)
        return {
            "ok": True,
            "exit_code": 0,
            "command": f"create data update for projects/{slug}",
            "stdout": message,
            "stderr": "",
            "log": "",
            "reload_suggested": True,
        }

    raise DashboardError(f"Action is copy-only or not allowlisted: {action_id}")


# ---------------------------------------------------------------------------
# Homework helpers
# ---------------------------------------------------------------------------

HOMEWORK_PATH = ROOT / "_system" / "docs" / "homework.json"


def _load_homework() -> dict:
    default: dict = {"frequency_days": 14, "current": None, "completed": [], "skipped": []}
    if not HOMEWORK_PATH.exists():
        return default
    try:
        return json.loads(HOMEWORK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_homework(data: dict) -> None:
    HOMEWORK_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOMEWORK_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _pick_random_wiki_paper(exclude_stems: set[str]) -> dict | None:
    """Pick a random wiki paper (not an overview) not in exclude_stems."""
    import random
    wiki_dir = ROOT / "wiki"
    candidates = []
    if wiki_dir.exists():
        for cat_dir in wiki_dir.iterdir():
            if not cat_dir.is_dir() or cat_dir.name == "overviews":
                continue
            for md in cat_dir.glob("*.md"):
                if md.stem not in exclude_stems:
                    fm_title = None
                    try:
                        text = md.read_text(encoding="utf-8")
                        for line in text.split("\n")[1:20]:
                            if line.lower().startswith("title:"):
                                fm_title = line.split(":", 1)[1].strip().strip('"').strip("'")
                                break
                    except OSError:
                        pass
                    candidates.append({
                        "stem": md.stem,
                        "title": fm_title or md.stem,
                        "category": cat_dir.name,
                    })
    if not candidates:
        return None
    return random.choice(candidates)


def handle_homework_action(action_id: str, params: dict) -> dict:
    """Handle homework-* actions. Returns a standard result dict."""
    from datetime import date, timedelta

    hw = _load_homework()

    if action_id == "homework-set-period":
        days = int(str(params.get("days") or 14))
        if days not in {7, 14, 30}:
            raise DashboardError(f"Invalid period: {days}. Must be 7, 14, or 30.")
        hw["frequency_days"] = days
        _save_homework(hw)
        rebuild_dashboard()
        return {"ok": True, "exit_code": 0, "command": f"Set homework period to {days} days",
                "stdout": f"Homework period updated to every {days} days.", "stderr": "", "log": "",
                "reload_suggested": True}

    if action_id in {"homework-complete", "homework-skip"}:
        current = hw.get("current")
        if current:
            record = {**current, "action": action_id.split("-")[1],
                      "action_date": date.today().isoformat()}
            key = "completed" if action_id == "homework-complete" else "skipped"
            hw.setdefault(key, []).append(record)
        # Assign next
        done_stems = {p["stem"] for p in hw.get("completed", [])} | \
                     {p["stem"] for p in hw.get("skipped", [])}
        new_paper = _pick_random_wiki_paper(done_stems)
        if new_paper is None:
            # All done — reset skipped pool
            hw["skipped"] = []
            done_stems = {p["stem"] for p in hw.get("completed", [])}
            new_paper = _pick_random_wiki_paper(done_stems)
        if new_paper:
            assigned = date.today()
            due = assigned + timedelta(days=hw.get("frequency_days", 14))
            hw["current"] = {
                **new_paper,
                "assigned_date": assigned.isoformat(),
                "due_date": due.isoformat(),
            }
        else:
            hw["current"] = None
        _save_homework(hw)
        rebuild_dashboard()
        verb = "marked complete" if action_id == "homework-complete" else "skipped"
        paper_name = new_paper["title"] if new_paper else "none"
        return {"ok": True, "exit_code": 0, "command": action_id,
                "stdout": f"Paper {verb}. Next assignment: {paper_name}", "stderr": "", "log": "",
                "reload_suggested": True}

    if action_id == "homework-assign":
        # Force-assign a random new paper
        done_stems = {p["stem"] for p in hw.get("completed", [])} | \
                     {p["stem"] for p in hw.get("skipped", [])}
        new_paper = _pick_random_wiki_paper(done_stems)
        if new_paper is None:
            raise DashboardError("No wiki papers available to assign.")
        from datetime import date, timedelta
        assigned = date.today()
        due = assigned + timedelta(days=hw.get("frequency_days", 14))
        hw["current"] = {
            **new_paper,
            "assigned_date": assigned.isoformat(),
            "due_date": due.isoformat(),
        }
        _save_homework(hw)
        rebuild_dashboard()
        return {"ok": True, "exit_code": 0, "command": "homework-assign",
                "stdout": f"Assigned: {new_paper['title']} (due {due.isoformat()})",
                "stderr": "", "log": "", "reload_suggested": True}

    if action_id == "homework-start-session":
        # Create session folder for current homework paper via homework_manager.py
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "homework_manager.py"), "start-session"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        if result.returncode != 0:
            raise DashboardError(result.stderr.strip() or "homework-start-session failed")
        out = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
        session_dir = out.get("session_dir", "")
        existed = out.get("existed", False)
        rebuild_dashboard()
        msg = f"Session folder {'already exists' if existed else 'created'}: {session_dir}"
        return {"ok": True, "exit_code": 0, "command": "homework-start-session",
                "stdout": msg, "stderr": "", "log": "", "reload_suggested": True,
                "session_dir": session_dir}

    if action_id == "homework-open-session":
        session_dir_name = str(params.get("session_dir") or "")
        if not session_dir_name:
            raise DashboardError("session_dir param required")
        session_path = ROOT / session_dir_name
        if not session_path.exists() or not session_path.is_dir():
            raise DashboardError(f"Session dir not found: {session_dir_name}")
        subprocess.Popen(["open", str(session_path)])
        return {"ok": True, "exit_code": 0, "command": f"open {session_path}",
                "stdout": f"Opened {session_dir_name}", "stderr": "", "log": ""}

    if action_id == "homework-open-idea-wiki":
        idea_wiki_path = ROOT / "homework" / "idea-wiki"
        idea_wiki_path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(idea_wiki_path)])
        return {"ok": True, "exit_code": 0, "command": f"open {idea_wiki_path}",
                "stdout": "Opened idea-wiki folder", "stderr": "", "log": ""}

    if action_id == "homework-save-idea":
        idea_title = str(params.get("idea_title") or "").strip()
        source_stem = str(params.get("source_stem") or "").strip()
        idea_slug = str(params.get("idea_slug") or "").strip()
        session_date = str(params.get("session_date") or "").strip()
        if not idea_title or not source_stem:
            raise DashboardError("idea_title and source_stem are required")
        cmd_args = [
            sys.executable, str(ROOT / "scripts" / "homework_manager.py"),
            "save-idea",
            "--idea-title", idea_title,
            "--source-stem", source_stem,
        ]
        if idea_slug:
            cmd_args += ["--idea-slug", idea_slug]
        if session_date:
            cmd_args += ["--session-date", session_date]
        result = subprocess.run(cmd_args, capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            raise DashboardError(result.stderr.strip() or "homework-save-idea failed")
        out = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
        rebuild_dashboard()
        wiki_msg = " + wiki backlink added" if out.get("wiki_linked") else ""
        return {"ok": True, "exit_code": 0, "command": "homework-save-idea",
                "stdout": f"Idea saved to {out.get('idea_entry', 'idea-wiki')}{wiki_msg}",
                "stderr": "", "log": "", "reload_suggested": True}

    raise DashboardError(f"Unknown homework action: {action_id}")


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

def handle_backup_action(action_id: str, params: dict) -> dict[str, Any]:
    """Handle backup-* actions (restic-based). Returns a standard result dict."""

    def _parse_json_stdout(result: dict) -> dict:
        """Attach parsed JSON from stdout into result['data']."""
        if result.get("stdout"):
            try:
                result["data"] = json.loads(result["stdout"])
            except json.JSONDecodeError:
                pass
        return result

    if action_id == "backup-detect-gdrive":
        return _parse_json_stdout(
            run_process([sys.executable, "scripts/backup_manager.py", "detect-gdrive"], timeout=30)
        )

    if action_id == "backup-set-path":
        path = str(params.get("path") or "").strip()
        if not path:
            raise DashboardError("Missing path for backup-set-path.")
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "set-path", "--path", path],
            timeout=30,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-init-repo":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "init-repo"],
            timeout=120,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-run":
        dry_run = bool(params.get("dry_run"))
        cmd = [sys.executable, "scripts/backup_manager.py", "run-backup"]
        if dry_run:
            cmd.append("--dry-run")
        result = run_process(cmd, timeout=1800)
        if result["ok"] and not dry_run:
            rebuild_dashboard()
            result["reload_suggested"] = True
        # Parse restic JSON summary out of stdout for dashboard display
        if result.get("stdout"):
            for line in result["stdout"].splitlines():
                try:
                    obj = json.loads(line)
                    if obj.get("message_type") == "summary":
                        result["summary"] = obj
                        break
                except json.JSONDecodeError:
                    continue
        return result

    if action_id == "backup-snapshots":
        limit = int(params.get("limit") or 20)
        return _parse_json_stdout(
            run_process(
                [sys.executable, "scripts/backup_manager.py", "snapshots",
                 "--limit", str(limit)],
                timeout=60,
            )
        )

    if action_id == "backup-prune":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "prune"],
            timeout=600,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-install-schedule":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "install-schedule"],
            timeout=60,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-uninstall-schedule":
        result = run_process(
            [sys.executable, "scripts/backup_manager.py", "uninstall-schedule"],
            timeout=30,
        )
        if result["ok"]:
            rebuild_dashboard()
            result["reload_suggested"] = True
        return result

    if action_id == "backup-open-folder":
        state_result = run_process(
            [sys.executable, "scripts/backup_manager.py", "status"], timeout=15
        )
        gdrive_path = ""
        if state_result.get("stdout"):
            try:
                gdrive_path = json.loads(state_result["stdout"]).get("gdrive_path", "")
            except json.JSONDecodeError:
                pass
        if not gdrive_path:
            raise DashboardError("Google Drive path not configured. Set it first.")
        backup_folder = Path(gdrive_path) / "LLM-Wiki-restic"
        subprocess.Popen(["open", str(backup_folder)])
        return {
            "ok": True, "exit_code": 0,
            "command": f"open {backup_folder}",
            "stdout": f"Opened {backup_folder}", "stderr": "", "log": "",
        }

    raise DashboardError(f"Unknown backup action: {action_id}")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # Allowed origins: only the dashboard itself (127.0.0.1 and localhost, same port).
    # This prevents arbitrary websites from sending API requests to the local server.
    _ALLOWED_ORIGINS = {
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    }

    def _cors_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        # Also allow file:// (no Origin header) and same-origin requests
        if not origin or origin in self._ALLOWED_ORIGINS:
            return origin or "http://127.0.0.1:8765"
        return ""   # denied — end_headers will send no Allow-Origin

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        allowed = self._cors_origin()
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", ""}:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/_system/dashboard/index.html")
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self.write_json({
                "ok": True,
                "interactive": True,
                "repo": str(ROOT),
                "allowed_actions": [
                    "rebuild-dashboard",
                    "stop-dashboard-server",
                    "open-obsidian",
                    "brief",
                    "queries",
                    "scout",
                    "scout-campaign",
                    "scout-exploration",
                    "scout-quick",
                    "approval-board-exploration",
                    "open-approval-board-exploration",
                    "approval-board-scout",
                    "open-approval-board-scout",
                    "open-inbox",
                    "import-local-pdfs",
                    "auto-download-queue",
                    "create-project",
                    "pre-drafter",
                    "fetch-external-info",
                    "copy-info-to-project",
                    "export-docx",
                    "open-user-drafts",
                    "open-figure-flow",
                    "open-data-needed",
                    "check-duplicates",
                    "save-triage-criteria",
                    "save-synthesis-brief",
                    "import-scopus-csv",
                    "project-scout",
                    "homework-assign",
                    "homework-complete",
                    "homework-skip",
                    "homework-set-period",
                    "homework-start-session",
                    "homework-open-session",
                    "homework-open-idea-wiki",
                    "homework-save-idea",
                    "backup-detect-gdrive",
                    "backup-set-path",
                    "backup-init-repo",
                    "backup-run",
                    "backup-snapshots",
                    "backup-prune",
                    "backup-install-schedule",
                    "backup-uninstall-schedule",
                    "backup-open-folder",
                    "local-planner",
                    "local-drafter",
                    "local-argue",
                    "local-demon",
                    "local-rejection-sim",
                    "local-generate-schematic",
                    "local-generate-figure-mockups",
                    "open-schematics-folder",
                    "open-figure-mockups-folder",
                    "verify-publish",
                    "publish-project",
                    "start-revision",
                    "approval-board",
                    "open-approval-board",
                    "prep-files",
                    "data-update",
                    "promote-exploration-to-project",
                    "local-exploration-synthesis",
                    "local-scout-brief",
                    "export-scout-brief",
                    "delete-scout-brief",
                ],
            })
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            action_id = str(payload.get("action_id") or "")
            project_slug = payload.get("project_slug")
            params = payload.get("params") if isinstance(payload.get("params"), dict) else None
            if not action_id:
                raise DashboardError("Missing action_id.")
            if action_id == "stop-dashboard-server":
                self.write_json({
                    "ok": True,
                    "exit_code": 0,
                    "command": "stop dashboard server",
                    "stdout": "Dashboard server is stopping. Restart with: python3 scripts/dashboard_server.py --port 8765",
                    "stderr": "",
                    "log": "",
                })
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            result = handle_action(action_id, str(project_slug) if project_slug else None, params)
            self.write_json(result)
        except subprocess.TimeoutExpired as exc:
            self.write_json({
                "ok": False,
                "exit_code": 124,
                "command": " ".join(exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd),
                "stdout": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
                "stderr": f"Timed out after {exc.timeout} seconds.",
                "log": "",
            }, status=HTTPStatus.REQUEST_TIMEOUT)
        except (DashboardError, FileNotFoundError, json.JSONDecodeError) as exc:
            self.write_json({
                "ok": False,
                "exit_code": 1,
                "command": "",
                "stdout": "",
                "stderr": str(exc),
                "log": "",
            }, status=HTTPStatus.BAD_REQUEST)

    def write_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the research dashboard with a local allowlisted command API.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", default=8765, type=int, help="Bind port. Default: 8765")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard server running at http://{args.host}:{args.port}/_system/dashboard/index.html")
    print("Only allowlisted local actions can run; Ctrl-C stops the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
