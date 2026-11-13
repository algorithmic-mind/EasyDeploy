from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.core.errors import EasyDeployError


class InvalidCredentials(EasyDeployError):
    code = "auth.invalid_credentials"
    status_code = 400
    default_message = _("Invalid username or password.")


class LoginLocked(EasyDeployError):
    code = "auth.locked"
    status_code = 429
    default_message = _("Too many failed attempts. Try again later.")


class InvalidOtp(EasyDeployError):
    code = "auth.invalid_otp"
    status_code = 400
    default_message = _("The verification code is invalid or expired.")


class TwoFactorNotPending(EasyDeployError):
    code = "auth.2fa_not_pending"
    status_code = 400
    default_message = _("There is no pending two-factor login. Sign in again.")


class SudoRequired(EasyDeployError):
    code = "auth.sudo_required"
    status_code = 403
    default_message = _("Confirm your password to continue with this action.")


class TwoFactorEnforced(EasyDeployError):
    code = "auth.2fa_enforced"
    status_code = 400
    default_message = _("Two-factor authentication is required by the panel settings.")


class ApiKeyForbidden(EasyDeployError):
    code = "auth.api_key_forbidden"
    status_code = 403
    default_message = _("This API key is not allowed to perform this action.")
