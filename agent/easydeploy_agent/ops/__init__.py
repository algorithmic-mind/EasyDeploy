"""Op modules. Importing this package registers every op in ``registry.registry``."""

from easydeploy_agent.ops import fs, service, system

__all__ = ["fs", "service", "system"]
