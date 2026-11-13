"""Minimal en/fa message catalog for edctl (language from --lang or the system locale)."""

from __future__ import annotations

import os

MESSAGES: dict[str, dict[str, str]] = {
    "need_root": {
        "en": "edctl must run as root (try: sudo edctl …)",
        "fa": "edctl باید با دسترسی root اجرا شود (sudo edctl …)",
    },
    "status_title": {"en": "EasyDeploy services", "fa": "سرویس‌های ایزی‌دیپلوی"},
    "panel_url": {"en": "Panel URL", "fa": "آدرس پنل"},
    "username": {"en": "Username", "fa": "نام کاربری"},
    "password_hint": {
        "en": "The password is not stored. Reset it with: edctl reset-password",
        "fa": "رمز عبور ذخیره نمی‌شود. برای تغییر: edctl reset-password",
    },
    "new_password": {
        "en": "New password (shown once)",
        "fa": "رمز عبور جدید (فقط یک بار نمایش داده می‌شود)",
    },
    "done": {"en": "Done.", "fa": "انجام شد."},
    "failed": {"en": "Failed", "fa": "ناموفق"},
    "twofa_reset": {
        "en": "Two-factor authentication disabled.",
        "fa": "احراز هویت دومرحله‌ای غیرفعال شد.",
    },
    "entrance_set": {"en": "New security entrance", "fa": "مسیر ورود امن جدید"},
    "port_invalid": {
        "en": "Port must be between 1024 and 65535 and not 80/443.",
        "fa": "پورت باید بین 1024 تا 65535 و غیر از 80/443 باشد.",
    },
    "port_in_use": {
        "en": "Port {port} is already in use.",
        "fa": "پورت {port} در حال استفاده است.",
    },
    "nginx_invalid": {
        "en": "Nginx rejected the new configuration; the previous one was restored.",
        "fa": "Nginx پیکربندی جدید را نپذیرفت؛ پیکربندی قبلی بازگردانده شد.",
    },
    "port_changed": {"en": "Panel port changed to {port}.", "fa": "پورت پنل به {port} تغییر کرد."},
    "doctor_title": {"en": "EasyDeploy doctor", "fa": "عیب‌یابی ایزی‌دیپلوی"},
    "doctor_ok": {"en": "All checks passed.", "fa": "همهٔ بررسی‌ها موفق بود."},
    "doctor_problems": {
        "en": "{count} problem(s) found.",
        "fa": "{count} مشکل پیدا شد.",
    },
    "fix": {"en": "fix", "fa": "راه‌حل"},
    "allowlist_reset": {"en": "IP allowlist cleared.", "fa": "فهرست IPهای مجاز پاک شد."},
    "bind_domain_reset": {"en": "Bind domain cleared.", "fa": "دامنهٔ متصل پاک شد."},
}


def detect_language(explicit: str | None) -> str:
    if explicit in ("en", "fa"):
        return explicit
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            return "fa" if value.lower().startswith("fa") else "en"
    return "en"


class Translator:
    def __init__(self, lang: str = "en") -> None:
        self.lang = lang

    def __call__(self, key: str, **params: object) -> str:
        entry = MESSAGES.get(key)
        if entry is None:
            return key
        return entry.get(self.lang, entry["en"]).format(**params)
