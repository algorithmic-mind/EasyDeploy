"""``system.*`` ops."""

from __future__ import annotations

import platform
import socket
import time

import psutil

from easydeploy_agent import __version__
from easydeploy_agent.errors import OpError
from easydeploy_agent.protocol.base import Empty
from easydeploy_agent.protocol.system import SystemInfo
from easydeploy_agent.registry import OpContext, op

_QUOTES = "\"'"


def parse_os_release(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key] = value.strip().strip(_QUOTES)
    return data


def _cpu_model(ctx: OpContext) -> str:
    try:
        for line in ctx.executor.read_text("/proc/cpuinfo").splitlines():
            if line.lower().startswith(("model name", "hardware")):
                return line.split(":", 1)[1].strip()
    except OpError:
        pass
    return platform.processor() or "unknown"


@op("system.info", params=Empty, result=SystemInfo, timeout=10)
def system_info(_params: Empty, ctx: OpContext) -> SystemInfo:
    """Static host information for the dashboard."""
    try:
        os_release = parse_os_release(ctx.executor.read_text("/etc/os-release"))
    except OpError:
        os_release = {}
    boot = psutil.boot_time()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return SystemInfo(
        hostname=socket.gethostname(),
        os_name=os_release.get("PRETTY_NAME", platform.system()),
        os_version=os_release.get("VERSION_ID", platform.release()),
        os_id=os_release.get("ID", platform.system().lower()),
        kernel=platform.release(),
        arch=platform.machine().lower(),
        cpu_model=_cpu_model(ctx),
        cpu_cores=psutil.cpu_count(logical=False) or 1,
        cpu_threads=psutil.cpu_count(logical=True) or 1,
        memory_total=mem.total,
        swap_total=swap.total,
        boot_time=boot,
        uptime_seconds=int(time.time() - boot),
        agent_version=__version__,
        executor=ctx.executor.name,
    )
