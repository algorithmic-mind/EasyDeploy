"""Periodic monitoring jobs (scheduled in ``CELERY_BEAT_SCHEDULE``, queue ``monitor``)."""

from __future__ import annotations

from typing import Any

import structlog
from celery import shared_task

from apps.core.errors import EasyDeployError
from apps.monitoring import services

log = structlog.get_logger(__name__)


@shared_task(name="monitor.collect", ignore_result=True, time_limit=50, soft_time_limit=45)
def collect() -> None:
    try:
        services.collect_sample()
    except EasyDeployError as exc:  # agent down: skip this sample, try again next minute
        log.warning("metrics collection skipped", code=exc.code)


@shared_task(name="monitor.maintenance", ignore_result=True, time_limit=600)
def maintenance() -> dict[str, Any]:
    return services.maintenance()
