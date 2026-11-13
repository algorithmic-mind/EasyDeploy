"""Create, run and observe Tasks.

Usage in a module::

    @tracked_task("panel.diagnostics")
    def run_diagnostics(rec: TaskRecorder) -> dict:
        rec.log("checking agent…")
        rec.progress(50)
        return {"ok": True}

    task = start_task(run_diagnostics, kind="panel.diagnostics", title_key="tasks.diagnostics",
                      user=request.user)
    return Response({"task_id": str(task.id)}, status=202)
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from apps.core.conf import ed_path
from apps.core.errors import EasyDeployError
from apps.core.redaction import redact_text
from apps.tasks.models import Task

log = structlog.get_logger(__name__)
MAX_LINE = 4000


class TaskCancelled(Exception):
    pass


def log_dir() -> Path:
    path = ed_path("TASK_LOG_DIR")
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialize(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "kind": task.kind,
        "title_key": task.title_key,
        "title_params": task.title_params,
        "status": task.status,
        "progress": task.progress,
        "progress_message": task.progress_message,
        "resource_type": task.resource_type,
        "resource_id": task.resource_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "result": task.result,
        "error": task.error,
    }


def publish(group: str, message: dict[str, Any]) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, message)
    except Exception:  # realtime is best effort; the log file is the source of truth
        log.warning("task publish failed", group=group, exc_info=True)


class TaskRecorder:
    """Writes a task's log/progress/status and streams them to ``/ws/tasks/<id>/``."""

    def __init__(self, task: Task, secrets: list[str] | None = None) -> None:
        self.task = task
        self.secrets = list(secrets or [])
        self.path = Path(task.log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seq = self._count_lines()
        self._last_progress_save = 0.0

    def _count_lines(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("rb") as fh:
            return sum(1 for _ in fh)

    def add_secret(self, value: str) -> None:
        self.secrets.append(value)

    # ---------------------------------------------------------------- output
    def log(self, line: str, stream: str = "stdout") -> None:
        clean = redact_text(line.rstrip("\n")[:MAX_LINE], self.secrets)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(clean + "\n")
        self.seq += 1
        publish(
            self.task.group_name,
            {"type": "task.log", "seq": self.seq, "line": clean, "stream": stream},
        )

    def progress(self, percent: int, message: str = "") -> None:
        self.task.progress = max(0, min(100, int(percent)))
        self.task.progress_message = redact_text(message, self.secrets)[:300]
        now = time.monotonic()
        if now - self._last_progress_save > 1 or self.task.progress == 100:
            self._last_progress_save = now
            Task.objects.filter(pk=self.task.pk).update(
                progress=self.task.progress, progress_message=self.task.progress_message
            )
        self._publish_status()

    def check_cancelled(self) -> None:
        """Cooperative cancellation point for long loops."""
        status = Task.objects.filter(pk=self.task.pk).values_list("status", flat=True).first()
        if status == Task.Status.CANCELLED:
            raise TaskCancelled()

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._save(status=Task.Status.RUNNING, started_at=timezone.now())

    def succeed(self, result: dict[str, Any] | None = None) -> None:
        self._save(
            status=Task.Status.SUCCEEDED,
            progress=100,
            result=result or {},
            finished_at=timezone.now(),
        )

    def fail(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.log(f"ERROR [{code}] {message}", stream="stderr")
        self._save(
            status=Task.Status.FAILED,
            error={
                "code": code,
                "message": redact_text(message, self.secrets),
                "details": details or {},
            },
            finished_at=timezone.now(),
        )

    def cancelled(self) -> None:
        self._save(status=Task.Status.CANCELLED, finished_at=timezone.now())

    def _save(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self.task, key, value)
        self.task.save(update_fields=[*fields.keys()])
        self._publish_status()

    def _publish_status(self) -> None:
        publish(self.task.group_name, {"type": "task.status", "task": serialize(self.task)})


def create_task(
    *,
    kind: str,
    title_key: str,
    title_params: dict[str, Any] | None = None,
    user: Any = None,
    resource_type: str = "",
    resource_id: str = "",
    parent: Task | None = None,
) -> Task:
    task = Task(
        kind=kind,
        title_key=title_key,
        title_params=title_params or {},
        created_by=user if user is not None and getattr(user, "is_authenticated", False) else None,
        resource_type=resource_type,
        resource_id=str(resource_id),
        parent=parent,
    )
    task.log_path = str(log_dir() / f"{task.id}.log")
    task.save()
    return task


def start_task(
    celery_task: Any,
    *,
    kind: str,
    title_key: str,
    title_params: dict[str, Any] | None = None,
    user: Any = None,
    resource_type: str = "",
    resource_id: str = "",
    parent: Task | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Task:
    """Create a Task row and enqueue its Celery job after the surrounding transaction commits."""
    task = create_task(
        kind=kind,
        title_key=title_key,
        title_params=title_params,
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        parent=parent,
    )

    def enqueue() -> None:
        async_result = celery_task.apply_async(kwargs={"task_id": str(task.id), **(kwargs or {})})
        if async_result is not None and async_result.id:
            Task.objects.filter(pk=task.pk, celery_id="").update(celery_id=async_result.id)

    transaction.on_commit(enqueue)
    return task


TaskFunc = Callable[..., dict[str, Any] | None]


def tracked_task(
    name: str, *, time_limit: int = 3600, soft_time_limit: int = 3300
) -> Callable[[TaskFunc], Any]:
    """Register ``fn(rec, **kwargs)`` as a Celery task bound to a ``Task`` row.

    The runner only starts ``pending`` tasks, so a redelivered message is a no-op.
    """

    def decorator(fn: TaskFunc) -> Any:
        @shared_task(name=name, bind=True, time_limit=time_limit, soft_time_limit=soft_time_limit)
        @functools.wraps(fn)
        def runner(self: Any, task_id: str, **kwargs: Any) -> None:
            task = Task.objects.filter(pk=task_id).first()
            if task is None or task.status != Task.Status.PENDING:
                return  # already handled (redelivery) or cancelled before start
            rec = TaskRecorder(task)
            structlog.contextvars.bind_contextvars(task_id=task_id)
            rec.start()
            try:
                rec.succeed(fn(rec, **kwargs))
            except TaskCancelled:
                rec.log("Cancelled.")
                rec.cancelled()
            except EasyDeployError as exc:
                rec.fail(exc.code, str(exc.message), exc.details)
            except SoftTimeLimitExceeded:
                rec.fail("task.timeout", "The task exceeded its time limit.")
            except Exception as exc:
                log.exception("task crashed", task=name)
                rec.fail("task.internal", f"Internal error: {type(exc).__name__}")
            finally:
                structlog.contextvars.unbind_contextvars("task_id")

        return runner

    return decorator


def mark_worker_lost() -> int:
    """Tasks still ``running`` when a worker (re)starts were interrupted by a crash (§5.4)."""
    return Task.objects.filter(status=Task.Status.RUNNING).update(
        status=Task.Status.FAILED,
        finished_at=timezone.now(),
        error={
            "code": "task.worker_lost",
            "message": "The worker stopped while running this task.",
            "details": {},
        },
    )


def cancel(task: Task) -> bool:
    if not task.is_active:
        return False
    was_pending = task.status == Task.Status.PENDING
    Task.objects.filter(pk=task.pk).update(status=Task.Status.CANCELLED, finished_at=timezone.now())
    task.refresh_from_db()
    if was_pending and task.celery_id:
        from easydeploy.celery import app

        app.control.revoke(task.celery_id)
    publish(task.group_name, {"type": "task.status", "task": serialize(task)})
    return True


def read_log(task: Task, max_lines: int = 5000) -> list[str]:
    path = Path(task.log_path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    return lines[-max_lines:]
