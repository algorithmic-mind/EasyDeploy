"""API keys for automation: ``X-API-Key: ed_<prefix>_<secret>`` (§9.1)."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from datetime import datetime

from django.utils import timezone

from apps.accounts.models import ApiKey, User
from apps.core.net import ip_in_networks

KEY_RE = re.compile(r"^ed_([a-z0-9]{8})_([A-Za-z0-9]{40})$")
SCOPE_RE = re.compile(r"^(\*|[a-z][a-z0-9_-]{1,30}):(read|write)$")
_PREFIX_ALPHABET = string.ascii_lowercase + string.digits
_SECRET_ALPHABET = string.ascii_letters + string.digits


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_key(
    user: User,
    *,
    name: str,
    scopes: list[str],
    ip_allowlist: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create a key and return ``(model, raw_key)``. The raw key is never stored."""
    while True:
        prefix = "".join(secrets.choice(_PREFIX_ALPHABET) for _ in range(8))
        if not ApiKey.objects.filter(prefix=prefix).exists():
            break
    secret = "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(40))
    raw = f"ed_{prefix}_{secret}"
    key = ApiKey.objects.create(
        user=user,
        name=name,
        prefix=prefix,
        key_hash=_hash(raw),
        scopes=sorted(set(scopes)),
        ip_allowlist=ip_allowlist or [],
        expires_at=expires_at,
    )
    return key, raw


def lookup(raw: str, ip: str | None = None) -> ApiKey | None:
    """Return the active key matching ``raw`` (and allowed for ``ip``), else ``None``."""
    match = KEY_RE.match(raw.strip())
    if not match:
        return None
    key = ApiKey.objects.select_related("user").filter(prefix=match.group(1)).first()
    if key is None or not hmac.compare_digest(key.key_hash, _hash(raw.strip())):
        return None
    if not key.is_active or not key.user.is_active:
        return None
    if key.ip_allowlist and (ip is None or not ip_in_networks(ip, key.ip_allowlist)):
        return None
    return key


def touch(key: ApiKey, ip: str | None) -> None:
    now = timezone.now()
    if key.last_used_at is None or (now - key.last_used_at).total_seconds() > 60:
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=now, last_used_ip=ip)


def allows(key: ApiKey, module: str, write: bool) -> bool:
    need = "write" if write else "read"
    granted = set(key.scopes)
    candidates = {f"{module}:{need}", f"*:{need}"}
    if not write:  # write implies read
        candidates |= {f"{module}:write", "*:write"}
    return bool(granted & candidates)


def revoke(key: ApiKey) -> None:
    if key.revoked_at is None:
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at", "updated_at"])
