"""``manage.py ed_user_info`` — JSON with username and entrance (never the password)."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.management.commands._admin import find_admin
from apps.panel.services import get_setting


class Command(BaseCommand):
    help = "Print the administrator username, 2FA state and panel access settings as JSON."

    def handle(self, *args: Any, **opts: Any) -> None:
        user = find_admin(None)
        self.stdout.write(
            json.dumps(
                {
                    "username": user.get_username(),
                    "totp_enabled": user.totp_enabled,
                    "entrance": get_setting("security.entrance"),
                    "bind_domain": get_setting("security.bind_domain"),
                    "ip_allowlist": get_setting("security.ip_allowlist"),
                }
            )
        )
