# EasyDeploy — Master Engineering Prompt

<div dir="rtl">

## راهنمای استفاده (فارسی)

این فایل «پرامپت مادر» پروژه **EasyDeploy** است: یک پنل مدیریت سرور مشابه 1Panel که با **Django و Python** ساخته می‌شود و با **یک دستور** روی یک **Ubuntu Server خام** نصب می‌شود. با آن می‌شود پروژه‌هایی با فناوری‌های مختلف را دیپلوی کرد، برنامه‌های آماده (وردپرس و…) و انواع دیتابیس را نصب کرد، و دامنه، SSL، فایل‌ها، کانتینرها، فایروال، بکاپ و… را مدیریت کرد.

متن اصلی عمداً **انگلیسی** نوشته شده، چون مدل‌ها و ابزارهای کدنویسی هوش مصنوعی مشخصات فنی انگلیسی را دقیق‌تر و بدون ابهام اجرا می‌کنند. در بخش ۱۶ از عامل هوش مصنوعی خواسته شده **با شما فارسی صحبت کند** و کد، کامنت و کامیت‌ها را انگلیسی بنویسد.

**قبل از شروع:**

1. جدول **بخش ۴ (Locked Decisions)** را مرور کنید. اگر می‌خواهید تصمیمی را عوض کنید (مثلاً نام پروژه، فریم‌ورک فرانت‌اند یا لایسنس)، همان‌جا قبل از شروع عوض کنید.
2. برای شروع هر فاز، پرامپت کوتاه همان فاز را از **پیوست C** کپی کنید و بفرستید. هر فاز را در یک نشست (session) تازه شروع کنید؛ پیوستگی کار از طریق فایل `docs/PROGRESS.md` حفظ می‌شود.
3. فاز ۰ این فایل را به `docs/MASTER_PROMPT.md` منتقل می‌کند و یک `CLAUDE.md` می‌سازد که به آن ارجاع می‌دهد.
4. نصب‌کننده و هر عملیاتی که سرور را تغییر می‌دهد را فقط روی **یک VPS یا ماشین مجازی یک‌بارمصرف** تست کنید، نه روی سیستم شخصی.
5. بخش ۳ خلاصهٔ بررسی ساختار 1Panel (نسخه 2.5.1، بررسی‌شده در ۲۰۲۶-۱۱-۱۳) است. کد 1Panel لایسنس GPL-3.0 دارد؛ فقط از ایده‌ها و قابلیت‌هایش الهام می‌گیریم و هیچ کدی از آن کپی نمی‌شود.

</div>

---

## 0. How to use this document (instructions to the AI agent)

You are reading the single source of truth for building EasyDeploy. Treat it as a binding specification:

- **Sections 4–14 are requirements.** Follow them unless the owner explicitly approves a change. Record every approved deviation as an ADR in `docs/adr/`.
- **Section 15 is the roadmap.** Work strictly phase by phase. Do not start a phase before the previous phase meets its acceptance criteria.
- **Section 16 is your working protocol.** Read it before writing any code, every session.
- When this document is silent on a detail, choose the simplest option consistent with the architecture, note it in `docs/PROGRESS.md` under "Decisions made", and continue. Ask the owner only when a choice is hard to reverse (data model shape exposed to users, security boundary, public file formats, external dependencies that are heavy or license-sensitive).
- Keywords: **MUST** = mandatory, **SHOULD** = default unless there is a documented reason, **MAY** = optional, **LATER** = out of scope until the phase that names it.

---

## 1. Role & mission

Act as a **senior full-stack platform engineer** with deep experience in Linux server administration (Ubuntu, systemd, Nginx, Docker, UFW, OpenSSH), Django/DRF/Channels/Celery, Vue 3 + TypeScript, shell scripting, and application security.

Mission: build **EasyDeploy**, an open, self-hosted, web-based server control panel that:

1. Installs on a **fresh Ubuntu Server** (22.04 / 24.04 / 26.04 LTS, amd64 and arm64) with **one command**, in under 10 minutes, with no manual steps.
2. Lets a single administrator (multi-user LATER) **deploy projects of any common stack** (Python, Node.js, PHP, Go, Java, .NET, static sites, Docker images, Docker Compose) from Git or uploads, with domains and automatic HTTPS.
3. Provides an **App Store** of ready-made Docker-based apps (WordPress, databases, tools) with one-click install, upgrade, backup, and domain binding.
4. Manages **databases** (MySQL, MariaDB, PostgreSQL, Redis, MongoDB), **domains/DNS/SSL**, **websites (Nginx)**, **containers**, **files**, **terminal**, **firewall/SSH/security**, **cron jobs**, **backups/snapshots**, **monitoring**, **logs**, and **notifications**.
5. Is **secure by default**, light enough for a **1 vCPU / 1 GB RAM** VPS, works in **network-restricted regions** through configurable mirrors and offline bundles, and has a **bilingual UI (English + Persian, full RTL)**.

---

## 2. Product vision & scope

### 2.1 Personas

- **Solo developer / freelancer**: has a few VPSs, wants to push a Git repo and get `https://app.example.com` without writing Nginx configs.
- **Small agency**: hosts many WordPress/PHP sites and a few Node/Python apps per server; needs backups and SSL renewals to work unattended.
- **Self-hoster**: installs apps (Nextcloud, Gitea, n8n, Uptime Kuma…) and databases with one click.

### 2.2 Product principles

1. **One command to install, one click to operate.** Every common task completes from the UI without SSH.
2. **The panel never leaves the server broken.** Every config change is validated before it is applied, and rolled back automatically if validation or reload fails.
3. **Transparent, not magic.** Generated configs, compose files, and commands are visible (read-only "view generated config"); advanced users MAY override through validated escape hatches.
4. **Declarative state, reconciled.** The panel database stores the desired state; the agent reports actual state; drift is shown and can be repaired.
5. **Everything long-running is a Task** with live logs, progress, cancel (where possible), and history.
6. **Offline-capable.** Every external download (apt, Docker images, Python wheels, app catalog, releases) goes through a configurable source.

### 2.3 Main navigation (UI information architecture)

| Menu | Sub-pages |
|---|---|
| Overview | Dashboard (system info, live metrics, installed apps, quick actions) |
| App Store | Browse (categories, search), Installed, Updates |
| Projects | Projects list, Project detail (Deployments, Processes, Environment, Domains, Logs, Webhooks, Settings), Git credentials |
| Websites | Sites, Runtimes (PHP) |
| Domains & SSL | Domains, DNS accounts, DNS zones (records), Certificates, ACME accounts |
| Databases | Servers (local/remote) per engine, Databases, Users |
| Containers | Containers, Compose stacks, Images, Networks, Volumes, Registries, Docker settings |
| Files | File manager, Recycle bin |
| Terminal | Local host, Saved SSH hosts, Container exec, Command snippets |
| Host | Monitoring (history), Processes, Services (systemd), Firewall, SSH, Fail2ban, Disks, Network |
| Cron Jobs | Jobs, Run history |
| Backups | Backup records, Backup accounts (storage targets), Snapshots |
| Logs | Audit log, Login log, Task log, System logs (journald), Website logs |
| Toolbox | System cleanup, Swap, Time & NTP, Hostname & hosts file, Antivirus (ClamAV), Daemons (custom systemd services), Script library |
| Settings | General, Security, Notifications, Network & Mirrors, Updates, About |

---

## 3. Reference analysis: 1Panel v2 (what we emulate, what we improve)

Facts below were collected from 1panel.pro, the 1Panel GitHub repository (branch `dev-v2`), and the 1Panel app store repository on 2026-11-13 (latest stable: **v2.5.1**). Items marked *(inferred)* were not directly confirmed.

### 3.1 Architecture of the reference

- **Backend:** Go, two binaries: `1panel-core` (main panel: auth, settings, logs, backups, routing) and `1panel-agent` (host operations, cron). The agent split is what enables Pro multi-node management.
- **Panel storage:** SQLite through GORM, with versioned migrations *(inferred from dependencies)*.
- **Frontend:** Vue 3 + TypeScript + Vite + Element Plus + Pinia + vue-router + vue-i18n + ECharts + xterm.js + Monaco/CodeMirror + noVNC.
- **Frontend view folders (≈ main modules):** `home`, `app-store`, `website`, `database`, `container`, `host` (files, monitor, firewall, SSH, process, disk *(inferred)*), `terminal`, `cronjob`, `log`, `toolbox`, `ai`, `vm`, `setting`, `login`.
- **Auth capabilities in dependencies:** TOTP, WebAuthn, OIDC, SAML, LDAP. Access uses `http://<ip>:<port>/<security-entrance-path>`; credentials are retrieved with the CLI `1pctl user-info`.
- **App store:** 185+ Docker Compose apps in categories: AI, Website, Database, Server, Runtime, Tools, Storage, BI, CRM, Security, DevTool, DevOps, Middleware, Media, Email, Game. Runtime apps include PHP 5/7/8, Java, Node.js, Go, Python, .NET. Web servers available as apps: OpenResty (default for websites), Caddy, OpenLiteSpeed, Nginx Proxy Manager.
- **App package format:** `apps/<app>/data.yml` (metadata, multilingual descriptions including `fa`, architectures, `crossVersionUpdate`), `logo.png`, `README*.md`, and one folder per version containing `data.yml` (form fields with `envKey`, type `text|password|number|apps|service`, `default`, `random`, validation `rule`, multilingual labels), `docker-compose.yml`, and `conf/`. Apps join an external Docker network (`1panel-network`). The panel injects variables such as `CONTAINER_NAME`. Dependencies (e.g., WordPress → MySQL/MariaDB) are expressed only as an `apps`-type form field with a child `service` field.
- **Installer:** `bash -c "$(curl -sSL https://resource.1panel.pro/v2/quick_start.sh)"` → detects architecture → fetches latest version → downloads the release tarball → runs the bundled `install.sh` (Docker install, port, entrance, credentials happen there *(inferred)*).
- **Pro-only features:** multi-node management, advanced WAF, website tamper protection, website uptime monitoring/reports, website backup, GPU monitoring, MCP server management, scheduled virus scanning, custom branding, custom app store URL.

### 3.2 What EasyDeploy keeps

The module set (§2.3), the security entrance + CLI recovery model, a Docker Compose-based app store with typed install forms, Docker-isolated runtimes, a core/agent split, SQLite as default panel storage, a Vue 3 SPA with xterm.js/Monaco/ECharts.

### 3.3 What EasyDeploy does better (requirements, not suggestions)

| Area | Reference behavior | EasyDeploy requirement |
|---|---|---|
| Installer integrity | Download uses `curl -k` (TLS verification off); a freshly downloaded tarball is not checked against `checksums.txt` | `curl -fsSL` only; **always** verify SHA-256 **and** a minisign signature before extracting; fail closed |
| Privilege model | Panel runs as root *(inferred)* | Unprivileged web/API process; all root work goes through a typed, validated **agent** API (§5.3) |
| App dependencies | Implicit, via form-field types | Explicit `requires:` block with provisioning (create DB + user automatically), health checks, backup spec, upgrade rules (§9.4, Appendix A) |
| Git deployment | Runtimes + manual setup | First-class **Projects** module: Git → build → zero-downtime deploy → rollback, webhooks (§9.7) |
| Web server | OpenResty as a container app | Native Nginx managed by the agent with transactional apply + rollback (§9.5) |
| Persian users | `fa` descriptions in catalog | Full **RTL** UI, Persian locale, optional Jalali dates, Bale/Telegram notifications, ArvanCloud DNS (§10.4) |
| Restricted networks | — | Mirror profiles + full offline install bundle (§11) |
| Free features | Multi-node, website backup, uptime monitoring are Pro | Website backup in core; uptime monitoring and multi-node on the roadmap (§15) |

### 3.4 Legal

1Panel is **GPL-3.0**. EasyDeploy is a **clean-room implementation**: do not copy 1Panel source code, app catalog files, UI assets, texts, or branding. Feature inspiration only.

---

## 4. Locked technical decisions (owner-editable)

The owner MAY edit this table **before Phase 0**. After Phase 0, a change requires an ADR.

| # | Topic | Decision |
|---|---|---|
| D1 | Product name / slugs | **EasyDeploy**; slug `easydeploy`; CLI `edctl`; Docker network `easydeploy-net`; Docker label prefix `io.easydeploy.`; release host placeholder `get.easydeploy.example` (replace with the owner's domain) |
| D2 | Target OS | Ubuntu Server 22.04, 24.04, 26.04 LTS; amd64 + arm64; systemd required. Other distros LATER |
| D3 | Python | CPython **3.12**, bundled with the release (python-build-standalone) so the host Python version does not matter |
| D4 | Backend framework | **Django 5.2 LTS** + Django REST Framework + drf-spectacular (OpenAPI 3) + django-filter |
| D5 | Realtime | **Django Channels 4** (ASGI) served by **Uvicorn**; channel layer on Redis |
| D6 | Background jobs | **Celery 5** + Redis broker; **django-celery-beat** (database scheduler) for cron jobs |
| D7 | Panel database | **SQLite** in WAL mode (`panel.db`) + separate `monitor.db` for metrics (Django multi-DB router). Code MUST stay database-agnostic so PostgreSQL can be swapped in |
| D8 | Internal Redis | Ubuntu `redis-server` (or `valkey-server` where Redis is not packaged), Unix socket only, password protected, panel-internal (never used for user apps) |
| D9 | Privileged agent | Separate Python service `easydeploy-agent`, runs as root, **FastAPI over a Unix domain socket**, Pydantic v2 schemas, Jinja2 templates; Docker via the `docker` Python SDK + `docker compose` CLI |
| D10 | Web server for sites & panel | Native **Nginx** from Ubuntu repositories, managed only by the agent |
| D11 | ACME / SSL | **lego** CLI (single Go binary, 150+ DNS providers incl. Cloudflare and ArvanCloud), driven by the agent |
| D12 | Containers | Docker Engine CE + Compose v2 plugin from the official Docker apt repo (or mirror) |
| D13 | Frontend | **Vue 3 + TypeScript (strict) + Vite + Pinia + Vue Router + vue-i18n**; UI framework **Bootstrap 5.3.x — latest stable, currently 5.3.9** (released 2026-11-11), compiled from its Sass sources with the project's theme variables; **Bootstrap Icons** bundled locally; Bootstrap's own ES-module JavaScript (modal, dropdown, tooltip, toast, offcanvas, collapse) wrapped in thin in-house Vue components (§13.2). No jQuery, and no third-party Vue–Bootstrap wrapper library without an ADR. RTL through the officially supported RTLCSS approach (§10.4); dark mode through Bootstrap color modes (`data-bs-theme`). Bootstrap 6 is only an alpha: do not use it; migrating is a later ADR once it is stable. ECharts, xterm.js, Monaco; API client generated from OpenAPI |
| D14 | Frontend delivery | Prebuilt static bundle shipped inside the release; **no Node.js on the server** |
| D15 | Python tooling | **uv** workspace (`backend`, `agent`, `cli`), `uv.lock`; ruff, mypy (django-stubs, djangorestframework-stubs) |
| D16 | Frontend tooling | Node 24 LTS, pnpm, Sass (`sass-embedded`), PostCSS with `postcss-rtlcss`, ESLint, Prettier, Vitest, Playwright |
| D17 | Backup format | tar + zstd; optional encryption in **age** format (pyrage) so backups can be decrypted with the standard `age` CLI outside the panel |
| D18 | Logging | structlog JSON logs; request ID propagated API → worker → agent |
| D19 | Users | Single admin in MVP; data model and permission layer designed for RBAC (admin/operator/viewer) LATER |
| D20 | UI languages | English (default) + Persian (RTL); every user-facing string translatable from day one |
| D21 | License | **TBD by owner before first public release** |

---

## 5. System architecture

### 5.1 Component diagram

```
                                   Internet
                                      │
                  ┌───────────────────┴────────────────────┐
                  │ Nginx (host, managed by agent)          │
                  │  :80/:443  → user sites / apps / projects│
                  │  :<panel_port> (TLS) → panel             │
                  └──────┬────────────────────────┬─────────┘
       static SPA files  │ proxy (HTTP + WS)      │ proxy_pass / fastcgi / static roots
       served directly   ▼                        ▼
             ┌──────────────────────┐   ┌──────────────────────────────────────┐
             │ easydeploy-api        │   │ Docker containers on easydeploy-net   │
             │ Django ASGI (Uvicorn) │   │  apps · projects · DBs · PHP-FPM      │
             │ DRF + Channels        │   │  ports published on 127.0.0.1 only    │
             │ user: easydeploy      │   └──────────────────────────────────────┘
             └───┬────────────┬─────┘                    ▲
                 │ Redis      │ HTTP/WS over UDS         │ docker.sock
                 │ (unix sock)│ agent.sock (see §5.3)     │
   ┌─────────────▼──────────┐ │                ┌─────────┴──────────────────────────┐
   │ easydeploy-worker       │─┴──────────────►│ easydeploy-agent (root)             │
   │ Celery worker (+ beat)  │                 │ typed ops: docker, nginx, lego, fs,  │
   │ user: easydeploy        │                 │ ufw, sshd, fail2ban, systemd, pty... │
   └─────────────────────────┘                 └────────────────────────────────────┘
   Storage: /opt/easydeploy/data/panel.db, monitor.db   Secrets: /etc/easydeploy/
```

### 5.2 Processes (systemd units)

| Unit | User | Command | Notes |
|---|---|---|---|
| `easydeploy-agent.service` | root | `python -m easydeploy_agent` | Starts first; creates `/run/easydeploy/agent/agent.sock` |
| `easydeploy-api.service` | easydeploy | `uvicorn easydeploy.asgi:application --uds /run/easydeploy/api/api.sock --workers 2` | `After=easydeploy-agent.service redis-server.service` |
| `easydeploy-worker.service` | easydeploy | `celery -A easydeploy worker -B -Q default,deploy,backup,monitor --concurrency 2` | Beat embedded on single node to save RAM; separate `easydeploy-beat.service` MAY be used for multi-node LATER |
| `easydeploy.target` | — | groups the units | `edctl start/stop/restart` act on the target |

**Socket directories** (created by a `tmpfiles.d` entry, because two services with different users share `/run/easydeploy`):

| Path | Owner : group | Mode | Who may connect |
|---|---|---|---|
| `/run/easydeploy/agent/` → `agent.sock` | root : easydeploy | dir 0750, socket 0660 | api + worker only |
| `/run/easydeploy/api/` → `api.sock` | easydeploy : www-data | dir 0750, socket 0660 | Nginx (`www-data`) only |

Nginx MUST NOT be able to reach the agent socket. Do not add `www-data` to the `easydeploy` group.

Hardening for non-root units: `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ReadWritePaths=` only for the panel data/log/tmp dirs, `PrivateTmp=yes`, `ProtectHome=yes`, `RestrictSUIDSGID=yes`, `MemoryMax=` sane limits, `Restart=on-failure`.

### 5.3 Privilege separation & agent protocol

**Why:** a web-layer bug (path traversal, injection, SSRF, deserialization) must not translate directly into root command execution. The agent only accepts **typed operations with validated parameters**; it never executes raw shell strings received from the API. Be honest about the limit: the panel admin is root-equivalent by design (terminal, scripts), and full remote code execution inside the API process can still drive the agent. The split is defense in depth plus the foundation for multi-node, not an absolute boundary.

**Transport:** HTTP/1.1 over Unix socket `/run/easydeploy/agent/agent.sock`. Auth: socket permissions (§5.2) **and** a bearer token stored in `/etc/easydeploy/secrets/agent.token` (0640 root:easydeploy). Multi-node LATER: same API over TCP with mutual TLS.

**Endpoints:**

- `POST /v1/ops/{op_name}` → `{"ok": true, "result": {...}}` or `{"ok": false, "error": {"code", "message", "details"}}`
- `POST /v1/ops/{op_name}/stream` → NDJSON event stream (`log`, `progress`, `result`, `error`) for long operations (image pull, compose up, cert issue, backup)
- `WS /v1/pty` → interactive PTY (host shell, `docker exec`), resize + input/output frames
- `GET /v1/health`, `GET /v1/ops` (registry listing with JSON schemas)

**Headers:** `Authorization: Bearer …`, `X-Request-ID`, `X-Actor` (panel user id, recorded in the agent's own audit log), `X-Sudo-Token` for operations flagged `sensitive`.

**Op registry rules (MUST):**

1. Every op is declared with `@op(name, params=Model, result=Model, lock=..., sensitive=bool, timeout=...)` (see Appendix B).
2. Parameters are Pydantic models with strict validators: domains (IDNA/punycode, RFC 1035 labels), ports (1–65535, reserved-port rules), paths (normalized, symlinks resolved, allow/deny roots), systemd unit names, usernames, Docker resource names.
3. Subprocesses use **argument lists only** (`subprocess.run([...], shell=False)`), explicit timeouts, minimal environment, captured output.
4. Config files are rendered **by the agent** from its own Jinja2 templates using structured input. The API never sends a full config file. Escape hatches (custom Nginx directives) pass through an allowlist validator (forbid `load_module`, `user`, `include` outside managed dirs, `lua_*`, `root`/`alias` outside allowed roots, etc.).
5. Mutating ops on shared resources take a named lock (`nginx`, `ufw`, `docker-network`, `apt`, `app:<id>`), so concurrent tasks cannot corrupt state.
6. Every config mutation is **transactional**: write to staging → validate (`nginx -t`, `sshd -t`, `docker compose config`, `fail2ban-client -t`…) → atomic swap → reload → health-check → on any failure restore the previous files and report the validator's stderr.
7. The agent keeps its own append-only audit log (`/var/log/easydeploy/agent-audit.log`).
8. **Executor abstraction:** `RealExecutor` (production), `DryRunExecutor` (logs argv, returns canned results), `SandboxExecutor` (file ops rooted under a temp dir). Tests and Windows/WSL development use the non-real executors.

**Op namespaces (initial):** `system.*` (info, hostname, timezone, reboot), `service.*` (systemd), `pkg.*` (allowlisted apt packages), `fs.*`, `docker.*`, `compose.*`, `nginx.*`, `cert.*`, `ufw.*`, `sshd.*`, `fail2ban.*`, `proc.*`, `disk.*`, `swap.*`, `user.*` (Linux users for SFTP LATER), `db.*` (dump/restore via `docker exec`), `backup.*`, `script.*` (run stored admin scripts, `sensitive`), `pty.*`, `panel.*` (self-update, snapshot).

### 5.4 Task system & realtime

- `Task` model: `id (UUID)`, `kind`, `title (i18n key + params)`, `status (pending|running|succeeded|failed|cancelled)`, `progress (0–100)`, `resource_type`, `resource_id`, `created_by`, `started_at`, `finished_at`, `log_path`, `result (JSON)`, `error (JSON)`, `parent_id` (sub-tasks).
- Every operation that may exceed ~2 seconds, or that touches the agent's streaming ops, MUST run as a Celery task and return `202 {"task_id": ...}`.
- Task logs are appended to `/opt/easydeploy/logs/tasks/<id>.log` and published to the Channels group `task.<id>`. WebSocket `/ws/tasks/<id>/` replays the existing log, then streams.
- A global **Task Center** drawer in the UI shows running and recent tasks.
- On worker start, tasks left in `running` from a crash are marked `failed (worker_lost)`.
- Queues: `default` (short ops), `deploy` (builds, concurrency 1), `backup` (concurrency 1), `monitor` (metrics collection).

**WebSocket endpoints:** `/ws/tasks/<id>/`, `/ws/monitor/live/`, `/ws/terminal/<session>/`, `/ws/containers/<id>/logs/`, `/ws/projects/<id>/logs/`. All require an authenticated session; terminal also requires sudo mode.

### 5.5 Data & configuration

- Bootstrap config: `/etc/easydeploy/easydeploy.env` (paths, ports, listen addresses, Redis socket, debug off), read through pydantic-settings.
- Secrets: `/etc/easydeploy/secrets/` (Django `SECRET_KEY`, Fernet keys for field encryption, agent token, Redis password), 0640 root:easydeploy.
- Runtime settings (editable in UI): `Setting` key/value table with a typed registry (Pydantic) and caching.
- Sensitive fields (DB passwords, DNS API tokens, registry passwords, backup credentials, SSH keys, env vars marked secret) use an `EncryptedTextField` (Fernet via `cryptography`, `MultiFernet` for key rotation). Secrets are never returned by list/detail endpoints; a separate `reveal` endpoint requires sudo mode and is audited.
- SQLite: WAL, `synchronous=NORMAL`, `busy_timeout=5000`, `transaction_mode="IMMEDIATE"`; nightly `VACUUM`/backup of `panel.db` to `/opt/easydeploy/backups/panel/`.

### 5.6 Reference flow — "Install WordPress and bind a domain"

1. UI posts the install form → API validates params (serializer) → creates `AppInstance(status=installing)` + `Task` → returns 202.
2. Worker: resolve `requires.db` (existing MariaDB instance or install one first as a sub-task) → `db.provision` (create DB + user) → render `.env` + compose into `/opt/easydeploy/apps/wordpress/<instance>/` → agent `compose.pull` (stream progress) → `compose.up` → wait for health check → status `running`.
3. User clicks "Bind domain" → API creates `Website(type=proxy, upstream=127.0.0.1:<port>)` + `Domain` → task: DNS check → agent `nginx.site.apply` (transactional) → `cert.issue` (HTTP-01) → `nginx.site.apply` with TLS → done; notification sent.

---

## 6. Repository layout (monorepo)

```
easydeploy/
├── pyproject.toml                 # uv workspace root (members: backend, agent, cli)
├── uv.lock
├── backend/
│   ├── pyproject.toml
│   ├── manage.py
│   ├── easydeploy/                # Django project package
│   │   ├── settings/{base,dev,prod,test}.py
│   │   ├── urls.py  asgi.py  routing.py  celery.py  db_routers.py
│   └── apps/
│       ├── core/                  # base models, mixins, errors, pagination, permissions,
│       │                          # encryption fields, agent client, locks, i18n helpers
│       ├── accounts/              # custom User, auth, 2FA, sessions, API keys, sudo mode
│       ├── audit/                 # audit log, login log
│       ├── tasks/                 # Task model, runner helpers, WS consumers
│       ├── dashboard/
│       ├── monitoring/            # collectors, monitor.db models, retention
│       ├── containers/
│       ├── appstore/              # catalog sync, manifest parser, install engine
│       ├── websites/              # sites, nginx specs
│       ├── runtimes/              # PHP-FPM runtimes
│       ├── domains/               # domains, DNS accounts, DNS zone records
│       ├── certificates/          # ACME accounts, certificates, renewals
│       ├── projects/              # git sources, builds, deployments, processes, webhooks
│       ├── databases/             # servers, databases, users, drivers per engine
│       ├── files/
│       ├── terminal/              # PTY bridge, SSH hosts, snippets
│       ├── host/                  # firewall, ssh, fail2ban, processes, services, disks, swap, time
│       ├── cronjobs/
│       ├── backups/               # storage accounts, backup records, snapshots
│       ├── notifications/         # channels, alert rules
│       ├── toolbox/
│       └── panel/                 # panel settings, updates, health, about
│   (each app: models.py, services/, selectors.py, serializers.py, views.py, urls.py,
│    tasks.py, consumers.py, permissions.py, admin.py(dev only), tests/)
├── agent/
│   ├── pyproject.toml
│   └── easydeploy_agent/
│       ├── __main__.py  server.py  auth.py  registry.py  executor.py  locks.py  audit.py  errors.py
│       ├── protocol/              # Pydantic models + enums, imported by backend's agent client
│       ├── validators/            # domain, path, port, unit, nginx-directive allowlist
│       ├── ops/                   # one module per namespace (§5.3)
│       └── templates/             # nginx, php-fpm, systemd, fail2ban, docker daemon.json
├── cli/
│   └── edctl/                     # Typer app, installed as `edctl`
├── frontend/
│   ├── package.json  vite.config.ts  tsconfig.json
│   └── src/
│       ├── api/                   # generated client (openapi-typescript + typed fetch wrapper)
│       ├── components/ui/         # Ed* wrappers around Bootstrap (modal, table, form controls…)
│       ├── components/  composables/  layouts/  router/  stores/  utils/
│       ├── styles/                # Bootstrap Sass entry, _variables.scss (theme), fonts
│       ├── locales/{en,fa}/       # one JSON per module
│       └── modules/<module>/{pages,components,store.ts,routes.ts}
├── catalog/                       # app catalog source (split into its own repo in Phase 3)
│   ├── apps/<key>/...             # format in Appendix A
│   └── tools/                     # `catalog-lint`, index builder, signer
├── installer/
│   ├── install.sh  upgrade.sh  uninstall.sh
│   ├── lib/{common,preflight,mirrors,packages,docker,python,panel,nginx,firewall,systemd,summary}.sh
│   └── tests/                     # bats
├── deploy/
│   ├── systemd/  nginx/  logrotate/
├── scripts/                       # build_release.sh, build_wheelhouse.sh, dev helpers
├── docs/
│   ├── MASTER_PROMPT.md  PROGRESS.md  architecture.md  threat-model.md
│   ├── adr/  modules/  user-guide/{en,fa}/
├── .github/workflows/             # ci.yml, release.yml, installer-e2e.yml
├── .gitattributes                 # `* text=auto eol=lf` — shell scripts MUST be LF (owner develops on Windows)
├── .editorconfig  .pre-commit-config.yaml
├── CLAUDE.md
└── README.md
```

---

## 7. Server filesystem layout & ports

```
/opt/easydeploy/
├── current -> releases/<version>      # atomic switch on upgrade
├── releases/<version>/{app,frontend,deploy,VERSION}
├── python/                            # bundled CPython
├── venvs/<version>/                   # one venv per release (enables instant rollback)
├── data/{panel.db,monitor.db}
├── apps/<app-key>/<instance>/         # compose.yaml, .env, data volumes
├── projects/<slug>/{src,builds,volumes}
├── www/<site>/{public,logs}           # static & PHP site roots
├── backups/{local,panel}/
├── catalog/                           # synced app catalog
├── logs/{tasks,deploys}/
└── tmp/                               # uploads in progress
/etc/easydeploy/{easydeploy.env,secrets/}
/etc/easydeploy/ssl/<cert-id>/{fullchain.pem,privkey.pem}
/etc/nginx/conf.d/easydeploy.conf      # includes /etc/nginx/easydeploy/**
/etc/nginx/easydeploy/{panel.conf,sites/,snippets/,upstreams/}
/run/easydeploy/agent/agent.sock       # root:easydeploy
/run/easydeploy/api/api.sock           # easydeploy:www-data
/var/log/easydeploy/{agent-audit.log,install.log,...}
/usr/local/bin/edctl
```

| Port | Purpose |
|---|---|
| 22 (or detected SSH port) | SSH — installer MUST detect the real port from `sshd -T` before touching the firewall |
| 80 / 443 | User websites (Nginx) |
| random 10000–60000 (configurable) | Panel (Nginx TLS → `api.sock`) |
| none public | API, agent, Redis (Unix sockets only); containers publish to `127.0.0.1` only |

**Docker vs UFW:** Docker-published ports bypass UFW rules. Default behavior MUST be publishing on `127.0.0.1`. When the admin deliberately exposes a container port publicly (e.g., remote DB access), the agent MUST manage matching rules in the `DOCKER-USER` iptables chain (re-applied by the agent on boot and after Docker restarts, since these rules are not persistent), and the UI MUST show a warning.

---

## 8. Installer, upgrade, uninstall

### 8.1 Usage

```bash
# Recommended: download, inspect, run
curl -fsSL https://get.easydeploy.example/install.sh -o install.sh && sudo bash install.sh

# One-liner
sudo bash -c "$(curl -fsSL https://get.easydeploy.example/install.sh)"

# Non-interactive with options
sudo bash install.sh --yes --port 28443 --username admin --mirror-profile ir --docker-mirror https://mirror.example
```

**Options (each also settable via `ED_*` env var):** `--version`, `--channel stable|beta`, `--port`, `--entrance`, `--username`, `--password` (generated if omitted), `--listen ipv4|ipv6|dual`, `--mirror-profile global|ir|custom`, `--apt-mirror`, `--pypi-index`, `--docker-mirror` (repeatable), `--release-url`, `--offline-bundle <path>`, `--from-source <git-ref>` (dev only), `--skip-docker-install`, `--no-firewall`, `--yes`, `--dry-run`, `--verbose`.

### 8.2 Steps (MUST be idempotent and resumable; each step logs to `/var/log/easydeploy/install.log`)

1. **Preflight:** root; `/etc/os-release` is Ubuntu 22.04/24.04/26.04; arch amd64/arm64; systemd is PID 1; RAM ≥ 1 GB (warn < 2 GB); free disk ≥ 10 GB; not OpenVZ/LXC without nesting (warn); clock synchronized; ports 80/443/panel free (name the process holding them, e.g., apache2, and offer to stop/disable it); detect an existing installation → offer upgrade instead; test reachability of every configured source and print which mirrors are used.
2. **Mirrors:** apply the selected profile (apt sources, Docker repo/registry mirrors, PyPI index for the wheelhouse fallback, catalog/release URLs).
3. **Base packages:** `ca-certificates curl gnupg tar zstd unzip git jq sqlite3 nginx redis-server ufw logrotate` (+ `fail2ban` installed but jails disabled until configured).
4. **Docker:** if Docker ≥ 24 with Compose v2 exists, reuse it; otherwise install Docker CE from the official apt repo or mirror. Write `/etc/docker/daemon.json` (merge, never overwrite blindly): `log-driver json-file` with `max-size 20m`, `max-file 3`; `live-restore true`; `registry-mirrors` from profile. Create network `easydeploy-net`.
5. **Release:** download `easydeploy-<ver>-linux-<arch>.tar.gz`, `SHA256SUMS`, `SHA256SUMS.minisig`; verify the signature with the public key embedded in `install.sh` and the checksum; **never** use `curl -k`; extract to `/opt/easydeploy/releases/<ver>`.
6. **Python:** use bundled CPython; create `venvs/<ver>` and install from the bundled **wheelhouse** with `--no-index` (offline). Fallback to the configured PyPI index only with `--allow-online-wheels`.
7. **Users & dirs:** system user/group `easydeploy` (no login shell); create directories with exact owners/modes.
8. **Config & secrets:** generate `SECRET_KEY`, Fernet key, agent token, Redis password, random panel port (if not given), random 12-char entrance, admin password (if not given). Configure Redis: Unix socket only, `requirepass`, `maxmemory 64mb`.
9. **Database:** `migrate` both DBs, create the admin user (Argon2 hash), seed default settings.
10. **lego:** install the pinned lego binary (bundled in the release, verified checksum).
11. **Nginx:** disable the default site; install `conf.d/easydeploy.conf`; default `server` blocks for 80/443 that return `444` for unknown hosts; panel vhost on the panel port with a generated self-signed certificate; ACME webroot snippet; `nginx -t` then reload.
12. **systemd:** install units + target; `systemctl enable --now easydeploy.target`.
13. **Firewall:** if UFW is inactive, allow the detected SSH port **first**, then 80, 443, panel port, then enable; if active, only add rules. Skip with `--no-firewall`.
14. **edctl:** symlink `/usr/local/bin/edctl`.
15. **Health check:** wait until `https://127.0.0.1:<port>/api/v1/health` returns OK (timeout 60 s), verifying TLS against the generated self-signed certificate with `--cacert` (not `-k`); on failure print diagnostics from `edctl doctor` and the last log lines.
16. **Summary:** print a box with panel URL(s) (public IPv4/IPv6 detected via local interfaces, with an optional external lookup), username, password (**printed once, never stored in plaintext**), and next steps (`edctl user-info`, `edctl reset-password`).

### 8.3 Upgrade (`edctl update` and UI → Settings → Updates)

Runs as a transient unit (`systemd-run --unit=easydeploy-upgrade`) so it survives restarts of the agent and API. Steps: download + verify → extract new release → new venv from wheelhouse → back up `panel.db`, `monitor.db`, `/etc/easydeploy` → stop units → run migrations → switch `current` symlink → start units → health check → on failure: restore DB backup, switch the symlink back, restart, report. Keep the last 2 releases for rollback (`edctl rollback`).

### 8.4 Uninstall

`edctl uninstall` (or `uninstall.sh`): stop and remove units, Nginx panel config, CLI, panel files. Asks separately (default **keep**) about: user sites and their Nginx configs, app/project containers and data, Docker itself, backups, certificates. `--purge --yes` removes everything non-interactively.

### 8.5 Release artifacts (built in CI on native amd64 and arm64 runners)

`easydeploy-<ver>-linux-<arch>.tar.gz` containing `python/` (python-build-standalone 3.12), `wheels/` (complete wheelhouse for the arch), `app/` (backend, agent, cli), `frontend/dist/`, `deploy/`, `bin/lego`, `install.sh`, `VERSION`. Plus `SHA256SUMS` and `SHA256SUMS.minisig`. An **offline bundle** variant additionally includes Docker CE `.deb` files and selected base images.

---

## 9. Functional modules

Each module lists: **MVP** (in its roadmap phase) and **LATER**. Every module MUST provide: models + migrations, services, REST endpoints (documented in OpenAPI), agent ops (if host access is needed), tasks for long operations, audit entries for every mutation, en+fa strings, UI pages, and tests.

### 9.1 Authentication & access security (`accounts`, `audit`)

MVP:
- Custom `User` model from the first migration (`AbstractUser` subclass) with `role` field (only `admin` used now), `language`, `timezone`, `calendar (gregorian|jalali)`, `theme`.
- Argon2 password hashing; password policy (length ≥ 12, breach-pattern denylist).
- Session auth (HttpOnly, Secure, SameSite=Strict cookies) + CSRF for the SPA; idle timeout (default 2 h) and absolute timeout.
- **Security entrance:** a random path segment; requests that have not passed the entrance receive a configurable response (404 page or connection drop via Nginx `444`). Treated as obscurity on top of real auth, not as auth.
- **TOTP 2FA** (pyotp) with QR enrollment and 10 one-time recovery codes; can be enforced.
- Login protection: per-IP and per-username counters in Redis, progressive delay, temporary lockout, optional self-hosted image captcha after N failures (no third-party captcha services).
- **Sudo mode:** sensitive actions (terminal, script run, reveal secrets, security settings, deleting resources, restore) require re-authentication within the last 10 minutes.
- **IP allowlist** (CIDR list) and **bind domain** (reject requests whose `Host` differs) for panel access.
- **API keys** for automation: prefix `ed_`, shown once, stored as SHA-256 hash, scopes (`read`, `write` per module), IP allowlist, expiry, last-used metadata; header `X-API-Key`.
- Login log (success/failure, IP, user agent, reason) and **audit log** (actor, action, resource, IP, request ID, before/after diff for settings, result).
- Recovery via CLI: `edctl reset-password`, `reset-2fa`, `reset-entrance`, `reset-allowlist`, `reset-bind-domain`.

LATER: WebAuthn/passkeys, OIDC/LDAP SSO, RBAC with roles admin/operator/viewer and per-resource permissions, session list with remote revoke.

### 9.2 Dashboard & monitoring (`dashboard`, `monitoring`)

MVP:
- System info: hostname, OS, kernel, CPU model/cores, uptime, public IPs, panel version, Docker version.
- Live (WebSocket, 3 s): CPU total/per-core, load 1/5/15, memory/swap, disk usage per mount, disk I/O, network throughput per interface, top 5 processes by CPU/RAM.
- History (`monitor.db`): sample every 60 s, retention 30 days (configurable), downsample data older than 7 days to 5-minute averages; ECharts with ranges 1 h / 24 h / 7 d / 30 d.
- Installed apps/projects/sites summary cards with status; quick actions.
- Container stats (CPU/RAM) via agent, collected only while a viewer is subscribed.

LATER: GPU metrics, per-site traffic statistics from Nginx logs, uptime checks for websites (HTTP probes with alerting).

### 9.3 Containers (`containers`)

MVP:
- Containers: list with filters (managed-by-panel, app, project), start/stop/restart/pause/kill/remove, rename, logs (follow, since, tail, download), exec terminal, inspect (read-only JSON), live stats, create from form (image, name, ports bound to 127.0.0.1 by default, env, volumes, network, restart policy, CPU/memory limits, labels, command, healthcheck).
- Compose stacks: create from YAML editor (validated with `docker compose config`), up/down/restart/pull, per-service logs, edit + redeploy.
- Images: list, pull (streamed progress), build from Dockerfile (LATER), tag, remove, prune, import/export tar.
- Networks and volumes: list, create, remove, inspect, prune.
- Registries: credentials (encrypted), login test, used automatically for pulls.
- Docker settings: registry mirrors, log rotation, live-restore, IPv6, default address pools; apply with daemon restart warning.
- Resources created by the panel carry labels `io.easydeploy.managed=true`, `io.easydeploy.kind=app|project|runtime|db`, `io.easydeploy.id=<uuid>`. Managed resources are protected: destructive actions redirect the user to the owning module.

### 9.4 App Store (`appstore`)

MVP:
- **Catalog:** separate Git repository; the panel syncs a signed index (`index.json` + `index.json.minisig`) and per-app tarballs with SHA-256 from a configurable URL (mirror-friendly). Manual "Sync now" + daily automatic sync. Local custom apps (upload a package) and additional catalog URLs.
- **Format:** see Appendix A. Parameter types: `text`, `password`, `secret` (auto-generated), `number`, `port`, `boolean`, `select`, `email`, `domain`, `path`, `textarea`. Each has default, validation rule, en/fa label and help. `requires:` declares dependencies on service kinds (`mysql`, `mariadb`, `postgresql`, `redis`, `mongodb`) with provisioning instructions.
- **Install engine:** validate params → check architecture and free resources → check port availability → resolve `requires` (choose an existing instance or install one as a sub-task) → provision (create DB/user, Redis DB index…) → render `.env` + `compose.yaml` + config files into `/opt/easydeploy/apps/<key>/<instance>/` → pull (streamed) → up → wait for health → mark `running`. Any failure rolls back created containers and provisioned DB objects (data dirs kept for inspection unless the user chooses cleanup).
- **Instance actions:** start/stop/restart, logs, terminal, edit params (re-render + recreate), open web UI, bind domain (creates a proxy Website + SSL), backup/restore (per the manifest's backup spec), upgrade (version constraints, mandatory pre-upgrade backup, rollback on failed health), uninstall (keep or delete data; deprovision DB optionally), rebuild.
- **Updates page:** lists instances with newer catalog versions and changelog.
- **Panel-injected variables:** `ED_CONTAINER_NAME`, `ED_INSTANCE`, `ED_APP_DIR`, `ED_NETWORK`, `ED_HOST_IP`, `ED_REQ_<ID>_HOST|PORT|USER|PASSWORD|DATABASE` for each resolved requirement.
- **Launch set (Phase 3, 10 apps):** MySQL 8.4 LTS, MariaDB 11.4 LTS, PostgreSQL 17, Redis 7 (or Valkey 8), MongoDB 7, WordPress, phpMyAdmin, Adminer, Uptime Kuma, Gitea.
- **Second wave:** Nextcloud, n8n, Ghost, MinIO, Grafana, Prometheus, Metabase, Vaultwarden, Matomo, Plausible, RabbitMQ, Memcached, Elasticsearch/OpenSearch, pgAdmin, Mattermost, Odoo.
- `catalog-lint` tool validates every app in CI (schema, image tags pinned — never `latest`, compose renders, ports not hard-bound to 0.0.0.0, labels present, en+fa texts present).

### 9.5 Websites (`websites`, `runtimes`)

Site types (MVP):
1. **Static** — root at `/opt/easydeploy/www/<site>/public`, index files, SPA fallback (`try_files … /index.html`) option.
2. **PHP** — static root + FastCGI to a shared PHP-FPM runtime container of the selected version.
3. **Reverse proxy** — to `host:port`, URL, container, app instance, or project process; WebSocket support; upstream with multiple backends (round-robin/least_conn).
4. **Redirect** — 301/302 to a target, preserve path option.
5. **Bound** — sites created automatically by App Store/Projects (editable within limits).

Per-site features (MVP): multiple domains (primary + aliases, `www` ↔ apex redirect), HTTPS on/off with certificate picker or "auto-issue", force HTTPS, HSTS, HTTP/2, gzip, client max body size, custom headers, basic auth, IP allow/deny, rate limiting, rewrite presets (WordPress, Laravel, SPA), redirects, custom error pages, access/error log viewer with download, enable/disable, maintenance page, "view generated config", custom directives (validated escape hatch), clone site, delete (with optional file removal).

Implementation:
- API stores a structured `SiteSpec`; the agent renders `/etc/nginx/easydeploy/sites/<site-id>.conf` from templates and applies it transactionally (`nginx -t` → reload → rollback on error with stderr shown).
- Every site includes a shared ACME HTTP-01 snippet (`/.well-known/acme-challenge/` → a dedicated webroot).
- Default 80/443 server blocks return `444` for unknown hosts.

Runtimes (MVP): PHP-FPM containers for PHP 8.2, 8.3, 8.4, 8.5, built from official `php:*-fpm` images with a selectable extension set (via a pinned extension-installer tool), `php.ini` editor, FPM pool tuning, published on `127.0.0.1:<port>`; site roots are bind-mounted at the same path inside the container; files owned by uid/gid 33 (`www-data`). Language runtimes for applications (Node, Python, Go, Java, .NET) are handled per project through build templates (§9.7), not as shared runtimes.

LATER: per-site PHP pools with separate users, HTTP/3, WAF (Coraza/ModSecurity with OWASP CRS), tamper protection, traffic statistics.

### 9.6 Domains, DNS & SSL (`domains`, `certificates`)

Domains (MVP):
- `Domain` entity: FQDN (IDN → punycode stored, Unicode displayed), parent zone, linked resource (site/app/project), status.
- **DNS check:** resolve A/AAAA through public resolvers and compare with the server's public IPs; show clear "points elsewhere / not found / OK" states before allowing certificate issuance.
- **DNS provider accounts** (encrypted credentials): Cloudflare and **ArvanCloud** in MVP; Hetzner DNS, DigitalOcean, AWS Route 53, Google Cloud DNS LATER (any lego-supported provider can be added by mapping its env vars).
- Auto-create/update the A/AAAA record when binding a domain (if the zone belongs to a configured account).
- **DNS zone editor** for configured accounts: list/create/edit/delete records (A, AAAA, CNAME, TXT, MX, CAA, SRV).

Certificates (MVP):
- **ACME accounts:** Let's Encrypt (production + staging), ZeroSSL and Google Trust Services (with EAB), custom ACME directory URL.
- **Issue:** HTTP-01 (webroot) or DNS-01 (via DNS account; required for wildcards); multi-SAN; key type ECDSA P-256 (default) or RSA 2048/4096.
- **Renewal:** daily job; renew when **less than one third of the certificate lifetime** remains (do not hardcode "30 days" — certificate lifetimes are shrinking); use ACME Renewal Information (ARI) when the CA and lego support it. After renewal, reload Nginx for all sites using the certificate.
- Upload custom certificate (validate key ↔ cert match, chain order, expiry), self-signed certificate generator, internal CA LATER.
- Expiry alerts (14/7/3 days) and failure alerts through notifications.
- Panel HTTPS: self-signed by default; one click to issue a real certificate for the bound panel domain.

### 9.7 Projects — Git-based deployment (`projects`)

This is the product's core differentiator. MVP:

**Sources:** Git over HTTPS (token) or SSH (panel-generated ed25519 deploy key, public key shown for copy), branch/tag/commit, subdirectory (monorepos); uploaded archive (zip/tar.gz); Docker image from a registry; Docker Compose file.

**Build strategies (pluggable `BuildStrategy` interface):**
- `dockerfile` — repository Dockerfile (path, build args, target stage).
- `template` — panel-provided, version-pinned Dockerfile templates per stack, multi-stage, non-root user, healthcheck-ready:
  - Python: generic WSGI (gunicorn), ASGI (uvicorn), Django (collectstatic, migrations as release command), FastAPI, Flask; dependency detection: `uv.lock`, `poetry.lock`, `requirements.txt`, `pyproject.toml`, `Pipfile`.
  - Node.js: Express/NestJS/generic (`npm|yarn|pnpm|bun` detected from lockfile), Next.js (standalone output), Nuxt.
  - Static SPA/SSG: build with Node, then **extract the output directory** into a Static website (no running container).
  - PHP: Laravel/generic (PHP-FPM + Nginx in one image, or attach to a PHP runtime).
  - Go, Java (Maven/Gradle → JRE), .NET, Rust, Ruby/Rails.
- `compose` — user compose file with panel-injected network/labels.
- `image` — run an existing image (no build).
- LATER: Cloud Native Buildpacks or Railpack strategy.

**Auto-detection:** inspect the repository (lockfiles, framework config files, Dockerfile, compose file) and propose strategy, template, port, start command, build command, and output directory; the user confirms before the first deploy.

**Processes:** `web` (gets domains, port, healthcheck), any number of `worker` processes (e.g., Celery, queue workers), a `release` command (runs once per deploy before the switch, e.g., migrations), and scheduled commands (integrated with Cron Jobs).

**Configuration:** environment variables (plain/secret, bulk `.env` import/export), **linked resources** (attach a database from the Databases module → inject `DATABASE_URL` and component variables; attach Redis → `REDIS_URL`), persistent volumes, CPU/memory limits, restart policy, healthcheck (HTTP path or TCP, interval, timeout, grace period), replicas (N containers behind an Nginx upstream on the single node).

**Deploy pipeline (Task with live logs):** fetch source at a commit → build image `easydeploy/<project>:<deploy-id>` (BuildKit, layer cache kept) → run `release` command in a one-off container → start the new containers → wait for health → switch the Nginx upstream (zero downtime) → stop old containers after a drain period → prune images beyond the last 5. A failed health check leaves the previous version serving and marks the deploy failed. **Rollback** = redeploy a previous image without rebuilding (< 30 s). **Cancel** a running deploy.

**Triggers:** manual, Git webhooks (GitHub, GitLab, Gitea, Bitbucket; HMAC/secret verified; branch filter), API key call, schedule.

**Observability:** build logs stored per deploy, runtime logs streamed per process, deployment history (commit, author, message, duration, status, who triggered), notifications on success/failure.

LATER: preview deployments per pull request, multiple environments (staging/production) per project, build on a separate builder node.

### 9.8 Databases (`databases`)

MVP:
- **Servers:** local (instances from the App Store) or **remote** (host, port, admin credentials, TLS option). Engines: MySQL, MariaDB, PostgreSQL, Redis; MongoDB in Phase 3b.
- **Driver interface** per engine (`create_database`, `drop_database`, `create_user`, `drop_user`, `set_password`, `grant`, `list_*`, `size`, `status`, `dump`, `restore`). Python drivers: PyMySQL, psycopg 3, redis-py, pymongo. Local instances are reached over the container IP on `easydeploy-net`; dumps/restores run through agent `db.*` ops (`docker exec` + streaming), never by publishing DB ports.
- **Databases:** create with charset/collation (MySQL/MariaDB) or encoding/owner (PostgreSQL), list with size, delete (sudo mode + typed confirmation).
- **Users:** create, change password, grants (MySQL host patterns `%`/`localhost`/IP; PostgreSQL role privileges), delete.
- **Backup/restore:** on demand and scheduled (Cron Jobs), import `.sql`/`.sql.gz`/`.dump` upload, export download.
- **Server operations:** config editor (`my.cnf` / `postgresql.conf` overrides) with restart, status (version, uptime, connections, slow queries), root password rotation, remote access toggle (publishes port + DOCKER-USER rule + warning).
- **Redis:** config (maxmemory, policy, persistence AOF/RDB), keyspace info, flush (sudo mode).
- **Web admin:** one-click install/link of Adminer/phpMyAdmin/pgAdmin from the App Store.

### 9.9 Files (`files`)

MVP:
- Browse any path (admin is root-equivalent), breadcrumbs, quick paths (`/opt/easydeploy/www`, app dirs, project dirs, `/etc/nginx`, home), favorites.
- Operations through agent `fs.*`: create file/dir, rename, move, copy, delete **to recycle bin** (permanent delete in sudo mode), chmod (numeric + checkbox UI), chown (user/group pickers), symlink, properties (size, du for dirs as a task), search by name/content (task).
- **Upload:** chunked + resumable (custom chunk API with checksum per chunk), drag & drop, folder upload, size limit configurable; chunks land in `/opt/easydeploy/tmp` then the agent moves them and sets ownership.
- **Download:** files (streamed), directories (zip on the fly as a task).
- **Remote download** (wget-like from URL) as a task.
- **Compress/extract:** zip, tar.gz, tar.zst, tar.xz, 7z (if `p7zip` installed); **zip-slip and symlink-escape protection** on extraction.
- **Editor:** Monaco with syntax highlighting, encoding detection, max 5 MB, save with conflict detection (mtime/hash check); image preview.
- Protected paths (`/`, `/etc`, `/boot`, `/usr`, `/var/lib/docker`, panel dirs…) require an extra typed confirmation for destructive actions.

### 9.10 Terminal (`terminal`)

MVP: local host shell (agent PTY as root or a chosen Linux user), container exec (choose shell), saved SSH hosts (asyncssh in the API process; password or key, encrypted; host-key verification with first-use confirmation), multiple tabs, resize, copy/paste, font size, command **snippets library**. Sudo mode required; idle timeout; each session start/stop audited.

LATER: session recording, SFTP side panel for saved hosts.

### 9.11 Host & security (`host`)

MVP:
- **Firewall (UFW):** status, enable/disable with lockout protection (SSH and panel ports are always allowed first), rules list (port/range, protocol, source IP/CIDR, allow/deny, comment), ICMP ping toggle, presets (HTTP/HTTPS/SSH), and display of Docker-exposed ports managed through `DOCKER-USER`.
- **SSH:** port change (also updates UFW; `sshd -t` validation; keeps the old port until the new one is confirmed reachable), root login policy, password/pubkey auth toggles, authorized keys management per user, SSH login history from journald/auth log.
- **Fail2ban:** enable jails (sshd, nginx-http-auth, nginx-botsearch, panel-login), parameters (bantime, findtime, maxretry), banned IP list, unban, ignore list.
- **Processes:** list (psutil) with sort/filter, details (cmdline, user, open ports), kill/terminate (agent).
- **Services:** systemd units list, status, start/stop/restart/enable/disable, journal tail. Panel-critical units are protected.
- **Disks:** mounts and usage, block devices (read-only view in MVP), largest directories analysis (task).
- **Network:** interfaces, IP addresses, listening ports (`ss`), DNS resolvers.

LATER: mounting new disks, port forwarding, Linux user management, kernel parameter tuning.

### 9.12 Cron jobs (`cronjobs`)

MVP job types: shell script (stored, run via agent `script.run`, sensitive), website backup, database backup, app backup, project backup, directory backup, panel snapshot, log rotation/cleanup, URL request (HTTP GET/POST with timeout), certificate renewal (system job), Docker prune, sync time. Schedule via cron expression or presets (hourly/daily/weekly/monthly with a builder UI) in the panel's timezone; backup targets + retention count; overlap prevention (lock per job); timeout; run now; enable/disable; run history with logs, duration, exit status; failure notifications. Implemented with django-celery-beat `PeriodicTask` linked 1:1 to `CronJob`.

### 9.13 Backups & snapshots (`backups`)

MVP:
- **Storage accounts** (`StorageBackend` interface: `put_stream`, `get_stream`, `list`, `delete`, `test`): Local directory, S3-compatible (AWS S3, MinIO, Cloudflare R2, ArvanCloud Object Storage, Wasabi… via boto3 with custom endpoint), SFTP (paramiko/asyncssh), WebDAV. LATER: FTP, Google Drive, OneDrive, Dropbox, generic rclone adapter.
- **Backup kinds:** website (files + linked DB), database, app instance (volumes + dumps per manifest), project (env, volumes, linked DB; source is in Git), directory, panel snapshot.
- Format: `tar` + `zstd`, optional **age** encryption with a passphrase or recipient key; a `manifest.json` inside each archive (kind, source, versions, checksums, created_at, panel version).
- Backup records: list with filters, download, restore (sudo mode, shows exactly what will be overwritten, automatic safety backup before restore), delete; retention per job.
- **Snapshots:** panel DB + `/etc/easydeploy` + Nginx configs + certificates + app/project definitions and data + optional Docker images; restore on a **fresh server** via `edctl snapshot restore <file|url>` → server migration.

### 9.14 Logs & audit (`audit`, `logs` views)

MVP: audit log (filter by user/module/action/date, export CSV), login log, task log, system logs (journald by unit/priority/time with live follow), website access/error logs (tail, search, download), panel service logs. Retention settings per log type.

### 9.15 Notifications & alerts (`notifications`)

MVP channels: Email (SMTP, TLS), Telegram bot, **Bale** bot (Telegram-compatible Bot API), generic webhook (JSON, HMAC signature), Slack/Discord webhooks. Events: login from a new IP, repeated failed logins, certificate expiring/renewal failed, backup failed, cron job failed, deploy succeeded/failed, app health failed, disk usage > X %, CPU/RAM above threshold for N minutes, service down, panel update available. Per-event channel routing, rate limiting/deduplication, test button, delivery history.

### 9.16 Toolbox (`toolbox`)

MVP: system cleanup (apt cache, old kernels listing, journald vacuum, Docker prune, old task logs, temp files — preview sizes before deleting), swap (create/resize/remove swapfile, swappiness), time (timezone, NTP status/sync), hostname and `/etc/hosts` editor, ClamAV (install on demand, scan directory as a task, scheduled scans via Cron Jobs), **Daemons** (create custom systemd services for non-Docker processes: command, working dir, user, env, restart policy, logs), script library (shared with Terminal snippets and Cron Jobs).

LATER: FTP server (Pure-FTPd) users, SFTP-only chroot users.

### 9.17 Settings (`panel`)

MVP: General (panel name, default language, theme, timezone, calendar type), Security (§9.1 options, panel port change with UFW update and confirmation countdown, listen IPv4/IPv6, panel SSL), Network & Mirrors (§11), Notifications (§9.15), Updates (channel, check, changelog, update, rollback), About (versions, system info export for support). Changing port/entrance/bind domain shows the new URL and auto-reverts if the admin does not confirm reachability within 60 s.

### 9.18 CLI `edctl` (`cli`)

Must run as root. Commands: `status`, `start|stop|restart [unit]`, `user-info` (URL, username — never the password), `reset-password`, `reset-2fa`, `reset-entrance`, `set-port <port>`, `listen-ip ipv4|ipv6|dual`, `reset-allowlist`, `reset-bind-domain`, `disable-panel-ssl`, `update [--version] [--channel]`, `rollback`, `version`, `logs [unit] [-f]`, `doctor` (checks units, sockets, DB integrity, Nginx config, Docker, disk space, clock, certificate expiry, mirror reachability; prints actionable fixes), `backup panel`, `snapshot create|restore`, `mirror show|set`, `uninstall [--purge] [--yes]`. Output is human-readable with `--json` for scripts. All strings en/fa based on the system locale or `--lang`.

---

## 10. Cross-cutting requirements

### 10.1 API conventions

- Base path `/api/v1/`; resources plural, kebab-case URLs, snake_case JSON; DRF ViewSets; ISO 8601 UTC timestamps (UI converts to user timezone/calendar).
- Pagination: page-number `{count, next, previous, results}`, `page_size` ≤ 200; filtering via django-filter; `search` and `ordering` params.
- Error envelope (all errors, including validation):
  ```json
  {"error": {"code": "websites.domain_conflict", "message": "<localized text>", "details": {"field": ["..."]}, "request_id": "..."}}
  ```
  Error codes are stable strings documented per module; messages are localized from the `Accept-Language` header or user preference.
- Long operations return `202 Accepted` with `{"task_id": "..."}`.
- Idempotency: create endpoints that start tasks accept an `Idempotency-Key` header.
- OpenAPI schema at `/api/v1/schema/` (authenticated); the frontend client is regenerated from it in CI, and CI fails if the committed client is stale.
- Health endpoint `/api/v1/health`: no auth and exempt from the entrance check **only for requests from localhost**; returns status only, no versions or other sensitive data.

### 10.2 Security baseline (MUST)

- OWASP ASVS Level 2 as the checklist; a threat model in `docs/threat-model.md` updated every phase.
- Authorization check on **every** endpoint; an automated test enumerates all URL patterns and asserts unauthenticated access is rejected except an explicit allowlist.
- Strict input validation in serializers **and** again in agent validators (double validation is intentional).
- No `shell=True`, no `os.system`, no string-built commands anywhere in backend or agent; enforce with ruff rules (`S602`, `S605`…) and a custom lint check.
- Security headers via Nginx for the panel: strict CSP (no inline scripts), `frame-ancestors 'none'`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS when a real certificate is used.
- Secrets: encrypted at rest, masked in logs (structlog processor), never in URLs, never in task logs (redaction helper used by all task log writers).
- Uploads: size limits, filename sanitization, no execution from upload temp dirs.
- Outbound requests (webhooks, remote download, URL cron jobs): timeouts, response size limits, optional block of link-local/metadata IPs.
- Dependency scanning in CI: `pip-audit`, `pnpm audit`, `bandit`; Docker images in the catalog pinned to explicit tags.
- Webhook endpoints verify signatures with constant-time comparison.

### 10.3 Performance & footprint

- Idle footprint of the whole panel stack (api + worker + agent + redis) **≤ 450 MB RSS** on a 1 GB VPS; measure in CI on a VM and report in release notes.
- List endpoints p95 < 200 ms with 1 000 rows (excluding agent round trips); dashboard live updates must not exceed 2 % CPU on 1 vCPU.
- Agent calls have explicit timeouts; the UI never blocks on a long agent call (use tasks).

### 10.4 Internationalization & RTL

- Backend: Django i18n (`gettext`) for messages and error texts; `en` and `fa` catalogs complete before a phase is accepted.
- Frontend: vue-i18n with one JSON file per module per locale; **no hard-coded UI strings** (ESLint rule). Bootstrap has no built-in locales, so every component text (pagination, empty states, close buttons' `aria-label`…) comes from vue-i18n.
- RTL: Bootstrap is compiled from Sass through **postcss-rtlcss**, so one CSS bundle serves both directions (`[dir="rtl"]` rules are generated automatically). Switching language sets `<html lang="fa" dir="rtl">` at runtime with no reload.
- Use Bootstrap's direction-aware utilities (`ms-*`, `me-*`, `ps-*`, `pe-*`, `text-start`, `text-end`, `float-start`, `float-end`) and, in custom CSS, logical properties (`margin-inline-start`, `padding-inline-end`, `inset-inline`). Never use `left`/`right` for layout; icons that imply direction are mirrored in RTL.
- Persian font (Vazirmatn, bundled locally — no external font CDN) with Persian digits optional; dates in Gregorian or **Jalali** (dayjs + jalali plugin) per user preference.
- Code, logs, terminal output, file paths, and config editors stay LTR inside RTL layouts (`dir="ltr"` islands).

### 10.5 Observability

- structlog JSON logs to journald with `request_id`, `user_id`, `task_id`; log level configurable.
- `edctl doctor` and Settings → About → "Export diagnostics" (redacted bundle).
- Agent audit log separate from the panel audit log.

### 10.6 UX rules

- Every destructive action: confirmation dialog stating exact consequences; critical deletes require typing the resource name.
- Every form shows validation errors inline (from the API error envelope).
- Every list: search, filters, empty state with a call to action, loading skeletons.
- Long operations open the task log automatically; the user can navigate away and return through the Task Center.
- Responsive down to 375 px width (usable on phones) using Bootstrap's grid and breakpoints; light/dark/system theme through Bootstrap color modes (`data-bs-theme` on `<html>`).

---

## 11. Restricted networks & mirrors

Some regions (for example Iran) face blocked or throttled access to Docker Hub, GitHub, PyPI, and other sources. Requirements:

1. **Every external source is configurable:** apt mirror, Docker apt repository, Docker registry mirrors (list), Python wheel index (fallback only), app catalog URL, release URL, lego binary URL, ACME directory, GitHub proxy prefix for Git clones (optional), HTTP(S) proxy for outbound panel traffic.
2. **Mirror profiles:** `global` (official sources), `ir` (a curated list maintained in `installer/lib/mirrors.sh` and the panel's settings — **do not hardcode third-party mirror URLs in code paths**; keep them in one data file the owner can update), `custom`.
3. **Offline bundle:** installation MUST succeed with no internet except apt (or with a local apt mirror) using the offline bundle (§8.5).
4. **Image pulls** use the configured registry mirrors; the App Store shows a clear error with remediation (set a mirror) when pulls fail due to network errors.
5. Settings → Network & Mirrors includes a **connectivity test** for every source.

---

## 12. Development environment (owner uses Windows 11 Home)

- Primary dev environment: **WSL2 with Ubuntu 24.04 and systemd enabled** (`/etc/wsl.conf` → `[boot] systemd=true`). Clone the repo **inside the WSL filesystem** (not `/mnt/c`) for performance and correct permissions. Docker Engine installed inside WSL (or Docker Desktop with the WSL backend).
- `make dev` / `just dev` (choose one, document it) starts: Redis, Django (Uvicorn with reload), Celery worker, Vite dev server, and the agent in **DryRun or Sandbox executor mode** by default. Running the agent with `RealExecutor` in WSL is allowed only behind an explicit flag.
- Real host testing (installer, Nginx, UFW, SSH, Fail2ban) happens only on a **disposable Ubuntu VM or cheap VPS** (Windows Home has no Hyper-V; use a cloud VPS with snapshots or Multipass/VirtualBox). Provide `scripts/vm-test.sh` that rsyncs a dev build to a VM and runs the installer in `--from-source` mode.
- `.gitattributes` enforces LF line endings; pre-commit runs on WSL.
- Seed command `manage.py seed_demo` creates demo data for UI work with the fake agent.

---

## 13. Coding standards

### 13.1 Python (backend, agent, cli)

- Python 3.12, full type hints, mypy strict on `agent` and `cli`, mypy standard + django-stubs on `backend`; ruff for lint + format (line length 100).
- **Layering:** `views` (HTTP only, thin) → `services` (business logic, transactions, task dispatch) → `selectors` (read queries) → `agent client` / adapters. No business logic in serializers, models' `save()`, or signals. Avoid Django signals except for audit hooks.
- Models: UUID primary keys, `created_at`/`updated_at`, soft-delete only where restore makes sense; explicit `on_delete`; DB constraints for invariants (unique domain per server, etc.).
- Celery tasks: idempotent, accept IDs (not objects), use `Task` model helpers for logging/progress, explicit `time_limit`/`soft_time_limit`.
- Agent ops: pure functions over validated params + `OpContext` (executor, logger, lock); no global state; every op unit-tested with `DryRunExecutor` asserting exact argv and rendered files.
- Error handling: domain exceptions (`EasyDeployError` subclasses with stable `code`) mapped to the error envelope by one DRF exception handler; never leak stack traces to clients.
- Docstrings for public services and ops; comments explain *why*, not *what*.

### 13.2 Frontend

- TypeScript strict, `<script setup lang="ts">`, Composition API, Pinia stores per module, feature-folder structure mirroring backend apps.
- All API calls through the generated client; TanStack Query for Vue (or a thin composable equivalent) for caching and refetch; WebSocket helper with auto-reconnect and backoff.
- **Bootstrap UI layer (`components/ui/`):** thin typed wrappers, written once and used everywhere: `EdModal`, `EdOffcanvas` (drawers, e.g., Task Center), `EdDropdown`, `EdTooltip`, `EdToast` (exposed as a notification service), `EdTabs`, `EdTable` (sorting, pagination, row selection, column toggles, loading skeletons), `EdPagination`, form controls with Bootstrap validation states (`EdInput`, `EdSelect` with search, `EdSwitch`, `EdFileDrop`), and `EdDatePicker` (Jalali + Gregorian). A wrapper creates its Bootstrap JS instance in `onMounted` and calls `dispose()` in `onBeforeUnmount`; outside these wrappers, never manipulate the DOM directly. Theme changes go through Sass variables in `styles/_variables.scss`, never by overriding compiled Bootstrap CSS.
- Reusable building blocks: `ResourceTable`, `ResourceForm` (schema-driven, used by App Store params), `ConfirmDanger`, `TaskLogViewer`, `CodeEditor`, `Terminal`, `StatusBadge`, `EmptyState`.
- ESLint (vue + ts + i18n no-raw-text), Prettier; components ≤ 300 lines, extract composables beyond that.

### 13.3 Shell (installer)

- `#!/usr/bin/env bash`, `set -Eeuo pipefail`, `trap` with a readable error message and the failing step name, functions per step, all variables quoted, `shellcheck` clean, no `curl | bash` inside the installer itself, every download verified.

### 13.4 Git & docs

- Conventional Commits (`feat(websites): ...`), one logical change per commit, CHANGELOG generated (git-cliff).
- ADRs (`docs/adr/NNNN-title.md`: context, decision, consequences) for every significant decision.
- `docs/modules/<module>.md` per module: purpose, models, endpoints, agent ops, tasks, edge cases.

---

## 14. Testing strategy

| Layer | Tools | Requirements |
|---|---|---|
| Backend unit/integration | pytest, pytest-django, factory_boy, pytest-cov | Services ≥ 85 % coverage; agent client replaced by `FakeAgent`; Channels consumers tested with `WebsocketCommunicator` |
| Agent | pytest, hypothesis | Every op tested with `DryRunExecutor` (argv + rendered files snapshot tests); validators property-tested (domains, paths, ports, directives); `@pytest.mark.host` tests run only on VMs |
| Security tests | pytest | Auth-required-everywhere test; permission tests per endpoint; path traversal, zip-slip, injection payload suites against validators |
| Frontend | Vitest + Vue Test Utils | Components and composables; i18n key completeness test (en ↔ fa) |
| E2E | Playwright | Critical journeys against the dev stack with fake agent: login + 2FA, install app, create site, deploy project, backup/restore |
| Installer | shellcheck, bats, VM matrix | Fresh-VM install on Ubuntu 22.04/24.04/26.04 (amd64; arm64 where runners exist), reinstall idempotency, upgrade from N-1, uninstall |
| Catalog | `catalog-lint` | Runs on every catalog change |

CI (`ci.yml`) on every push: lint, type check, unit tests, frontend build, OpenAPI client staleness check, catalog lint, shellcheck/bats. `installer-e2e.yml` nightly and on release branches.

---

## 15. Roadmap (phases, deliverables, acceptance criteria)

Work in order. A phase is complete only when **all** acceptance criteria pass and `docs/PROGRESS.md` is updated.

### Phase 0 — Foundation

Deliverables: monorepo scaffold (§6), tooling + pre-commit + CI; Django project (settings split, SQLite WAL + `monitor.db` router, Redis, Celery, Channels, DRF, drf-spectacular, structlog, error envelope); `accounts` + `audit` (login/logout, entrance middleware, TOTP 2FA, lockout, sudo mode, API keys, login/audit logs); `tasks` (model, helpers, WS streaming, worker-lost recovery); agent skeleton (UDS server, token auth, op registry, executors, locks, audit) with ops `system.info`, `service.status`, `fs.list`; frontend shell (layout + full menu from §2.3 with placeholder pages, login + 2FA pages, i18n en/fa, RTL switch, dark mode, generated API client, Task Center drawer); installer v0 (`--from-source` and local tarball modes, steps 1–16 of §8.2 except signed releases); `edctl` (status, start/stop/restart, user-info, reset-password, reset-2fa, reset-entrance, set-port, doctor-lite); `docs/` skeleton, `CLAUDE.md`, `PROGRESS.md`, ADR-0001..000N for decisions D1–D21.

Acceptance:
- On a fresh Ubuntu 24.04 VM, one command installs the panel in < 10 min and prints a working URL; login with 2FA works; reboot → everything comes back.
- Wrong entrance → 404/drop; 5 failed logins → lockout; `edctl reset-password` works.
- Switching to Persian flips the entire layout to RTL with no untranslated strings.
- CI green; idle RSS measured and recorded.

### Phase 1 — Host essentials

Deliverables: Dashboard + Monitoring (§9.2), Files (§9.9), Terminal (§9.10, host + container), Containers (§9.3), Logs viewers (§9.14), Processes & Services (§9.11 partial).

Acceptance: upload a 2 GB file with a pause/resume; extract an archive containing a zip-slip entry → rejected; open a root terminal (sudo mode) and a container shell; create and run a compose stack from the editor; live charts update and history survives restarts; audit log records every mutation above.

### Phase 2 — Websites, domains & SSL

Deliverables: Nginx integration + transactional apply (§9.5), static/proxy/redirect/PHP sites, PHP runtimes, Domains + DNS check + Cloudflare/ArvanCloud accounts + zone editor (§9.6), ACME accounts, HTTP-01 + DNS-01 + wildcard issuance, renewal job, custom/self-signed certs, panel domain + real certificate.

Acceptance: static site with a real domain gets a valid certificate in < 2 min; a wildcard certificate is issued via DNS-01; an invalid custom directive is rejected and the previous config keeps serving; a PHP site runs `phpinfo()` on PHP 8.3 and switches to 8.4; renewal job renews a staging certificate forced near expiry.

### Phase 3 — App Store & databases

Deliverables: catalog format + `catalog-lint` + signed index + sync; install/upgrade/uninstall engine with `requires` provisioning; launch set of 10 apps (§9.4); Databases module (§9.8) for MySQL/MariaDB/PostgreSQL/Redis (+ MongoDB as 3b); domain binding for app instances.

Acceptance: install WordPress choosing "create new MariaDB" in one flow → bind domain + SSL → site reachable over HTTPS; upgrade with automatic pre-upgrade backup; a broken upgrade (simulated failed health) rolls back; uninstall with "keep data" then reinstall reuses data; create DB + user in PostgreSQL and connect with the generated credentials; tampered catalog index → sync refused.

### Phase 4 — Project deployments

Deliverables: Projects module (§9.7) with all MVP strategies and templates, auto-detection, env/secrets, linked resources, release command, workers, zero-downtime switch, rollback, webhooks, deploy history, notifications hook.

Acceptance: sample repos (Django, FastAPI, Express, Next.js, Vite SPA as static, Laravel, Go, Spring Boot, ASP.NET) deploy from GitHub with domain + SSL; a push triggers auto-deploy through a verified webhook; a deploy with a failing health check keeps the previous version serving; rollback completes in < 30 s; secrets never appear in build logs.

### Phase 5 — Operations

Deliverables: Cron Jobs (§9.12), Backups + storage accounts + restore (§9.13), Snapshots + `edctl snapshot`, Notifications & alerts (§9.15), Firewall/SSH/Fail2ban/Disks/Network (§9.11), Toolbox (§9.16).

Acceptance: scheduled encrypted DB backup lands in S3-compatible storage and restores on a second server; a full snapshot restored on a fresh VM reproduces sites, apps, projects, and certificates; enabling UFW never locks out SSH or the panel; changing the SSH port is safe; Telegram/Bale/email alerts fire for a failed backup and high disk usage.

### Phase 6 — Hardening & release

Deliverables: threat model review + ASVS L2 checklist, security test suite completion, footprint/performance tuning, release pipeline (signed multi-arch tarballs, wheelhouse, bundled Python, lego, offline bundle), `edctl update/rollback` + UI updates, mirror profiles finalized, installer VM matrix, user guide (en + fa), README with screenshots.

Acceptance: install/upgrade/uninstall pass on the full VM matrix; upgrade N-1 → N preserves all data; a failed upgrade rolls back automatically; signature tampering is detected; offline bundle installs with no internet except a local apt mirror; idle RSS ≤ 450 MB.

### Phase 7+ — Backlog (prioritize with the owner)

RBAC multi-user; multi-node management (agent over mTLS, node switcher, cross-node file transfer); website uptime monitoring + status page; WAF (Coraza + OWASP CRS) and tamper protection; preview deployments; per-site PHP pools; FTP/SFTP users; mail server app integration; AI module (Ollama model management, MCP server hosting); traffic analytics; WebAuthn/OIDC/LDAP; additional DNS and backup providers; additional distros (Debian 12/13).

---

## 16. Working protocol for the AI agent

1. **Language:** talk to the owner in **Persian (Farsi)**. Write code, identifiers, comments, commit messages, ADRs, and `docs/` technical files in English. User-facing UI strings in both en and fa.
2. **Session start:** read `CLAUDE.md`, this document (relevant sections), `docs/PROGRESS.md`, and the ADRs touching the current work. Summarize in 3–5 lines where the project stands.
3. **Phase start:** present a short plan (tasks in order, files/modules touched, tests to write, risks) and wait for the owner's confirmation. Within a confirmed phase, work autonomously task by task.
4. **Per task loop:** implement → write/extend tests → run lint, type check, and tests → update docs (`docs/modules/*`, OpenAPI, i18n) → update `docs/PROGRESS.md` → commit with a Conventional Commit message. Small, reviewable commits.
5. **Safety:** never run host-modifying commands (apt, ufw, nginx, systemctl, docker system prune, file deletes outside the repo) on the owner's machine; use DryRun/Sandbox executors locally and the disposable VM for real tests. Never commit secrets; use `.env.example`.
6. **Scope control:** do not implement LATER items early; do not add dependencies not listed here without an ADR (lightweight, well-maintained, license-compatible, with a reason).
7. **Ambiguity:** follow §0. When blocked by a genuine owner decision, ask one concise question with your recommended option first.
8. **Clean room:** never copy code or catalog files from 1Panel or other GPL projects; implement from this specification and official upstream documentation.
9. **Reporting:** end each session with: what was done, what was verified (with commands run), what is not done, next steps — mirrored in `docs/PROGRESS.md`.

### Definition of Done (every task)

- [ ] Feature works end-to-end through the UI (or CLI) for its acceptance scenario.
- [ ] Unit/integration tests added and passing; lint and type checks pass.
- [ ] Endpoint permissions enforced and covered by tests; mutations audited.
- [ ] Long operations run as Tasks with logs; failures are reported with actionable messages.
- [ ] Config changes are validated and roll back on failure.
- [ ] en + fa strings complete; RTL layout verified.
- [ ] OpenAPI and generated client updated; module docs and PROGRESS updated.
- [ ] No secrets in logs, responses, or commits.

---

## 17. Non-goals (for now)

Shared-hosting reseller features and billing; email hosting stack built into the panel; Kubernetes orchestration; Windows servers; non-Ubuntu distros before Phase 7; mobile apps; VM/KVM management.

---

## Appendix A — App catalog package format (EasyDeploy's own format)

```
apps/<key>/
├── app.yaml                     # metadata (below)
├── logo.svg                     # or logo.png, ≤ 64 KB
├── README.md  README.fa.md
└── versions/<version>/
    ├── manifest.yaml            # params, requires, health, backup, upgrade rules
    ├── compose.yaml             # Docker Compose using ${VARS} from the generated .env
    └── files/                   # optional config templates (Jinja2, rendered by the panel)
```

`apps/wordpress/app.yaml`
```yaml
key: wordpress
name: WordPress
category: website            # ai|website|database|server|runtime|tools|storage|bi|crm|security|devtool|devops|middleware|media|email|game
tags: [cms, blog, php]
summary:
  en: The most popular open-source CMS.
  fa: محبوب‌ترین سیستم مدیریت محتوای متن‌باز.
homepage: https://wordpress.org
source: https://github.com/WordPress/WordPress
license: GPL-2.0-or-later
architectures: [amd64, arm64]
min_resources: {memory_mb: 512, disk_mb: 1024}
web_ui: {service: wordpress, port_param: HTTP_PORT, path: /}
domain_binding: true
single_instance: false
```

`apps/wordpress/versions/7.1.4/manifest.yaml`
```yaml
version: "7.1.4"
images: ["wordpress:7.1.4-apache"]
requires:
  - id: db
    kinds: [mariadb, mysql]
    provision: {database: true, user: true}
    defaults: {database: "wp_{{ random_alnum(6) }}", user: "wp_{{ random_alnum(6) }}"}
params:
  - key: HTTP_PORT
    type: port
    default: auto            # panel picks a free port in the apps range
    bind: localhost          # published on 127.0.0.1 only
    label: {en: HTTP port, fa: پورت HTTP}
  - key: UPLOAD_MAX_MB
    type: number
    default: 64
    min: 2
    max: 2048
    label: {en: Max upload size (MB), fa: حداکثر حجم آپلود (مگابایت)}
health:
  service: wordpress
  http: {port: 80, path: /wp-login.php, expect_status: [200, 302]}
  timeout_s: 180
backup:
  paths: [./data]
  dumps: [{require: db}]
upgrade:
  from: ">=6.0,<8"
  pre_backup: true
files:
  - src: files/uploads.ini.j2
    dest: ./conf/uploads.ini
```

`apps/wordpress/versions/7.1.4/compose.yaml`
```yaml
services:
  wordpress:
    image: wordpress:7.1.4-apache
    container_name: ${ED_CONTAINER_NAME}
    restart: unless-stopped
    ports:
      - "127.0.0.1:${HTTP_PORT}:80"
    environment:
      WORDPRESS_DB_HOST: ${ED_REQ_DB_HOST}:${ED_REQ_DB_PORT}
      WORDPRESS_DB_NAME: ${ED_REQ_DB_DATABASE}
      WORDPRESS_DB_USER: ${ED_REQ_DB_USER}
      WORDPRESS_DB_PASSWORD: ${ED_REQ_DB_PASSWORD}
    volumes:
      - ./data:/var/www/html
      - ./conf/uploads.ini:/usr/local/etc/php/conf.d/uploads.ini:ro
    networks: [easydeploy-net]
    labels:
      io.easydeploy.managed: "true"
      io.easydeploy.kind: app
      io.easydeploy.app: wordpress
      io.easydeploy.instance: ${ED_INSTANCE}
networks:
  easydeploy-net:
    external: true
```

(The WordPress version shown is an example; `catalog-lint` enforces pinned tags, localhost-bound ports, required labels, and en+fa texts.)

---

## Appendix B — Agent op example

```python
# agent/easydeploy_agent/ops/nginx.py
from easydeploy_agent.registry import op, OpContext
from easydeploy_agent.protocol.nginx import SiteSpec, ApplyResult
from easydeploy_agent.nginx_tx import nginx_transaction
from easydeploy_agent.templates import render


@op("nginx.site.apply", params=SiteSpec, result=ApplyResult, lock="nginx", timeout=60)
def apply_site(spec: SiteSpec, ctx: OpContext) -> ApplyResult:
    """Render a site's server blocks and apply them atomically.

    Rolls back to the previous file set if `nginx -t` or the reload fails,
    so a bad site never takes down the other sites.
    """
    content = render("nginx/site.conf.j2", spec=spec)
    with nginx_transaction(ctx) as tx:
        changed = tx.write(f"sites/{spec.site_id}.conf", content)
        if changed:
            tx.test()      # runs ["nginx", "-t"]; raises OpError(code="nginx.invalid", details=stderr)
            tx.reload()    # runs ["systemctl", "reload", "nginx"]; health-checks afterwards
    return ApplyResult(changed=changed)
```

```python
# agent/easydeploy_agent/protocol/nginx.py (excerpt)
class SiteSpec(StrictModel):
    site_id: SiteId                      # ^[a-z0-9][a-z0-9-]{0,62}$
    domains: list[DomainName]            # IDNA-validated, punycode
    kind: Literal["static", "php", "proxy", "redirect"]
    root: SafePath | None                # must resolve under /opt/easydeploy/www
    upstreams: list[Upstream] = []
    tls: TlsSpec | None = None
    options: SiteOptions = SiteOptions()
    custom_directives: list[NginxDirective] = []   # allowlist-validated
```

---

## Appendix C — Phase kickoff prompts

Send one per new session.

**Phase 0**
```
Read EASYDEPLOY_MASTER_PROMPT.md completely. We are starting Phase 0 (Foundation).
First: move it to docs/MASTER_PROMPT.md, create CLAUDE.md that points to it and
summarizes the working protocol (§16), create docs/PROGRESS.md, and write ADRs for
decisions D1–D21. Then present your Phase 0 plan (§15) and wait for my confirmation.
Talk to me in Persian.
```

**Phase N (1–6)**
```
Read CLAUDE.md, docs/MASTER_PROMPT.md (sections relevant to Phase N), docs/PROGRESS.md
and related ADRs. Confirm Phase N-1 acceptance criteria are all met (list them with
evidence). Then present the Phase N plan per §15 and §16 and wait for my confirmation.
```

**Continue a phase**
```
Read CLAUDE.md and docs/PROGRESS.md. Summarize where we are in 5 lines, then continue
with the next unfinished task of the current phase following the Definition of Done.
```

**Review checkpoint**
```
Pause feature work. Review the code of the current phase against docs/MASTER_PROMPT.md
§10 (security, API conventions, i18n) and §13 (coding standards). List concrete
violations with file:line, fix them, and update docs/PROGRESS.md.
```

---

## Appendix D — Glossary

| Term | Meaning |
|---|---|
| Agent | Root daemon executing typed, validated host operations for the panel |
| Op | One registered agent operation (e.g., `nginx.site.apply`) |
| Task | A tracked background job with status, progress, and live logs |
| Entrance | Secret URL path segment required before the login page is shown |
| Sudo mode | Short-lived re-authentication required for sensitive actions |
| App / App instance | Catalog package / an installed copy of it |
| Requirement (`requires`) | A service an app depends on, resolved and provisioned at install |
| Project | A user application deployed from Git, upload, image, or compose |
| Deployment | One build + release of a project at a specific commit |
| Site | An Nginx virtual host managed by the panel |
| Runtime | A shared PHP-FPM container serving PHP sites |
| Snapshot | Full panel state archive used for disaster recovery or migration |
| Mirror profile | Preset of download sources for restricted networks |
