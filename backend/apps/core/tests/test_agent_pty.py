"""``AgentClient.open_pty`` against the real agent app (dry-run executor) over TCP."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from apps.core.agent_client import AgentClient, AgentError, AgentUnavailable
from easydeploy_agent.audit import AuditLog
from easydeploy_agent.executor import DryRunExecutor
from easydeploy_agent.registry import registry
from easydeploy_agent.server import create_app

TOKEN = "p" * 48


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def agent_url() -> Iterator[str]:
    app = create_app(
        registry=registry, executor=DryRunExecutor(), token=TOKEN, audit=AuditLog(None)
    )
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(5)


@pytest.mark.asyncio
async def test_open_pty_round_trip(agent_url: str) -> None:
    client = AgentClient(base_url=agent_url, token=TOKEN)
    pty = await client.open_pty(actor="u1")
    try:
        await pty.send(json.dumps({"type": "start", "mode": "host"}))
        assert json.loads(await pty.recv()) == {"type": "started"}
        assert b"dry-run terminal" in await pty.recv()
        await pty.send(json.dumps({"type": "input", "data": "whoami"}))
        assert await pty.recv() == b"whoami"
    finally:
        await pty.close()


@pytest.mark.asyncio
async def test_open_pty_wrong_token(agent_url: str) -> None:
    client = AgentClient(base_url=agent_url, token="x" * 48)
    with pytest.raises(AgentError) as info:
        await client.open_pty(actor="u1")
    assert info.value.code == "terminal.refused"


@pytest.mark.asyncio
async def test_open_pty_agent_down() -> None:
    client = AgentClient(base_url=f"http://127.0.0.1:{_free_port()}", token=TOKEN)
    with pytest.raises(AgentUnavailable):
        await client.open_pty(actor="u1")
