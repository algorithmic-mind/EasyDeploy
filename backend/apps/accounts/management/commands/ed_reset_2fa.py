"""``manage.py ed_reset_2fa [--username U]`` (``edctl reset-2fa``)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.accounts.management.commands._admin import find_admin
from apps.accounts.services import totp
from apps.audit.services import record


class Command(BaseCommand):
    help = "Disable two-factor authentication for the administrator."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username")

    def handle(self, *args: Any, **opts: Any) -> None:
        user = find_admin(opts["username"])
        totp.disable(user)
        record("accounts.2fa_reset", actor_label="edctl", resource_id=str(user.pk))
        self.stdout.write("2fa disabled")
