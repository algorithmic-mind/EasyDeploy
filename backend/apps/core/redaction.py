"""Secret masking for logs and task logs (§10.2)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "***"
SECRET_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "passphrase",
    "private_key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "otp",
    "recovery_code",
)
_PATTERNS = [
    # key=value / key: value pairs whose key looks secret
    re.compile(
        r"(?i)\b([\w.-]*(?:password|passwd|secret|token|api[_-]?key|passphrase)[\w.-]*)"
        r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
    ),
    # URLs with credentials: scheme://user:pass@host
    re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^:/\s@]*:)([^@\s]+)(@)"),
    # Bearer tokens
    re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9._~+/=-]{8,})"),
    # EasyDeploy API keys
    re.compile(r"\b(ed_)([A-Za-z0-9]{6,}_[A-Za-z0-9_-]{16,})"),
]


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def redact_text(text: str, extra_secrets: list[str] | None = None) -> str:
    """Mask secrets in free text. ``extra_secrets`` are literal values that must never appear."""
    for secret in extra_secrets or []:
        if secret and len(secret) >= 4:
            text = text.replace(secret, REDACTED)
    text = _PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    text = _PATTERNS[1].sub(lambda m: f"{m.group(1)}{REDACTED}{m.group(3)}", text)
    text = _PATTERNS[2].sub(lambda m: f"{m.group(1)}{REDACTED}", text)
    return _PATTERNS[3].sub(lambda m: f"{m.group(1)}{REDACTED}", text)


def redact_mapping(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: (REDACTED if isinstance(k, str) and is_secret_key(k) and v else redact_mapping(v))
            for k, v in data.items()
        }
    if isinstance(data, list | tuple):
        return [redact_mapping(v) for v in data]
    return data
