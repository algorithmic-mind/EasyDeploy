from __future__ import annotations

import json
import os

import pytest

from easydeploy_agent.errors import OpError
from easydeploy_agent.executor import SandboxExecutor
from easydeploy_agent.protocol.host import JournalResult, ProcessList, ServiceActionResult, UnitList
from easydeploy_agent.registry import OpContext, registry


def test_proc_list_sorted(ctx: OpContext) -> None:
    result = registry.invoke("proc.list", {"sort": "memory", "limit": 5}, ctx)
    assert isinstance(result, ProcessList)
    assert 0 < len(result.processes) <= 5
    rss = [p.memory_rss for p in result.processes]
    assert rss == sorted(rss, reverse=True)
    assert result.total >= len(result.processes)


def test_proc_detail_self(ctx: OpContext) -> None:
    detail = registry.invoke("proc.detail", {"pid": os.getpid()}, ctx)
    assert detail.process.pid == os.getpid()  # type: ignore[attr-defined]
    assert detail.protected is True  # type: ignore[attr-defined]


def test_proc_signal_refuses_protected(ctx: OpContext) -> None:
    for pid in (1, os.getpid()):
        with pytest.raises(OpError) as info:
            registry.invoke("proc.signal", {"pid": pid, "signal": "KILL"}, ctx)
        assert info.value.code == "proc.protected"


def test_proc_signal_validates(ctx: OpContext) -> None:
    with pytest.raises(OpError) as info:
        registry.invoke("proc.signal", {"pid": 99, "signal": "STOP"}, ctx)
    assert info.value.code == "agent.invalid_params"


def test_service_list_merges_unit_files(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.expect(
        "systemctl",
        "list-units",
        stdout=json.dumps(
            [
                {
                    "unit": "nginx.service",
                    "load": "loaded",
                    "active": "active",
                    "sub": "running",
                    "description": "nginx",
                },
                {
                    "unit": "cron.service",
                    "load": "loaded",
                    "active": "active",
                    "sub": "running",
                    "description": "cron",
                },
            ]
        ),
    )
    sandbox.expect(
        "systemctl",
        "list-unit-files",
        stdout=json.dumps(
            [
                {"unit_file": "nginx.service", "state": "enabled"},
                {"unit_file": "cron.service", "state": "enabled"},
                {"unit_file": "apache2.service", "state": "disabled"},
                {"unit_file": "getty@.service", "state": "enabled"},
            ]
        ),
    )
    result = registry.invoke("service.list", {}, ctx)
    assert isinstance(result, UnitList)
    by_name = {u.unit: u for u in result.units}
    assert set(by_name) == {"apache2.service", "cron.service", "nginx.service"}
    assert by_name["nginx.service"].protected is True
    assert by_name["apache2.service"].load_state == "not-loaded"


def test_service_action_argv(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.expect("systemctl", "is-active", stdout="active\n")
    result = registry.invoke("service.action", {"unit": "cron", "action": "restart"}, ctx)
    assert isinstance(result, ServiceActionResult)
    assert ("systemctl", "restart", "cron.service") in sandbox.calls
    assert result.active_state == "active"


@pytest.mark.parametrize(
    ("unit", "action"),
    [
        ("easydeploy-api", "restart"),
        ("nginx", "stop"),
        ("ssh", "disable"),
        ("docker", "stop"),
    ],
)
def test_service_action_protected(ctx: OpContext, unit: str, action: str) -> None:
    with pytest.raises(OpError) as info:
        registry.invoke("service.action", {"unit": unit, "action": action}, ctx)
    assert info.value.code == "service.protected"


def test_nginx_restart_allowed(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    registry.invoke("service.action", {"unit": "nginx", "action": "restart"}, ctx)
    assert ("systemctl", "restart", "nginx.service") in sandbox.calls


def test_journal_query(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    lines = [
        {
            "__REALTIME_TIMESTAMP": "1763000000000000",
            "_SYSTEMD_UNIT": "nginx.service",
            "SYSLOG_IDENTIFIER": "nginx",
            "PRIORITY": "3",
            "MESSAGE": "boom",
            "_PID": "12",
        },
        {"__REALTIME_TIMESTAMP": "1763000001000000", "MESSAGE": [104, 105], "PRIORITY": "6"},
    ]
    sandbox.expect("journalctl", stdout="\n".join(json.dumps(x) for x in lines))
    result = registry.invoke(
        "journal.query",
        {"unit": "nginx", "lines": 50, "priority": 3, "since": "2026-11-13 08:00", "grep": "boom"},
        ctx,
    )
    assert isinstance(result, JournalResult)
    assert sandbox.calls[-1] == (
        "journalctl",
        "--no-pager",
        "-o",
        "json",
        "-n",
        "50",
        "-u",
        "nginx.service",
        "-p",
        "3",
        "--since",
        "2026-11-13 08:00",
        "--grep",
        "boom",
        "--case-sensitive=false",
    )
    assert result.entries[0].message == "boom"
    assert result.entries[0].pid == 12
    assert result.entries[1].message == "hi"


def test_journal_rejects_bad_time(ctx: OpContext) -> None:
    with pytest.raises(OpError):
        registry.invoke("journal.query", {"since": "yesterday; rm -rf /"}, ctx)
