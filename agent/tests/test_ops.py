from __future__ import annotations

import pytest

from easydeploy_agent.errors import NotFoundError, OpError
from easydeploy_agent.executor import SandboxExecutor
from easydeploy_agent.protocol.fs import FsListResult
from easydeploy_agent.protocol.service import ServiceStatus
from easydeploy_agent.protocol.system import SystemInfo
from easydeploy_agent.registry import OpContext, registry

OS_RELEASE = 'PRETTY_NAME="Ubuntu 24.04.3 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\nID=ubuntu\n'


def test_system_info_reads_os_release(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/etc/os-release", OS_RELEASE)
    info = registry.invoke("system.info", {}, ctx)
    assert isinstance(info, SystemInfo)
    assert info.os_name == "Ubuntu 24.04.3 LTS"
    assert info.os_version == "24.04"
    assert info.os_id == "ubuntu"
    assert info.executor == "sandbox"
    assert info.cpu_threads >= 1


def test_system_info_without_os_release(ctx: OpContext) -> None:
    info = registry.invoke("system.info", {}, ctx)
    assert isinstance(info, SystemInfo)
    assert info.os_name


def test_service_status_argv_and_parse(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.expect(
        "systemctl",
        "show",
        stdout=(
            "Id=nginx.service\nDescription=nginx web server\nLoadState=loaded\n"
            "ActiveState=active\nSubState=running\nUnitFileState=enabled\nMainPID=812\n"
            "ActiveEnterTimestamp=Fri 2026-11-13 08:00:00 UTC\n"
        ),
    )
    status = registry.invoke("service.status", {"unit": "nginx"}, ctx)
    assert sandbox.calls == [
        (
            "systemctl",
            "show",
            "nginx.service",
            "--no-pager",
            "--property=Id,Description,LoadState,ActiveState,SubState,UnitFileState,MainPID,"
            "ActiveEnterTimestamp",
        )
    ]
    assert status == ServiceStatus(
        unit="nginx.service",
        description="nginx web server",
        load_state="loaded",
        active_state="active",
        sub_state="running",
        unit_file_state="enabled",
        main_pid=812,
        active_since="Fri 2026-11-13 08:00:00 UTC",
    )


def test_service_status_not_found(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.expect("systemctl", "show", stdout="Id=nope.service\nLoadState=not-found\n")
    with pytest.raises(NotFoundError):
        registry.invoke("service.status", {"unit": "nope"}, ctx)


def test_service_status_command_failure(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.expect("systemctl", returncode=1, stderr="Failed to connect to bus")
    with pytest.raises(OpError) as info:
        registry.invoke("service.status", {"unit": "nginx"}, ctx)
    assert info.value.code == "agent.command_failed"
    assert "Failed to connect" in info.value.details["stderr"]


def test_service_status_rejects_injection(ctx: OpContext) -> None:
    with pytest.raises(OpError) as info:
        registry.invoke("service.status", {"unit": "nginx; reboot"}, ctx)
    assert info.value.code == "agent.invalid_params"


def test_fs_list_sorted_dirs_first(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/srv/site/b.txt", "bb")
    sandbox.write_text("/srv/site/.hidden", "")
    sandbox.write_text("/srv/site/A/index.html", "<h1>")
    result = registry.invoke("fs.list", {"path": "/srv/site/../site"}, ctx)
    assert isinstance(result, FsListResult)
    assert result.path == "/srv/site"
    assert [e.name for e in result.entries] == ["A", ".hidden", "b.txt"]
    assert result.entries[0].kind == "dir"
    assert result.entries[2].size == 2
    assert result.entries[2].path == "/srv/site/b.txt"


def test_fs_list_hidden_filter_and_limit(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    for name in ("a", "b", "c", ".d"):
        sandbox.write_text(f"/data/{name}", "")
    result = registry.invoke("fs.list", {"path": "/data", "show_hidden": False, "limit": 2}, ctx)
    assert isinstance(result, FsListResult)
    assert [e.name for e in result.entries] == ["a", "b"]
    assert result.truncated is True


def test_fs_list_missing_dir(ctx: OpContext) -> None:
    with pytest.raises(NotFoundError):
        registry.invoke("fs.list", {"path": "/does/not/exist"}, ctx)


def test_sandbox_blocks_escape(sandbox: SandboxExecutor) -> None:
    with pytest.raises(OpError):
        sandbox.local_path("relative")


def test_system_metrics_shape(ctx: OpContext) -> None:
    from easydeploy_agent.protocol.metrics import SystemMetrics

    first = registry.invoke("system.metrics", {}, ctx)
    second = registry.invoke("system.metrics", {}, ctx)
    assert isinstance(first, SystemMetrics)
    assert isinstance(second, SystemMetrics)
    assert 0 <= second.cpu_percent <= 100
    assert second.memory_total >= second.memory_used > 0
    assert len(second.top_memory) <= 5
    assert all(not n.interface.startswith(("lo", "veth", "docker")) for n in second.net)
    assert second.disk_read_bytes >= first.disk_read_bytes
