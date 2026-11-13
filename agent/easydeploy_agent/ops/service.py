"""``service.*`` ops (systemd)."""

from __future__ import annotations

from easydeploy_agent.errors import NotFoundError
from easydeploy_agent.protocol.service import ServiceStatus, ServiceStatusParams
from easydeploy_agent.registry import OpContext, op

_PROPERTIES = (
    "Id",
    "Description",
    "LoadState",
    "ActiveState",
    "SubState",
    "UnitFileState",
    "MainPID",
    "ActiveEnterTimestamp",
)


def parse_systemctl_show(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            props[key] = value
    return props


@op("service.status", params=ServiceStatusParams, result=ServiceStatus, timeout=10)
def service_status(params: ServiceStatusParams, ctx: OpContext) -> ServiceStatus:
    """Status of one systemd unit."""
    argv = [
        "systemctl",
        "show",
        params.unit,
        "--no-pager",
        f"--property={','.join(_PROPERTIES)}",
    ]
    result = ctx.executor.run(argv, timeout=ctx.remaining(10)).check()
    props = parse_systemctl_show(result.stdout)
    if props.get("LoadState") == "not-found":
        raise NotFoundError("service.not_found", "Unit not found", {"unit": params.unit})
    try:
        pid = int(props.get("MainPID", "0") or 0)
    except ValueError:
        pid = 0
    return ServiceStatus(
        unit=props.get("Id", params.unit),
        description=props.get("Description", ""),
        load_state=props.get("LoadState", "unknown"),
        active_state=props.get("ActiveState", "unknown"),
        sub_state=props.get("SubState", "unknown"),
        unit_file_state=props.get("UnitFileState", "unknown"),
        main_pid=pid,
        active_since=props.get("ActiveEnterTimestamp") or None,
    )
