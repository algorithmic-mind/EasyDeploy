# Module: accounts (+ audit)

## Purpose
Authentication and panel access security (§9.1): single admin (RBAC-ready), login with lockout, TOTP 2FA,
sudo mode, API keys, security entrance, IP allowlist, bind domain, session timeouts, login/audit logs.

## Models
* `accounts.User` — UUID pk, `role`, `language`, `timezone`, `calendar`, `theme`, `totp_secret` (encrypted),
  `totp_enabled`, `totp_last_counter`, `password_changed_at`.
* `accounts.RecoveryCode` — SHA-256 of one-time codes.
* `accounts.ApiKey` — `prefix`, `key_hash`, `scopes`, `ip_allowlist`, `expires_at`, usage, `revoked_at`.
* `audit.AuditLog`, `audit.LoginLog`.

## Endpoints (`/api/v1/auth/`)
| Method | Path | Notes |
|---|---|---|
| GET | `csrf` | sets `ed_csrftoken` |
| POST | `login` | `{status: ok|2fa_required}`; CSRF enforced; 429 `auth.locked` |
| POST | `login/2fa` | `{code}` or `{recovery_code}` |
| POST | `logout` | keeps the entrance flag |
| GET/PATCH | `me` | profile + `sudo_until`, `must_enroll_2fa` |
| POST | `sudo` | password (+ TOTP) → sudo mode |
| POST | `password` | policy: ≥12 chars, denylist, no sequences |
| POST | `2fa/setup`, `2fa/enable`, `2fa/disable`, `2fa/recovery-codes` | sudo mode |
| GET/POST/DELETE | `api-keys` | create/revoke need sudo; session only |

Audit: `GET /api/v1/audit/logs`, `GET /api/v1/audit/login-logs` (filters: module, action, actor, since, until).

## Error codes
`auth.invalid_credentials`, `auth.locked`, `auth.invalid_otp`, `auth.2fa_not_pending`, `auth.sudo_required`,
`auth.2fa_enforced`, `auth.2fa_not_enabled`, `auth.api_key_forbidden`, `auth.csrf_failed`,
`auth.not_authenticated`, `auth.authentication_failed`.

## Settings (panel registry)
`security.entrance`, `security.entrance_response` (404|drop), `security.ip_allowlist`, `security.bind_domain`,
`security.session_idle_minutes` (120), `security.session_absolute_hours` (24), `security.enforce_2fa`,
`security.login_max_failures` (5), `security.login_lockout_minutes` (15), `security.sudo_minutes` (10).

## Management commands (used by installer / edctl)
`ed_create_admin`, `ed_reset_password`, `ed_reset_2fa`, `ed_user_info`, `ed_setting`.

## Edge cases
* Locking is per IP **and** per username; `edctl reset-password` unlocks the username.
* A TOTP time step can be used once (`totp_last_counter`).
* API keys never reach `accounts` endpoints or sudo-mode actions.
* Valid API keys bypass the entrance; invalid ones get the hidden response (404/444).
