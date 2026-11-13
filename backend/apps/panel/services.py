"""Read and write runtime settings with caching and auditing."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.http import HttpRequest

from apps.core.errors import ValidationFailed
from apps.panel.models import Setting
from apps.panel.settings_registry import PydanticValidationError, get_def

CACHE_PREFIX = "setting:"
CACHE_TTL = 60


def get_setting(key: str) -> Any:
    definition = get_def(key)
    cached = cache.get(CACHE_PREFIX + key)
    if cached is not None:
        return cached["v"]
    row = Setting.objects.filter(key=key).first()
    value = definition.default if row is None else row.value
    cache.set(CACHE_PREFIX + key, {"v": value}, CACHE_TTL)
    return value


def set_setting(
    key: str,
    value: Any,
    *,
    request: HttpRequest | None = None,
    actor_label: str = "",
) -> Any:
    """Validate, persist and audit a setting change. Returns the normalized value."""
    from apps.audit.services import record

    definition = get_def(key)
    try:
        normalized = definition.validate(value)
    except PydanticValidationError as exc:
        raise ValidationFailed(
            details={key: [e["msg"] for e in exc.errors(include_url=False)]}
        ) from None
    before = get_setting(key)
    Setting.objects.update_or_create(key=key, defaults={"value": normalized})
    cache.delete(CACHE_PREFIX + key)
    if before != normalized:
        shown_before, shown_after = ("***", "***") if definition.sensitive else (before, normalized)
        record(
            "panel.setting_changed",
            request=request,
            actor_label=actor_label,
            resource_type="setting",
            resource_id=key,
            changes={"before": shown_before, "after": shown_after},
        )
    return normalized
