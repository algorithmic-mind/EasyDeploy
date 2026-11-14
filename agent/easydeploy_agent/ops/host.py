"""``proc.*``, ``service.list|action`` and ``journal.query`` ops (§9.11, §9.14)."""

from __future__ import annotations

import json
import os
import signal as signal_mod
from typing import Any

import psutil

from easydeploy_agent.errors import NotFoundError, OpError
from easydeploy_agent.protocol.base import Empty
from easydeploy_agent.protocol.host import (
    JournalEntry,
    JournalParams,
    JournalResult,
    ListeningPort,
    PidParams,
    ProcessDetail,
    ProcessInfo,
    ProcessList,
    ProcessListParams,
    ServiceActionParams,
    ServiceActionResult,
    SignalParams,
    SignalResult,
    UnitInfo,
    UnitList,
)
from easydeploy_agent.registry import OpContext, op

# Units the panel depends on. Stopping/disabling them from the UI would cut the panel off;
# use `edctl` on the server instead. Restart stays allowed for the non-panel ones.
PANEL_UNITS = frozenset(
    {"easydeploy-agent.service", "easydeploy-api.service", "easydeploy-worker.service"}
)
CRITICAL_UNITS = PANEL_UNITS | frozenset(
    {
        "nginx.service",
        "redis-server.service",
        "docker.service",
        "containerd.service",
        "ssh.service",
        "sshd.service",
        "systemd-journald.service",
        "systemd-logind.service",
        "dbus.service",
    }
)
SIGNALS = {
    "TERM": signal_mod.SIGTERM,
    "INT": signal_mod.SIGINT,
    "KILL": getattr(signal_mod, "SIGKILL", signal_mod.SIGTERM),
    "HUP": getattr(signal_mod, "SIGHUP", signal_mod.SIGTERM),
}
PROC_ATTRS = [
    "pid",
    "ppid",
    "name",
    "username",
    "status",
    "cpu_percent",
    "memory_info",
    "memory_percent",
    "num_threads",
    "create_time",
    "cmdline",
]


def _info(raw: dict[str, Any]) -> ProcessInfo:
    mem = raw.get("memory_info")
    cmd = raw.get("cmdline") or []
    return ProcessInfo(
        pid=raw["pid"],
        ppid=raw.get("ppid") or 0,
        name=raw.get("name") or "?",
        username=raw.get("username") or "?",
        status=str(raw.get("status") or "?"),
        cpu_percent=float(raw.get("cpu_percent") or 0.0),
        memory_rss=int(mem.rss) if mem else 0,
        memory_percent=round(float(raw.get("memory_percent") or 0.0), 2),
        num_threads=int(raw.get("num_threads") or 0),
        create_time=float(raw.get("create_time") or 0.0),
        cmdline=" ".join(cmd)[:1000],
    )


def _is_protected_pid(pid: int) -> bool:
    """PID 1, the agent itself and processes of the panel's own units."""
    if pid <= 1 or pid == os.getpid():
        return True
    try:
        with open(f"/proc/{pid}/cgroup", encoding="utf-8") as fh:
            cgroup = fh.read()
    except OSError:
        return False
    return any(unit in cgroup for unit in PANEL_UNITS)


@op("proc.list", params=ProcessListParams, result=ProcessList, timeout=20)
def proc_list(params: ProcessListParams, ctx: OpContext) -> ProcessList:
    """All processes with CPU and memory usage."""
    procs = [_info(p.info) for p in psutil.process_iter(PROC_ATTRS)]
    keys = {
        "cpu": (lambda p: p.cpu_percent, True),
        "memory": (lambda p: p.memory_rss, True),
        "pid": (lambda p: p.pid, False),
        "name": (lambda p: p.name.lower(), False),
    }
    key, reverse = keys[params.sort]
    procs.sort(key=key, reverse=reverse)
    return ProcessList(processes=procs[: params.limit], total=len(procs))


def _process(pid: int) -> psutil.Process:
    try:
        return psutil.Process(pid)
    except psutil.NoSuchProcess as exc:
        raise NotFoundError("proc.not_found", "Process not found", {"pid": pid}) from exc


@op("proc.detail", params=PidParams, result=ProcessDetail, timeout=15)
def proc_detail(params: PidParams, ctx: OpContext) -> ProcessDetail:
    """One process with its executable, working directory, children and listening ports."""
    proc = _process(params.pid)
    with proc.oneshot():
        info = _info(proc.as_dict(PROC_ATTRS))
        try:
            exe, cwd = proc.exe(), proc.cwd()
        except (psutil.AccessDenied, psutil.ZombieProcess):
            exe, cwd = "", ""
        children = [c.pid for c in proc.children()]
    ports: list[ListeningPort] = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.pid == params.pid and conn.status == psutil.CONN_LISTEN and conn.laddr:
                proto = "tcp" if conn.type == 1 else "udp"
                ports.append(
                    ListeningPort(protocol=proto, address=conn.laddr.ip, port=conn.laddr.port)
                )
    except psutil.AccessDenied:
        pass
    return ProcessDetail(
        process=info,
        exe=exe,
        cwd=cwd,
        children=children,
        ports=ports,
        protected=_is_protected_pid(params.pid),
    )


@op("proc.signal", params=SignalParams, result=SignalResult, timeout=10)
def proc_signal(params: SignalParams, ctx: OpContext) -> SignalResult:
    """Send TERM/INT/HUP/KILL to a process (never to PID 1, the agent or panel units)."""
    if _is_protected_pid(params.pid):
        raise OpError(
            "proc.protected", "This process is protected", {"pid": params.pid}, status_code=403
        )
    proc = _process(params.pid)
    try:
        proc.send_signal(SIGNALS[params.signal])
    except psutil.NoSuchProcess as exc:
        raise NotFoundError("proc.not_found", "Process not found", {"pid": params.pid}) from exc
    except psutil.AccessDenied as exc:
        raise OpError(
            "proc.denied", "Permission denied", {"pid": params.pid}, status_code=403
        ) from exc
    ctx.log.info("signal sent", pid=params.pid, signal=params.signal)
    return SignalResult(pid=params.pid, signal=params.signal)


@op("service.list", params=Empty, result=UnitList, timeout=20)
def service_list(_params: Empty, ctx: OpContext) -> UnitList:
    """All systemd service units with their runtime and enablement state."""
    units = json.loads(
        ctx.executor.run(
            ["systemctl", "list-units", "--type=service", "--all", "--output=json", "--no-pager"],
            timeout=ctx.remaining(15),
        )
        .check()
        .stdout
        or "[]"
    )
    files = json.loads(
        ctx.executor.run(
            ["systemctl", "list-unit-files", "--type=service", "--output=json", "--no-pager"],
            timeout=ctx.remaining(15),
        )
        .check()
        .stdout
        or "[]"
    )
    file_state = {f["unit_file"]: f.get("state", "") for f in files}
    seen: set[str] = set()
    result = []
    for u in units:
        name = u["unit"]
        seen.add(name)
        result.append(
            UnitInfo(
                unit=name,
                description=u.get("description", ""),
                load_state=u.get("load", ""),
                active_state=u.get("active", ""),
                sub_state=u.get("sub", ""),
                unit_file_state=file_state.get(name, ""),
                protected=name in CRITICAL_UNITS,
            )
        )
    for name, state in file_state.items():  # installed but never loaded
        if name not in seen and not name.endswith("@.service"):
            result.append(
                UnitInfo(
                    unit=name,
                    description="",
                    load_state="not-loaded",
                    active_state="inactive",
                    sub_state="dead",
                    unit_file_state=state,
                    protected=name in CRITICAL_UNITS,
                )
            )
    result.sort(key=lambda x: x.unit)
    return UnitList(units=result)


@op(
    "service.action",
    params=ServiceActionParams,
    result=ServiceActionResult,
    lock="service:{unit}",
    timeout=120,
)
def service_action(params: ServiceActionParams, ctx: OpContext) -> ServiceActionResult:
    """start / stop / restart / reload / enable / disable a unit, protecting critical units."""
    if params.unit in PANEL_UNITS:
        raise OpError(
            "service.protected",
            "Panel units are managed with edctl on the server",
            {"unit": params.unit},
            status_code=403,
        )
    if params.unit in CRITICAL_UNITS and params.action in {"stop", "disable"}:
        raise OpError(
            "service.protected",
            "Stopping or disabling this unit would break the server or the panel",
            {"unit": params.unit},
            status_code=403,
        )
    ctx.executor.run(["systemctl", params.action, params.unit], timeout=ctx.remaining(110)).check()
    state = ctx.executor.run(
        ["systemctl", "is-active", params.unit], timeout=ctx.remaining(10)
    ).stdout.strip()
    return ServiceActionResult(
        unit=params.unit, action=params.action, active_state=state or "unknown"
    )


@op("journal.query", params=JournalParams, result=JournalResult, timeout=30)
def journal_query(params: JournalParams, ctx: OpContext) -> JournalResult:
    """Recent journald entries, newest last, filtered by unit / priority / time / text."""
    argv = ["journalctl", "--no-pager", "-o", "json", "-n", str(params.lines)]
    if params.unit:
        argv += ["-u", params.unit]
    if params.priority is not None:
        argv += ["-p", str(params.priority)]
    if params.since:
        argv += ["--since", params.since]
    if params.until:
        argv += ["--until", params.until]
    if params.grep:
        argv += ["--grep", params.grep, "--case-sensitive=false"]
    result = ctx.executor.run(argv, timeout=ctx.remaining(25))
    if result.returncode not in (0, 1):  # 1 = no entries matched --grep
        result.check()
    entries = []
    for line in result.stdout.splitlines():
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = raw.get("MESSAGE", "")
        if isinstance(message, list):  # binary payloads arrive as byte arrays
            message = bytes(v for v in message if isinstance(v, int)).decode("utf-8", "replace")
        pid = raw.get("_PID")
        entries.append(
            JournalEntry(
                timestamp=int(raw.get("__REALTIME_TIMESTAMP", "0")) / 1_000_000,
                unit=raw.get("_SYSTEMD_UNIT", ""),
                identifier=raw.get("SYSLOG_IDENTIFIER", ""),
                priority=int(raw.get("PRIORITY", "6")),
                message=str(message)[:4000],
                pid=int(pid) if isinstance(pid, str) and pid.isdigit() else None,
            )
        )
    return JournalResult(entries=entries)
