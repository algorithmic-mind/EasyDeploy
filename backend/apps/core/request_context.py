"""Per-request context (request ID, actor) shared by logs, audit and the agent client."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_request_id(incoming: str | None = None) -> str:
    """Accept a well-formed incoming ID (e.g., from Nginx), otherwise generate one."""
    if incoming and _VALID_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def current_request_id() -> str | None:
    return request_id_var.get()
