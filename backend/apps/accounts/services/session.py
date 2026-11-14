"""Session helpers: entrance flag, sudo mode, login timestamps (§9.1)."""

from __future__ import annotations

import time

from django.contrib.auth import login, logout
from django.http import HttpRequest

from apps.accounts.models import User
from apps.panel.services import get_setting

ENTRANCE_KEY = "ed_entrance_ok"
LOGIN_AT_KEY = "ed_login_at"
LAST_SEEN_KEY = "ed_last_seen"
SUDO_UNTIL_KEY = "ed_sudo_until"
PENDING_2FA_KEY = "ed_pending_2fa"
PENDING_TOTP_SECRET_KEY = "ed_totp_pending_secret"  # noqa: S105  # nosec B105 - session key
PENDING_2FA_TTL = 300


def mark_entrance(request: HttpRequest) -> None:
    request.session[ENTRANCE_KEY] = True


def passed_entrance(request: HttpRequest) -> bool:
    return bool(request.session.get(ENTRANCE_KEY))


def start_session(request: HttpRequest, user: User) -> None:
    """Log the user in (rotates the session key, keeps the entrance flag) and grant sudo mode."""
    entrance = passed_entrance(request)
    request.session.pop(PENDING_2FA_KEY, None)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    now = time.time()
    request.session[LOGIN_AT_KEY] = now
    request.session[LAST_SEEN_KEY] = now
    if entrance:
        mark_entrance(request)
    grant_sudo(request)


def end_session(request: HttpRequest) -> None:
    """Log out but keep the entrance flag, so the login page stays reachable."""
    entrance = passed_entrance(request)
    logout(request)
    if entrance:
        mark_entrance(request)


def grant_sudo(request: HttpRequest) -> float:
    until = time.time() + int(get_setting("security.sudo_minutes")) * 60
    request.session[SUDO_UNTIL_KEY] = until
    return until


def sudo_until(request: HttpRequest) -> float | None:
    until = request.session.get(SUDO_UNTIL_KEY)
    if until and float(until) > time.time():
        return float(until)
    return None


def set_pending_2fa(request: HttpRequest, user: User) -> None:
    request.session[PENDING_2FA_KEY] = {"user_id": str(user.pk), "at": time.time()}


def pop_pending_2fa_user(request: HttpRequest, *, consume: bool) -> User | None:
    pending = request.session.get(PENDING_2FA_KEY)
    if not pending or time.time() - float(pending.get("at", 0)) > PENDING_2FA_TTL:
        request.session.pop(PENDING_2FA_KEY, None)
        return None
    if consume:
        request.session.pop(PENDING_2FA_KEY, None)
    return User.objects.filter(pk=pending["user_id"], is_active=True).first()


def session_expired(request: HttpRequest) -> bool:
    now = time.time()
    login_at = float(request.session.get(LOGIN_AT_KEY, 0))
    last_seen = float(request.session.get(LAST_SEEN_KEY, 0))
    idle_limit = int(get_setting("security.session_idle_minutes")) * 60
    absolute_limit = int(get_setting("security.session_absolute_hours")) * 3600
    return (now - last_seen) > idle_limit or (now - login_at) > absolute_limit


def touch(request: HttpRequest) -> None:
    now = time.time()
    if now - float(request.session.get(LAST_SEEN_KEY, 0)) > 30:
        request.session[LAST_SEEN_KEY] = now
