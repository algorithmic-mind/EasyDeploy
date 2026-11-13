"""Append-only audit log of every op invocation (``/var/log/easydeploy/agent-audit.log``)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

SECRET_MARKERS = ("password", "secret", "token", "passphrase", "private_key", "api_key")
REDACTED = "***"


def redact(value: Any) -> Any:
    """Recursively mask values whose key looks secret."""
    if isinstance(value, dict):
        return {
            k: REDACTED if any(m in str(k).lower() for m in SECRET_MARKERS) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class AuditLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.records: list[dict[str, Any]] = []  # kept in memory when no path (dev/tests)

    def write(
        self,
        *,
        op: str,
        params: dict[str, Any],
        ok: bool,
        duration_ms: float,
        request_id: str | None,
        actor: str | None,
        error_code: str | None = None,
    ) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "op": op,
            "ok": ok,
            "error": error_code,
            "duration_ms": round(duration_ms, 1),
            "request_id": request_id,
            "actor": actor,
            "params": redact(params),
        }
        if self.path is None:
            self.records.append(record)
            return
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
