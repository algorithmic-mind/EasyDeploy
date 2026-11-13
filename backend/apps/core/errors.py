"""Domain exceptions with stable codes, rendered as the API error envelope (§10.1, §13.1)."""

from __future__ import annotations

from typing import Any

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _


class EasyDeployError(Exception):
    code = "error"
    status_code = 400
    default_message: str | Promise = _("The request could not be completed.")

    def __init__(
        self,
        message: str | Promise | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message if message is not None else self.default_message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(str(self.message))


class NotFound(EasyDeployError):
    code = "not_found"
    status_code = 404
    default_message = _("Not found.")


class Conflict(EasyDeployError):
    code = "conflict"
    status_code = 409
    default_message = _("The resource is in a conflicting state.")


class PermissionDenied(EasyDeployError):
    code = "permission_denied"
    status_code = 403
    default_message = _("You do not have permission to perform this action.")


class ValidationFailed(EasyDeployError):
    code = "validation_error"
    status_code = 400
    default_message = _("Some fields are invalid.")


class ServiceUnavailable(EasyDeployError):
    code = "service_unavailable"
    status_code = 503
    default_message = _("A required service is unavailable.")
