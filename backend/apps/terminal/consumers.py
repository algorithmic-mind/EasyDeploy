"""``/ws/terminal/<session>/`` — bridges the browser's xterm.js to an agent PTY (§9.10).

The protocol is the agent's ``WS /v1/pty``: the browser sends a JSON ``start`` frame, then
``input`` / ``resize`` frames; terminal output arrives as binary frames and control messages
(``started``, ``exit``, ``error``) as JSON text frames. Opening a terminal needs sudo mode; the
session is closed after ``terminal.idle_minutes`` without input. Start and end are audited.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from pydantic import ValidationError

from apps.accounts.services.session import SUDO_UNTIL_KEY
from apps.audit.services import record
from apps.core.agent_client import AgentPty, FakePty, PtyClosed, get_agent
from apps.core.errors import EasyDeployError
from apps.core.net import scope_ip
from apps.panel.services import get_setting
from easydeploy_agent.pty_session import PtyStart

WS_CLOSE_BAD_REQUEST = 4400
WS_CLOSE_SUDO_REQUIRED = 4403
WS_CLOSE_IDLE = 4408
WS_CLOSE_AGENT = 4502
MAX_INPUT = 65536


@database_sync_to_async
def _sudo_active(sess: Any) -> bool:
    until = sess.get(SUDO_UNTIL_KEY)
    return bool(until) and float(until) > time.time()


@database_sync_to_async
def _idle_seconds() -> int:
    return int(get_setting("terminal.idle_minutes")) * 60


@database_sync_to_async
def _audit(action: str, user: Any, session_id: str, ip: str, details: dict[str, Any]) -> None:
    record(
        action,
        actor=user,
        resource_type="terminal_session",
        resource_id=session_id,
        ip=None if ip == "unknown" else ip,
        details=details,
    )


class TerminalConsumer(AsyncWebsocketConsumer):
    pty: AgentPty | FakePty | None = None
    start_params: dict[str, Any]
    opened_at = 0.0
    last_input = 0.0

    async def connect(self) -> None:
        self.tasks: list[asyncio.Task[None]] = []
        self.session_id = str(self.scope["url_route"]["kwargs"]["session"])
        if not await _sudo_active(self.scope["session"]):
            await self.close(code=WS_CLOSE_SUDO_REQUIRED)
            return
        await self.accept()

    async def disconnect(self, code: int) -> None:
        for task in self.tasks:
            task.cancel()
        if self.pty is None:
            return
        pty, self.pty = self.pty, None
        with contextlib.suppress(Exception):
            await pty.close()
        await _audit(
            "terminal.session_ended",
            self.scope["user"],
            self.session_id,
            scope_ip(self.scope),
            {**self.start_params, "duration_seconds": round(time.monotonic() - self.opened_at)},
        )

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if text_data is None:
            return
        try:
            frame = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if not isinstance(frame, dict):
            return
        if self.pty is None:
            await self._start(frame)
            return
        kind = frame.get("type")
        if kind == "input" and isinstance(frame.get("data"), str):
            self.last_input = time.monotonic()
            await self._forward({"type": "input", "data": frame["data"][:MAX_INPUT]})
        elif kind == "resize":
            cols, rows = frame.get("cols"), frame.get("rows")
            if isinstance(cols, int) and isinstance(rows, int):
                cols, rows = min(max(cols, 10), 500), min(max(rows, 5), 300)
                await self._forward({"type": "resize", "cols": cols, "rows": rows})

    async def _start(self, frame: dict[str, Any]) -> None:
        try:
            start = PtyStart.model_validate(frame)
        except ValidationError as exc:
            fields = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
            await self._fail("terminal.invalid_start", fields, WS_CLOSE_BAD_REQUEST)
            return
        user = self.scope["user"]
        try:
            pty = await get_agent().open_pty(actor=str(user.pk))
            await pty.send(start.model_dump_json())
        except EasyDeployError as exc:
            await self._fail(exc.code, [], WS_CLOSE_AGENT)
            return
        except PtyClosed:
            await self._fail("terminal.closed", [], WS_CLOSE_AGENT)
            return
        self.pty = pty
        self.start_params = start.model_dump(include={"mode", "user", "container", "shell_path"})
        self.opened_at = self.last_input = time.monotonic()
        await _audit(
            "terminal.session_started",
            user,
            self.session_id,
            scope_ip(self.scope),
            self.start_params,
        )
        idle = await _idle_seconds()
        self.tasks = [asyncio.create_task(self._pump()), asyncio.create_task(self._watch(idle))]

    async def _forward(self, frame: dict[str, Any]) -> None:
        if self.pty is None:
            return
        with contextlib.suppress(PtyClosed):
            await self.pty.send(json.dumps(frame))

    async def _pump(self) -> None:
        """Agent to browser, until the shell exits or the agent goes away."""
        pty = self.pty
        if pty is None:
            return
        with contextlib.suppress(PtyClosed):
            while True:
                message = await pty.recv()
                if isinstance(message, bytes):
                    await self.send(bytes_data=message)
                else:
                    await self.send(text_data=message)
        await self.close()

    async def _watch(self, idle_seconds: int) -> None:
        while True:
            remaining = idle_seconds - (time.monotonic() - self.last_input)
            if remaining <= 0:
                await self._fail("terminal.idle_timeout", [], WS_CLOSE_IDLE)
                return
            await asyncio.sleep(min(remaining, 30.0))

    async def _fail(self, code: str, fields: list[str], close_code: int) -> None:
        payload = {"type": "error", "code": code, "fields": fields}
        await self.send(text_data=json.dumps(payload))
        await self.close(code=close_code)
