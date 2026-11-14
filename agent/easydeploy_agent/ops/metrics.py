"""``system.metrics``: live host metrics for the dashboard and the history collector (§9.2)."""

from __future__ import annotations

import time

import psutil

from easydeploy_agent.protocol.base import Empty
from easydeploy_agent.protocol.metrics import DiskUsage, NetCounters, SystemMetrics, TopProcess
from easydeploy_agent.registry import OpContext, op

# Pseudo / container filesystems that would only add noise to the dashboard.
IGNORED_FSTYPES = frozenset(
    {"squashfs", "overlay", "tmpfs", "devtmpfs", "nsfs", "tracefs", "autofs", "ramfs"}
)
IGNORED_IFACE_PREFIXES = ("lo", "veth", "docker", "br-")
TOP_N = 5


def _disks() -> list[DiskUsage]:
    result = []
    seen: set[str] = set()
    for part in psutil.disk_partitions(all=False):
        if part.fstype in IGNORED_FSTYPES or part.mountpoint in seen:
            continue
        if part.mountpoint.startswith(("/snap", "/var/lib/docker", "/boot/efi")):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        seen.add(part.mountpoint)
        result.append(
            DiskUsage(
                mountpoint=part.mountpoint,
                device=part.device,
                fstype=part.fstype,
                total=usage.total,
                used=usage.used,
                percent=usage.percent,
            )
        )
    return result


def _net() -> list[NetCounters]:
    counters = psutil.net_io_counters(pernic=True)
    return [
        NetCounters(interface=name, bytes_sent=c.bytes_sent, bytes_recv=c.bytes_recv)
        for name, c in sorted(counters.items())
        if not name.startswith(IGNORED_IFACE_PREFIXES)
    ]


def _top() -> tuple[list[TopProcess], list[TopProcess]]:
    procs = []
    # process_iter caches Process objects, so cpu_percent is measured since the previous call.
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info"]):
        info = p.info
        mem = info.get("memory_info")
        procs.append(
            TopProcess(
                pid=info["pid"],
                name=info.get("name") or "?",
                username=info.get("username") or "?",
                cpu_percent=float(info.get("cpu_percent") or 0.0),
                memory_rss=int(mem.rss) if mem else 0,
            )
        )
    by_cpu = sorted(procs, key=lambda x: x.cpu_percent, reverse=True)[:TOP_N]
    by_mem = sorted(procs, key=lambda x: x.memory_rss, reverse=True)[:TOP_N]
    return by_cpu, by_mem


@op("system.metrics", params=Empty, result=SystemMetrics, timeout=15)
def system_metrics(_params: Empty, ctx: OpContext) -> SystemMetrics:
    """Current CPU, memory, disk, network and top-process metrics."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    load1, load5, load15 = psutil.getloadavg()
    io = psutil.disk_io_counters()
    top_cpu, top_mem = _top()
    return SystemMetrics(
        timestamp=time.time(),
        cpu_percent=psutil.cpu_percent(interval=None),
        cpu_per_core=psutil.cpu_percent(interval=None, percpu=True),
        load1=load1,
        load5=load5,
        load15=load15,
        memory_total=mem.total,
        memory_used=mem.total - mem.available,
        memory_available=mem.available,
        swap_total=swap.total,
        swap_used=swap.used,
        disks=_disks(),
        disk_read_bytes=io.read_bytes if io else 0,
        disk_write_bytes=io.write_bytes if io else 0,
        net=_net(),
        top_cpu=top_cpu,
        top_memory=top_mem,
        uptime_seconds=int(time.time() - psutil.boot_time()),
    )
