"""Route metrics models to ``monitor.db`` so frequent writes do not contend with panel data."""

from __future__ import annotations

from typing import Any

MONITOR_APPS = frozenset({"monitoring"})


class MonitorRouter:
    def db_for_read(self, model: Any, **hints: Any) -> str | None:
        return "monitor" if model._meta.app_label in MONITOR_APPS else "default"

    def db_for_write(self, model: Any, **hints: Any) -> str | None:
        return "monitor" if model._meta.app_label in MONITOR_APPS else "default"

    def allow_relation(self, obj1: Any, obj2: Any, **hints: Any) -> bool | None:
        in_monitor = {obj1._meta.app_label in MONITOR_APPS, obj2._meta.app_label in MONITOR_APPS}
        return len(in_monitor) == 1

    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool | None:
        if app_label in MONITOR_APPS:
            return db == "monitor"
        return db == "default"
