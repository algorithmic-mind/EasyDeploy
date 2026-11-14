# Threat model

Updated every phase (§10.2). Baseline: OWASP ASVS Level 2. Last update: Phase 0 (2026-11-14).

## Assets

1. Root on the host (via the agent). 2. Admin credentials, sessions, API keys. 3. Secrets in
`/etc/easydeploy/secrets` and encrypted DB fields. 4. User data: sites, apps, databases, backups.

## Trust boundaries

| Boundary | Control |
|---|---|
| Internet → Nginx | TLS, security headers/CSP, 444 for unknown hosts, optional bind domain + IP allowlist |
| Nginx → API (`api.sock`) | dir `/run/easydeploy/api` 2750 easydeploy:www-data |
| API → agent (`agent.sock`) | dir 0750 root:easydeploy (Nginx cannot reach it), bearer token, typed ops, sudo token for sensitive ops |
| API → Redis | Unix socket (group redis), password |
| Browser session | HttpOnly + SameSite=Strict cookies, CSRF header, idle/absolute timeouts, same-origin WebSocket check |

## Threats and mitigations (Phase 0)

| Threat | Mitigation | Status |
|---|---|---|
| Panel discovery / scanning | Security entrance (404 or dropped connection), random port, entrance also gates the SPA shell | ✅ |
| Password brute force | Per-IP + per-username counters, progressive delay, temporary lockout, login log | ✅ |
| Stolen password | TOTP 2FA with replay protection, recovery codes, enforceable | ✅ |
| Session hijack / CSRF | HttpOnly/Secure/SameSite=Strict cookies, CSRF on all unsafe requests incl. login | ✅ |
| Cross-site WebSocket hijacking | Origin must equal Host; session required | ✅ |
| Sensitive actions from a stolen session | Sudo mode (re-auth ≤ 10 min) for 2FA changes and API keys | ✅ |
| Command injection via API | No shell anywhere (lint), agent validators + argv lists, double validation | ✅ |
| API-layer RCE → root | Typed op registry only; sensitive ops need sudo HMAC; agent audit log. Residual: full RCE in the API can still drive non-sensitive ops (accepted, §5.3) | ⚠️ |
| Secrets in logs | structlog redaction processor, task-log redaction, secrets never returned | ✅ |
| Lockout of the admin by an attacker (username lock) | Time-limited lock; `edctl reset-password` unlocks | ⚠️ accepted |
| Tampered release | SHA-256 check of local tarballs; minisign signatures | ⏳ Phase 6 |
| Unauthenticated endpoints | Automated test enumerates all routes (`test_auth_required.py`) | ✅ |
| Docker ports bypassing UFW | Publish on 127.0.0.1 by default; DOCKER-USER management | ⏳ Phase 1/3 |

## Open items

* Self-hosted captcha after N failed logins (§9.1) — not built yet.
* CSP allows inline *styles* (Bootstrap/Vue runtime styles); scripts are strict.
* HSTS only after a real certificate is issued (Phase 2).
