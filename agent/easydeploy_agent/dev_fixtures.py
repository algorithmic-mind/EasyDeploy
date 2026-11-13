"""Canned command results used by ``DryRunExecutor`` in development (``--dev``).

They let the UI be built against realistic data on a laptop (including Windows) without
touching the host. Keep them minimal and close to real command output.
"""

from __future__ import annotations

from easydeploy_agent.executor import CommandResult

_SYSTEMCTL_SHOW = """Id={unit}
Description={description}
LoadState=loaded
ActiveState=active
SubState=running
UnitFileState=enabled
MainPID=1234
ActiveEnterTimestamp=Fri 2026-11-13 08:00:00 UTC
"""

_DESCRIPTIONS = {
    "nginx.service": "A high performance web server and a reverse proxy server",
    "docker.service": "Docker Application Container Engine",
    "redis-server.service": "Advanced key-value store",
}


def dev_responder(argv: tuple[str, ...]) -> CommandResult | None:
    if argv[:2] == ("systemctl", "show") and len(argv) >= 3:
        unit = argv[2]
        desc = _DESCRIPTIONS.get(unit, f"{unit} (dry-run)")
        return CommandResult(argv, 0, _SYSTEMCTL_SHOW.format(unit=unit, description=desc), "")
    return None
