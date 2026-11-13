"""Domain name validation (IDNA 2008 → punycode, RFC 1035 label rules)."""

from __future__ import annotations

import re
from typing import Annotated

import idna
from pydantic import AfterValidator

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def validate_domain(value: str, *, allow_wildcard: bool = False) -> str:
    """Return the ASCII (punycode) lowercase form of ``value`` or raise ``ValueError``."""
    if not isinstance(value, str):
        raise ValueError("domain must be a string")
    name = value.strip().rstrip(".").lower()
    if not name or len(name) > 253:
        raise ValueError("domain length must be 1-253 characters")
    wildcard = name.startswith("*.")
    if wildcard:
        if not allow_wildcard:
            raise ValueError("wildcard domains are not allowed here")
        name = name[2:]
    try:
        ascii_name = idna.encode(name, uts46=True).decode("ascii")
    except idna.IDNAError as exc:
        raise ValueError(f"invalid internationalized domain: {exc}") from None
    labels = ascii_name.split(".")
    if len(labels) < 2:
        raise ValueError("domain must contain at least two labels")
    for label in labels:
        if not _LABEL.match(label):
            raise ValueError(f"invalid domain label: {label!r}")
    if labels[-1].isdigit():
        raise ValueError("top-level label must not be numeric")
    result = ("*." if wildcard else "") + ascii_name
    if len(result) > 253:
        raise ValueError("domain is too long")
    return result


def _wildcard(value: str) -> str:
    return validate_domain(value, allow_wildcard=True)


DomainName = Annotated[str, AfterValidator(validate_domain)]
WildcardDomainName = Annotated[str, AfterValidator(_wildcard)]
