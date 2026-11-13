"""``manage.py ed_reset_password [--username U] [--password-stdin]`` (``edctl reset-password``)."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from apps.accounts.management.commands._admin import (
    find_admin,
    generate_password,
    read_password_stdin,
)
from apps.accounts.services.lockout import unlock_username
from apps.audit.services import record


class Command(BaseCommand):
    help = "Reset the administrator password, unlock the account and end all sessions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username")
        parser.add_argument("--password-stdin", action="store_true")

    def handle(self, *args: Any, **opts: Any) -> None:
        user = find_admin(opts["username"])
        password = read_password_stdin() if opts["password_stdin"] else generate_password()
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user.set_password(password)
        user.is_active = True
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password", "is_active", "password_changed_at"])
        unlock_username(user.get_username())
        Session.objects.all().delete()  # single-admin panel: invalidate every session
        record("accounts.password_reset", actor_label="edctl", resource_id=str(user.pk))
        self.stdout.write(password if not opts["password_stdin"] else "updated")
