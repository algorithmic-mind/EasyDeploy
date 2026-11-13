"""Encrypted model fields (Fernet / MultiFernet for key rotation, §5.5)."""

from __future__ import annotations

import functools
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models

PREFIX = "fernet:"


@functools.cache
def _fernet() -> MultiFernet:
    keys = settings.FERNET_KEYS
    if not keys:
        raise RuntimeError("FERNET_KEYS is empty")
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def encrypt(value: str) -> str:
    return PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str) -> str:
    if not value.startswith(PREFIX):
        raise ValueError("value is not encrypted")
    try:
        return _fernet().decrypt(value[len(PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("cannot decrypt value (wrong key?)") from exc


def rotate(value: str) -> str:
    """Re-encrypt with the newest key (first in FERNET_KEYS)."""
    return PREFIX + _fernet().rotate(value[len(PREFIX) :].encode("ascii")).decode("ascii")


class EncryptedTextField(models.TextField):
    """Stores text encrypted at rest. Never expose it through list/detail serializers."""

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return encrypt(str(value))

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        if value is None or value == "":
            return value
        return decrypt(value)

    def to_python(self, value: Any) -> Any:
        if isinstance(value, str) and value.startswith(PREFIX):
            return decrypt(value)
        return value
