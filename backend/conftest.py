"""Shared pytest fixtures for the backend."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from asgiref.testing import ApplicationCommunicator
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.agent_client import FakeAgent, reset_fake_agent

PASSWORD = "Violet-Harbor-7319"


class WebsocketCommunicator(ApplicationCommunicator):
    """Minimal WebSocket test client (channels.testing needs daphne, which we do not ship)."""

    def __init__(self, app: Any, path: str, headers: list[tuple[bytes, bytes]]) -> None:
        super().__init__(
            app,
            {
                "type": "websocket",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": headers,
                "subprotocols": [],
                "client": ("127.0.0.1", 50000),
                "server": ("testserver", 80),
            },
        )

    async def connect(self, timeout: float = 2) -> tuple[bool, int | None]:
        await self.send_input({"type": "websocket.connect"})
        message = await self.receive_output(timeout)
        if message["type"] == "websocket.close":
            return False, message.get("code", 1000)
        return True, message.get("subprotocol")

    async def receive_json_from(self, timeout: float = 2) -> Any:
        message = await self.receive_output(timeout)
        assert message["type"] == "websocket.send", message
        return json.loads(message["text"])

    async def disconnect(self, code: int = 1000, timeout: float = 2) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})
        await self.wait(timeout)


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def fake_agent() -> FakeAgent:
    return reset_fake_agent()


@pytest.fixture
def admin_user(db: Any) -> User:
    user = User(username="admin", role=User.Role.ADMIN)
    user.set_password(PASSWORD)
    user.save()
    return user


@pytest.fixture
def client() -> APIClient:  # overrides pytest-django's Django test client
    return APIClient()


@pytest.fixture
def auth_client(client: APIClient, admin_user: User) -> APIClient:
    """A client logged in through the real login endpoint (session has sudo + timestamps)."""
    resp = client.post(
        "/api/v1/auth/login", {"username": "admin", "password": PASSWORD}, format="json"
    )
    assert resp.status_code == 200, resp.content
    return client


@pytest.fixture
def set_setting() -> Any:
    from apps.panel.services import set_setting as _set

    def setter(key: str, value: Any) -> Any:
        return _set(key, value, actor_label="test")

    return setter
