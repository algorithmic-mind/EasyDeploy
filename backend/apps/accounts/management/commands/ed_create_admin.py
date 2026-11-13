"""``manage.py ed_create_admin --username admin [--password-stdin]`` (installer step 9).

Prints the generated password once when none is supplied; it is never stored in plaintext.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from apps.accounts.management.commands._admin import generate_password, read_password_stdin
from apps.accounts.models import User
from apps.audit.services import record


class Command(BaseCommand):
    help = "Create the panel administrator."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username", default="admin")
        parser.add_argument("--password-stdin", action="store_true")
        parser.add_argument("--language", choices=["en", "fa"], default="en")
        parser.add_argument("--if-missing", action="store_true", help="no-op if an admin exists")

    def handle(self, *args: Any, **opts: Any) -> None:
        if User.objects.filter(role=User.Role.ADMIN).exists():
            if opts["if_missing"]:
                self.stdout.write("admin exists")
                return
            raise CommandError("an admin user already exists; use ed_reset_password")
        username = opts["username"]
        password = read_password_stdin() if opts["password_stdin"] else generate_password()
        user = User(username=username, role=User.Role.ADMIN, language=opts["language"])
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user.set_password(password)
        user.password_changed_at = timezone.now()
        user.save()
        record("accounts.admin_created", actor_label="installer", resource_id=str(user.pk))
        self.stdout.write(password if not opts["password_stdin"] else "created")
