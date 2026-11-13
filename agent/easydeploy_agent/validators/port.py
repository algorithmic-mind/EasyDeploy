"""Port validation."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field

Port = Annotated[int, Field(ge=1, le=65535)]

# Ports the panel must never hand to apps/projects (SSH, web, panel internals by convention).
RESERVED_PORTS = frozenset({22, 25, 53, 80, 443})


def validate_app_port(value: int) -> int:
    """Ports assigned to apps/projects: unprivileged and not reserved."""
    if value < 1024:
        raise ValueError("privileged ports (< 1024) cannot be assigned to apps")
    if value in RESERVED_PORTS:
        raise ValueError(f"port {value} is reserved")
    return value


AppPort = Annotated[int, Field(ge=1024, le=65535), AfterValidator(validate_app_port)]
