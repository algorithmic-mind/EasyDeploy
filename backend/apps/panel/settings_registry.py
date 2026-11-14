"""Typed registry of runtime settings (§5.5). Values are validated with Pydantic TypeAdapters."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

ENTRANCE_RE = re.compile(r"^[A-Za-z0-9]{6,64}$")


def _entrance(value: str) -> str:
    if value and not ENTRANCE_RE.match(value):
        raise ValueError("entrance must be 6-64 letters or digits")
    return value


def _cidrs(values: list[str]) -> list[str]:
    result = []
    for v in values:
        try:
            result.append(str(ipaddress.ip_network(v.strip(), strict=False)))
        except ValueError as exc:
            raise ValueError(f"invalid IP or CIDR: {v}") from exc
    return result


def _bind_domain(value: str) -> str:
    if not value:
        return value
    from easydeploy_agent.validators.domain import validate_domain

    return validate_domain(value)


@dataclass(frozen=True)
class SettingDef:
    key: str
    adapter: TypeAdapter[Any]
    default: Any
    sensitive: bool = False

    def validate(self, value: Any) -> Any:
        return self.adapter.validate_python(value)


REGISTRY: dict[str, SettingDef] = {}


def define(key: str, type_: Any, default: Any, *, sensitive: bool = False) -> None:
    REGISTRY[key] = SettingDef(key, TypeAdapter(type_), default, sensitive)


define("panel.name", Annotated[str, Field(min_length=1, max_length=64)], "EasyDeploy")
define("panel.default_language", Literal["en", "fa"], "en")
define("security.entrance", Annotated[str, AfterValidator(_entrance)], "", sensitive=True)
define("security.entrance_response", Literal["404", "drop"], "404")
define("security.ip_allowlist", Annotated[list[str], AfterValidator(_cidrs)], [])
define("security.bind_domain", Annotated[str, AfterValidator(_bind_domain)], "")
define("security.session_idle_minutes", Annotated[int, Field(ge=5, le=1440)], 120)
define("security.session_absolute_hours", Annotated[int, Field(ge=1, le=720)], 24)
define("security.enforce_2fa", bool, False)
define("security.login_max_failures", Annotated[int, Field(ge=3, le=50)], 5)
define("security.login_lockout_minutes", Annotated[int, Field(ge=1, le=1440)], 15)
define("security.sudo_minutes", Annotated[int, Field(ge=1, le=60)], 10)
define("monitoring.enabled", bool, True)
define("monitoring.retention_days", Annotated[int, Field(ge=1, le=365)], 30)
define("files.max_upload_mb", Annotated[int, Field(ge=1, le=102400)], 10240)


class UnknownSetting(KeyError):
    pass


def get_def(key: str) -> SettingDef:
    try:
        return REGISTRY[key]
    except KeyError:
        raise UnknownSetting(key) from None


__all__ = ["REGISTRY", "PydanticValidationError", "SettingDef", "UnknownSetting", "get_def"]
