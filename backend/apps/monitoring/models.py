"""Metric history, stored in ``monitor.db`` (see ``easydeploy.db_routers``). Collectors: Phase 1."""

from __future__ import annotations

from django.db import models


class HostSample(models.Model):
    ts = models.DateTimeField(db_index=True)
    resolution = models.PositiveSmallIntegerField(default=60)  # seconds (60 raw, 300 downsampled)
    cpu_percent = models.FloatField()
    load1 = models.FloatField(default=0)
    mem_used = models.BigIntegerField(default=0)
    mem_total = models.BigIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)  # per-disk / per-interface details

    class Meta:
        ordering = ["-ts"]

    def __str__(self) -> str:
        return f"{self.ts:%Y-%m-%d %H:%M} cpu={self.cpu_percent:.0f}%"
