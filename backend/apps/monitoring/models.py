"""Metric history in ``monitor.db`` (see ``easydeploy.db_routers``), §9.2.

Raw samples every 60 s (``resolution=60``); samples older than 7 days are averaged into 5-minute
buckets (``resolution=300``); everything older than ``monitoring.retention_days`` is deleted.
"""

from __future__ import annotations

from django.db import models


class HostSample(models.Model):
    ts = models.DateTimeField(db_index=True)
    resolution = models.PositiveSmallIntegerField(default=60)  # seconds per sample
    cpu_percent = models.FloatField()
    load1 = models.FloatField(default=0)
    mem_used = models.BigIntegerField(default=0)
    mem_total = models.BigIntegerField(default=0)
    swap_used = models.BigIntegerField(default=0)
    swap_total = models.BigIntegerField(default=0)
    disk_read_bps = models.FloatField(default=0)
    disk_write_bps = models.FloatField(default=0)
    net_rx_bps = models.FloatField(default=0)
    net_tx_bps = models.FloatField(default=0)
    disk_percent = models.FloatField(default=0)  # fullest mount
    data = models.JSONField(default=dict, blank=True)  # per-mount usage, per-interface rates

    class Meta:
        ordering = ["-ts"]
        indexes = [models.Index(fields=["resolution", "ts"])]

    def __str__(self) -> str:
        return f"{self.ts:%Y-%m-%d %H:%M} cpu={self.cpu_percent:.0f}%"
