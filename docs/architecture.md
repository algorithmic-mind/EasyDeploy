# Architecture

The binding description is `MASTER_PROMPT.md` §5. This page summarizes what is **built** and where it lives.

## Processes

| Unit | User | Code | Talks to |
|---|---|---|---|
| `easydeploy-agent` | root | `agent/easydeploy_agent` (FastAPI) | listens on `/run/easydeploy/agent/agent.sock` |
| `easydeploy-api` | easydeploy | `backend/` (Django ASGI on Uvicorn, 2 workers) | agent socket, Redis socket, SQLite; listens on `/run/easydeploy/api/api.sock` |
| `easydeploy-worker` | easydeploy | `backend/` (Celery worker + embedded beat) | agent socket, Redis socket, SQLite |
| Nginx | www-data | `deploy/nginx/*` | API socket; serves `/assets/*` directly |
| Redis | redis | `deploy/redis/easydeploy.conf` | Unix socket only, password |

`easydeploy.target` groups the three EasyDeploy units; `edctl start|stop|restart` act on it.

## Request path

```
browser ──TLS──► Nginx :<panel port>
                  ├─ /assets/*  → /opt/easydeploy/current/frontend/assets (static)
                  ├─ /ws/*      → api.sock (WebSocket: task logs)
                  └─ /*         → api.sock → Django
                                   ├─ RequestId → BindDomain → IpAllowlist → Session → Entrance
                                   ├─ Locale → CSRF → Auth → SessionTimeout → UserLanguage
                                   ├─ /api/v1/*  DRF (error envelope, ApiKey/Session auth, scopes)
                                   └─ /*         SPA index.html (so the entrance guards the shell)
```

## Privilege separation (§5.3)

* The API never runs shell commands. It calls typed agent ops (`apps/core/agent_client.py`) with a
  bearer token; sensitive ops also need an HMAC sudo token minted only in sudo mode.
* The agent validates every parameter with Pydantic models + validators (`agent/easydeploy_agent/validators`),
  runs subprocesses with argv lists through an `Executor`, takes named locks, and writes an append-only audit log.
* Executors: `RealExecutor` (production), `DryRunExecutor` (development: reads real FS, never writes or runs),
  `SandboxExecutor` (tests: everything under a temp root).

## Data

| Store | Path | Contents |
|---|---|---|
| `panel.db` (SQLite WAL) | `/opt/easydeploy/data/panel.db` | users, API keys, settings, audit/login logs, tasks, celery-beat schedules |
| `monitor.db` (SQLite WAL) | `/opt/easydeploy/data/monitor.db` | metrics (`monitoring` app), routed by `easydeploy.db_routers.MonitorRouter` |
| Redis db 0/1/2 | socket | Celery broker / cache (settings, login counters) / Channels layer |
| Task logs | `/opt/easydeploy/logs/tasks/<id>.log` | redacted output, replayed over `/ws/tasks/<id>/` |
| Secrets | `/etc/easydeploy/secrets/` (0640 root:easydeploy) | Django key, Fernet keys, agent token, Redis password |

## Backend apps (Phase 0)

| App | Purpose |
|---|---|
| `core` | base models, error envelope, request IDs, encrypted fields, redaction, agent client, health, SPA view |
| `panel` | typed runtime settings registry (`Setting` table) |
| `accounts` | user, login + lockout, TOTP 2FA, sudo mode, API keys, entrance/allowlist/bind-domain middleware |
| `audit` | audit log + login log |
| `tasks` | Task model, recorder, Celery integration, WebSocket consumer |
| `dashboard` | system info via agent |
| `monitoring` | metric models in monitor.db (collectors in Phase 1) |

## Frontend

Vue 3 + TS + Vite + Pinia + vue-i18n + Bootstrap 5.3.9 (Sass, postcss-rtlcss). Feature folders in
`frontend/src/modules/`, Bootstrap JS only in `components/ui/Ed*`, API types generated from OpenAPI
(`frontend/openapi.yaml` → `src/api/schema.d.ts`).
