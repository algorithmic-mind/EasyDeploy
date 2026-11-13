# CLAUDE.md — EasyDeploy

EasyDeploy is a self-hosted server control panel (Django + Vue 3 + Bootstrap) installed on a fresh
Ubuntu Server with one command. The **binding specification** is `docs/MASTER_PROMPT.md`.

## Read first, every session

1. This file.
2. `docs/PROGRESS.md` — current phase, checklist, change log, **next step**. Continue from there.
3. The sections of `docs/MASTER_PROMPT.md` relevant to the current task (§4 decisions, §5 architecture,
   §9 module spec, §10 cross-cutting rules, §13 coding standards, §15 roadmap).
4. ADRs in `docs/adr/` touching the current work.

Then summarize in 3–5 lines where the project stands before writing code.

## Working protocol (summary of §16)

- **Language:** talk to the owner in **Persian (Farsi)**. Code, identifiers, comments, commit messages,
  ADRs and technical docs in English. UI strings in both `en` and `fa`.
- **Phases:** work strictly phase by phase (§15). Present a short plan at phase start; inside a confirmed
  phase work autonomously task by task.
- **Per task loop:** implement → tests → lint / type check / tests → docs (`docs/modules/*`, i18n) →
  update `docs/PROGRESS.md` → commit (Conventional Commits, e.g. `feat(accounts): add TOTP 2FA`).
- **Safety:** never run host-modifying commands (apt, ufw, nginx, systemctl, docker prune, deletes outside
  the repo) on the owner's machine. Use the agent's `DryRunExecutor` / `SandboxExecutor` locally; real host
  tests only on a disposable VM. Never commit secrets.
- **Scope:** do not implement LATER items early; no new dependencies outside the spec without an ADR.
- **Clean room:** never copy code or catalog files from 1Panel or other GPL projects.
- **Session end:** report done / verified (with commands) / not done / next steps, mirrored in PROGRESS.md.

## Repository map

| Path | What |
|---|---|
| `backend/` | Django project `easydeploy` + apps in `backend/apps/` (core, accounts, audit, tasks, panel, monitoring…) |
| `agent/` | `easydeploy_agent` — root daemon, FastAPI over a Unix socket, typed ops (`ops/`), validators, executors |
| `cli/` | `edctl` Typer CLI |
| `frontend/` | Vue 3 + TS + Vite + Bootstrap 5.3 SPA |
| `installer/` | `install.sh`, `upgrade.sh`, `uninstall.sh`, `lib/*.sh`, bats tests |
| `deploy/` | systemd units, nginx templates, logrotate |
| `catalog/` | App Store catalog source (Phase 3) |
| `docs/` | spec, progress, ADRs, module docs, threat model |

## Common commands

Python (uv workspace, Python 3.12):

```bash
uv sync --all-packages              # install backend, agent, cli + dev tools
uv run ruff check . && uv run ruff format --check .
uv run mypy agent cli               # strict
uv run mypy backend                 # django-stubs
uv run pytest agent cli backend     # all Python tests
uv run python backend/manage.py runserver   # dev API (settings: easydeploy.settings.dev)
uv run python -m easydeploy_agent --dev     # agent with DryRun executor on TCP 127.0.0.1:7801
```

Frontend (`cd frontend`):

```bash
npm install      # or pnpm install
npm run dev      # Vite dev server, proxies /api and /ws to Django
npm run build    # type check + production build
npm run test     # Vitest
npm run lint
```

`make dev` (Linux/WSL) starts the whole dev stack; see `Makefile`.

## Conventions that are easy to get wrong

- Subprocesses: argument lists only, never `shell=True` / `os.system` / string-built commands.
- Agent never receives full config files from the API — it renders its own templates from typed params.
- Every mutation writes an audit entry; every long operation is a `Task` returning `202 {"task_id"}`.
- API errors always use the envelope `{"error": {"code", "message", "details", "request_id"}}`.
- Frontend: no hard-coded UI text (use vue-i18n), no `left`/`right` in layout CSS (use logical
  properties / Bootstrap `ms-*`/`me-*`), Bootstrap JS only inside `components/ui/Ed*` wrappers.
- Shell scripts MUST use LF line endings (`.gitattributes` enforces it).
