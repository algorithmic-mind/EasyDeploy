from __future__ import annotations

import json

from fastapi.testclient import TestClient

from easydeploy_agent.audit import AuditLog
from easydeploy_agent.auth import make_sudo_token, verify_sudo_token
from easydeploy_agent.executor import SandboxExecutor
from easydeploy_agent.protocol.base import Empty, StrictModel
from easydeploy_agent.registry import OpContext, Registry
from easydeploy_agent.server import create_app

TOKEN = "t" * 48  # same value as conftest.TOKEN


def test_health_needs_no_token(client: TestClient) -> None:
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "result": {"status": "ok", "executor": "sandbox"}}


def test_ops_require_token(client: TestClient) -> None:
    assert client.get("/v1/ops").status_code == 401
    resp = client.post("/v1/ops/system.info", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "agent.unauthorized"


def test_list_ops(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/v1/ops", headers=auth_headers)
    names = {o["name"] for o in resp.json()["result"]["ops"]}
    assert {"system.info", "service.status", "fs.list"} <= names


def test_invoke_ok(
    client: TestClient, auth_headers: dict[str, str], sandbox: SandboxExecutor, audit: AuditLog
) -> None:
    sandbox.write_text("/tmp/x/file.txt", "hi")
    resp = client.post("/v1/ops/fs.list", headers=auth_headers, json={"path": "/tmp/x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["result"]["entries"][0]["name"] == "file.txt"
    assert audit.records[-1]["actor"] == "user-1"


def test_invoke_errors(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post("/v1/ops/nope", headers=auth_headers, json={})
    assert resp.status_code == 404
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "agent.unknown_op",
            "message": "Unknown operation: nope",
            "details": {"op": "nope"},
        },
    }
    resp = client.post("/v1/ops/fs.list", headers=auth_headers, json={"path": "relative"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "agent.invalid_params"
    resp = client.post("/v1/ops/fs.list", headers=auth_headers, content=b"[1,2]")
    assert resp.json()["error"]["code"] == "agent.bad_json"


class Num(StrictModel):
    n: int


def _sensitive_app(sandbox: SandboxExecutor) -> TestClient:
    reg = Registry()

    @reg.op("test.secret", params=Empty, result=Num, sensitive=True)
    def secret(_p: Empty, _ctx: OpContext) -> Num:
        return Num(n=42)

    @reg.op("test.count", params=Num, result=Num, stream=True)
    def count(params: Num, ctx: OpContext) -> Num:
        for i in range(params.n):
            ctx.emit_log(f"line {i}")
        ctx.emit_progress(100)
        return Num(n=params.n)

    return TestClient(create_app(registry=reg, executor=sandbox, token=TOKEN, audit=AuditLog(None)))


def test_sensitive_op_requires_sudo_token(
    sandbox: SandboxExecutor, auth_headers: dict[str, str]
) -> None:
    client = _sensitive_app(sandbox)
    resp = client.post("/v1/ops/test.secret", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "agent.sudo_required"
    # A token minted for another actor is rejected.
    other = make_sudo_token(TOKEN, "user-2")
    resp = client.post("/v1/ops/test.secret", headers={**auth_headers, "X-Sudo-Token": other})
    assert resp.status_code == 403
    good = make_sudo_token(TOKEN, "user-1")
    resp = client.post("/v1/ops/test.secret", headers={**auth_headers, "X-Sudo-Token": good})
    assert resp.json() == {"ok": True, "result": {"n": 42}}


def test_stream_ndjson(sandbox: SandboxExecutor, auth_headers: dict[str, str]) -> None:
    client = _sensitive_app(sandbox)
    resp = client.post("/v1/ops/test.count/stream", headers=auth_headers, json={"n": 3})
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in resp.text.splitlines()]
    assert [e["type"] for e in events] == ["log", "log", "log", "progress", "result"]
    assert events[-1]["result"] == {"n": 3}


def test_sudo_token_expiry_and_tamper() -> None:
    token = make_sudo_token(TOKEN, "u", ttl=60, now=1000)
    assert verify_sudo_token(TOKEN, token, "u", now=1001)
    assert not verify_sudo_token(TOKEN, token, "u", now=1061)
    assert not verify_sudo_token(TOKEN, token[:-1] + "0", "u", now=1001)
    assert not verify_sudo_token("x" * 48, token, "u", now=1001)
    assert not verify_sudo_token(TOKEN, "garbage", "u", now=1001)
