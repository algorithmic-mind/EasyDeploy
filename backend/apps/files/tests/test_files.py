from __future__ import annotations

import hashlib
import time
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import session as session_svc
from apps.audit.models import AuditLog
from apps.core.agent_client import FakeAgent
from apps.files import services
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


def test_list_marks_protected(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["fs.list"] = lambda p: {
        "path": p["path"],
        "entries": [{"path": "/etc/nginx", "name": "nginx"}, {"path": "/srv/x", "name": "x"}],
        "truncated": False,
    }
    body = auth_client.get("/api/v1/files/list", {"path": "/etc"}).json()
    assert body["protected"] is True
    assert [e["protected"] for e in body["entries"]] == [True, False]


def test_write_is_audited(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["fs.write"] = lambda p: {"path": p["path"], "sha256": "x", "size": 3}
    resp = auth_client.put(
        "/api/v1/files/content", {"path": "/srv/a.txt", "content": "abc"}, format="json"
    )
    assert resp.status_code == 200
    assert fake_agent.calls[-1][1] == {"path": "/srv/a.txt", "content": "abc", "create_only": False}
    assert AuditLog.objects.filter(action="files.write").exists()


def test_purge_requires_sudo(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["fs.recycle_purge"] = lambda p: {"ok": True, "count": 1}
    session = auth_client.session
    session[session_svc.SUDO_UNTIL_KEY] = 0
    session.save()
    resp = auth_client.post("/api/v1/files/recycle/purge", {"all": True}, format="json")
    assert resp.json()["error"]["code"] == "auth.sudo_required"
    session[session_svc.SUDO_UNTIL_KEY] = time.time() + 60
    session.save()
    resp = auth_client.post("/api/v1/files/recycle/purge", {"all": True}, format="json")
    assert resp.status_code == 200
    assert fake_agent.calls[-1][3] is True  # sudo token sent to the agent


def test_task_ops_start_tasks(
    auth_client: APIClient, fake_agent: FakeAgent, django_capture_on_commit_callbacks: Any
) -> None:
    fake_agent.handlers["fs.compress"] = lambda p: {"path": p["destination"], "size": 10}
    with django_capture_on_commit_callbacks(execute=True):
        resp = auth_client.post(
            "/api/v1/files/tasks/compress",
            {"paths": ["/srv/site"], "destination": "/srv/site.zip", "format": "zip"},
            format="json",
        )
    assert resp.status_code == 202
    task = Task.objects.get(pk=resp.json()["task_id"])
    assert task.status == Task.Status.SUCCEEDED
    assert task.result == {"path": "/srv/site.zip", "size": 10}
    assert auth_client.post("/api/v1/files/tasks/nope", {}, format="json").status_code == 404
    bad = auth_client.post(
        "/api/v1/files/tasks/fetch", {"url": "file:///etc/passwd"}, format="json"
    )
    assert bad.status_code == 400


def test_download_streams(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.files["/srv/گزارش.txt"] = b"hello"
    resp = auth_client.get("/api/v1/files/download", {"path": "/srv/گزارش.txt"})
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == b"hello"
    assert resp["Content-Disposition"].startswith("attachment; filename*=UTF-8''")
    missing = auth_client.get("/api/v1/files/download", {"path": "/nope"})
    assert missing.status_code == 404


def _put_chunk(client: APIClient, upload_id: str, index: int, data: bytes, sha: bool = True) -> Any:
    headers = {"HTTP_X_CHUNK_SHA256": hashlib.sha256(data).hexdigest()} if sha else {}
    return client.put(
        f"/api/v1/files/uploads/{upload_id}/chunks/{index}",
        data,
        content_type="application/octet-stream",
        **headers,
    )


def test_resumable_upload(
    auth_client: APIClient, fake_agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "CHUNK_SIZE", 4)
    fake_agent.handlers["fs.upload_finalize"] = lambda p: {
        "path": p["destination"],
        "size": p["size"],
    }
    created = auth_client.post(
        "/api/v1/files/uploads",
        {"directory": "/srv/files", "filename": "data.bin", "size": 10},
        format="json",
    ).json()
    uid = created["id"]
    assert created["total_chunks"] == 3
    assert _put_chunk(auth_client, uid, 0, b"0123").status_code == 204
    # Pause: the client asks what the server already has, then resumes.
    assert auth_client.get(f"/api/v1/files/uploads/{uid}").json()["received"] == [0]
    incomplete = auth_client.post(f"/api/v1/files/uploads/{uid}/complete")
    assert incomplete.json()["error"]["details"]["missing"] == [1, 2]
    assert _put_chunk(auth_client, uid, 1, b"4567").status_code == 204
    bad = auth_client.put(
        f"/api/v1/files/uploads/{uid}/chunks/2",
        b"89",
        content_type="application/octet-stream",
        HTTP_X_CHUNK_SHA256="0" * 64,
    )
    assert bad.json()["error"]["code"] == "files.chunk_checksum"
    assert _put_chunk(auth_client, uid, 2, b"89").status_code == 204
    done = auth_client.post(f"/api/v1/files/uploads/{uid}/complete")
    assert done.json() == {"path": "/srv/files/data.bin", "size": 10}
    assert fake_agent.calls[-1][1]["chunks"] == 3
    assert AuditLog.objects.filter(action="files.upload").exists()


@pytest.mark.parametrize("name", ["../x", "a/b", "", ".."])
def test_upload_rejects_bad_names(auth_client: APIClient, name: str) -> None:
    resp = auth_client.post(
        "/api/v1/files/uploads", {"directory": "/srv", "filename": name, "size": 1}, format="json"
    )
    assert resp.status_code == 400


def test_upload_size_limit(auth_client: APIClient, set_setting: Any) -> None:
    set_setting("files.max_upload_mb", 1)
    resp = auth_client.post(
        "/api/v1/files/uploads",
        {"directory": "/srv", "filename": "big.iso", "size": 2 * 1024 * 1024},
        format="json",
    )
    assert resp.status_code == 400
