"""TOTP two-factor authentication with replay protection and one-time recovery codes."""

from __future__ import annotations

import hashlib
import hmac
import secrets

import pyotp
import segno
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RecoveryCode, User
from apps.panel.services import get_setting

RECOVERY_CODE_COUNT = 10
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no ambiguous characters


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning(user: User, secret: str) -> tuple[str, str]:
    """Return the ``otpauth://`` URI and an SVG data URI of its QR code."""
    issuer = str(get_setting("panel.name"))
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.get_username(), issuer_name=issuer)
    qr = segno.make(uri, error="m").svg_data_uri(scale=5, border=2)
    return uri, qr


def _normalize(code: str) -> str:
    return "".join(ch for ch in code if ch.isdigit())


def check_code(secret: str, code: str, *, after_counter: int = 0) -> int | None:
    """Return the matched time counter (±1 step) if valid and newer than ``after_counter``."""
    code = _normalize(code)
    if len(code) != 6 or not secret:
        return None
    totp = pyotp.TOTP(secret)
    current = totp.timecode(timezone.now())
    for counter in (current - 1, current, current + 1):
        if counter <= after_counter:
            continue
        if hmac.compare_digest(totp.generate_otp(counter), code):
            return counter
    return None


def verify_user_code(user: User, code: str) -> bool:
    """Verify a login/sudo code and consume its time step so it cannot be replayed."""
    if not user.totp_enabled:
        return False
    counter = check_code(user.totp_secret, code, after_counter=user.totp_last_counter)
    if counter is None:
        return False
    updated = User.objects.filter(pk=user.pk, totp_last_counter__lt=counter).update(
        totp_last_counter=counter
    )
    user.totp_last_counter = counter
    return updated == 1


def _hash(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").strip().lower().encode()).hexdigest()


@transaction.atomic
def generate_recovery_codes(user: User) -> list[str]:
    user.recovery_codes.all().delete()
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    RecoveryCode.objects.bulk_create(RecoveryCode(user=user, code_hash=_hash(c)) for c in codes)
    return codes


def use_recovery_code(user: User, code: str) -> bool:
    updated = RecoveryCode.objects.filter(
        user=user, code_hash=_hash(code), used_at__isnull=True
    ).update(used_at=timezone.now())
    return updated == 1


@transaction.atomic
def enable(user: User, secret: str) -> list[str]:
    user.totp_secret = secret
    user.totp_enabled = True
    user.totp_last_counter = 0
    user.save(update_fields=["totp_secret", "totp_enabled", "totp_last_counter"])
    return generate_recovery_codes(user)


@transaction.atomic
def disable(user: User) -> None:
    user.totp_secret = ""  # nosec B105 - clearing the secret
    user.totp_enabled = False
    user.totp_last_counter = 0
    user.save(update_fields=["totp_secret", "totp_enabled", "totp_last_counter"])
    user.recovery_codes.all().delete()
