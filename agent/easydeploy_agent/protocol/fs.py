from __future__ import annotations

from typing import Literal

from pydantic import Field

from easydeploy_agent.protocol.base import StrictModel
from easydeploy_agent.validators.path import AbsPath


class FsListParams(StrictModel):
    path: AbsPath
    show_hidden: bool = True
    limit: int = Field(default=5000, ge=1, le=20000)


class FsEntry(StrictModel):
    name: str
    path: str
    kind: Literal["file", "dir", "symlink", "other"]
    size: int
    mode: str  # octal, e.g. "0644"
    owner: str
    group: str
    mtime: float
    link_target: str | None = None


class FsListResult(StrictModel):
    path: str
    entries: list[FsEntry]
    truncated: bool = False
