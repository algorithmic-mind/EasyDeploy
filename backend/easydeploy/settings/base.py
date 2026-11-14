"""Settings shared by every environment. Environment modules: dev, prod, test."""

from __future__ import annotations

from pathlib import Path

from django.utils.translation import gettext_lazy as _

from easydeploy.config import get_config

CFG = get_config()
BASE_DIR = Path(__file__).resolve().parents[2]  # backend/

DEBUG = False
VERSION = CFG.version
ALLOWED_HOSTS = ["*"]  # host checks are done by BindDomainMiddleware (panel is reached by IP)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "channels",
    "django_celery_beat",
    "apps.core",
    "apps.panel",
    "apps.accounts",
    "apps.audit",
    "apps.tasks",
    "apps.monitoring",
    "apps.dashboard",
    "apps.host",
    "apps.files",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.middleware.BindDomainMiddleware",
    "apps.accounts.middleware.IpAllowlistMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.accounts.middleware.EntranceMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.SessionTimeoutMiddleware",
    "apps.accounts.middleware.UserLanguageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "easydeploy.urls"
ASGI_APPLICATION = "easydeploy.asgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# ------------------------------------------------------------------ databases (§5.5, ADR-0007)
SQLITE_OPTIONS = {
    "init_command": (
        "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;PRAGMA busy_timeout=5000;"
        "PRAGMA foreign_keys=ON;"
    ),
    "transaction_mode": "IMMEDIATE",
    "timeout": 5,
}
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": CFG.data_dir / "panel.db",
        "OPTIONS": SQLITE_OPTIONS,
    },
    "monitor": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": CFG.data_dir / "monitor.db",
        "OPTIONS": SQLITE_OPTIONS,
    },
}
DATABASE_ROUTERS = ["easydeploy.db_routers.MonitorRouter"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ auth (§9.1)
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "apps.accounts.validators.DenylistPasswordValidator"},
]

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_NAME = "ed_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 60 * 60 * 24  # absolute upper bound; idle/absolute timeouts are enforced too
CSRF_COOKIE_NAME = "ed_csrftoken"
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send X-CSRFToken
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------------------ i18n (§10.4)
LANGUAGE_CODE = "en"
LANGUAGES = [("en", _("English")), ("fa", _("Persian"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
TIME_ZONE = "UTC"
USE_TZ = True

# ------------------------------------------------------------------ REST framework (§10.1)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.ApiKeyAuthentication",
        "apps.accounts.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "apps.core.permissions.IsPanelAdmin",
        "apps.accounts.permissions.ApiKeyScopePermission",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "DATETIME_FORMAT": "iso-8601",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "EasyDeploy API",
    "DESCRIPTION": "EasyDeploy server control panel API.",
    "VERSION": VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {},
}

# ------------------------------------------------------------------ cache, channels, celery
# Redis-backed CACHES / CHANNEL_LAYERS / CELERY_BROKER_URL are set per environment
# (prod reads the Redis password from the secrets dir; dev/test may run without Redis).


def redis_backed_settings() -> dict[str, object]:
    return {
        "CACHES": {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": CFG.redis_location(1),
                "KEY_PREFIX": "ed",
            }
        },
        "CHANNEL_LAYERS": {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [CFG.redis_location(2)], "capacity": 500, "expiry": 30},
            }
        },
        "CELERY_BROKER_URL": CFG.celery_broker_url(),
    }


CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "deploy.*": {"queue": "deploy"},
    "backup.*": {"queue": "backup"},
    "monitor.*": {"queue": "monitor"},
}
CELERY_TASK_TIME_LIMIT = 3600
CELERY_TASK_SOFT_TIME_LIMIT = 3300
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# System jobs; synced into django-celery-beat's tables by the DatabaseScheduler.
CELERY_BEAT_SCHEDULE = {
    "monitor-collect": {"task": "monitor.collect", "schedule": 60.0},
    "monitor-maintenance": {"task": "monitor.maintenance", "schedule": 6 * 3600.0},
}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = "UTC"

# ------------------------------------------------------------------ EasyDeploy specific
EASYDEPLOY = {
    "AGENT_BACKEND": "apps.core.agent_client.AgentClient",
    "AGENT_SOCKET": str(CFG.agent_socket),
    "AGENT_URL": CFG.agent_url,
    "AGENT_TIMEOUT": 30.0,
    "TASK_LOG_DIR": CFG.log_dir / "tasks",
    "UPLOAD_DIR": CFG.tmp_dir
    / "uploads",  # the agent joins chunks from here (fs_safety.UPLOAD_ROOT)
    "FRONTEND_DIR": CFG.frontend_dir,
    "DATA_DIR": CFG.data_dir,
    "AGENT_TOKEN": CFG.agent_token,  # dev/test only
    "AGENT_TOKEN_FILE": CFG.secrets_dir / "agent.token",
    "TRUSTED_PROXIES": ["127.0.0.1", "::1"],
}


LOG_LEVEL = CFG.log_level
LOGGING_CONFIG = None  # structlog is configured by easydeploy.log_config (from settings modules)
