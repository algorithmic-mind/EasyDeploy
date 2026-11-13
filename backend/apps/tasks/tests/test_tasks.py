from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import WebsocketCommunicator
from django.test import Client
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.agent_client import FakeAgent
from apps.tasks import services
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db(transaction=True)


def start_diagnostics(client: APIClient) -> Task:
    resp = client.post("/api/v1/tasks/diagnostics")
    assert resp.status_code == 202, resp.content
    return Task.objects.get(pk=resp.json()["task_id"])


def test_diagnostics_task_succeeds(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    task = start_diagnostics(auth_client)
    assert task.status == Task.Status.SUCCEEDED
    assert task.progress == 100
    assert task.result == {"checks": {"database": "ok", "agent": "ok"}}
    lines = auth_client.get(f"/api/v1/tasks/{task.id}/log").json()["lines"]
    assert any("demo-server" in line for line in lines)
    assert AuditLog.objects.filter(action="tasks.diagnostics_started").exists()

    listed = auth_client.get("/api/v1/tasks", {"status": "succeeded"}).json()
    assert listed["count"] == 1
    assert listed["results"][0]["title_key"] == "tasks.titles.diagnostics"


def test_diagnostics_task_fails_when_agent_down(
    auth_client: APIClient, fake_agent: FakeAgent
) -> None:
    fake_agent.available = False
    task = start_diagnostics(auth_client)
    assert task.status == Task.Status.FAILED
    assert task.error["code"] == "tasks.diagnostics_failed"
    assert task.error["details"]["checks"]["agent"] == "unreachable"


def test_secrets_never_reach_task_logs(db: Any) -> None:
    task = services.create_task(kind="t", title_key="t")
    rec = services.TaskRecorder(task, secrets=["hunter2-very-secret"])
    rec.log("connecting with password=abc123 and hunter2-very-secret")
    content = Path(task.log_path).read_text(encoding="utf-8")
    assert "abc123" not in content
    assert "hunter2-very-secret" not in content


def test_cancel_pending_task(auth_client: APIClient) -> None:
    task = services.create_task(kind="t", title_key="t")
    resp = auth_client.post(f"/api/v1/tasks/{task.id}/cancel")
    assert resp.json()["status"] == "cancelled"
    assert AuditLog.objects.filter(action="tasks.cancelled").exists()


def test_worker_lost_recovery(db: Any) -> None:
    task = services.create_task(kind="t", title_key="t")
    Task.objects.filter(pk=task.pk).update(status=Task.Status.RUNNING)
    assert services.mark_worker_lost() == 1
    task.refresh_from_db()
    assert task.status == Task.Status.FAILED
    assert task.error["code"] == "task.worker_lost"


def _session_cookie(client: Client) -> bytes:
    return f"ed_session={client.cookies['ed_session'].value}".encode()


@pytest.mark.asyncio
async def test_task_websocket_replays_and_streams(auth_client: APIClient) -> None:
    from asgiref.sync import sync_to_async

    from easydeploy.asgi import application

    task = await sync_to_async(services.create_task)(kind="t", title_key="t")
    rec = await sync_to_async(services.TaskRecorder)(task)
    await sync_to_async(rec.log)("first line")

    headers = [
        (b"cookie", _session_cookie(auth_client)),
        (b"origin", b"http://testserver"),
        (b"host", b"testserver"),
    ]
    comm = WebsocketCommunicator(application, f"/ws/tasks/{task.id}/", headers=headers)
    connected, _ = await comm.connect()
    assert connected
    snapshot = await comm.receive_json_from()
    assert snapshot["type"] == "snapshot"
    assert snapshot["lines"] == ["first line"]

    await sync_to_async(rec.log)("second line")
    event = await comm.receive_json_from()
    assert event == {"type": "log", "seq": 2, "line": "second line", "stream": "stdout"}
    await comm.disconnect()


@pytest.mark.asyncio
async def test_task_websocket_rejects_anonymous_and_cross_origin(auth_client: APIClient) -> None:
    from easydeploy.asgi import application

    anon = WebsocketCommunicator(
        application,
        "/ws/tasks/00000000-0000-0000-0000-000000000000/",
        headers=[(b"origin", b"http://testserver"), (b"host", b"testserver")],
    )
    connected, code = await anon.connect()
    assert not connected
    assert code == 4401

    evil = WebsocketCommunicator(
        application,
        "/ws/tasks/00000000-0000-0000-0000-000000000000/",
        headers=[
            (b"cookie", _session_cookie(auth_client)),
            (b"origin", b"https://evil.example"),
            (b"host", b"testserver"),
        ],
    )
    connected, code = await evil.connect()
    assert not connected
    assert code == 4403
