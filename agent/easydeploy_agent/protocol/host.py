from __future__ import annotations

from typing import Literal

from pydantic import Field

from easydeploy_agent.protocol.base import StrictModel
from easydeploy_agent.validators.names import UnitName


class ProcessInfo(StrictModel):
    pid: int
    ppid: int
    name: str
    username: str
    status: str
    cpu_percent: float
    memory_rss: int
    memory_percent: float
    num_threads: int
    create_time: float
    cmdline: str


class ProcessListParams(StrictModel):
    sort: Literal["cpu", "memory", "pid", "name"] = "cpu"
    limit: int = Field(default=500, ge=1, le=5000)


class ProcessList(StrictModel):
    processes: list[ProcessInfo]
    total: int


class PidParams(StrictModel):
    pid: int = Field(ge=1, le=4_194_304)


class ListeningPort(StrictModel):
    protocol: str
    address: str
    port: int


class ProcessDetail(StrictModel):
    process: ProcessInfo
    exe: str
    cwd: str
    children: list[int]
    ports: list[ListeningPort]
    protected: bool


class SignalParams(PidParams):
    signal: Literal["TERM", "KILL", "HUP", "INT"] = "TERM"


class SignalResult(StrictModel):
    pid: int
    signal: str


class UnitInfo(StrictModel):
    unit: str
    description: str
    load_state: str
    active_state: str
    sub_state: str
    unit_file_state: str
    protected: bool


class UnitList(StrictModel):
    units: list[UnitInfo]


ServiceAction = Literal["start", "stop", "restart", "reload", "enable", "disable"]


class ServiceActionParams(StrictModel):
    unit: UnitName
    action: ServiceAction


class ServiceActionResult(StrictModel):
    unit: str
    action: str
    active_state: str


class JournalParams(StrictModel):
    unit: UnitName | None = None
    lines: int = Field(default=200, ge=1, le=5000)
    priority: int | None = Field(default=None, ge=0, le=7)
    since: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$")
    until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$")
    grep: str | None = Field(default=None, max_length=200)


class JournalEntry(StrictModel):
    timestamp: float
    unit: str
    identifier: str
    priority: int
    message: str
    pid: int | None = None


class JournalResult(StrictModel):
    entries: list[JournalEntry]
