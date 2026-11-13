from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easydeploy_agent import ops as _ops  # noqa: F401  (registers default ops)
from easydeploy_agent.audit import AuditLog
from easydeploy_agent.executor import SandboxExecutor
from easydeploy_agent.locks import LockManager
from easydeploy_agent.registry import OpContext, registry
from easydeploy_agent.server import create_app

TOKEN = "t" * 48


@pytest.fixture
def sandbox(tmp_path: Path) -> SandboxExecutor:
    return SandboxExecutor(root=tmp_path / "root")


@pytest.fixture
def ctx(sandbox: SandboxExecutor) -> OpContext:
    return OpContext(executor=sandbox, locks=LockManager(default_timeout=1), request_id="req-1")


@pytest.fixture
def audit() -> AuditLog:
    return AuditLog(None)


@pytest.fixture
def client(sandbox: SandboxExecutor, audit: AuditLog) -> TestClient:
    app = create_app(registry=registry, executor=sandbox, token=TOKEN, audit=audit)
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}", "X-Request-ID": "req-1", "X-Actor": "user-1"}
