from __future__ import annotations

import io
import time
from typing import Any

import pyotp
import pytest
from conftest import PASSWORD
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import session as session_svc
from apps.audit.models import AuditLog, LoginLog

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.accounts.services.lockout.time.sleep", lambda _s: None)


def login(client: APIClient, password: str = PASSWORD, **extra: Any) -> Any:
    return client.post(
        "/api/v1/auth/login", {"username": "admin", "password": password}, format="json", **extra
    )


def test_login_success_and_me(client: APIClient, admin_user: User) -> None:
    resp = login(client)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    me = client.get("/api/v1/auth/me").json()
    assert me["user"]["username"] == "admin"
    assert me["sudo_until"] is not None
    assert me["must_enroll_2fa"] is False
    assert LoginLog.objects.filter(success=True).count() == 1
    assert AuditLog.objects.filter(action="accounts.login").exists()


def test_wrong_password(client: APIClient, admin_user: User) -> None:
    resp = login(client, "nope-nope-nope")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "auth.invalid_credentials"
    entry = LoginLog.objects.get()
    assert entry.success is False
    assert entry.reason == "bad_credentials"


def test_lockout_after_five_failures(client: APIClient, admin_user: User) -> None:
    for _ in range(5):
        assert login(client, "wrong-password-1").status_code == 400
    resp = login(client)  # correct password, but locked
    assert resp.status_code == 429
    err = resp.json()["error"]
    assert err["code"] == "auth.locked"
    assert err["details"]["retry_after"] > 0


def test_lockout_is_per_username_across_ips(client: APIClient, admin_user: User) -> None:
    for i in range(5):
        login(client, "wrong-password-1", REMOTE_ADDR=f"198.51.100.{i}")
    assert login(client, REMOTE_ADDR="198.51.100.200").status_code == 429


def test_reset_password_command_unlocks(client: APIClient, admin_user: User) -> None:
    for _ in range(5):
        login(client, "wrong-password-1")
    assert login(client).status_code == 429
    out = io.StringIO()
    call_command("ed_reset_password", stdout=out)
    new_password = out.getvalue().strip()
    assert len(new_password) >= 16
    assert AuditLog.objects.filter(action="accounts.password_reset").exists()
    # Both the username and the IP lock are cleared, so the admin can sign in from the same IP.
    assert login(client, new_password).status_code == 200


def test_logout_keeps_entrance(client: APIClient, admin_user: User, set_setting: Any) -> None:
    set_setting("security.entrance", "Secret123")
    assert client.get("/Secret123").status_code == 302
    assert login(client).status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code in {401, 403}
    assert login(client).status_code == 200


def enable_2fa(client: APIClient) -> tuple[str, list[str]]:
    setup = client.post("/api/v1/auth/2fa/setup").json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert setup["qr_svg"].startswith("data:image/svg+xml")
    code = pyotp.TOTP(setup["secret"]).now()
    resp = client.post("/api/v1/auth/2fa/enable", {"code": code}, format="json")
    assert resp.status_code == 200, resp.content
    codes = resp.json()["recovery_codes"]
    assert len(codes) == 10
    return setup["secret"], codes


def test_totp_login_flow(auth_client: APIClient, admin_user: User) -> None:
    secret, codes = enable_2fa(auth_client)
    auth_client.post("/api/v1/auth/logout")

    resp = login(auth_client)
    assert resp.json() == {"status": "2fa_required"}
    assert auth_client.get("/api/v1/auth/me").status_code in {401, 403}

    bad = auth_client.post("/api/v1/auth/login/2fa", {"code": "000000"}, format="json")
    assert bad.json()["error"]["code"] == "auth.invalid_otp"

    # Use the previous time step so the code differs from the one used during enrollment.
    totp = pyotp.TOTP(secret)
    code = totp.at(time.time() + 30)
    resp = auth_client.post("/api/v1/auth/login/2fa", {"code": code}, format="json")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Replay of the same code is rejected.
    auth_client.post("/api/v1/auth/logout")
    login(auth_client)
    replay = auth_client.post("/api/v1/auth/login/2fa", {"code": code}, format="json")
    assert replay.status_code == 400

    # A recovery code works exactly once.
    ok = auth_client.post("/api/v1/auth/login/2fa", {"recovery_code": codes[0]}, format="json")
    assert ok.status_code == 200
    auth_client.post("/api/v1/auth/logout")
    login(auth_client)
    again = auth_client.post("/api/v1/auth/login/2fa", {"recovery_code": codes[0]}, format="json")
    assert again.status_code == 400


def test_2fa_requires_pending_login(client: APIClient, admin_user: User) -> None:
    resp = client.post("/api/v1/auth/login/2fa", {"code": "123456"}, format="json")
    assert resp.json()["error"]["code"] == "auth.2fa_not_pending"


def test_reset_2fa_command(auth_client: APIClient, admin_user: User) -> None:
    enable_2fa(auth_client)
    call_command("ed_reset_2fa", stdout=io.StringIO())
    admin_user.refresh_from_db()
    assert admin_user.totp_enabled is False
    assert admin_user.recovery_codes.count() == 0


def test_sudo_mode(auth_client: APIClient, admin_user: User) -> None:
    session = auth_client.session
    session[session_svc.SUDO_UNTIL_KEY] = time.time() - 1
    session.save()
    resp = auth_client.post("/api/v1/auth/2fa/setup")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.sudo_required"

    bad = auth_client.post("/api/v1/auth/sudo", {"password": "wrong-password"}, format="json")
    assert bad.status_code == 400
    ok = auth_client.post("/api/v1/auth/sudo", {"password": PASSWORD}, format="json")
    assert ok.status_code == 200
    assert ok.json()["sudo_until"]
    assert auth_client.post("/api/v1/auth/2fa/setup").status_code == 200


def test_session_idle_timeout(auth_client: APIClient, admin_user: User) -> None:
    session = auth_client.session
    session[session_svc.LAST_SEEN_KEY] = time.time() - 3 * 3600
    session.save()
    assert auth_client.get("/api/v1/auth/me").status_code in {401, 403}


def test_password_change_policy(auth_client: APIClient, admin_user: User) -> None:
    weak = auth_client.post(
        "/api/v1/auth/password",
        {"current_password": PASSWORD, "new_password": "Password1234!"},
        format="json",
    )
    assert weak.status_code == 400
    assert "new_password" in weak.json()["error"]["details"]
    ok = auth_client.post(
        "/api/v1/auth/password",
        {"current_password": PASSWORD, "new_password": "Quiet-Lantern-5582"},
        format="json",
    )
    assert ok.status_code == 204
    assert auth_client.get("/api/v1/auth/me").status_code == 200  # session survives


def test_profile_update(auth_client: APIClient) -> None:
    resp = auth_client.patch(
        "/api/v1/auth/me",
        {"language": "fa", "calendar": "jalali", "timezone": "Asia/Tehran", "theme": "dark"},
        format="json",
    )
    assert resp.status_code == 200
    user = resp.json()["user"]
    assert (user["language"], user["calendar"], user["timezone"]) == ("fa", "jalali", "Asia/Tehran")
    bad = auth_client.patch("/api/v1/auth/me", {"timezone": "Mars/Base"}, format="json")
    assert bad.status_code == 400
    # Messages follow the user's language.
    assert bad.json()["error"]["message"] != "Some fields are invalid."


def test_create_admin_command(db: Any) -> None:
    out = io.StringIO()
    call_command("ed_create_admin", "--username", "root-admin", stdout=out)
    password = out.getvalue().strip()
    user = User.objects.get(username="root-admin")
    assert user.check_password(password)
    out = io.StringIO()
    call_command("ed_create_admin", "--if-missing", stdout=out)
    assert "exists" in out.getvalue()


def test_reset_password_ends_sessions(auth_client: APIClient) -> None:
    assert auth_client.get("/api/v1/auth/me").status_code == 200
    call_command("ed_reset_password", stdout=io.StringIO())
    assert auth_client.get("/api/v1/auth/me").status_code in {401, 403}
