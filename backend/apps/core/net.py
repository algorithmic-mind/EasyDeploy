"""Client IP resolution. Nginx is the only trusted proxy (it connects over the Unix socket)."""

from __future__ import annotations

import ipaddress
from typing import Any

from django.http import HttpRequest

from apps.core.conf import ed


def client_ip(request: HttpRequest) -> str:
    remote = request.META.get("REMOTE_ADDR") or ""
    trusted: list[str] = list(ed("TRUSTED_PROXIES", []))
    # Over the Unix socket there is no REMOTE_ADDR; then Nginx's X-Real-IP is authoritative.
    if not remote or remote in trusted:
        forwarded = request.META.get("HTTP_X_REAL_IP", "").strip()
        if forwarded and _is_ip(forwarded):
            return forwarded
    return remote or "unknown"


def scope_ip(scope: dict[str, Any]) -> str:
    """``client_ip`` for an ASGI (WebSocket) scope."""
    client = scope.get("client")
    remote = str(client[0]) if client else ""
    trusted: list[str] = list(ed("TRUSTED_PROXIES", []))
    if not remote or remote in trusted:
        headers = dict(scope.get("headers") or [])
        forwarded = headers.get(b"x-real-ip", b"").decode("latin-1").strip()
        if forwarded and _is_ip(forwarded):
            return forwarded
    return remote or "unknown"


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def is_local(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def ip_in_networks(ip: str, networks: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in networks:
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False
