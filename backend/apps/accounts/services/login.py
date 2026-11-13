"""Login, two-factor completion, sudo re-authentication, logout."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import authenticate
from django.http import HttpRequest

from apps.accounts.errors import InvalidCredentials, InvalidOtp, TwoFactorNotPending
from apps.accounts.models import User
from apps.accounts.services import session, totp
from apps.accounts.services.lockout import LoginGuard
from apps.audit.services import record, record_login
from apps.core.net import client_ip


@dataclass(frozen=True)
class LoginOutcome:
    status: str  # "ok" | "2fa_required"
    user: User | None = None


def login_with_password(request: HttpRequest, username: str, password: str) -> LoginOutcome:
    guard = LoginGuard(client_ip(request), username)
    guard.check()
    user = authenticate(request, username=username, password=password)
    if user is None or not isinstance(user, User):
        guard.failure()
        record_login(request, username, success=False, reason="bad_credentials")
        raise InvalidCredentials()
    if user.totp_enabled:
        session.set_pending_2fa(request, user)
        return LoginOutcome("2fa_required")
    guard.success()
    _complete(request, user, method="password")
    return LoginOutcome("ok", user)


def login_second_factor(
    request: HttpRequest, *, code: str = "", recovery_code: str = ""
) -> LoginOutcome:
    user = session.pop_pending_2fa_user(request, consume=False)
    if user is None:
        raise TwoFactorNotPending()
    guard = LoginGuard(client_ip(request), user.get_username())
    guard.check()
    if recovery_code:
        ok = totp.use_recovery_code(user, recovery_code)
        method = "recovery_code"
    else:
        ok = totp.verify_user_code(user, code)
        method = "totp"
    if not ok:
        guard.failure()
        record_login(request, user.get_username(), success=False, reason="bad_2fa", user=user)
        raise InvalidOtp()
    guard.success()
    _complete(request, user, method=method)
    return LoginOutcome("ok", user)


def _complete(request: HttpRequest, user: User, *, method: str) -> None:
    session.start_session(request, user)
    record_login(request, user.get_username(), success=True, reason="ok", user=user)
    record("accounts.login", request=request, actor=user, details={"method": method})


def confirm_sudo(request: HttpRequest, user: User, *, password: str, code: str = "") -> float:
    """Re-authenticate for sensitive actions (§9.1 sudo mode)."""
    guard = LoginGuard(client_ip(request), user.get_username())
    guard.check()
    ok = user.check_password(password)
    if ok and user.totp_enabled:
        ok = totp.verify_user_code(user, code)
    if not ok:
        guard.failure()
        record("accounts.sudo", request=request, result="failure")
        raise InvalidCredentials()
    guard.success()
    until = session.grant_sudo(request)
    record("accounts.sudo", request=request)
    return until


def logout_user(request: HttpRequest) -> None:
    if request.user.is_authenticated:
        record("accounts.logout", request=request)
    session.end_session(request)
