#!/usr/bin/env python3
"""Restic-based incremental backup manager for the LLM-Wiki research system.

Strategy
--------
* **restic** with zstd compression + content-addressed deduplication.
* Each run creates one snapshot. Unchanged files cost zero extra space.
* Old snapshots are pruned automatically: keep everything within 6 months
  (daily for the last month, weekly for months 2–3, monthly after that).
* Password stored in _system/docs/.restic_password (chmod 600, auto-generated).

Subcommands (all print JSON to stdout):
  detect-gdrive          — Find Google Drive mount points
  init-repo              — Initialise restic repo at configured gdrive_path
  run-backup             — Create incremental snapshot [--dry-run]
  snapshots              — List recent snapshots (--limit N, default 20)
  prune                  — Forget snapshots older than 6 months + compact
  status                 — Show state + restic availability
  set-path               — Update gdrive_path in backup_state.json
  install-schedule       — Install macOS LaunchAgent for daily auto-backup
  uninstall-schedule     — Remove LaunchAgent
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT        = Path(__file__).resolve().parents[1]
STATE_PATH  = ROOT / "_system" / "docs" / "backup_state.json"
PASS_PATH   = ROOT / "_system" / "docs" / ".restic_password"
PLIST_PATH  = Path.home() / "Library" / "LaunchAgents" / "com.llmwiki.backup.plist"
REPO_NAME   = "LLM-Wiki-restic"

# Files / dirs never worth backing up
EXCLUDES = [
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    ".git",
    "node_modules",
    "_system/mendeley/watch",   # transient import watch folder
]

DEFAULT_STATE: dict = {
    "gdrive_path": "",
    "repo_initialized": False,
    "last_backup": None,
    "last_snapshot_id": None,
    "files_new": None,
    "data_added_bytes": None,
    "auto_backup_installed": False,
    "auto_backup_interval_hours": 24,
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if not STATE_PATH.exists():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        for k, v in DEFAULT_STATE.items():
            data.setdefault(k, v)
        return data
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_STATE)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def days_since(iso_dt: str | None) -> int | None:
    if not iso_dt:
        return None
    try:
        dt = datetime.fromisoformat(iso_dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(tz=timezone.utc) - dt).days
    except ValueError:
        return None


def restic_path() -> str | None:
    """Return path to restic binary, or None if not found."""
    for candidate in ["/opt/homebrew/bin/restic", "/usr/local/bin/restic"]:
        if Path(candidate).exists():
            return candidate
    result = subprocess.run(["which", "restic"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def ensure_password() -> str:
    """Return existing password or generate + save a new one."""
    if PASS_PATH.exists():
        return PASS_PATH.read_text(encoding="utf-8").strip()
    pw = secrets.token_hex(32)
    PASS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PASS_PATH.write_text(pw + "\n", encoding="utf-8")
    os.chmod(PASS_PATH, 0o600)
    return pw


def restic_env(repo_path: str) -> dict:
    """Env vars restic needs."""
    return {
        **os.environ,
        "RESTIC_REPOSITORY": repo_path,
        "RESTIC_PASSWORD_FILE": str(PASS_PATH),
    }


def run_restic(args_list: list[str], repo_path: str, timeout: int = 900) -> subprocess.CompletedProcess:
    exe = restic_path()
    if not exe:
        raise FileNotFoundError("restic not found")
    return subprocess.run(
        [exe] + args_list,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=restic_env(repo_path),
    )


# ── Subcommands ────────────────────────────────────────────────────────────────

def cmd_detect_gdrive(_args: argparse.Namespace) -> dict:
    patterns = [
        str(Path.home() / "Library" / "CloudStorage" / "GoogleDrive-*" / "My Drive"),
        str(Path.home() / "Google Drive" / "My Drive"),
    ]
    candidates: list[str] = []
    for p in patterns:
        candidates.extend(sorted(glob.glob(p)))
    candidates = [p for p in candidates if Path(p).exists()]
    return {"found": bool(candidates),
            "path": candidates[0] if candidates else "",
            "candidates": candidates}


def cmd_init_repo(args: argparse.Namespace) -> dict:  # noqa: ARG001
    state = load_state()
    gdrive = state.get("gdrive_path", "").strip()
    if not gdrive:
        return {"ok": False, "error": "Google Drive path not configured. Run set-path first."}
    if not Path(gdrive).exists():
        return {"ok": False, "error": f"Google Drive path not found: {gdrive}"}

    exe = restic_path()
    if not exe:
        return {"ok": False,
                "error": "restic not installed. Run: brew install restic"}

    ensure_password()
    repo_path = str(Path(gdrive) / REPO_NAME)

    result = run_restic(["init", "--compression", "max"], repo_path)
    already_exists = (result.returncode != 0 and
                      ("already initialized" in result.stderr or
                       "config already initialized" in result.stderr))
    if result.returncode != 0 and not already_exists:
        return {"ok": False, "error": result.stderr.strip(),
                "stdout": result.stdout.strip()}

    # Verify repo is accessible
    check = run_restic(["snapshots", "--json"], repo_path)
    ok = check.returncode == 0

    if ok:
        state["repo_initialized"] = True
        state["gdrive_path"] = gdrive
        save_state(state)

    return {
        "ok": ok,
        "repo_path": repo_path,
        "password_file": str(PASS_PATH),
        "stdout": result.stdout.strip(),
        "error": "" if ok else check.stderr.strip(),
    }


def cmd_run_backup(args: argparse.Namespace) -> dict:
    state = load_state()
    gdrive = state.get("gdrive_path", "").strip()
    if not gdrive or not Path(gdrive).exists():
        return {"ok": False, "error": "Google Drive path not configured or not mounted."}
    if not state.get("repo_initialized"):
        return {"ok": False, "error": "Restic repo not initialised. Run init-repo first."}

    exe = restic_path()
    if not exe:
        return {"ok": False, "error": "restic not installed. Run: brew install restic"}

    ensure_password()
    repo_path = str(Path(gdrive) / REPO_NAME)
    dry_run = getattr(args, "dry_run", False)

    cmd = ["backup", "--compression", "max", "--json"]
    if dry_run:
        cmd.append("--dry-run")
    for exc in EXCLUDES:
        cmd += ["--exclude", exc]
    cmd.append(str(ROOT))

    result = run_restic(cmd, repo_path, timeout=1800)
    ok = result.returncode == 0

    # Parse JSON summary from stdout (restic --json emits one JSON object per line)
    snapshot_id = None
    files_new = files_changed = data_added = 0
    for line in result.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("message_type") == "summary":
            files_new      = obj.get("files_new", 0)
            files_changed  = obj.get("files_changed", 0)
            data_added     = obj.get("data_added", 0)
            snapshot_id    = obj.get("snapshot_id")

    if ok and not dry_run:
        state["last_backup"] = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        state["last_snapshot_id"] = snapshot_id
        state["files_new"] = files_new
        state["data_added_bytes"] = data_added
        save_state(state)

        # Auto-prune after each backup (non-fatal)
        run_restic(
            ["forget", "--keep-within-daily", "1m",
             "--keep-within-weekly", "3m",
             "--keep-within-monthly", "6m",
             "--prune"],
            repo_path, timeout=300,
        )

    return {
        "ok": ok,
        "dry_run": dry_run,
        "snapshot_id": snapshot_id,
        "files_new": files_new,
        "files_changed": files_changed,
        "data_added_bytes": data_added,
        "data_added_mb": round(data_added / 1_048_576, 2) if data_added else 0,
        "repo_path": repo_path,
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-2000:] if result.stderr else "",
        "error": "" if ok else result.stderr.strip(),
    }


def cmd_snapshots(args: argparse.Namespace) -> dict:
    state = load_state()
    gdrive = state.get("gdrive_path", "").strip()
    if not gdrive or not state.get("repo_initialized"):
        return {"ok": False, "snapshots": [], "error": "Repo not initialised."}

    ensure_password()
    repo_path = str(Path(gdrive) / REPO_NAME)
    limit = getattr(args, "limit", 20)

    result = run_restic(["snapshots", "--json", "--latest", str(limit)], repo_path, timeout=60)
    if result.returncode != 0:
        return {"ok": False, "snapshots": [], "error": result.stderr.strip()}

    try:
        snaps = json.loads(result.stdout)
    except json.JSONDecodeError:
        snaps = []

    # Simplify for the dashboard
    simplified = []
    for s in reversed(snaps):   # newest first
        simplified.append({
            "id":       s.get("short_id", s.get("id", "")[:8]),
            "time":     s.get("time", ""),
            "hostname": s.get("hostname", ""),
            "tags":     s.get("tags") or [],
        })
    return {"ok": True, "snapshots": simplified, "count": len(simplified)}


def cmd_prune(_args: argparse.Namespace) -> dict:
    state = load_state()
    gdrive = state.get("gdrive_path", "").strip()
    if not gdrive or not state.get("repo_initialized"):
        return {"ok": False, "error": "Repo not initialised."}

    ensure_password()
    repo_path = str(Path(gdrive) / REPO_NAME)
    result = run_restic(
        ["forget",
         "--keep-within-daily", "1m",
         "--keep-within-weekly", "3m",
         "--keep-within-monthly", "6m",
         "--prune"],
        repo_path, timeout=600,
    )
    ok = result.returncode == 0
    return {
        "ok": ok,
        "stdout": result.stdout[-4000:],
        "error": "" if ok else result.stderr.strip(),
    }


def cmd_status(_args: argparse.Namespace) -> dict:
    state = load_state()
    state["days_since_backup"] = days_since(state.get("last_backup"))
    state["overdue"]           = (state["days_since_backup"] is None
                                  or state["days_since_backup"] > 30)
    state["plist_installed"]   = PLIST_PATH.exists()
    state["restic_available"]  = restic_path() is not None
    state["restic_path"]       = restic_path()
    return state


def cmd_set_path(args: argparse.Namespace) -> dict:
    state = load_state()
    state["gdrive_path"] = args.path.strip()
    state["repo_initialized"] = False   # must re-init for new path
    save_state(state)
    return {"ok": True, "path": args.path.strip()}


def cmd_install_schedule(args: argparse.Namespace) -> dict:
    interval_hours   = getattr(args, "interval_hours", 24)
    interval_seconds = int(interval_hours) * 3600
    python_exe       = sys.executable
    script_path      = str(ROOT / "scripts" / "backup_manager.py")

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.llmwiki.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_path}</string>
        <string>run-backup</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>StandardOutPath</key>
    <string>{ROOT}/_system/docs/backup_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>{ROOT}/_system/docs/backup_launchd_err.log</string>
    <key>WorkingDirectory</key>
    <string>{ROOT}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist, encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True, check=False)
    load = subprocess.run(["launchctl", "load", str(PLIST_PATH)],
                          capture_output=True, text=True, check=False)
    state = load_state()
    state["auto_backup_installed"]    = True
    state["auto_backup_interval_hours"] = int(interval_hours)
    save_state(state)
    if load.returncode != 0:
        return {"ok": False, "error": load.stderr.strip(), "plist_path": str(PLIST_PATH)}
    return {"ok": True, "plist_path": str(PLIST_PATH), "interval_hours": int(interval_hours)}


def cmd_uninstall_schedule(_args: argparse.Namespace) -> dict:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True, check=False)
        PLIST_PATH.unlink()
    state = load_state()
    state["auto_backup_installed"] = False
    save_state(state)
    return {"ok": True}


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Restic backup manager for LLM-Wiki.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("detect-gdrive",  help="Find Google Drive mount path")
    sub.add_parser("init-repo",      help="Initialise restic repo at gdrive_path")

    run_p = sub.add_parser("run-backup", help="Create incremental snapshot")
    run_p.add_argument("--dry-run", action="store_true")

    snap_p = sub.add_parser("snapshots", help="List recent snapshots")
    snap_p.add_argument("--limit", type=int, default=20)

    sub.add_parser("prune",  help="Forget snapshots older than 6 months + prune data")
    sub.add_parser("status", help="Show backup state")

    path_p = sub.add_parser("set-path", help="Set Google Drive path")
    path_p.add_argument("--path", required=True)

    sched_p = sub.add_parser("install-schedule", help="Install LaunchAgent")
    sched_p.add_argument("--interval-hours", type=int, default=24)

    sub.add_parser("uninstall-schedule", help="Remove LaunchAgent")

    args    = parser.parse_args()
    dispatch = {
        "detect-gdrive":      cmd_detect_gdrive,
        "init-repo":          cmd_init_repo,
        "run-backup":         cmd_run_backup,
        "snapshots":          cmd_snapshots,
        "prune":              cmd_prune,
        "status":             cmd_status,
        "set-path":           cmd_set_path,
        "install-schedule":   cmd_install_schedule,
        "uninstall-schedule": cmd_uninstall_schedule,
    }

    if not args.command or args.command not in dispatch:
        parser.print_help()
        return 1

    result = dispatch[args.command](args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
