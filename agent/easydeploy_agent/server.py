"""HTTP API of the agent (served over a Unix domain socket in production).

Endpoints (§5.3):
    GET  /v1/health
    GET  /v1/ops                    registry listing with JSON schemas
    GET  /v1/files/download?path=   raw file bytes (bearer token)
    POST /v1/ops/{op_name}          {"ok": true, "result": {...}} | {"ok": false, "error": {...}}
    POST /v1/ops/{op_name}/stream   NDJSON events: log, progress, result, error
    WS   /v1/pty                    interactive terminal (bearer + sudo token)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import queue
import threading
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import structlog
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from easydeploy_agent import __version__
from easydeploy_agent.audit import AuditLog
from easydeploy_agent.auth import Authenticator
from easydeploy_agent.errors import OpError
from easydeploy_agent.executor import Executor
from easydeploy_agent.locks import LockManager
from easydeploy_agent.pty_session import EchoSession, PtySession, PtyStart
from easydeploy_agent.registry import OpContext, Registry
from easydeploy_agent.validators.path import normalize_path

log = structlog.get_logger(__name__)

_INTERNAL = {"code": "agent.internal", "message": "Internal agent error", "details": {}}
_DONE = object()


def create_app(
    *,
    registry: Registry,
    executor: Executor,
    token: str,
    audit: AuditLog,
    locks: LockManager | None = None,
) -> FastAPI:
    app = FastAPI(
        title="EasyDeploy Agent",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    auth = Authenticator(token)
    lock_manager = locks or LockManager()

    @app.exception_handler(OpError)
    async def _op_error(_request: Request, exc: OpError) -> JSONResponse:
        return JSONResponse({"ok": False, "error": exc.to_dict()}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _crash(_request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled agent error", exc_info=exc)
        return JSONResponse({"ok": False, "error": _INTERNAL}, status_code=500)

    async def _prepare(request: Request, op_name: str) -> tuple[dict[str, Any], OpContext]:
        auth.check_bearer(request.headers.get("authorization"))
        spec = registry.get(op_name)
        actor = request.headers.get("x-actor")
        if spec.sensitive:
            auth.check_sudo(request.headers.get("x-sudo-token"), actor)
        body = await request.body()
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            raise OpError("agent.bad_json", "Request body is not valid JSON") from None
        if not isinstance(params, dict):
            raise OpError("agent.bad_json", "Request body must be a JSON object")
        ctx = OpContext(
            executor=executor,
            locks=lock_manager,
            request_id=request.headers.get("x-request-id"),
            actor=actor,
            log=log.bind(op=op_name, request_id=request.headers.get("x-request-id")),
        )
        return params, ctx

    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "result": {"status": "ok", "executor": executor.name}}

    @app.websocket("/v1/pty")
    async def pty(websocket: WebSocket) -> None:
        """Terminal: {"type":"start",...} then input/resize frames; output as binary frames."""
        headers = websocket.headers
        actor = headers.get("x-actor")
        try:
            auth.check_bearer(headers.get("authorization"))
            auth.check_sudo(headers.get("x-sudo-token"), actor)
        except OpError as exc:
            await websocket.close(code=4401 if exc.code == "agent.unauthorized" else 4403)
            return
        await websocket.accept()
        try:
            start = PtyStart.model_validate(await websocket.receive_json())
            real = executor.name == "real" and os.name == "posix"
            session: PtySession | EchoSession = PtySession(start) if real else EchoSession(start)
        except (ValueError, OpError, OSError) as exc:
            await websocket.send_json({"type": "error", "message": str(exc)[:300]})
            await websocket.close(code=4400)
            return
        opened = time.monotonic()
        audit.write(
            op="pty.open",
            params=start.model_dump(),
            ok=True,
            duration_ms=0,
            request_id=headers.get("x-request-id"),
            actor=actor,
        )
        await websocket.send_json({"type": "started"})

        async def pump() -> None:
            while (data := await session.read()) is not None:
                await websocket.send_bytes(data)
            code = session.close()
            with contextlib.suppress(Exception):
                await websocket.send_json({"type": "exit", "code": code})
                await websocket.close()

        pump_task = asyncio.create_task(pump())
        try:
            while True:
                message = await websocket.receive_json()
                kind = message.get("type")
                if kind == "input" and isinstance(message.get("data"), str):
                    session.write(message["data"][:65536].encode())
                elif kind == "resize":
                    session.resize(int(message.get("cols", 80)), int(message.get("rows", 24)))
        except (WebSocketDisconnect, RuntimeError, ValueError):
            pass
        finally:
            session.close()
            pump_task.cancel()
            audit.write(
                op="pty.close",
                params={"mode": start.mode},
                ok=True,
                duration_ms=(time.monotonic() - opened) * 1000,
                request_id=headers.get("x-request-id"),
                actor=actor,
            )

    @app.get("/v1/files/download")
    async def download(request: Request, path: str) -> StreamingResponse:
        """Raw bytes of one file (the API proxies this to the browser)."""
        auth.check_bearer(request.headers.get("authorization"))
        try:
            clean = normalize_path(path)
        except ValueError as exc:
            raise OpError("agent.invalid_params", str(exc)) from None
        st = await run_in_threadpool(executor.stat, clean)
        handle = await run_in_threadpool(executor.open_read, clean)
        audit.write(
            op="fs.download",
            params={"path": clean},
            ok=True,
            duration_ms=0,
            request_id=request.headers.get("x-request-id"),
            actor=request.headers.get("x-actor"),
        )

        def chunks() -> Iterator[bytes]:
            with handle:
                while block := handle.read(256 * 1024):
                    yield block

        return StreamingResponse(
            chunks(),
            media_type="application/octet-stream",
            headers={"Content-Length": str(st.size)},
        )

    @app.get("/v1/ops")
    async def list_ops(request: Request) -> dict[str, Any]:
        auth.check_bearer(request.headers.get("authorization"))
        return {"ok": True, "result": {"ops": [spec.describe() for spec in registry.all()]}}

    @app.post("/v1/ops/{op_name}")
    async def invoke(op_name: str, request: Request) -> dict[str, Any]:
        params, ctx = await _prepare(request, op_name)
        result = await run_in_threadpool(registry.invoke, op_name, params, ctx, audit)
        return {"ok": True, "result": result.model_dump(mode="json")}

    @app.post("/v1/ops/{op_name}/stream")
    async def invoke_stream(op_name: str, request: Request) -> StreamingResponse:
        params, ctx = await _prepare(request, op_name)
        events: queue.Queue[Any] = queue.Queue()
        ctx.emit_event = events.put

        def worker() -> None:
            try:
                result = registry.invoke(op_name, params, ctx, audit)
                events.put({"type": "result", "result": result.model_dump(mode="json")})
            except OpError as exc:
                events.put({"type": "error", "error": exc.to_dict()})
            except Exception:
                log.exception("streamed op crashed", op=op_name)
                events.put({"type": "error", "error": _INTERNAL})
            finally:
                events.put(_DONE)

        threading.Thread(target=worker, name=f"op-{op_name}", daemon=True).start()

        async def lines() -> AsyncIterator[bytes]:
            while True:
                event = await run_in_threadpool(events.get)
                if event is _DONE:
                    return
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode()

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    return app
