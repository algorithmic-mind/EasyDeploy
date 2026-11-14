# EasyDeploy

Self-hosted server control panel for Ubuntu Server: deploy projects from Git, install apps and databases,
manage domains, SSL, files, containers, firewall, backups and more — from one web UI in English or Persian.

> **Status:** Phase 0 (foundation) — see [`docs/PROGRESS.md`](docs/PROGRESS.md).
> The full specification is [`docs/MASTER_PROMPT.md`](docs/MASTER_PROMPT.md).

## Install (test on a disposable VM)

Requirements: Ubuntu Server 22.04 / 24.04 / 26.04 (amd64 or arm64), root, ≥ 1 GB RAM, ≥ 10 GB free disk.

From a source checkout (development builds):

```bash
cd frontend && npm ci && npm run build && cd ..
sudo bash installer/install.sh --from-source --yes
```

From a release tarball:

```bash
sudo bash install.sh --release-file easydeploy-<version>-linux-amd64.tar.gz
```

The installer prints the panel URL (`https://<ip>:<port>/<entrance>`), the admin username and a generated
password **once**. Recover access with `sudo edctl user-info`, `sudo edctl reset-password`,
`sudo edctl reset-2fa`, `sudo edctl reset-entrance`.

## Develop

See [`CLAUDE.md`](CLAUDE.md) for commands. In short:

```bash
uv sync --all-packages
uv run python -m easydeploy_agent --dev          # agent (dry-run executor)
uv run python backend/manage.py migrate
uv run python backend/manage.py migrate --database monitor
uv run python backend/manage.py ed_create_admin  # prints a password
uv run uvicorn easydeploy.asgi:application --app-dir backend --reload --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173
```

## Layout

`agent/` privileged agent · `backend/` Django API · `cli/` edctl · `frontend/` Vue 3 SPA ·
`installer/` install/uninstall scripts · `deploy/` systemd + Nginx templates · `docs/` spec, ADRs, progress.

## License

To be decided by the owner before the first public release (ADR-0021).
