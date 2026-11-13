"""Bootstrap configuration from ``/etc/easydeploy/easydeploy.env`` and ``ED_*`` env vars (§5.5).

Runtime settings that the admin edits in the UI live in the ``panel.Setting`` table instead.
"""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PanelConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ED_",
        env_file="/etc/easydeploy/easydeploy.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("/opt/easydeploy/data")
    log_dir: Path = Path("/opt/easydeploy/logs")
    tmp_dir: Path = Path("/opt/easydeploy/tmp")
    secrets_dir: Path = Path("/etc/easydeploy/secrets")
    frontend_dir: Path = Path("/opt/easydeploy/current/frontend")
    redis_socket: Path = Path("/run/redis/redis-server.sock")
    redis_url: str | None = None  # overrides redis_socket when set (dev)
    agent_socket: Path = Path("/run/easydeploy/agent/agent.sock")
    agent_url: str | None = None  # dev only: http://127.0.0.1:7801
    agent_token: str | None = None  # dev/test only; production reads secrets/agent.token
    panel_port: int = Field(default=0, ge=0, le=65535)
    log_level: str = "info"
    version: str = "0.1.0-dev"

    def read_secret(self, name: str) -> str:
        return (self.secrets_dir / name).read_text(encoding="utf-8").strip()

    def redis_location(self, db: int) -> str:
        """URL for redis-py (cache, channels). Password comes from the secrets dir."""
        if self.redis_url:
            return f"{self.redis_url.rstrip('/')}/{db}"
        password = self.read_secret("redis.password")
        return f"unix://:{password}@{self.redis_socket}?db={db}"

    def celery_broker_url(self) -> str:
        if self.redis_url:
            return f"{self.redis_url.rstrip('/')}/0"
        password = self.read_secret("redis.password")
        return f"redis+socket://:{password}@{self.redis_socket}?virtual_host=0"


@functools.cache
def get_config() -> PanelConfig:
    return PanelConfig()
