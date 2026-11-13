from __future__ import annotations

import io
from typing import Any

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.agent_client import FakeAgent
from apps.panel.services import get_setting

pytestmark = pytest.mark.django_db


def test_panel_info_public(client: APIClient) -> None:
    body = client.get("/api/v1/panel/info").json()
    assert body == {"name": "EasyDeploy", "default_language": "en", "languages": ["en", "fa"]}


def test_setting_change_is_audited_and_sensitive_masked(set_setting: Any) -> None:
    set_setting("panel.name", "My Panel")
    set_setting("security.entrance", "Hidden1234")
    assert get_setting("panel.name") == "My Panel"
    name_change = AuditLog.objects.get(resource_id="panel.name")
    assert name_change.changes == {"before": "EasyDeploy", "after": "My Panel"}
    entrance_change = AuditLog.objects.get(resource_id="security.entrance")
    assert entrance_change.changes == {"before": "***", "after": "***"}


def test_ed_setting_command() -> None:
    out = io.StringIO()
    call_command("ed_setting", "set", "security.entrance", "Abcdef123", stdout=out)
    assert get_setting("security.entrance") == "Abcdef123"
    call_command("ed_setting", "reset", "security.entrance", stdout=io.StringIO())
    assert get_setting("security.entrance") == ""


def test_dashboard_system_info(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    body = auth_client.get("/api/v1/dashboard/system-info").json()
    assert body["hostname"] == "demo-server"
    assert "panel_version" in body
    assert fake_agent.calls[-1][0] == "system.info"


def test_dashboard_agent_unavailable(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    fake_agent.available = False
    resp = auth_client.get("/api/v1/dashboard/system-info")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "agent.unavailable"
