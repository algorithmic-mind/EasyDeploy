from __future__ import annotations

import zoneinfo
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import ApiKey, User
from apps.accounts.services.api_keys import SCOPE_RE
from apps.panel.settings_registry import _cidrs


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "language",
            "timezone",
            "calendar",
            "theme",
            "totp_enabled",
            "last_login",
        ]
        read_only_fields = ["id", "username", "email", "role", "totp_enabled", "last_login"]

    def validate_timezone(self, value: str) -> str:
        if value not in zoneinfo.available_timezones() and value != "UTC":
            raise serializers.ValidationError(_("Unknown time zone."))
        return value


class MeSerializer(serializers.Serializer[Any]):
    user = UserSerializer()
    sudo_until = serializers.DateTimeField(allow_null=True)
    must_enroll_2fa = serializers.BooleanField()


class LoginSerializer(serializers.Serializer[Any]):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class LoginResultSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=["ok", "2fa_required"])
    user = UserSerializer(required=False)


class SecondFactorSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    recovery_code = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("code") and not attrs.get("recovery_code"):
            raise serializers.ValidationError(_("Enter a verification code or a recovery code."))
        return attrs


class SudoSerializer(serializers.Serializer[Any]):
    password = serializers.CharField(max_length=256, trim_whitespace=False)
    code = serializers.CharField(max_length=10, required=False, allow_blank=True)


class SudoResultSerializer(serializers.Serializer[Any]):
    sudo_until = serializers.DateTimeField()


class PasswordChangeSerializer(serializers.Serializer[Any]):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False)
    new_password = serializers.CharField(max_length=256, trim_whitespace=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": [_("The current password is incorrect.")]}
            )
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        return attrs


class TotpSetupSerializer(serializers.Serializer[Any]):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()
    qr_svg = serializers.CharField(help_text="SVG data URI of the QR code")


class TotpCodeSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=10)


class RecoveryCodesSerializer(serializers.Serializer[Any]):
    recovery_codes = serializers.ListField(child=serializers.CharField())


class ApiKeySerializer(serializers.ModelSerializer[ApiKey]):
    class Meta:
        model = ApiKey
        fields = [
            "id",
            "name",
            "prefix",
            "scopes",
            "ip_allowlist",
            "expires_at",
            "last_used_at",
            "last_used_ip",
            "revoked_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "prefix",
            "last_used_at",
            "last_used_ip",
            "revoked_at",
            "created_at",
        ]

    def validate_scopes(self, value: list[str]) -> list[str]:
        if not value:
            raise serializers.ValidationError(_("Select at least one scope."))
        bad = [s for s in value if not isinstance(s, str) or not SCOPE_RE.match(s)]
        if bad:
            raise serializers.ValidationError(_("Invalid scopes: %(scopes)s") % {"scopes": bad})
        return value

    def validate_ip_allowlist(self, value: list[str]) -> list[str]:
        try:
            return _cidrs(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class ApiKeyCreatedSerializer(ApiKeySerializer):
    key = serializers.CharField(read_only=True, help_text="Shown only once.")

    class Meta(ApiKeySerializer.Meta):
        fields = [*ApiKeySerializer.Meta.fields, "key"]
