"""Development settings: state in ``<repo>/var/``, agent over TCP (``easydeploy_agent --dev``).

Redis is optional: without ``ED_REDIS_URL`` the cache and channel layer are in-process and Celery
tasks run eagerly inside the API process (enough for UI work on Windows without WSL).
"""

import os
import secrets

from easydeploy.log_config import configure_logging
from easydeploy.settings.base import *

DEBUG = True
VAR_DIR = BASE_DIR.parent / "var"
VAR_DIR.mkdir(exist_ok=True)


def _dev_secret(name: str, factory: object) -> str:
    path = VAR_DIR / name
    if not path.exists():
        path.write_text(factory(), encoding="utf-8")  # type: ignore[operator]
    return path.read_text(encoding="utf-8").strip()


def _fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


SECRET_KEY = _dev_secret("django.secret", lambda: secrets.token_urlsafe(50))
FERNET_KEYS = [_dev_secret("fernet.key", _fernet_key)]

DATABASES["default"]["NAME"] = VAR_DIR / "panel.db"
DATABASES["monitor"]["NAME"] = VAR_DIR / "monitor.db"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

EASYDEPLOY = {
    **EASYDEPLOY,
    "AGENT_URL": CFG.agent_url or "http://127.0.0.1:7801",
    "TASK_LOG_DIR": VAR_DIR / "logs" / "tasks",
    "UPLOAD_DIR": VAR_DIR / "tmp" / "uploads",
    "FRONTEND_DIR": BASE_DIR.parent / "frontend" / "dist",
    "DATA_DIR": VAR_DIR,
    # Shared with `python -m easydeploy_agent --dev` (run from the repo root).
    "AGENT_TOKEN": CFG.agent_token or _dev_secret("agent.token", lambda: secrets.token_urlsafe(48)),
}

if os.environ.get("ED_REDIS_URL"):
    globals().update(redis_backed_settings())
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CELERY_BROKER_URL = "memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False

configure_logging(LOG_LEVEL, json_output=False)
