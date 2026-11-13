"""Authentication endpoints under ``/api/v1/auth/`` (§9.1). Thin views: logic is in services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from django.contrib.auth import update_session_auth_hash
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import serializers as s
from apps.accounts.authentication import CsrfProtectedMixin
from apps.accounts.errors import TwoFactorEnforced
from apps.accounts.models import ApiKey, User
from apps.accounts.permissions import RequireSudo, SessionOnly
from apps.accounts.services import api_keys, login, session, totp
from apps.audit.services import record
from apps.core.permissions import IsPanelAdmin
from apps.panel.services import get_setting


def current_user(request: Request) -> User:
    """The authenticated panel user (views using this require IsAuthenticated)."""
    return cast(User, request.user)


def _ts(value: float | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value else None


def _me_payload(request: Request) -> dict[str, Any]:
    user = current_user(request)
    return {
        "user": s.UserSerializer(user).data,
        "sudo_until": _ts(session.sudo_until(request._request)),
        "must_enroll_2fa": bool(get_setting("security.enforce_2fa")) and not user.totp_enabled,
    }


class SessionAdminView(APIView):
    permission_classes = [IsAuthenticated, IsPanelAdmin, SessionOnly]


class SudoAdminView(APIView):
    permission_classes = [IsAuthenticated, IsPanelAdmin, SessionOnly, RequireSudo]


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie; the SPA calls it once at startup."""

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(responses={204: None}, auth=[])
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginView(CsrfProtectedMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(request=s.LoginSerializer, responses=s.LoginResultSerializer, auth=[])
    def post(self, request: Request) -> Response:
        data = s.LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        outcome = login.login_with_password(
            request._request, data.validated_data["username"], data.validated_data["password"]
        )
        body: dict[str, Any] = {"status": outcome.status}
        if outcome.user is not None:
            body["user"] = s.UserSerializer(outcome.user).data
        return Response(body)


class SecondFactorView(CsrfProtectedMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(request=s.SecondFactorSerializer, responses=s.LoginResultSerializer, auth=[])
    def post(self, request: Request) -> Response:
        data = s.SecondFactorSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        outcome = login.login_second_factor(
            request._request,
            code=data.validated_data.get("code", ""),
            recovery_code=data.validated_data.get("recovery_code", ""),
        )
        return Response({"status": outcome.status, "user": s.UserSerializer(outcome.user).data})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        login.logout_user(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(SessionAdminView):
    @extend_schema(responses=s.MeSerializer)
    def get(self, request: Request) -> Response:
        return Response(_me_payload(request))

    @extend_schema(request=s.UserSerializer, responses=s.MeSerializer)
    def patch(self, request: Request) -> Response:
        user = current_user(request)
        before = s.UserSerializer(user).data
        ser = s.UserSerializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        changed = {k: v for k, v in ser.data.items() if before.get(k) != v}
        if changed:
            record(
                "accounts.profile_updated",
                request=request._request,
                resource_type="user",
                resource_id=str(user.pk),
                changes={"before": {k: before[k] for k in changed}, "after": changed},
            )
        return Response(_me_payload(request))


class SudoView(SessionAdminView):
    @extend_schema(request=s.SudoSerializer, responses=s.SudoResultSerializer)
    def post(self, request: Request) -> Response:
        data = s.SudoSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = current_user(request)
        until = login.confirm_sudo(
            request._request,
            user,
            password=data.validated_data["password"],
            code=data.validated_data.get("code", ""),
        )
        return Response({"sudo_until": _ts(until)})


class PasswordChangeView(SessionAdminView):
    @extend_schema(request=s.PasswordChangeSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        ser = s.PasswordChangeSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = current_user(request)
        user.set_password(ser.validated_data["new_password"])
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password", "password_changed_at"])
        update_session_auth_hash(request._request, user)
        record("accounts.password_changed", request=request._request, resource_id=str(user.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TotpSetupView(SudoAdminView):
    """Start enrollment: a new secret is kept in the session until confirmed."""

    @extend_schema(request=None, responses=s.TotpSetupSerializer)
    def post(self, request: Request) -> Response:
        user = current_user(request)
        secret = totp.new_secret()
        request.session[session.PENDING_TOTP_SECRET_KEY] = secret
        uri, qr = totp.provisioning(user, secret)
        return Response({"secret": secret, "otpauth_uri": uri, "qr_svg": qr})


class TotpEnableView(SudoAdminView):
    @extend_schema(request=s.TotpCodeSerializer, responses=s.RecoveryCodesSerializer)
    def post(self, request: Request) -> Response:
        data = s.TotpCodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        secret = request.session.get(session.PENDING_TOTP_SECRET_KEY)
        if not secret or totp.check_code(secret, data.validated_data["code"]) is None:
            from apps.accounts.errors import InvalidOtp

            raise InvalidOtp()
        user = current_user(request)
        codes = totp.enable(user, secret)
        request.session.pop(session.PENDING_TOTP_SECRET_KEY, None)
        record("accounts.2fa_enabled", request=request._request, resource_id=str(user.pk))
        return Response({"recovery_codes": codes})


class TotpDisableView(SudoAdminView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        if get_setting("security.enforce_2fa"):
            raise TwoFactorEnforced()
        user = current_user(request)
        totp.disable(user)
        record("accounts.2fa_disabled", request=request._request, resource_id=str(user.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecoveryCodesView(SudoAdminView):
    @extend_schema(request=None, responses=s.RecoveryCodesSerializer)
    def post(self, request: Request) -> Response:
        user = current_user(request)
        if not user.totp_enabled:
            raise TwoFactorEnforced(
                _("Enable two-factor authentication first."), code="auth.2fa_not_enabled"
            )
        codes = totp.generate_recovery_codes(user)
        record("accounts.recovery_codes_regenerated", request=request._request)
        return Response({"recovery_codes": codes})


class ApiKeyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[ApiKey],
):
    serializer_class = s.ApiKeySerializer
    permission_classes = [IsAuthenticated, IsPanelAdmin, SessionOnly]
    search_fields = ["name", "prefix"]
    ordering_fields = ["created_at", "name", "last_used_at"]
    filterset_fields: list[str] = []

    def get_queryset(self) -> QuerySet[ApiKey]:
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return ApiKey.objects.none()
        return ApiKey.objects.filter(user=current_user(self.request))

    def get_permissions(self) -> list[Any]:
        perms: list[Any] = list(super().get_permissions())
        if self.action in {"create", "destroy"}:
            perms.append(RequireSudo())
        return perms

    @extend_schema(responses={201: s.ApiKeyCreatedSerializer})
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        ser = s.ApiKeySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = current_user(request)
        key, raw = api_keys.create_key(
            user,
            name=ser.validated_data["name"],
            scopes=ser.validated_data["scopes"],
            ip_allowlist=ser.validated_data.get("ip_allowlist", []),
            expires_at=ser.validated_data.get("expires_at"),
        )
        record(
            "accounts.api_key_created",
            request=request._request,
            resource_type="api_key",
            resource_id=str(key.pk),
            details={"name": key.name, "scopes": key.scopes},
        )
        body = dict(s.ApiKeySerializer(key).data)
        body["key"] = raw
        return Response(body, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: OpenApiResponse(description="Revoked")})
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        key = self.get_object()
        api_keys.revoke(key)
        record(
            "accounts.api_key_revoked",
            request=request._request,
            resource_type="api_key",
            resource_id=str(key.pk),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
