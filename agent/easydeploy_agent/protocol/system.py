from __future__ import annotations

from easydeploy_agent.protocol.base import StrictModel


class SystemInfo(StrictModel):
    hostname: str
    os_name: str
    os_version: str
    os_id: str
    kernel: str
    arch: str
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    memory_total: int
    swap_total: int
    boot_time: float
    uptime_seconds: int
    agent_version: str
    executor: str
