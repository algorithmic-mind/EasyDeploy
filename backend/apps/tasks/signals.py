"""Celery signal hooks."""

from __future__ import annotations

from typing import Any

import structlog
from celery.signals import worker_ready

log = structlog.get_logger(__name__)


@worker_ready.connect
def _recover_lost_tasks(**_kwargs: Any) -> None:
    from apps.tasks.services import mark_worker_lost

    count = mark_worker_lost()
    if count:
        log.warning("marked interrupted tasks as failed", count=count)
