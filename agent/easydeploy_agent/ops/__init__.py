"""Op modules. Importing this package registers every op in ``registry.registry``."""

from easydeploy_agent.ops import fs, host, metrics, service, system

__all__ = ["fs", "host", "metrics", "service", "system"]
