from __future__ import annotations

from easydeploy_agent.protocol.base import StrictModel


class DiskUsage(StrictModel):
    mountpoint: str
    device: str
    fstype: str
    total: int
    used: int
    percent: float


class NetCounters(StrictModel):
    interface: str
    bytes_sent: int
    bytes_recv: int


class TopProcess(StrictModel):
    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_rss: int


class SystemMetrics(StrictModel):
    """Point-in-time metrics. I/O values are cumulative counters; callers derive rates."""

    timestamp: float
    cpu_percent: float
    cpu_per_core: list[float]
    load1: float
    load5: float
    load15: float
    memory_total: int
    memory_used: int
    memory_available: int
    swap_total: int
    swap_used: int
    disks: list[DiskUsage]
    disk_read_bytes: int
    disk_write_bytes: int
    net: list[NetCounters]
    top_cpu: list[TopProcess]
    top_memory: list[TopProcess]
    uptime_seconds: int
