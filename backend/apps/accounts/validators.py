"""Password policy beyond length: common/breached patterns (§9.1)."""

from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Small built-in denylist of base words seen in breach corpora; matched case-insensitively
# after stripping digits/symbols, so "Password123!" and "p@ssw0rd2026" are both rejected.
DENYLIST = frozenset(
    {
        "password",
        "passw0rd",
        "p@ssword",
        "p@ssw0rd",
        "qwerty",
        "qwertyuiop",
        "asdfgh",
        "letmein",
        "welcome",
        "admin",
        "administrator",
        "root",
        "toor",
        "changeme",
        "default",
        "iloveyou",
        "monkey",
        "dragon",
        "football",
        "baseball",
        "master",
        "sunshine",
        "princess",
        "trustno",
        "abc",
        "abcdef",
        "secret",
        "server",
        "ubuntu",
        "easydeploy",
        "panel",
        "login",
    }
)
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_SEQUENCES = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm")


MAX_EXTRA_LETTERS = 3


def _cores(password: str) -> set[str]:
    """Letters-only forms of the password, with and without leetspeak substitution."""
    lowered = password.lower()
    return {re.sub(r"[^a-z]", "", lowered), re.sub(r"[^a-z]", "", lowered.translate(_LEET))}


def _is_common(core: str) -> bool:
    if core in DENYLIST:
        return True
    # A denylisted word decorated with a few letters/digits/symbols ("Password1234!", "admin2026x").
    return any(
        len(word) >= 5
        and (core.startswith(word) or core.endswith(word))
        and len(core) - len(word) <= MAX_EXTRA_LETTERS
        for word in DENYLIST
    )


class DenylistPasswordValidator:
    def validate(self, password: str, user: Any = None) -> None:
        if password.lower() in DENYLIST or any(_is_common(c) for c in _cores(password)):
            raise ValidationError(_("This password is too common."), code="password_common")
        if len(set(password)) <= 3:
            raise ValidationError(
                _("This password repeats too few characters."), code="password_repetitive"
            )
        lowered = password.lower()
        for seq in _SEQUENCES:
            if lowered in seq or lowered in seq[::-1]:
                raise ValidationError(
                    _("This password is a keyboard or alphabet sequence."),
                    code="password_sequence",
                )

    def get_help_text(self) -> str:
        return _("Your password cannot be a common password, a sequence or a repetition.")
