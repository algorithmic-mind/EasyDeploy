# Module: agent (`easydeploy_agent`)

## Purpose
The only root component. Executes typed, validated host operations requested by the API/worker (§5.3).

## Protocol
* `GET /v1/health` (no token) · `GET /v1/ops` (registry + JSON schemas)
* `POST /v1/ops/{op}` → `{"ok": true, "result": …}` | `{"ok": false, "error": {"code","message","details"}}`
* `POST /v1/ops/{op}/stream` → NDJSON events `log`, `progress`, `result`, `error`
* Headers: `Authorization: Bearer <agent.token>`, `X-Request-ID`, `X-Actor`, `X-Sudo-Token` (sensitive ops)

## Writing an op
```python
@op("service.status", params=ServiceStatusParams, result=ServiceStatus, timeout=10, lock=None)
def service_status(params: ServiceStatusParams, ctx: OpContext) -> ServiceStatus:
    result = ctx.executor.run(["systemctl", "show", params.unit, ...], timeout=ctx.remaining(10)).check()
    ...
```
Rules: params/results are `StrictModel`s; subprocess argv lists only via `ctx.executor`; config files are
rendered by the agent from its own templates; mutating ops on shared resources declare `lock=` (e.g.
`"nginx"`, `"app:{app_id}"`); every op has DryRun/Sandbox tests asserting argv and written files.

## Ops (Phase 0)
| Op | Params | Notes |
|---|---|---|
| `system.info` | — | os-release, kernel, CPU, memory, uptime |
| `service.status` | `unit` (validated, `.service` appended) | `systemctl show` |
| `fs.list` | `path`, `show_hidden`, `limit` | directories first |

## Error codes
`agent.unauthorized`, `agent.sudo_required`, `agent.unknown_op`, `agent.invalid_params`, `agent.bad_json`,
`agent.lock_timeout`, `agent.command_failed`, `agent.command_timeout`, `agent.binary_missing`,
`agent.internal`, `fs.not_found`, `fs.not_a_directory`, `fs.permission_denied`, `service.not_found`.

## Running
Production: `python -m easydeploy_agent` (root, Unix socket). Development: `python -m easydeploy_agent --dev`
(TCP 127.0.0.1:7801, DryRun executor, token in `var/agent.token`).
