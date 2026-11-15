from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from easydeploy_agent.audit import AuditLog
from easydeploy_agent.auth import make_sudo_token
from easydeploy_agent.executor import SandboxExecutor
from easydeploy_agent.pty_session import PtyStart, build_argv
from easydeploy_agent.registry import registry
from easydeploy_agent.server import create_app

TOKEN = "t" * 48


def _client(sandbox: SandboxExecutor, audit: AuditLog) -> TestClient:
    return TestClient(create_app(registry=registry, executor=sandbox, token=TOKEN, audit=audit))


def test_pty_requires_sudo_token(sandbox: SandboxExecutor) -> None:
    client = _client(sandbox, AuditLog(None))
    headers = {"Authorization": f"Bearer {TOKEN}", "X-Actor": "u1"}
    with (
        pytest.raises(WebSocketDisconnect) as info,
        client.websocket_connect("/v1/pty", headers=headers) as ws,
    ):
        ws.receive_json()
    assert info.value.code == 4403


def test_pty_echo_session(sandbox: SandboxExecutor) -> None:
    audit = AuditLog(None)
    client = _client(sandbox, audit)
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Actor": "u1",
        "X-Sudo-Token": make_sudo_token(TOKEN, "u1"),
    }
    with client.websocket_connect("/v1/pty", headers=headers) as ws:
        ws.send_json({"type": "start", "mode": "host", "cols": 100, "rows": 30})
        assert ws.receive_json() == {"type": "started"}
        assert b"dry-run terminal" in ws.receive_bytes()
        ws.send_json({"type": "input", "data": "ls"})
        assert ws.receive_bytes() == b"ls"
        ws.send_json({"type": "resize", "cols": 80, "rows": 20})
    assert [r["op"] for r in audit.records][:1] == ["pty.open"]


def test_pty_rejects_bad_start(sandbox: SandboxExecutor) -> None:
    client = _client(sandbox, AuditLog(None))
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Actor": "u1",
        "X-Sudo-Token": make_sudo_token(TOKEN, "u1"),
    }
    with client.websocket_connect("/v1/pty", headers=headers) as ws:
        ws.send_json({"type": "start", "mode": "container", "container": "x; rm -rf /"})
        assert ws.receive_json()["type"] == "error"


def test_argv() -> None:
    assert build_argv(PtyStart()) == ["/bin/bash", "-l"]
    assert build_argv(PtyStart(user="deploy")) == ["runuser", "-l", "deploy"]
    assert build_argv(PtyStart(mode="container", container="web-1", shell_path="/bin/sh")) == [
        "docker",
        "exec",
        "-it",
        "-e",
        "TERM=xterm-256color",
        "web-1",
        "/bin/sh",
    ]
