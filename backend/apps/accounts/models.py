"""Custom user (present from the first migration), recovery codes and API keys (§9.1)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin"
        OPERATOR = "operator"  # LATER (RBAC)
        VIEWER = "viewer"  # LATER (RBAC)

    class Language(models.TextChoices):
        EN = "en"
        FA = "fa"

    class Calendar(models.TextChoices):
        GREGORIAN = "gregorian"
        JALALI = "jalali"

    class Theme(models.TextChoices):
        LIGHT = "light"
        DARK = "dark"
        SYSTEM = "system"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ADMIN)
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.EN)
    timezone = models.CharField(max_length=64, default="UTC")
    calendar = models.CharField(max_length=10, choices=Calendar.choices, default=Calendar.GREGORIAN)
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.SYSTEM)
    totp_secret = EncryptedTextField(blank=True, default="")
    totp_enabled = models.BooleanField(default=False)
    totp_last_counter = models.BigIntegerField(default=0)  # replay protection
    password_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_user"


class RecoveryCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recovery_codes"
    )
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "code_hash"], name="uniq_recovery_code")
        ]

    def __str__(self) -> str:
        return f"recovery code of {self.user_id} ({'used' if self.used_at else 'unused'})"


class ApiKey(TimeStampedModel):
    """Automation key: ``ed_<prefix>_<secret>``; only the SHA-256 hash is stored."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, unique=True)
    key_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)  # e.g. ["*:read", "containers:write"]
    ip_allowlist = models.JSONField(default=list, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} (ed_{self.prefix}_…)"

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()
