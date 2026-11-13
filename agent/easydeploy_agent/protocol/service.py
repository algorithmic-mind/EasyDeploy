from __future__ import annotations

from easydeploy_agent.protocol.base import StrictModel
from easydeploy_agent.validators.names import UnitName


class ServiceStatusParams(StrictModel):
    unit: UnitName


class ServiceStatus(StrictModel):
    unit: str
    description: str
    load_state: str
    active_state: str
    sub_state: str
    unit_file_state: str
    main_pid: int
    active_since: str | None
