"""Op registry: every host operation is declared with ``@op`` and typed Pydantic params/results.

Example::

    @op("service.status", params=ServiceStatusParams, result=ServiceStatus, timeout=10)
    def service_status(params: ServiceStatusParams, ctx: OpContext) -> ServiceStatus: ...
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from easydeploy_agent.audit import AuditLog
from easydeploy_agent.errors import InvalidParamsError, OpError, UnknownOpError
from easydeploy_agent.executor import Executor
from easydeploy_agent.locks import LockManager

P = TypeVar("P", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)

EventSink = Callable[[dict[str, Any]], None]
OpFunc = Callable[[Any, "OpContext"], BaseModel]


def _discard(_event: dict[str, Any]) -> None:
    return None


@dataclass
class OpContext:
    """Everything an op may use. Ops have no other access to global state."""

    executor: Executor
    locks: LockManager
    request_id: str | None = None
    actor: str | None = None
    emit_event: EventSink = field(default=_discard)
    log: Any = field(default_factory=lambda: structlog.get_logger("easydeploy_agent.op"))
    deadline: float | None = None

    def emit_log(self, line: str, stream: str = "stdout") -> None:
        self.emit_event({"type": "log", "stream": stream, "line": line})

    def emit_progress(self, percent: int, message: str | None = None) -> None:
        self.emit_event(
            {"type": "progress", "percent": max(0, min(100, percent)), "message": message}
        )

    def remaining(self, default: float) -> float:
        """Seconds left before the op deadline, used to bound subprocess timeouts."""
        if self.deadline is None:
            return default
        return max(0.1, min(default, self.deadline - time.monotonic()))


@dataclass(frozen=True)
class OpSpec:
    name: str
    func: OpFunc
    params: type[BaseModel]
    result: type[BaseModel]
    lock: str | Callable[[Any], str] | None
    sensitive: bool
    timeout: float
    stream: bool
    description: str

    def lock_name(self, params: BaseModel) -> str | None:
        if self.lock is None:
            return None
        if callable(self.lock):
            return self.lock(params)
        return self.lock.format(**params.model_dump())

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "sensitive": self.sensitive,
            "stream": self.stream,
            "timeout": self.timeout,
            "params_schema": self.params.model_json_schema(),
            "result_schema": self.result.model_json_schema(),
        }


class Registry:
    def __init__(self) -> None:
        self._ops: dict[str, OpSpec] = {}

    def op(
        self,
        name: str,
        *,
        params: type[P],
        result: type[R],
        lock: str | Callable[[P], str] | None = None,
        sensitive: bool = False,
        timeout: float = 30.0,
        stream: bool = False,
    ) -> Callable[[Callable[[P, OpContext], R]], Callable[[P, OpContext], R]]:
        def decorator(func: Callable[[P, OpContext], R]) -> Callable[[P, OpContext], R]:
            if name in self._ops:
                raise ValueError(f"op {name!r} registered twice")
            self._ops[name] = OpSpec(
                name=name,
                func=func,
                params=params,
                result=result,
                lock=lock,
                sensitive=sensitive,
                timeout=timeout,
                stream=stream,
                description=(func.__doc__ or "").strip().split("\n")[0],
            )
            return func

        return decorator

    def get(self, name: str) -> OpSpec:
        try:
            return self._ops[name]
        except KeyError:
            raise UnknownOpError(name) from None

    def all(self) -> list[OpSpec]:
        return sorted(self._ops.values(), key=lambda s: s.name)

    def invoke(
        self,
        name: str,
        raw_params: dict[str, Any],
        ctx: OpContext,
        audit: AuditLog | None = None,
    ) -> BaseModel:
        """Validate params, take the op's lock, run it, audit the outcome."""
        spec = self.get(name)
        started = time.monotonic()
        ok = False
        error_code: str | None = None
        try:
            try:
                params = spec.params.model_validate(raw_params)
            except ValidationError as exc:
                errors = exc.errors(include_url=False, include_context=False, include_input=False)
                raise InvalidParamsError([dict(e) for e in errors]) from None
            ctx.deadline = started + spec.timeout
            with ctx.locks.hold(spec.lock_name(params)):
                result = spec.func(params, ctx)
            if not isinstance(result, spec.result):
                raise OpError("agent.bad_result", f"op {name} returned an unexpected type")
            ok = True
            return result
        except OpError as exc:
            error_code = exc.code
            raise
        except Exception:
            error_code = "agent.internal"
            ctx.log.exception("op crashed", op=name)
            raise
        finally:
            if audit is not None:
                audit.write(
                    op=name,
                    params=raw_params,
                    ok=ok,
                    duration_ms=(time.monotonic() - started) * 1000,
                    request_id=ctx.request_id,
                    actor=ctx.actor,
                    error_code=error_code,
                )


# The default registry, populated by importing ``easydeploy_agent.ops``.
registry = Registry()
op = registry.op
