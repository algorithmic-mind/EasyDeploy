"""Typed access to the ``EASYDEPLOY`` settings dict."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from django.conf import settings


def _cfg() -> dict[str, Any]:
    return cast(dict[str, Any], settings.EASYDEPLOY)


def ed(name: str, default: Any = None) -> Any:
    return _cfg().get(name, default)


def ed_path(name: str) -> Path:
    return Path(_cfg()[name])


def ed_str(name: str) -> str | None:
    value = _cfg().get(name)
    return None if value is None else str(value)


def ed_float(name: str, default: float) -> float:
    return float(_cfg().get(name, default))
