"""Production settings (systemd units set DJANGO_SETTINGS_MODULE=easydeploy.settings.prod)."""

from easydeploy.log_config import configure_logging
from easydeploy.settings.base import *

SECRET_KEY = CFG.read_secret("django.secret")
FERNET_KEYS = [k for k in CFG.read_secret("fernet.keys").splitlines() if k.strip()]

globals().update(redis_backed_settings())

configure_logging(LOG_LEVEL, json_output=True)
