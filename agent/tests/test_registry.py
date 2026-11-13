from __future__ import annotations

import threading

import pytest

from easydeploy_agent.audit import AuditLog
from easydeploy_agent.errors import InvalidParamsError, LockTimeoutError, OpError, UnknownOpError
from easydeploy_agent.protocol.base import StrictModel
from easydeploy_agent.registry import OpContext, Registry


class EchoParams(StrictModel):
    name: str
    password: str = "x"


class EchoResult(StrictModel):
    greeting: str


def make_registry() -> Registry:
    reg = Registry()

    @reg.op("test.echo", params=EchoParams, result=EchoResult, lock="echo:{name}")
    def echo(params: EchoParams, ctx: OpContext) -> EchoResult:
        """Echo a greeting."""
        ctx.emit_progress(50)
        return EchoResult(greeting=f"hello {params.name}")

    @reg.op("test.bad", params=EchoParams, result=EchoResult)
    def bad(params: EchoParams, ctx: OpContext) -> EchoResult:
        return EchoParams(name="wrong")  # type: ignore[return-value]

    return reg


def test_invoke_and_audit(ctx: OpContext) -> None:
    reg = make_registry()
    audit = AuditLog(None)
    result = reg.invoke("test.echo", {"name": "ali", "password": "s3cret"}, ctx, audit)
    assert result == EchoResult(greeting="hello ali")
    record = audit.records[-1]
    assert record["ok"] is True
    assert record["params"]["password"] == "***"
    assert record["request_id"] == "req-1"


def test_duplicate_registration_fails() -> None:
    reg = make_registry()
    with pytest.raises(ValueError):
        reg.op("test.echo", params=EchoParams, result=EchoResult)(
            lambda p, c: EchoResult(greeting="")
        )


def test_unknown_op(ctx: OpContext) -> None:
    with pytest.raises(UnknownOpError):
        make_registry().invoke("nope", {}, ctx)


def test_invalid_params_rejected(ctx: OpContext) -> None:
    audit = AuditLog(None)
    with pytest.raises(InvalidParamsError) as info:
        make_registry().invoke("test.echo", {"name": "a", "extra": 1}, ctx, audit)
    assert info.value.code == "agent.invalid_params"
    assert audit.records[-1]["error"] == "agent.invalid_params"


def test_wrong_result_type(ctx: OpContext) -> None:
    with pytest.raises(OpError) as info:
        make_registry().invoke("test.bad", {"name": "a"}, ctx)
    assert info.value.code == "agent.bad_result"


def test_lock_is_held_and_times_out(ctx: OpContext) -> None:
    reg = make_registry()
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with ctx.locks.hold("echo:ali"):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=hold)
    thread.start()
    held.wait(5)
    try:
        ctx.locks.default_timeout = 0.05
        with pytest.raises(LockTimeoutError):
            reg.invoke("test.echo", {"name": "ali"}, ctx)
        # A different lock key is not blocked.
        assert reg.invoke("test.echo", {"name": "reza"}, ctx) == EchoResult(greeting="hello reza")
    finally:
        release.set()
        thread.join()


def test_describe_contains_schemas() -> None:
    spec = make_registry().get("test.echo")
    desc = spec.describe()
    assert desc["description"] == "Echo a greeting."
    assert desc["params_schema"]["properties"]["name"]["type"] == "string"
