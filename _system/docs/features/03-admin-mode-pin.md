# 03 · Admin mode (PIN-protected) with email recovery

## What it does
- The dashboard top bar has a `🔒 Admin: Off` toggle.
- Privileged edits (currently: editing project managers) are gated behind a **4–8 digit PIN**.
- A **recovery email** is collected at setup so the PIN can be reset later.
- The unlocked state is **session-scoped** (cleared when the browser tab closes).

## First-time setup
On the first click of the toggle, a **Setup modal** asks for:
- PIN (4–8 digits, confirmed twice)
- Recovery email

After save, the PIN hash + recovery email are written to `_system/admin/admin_config.json` (gitignored, chmod 600).

## Unlocking later
- Click the toggle → **Enter PIN** modal → verified server-side → tab becomes admin-unlocked.
- A `Forgot PIN?` link is shown.

## Forgot PIN (recovery flow)
1. Confirm the recovery email.
2. Server generates a 6-digit code, hashes it, stores expiry (15 min).
3. If SMTP env vars are set, the code is **emailed** to the recovery address.
4. If SMTP is **not configured**, the code is printed to the dashboard-server terminal as a fallback.
5. Enter code + new PIN → server resets the PIN hash.

## SMTP environment variables (for real email delivery)
```bash
export DASHBOARD_SMTP_HOST=smtp.gmail.com
export DASHBOARD_SMTP_PORT=587
export DASHBOARD_SMTP_USER=user@example.com
export DASHBOARD_SMTP_PASSWORD=<gmail-app-password>   # not your account password
export DASHBOARD_SMTP_FROM=user@example.com      # optional; defaults to USER
python3 scripts/dashboard_server.py --port 8765
```

Gmail requires an [App Password](https://myaccount.google.com/apppasswords) — not your regular password.

## Security details
- Hashing: **PBKDF2-HMAC-SHA256, 200 000 iterations** with a per-install random salt.
- Constant-time comparison via `hmac.compare_digest`.
- The dashboard server binds to **127.0.0.1** only; no remote access by default.
- Session-scoped: the PIN is cached in `sessionStorage` only for the current tab; closing the tab locks admin again.

## Server API
| Action | Description |
|---|---|
| `admin-status` | Reports whether PIN is configured; returns masked recovery email and SMTP-configured flag. |
| `admin-setup` | First-time setup; stores hash + recovery email. |
| `admin-verify` | Verifies a PIN; called from the Unlock modal. |
| `admin-request-reset` | Generates a 6-digit code, hashes & stores expiry, sends or prints. |
| `admin-reset-pin` | Verifies the code and writes the new PIN. |

## Files
- `_system/admin/admin_config.json` (gitignored)
- Server helpers in `scripts/dashboard_server.py`: `_load_admin_config`, `_hash_pin`, `_send_reset_email`, `handle_admin_action`, `_require_admin_unlocked`.
- UI: `_system/dashboard/app.js` — `openAdminSetupModal`, `openAdminUnlockModal`, `openForgotPinModal`.
