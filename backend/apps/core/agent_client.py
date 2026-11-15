"""Client for the privileged agent (§5.3).

Production talks HTTP over ``/run/easydeploy/agent/agent.sock``; development uses TCP
(``ED_AGENT_URL``); tests use ``FakeAgent``. Obtain the configured client with ``get_agent()``.
Terminals use a WebSocket to the agent's ``/v1/pty`` (``open_pty``).
"""

from __future__ import annotations

import asyncio
import functools
import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from websockets.asyncio.client import ClientConnection, connect, unix_connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidStatus

from apps.core.conf import ed, ed_float, ed_path, ed_str
from apps.core.errors import EasyDeployError, ServiceUnavailable
from apps.core.request_context import current_request_id
from easydeploy_agent.auth import make_sudo_token

EventCallback = Callable[[dict[str, Any]], None]


class AgentError(EasyDeployError):
    """An op failed inside the agent; ``code`` is the agent's stable error code."""

    status_code = 502

    @classmethod
    def from_body(cls, body: dict[str, Any], http_status: int) -> AgentError:
        err = body.get("error") or {}
        status = http_status if http_status in {400, 403, 404, 409, 422} else 502
        return cls(
            str(err.get("message") or "Agent error"),
            code=str(err.get("code") or "agent.error"),
            details=err.get("details") or {},
            status_code=status,
        )


class AgentUnavailable(ServiceUnavailable):
    code = "agent.unavailable"
    default_message = _("The EasyDeploy agent is not reachable.")


class PtyClosed(Exception):
    """The agent side of a terminal session has ended."""


class AgentPty:
    """One terminal session on the agent (``WS /v1/pty``); frames are passed through as-is."""

    def __init__(self, conn: ClientConnection) -> None:
        self._conn = conn

    async def send(self, message: str | bytes) -> None:
        try:
            await self._conn.send(message)
        except ConnectionClosed as exc:
            raise PtyClosed from exc

    async def recv(self) -> str | bytes:
        try:
            return await self._conn.recv()
        except ConnectionClosed as exc:
            raise PtyClosed from exc

    async def close(self) -> None:
        await self._conn.close()


def _token() -> str:
    return ed_str("AGENT_TOKEN") or ed_path("AGENT_TOKEN_FILE").read_text(encoding="utf-8").strip()


class AgentClient:
    def __init__(
        self,
        *,
        socket_path: str | None = None,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url: str | None = base_url or ed_str("AGENT_URL")
        self.socket_path: str | None = (
            None if self.base_url else (socket_path or ed_str("AGENT_SOCKET"))
        )
        self.token = token or _token()
        self.timeout = timeout or ed_float("AGENT_TIMEOUT", 30.0)

    def _client(self, timeout: float | None) -> httpx.Client:
        transport = httpx.HTTPTransport(uds=self.socket_path) if self.socket_path else None
        return httpx.Client(
            base_url=self.base_url or "http://agent",
            transport=transport,
            timeout=httpx.Timeout(timeout or self.timeout, connect=5.0),
        )

    def _headers(self, actor: str | None, sudo: bool) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.token}"}
        if rid := current_request_id():
            headers["X-Request-ID"] = rid
        if actor:
            headers["X-Actor"] = actor
        if sudo:
            if not actor:
                raise ValueError("sudo agent calls need an actor")
            headers["X-Sudo-Token"] = make_sudo_token(self.token, actor)
        return headers

    def call(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        actor: str | None = None,
        sudo: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            with self._client(timeout) as client:
                resp = client.post(
                    f"/v1/ops/{op}", json=params or {}, headers=self._headers(actor, sudo)
                )
        except httpx.HTTPError as exc:
            raise AgentUnavailable(details={"reason": type(exc).__name__}) from exc
        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            raise AgentUnavailable(details={"reason": "invalid_response"}) from exc
        if not body.get("ok"):
            raise AgentError.from_body(body, resp.status_code)
        result: dict[str, Any] = body["result"]
        return result

    def stream(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        on_event: EventCallback,
        actor: str | None = None,
        sudo: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Run a streaming op: ``log``/``progress`` events go to ``on_event``; return the result."""
        try:
            with (
                self._client(timeout) as client,
                client.stream(
                    "POST",
                    f"/v1/ops/{op}/stream",
                    json=params or {},
                    headers=self._headers(actor, sudo),
                ) as resp,
            ):
                if resp.status_code != 200:
                    resp.read()
                    raise AgentError.from_body(resp.json(), resp.status_code)
                for event in _ndjson(resp.iter_lines()):
                    if event.get("type") == "result":
                        result: dict[str, Any] = event["result"]
                        return result
                    if event.get("type") == "error":
                        raise AgentError.from_body(event, 422)
                    on_event(event)
        except httpx.HTTPError as exc:
            raise AgentUnavailable(details={"reason": type(exc).__name__}) from exc
        raise AgentUnavailable(details={"reason": "stream_ended_without_result"})

    def download(self, path: str, *, actor: str | None = None) -> tuple[Iterator[bytes], int]:
        """Stream a file's bytes from the agent; returns ``(chunks, size)``."""
        client = self._client(None)
        try:
            request = client.build_request(
                "GET",
                "/v1/files/download",
                params={"path": path},
                headers=self._headers(actor, False),
            )
            resp = client.send(request, stream=True)
        except httpx.HTTPError as exc:
            client.close()
            raise AgentUnavailable(details={"reason": type(exc).__name__}) from exc
        if resp.status_code != 200:
            resp.read()
            client.close()
            raise AgentError.from_body(resp.json(), resp.status_code)

        def chunks() -> Iterator[bytes]:
            try:
                yield from resp.iter_bytes(256 * 1024)
            finally:
                resp.close()
                client.close()

        return chunks(), int(resp.headers.get("content-length", "0"))

    async def open_pty(self, *, actor: str) -> AgentPty:
        """Connect to the agent's terminal endpoint (bearer + sudo token for ``actor``)."""
        options: dict[str, Any] = {
            "additional_headers": self._headers(actor, True),
            "open_timeout": 5,
            "max_size": 1024 * 1024,
            "compression": None,
        }
        try:
            if self.socket_path:
                conn = await unix_connect(self.socket_path, "ws://agent/v1/pty", **options)
            else:
                base = (self.base_url or "").rstrip("/")
                url = "ws" + base.removeprefix("http") + "/v1/pty"
                conn = await connect(url, proxy=None, **options)
        except InvalidStatus as exc:
            raise AgentError(
                "The agent refused the terminal session",
                code="terminal.refused",
                details={"status": exc.response.status_code},
            ) from exc
        except (OSError, InvalidHandshake, TimeoutError) as exc:
            raise AgentUnavailable(details={"reason": type(exc).__name__}) from exc
        return AgentPty(conn)

    def health(self) -> bool:
        try:
            with self._client(5.0) as client:
                return bool(client.get("/v1/health").json().get("ok"))
        except (httpx.HTTPError, json.JSONDecodeError):
            return False


def _ndjson(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    for line in lines:
        if line.strip():
            yield json.loads(line)


def _fake_metrics(_params: dict[str, Any]) -> dict[str, Any]:
    import time

    now = time.time()
    return {
        "timestamp": now,
        "cpu_percent": 12.5,
        "cpu_per_core": [10.0, 15.0],
        "load1": 0.3,
        "load5": 0.2,
        "load15": 0.1,
        "memory_total": 2 * 1024**3,
        "memory_used": 1024**3,
        "memory_available": 1024**3,
        "swap_total": 1024**3,
        "swap_used": 0,
        "disks": [
            {
                "mountpoint": "/",
                "device": "/dev/sda1",
                "fstype": "ext4",
                "total": 40 * 1024**3,
                "used": 10 * 1024**3,
                "percent": 25.0,
            },
        ],
        "disk_read_bytes": int(now * 1000),
        "disk_write_bytes": int(now * 2000),
        "net": [{"interface": "eth0", "bytes_sent": int(now * 100), "bytes_recv": int(now * 300)}],
        "top_cpu": [
            {
                "pid": 1,
                "name": "systemd",
                "username": "root",
                "cpu_percent": 0.5,
                "memory_rss": 10 * 1024**2,
            }
        ],
        "top_memory": [
            {
                "pid": 1,
                "name": "systemd",
                "username": "root",
                "cpu_percent": 0.5,
                "memory_rss": 10 * 1024**2,
            }
        ],
        "uptime_seconds": 86_400,
    }


class FakePty:
    """Echo terminal used with ``FakeAgent``: mirrors the agent's dry-run session."""

    def __init__(self) -> None:
        self.start: dict[str, Any] | None = None
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self._out: asyncio.Queue[str | bytes | None] = asyncio.Queue()

    async def send(self, message: str | bytes) -> None:
        if self.closed:
            raise PtyClosed
        frame = json.loads(message)
        self.sent.append(frame)
        if self.start is None:
            self.start = frame
            self._out.put_nowait(json.dumps({"type": "started"}))
            self._out.put_nowait(b"fake terminal\r\n$ ")
        elif frame.get("type") == "input":
            self._out.put_nowait(str(frame["data"]).encode())

    async def recv(self) -> str | bytes:
        item = await self._out.get()
        if item is None:
            raise PtyClosed
        return item

    def end(self, code: int = 0) -> None:
        """Simulate the shell exiting."""
        self._out.put_nowait(json.dumps({"type": "exit", "code": code}))
        self._out.put_nowait(None)

    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._out.put_nowait(None)


class FakeAgent:
    """In-memory stand-in used by tests and ``seed_demo``. Register handlers per op."""

    def __init__(self, **_kwargs: Any) -> None:
        self.calls: list[tuple[str, dict[str, Any], str | None, bool]] = []
        self.handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "system.info": lambda _p: {
                "hostname": "demo-server",
                "os_name": "Ubuntu 24.04.3 LTS",
                "os_version": "24.04",
                "os_id": "ubuntu",
                "kernel": "6.8.0-48-generic",
                "arch": "x86_64",
                "cpu_model": "Demo CPU @ 2.40GHz",
                "cpu_cores": 2,
                "cpu_threads": 2,
                "memory_total": 2 * 1024**3,
                "swap_total": 1024**3,
                "boot_time": 1_763_000_000.0,
                "uptime_seconds": 86_400,
                "agent_version": "0.1.0",
                "executor": "fake",
            },
            "system.metrics": _fake_metrics,
        }
        self.available = True
        self.files: dict[str, bytes] = {}  # served by download()
        self.ptys: list[FakePty] = []

    def call(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        actor: str | None = None,
        sudo: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        self.calls.append((op, params, actor, sudo))
        if not self.available:
            raise AgentUnavailable(details={"reason": "fake_unavailable"})
        handler = self.handlers.get(op)
        if handler is None:
            raise AgentError(f"Unknown operation: {op}", code="agent.unknown_op", status_code=502)
        return handler(params)

    def stream(
        self,
        op: str,
        params: dict[str, Any] | None = None,
        *,
        on_event: EventCallback,
        actor: str | None = None,
        sudo: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        on_event({"type": "log", "stream": "stdout", "line": f"[fake] {op}"})
        return self.call(op, params, actor=actor, sudo=sudo)

    def download(self, path: str, *, actor: str | None = None) -> tuple[Iterator[bytes], int]:
        self.calls.append(("fs.download", {"path": path}, actor, False))
        data = self.files.get(path)
        if data is None:
            raise AgentError("Path does not exist", code="fs.not_found", status_code=404)
        return iter([data]), len(data)

    async def open_pty(self, *, actor: str) -> FakePty:
        self.calls.append(("pty.open", {}, actor, True))
        if not self.available:
            raise AgentUnavailable(details={"reason": "fake_unavailable"})
        session = FakePty()
        self.ptys.append(session)
        return session

    def health(self) -> bool:
        return self.available


@functools.cache
def _agent_class() -> type[Any]:
    cls: type[Any] = import_string(str(ed("AGENT_BACKEND")))
    return cls


_fake_singleton: FakeAgent | None = None


def get_agent() -> AgentClient | FakeAgent:
    """Return the configured agent client (FakeAgent is a singleton so tests can inspect it)."""
    global _fake_singleton
    cls = _agent_class()
    if cls is FakeAgent:
        if _fake_singleton is None:
            _fake_singleton = FakeAgent()
        return _fake_singleton
    client: AgentClient = cls()
    return client


def reset_fake_agent() -> FakeAgent:
    global _fake_singleton
    _fake_singleton = FakeAgent()
    return _fake_singleton
