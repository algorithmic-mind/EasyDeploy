"""``manage.py ed_reset_password [--username U] [--password-stdin]`` (``edctl reset-password``)."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.conf import settings
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
from apps.accounts.services.lockout import reset_all_lockouts
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
        reset_all_lockouts()
        # Single-admin panel: end every session. Going through the session engine also clears
        # the cached copies (SESSION_ENGINE = cached_db in production).
        store = import_module(settings.SESSION_ENGINE).SessionStore
        for key in Session.objects.values_list("session_key", flat=True):
            store(session_key=key).delete()
        record("accounts.password_reset", actor_label="edctl", resource_id=str(user.pk))
        self.stdout.write(password if not opts["password_stdin"] else "updated")
