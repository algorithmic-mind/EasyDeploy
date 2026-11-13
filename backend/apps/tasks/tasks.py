"""Celery tasks of the tasks app."""

from __future__ import annotations

from typing import Any

from django.db import connections

from apps.core.agent_client import get_agent
from apps.core.errors import EasyDeployError
from apps.tasks.services import TaskRecorder, tracked_task


@tracked_task("panel.diagnostics", time_limit=120, soft_time_limit=100)
def run_diagnostics(rec: TaskRecorder) -> dict[str, Any]:
    checks: dict[str, str] = {}

    rec.log("Checking panel database…")
    with connections["default"].cursor() as cursor:
        cursor.execute("PRAGMA integrity_check")
        row = cursor.fetchone()
    checks["database"] = "ok" if row and row[0] == "ok" else f"error: {row}"
    rec.log(f"  database: {checks['database']}")
    rec.progress(30, "database")

    rec.log("Checking agent…")
    agent = get_agent()
    if not agent.health():
        checks["agent"] = "unreachable"
        rec.log("  agent: unreachable", stream="stderr")
    else:
        try:
            info = agent.call("system.info")
        except EasyDeployError as exc:
            checks["agent"] = f"error: {exc.code}"
            rec.log(f"  agent: {exc.code}", stream="stderr")
        else:
            checks["agent"] = "ok"
            rec.log(f"  agent: ok (executor={info.get('executor')})")
            rec.log(f"  host: {info.get('hostname')} — {info.get('os_name')} ({info.get('arch')})")
    rec.progress(90, "agent")

    failed = [name for name, value in checks.items() if value != "ok"]
    if failed:
        raise EasyDeployError(
            f"Diagnostics found problems: {', '.join(failed)}",
            code="tasks.diagnostics_failed",
            details={"checks": checks},
        )
    rec.log("All checks passed.")
    return {"checks": checks}
