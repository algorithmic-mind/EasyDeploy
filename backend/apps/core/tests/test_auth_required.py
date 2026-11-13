"""§10.2: every endpoint rejects unauthenticated access except an explicit allowlist."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

# Endpoints that are intentionally reachable without authentication.
PUBLIC = {
    "api/v1/health",
    "api/v1/auth/csrf",
    "api/v1/auth/login",
    "api/v1/auth/login/2fa",
    "api/v1/auth/logout",
    "api/v1/panel/info",
}


def _walk(patterns: list[URLPattern | URLResolver], prefix: str = "") -> Iterator[str]:
    for p in patterns:
        route = str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + route)
        else:
            yield prefix + route


def _concrete(route: str) -> str:
    route = route.lstrip("^").rstrip("$")
    route = re.sub(r"<uuid:[^>]+>", str(uuid.uuid4()), route)
    route = re.sub(r"<[^>]+>", "x", route)
    route = re.sub(r"\(\?P<[^>]+>[^)]+\)", str(uuid.uuid4()), route)
    return route.replace("\\.", ".").replace("\\", "")


def api_routes() -> list[str]:
    routes = {_concrete(r) for r in _walk(get_resolver().url_patterns) if r.startswith("api/v1/")}
    return sorted(r for r in routes if "(" not in r and "[" not in r)


def test_route_discovery_finds_endpoints() -> None:
    routes = api_routes()
    assert "api/v1/auth/me" in routes
    assert any(r.startswith("api/v1/tasks") for r in routes)
    assert len(routes) > 15


@pytest.mark.parametrize("route", api_routes())
def test_unauthenticated_rejected(client: APIClient, route: str) -> None:
    if route.rstrip("/") in PUBLIC:
        pytest.skip("public endpoint")
    for method in ("get", "post", "patch", "delete"):
        resp = getattr(client, method)("/" + route, {}, format="json")
        assert resp.status_code in {401, 403, 404, 405}, (method, route, resp.status_code)
        if resp.status_code in {401, 403} and resp["Content-Type"].startswith("application/json"):
            assert resp.json()["error"]["code"].startswith(("auth.", "permission_denied"))
