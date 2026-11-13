"""``/ws/tasks/<id>/`` — replays the existing log, then streams new lines and status changes."""

from __future__ import annotations

from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.tasks.models import Task
from apps.tasks.services import read_log, serialize

WS_CLOSE_NOT_FOUND = 4404


@database_sync_to_async
def _snapshot(task_id: str) -> tuple[str, dict[str, Any], list[str]] | None:
    task = Task.objects.filter(pk=task_id).first()
    if task is None:
        return None
    return task.group_name, serialize(task), read_log(task)


class TaskLogConsumer(AsyncJsonWebsocketConsumer):
    group: str | None = None

    async def connect(self) -> None:
        task_id = self.scope["url_route"]["kwargs"]["task_id"]
        snap = await _snapshot(task_id)
        if snap is None:
            await self.close(code=WS_CLOSE_NOT_FOUND)
            return
        self.group, task, lines = snap
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"type": "snapshot", "task": task, "lines": lines, "seq": len(lines)})

    async def disconnect(self, code: int) -> None:
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        return None  # read-only stream

    async def task_log(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {"type": "log", "seq": event["seq"], "line": event["line"], "stream": event["stream"]}
        )

    async def task_status(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "status", "task": event["task"]})
