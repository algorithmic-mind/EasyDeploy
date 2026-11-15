"""Write audit and login records. Call ``record`` for every mutation (§9)."""

from __future__ import annotations

from typing import Any

import structlog
from django.http import HttpRequest

from apps.audit.models import AuditLog, LoginLog
from apps.core.net import client_ip
from apps.core.redaction import redact_mapping
from apps.core.request_context import current_request_id

log = structlog.get_logger(__name__)


def _ip_or_none(ip: str) -> str | None:
    return None if ip in ("", "unknown") else ip


def record(
    action: str,
    *,
    request: HttpRequest | None = None,
    actor: Any = None,
    actor_label: str = "",
    resource_type: str = "",
    resource_id: str = "",
    result: str = AuditLog.Result.SUCCESS,
    changes: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Write one audit entry; ``ip`` is for callers without an HTTP request (WebSockets)."""
    user = actor
    if user is None and request is not None:
        candidate = getattr(request, "user", None)
        if candidate is not None and candidate.is_authenticated:
            user = candidate
    entry = AuditLog.objects.create(
        actor=user,
        actor_label=actor_label or (user.get_username() if user is not None else "system"),
        action=action,
        module=action.split(".", 1)[0],
        resource_type=resource_type,
        resource_id=str(resource_id),
        ip=_ip_or_none(client_ip(request)) if request is not None else ip,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300] if request is not None else "",
        request_id=current_request_id() or "",
        result=result,
        changes=redact_mapping(changes or {}),
        details=redact_mapping(details or {}),
    )
    log.info("audit", action=action, actor=entry.actor_label, resource=resource_id, result=result)
    return entry


def record_login(
    request: HttpRequest, username: str, *, success: bool, reason: str, user: Any = None
) -> LoginLog:
    return LoginLog.objects.create(
        username=username[:150],
        user=user,
        ip=_ip_or_none(client_ip(request)),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        success=success,
        reason=reason,
    )
