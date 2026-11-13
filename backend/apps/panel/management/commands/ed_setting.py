"""``manage.py ed_setting get|set|reset|list <key> [json-value]`` — used by ``edctl``."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.errors import ValidationFailed
from apps.panel.services import get_setting, set_setting
from apps.panel.settings_registry import REGISTRY, UnknownSetting


class Command(BaseCommand):
    help = "Read or change a runtime setting."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", choices=["get", "set", "reset", "list"])
        parser.add_argument("key", nargs="?")
        parser.add_argument("value", nargs="?", help="JSON value (plain strings are accepted)")

    def handle(self, *args: Any, **opts: Any) -> None:
        action, key = opts["action"], opts["key"]
        if action == "list":
            for name in sorted(REGISTRY):
                shown = "***" if REGISTRY[name].sensitive else get_setting(name)
                self.stdout.write(f"{name} = {json.dumps(shown, ensure_ascii=False)}")
            return
        if not key:
            raise CommandError("key is required")
        try:
            if action == "get":
                self.stdout.write(json.dumps(get_setting(key), ensure_ascii=False))
                return
            if action == "reset":
                value = REGISTRY[key].default
            else:
                raw = opts["value"]
                if raw is None:
                    raise CommandError("value is required")
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    value = raw
            result = set_setting(key, value, actor_label="edctl")
        except (UnknownSetting, KeyError) as exc:
            raise CommandError(f"unknown setting: {key}") from exc
        except ValidationFailed as exc:
            raise CommandError(json.dumps(exc.details, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False))
