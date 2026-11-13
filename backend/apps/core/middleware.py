"""Request ID propagation (API → worker → agent, ADR-0018)."""

from __future__ import annotations

from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse

from apps.core.request_context import new_request_id, request_id_var


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        rid = new_request_id(request.META.get("HTTP_X_REQUEST_ID"))
        request.request_id = rid  # type: ignore[attr-defined]
        token = request_id_var.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)
        try:
            response = self.get_response(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)
        response["X-Request-ID"] = rid
        return response
