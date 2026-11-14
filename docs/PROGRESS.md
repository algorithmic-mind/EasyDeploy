# EasyDeploy — Progress Log

> **This file is the hand-off point between sessions and between AI models.**
> Any agent (Claude, GPT, Gemini, …) continuing this work MUST:
> 1. Read `CLAUDE.md`, then this file top to bottom, then the relevant sections of `docs/MASTER_PROMPT.md`.
> 2. Continue from **"Next step"** below. Do not redo finished items.
> 3. After every finished task: update the checklist, add an entry to **Change log** (newest first),
>    record decisions under **Decisions made**, and commit (Conventional Commits).

---

## Current status

| Item | Value |
|---|---|
| Current phase | **Phase 0 — Foundation**: all code deliverables built and verified locally; VM/CI acceptance pending |
| Last updated | 2026-11-14 |
| Last agent | Claude Opus 5.5 (Claude Code) |
| Git | branch `main`, no remote configured yet |
| Next step | See "Next step" at the bottom |

---

## Phase 0 checklist (§15)

- [x] 0.1 Move spec to `docs/MASTER_PROMPT.md`, create `CLAUDE.md`, `docs/PROGRESS.md`
- [x] 0.2 ADR-0001..0021 for decisions D1–D21 (+ ADR-0022 segno)
- [x] 0.3 Monorepo scaffold (§6): uv workspace, `.gitattributes`, `.editorconfig`, pre-commit, Makefile, CI workflows
- [x] 0.4 Agent skeleton: UDS server, token auth, op registry, executors, locks, audit; ops `system.info`, `service.status`, `fs.list`; tests
- [x] 0.5 Django project: settings split, SQLite WAL + `monitor.db` router, Redis, Celery, Channels, DRF, drf-spectacular, structlog, error envelope
- [x] 0.6 `accounts` + `audit`: login/logout, entrance middleware, TOTP 2FA, lockout, sudo mode, API keys, login/audit logs
- [x] 0.7 `tasks`: model, helpers, WS streaming, worker-lost recovery
- [x] 0.8 `edctl`: status, start/stop/restart, logs, user-info, reset-password, reset-2fa, reset-entrance, reset-allowlist, reset-bind-domain, set-port, doctor, version
- [x] 0.9 Frontend shell: layout + full menu (§2.3) with placeholders, login + 2FA, account (2FA enrollment, password, preferences), i18n en/fa, RTL, dark mode, generated API client, Task Center
- [x] 0.10 Installer v0 (`--from-source` + local tarball), deploy files (systemd, nginx, redis, logrotate), uninstall, bats tests, build_release.sh, vm-test.sh
- [x] 0.11 Docs skeleton (`architecture.md`, `threat-model.md`, `modules/*`, user guide en/fa, README)
- [x] 0.12 Local verification: lint, type check, tests, frontend build, dev-stack smoke test, browser check (see Verification log)
- [ ] 0.13 VM acceptance on a disposable Ubuntu 24.04 VM (owner action, or push to GitHub so `installer-e2e.yml` runs)

### Phase 0 acceptance criteria (§15) — status

- [ ] Fresh Ubuntu 24.04 VM: one command installs in < 10 min, prints working URL; login with 2FA; survives reboot — **needs VM** (`scripts/vm-test.sh root@<vm>`)
- [~] Wrong entrance → 404/drop; 5 failed logins → lockout; `edctl reset-password` works — **verified by automated tests** (`apps/accounts/tests/*`, `cli/tests`), not yet on a VM
- [x] Persian switches whole layout to RTL with no untranslated strings — verified in the browser (login, overview, account, mobile 375 px) + i18n completeness test + `no-raw-text`/`no-missing-keys` lint
- [ ] CI green; idle RSS measured and recorded — **needs a GitHub remote** (workflows written: `ci.yml`, `installer-e2e.yml` measures RSS)

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
| 2026-11-13 | mypy runs with `platform = "linux"`. | Targets are Linux servers; lets type checking work on Windows. |
| 2026-11-13 | Ruff `PTH` rules not enabled; `N818` and `RUF001-003` ignored. | `os.*` on fds is clearer; domain exception names; Persian text is intentional. |
| 2026-11-13 | Entrance gates the SPA shell too: Django serves `index.html` (catch-all route), Nginx serves only `/assets/*`. Entrance flag lives in the session and survives logout. A *valid* API key bypasses the entrance. | §9.1: unauthenticated visitors must see 404/drop; a statically served SPA would reveal the panel. |
| 2026-11-13 | `security.entrance_response = drop` → Django answers status **444**; Nginx maps it to a dropped connection (`proxy_intercept_errors` + `error_page 444 = @ed_drop`). | Only Nginx can drop a connection. |
| 2026-11-13 | Login returns `{"status": "2fa_required"}` and keeps a 5-minute pending-2FA marker in the session; `POST /auth/login/2fa` completes. Login grants sudo mode for `security.sudo_minutes` (10). | §9.1 "re-authentication within the last 10 minutes". |
| 2026-11-13 | API keys: `ed_<8 prefix>_<40 secret>`, SHA-256 stored; scopes `<module>:read|write` or `*:…`; `accounts` module and sudo actions are session-only. Views declare `api_module`. | §9.1 leaves the scope grammar open. |
| 2026-11-13 | TOTP QR rendered server-side as SVG with **segno**. | ADR-0022. |
| 2026-11-13 | WebSocket origin check: Origin host must equal Host (`SameOriginValidator`), since `ALLOWED_HOSTS=["*"]`. | Channels' AllowedHostsOriginValidator would accept any origin. |
| 2026-11-13 | Dev without Redis: LocMem cache, in-memory channel layer, Celery eager. `ED_REDIS_URL=redis://localhost:6379` switches to Redis. | Windows dev machine without WSL. |
| 2026-11-13 | Backend `.po` → `.mo` compiled by `scripts/compile_messages.py` (pure Python; `--check` in CI). | GNU gettext is not available on Windows. |
| 2026-11-13 | `channels.testing` not used (imports daphne); tests use a small `WebsocketCommunicator` in `backend/conftest.py`. | Avoid depending on daphne. |
| 2026-11-14 | Frontend dependency majors pinned to the versions the code was written and verified against: vue 3.5, vue-router 4, pinia 3, vite 7, vitest 3, TypeScript 5.8, eslint 9 (newer majors exist: router 5, pinia 4, vite 8, TS 7). Upgrade later with an ADR. | Stability; avoid untested majors. |
| 2026-11-14 | npm (with `package-lock.json`) instead of pnpm. | pnpm is not installed on the owner's machine; D16 allows switching later. CI uses `npm ci`. |
| 2026-11-14 | Locale files: one JSON per module per locale, each file's top-level key is its namespace (`locales/fa/auth.json` → `{"auth": {...}}`). | Required by `@intlify/eslint-plugin-vue-i18n` key checks while keeping §6's per-module files. |
| 2026-11-14 | Panel vhost template `deploy/nginx/panel.conf.template` uses `@TOKENS@`, rendered by the installer (awk) and `edctl set-port` (Python). Moving panel config into an agent op is Phase 2 (nginx module). | edctl must work when the agent is down. |
| 2026-11-14 | Nginx: `listen … ssl http2` (not the `http2 on` directive) and a placeholder cert on the default 443 server instead of `ssl_reject_handshake`. | Ubuntu 22.04 ships nginx 1.18, 24.04 ships 1.24. |
| 2026-11-14 | Redis via an `include /etc/redis/easydeploy.conf` appended to redis.conf: socket `/run/redis/redis-server.sock` 770, `maxmemory 64mb`, `volatile-lru`, no persistence; `easydeploy` user joins group `redis`. | ADR-0008; broker keys (no TTL) are never evicted. |
| 2026-11-14 | Source installs use uv (pip-installed into a bootstrap venv) to fetch CPython 3.12 and install from `uv.lock`; release tarballs ship `python/` + `wheels/` and install with `--no-index`. | D3 bundled Python without depending on host Python. |
| 2026-11-14 | Release layout: `releases/<ver>/{app,frontend,deploy,installer,VERSION,venv→venvs/<ver>}`; units use `/opt/easydeploy/current/venv/bin/...`. ACME webroot `/opt/easydeploy/acme`. | Stable paths across upgrades. |
| 2026-11-14 | Re-running the installer requires `--reinstall` (keeps DB, secrets, admin password, entrance, port). `upgrade.sh` is a stub until Phase 6. | §8.2 "detect existing installation → offer upgrade". |
| 2026-11-14 | CSP allows inline *styles* (`style-src 'self' 'unsafe-inline'`); scripts stay strict. | Bootstrap/Vue runtime style attributes. |

---

## Change log (newest first)

### 2026-11-14 — Session 1, part 3 (Claude Opus 5.5) — preparing VM / CI acceptance
- Owner chose **GitHub Actions** for the VM test (no VPS available here; Windows Home has no WSL/Hyper-V).
- `scripts/vm-acceptance.sh`: on-server Phase 0 checks (units, doctor, TLS health, entrance 404/302, lockout 429,
  `edctl reset-password` + login, diagnostics task, idle RSS ≤ 450 MB, `--after-reboot` mode).
- `scripts/vm-test.sh`: works from Git Bash without rsync (tar over ssh), one SSH connection, CRLF cleanup,
  runs the acceptance script.
- `edctl reset-password` now clears **all** login locks (IP + username, via a generation counter) and deletes
  sessions through the session engine (cached_db cache entries too). Tests added.
- CI hardening: bandit config in `pyproject.toml` (B404/B603 skipped — argv lists are mandated; intended findings
  annotated `# nosec`), nginx template rendering through `ENVIRON` (mawk), bats negative assertions fixed,
  `edctl doctor` clock check is a warning, `installer-e2e.yml` runs the acceptance script and records install time.

### 2026-11-14 — Session 1, part 2 (Claude Opus 5.5)
- `edctl` (`cli/edctl`): Typer CLI with en/fa messages, `--json`, management commands via `runuser -u easydeploy`,
  transactional `set-port` (nginx -t + rollback + UFW), `doctor` checks (units, socket dirs, DBs, nginx, docker,
  disk, clock, panel health). 13 tests.
- Frontend (`frontend/`): Vite + Vue 3 + TS strict + Pinia + vue-i18n + Bootstrap 5.3.9 (Sass) + postcss-rtlcss +
  Bootstrap Icons + Vazirmatn (local). `api/http.ts` (CSRF, error envelope → `ApiError`, 401 handler), `api/ws.ts`
  (reconnect/backoff), `api/client.ts` (types from `schema.d.ts`, generated by openapi-typescript from
  `frontend/openapi.yaml`). Ed* wrappers (Modal, Offcanvas, Dropdown, ToastHost, Tooltip), AppSidebar (full §2.3
  menu with phase placeholders), AppTopbar (language, theme, Task Center, user menu), TaskCenter + TaskLogViewer
  (live WS log), SudoModal + `useSudo`, pages: Login (+2FA/recovery), Overview (system info + diagnostics task),
  Account (preferences, password, TOTP enrollment with recovery codes), NotFound. 14 Vitest tests (i18n parity,
  http wrapper, formatting/Jalali).
- Installer (`installer/`): `install.sh` + `lib/{common,preflight,mirrors,packages,docker,python,panel,nginx,
  firewall,systemd,summary}.sh`, mirror profiles `installer/mirrors/{global,ir,custom}.env` (ir.env left for the
  owner to fill), `uninstall.sh`, `upgrade.sh` (stub), `tests/common.bats`. shellcheck clean.
- Deploy files: systemd units + target + tmpfiles, Nginx conf.d include, default 444 servers, panel template,
  security headers + ACME snippets, Redis include, logrotate.
- Scripts: `build_release.sh` (tarball with bundled CPython + wheelhouse + frontend), `vm-test.sh`.
- CI: `.github/workflows/ci.yml` (ruff, mypy, pytest+coverage, bandit, pip-audit, OpenAPI + TS client staleness,
  eslint/prettier, vue-tsc, vitest, build, npm audit, shellcheck, bats), `installer-e2e.yml` (fresh-runner install,
  doctor, reinstall, idle RSS, uninstall on 22.04/24.04), `release.yml` (amd64/arm64 tarballs).
- Docs: `architecture.md`, `threat-model.md`, `modules/{accounts,tasks,agent,installer}.md`,
  `user-guide/{en,fa}/README.md`, root `README.md`.
- Fixes found by the smoke/browser test: CSRF failures now return `auth.csrf_failed`; LTR islands are excluded
  from rtlcss flipping (`/* rtl:begin:ignore */`); only technical values (hostname, OS, kernel) are LTR islands.

### 2026-11-13 — Session 1, part 1 (Claude Opus 5.5)
- Git repo, spec moved to `docs/MASTER_PROMPT.md`, `CLAUDE.md`, this file, ADR-0001..0022.
- Root tooling: uv workspace, ruff, mypy, pytest config, `.gitattributes` (LF), `.editorconfig`, pre-commit,
  `Makefile`, `scripts/check_no_shell.py`, `scripts/compile_messages.py`.
- Agent: config, errors, executors (Real/DryRun/Sandbox), locks, audit log, op registry, auth (bearer + HMAC sudo
  token), FastAPI server (health, ops listing, invoke, NDJSON stream), Unix-socket main, validators, ops
  `system.info`, `service.status`, `fs.list`. 63 tests.
- Backend: settings split + pydantic-settings bootstrap, SQLite WAL + monitor.db router, Celery, Channels ASGI,
  structlog, request IDs, error envelope, encrypted fields, redaction, agent client + FakeAgent; apps `core`,
  `panel` (typed settings registry), `accounts`, `audit`, `tasks`, `dashboard`, `monitoring`; Persian catalog;
  route-enumerating auth test.

---

## Verification log

Commands run on 2026-11-14 (Windows 11, Python 3.12.16 via uv, Node 24.18):

- `.venv/Scripts/python -m pytest` → **138 passed**, 6 skipped (skips = public endpoints in the auth-required test)
- `ruff check .`, `ruff format --check .` → clean · `mypy agent/easydeploy_agent cli/edctl` (strict) → clean ·
  `cd backend && mypy .` → clean (90 files)
- `python scripts/check_no_shell.py` → OK · `python scripts/compile_messages.py --check` → OK
- `manage.py spectacular --validate --fail-on-warn` → 0 warnings; regenerated `openapi.yaml`/`schema.d.ts` unchanged
- `cd frontend && npm run lint && npx vue-tsc -b && npx vitest run && npm run build` → clean, 14 tests, build OK
  (CSS has 537 `[dir=rtl]` rules)
- `shellcheck -x installer/*.sh installer/lib/*.sh scripts/*.sh` → 0 findings · `bash -n` on all scripts → OK
- Dev-stack smoke test (agent `--dev` + uvicorn + dev settings): health, panel info, 401 for anonymous, CSRF
  required on login, wrong password 400, login OK, `system-info` through the real agent client over TCP,
  diagnostics task 202 → succeeded with log lines, OpenAPI schema served.
- Browser (built-in, Vite dev server): login page en/fa, overview, Task Center live log over WebSocket, Persian
  RTL + dark theme, account page 2FA QR, 375 px mobile without horizontal scroll.
- **Not run here:** bats (not installed on Windows), installer on a VM, CI on GitHub, idle RSS measurement.

---

## Not done / known gaps

- Phase 0 VM acceptance (install < 10 min, reboot survival, entrance/lockout/reset-password on a real host) — needs
  a disposable Ubuntu 24.04 VM: `scripts/vm-test.sh root@<vm-ip>`.
- CI has never run: the repository has no GitHub remote yet.
- Idle RSS (≤ 450 MB target) not measured yet (`installer-e2e.yml` prints it).
- Optional self-hosted login captcha after N failures (§9.1) — not built.
- Signed releases / minisign, bundled lego, offline bundle, `edctl update/rollback`, `upgrade.sh` — Phase 6.
- `installer/mirrors/ir.env` has no mirror URLs: the owner must fill in trusted mirrors (§11 forbids hardcoding).
- `seed_demo` management command (§12) — not built. Playwright E2E — not set up yet.
- After login the UI switches to the user's *saved* language, even if another language was picked on the login page.
- License (D21) still TBD.

---

## How to run locally (Windows, no WSL)

```bash
python -m uv sync --all-packages                       # .venv with Python 3.12
.venv/Scripts/python -m easydeploy_agent --dev         # terminal 1 (agent, dry-run)
cd backend && ../.venv/Scripts/python manage.py migrate && ../.venv/Scripts/python manage.py migrate --database monitor
../.venv/Scripts/python manage.py ed_create_admin      # prints a password
cd .. && .venv/Scripts/python -m uvicorn easydeploy.asgi:application --app-dir backend --port 8000   # terminal 2
cd frontend && npm install && npm run dev               # terminal 3 → http://localhost:5173
```
(`DJANGO_SETTINGS_MODULE` defaults to `easydeploy.settings.dev` via `manage.py`; for uvicorn set
`DJANGO_SETTINGS_MODULE=easydeploy.settings.dev`.)

---

## Next step

1. **Owner action:** create an empty GitHub repository (private is fine), then
   `git remote add origin <url> && git push -u origin main`. `ci.yml` runs on push; start
   **Actions → Installer E2E → Run workflow** manually. Read both results (install time, RSS, acceptance
   PASS/FAIL lines are in the job logs / step summary) and record them here.
   Alternative with a VPS: `scripts/vm-test.sh root@<disposable-vm>`, reboot, then
   `sudo bash /root/easydeploy-src/scripts/vm-acceptance.sh --after-reboot`.
2. Fix whatever the VM/CI run reveals, then mark 0.13 and the acceptance criteria.
3. Start **Phase 1 — Host essentials** (§15): Dashboard live metrics + monitoring history (monitor.db collectors,
   ECharts), Files (agent `fs.*` ops, chunked upload, archives with zip-slip protection, Monaco editor), Terminal
   (agent `/v1/pty`, xterm.js, sudo mode), Containers (docker SDK ops, compose stacks), Logs viewers, Processes &
   Services. Use the Phase N kickoff prompt from `docs/MASTER_PROMPT.md` Appendix C.
