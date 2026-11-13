from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.core.fields import decrypt, encrypt, rotate
from apps.core.redaction import redact_mapping, redact_text
from apps.monitoring.models import HostSample

pytestmark = pytest.mark.django_db(databases=["default", "monitor"])


def test_unknown_api_path_uses_envelope(client: APIClient) -> None:
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"]
    assert resp["X-Request-ID"] == body["error"]["request_id"]


def test_request_id_is_propagated(client: APIClient) -> None:
    resp = client.get("/api/v1/health", HTTP_X_REQUEST_ID="abc12345-request")
    assert resp["X-Request-ID"] == "abc12345-request"
    # Malformed IDs are replaced.
    resp = client.get("/api/v1/health", HTTP_X_REQUEST_ID="bad id with spaces")
    assert resp["X-Request-ID"] != "bad id with spaces"


def test_health_only_from_localhost(client: APIClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    resp = client.get("/api/v1/health", REMOTE_ADDR="203.0.113.9")
    assert resp.status_code == 404


def test_health_trusts_nginx_real_ip_header(client: APIClient) -> None:
    # Over the Unix socket there is no REMOTE_ADDR; Nginx sets X-Real-IP.
    resp = client.get("/api/v1/health", REMOTE_ADDR="", HTTP_X_REAL_IP="203.0.113.9")
    assert resp.status_code == 404
    # A client-supplied X-Real-IP on a direct connection is ignored.
    resp = client.get("/api/v1/health", REMOTE_ADDR="203.0.113.9", HTTP_X_REAL_IP="127.0.0.1")
    assert resp.status_code == 404


def test_validation_error_envelope(client: APIClient) -> None:
    resp = client.post("/api/v1/auth/login", {"username": "x"}, format="json")
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert "password" in err["details"]


def test_encryption_roundtrip() -> None:
    token = encrypt("s3cret value")
    assert token.startswith("fernet:")
    assert "s3cret" not in token
    assert decrypt(token) == "s3cret value"
    assert decrypt(rotate(token)) == "s3cret value"


def test_redaction() -> None:
    text = "password=hunter2 url=postgres://user:pa55@db:5432 Authorization: Bearer abcdefghijk"
    out = redact_text(text, extra_secrets=["topsecretvalue"])
    assert "hunter2" not in out
    assert "pa55" not in out
    assert "abcdefghijk" not in out
    assert redact_text("token is topsecretvalue", ["topsecretvalue"]) == "token is ***"
    assert redact_mapping({"db_password": "x", "nested": {"api_key": "y", "name": "n"}}) == {
        "db_password": "***",
        "nested": {"api_key": "***", "name": "n"},
    }


def test_monitor_models_use_monitor_db() -> None:
    from django.utils import timezone

    sample = HostSample.objects.create(ts=timezone.now(), cpu_percent=12.5)
    assert sample._state.db == "monitor"
    assert HostSample.objects.count() == 1
