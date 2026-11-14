from __future__ import annotations

from typing import Literal

from pydantic import Field

from easydeploy_agent.protocol.base import StrictModel
from easydeploy_agent.protocol.fs import FsEntry
from easydeploy_agent.validators.names import LinuxUser
from easydeploy_agent.validators.path import AbsPath

Paths = list[AbsPath]


class PathParams(StrictModel):
    path: AbsPath


class StatResult(StrictModel):
    entry: FsEntry
    protected: bool
    realpath: str


class ReadParams(PathParams):
    max_bytes: int = Field(default=5 * 1024 * 1024, ge=1, le=5 * 1024 * 1024)


class ReadResult(StrictModel):
    path: str
    content: str
    sha256: str
    size: int
    mtime: float
    encoding: str


class WriteParams(PathParams):
    content: str = Field(max_length=5 * 1024 * 1024)
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    create_only: bool = False


class WriteResult(StrictModel):
    path: str
    sha256: str
    size: int


class MkdirParams(PathParams):
    parents: bool = True


class OkResult(StrictModel):
    ok: bool = True
    count: int = 0


class MoveParams(StrictModel):
    sources: Paths = Field(min_length=1, max_length=1000)
    destination: AbsPath  # target directory, or the new name when renaming one source
    rename: bool = False
    overwrite: bool = False
    confirm_protected: bool = False


class DeleteParams(StrictModel):
    paths: Paths = Field(min_length=1, max_length=1000)
    confirm_protected: bool = False


class RecycleItem(StrictModel):
    id: str
    original_path: str
    deleted_at: float
    size: int
    kind: str


class RecycleList(StrictModel):
    items: list[RecycleItem]


class RecycleIdsParams(StrictModel):
    ids: list[str] = Field(default_factory=list, max_length=1000)
    all: bool = False


class ChmodParams(StrictModel):
    paths: Paths = Field(min_length=1, max_length=1000)
    mode: str = Field(pattern=r"^[0-7]{3,4}$")
    recursive: bool = False
    confirm_protected: bool = False


class ChownParams(StrictModel):
    paths: Paths = Field(min_length=1, max_length=1000)
    user: LinuxUser
    group: LinuxUser
    recursive: bool = False
    confirm_protected: bool = False


class SymlinkParams(StrictModel):
    target: AbsPath
    link: AbsPath


class UploadFinalizeParams(StrictModel):
    upload_dir: AbsPath
    destination: AbsPath
    chunks: int = Field(ge=1, le=1_000_000)
    size: int = Field(ge=0)
    overwrite: bool = False


class DuResult(StrictModel):
    path: str
    size: int
    files: int
    dirs: int


class SearchParams(StrictModel):
    root: AbsPath
    name: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=200)
    max_results: int = Field(default=500, ge=1, le=5000)


class SearchResult(StrictModel):
    matches: list[str]
    truncated: bool


ArchiveFormat = Literal["zip", "tar.gz", "tar.xz", "tar.zst"]


class CompressParams(StrictModel):
    paths: Paths = Field(min_length=1, max_length=1000)
    destination: AbsPath
    format: ArchiveFormat = "zip"


class ExtractParams(StrictModel):
    archive: AbsPath
    destination: AbsPath


class FetchParams(StrictModel):
    url: str = Field(pattern=r"^https?://", max_length=2000)
    destination: AbsPath
    max_bytes: int = Field(default=10 * 1024**3, ge=1)


class FileResult(StrictModel):
    path: str
    size: int
