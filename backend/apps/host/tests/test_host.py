from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.agent_client import AgentError, FakeAgent

pytestmark = pytest.mark.django_db


def test_process_list_passes_params(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["proc.list"] = lambda p: {"processes": [{"pid": 1}], "total": 1}
    body = auth_client.get("/api/v1/host/processes", {"sort": "memory", "limit": "10"}).json()
    assert body["total"] == 1
    assert fake_agent.calls[-1][:2] == ("proc.list", {"sort": "memory", "limit": 10})


def test_signal_is_audited(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["proc.signal"] = lambda p: {"pid": p["pid"], "signal": p["signal"]}
    resp = auth_client.post("/api/v1/host/processes/321/signal", {"signal": "KILL"}, format="json")
    assert resp.json() == {"pid": 321, "signal": "KILL"}
    entry = AuditLog.objects.get(action="host.process_signal")
    assert entry.resource_id == "321"
    bad = auth_client.post("/api/v1/host/processes/321/signal", {"signal": "STOP"}, format="json")
    assert bad.status_code == 400


def test_agent_errors_are_forwarded(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    def refuse(_p: dict[str, Any]) -> dict[str, Any]:
        raise AgentError("This process is protected", code="proc.protected", status_code=403)

    fake_agent.handlers["proc.signal"] = refuse
    resp = auth_client.post("/api/v1/host/processes/1/signal", {"signal": "TERM"}, format="json")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "proc.protected"


def test_service_action(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["service.action"] = lambda p: {
        "unit": f"{p['unit']}.service",
        "action": p["action"],
        "active_state": "active",
    }
    resp = auth_client.post(
        "/api/v1/host/services/cron/action", {"action": "restart"}, format="json"
    )
    assert resp.json()["unit"] == "cron.service"
    assert AuditLog.objects.filter(
        action="host.service_action", resource_id="cron.service"
    ).exists()


def test_journal_query_params(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.handlers["journal.query"] = lambda p: {"entries": []}
    auth_client.get(
        "/api/v1/host/journal", {"unit": "nginx", "priority": "3", "lines": "50", "grep": "x"}
    )
    assert fake_agent.calls[-1][1] == {"unit": "nginx", "grep": "x", "priority": 3, "lines": 50}


def test_api_key_needs_host_scope(admin_user: Any, fake_agent: FakeAgent) -> None:
    from apps.accounts.services import api_keys

    fake_agent.handlers["service.list"] = lambda p: {"units": []}
    _k, raw = api_keys.create_key(admin_user, name="ro", scopes=["host:read"])
    bot = APIClient()
    assert bot.get("/api/v1/host/services", HTTP_X_API_KEY=raw).status_code == 200
    resp = bot.post(
        "/api/v1/host/services/cron/action", {"action": "stop"}, format="json", HTTP_X_API_KEY=raw
    )
    assert resp.status_code == 403
