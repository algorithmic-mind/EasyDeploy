"""EasyDeploy privileged agent.

The agent is the only component that runs as root. It exposes a registry of typed,
validated operations ("ops") over a Unix domain socket and never executes raw shell
strings received from the API (MASTER_PROMPT §5.3).
"""

__version__ = "0.1.0"
