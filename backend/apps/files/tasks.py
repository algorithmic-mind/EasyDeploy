"""Celery tasks of the files app (long ``fs.*`` operations)."""

from __future__ import annotations

from typing import Any

from apps.core.agent_client import get_agent
from apps.tasks.services import TaskRecorder, tracked_task


@tracked_task("files.agent_op", time_limit=7300, soft_time_limit=7200)
def run_agent_op(rec: TaskRecorder, op: str, params: dict[str, Any], actor: str) -> dict[str, Any]:
    """Run a long ``fs.*`` op through the agent's streaming endpoint with live task logs."""

    def on_event(event: dict[str, Any]) -> None:
        if event.get("type") == "log":
            rec.log(str(event.get("line", "")))
        elif event.get("type") == "progress":
            rec.progress(int(event.get("percent", 0)), str(event.get("message") or ""))

    rec.log(f"{op}: started")
    result = get_agent().stream(op, params, on_event=on_event, actor=actor, timeout=7200)
    rec.log(f"{op}: done")
    return result
