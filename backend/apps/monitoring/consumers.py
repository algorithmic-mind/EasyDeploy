"""``/ws/monitor/live/`` — pushes host metrics every 3 s while a viewer is connected (§9.2)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.core.agent_client import get_agent
from apps.core.errors import EasyDeployError
from apps.monitoring.services import with_rates

INTERVAL_SECONDS = 3.0


def _read() -> dict[str, Any]:
    return get_agent().call("system.metrics")


class LiveMetricsConsumer(AsyncJsonWebsocketConsumer):
    loop_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        await self.accept()
        self.loop_task = asyncio.create_task(self._loop())

    async def disconnect(self, code: int) -> None:
        if self.loop_task:
            self.loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.loop_task

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        return None

    async def _loop(self) -> None:
        previous: dict[str, Any] | None = None
        while True:
            try:
                current = await sync_to_async(_read, thread_sensitive=False)()
            except EasyDeployError as exc:
                await self.send_json({"type": "error", "code": exc.code})
            else:
                await self.send_json({"type": "metrics", "data": with_rates(current, previous)})
                previous = current
            await asyncio.sleep(INTERVAL_SECONDS)
