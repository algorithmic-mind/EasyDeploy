"""Identifiers: systemd units, site IDs, Docker resource names, Linux usernames."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_UNIT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9:_.@\-]{0,240}"
    r"\.(service|socket|timer|target|mount|path|slice|scope)$"
)


def validate_unit_name(value: str) -> str:
    """systemd unit name; ``.service`` is appended when no suffix is given."""
    name = value.strip()
    if "." not in name.rsplit("@", 1)[-1] or not name.rsplit(".", 1)[-1].isalpha():
        name = f"{name}.service"
    if not _UNIT.match(name) or ".." in name or "/" in name:
        raise ValueError("invalid systemd unit name")
    return name


UnitName = Annotated[str, AfterValidator(validate_unit_name)]
SiteId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")]
DockerName = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")]
LinuxUser = Annotated[str, StringConstraints(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")]
