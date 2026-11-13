"""Agent error types. Every error carries a stable, dotted ``code``."""

from __future__ import annotations

from typing import Any


class OpError(Exception):
    """An expected failure of an operation, reported to the caller in the error envelope."""

    status_code = 400

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class UnknownOpError(OpError):
    status_code = 404

    def __init__(self, name: str) -> None:
        super().__init__("agent.unknown_op", f"Unknown operation: {name}", {"op": name})


class InvalidParamsError(OpError):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("agent.invalid_params", "Invalid operation parameters", {"errors": errors})


class LockTimeoutError(OpError):
    status_code = 409

    def __init__(self, lock: str) -> None:
        super().__init__("agent.lock_timeout", f"Resource is busy (lock '{lock}')", {"lock": lock})


class CommandError(OpError):
    """A subprocess failed. ``details`` carries argv, exit code and (truncated) stderr."""

    def __init__(self, argv: list[str], returncode: int, stderr: str) -> None:
        super().__init__(
            "agent.command_failed",
            f"Command failed with exit code {returncode}: {argv[0]}",
            {"argv": argv, "returncode": returncode, "stderr": stderr[-4000:]},
            status_code=422,
        )


class CommandTimeoutError(OpError):
    def __init__(self, argv: list[str], timeout: float) -> None:
        super().__init__(
            "agent.command_timeout",
            f"Command timed out after {timeout:.0f}s: {argv[0]}",
            {"argv": argv, "timeout": timeout},
            status_code=504,
        )


class PathNotAllowedError(OpError):
    status_code = 403

    def __init__(self, path: str, reason: str) -> None:
        super().__init__("fs.path_not_allowed", f"Path not allowed: {reason}", {"path": path})


class NotFoundError(OpError):
    status_code = 404

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details)
