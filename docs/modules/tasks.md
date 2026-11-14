# Module: tasks

## Purpose
Every operation that may exceed ~2 s runs as a tracked Task with live logs, progress, cancel and history (§5.4).

## Usage
```python
from apps.tasks.services import TaskRecorder, start_task, tracked_task

@tracked_task("panel.diagnostics", time_limit=120, soft_time_limit=100)
def run_diagnostics(rec: TaskRecorder) -> dict:
    rec.log("checking…")          # redacted, appended to the log file, streamed to /ws/tasks/<id>/
    rec.progress(50, "agent")
    rec.check_cancelled()          # cooperative cancellation point
    return {"ok": True}            # stored in Task.result

task = start_task(run_diagnostics, kind="panel.diagnostics",
                  title_key="tasks.titles.diagnostics", user=request.user)
return Response({"task_id": str(task.id)}, status=202)
```
Raise `EasyDeployError` for expected failures (stored as `Task.error`); unexpected exceptions become
`task.internal`, time limits `task.timeout`.

## Model
`Task`: `id`, `kind`, `title_key` + `title_params` (i18n in the UI), `status`, `progress`, `progress_message`,
`resource_type/id`, `created_by`, `parent`, `celery_id`, timestamps, `log_path`, `result`, `error`.

## Endpoints
`GET /api/v1/tasks` (filters status, kind, resource), `GET /api/v1/tasks/{id}`, `GET /api/v1/tasks/{id}/log`,
`POST /api/v1/tasks/{id}/cancel`, `POST /api/v1/tasks/diagnostics` → 202.

## WebSocket
`/ws/tasks/<id>/`: first frame `{"type":"snapshot","task":…,"lines":[…],"seq":N}`, then
`{"type":"log","seq","line","stream"}` and `{"type":"status","task":…}`. Clients drop log frames with
`seq <= snapshot.seq`.

## Recovery
On `worker_ready`, tasks still `running` become `failed` with `task.worker_lost`.
