# EasyDeploy — Progress Log

> **This file is the hand-off point between sessions and between AI models.**
> Any agent (Claude, GPT, Gemini, …) continuing this work MUST:
> 1. Read `CLAUDE.md`, then this file top to bottom, then the relevant sections of `docs/MASTER_PROMPT.md`.
> 2. Continue from **"Next step"** below. Do not redo finished items.
> 3. After every finished task: update the checklist, add an entry to **Change log** (newest first),
>    record decisions under **Decisions made**, and commit.

---

## Current status

| Item | Value |
|---|---|
| Current phase | **Phase 0 — Foundation** (in progress) |
| Last updated | 2026-11-13 |
| Last agent | Claude Opus 5.5 (Claude Code) |
| Next step | See "Next step" section at the bottom |

---

## Phase 0 checklist (§15)

- [x] 0.1 Move spec to `docs/MASTER_PROMPT.md`, create `CLAUDE.md`, `docs/PROGRESS.md`
- [x] 0.2 ADR-0001..0021 for decisions D1–D21
- [ ] 0.3 Monorepo scaffold (§6): uv workspace, `.gitattributes`, `.editorconfig`, pre-commit, Makefile, CI
- [x] 0.4 Agent skeleton: UDS server, token auth, op registry, executors, locks, audit; ops `system.info`, `service.status`, `fs.list`; tests
- [x] 0.5 Django project: settings split, SQLite WAL + `monitor.db` router, Redis, Celery, Channels, DRF, drf-spectacular, structlog, error envelope
- [x] 0.6 `accounts` + `audit`: login/logout, entrance middleware, TOTP 2FA, lockout, sudo mode, API keys, login/audit logs
- [x] 0.7 `tasks`: model, helpers, WS streaming, worker-lost recovery
- [ ] 0.8 `edctl`: status, start/stop/restart, user-info, reset-password, reset-2fa, reset-entrance, set-port, doctor-lite
- [ ] 0.9 Frontend shell: layout + full menu (§2.3) with placeholders, login + 2FA, i18n en/fa, RTL, dark mode, API client, Task Center
- [ ] 0.10 Installer v0 (`--from-source` + local tarball), deploy files (systemd, nginx, logrotate)
- [ ] 0.11 Docs skeleton (`architecture.md`, `threat-model.md`, `modules/*`)
- [ ] 0.12 Local verification: lint, type check, tests, frontend build
- [ ] 0.13 VM acceptance (needs a disposable Ubuntu 24.04 VM — owner action)

### Phase 0 acceptance criteria (§15) — status

- [ ] Fresh Ubuntu 24.04 VM: one command installs in < 10 min, prints working URL; login with 2FA; survives reboot — **needs VM**
- [ ] Wrong entrance → 404/drop; 5 failed logins → lockout; `edctl reset-password` works
- [ ] Persian switches whole layout to RTL with no untranslated strings
- [ ] CI green; idle RSS measured and recorded — **needs CI run + VM**

---

## Decisions made

Small decisions taken where the spec is silent (§0). Hard-to-reverse ones get an ADR.

| Date | Decision | Reason |
|---|---|---|
| 2026-11-13 | Owner's message "start building step by step" is treated as confirmation of the Phase 0 plan (§16.3). | Owner asked to build directly. |
| 2026-11-13 | Agent dev mode (`--dev`) listens on TCP 127.0.0.1:7801 with the DryRun executor; token in `var/agent.token`. | Python on Windows has no reliable AF_UNIX server; owner develops on Windows 11 Home without WSL. Production always uses the Unix socket. |
| 2026-11-13 | Executors: `DryRunExecutor` reads the real FS, keeps writes in memory, never runs commands; `SandboxExecutor` roots all file ops under a temp dir (tests). | §5.3 rule 8 leaves the split open. |
| 2026-11-13 | Sudo token for sensitive agent ops = `<expiry>.<HMAC-SHA256(agent_token, "sudo:<actor>:<expiry>")>`, max TTL 900 s. | §5.3 names `X-Sudo-Token` without a format. |
| 2026-11-13 | `backend` is a virtual uv workspace member (not installed as a package); it runs from its directory (`pythonpath = backend`). | Avoids installing a top-level `apps` package into site-packages. |
| 2026-11-13 | mypy runs with `platform = "linux"` (targets are Linux servers). | Lets type checking work on the Windows dev machine. |
| 2026-11-13 | Ruff `PTH` rules not enabled. | `os.*` calls on fds/str paths are clearer in executor code. |
| 2026-11-13 | Entrance gates the SPA shell too: Django serves `index.html` (catch-all route), Nginx serves only `/assets/*`. Entrance flag lives in the session and survives logout. API-key requests with a *valid* key bypass the entrance. | §9.1 says unauthenticated visitors must see 404/drop; a statically served SPA would reveal the panel. |
| 2026-11-13 | `security.entrance_response = drop` → Django answers status **444**; Nginx must map it to a dropped connection (`proxy_intercept_errors` + `error_page 444 = @drop`). | Only Nginx can drop a connection. |
| 2026-11-13 | Login returns `{"status": "2fa_required"}` and stores a 5-minute pending-2FA marker in the session; `POST /auth/login/2fa` completes. Login grants sudo mode for `security.sudo_minutes` (default 10). | §9.1 "re-authentication within the last 10 minutes". |
| 2026-11-13 | API keys: `ed_<8 prefix>_<40 secret>`, SHA-256 stored; scopes `<module>:read|write` or `*:…`; `accounts` module and sudo actions are session-only. Views declare `api_module`. | §9.1 leaves scope grammar open. |
| 2026-11-13 | QR code for TOTP enrollment rendered server-side as SVG with **segno** (pure Python, BSD). | Needs one small dependency; see ADR-0022. |
| 2026-11-13 | WebSocket origin check: Origin host must equal Host (custom `SameOriginValidator`), since `ALLOWED_HOSTS=["*"]`. | Channels' AllowedHostsOriginValidator would accept any origin. |
| 2026-11-13 | Dev without Redis: LocMem cache, in-memory channel layer, Celery eager. Set `ED_REDIS_URL=redis://localhost:6379` to use Redis. | Owner develops on Windows without WSL. |
| 2026-11-13 | Backend `.po` → `.mo` compiled by `scripts/compile_messages.py` (pure Python; `--check` for CI). | GNU gettext is not available on Windows. |
| 2026-11-13 | `channels.testing` not used (it imports daphne); tests use a small `WebsocketCommunicator` in `backend/conftest.py`. | Avoid shipping/depending on daphne. |

---

## Change log (newest first)

### 2026-11-13 — Session 1 (Claude Opus 5.5)
- Initialized git repository (`main`), moved spec to `docs/MASTER_PROMPT.md`, created this file and `CLAUDE.md`.
- ADR-0001..0021 written in `docs/adr/` (one per decision D1–D21) + index.
- Root tooling: `pyproject.toml` (uv workspace: backend, agent, cli; ruff; mypy; pytest), `.gitattributes` (LF),
  `.editorconfig`, `.gitignore`, `.pre-commit-config.yaml`, `Makefile`, `scripts/check_no_shell.py`.
- Agent (`agent/easydeploy_agent`): config, errors, executors (Real/DryRun/Sandbox), locks, audit log (redaction),
  op registry (`@op`, `OpContext`, invoke with validation + lock + audit), auth (bearer + HMAC sudo token),
  FastAPI server (`/v1/health`, `/v1/ops`, `/v1/ops/{op}`, `/v1/ops/{op}/stream` NDJSON), `__main__`
  (Unix socket 0660 root:easydeploy; `--dev` TCP), validators (domain/IDNA, path, port, unit, names),
  ops `system.info`, `service.status`, `fs.list`. 63 tests passing.
- Backend (`backend/`): settings split (base/dev/prod/test) with pydantic-settings bootstrap (`easydeploy/config.py`),
  SQLite WAL + `monitor.db` router, Celery app, Channels ASGI (session auth + same-origin WS check), structlog,
  request-ID middleware, error envelope handler, typed `EASYDEPLOY` accessor (`apps/core/conf.py`),
  `EncryptedTextField` (MultiFernet), redaction helpers, agent client (UDS/TCP + NDJSON stream) + `FakeAgent`.
- `panel`: typed settings registry (`Setting` table), cached get/set with audit; `ed_setting` command; `/panel/info`.
- `accounts`: custom `User` (UUID, role, language, timezone, calendar, theme, TOTP), password policy, login with
  lockout (per IP + username, progressive delay), TOTP 2FA (QR, replay protection, 10 recovery codes), sudo mode,
  API keys with scopes, entrance / IP allowlist / bind-domain / session-timeout middleware, management commands
  (`ed_create_admin`, `ed_reset_password`, `ed_reset_2fa`, `ed_user_info`).
- `audit`: `AuditLog`, `LoginLog`, `record()` helper, read-only list APIs with filters.
- `tasks`: `Task` model, `TaskRecorder` (redacted log file + Channels group), `tracked_task` decorator,
  `start_task`, cancel, worker-lost recovery on `worker_ready`, `/ws/tasks/<id>/` consumer (replay + stream),
  diagnostics task (`POST /api/v1/tasks/diagnostics`).
- `dashboard`: `/api/v1/dashboard/system-info` via agent; `monitoring`: `HostSample` model in monitor.db.
- Persian backend catalog `backend/locale/fa/LC_MESSAGES/django.po` + compiled `.mo`.
- Security test enumerating every `/api/v1/` route for unauthenticated access (§10.2).

---

## Verification log

Commands run and their results (keep the last few sessions).

- `uv sync --all-packages --python <uv cpython 3.12.16>` → OK (Windows 11, Python 3.12.16)
- `.venv/Scripts/python -m pytest agent/tests -p no:django` → 63 passed
- `ruff check agent scripts`, `ruff format --check`, `mypy agent/easydeploy_agent` (strict) → clean
- `.venv/Scripts/python -m pytest` (agent + backend) → 124 passed, 6 skipped (public endpoints in auth test)
- `ruff check .` + `ruff format --check .` → clean; `cd backend && mypy .` → clean (89 files)
- `manage.py spectacular --validate` → 0 warnings, 0 errors

---

## Not done / known gaps

- Optional self-hosted login captcha after N failures (§9.1) — not built yet (not listed in Phase 0 deliverables).
- Audit log CSV export, panel settings UI/API (§9.17) — later phases.
- `seed_demo` management command (§12) — not built yet.

---

## Next step

Continue Phase 0 with item **0.8** (`edctl`), then 0.9 (frontend), 0.10 (installer), 0.11 (docs). 0.3 still needs CI workflows.
