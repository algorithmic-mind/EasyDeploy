"""Shared helpers for the account management commands used by the installer and ``edctl``."""

from __future__ import annotations

import secrets
import string
import sys

from django.core.management.base import CommandError

from apps.accounts.models import User

_ALPHABET = string.ascii_letters + string.digits


def generate_password(length: int = 20) -> str:
    while True:
        value = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if (
            any(c.islower() for c in value)
            and any(c.isupper() for c in value)
            and any(c.isdigit() for c in value)
        ):
            return value


def read_password_stdin() -> str:
    value = sys.stdin.readline().rstrip("\r\n")
    if not value:
        raise CommandError("empty password on stdin")
    return value


def find_admin(username: str | None) -> User:
    qs = User.objects.filter(role=User.Role.ADMIN)
    user = qs.filter(username=username).first() if username else qs.order_by("date_joined").first()
    if user is None:
        raise CommandError("admin user not found")
    return user
