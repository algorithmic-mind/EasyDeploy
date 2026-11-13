"""Path validation. Paths are POSIX, absolute, normalized and NUL-free.

Symlink resolution needs the filesystem, so it happens in ops through the executor
(``resolve_under``), not in the Pydantic validator.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from typing import Annotated

from pydantic import AfterValidator

MAX_PATH = 4096


def normalize_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("path must be a non-empty string")
    if "\x00" in value:
        raise ValueError("path must not contain NUL bytes")
    if len(value) > MAX_PATH:
        raise ValueError("path is too long")
    if not value.startswith("/"):
        raise ValueError("path must be absolute")
    if "\\" in value:
        raise ValueError("backslashes are not allowed in paths")
    normalized = posixpath.normpath(value)
    # normpath keeps a leading '//' (POSIX allows it); collapse it.
    if normalized.startswith("//"):
        normalized = "/" + normalized.lstrip("/")
    return normalized


def is_under(path: str, root: str) -> bool:
    path = normalize_path(path)
    root = normalize_path(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


def is_under_any(path: str, roots: Iterable[str]) -> bool:
    return any(is_under(path, r) for r in roots)


AbsPath = Annotated[str, AfterValidator(normalize_path)]
