"""Test settings: in-memory everything, FakeAgent, fast password hashing."""

import tempfile
from pathlib import Path

from easydeploy.log_config import configure_logging
from easydeploy.settings.base import *

SECRET_KEY = "test-secret-key-not-for-production-0123456789abcdefghijklmnop"  # nosec B105
FERNET_KEYS = ["n4bQgYhMfWWaL-qkxRhLJ-6Ewdl-ZuLz0Bb3s7Jz9Ks="]

_TMP = Path(tempfile.mkdtemp(prefix="easydeploy-test-"))
DATABASES["default"]["NAME"] = _TMP / "panel.db"
DATABASES["monitor"]["NAME"] = _TMP / "monitor.db"
for _db in DATABASES.values():
    _db["TEST"] = {"NAME": None}  # in-memory test databases

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EASYDEPLOY = {
    **EASYDEPLOY,
    "AGENT_BACKEND": "apps.core.agent_client.FakeAgent",
    "TASK_LOG_DIR": _TMP / "logs" / "tasks",
    "FRONTEND_DIR": _TMP / "frontend",
    "DATA_DIR": _TMP,
    "AGENT_TOKEN": "test-agent-token-" + "x" * 32,
}

configure_logging("warning", json_output=False)
