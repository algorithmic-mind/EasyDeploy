"""Op modules. Importing this package registers every op in ``registry.registry``."""

from easydeploy_agent.ops import files, fs, host, metrics, service, system

__all__ = ["files", "fs", "host", "metrics", "service", "system"]
