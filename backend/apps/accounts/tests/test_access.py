"""Entrance, IP allowlist, bind domain and API keys."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from conftest import PASSWORD
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ApiKey, User
from apps.accounts.services import api_keys

pytestmark = pytest.mark.django_db


def test_wrong_entrance_hides_panel(client: APIClient, admin_user: User, set_setting: Any) -> None:
    set_setting("security.entrance", "OpenSesame42")
    assert client.get("/api/v1/panel/info").status_code == 404
    assert client.get("/").status_code == 404
    assert client.get("/wrong-entrance").status_code == 404
    resp = client.post(
        "/api/v1/auth/login", {"username": "admin", "password": PASSWORD}, format="json"
    )
    assert resp.status_code == 404

    assert client.get("/OpenSesame42").status_code == 302
    assert client.get("/api/v1/panel/info").status_code == 200


def test_entrance_drop_mode(client: APIClient, set_setting: Any) -> None:
    set_setting("security.entrance", "OpenSesame42")
    set_setting("security.entrance_response", "drop")
    assert client.get("/api/v1/panel/info").status_code == 444


def test_health_bypasses_entrance_only_locally(client: APIClient, set_setting: Any) -> None:
    set_setting("security.entrance", "OpenSesame42")
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health", REMOTE_ADDR="203.0.113.5").status_code == 404


def test_ip_allowlist(client: APIClient, set_setting: Any) -> None:
    set_setting("security.ip_allowlist", ["10.0.0.0/8"])
    assert client.get("/api/v1/panel/info", REMOTE_ADDR="203.0.113.5").status_code == 404
    assert client.get("/api/v1/panel/info", REMOTE_ADDR="10.1.2.3").status_code == 200
    assert client.get("/api/v1/panel/info").status_code == 200  # localhost always allowed


def test_bind_domain(client: APIClient, set_setting: Any) -> None:
    set_setting("security.bind_domain", "panel.example.com")
    remote = {"REMOTE_ADDR": "203.0.113.5"}
    assert client.get("/api/v1/panel/info", HTTP_HOST="1.2.3.4:28443", **remote).status_code == 404
    ok = client.get("/api/v1/panel/info", HTTP_HOST="panel.example.com:28443", **remote)
    assert ok.status_code == 200


def test_invalid_settings_rejected(set_setting: Any) -> None:
    from apps.core.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        set_setting("security.entrance", "../etc")
    with pytest.raises(ValidationFailed):
        set_setting("security.ip_allowlist", ["not-an-ip"])


def create_key(client: APIClient, scopes: list[str]) -> str:
    resp = client.post("/api/v1/auth/api-keys", {"name": "ci", "scopes": scopes}, format="json")
    assert resp.status_code == 201, resp.content
    key: str = resp.json()["key"]
    assert key.startswith("ed_")
    return key


def test_api_key_lifecycle(auth_client: APIClient, admin_user: User) -> None:
    raw = create_key(auth_client, ["tasks:read"])
    stored = ApiKey.objects.get()
    assert stored.key_hash != raw
    assert raw not in stored.key_hash

    bot = APIClient()
    assert bot.get("/api/v1/tasks", HTTP_X_API_KEY=raw).status_code == 200
    # Write scope missing.
    resp = bot.post("/api/v1/tasks/diagnostics", HTTP_X_API_KEY=raw)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.api_key_forbidden"
    # Credential management is session-only.
    assert bot.get("/api/v1/auth/me", HTTP_X_API_KEY=raw).status_code == 403
    # No scope for this module.
    assert bot.get("/api/v1/audit/logs", HTTP_X_API_KEY=raw).status_code == 403

    listed = auth_client.get("/api/v1/auth/api-keys").json()["results"]
    assert listed[0]["prefix"] == stored.prefix
    assert "key" not in listed[0]

    assert auth_client.delete(f"/api/v1/auth/api-keys/{stored.pk}").status_code == 204
    resp = bot.get("/api/v1/tasks", HTTP_X_API_KEY=raw)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.authentication_failed"


def test_api_key_expiry_and_ip(admin_user: User) -> None:
    key, raw = api_keys.create_key(
        admin_user, name="x", scopes=["*:read"], ip_allowlist=["192.0.2.0/24"]
    )
    assert api_keys.lookup(raw, "192.0.2.10") is not None
    assert api_keys.lookup(raw, "198.51.100.1") is None
    key.expires_at = timezone.now() - timedelta(seconds=1)
    key.save()
    assert api_keys.lookup(raw, "192.0.2.10") is None
    assert api_keys.lookup("ed_garbage", None) is None


def test_api_key_bypasses_entrance(admin_user: User, set_setting: Any) -> None:
    _key, raw = api_keys.create_key(admin_user, name="x", scopes=["*:read"])
    set_setting("security.entrance", "OpenSesame42")
    bot = APIClient()
    assert bot.get("/api/v1/tasks", HTTP_X_API_KEY=raw).status_code == 200
    assert bot.get("/api/v1/tasks", HTTP_X_API_KEY="ed_aaaaaaaa_" + "b" * 40).status_code == 404


def test_api_key_create_requires_sudo(auth_client: APIClient) -> None:
    from apps.accounts.services import session as session_svc

    session = auth_client.session
    session[session_svc.SUDO_UNTIL_KEY] = 0
    session.save()
    resp = auth_client.post(
        "/api/v1/auth/api-keys", {"name": "x", "scopes": ["*:read"]}, format="json"
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.sudo_required"


def test_api_key_scope_validation(auth_client: APIClient) -> None:
    resp = auth_client.post(
        "/api/v1/auth/api-keys", {"name": "x", "scopes": ["root"]}, format="json"
    )
    assert resp.status_code == 400
    assert "scopes" in resp.json()["error"]["details"]
