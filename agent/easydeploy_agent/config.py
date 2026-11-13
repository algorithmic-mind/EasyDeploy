"""Agent configuration from ``ED_AGENT_*`` env vars and ``/etc/easydeploy/easydeploy.env``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ExecutorKind = Literal["real", "dryrun", "sandbox"]


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ED_AGENT_",
        env_file="/etc/easydeploy/easydeploy.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    socket_path: Path = Path("/run/easydeploy/agent/agent.sock")
    # TCP is only for development on systems without AF_UNIX server support (Windows).
    tcp_host: str | None = None
    tcp_port: int = Field(default=7801, ge=1, le=65535)
    socket_group: str = "easydeploy"
    token_file: Path = Path("/etc/easydeploy/secrets/agent.token")
    token: str | None = None  # dev/test only; production reads token_file
    executor: ExecutorKind = "real"
    sandbox_root: Path | None = None
    audit_log: Path = Path("/var/log/easydeploy/agent-audit.log")
    log_level: str = "info"
    lock_timeout: float = Field(default=120.0, gt=0)

    def load_token(self) -> str:
        if self.token:
            return self.token
        token = self.token_file.read_text(encoding="utf-8").strip()
        if len(token) < 32:
            raise RuntimeError(f"agent token in {self.token_file} is too short")
        return token
