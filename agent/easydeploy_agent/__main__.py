"""Entry point: ``python -m easydeploy_agent [--dev]``.

Production: binds ``/run/easydeploy/agent/agent.sock`` (0660 root:easydeploy), real executor.
Development (``--dev``): TCP 127.0.0.1:7801, DryRun executor, token from ``var/agent.token``.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import secrets
import socket
import sys
from pathlib import Path

import structlog
import uvicorn

from easydeploy_agent import ops as _ops  # noqa: F401  (registers ops)
from easydeploy_agent.audit import AuditLog
from easydeploy_agent.config import AgentSettings
from easydeploy_agent.executor import build_executor
from easydeploy_agent.locks import LockManager
from easydeploy_agent.logging_setup import configure_logging
from easydeploy_agent.registry import registry
from easydeploy_agent.server import create_app

DEV_DIR = Path("var")


def dev_token() -> str:
    """Shared dev token file, also read by the backend's dev settings."""
    path = DEV_DIR / "agent.token"
    if not path.exists():
        DEV_DIR.mkdir(exist_ok=True)
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def bind_unix_socket(path: Path, group: str) -> socket.socket:
    """Create the agent socket with mode 0660 and group ``easydeploy`` before serving."""
    import grp

    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old_umask = os.umask(0o117)
    try:
        sock.bind(str(path))
    finally:
        os.umask(old_umask)
    os.chmod(path, 0o660)  # nosec B103 - group easydeploy must connect (§5.2)
    try:
        os.chown(path, 0, grp.getgrnam(group).gr_gid)
    except KeyError:
        structlog.get_logger().warning("socket group missing; socket stays root-only", group=group)
        os.chmod(path, 0o600)
    sock.listen(128)
    return sock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="easydeploy-agent")
    parser.add_argument("--dev", action="store_true", help="TCP 127.0.0.1 + DryRun executor")
    parser.add_argument("--executor", choices=["real", "dryrun", "sandbox"])
    parser.add_argument("--socket", type=Path, help="Unix socket path")
    parser.add_argument("--tcp-port", type=int)
    args = parser.parse_args(argv)

    settings = AgentSettings()
    if args.dev:
        settings.executor = "dryrun"
        settings.tcp_host = settings.tcp_host or "127.0.0.1"
        settings.token = settings.token or dev_token()
        settings.audit_log = DEV_DIR / "agent-audit.log"
    if args.executor:
        settings.executor = args.executor
    if args.socket:
        settings.socket_path = args.socket
    if args.tcp_port:
        settings.tcp_port = args.tcp_port

    configure_logging(settings.log_level)
    log = structlog.get_logger("easydeploy_agent")
    if settings.executor == "real" and os.name == "posix" and os.geteuid() != 0:
        log.error("the real executor requires root; use --dev for development")
        return 2

    app = create_app(
        registry=registry,
        executor=build_executor(settings.executor, settings.sandbox_root),
        token=settings.load_token(),
        audit=AuditLog(settings.audit_log),
        locks=LockManager(settings.lock_timeout),
    )
    common = {"log_config": None, "access_log": False, "server_header": False}
    if settings.tcp_host:
        if settings.tcp_host not in {"127.0.0.1", "::1", "localhost"}:
            log.error("TCP mode is for local development only")
            return 2
        log.info("agent listening", tcp=f"{settings.tcp_host}:{settings.tcp_port}")
        uvicorn.run(app, host=settings.tcp_host, port=settings.tcp_port, **common)  # type: ignore[arg-type]
        return 0

    sock = bind_unix_socket(settings.socket_path, settings.socket_group)
    log.info("agent listening", socket=str(settings.socket_path), executor=settings.executor)
    server = uvicorn.Server(uvicorn.Config(app, **common))  # type: ignore[arg-type]
    server.run(sockets=[sock])
    return 0


if __name__ == "__main__":
    sys.exit(main())
