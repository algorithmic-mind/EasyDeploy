"""structlog configuration (ADR-0018). Request/task IDs come from contextvars."""

from __future__ import annotations

import logging
import logging.config
import sys
from typing import Any

import structlog

from apps.core.redaction import redact_mapping


def _redact(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact_mapping(event_dict)


def configure_logging(level: str = "info", *, json_output: bool = True) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structlog": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.processors.format_exc_info,
                        renderer,
                    ],
                    "foreign_pre_chain": shared,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    # stderr: journald captures it, and command output on stdout stays clean.
                    "stream": sys.stderr,
                    "formatter": "structlog",
                }
            },
            "root": {"handlers": ["console"], "level": numeric},
            "loggers": {
                "django.db.backends": {"level": "WARNING"},
                "uvicorn.access": {"level": "WARNING"},
            },
        }
    )
