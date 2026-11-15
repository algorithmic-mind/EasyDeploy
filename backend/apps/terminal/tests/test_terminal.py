from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import WebsocketCommunicator
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.agent_client import FakeAgent
from apps.terminal.models import Snippet


def _drop_sudo(client: APIClient) -> None:
    from apps.accounts.services import session as session_svc

    session = client.session
    session[session_svc.SUDO_UNTIL_KEY] = 0
    session.save()


def _socket(client: APIClient, session_id: str = "tab-1") -> WebsocketCommunicator:
    from easydeploy.asgi import application

    return WebsocketCommunicator(
        application,
        f"/ws/terminal/{session_id}/",
        headers=[
            (b"cookie", f"ed_session={client.cookies['ed_session'].value}".encode()),
            (b"origin", b"http://testserver"),
            (b"host", b"testserver"),
        ],
    )


async def _frame(comm: WebsocketCommunicator) -> Any:
    """Next message: bytes for terminal output, a dict for JSON control frames."""
    message = await comm.receive_output(2)
    if message["type"] == "websocket.close":
        return ("close", message.get("code"))
    if message.get("bytes") is not None:
        return message["bytes"]
    return json.loads(message["text"])


async def _send(comm: WebsocketCommunicator, frame: dict[str, Any]) -> None:
    await comm.send_input({"type": "websocket.receive", "text": json.dumps(frame)})


def test_check_requires_sudo(auth_client: APIClient) -> None:
    resp = auth_client.post("/api/v1/terminal/check")
    assert resp.status_code == 200
    assert resp.json()["idle_minutes"] == 30
    _drop_sudo(auth_client)
    resp = auth_client.post("/api/v1/terminal/check")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.sudo_required"


def test_snippets_crud_is_audited(auth_client: APIClient) -> None:
    resp = auth_client.post(
        "/api/v1/terminal/snippets",
        {"name": "Disk usage", "command": "df -h\n", "description": "free space"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    snippet_id = resp.json()["id"]
    assert Snippet.objects.get(pk=snippet_id).command == "df -h\n"

    listing = auth_client.get("/api/v1/terminal/snippets").json()
    assert [row["name"] for row in listing["results"]] == ["Disk usage"]

    resp = auth_client.patch(
        f"/api/v1/terminal/snippets/{snippet_id}", {"command": "df -hT"}, format="json"
    )
    assert resp.status_code == 200
    assert auth_client.delete(f"/api/v1/terminal/snippets/{snippet_id}").status_code == 204
    # Rows written in the same clock tick share created_at, so compare without ordering.
    actions = AuditLog.objects.filter(module="terminal").values_list("action", flat=True)
    assert sorted(actions) == [
        "terminal.snippet_created",
        "terminal.snippet_deleted",
        "terminal.snippet_updated",
    ]


def test_snippet_rejects_blank_command(auth_client: APIClient) -> None:
    resp = auth_client.post(
        "/api/v1/terminal/snippets", {"name": "x", "command": "   "}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_terminal_requires_sudo(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    from asgiref.sync import sync_to_async

    await sync_to_async(_drop_sudo)(auth_client)
    comm = _socket(auth_client)
    connected, code = await comm.connect()
    assert not connected
    assert code == 4403
    assert fake_agent.ptys == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_terminal_session_bridges_and_audits(
    auth_client: APIClient, fake_agent: FakeAgent
) -> None:
    from asgiref.sync import sync_to_async

    comm = _socket(auth_client, "tab-7")
    connected, _ = await comm.connect()
    assert connected
    await _send(comm, {"type": "start", "mode": "host", "user": "root", "cols": 100, "rows": 30})
    assert await _frame(comm) == {"type": "started"}
    assert b"fake terminal" in await _frame(comm)

    await _send(comm, {"type": "input", "data": "ls\r"})
    assert await _frame(comm) == b"ls\r"
    await _send(comm, {"type": "resize", "cols": 9999, "rows": 40})
    await _send(comm, {"type": "input", "data": "x"})
    assert await _frame(comm) == b"x"  # frames are handled in order: the resize went first

    pty = fake_agent.ptys[0]
    assert pty.start is not None
    assert pty.start["cols"] == 100
    assert {"type": "resize", "cols": 500, "rows": 40} in pty.sent
    assert fake_agent.calls[-1][0] == "pty.open"
    assert fake_agent.calls[-1][3] is True

    await comm.disconnect()
    assert pty.closed
    entries = await sync_to_async(
        lambda: dict(AuditLog.objects.filter(resource_id="tab-7").values_list("action", "details"))
    )()
    assert set(entries) == {"terminal.session_started", "terminal.session_ended"}
    assert entries["terminal.session_started"]["mode"] == "host"
    assert "duration_seconds" in entries["terminal.session_ended"]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_terminal_rejects_bad_start(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    comm = _socket(auth_client)
    assert (await comm.connect())[0]
    await _send(comm, {"type": "start", "mode": "container", "container": "bad name;rm"})
    error = await _frame(comm)
    assert error["code"] == "terminal.invalid_start"
    assert "container" in error["fields"]
    assert await _frame(comm) == ("close", 4400)
    assert fake_agent.ptys == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_terminal_agent_unavailable(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.available = False
    comm = _socket(auth_client)
    assert (await comm.connect())[0]
    await _send(comm, {"type": "start"})
    assert (await _frame(comm))["code"] == "agent.unavailable"
    assert await _frame(comm) == ("close", 4502)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_terminal_shell_exit_closes(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    comm = _socket(auth_client)
    assert (await comm.connect())[0]
    await _send(comm, {"type": "start"})
    await _frame(comm)  # started
    await _frame(comm)  # banner
    fake_agent.ptys[0].end(code=3)
    assert await _frame(comm) == {"type": "exit", "code": 3}
    assert (await _frame(comm))[0] == "close"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_terminal_idle_timeout(
    auth_client: APIClient, fake_agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.terminal import consumers

    async def no_idle() -> int:
        return 0

    monkeypatch.setattr(consumers, "_idle_seconds", no_idle)
    comm = _socket(auth_client)
    assert (await comm.connect())[0]
    await _send(comm, {"type": "start"})
    frames = [await _frame(comm) for _ in range(4)]
    assert {"type": "error", "code": "terminal.idle_timeout", "fields": []} in frames
    assert ("close", 4408) in frames
