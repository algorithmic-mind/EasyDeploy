"""Metric collection, rates, history queries and retention (§9.2)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.core.agent_client import get_agent
from apps.monitoring.models import HostSample
from apps.panel.services import get_setting

LAST_KEY = "monitor:last-metrics"
RAW = 60
DOWNSAMPLED = 300
DOWNSAMPLE_AFTER = timedelta(days=7)
RANGES: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
MAX_POINTS = 720
AVERAGED = (
    "cpu_percent",
    "load1",
    "mem_used",
    "mem_total",
    "swap_used",
    "swap_total",
    "disk_read_bps",
    "disk_write_bps",
    "net_rx_bps",
    "net_tx_bps",
    "disk_percent",
)


def _rate(cur: float, prev: float, dt: float) -> float:
    return max(0.0, (cur - prev) / dt) if dt > 0 else 0.0


def with_rates(cur: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
    """Add I/O rates (bytes/s) computed from the previous sample's cumulative counters."""
    out = dict(cur)
    out["disk_read_bps"] = out["disk_write_bps"] = 0.0
    out["net_rx_bps"] = out["net_tx_bps"] = 0.0
    out["net_rates"] = {}
    if not prev:
        return out
    dt = float(cur["timestamp"]) - float(prev["timestamp"])
    out["disk_read_bps"] = _rate(cur["disk_read_bytes"], prev["disk_read_bytes"], dt)
    out["disk_write_bps"] = _rate(cur["disk_write_bytes"], prev["disk_write_bytes"], dt)
    before = {n["interface"]: n for n in prev.get("net", [])}
    for nic in cur.get("net", []):
        old = before.get(nic["interface"])
        if old is None:
            continue
        rx = _rate(nic["bytes_recv"], old["bytes_recv"], dt)
        tx = _rate(nic["bytes_sent"], old["bytes_sent"], dt)
        out["net_rates"][nic["interface"]] = {"rx_bps": rx, "tx_bps": tx}
        out["net_rx_bps"] += rx
        out["net_tx_bps"] += tx
    return out


def collect_sample() -> HostSample | None:
    """Read metrics from the agent and store one raw sample (called every 60 s by beat)."""
    if not get_setting("monitoring.enabled"):
        return None
    current = get_agent().call("system.metrics")
    previous = cache.get(LAST_KEY)
    cache.set(LAST_KEY, current, 3600)
    m = with_rates(current, previous)
    disks = m.get("disks", [])
    return HostSample.objects.create(
        ts=timezone.now(),
        resolution=RAW,
        cpu_percent=m["cpu_percent"],
        load1=m["load1"],
        mem_used=m["memory_used"],
        mem_total=m["memory_total"],
        swap_used=m["swap_used"],
        swap_total=m["swap_total"],
        disk_read_bps=m["disk_read_bps"],
        disk_write_bps=m["disk_write_bps"],
        net_rx_bps=m["net_rx_bps"],
        net_tx_bps=m["net_tx_bps"],
        disk_percent=max((d["percent"] for d in disks), default=0.0),
        data={
            "disks": {d["mountpoint"]: d["percent"] for d in disks},
            "net": m["net_rates"],
        },
    )


def _average(rows: Sequence[HostSample]) -> dict[str, float]:
    return {f: sum(getattr(r, f) for r in rows) / len(rows) for f in AVERAGED}


@transaction.atomic(using="monitor")
def maintenance(now: datetime | None = None) -> dict[str, int]:
    """Downsample raw samples older than 7 days to 5-minute averages; apply retention."""
    now = now or timezone.now()
    retention = timedelta(days=int(get_setting("monitoring.retention_days")))
    deleted, _ = HostSample.objects.filter(ts__lt=now - retention).delete()

    old_raw = list(
        HostSample.objects.filter(resolution=RAW, ts__lt=now - DOWNSAMPLE_AFTER).order_by("ts")
    )
    buckets: dict[int, list[HostSample]] = {}
    for row in old_raw:
        buckets.setdefault(int(row.ts.timestamp()) // DOWNSAMPLED, []).append(row)
    HostSample.objects.bulk_create(
        HostSample(
            ts=datetime.fromtimestamp(key * DOWNSAMPLED, tz=now.tzinfo),
            resolution=DOWNSAMPLED,
            **_average(rows),
        )
        for key, rows in buckets.items()
    )
    HostSample.objects.filter(pk__in=[r.pk for r in old_raw]).delete()
    return {"deleted": deleted, "downsampled": len(old_raw), "buckets": len(buckets)}


def _point(ts: datetime, values: dict[str, float]) -> dict[str, Any]:
    return {"ts": ts.isoformat(), **{k: round(v, 2) for k, v in values.items()}}


def history(range_key: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """Points for a chart range, averaged down to at most ``MAX_POINTS``."""
    now = now or timezone.now()
    rows = list(HostSample.objects.filter(ts__gte=now - RANGES[range_key]).order_by("ts"))
    if len(rows) <= MAX_POINTS:
        return [_point(r.ts, {f: getattr(r, f) for f in AVERAGED}) for r in rows]
    size = -(-len(rows) // MAX_POINTS)
    return [_point(chunk[0].ts, _average(chunk)) for chunk in _chunks(rows, size)]


def _chunks(rows: Sequence[HostSample], size: int) -> Iterable[Sequence[HostSample]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]
