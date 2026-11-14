"""Mutating ``fs.*`` ops: read/write, mkdir, move/copy, recycle bin, permissions, uploads (§9.9).

Long-running ops (``fs.du``, ``fs.search``, ``fs.compress``, ``fs.extract``, ``fs.fetch``) are
meant to be called through the streaming endpoint by worker tasks; they emit progress events.
"""

from __future__ import annotations

import fnmatch
import hashlib
import ipaddress
import json
import posixpath
import socket
import time
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator

from easydeploy_agent.errors import NotFoundError, OpError
from easydeploy_agent.fs_safety import RECYCLE_ROOT, UPLOAD_ROOT, check_destructive, is_protected
from easydeploy_agent.ops.fs import to_entry
from easydeploy_agent.protocol.base import Empty
from easydeploy_agent.protocol.files import (
    ChmodParams,
    ChownParams,
    CompressParams,
    DeleteParams,
    DuResult,
    ExtractParams,
    FetchParams,
    FileResult,
    MkdirParams,
    MoveParams,
    OkResult,
    PathParams,
    ReadParams,
    ReadResult,
    RecycleIdsParams,
    RecycleItem,
    RecycleList,
    SearchParams,
    SearchResult,
    StatResult,
    SymlinkParams,
    UploadFinalizeParams,
    WriteParams,
    WriteResult,
)
from easydeploy_agent.registry import OpContext, op
from easydeploy_agent.validators.path import is_under

ENCODINGS = ("utf-8", "cp1256", "latin-1")  # UTF-16 only when a BOM says so
UTF16_BOMS = (bytes([0xFF, 0xFE]), bytes([0xFE, 0xFF]))
BLOCKED_NETWORKS = [ipaddress.ip_network("169.254.0.0/16"), ipaddress.ip_network("fd00:ec2::/32")]


def _exists(ctx: OpContext, path: str) -> bool:
    return ctx.executor.exists(path)


def _require(ctx: OpContext, path: str) -> None:
    if not _exists(ctx, path):
        raise NotFoundError("fs.not_found", "Path does not exist", {"path": path})


@op("fs.stat", params=PathParams, result=StatResult, timeout=10)
def fs_stat(params: PathParams, ctx: OpContext) -> StatResult:
    """Metadata of one path."""
    st = ctx.executor.stat(params.path)
    return StatResult(
        entry=to_entry(st),
        protected=is_protected(params.path),
        realpath=ctx.executor.realpath(params.path),
    )


@op("fs.read", params=ReadParams, result=ReadResult, timeout=20)
def fs_read(params: ReadParams, ctx: OpContext) -> ReadResult:
    """Read a text file for the editor (≤ 5 MB, encoding detected)."""
    st = ctx.executor.stat(params.path)
    if st.kind != "file":
        raise OpError("fs.not_a_file", "Not a regular file", {"path": params.path})
    if st.size > params.max_bytes:
        raise OpError(
            "fs.too_large", "File is too large for the editor", {"max_bytes": params.max_bytes}
        )
    with ctx.executor.open_read(params.path) as fh:
        data = fh.read(params.max_bytes + 1)
    if b"\x00" in data[:8192] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise OpError("fs.binary", "Binary files cannot be edited", {"path": params.path})
    candidates = ("utf-16",) if data.startswith(UTF16_BOMS) else ENCODINGS
    for encoding in candidates:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return ReadResult(
        path=params.path,
        content=text,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        mtime=st.mtime,
        encoding=encoding,
    )


@op("fs.write", params=WriteParams, result=WriteResult, timeout=30)
def fs_write(params: WriteParams, ctx: OpContext) -> WriteResult:
    """Atomically write a text file; refuses if it changed since it was read (conflict)."""
    exists = _exists(ctx, params.path)
    if exists and params.create_only:
        raise OpError(
            "fs.exists",
            "A file with this name already exists",
            {"path": params.path},
            status_code=409,
        )
    mode, owner = 0o644, None
    if exists:
        st = ctx.executor.stat(params.path)
        if st.kind != "file":
            raise OpError("fs.not_a_file", "Not a regular file", {"path": params.path})
        if params.expected_sha256:
            with ctx.executor.open_read(params.path) as fh:
                current = hashlib.sha256(fh.read()).hexdigest()
            if current != params.expected_sha256:
                raise OpError(
                    "fs.conflict",
                    "The file changed since it was opened",
                    {"path": params.path, "sha256": current},
                    status_code=409,
                )
        mode, owner = st.mode, (st.uid, st.gid)
    else:
        parent = ctx.executor.stat(posixpath.dirname(params.path))
        owner = (parent.uid, parent.gid)
    data = params.content.encode("utf-8")
    ctx.executor.write_stream(params.path, [data], mode=mode)
    if owner:
        ctx.executor.chown(params.path, *owner)
    return WriteResult(path=params.path, sha256=hashlib.sha256(data).hexdigest(), size=len(data))


@op("fs.mkdir", params=MkdirParams, result=OkResult, timeout=10)
def fs_mkdir(params: MkdirParams, ctx: OpContext) -> OkResult:
    """Create a directory (owned like its parent)."""
    if _exists(ctx, params.path):
        raise OpError("fs.exists", "Already exists", {"path": params.path}, status_code=409)
    parent = posixpath.dirname(params.path)
    if not params.parents:
        _require(ctx, parent)
    ctx.executor.makedirs(params.path)
    if _exists(ctx, parent):
        st = ctx.executor.stat(parent)
        ctx.executor.chown(params.path, st.uid, st.gid)
    return OkResult(count=1)


def _targets(params: MoveParams) -> Iterator[tuple[str, str]]:
    if params.rename:
        if len(params.sources) != 1:
            raise OpError("fs.invalid", "Rename takes exactly one source")
        yield params.sources[0], params.destination
        return
    for src in params.sources:
        yield src, posixpath.join(params.destination, posixpath.basename(src))


def _transfer(params: MoveParams, ctx: OpContext, *, copy: bool) -> OkResult:
    count = 0
    for src, dst in _targets(params):
        _require(ctx, src)
        if not copy:
            check_destructive(src, confirmed=params.confirm_protected)
        if src == dst or is_under(dst, src):
            raise OpError("fs.invalid", "Cannot move or copy a folder into itself", {"path": src})
        if _exists(ctx, dst):
            if not params.overwrite:
                raise OpError("fs.exists", "Destination exists", {"path": dst}, status_code=409)
            check_destructive(dst, confirmed=params.confirm_protected)
            ctx.executor.remove(dst)
        (ctx.executor.copy if copy else ctx.executor.move)(src, dst)
        count += 1
    return OkResult(count=count)


@op("fs.move", params=MoveParams, result=OkResult, timeout=600)
def fs_move(params: MoveParams, ctx: OpContext) -> OkResult:
    """Move or rename files and folders."""
    return _transfer(params, ctx, copy=False)


@op("fs.copy", params=MoveParams, result=OkResult, timeout=3600)
def fs_copy(params: MoveParams, ctx: OpContext) -> OkResult:
    """Copy files and folders (recursively, symlinks preserved)."""
    return _transfer(params, ctx, copy=True)


@op("fs.delete", params=DeleteParams, result=OkResult, lock="recycle", timeout=600)
def fs_delete(params: DeleteParams, ctx: OpContext) -> OkResult:
    """Move paths to the recycle bin (``/opt/easydeploy/recycle``)."""
    for path in params.paths:
        _require(ctx, path)
        check_destructive(path, confirmed=params.confirm_protected)
        if is_under(path, RECYCLE_ROOT):
            raise OpError("fs.invalid", "Use the recycle bin to purge items", {"path": path})
    for path in params.paths:
        st = ctx.executor.stat(path)
        item_id = uuid.uuid4().hex
        base = f"{RECYCLE_ROOT}/{item_id}"
        ctx.executor.makedirs(base, mode=0o700)
        meta = {
            "original_path": path,
            "deleted_at": time.time(),
            "size": st.size if st.kind == "file" else 0,
            "kind": st.kind,
        }
        ctx.executor.write_text(f"{base}/meta.json", json.dumps(meta), mode=0o600)
        ctx.executor.move(path, f"{base}/item")
    return OkResult(count=len(params.paths))


def _recycle_items(ctx: OpContext) -> list[RecycleItem]:
    if not _exists(ctx, RECYCLE_ROOT):
        return []
    items = []
    for entry in ctx.executor.scandir(RECYCLE_ROOT):
        try:
            meta = json.loads(ctx.executor.read_text(f"{entry.path}/meta.json"))
        except (OpError, json.JSONDecodeError):
            continue
        items.append(RecycleItem(id=entry.name, **meta))
    items.sort(key=lambda i: i.deleted_at, reverse=True)
    return items


@op("fs.recycle_list", params=Empty, result=RecycleList, timeout=30)
def fs_recycle_list(_params: Empty, ctx: OpContext) -> RecycleList:
    """Items in the recycle bin, newest first."""
    return RecycleList(items=_recycle_items(ctx))


def _selected(params: RecycleIdsParams, ctx: OpContext) -> list[RecycleItem]:
    items = _recycle_items(ctx)
    if params.all:
        return items
    wanted = set(params.ids)
    return [i for i in items if i.id in wanted]


@op("fs.recycle_restore", params=RecycleIdsParams, result=OkResult, lock="recycle", timeout=600)
def fs_recycle_restore(params: RecycleIdsParams, ctx: OpContext) -> OkResult:
    """Put items back where they were (fails if the original path is taken again)."""
    count = 0
    for item in _selected(params, ctx):
        if _exists(ctx, item.original_path):
            raise OpError(
                "fs.exists",
                "The original path exists again",
                {"path": item.original_path},
                status_code=409,
            )
        ctx.executor.makedirs(posixpath.dirname(item.original_path))
        ctx.executor.move(f"{RECYCLE_ROOT}/{item.id}/item", item.original_path)
        ctx.executor.remove(f"{RECYCLE_ROOT}/{item.id}")
        count += 1
    return OkResult(count=count)


@op(
    "fs.recycle_purge",
    params=RecycleIdsParams,
    result=OkResult,
    lock="recycle",
    sensitive=True,
    timeout=3600,
)
def fs_recycle_purge(params: RecycleIdsParams, ctx: OpContext) -> OkResult:
    """Permanently delete recycle-bin items (sudo mode)."""
    items = _selected(params, ctx)
    for item in items:
        ctx.executor.remove(f"{RECYCLE_ROOT}/{item.id}")
    return OkResult(count=len(items))


def _each_path(ctx: OpContext, paths: list[str], recursive: bool) -> Iterator[str]:
    for path in paths:
        _require(ctx, path)
        yield path
        if recursive and ctx.executor.stat(path).kind == "dir":
            for root, dirs, files in ctx.executor.walk(path):
                for name in dirs + files:
                    yield posixpath.join(root, name)


@op("fs.chmod", params=ChmodParams, result=OkResult, timeout=600)
def fs_chmod(params: ChmodParams, ctx: OpContext) -> OkResult:
    """Change permissions (octal), optionally recursively."""
    for path in params.paths:
        if params.recursive:
            check_destructive(path, confirmed=params.confirm_protected)
    mode = int(params.mode, 8)
    count = 0
    for path in _each_path(ctx, params.paths, params.recursive):
        ctx.executor.chmod(path, mode)
        count += 1
    return OkResult(count=count)


@op("fs.chown", params=ChownParams, result=OkResult, timeout=600)
def fs_chown(params: ChownParams, ctx: OpContext) -> OkResult:
    """Change owner and group, optionally recursively."""
    import grp
    import pwd

    try:
        uid = pwd.getpwnam(params.user).pw_uid
        gid = grp.getgrnam(params.group).gr_gid
    except KeyError as exc:
        raise OpError(
            "fs.unknown_owner",
            "Unknown user or group",
            {"user": params.user, "group": params.group},
        ) from exc
    for path in params.paths:
        if params.recursive:
            check_destructive(path, confirmed=params.confirm_protected)
    count = 0
    for path in _each_path(ctx, params.paths, params.recursive):
        ctx.executor.chown(path, uid, gid)
        count += 1
    return OkResult(count=count)


@op("fs.symlink", params=SymlinkParams, result=OkResult, timeout=10)
def fs_symlink(params: SymlinkParams, ctx: OpContext) -> OkResult:
    """Create a symbolic link ``link`` → ``target``."""
    if _exists(ctx, params.link):
        raise OpError("fs.exists", "Already exists", {"path": params.link}, status_code=409)
    ctx.executor.symlink(params.target, params.link)
    return OkResult(count=1)


@op("fs.upload_finalize", params=UploadFinalizeParams, result=FileResult, timeout=3600)
def fs_upload_finalize(params: UploadFinalizeParams, ctx: OpContext) -> FileResult:
    """Join uploaded chunks (written by the API under the upload root) into the destination."""
    if not is_under(params.upload_dir, UPLOAD_ROOT) or params.upload_dir == UPLOAD_ROOT:
        raise OpError("fs.invalid", "Upload directory outside the upload area", status_code=403)
    if _exists(ctx, params.destination) and not params.overwrite:
        raise OpError(
            "fs.exists", "Destination exists", {"path": params.destination}, status_code=409
        )
    parent = posixpath.dirname(params.destination)
    _require(ctx, parent)

    def chunks() -> Iterator[bytes]:
        for index in range(params.chunks):
            with ctx.executor.open_read(f"{params.upload_dir}/{index:06d}.part") as fh:
                while block := fh.read(1024 * 1024):
                    yield block
            if index % 16 == 0:
                ctx.emit_progress(int(index * 100 / params.chunks))

    size = ctx.executor.write_stream(params.destination, chunks())
    if size != params.size:
        ctx.executor.remove(params.destination)
        raise OpError(
            "fs.upload_incomplete",
            "Uploaded size does not match",
            {"expected": params.size, "got": size},
        )
    st = ctx.executor.stat(parent)
    ctx.executor.chown(params.destination, st.uid, st.gid)
    ctx.executor.remove(params.upload_dir)
    return FileResult(path=params.destination, size=size)


@op("fs.du", params=PathParams, result=DuResult, timeout=3600, stream=True)
def fs_du(params: PathParams, ctx: OpContext) -> DuResult:
    """Total size of a directory tree (does not follow symlinks)."""
    size = files = dirs = 0
    for root, dnames, fnames in ctx.executor.walk(params.path):
        dirs += len(dnames)
        for name in fnames:
            try:
                size += ctx.executor.stat(posixpath.join(root, name)).size
                files += 1
            except OpError:
                continue
        if files and files % 5000 == 0:
            ctx.emit_log(f"{files} files, {size} bytes so far")
    return DuResult(path=params.path, size=size, files=files, dirs=dirs)


@op("fs.search", params=SearchParams, result=SearchResult, timeout=3600, stream=True)
def fs_search(params: SearchParams, ctx: OpContext) -> SearchResult:
    """Find files by name (glob) and/or text content (files ≤ 5 MB)."""
    if not params.name and not params.content:
        raise OpError("fs.invalid", "Give a name pattern or a text to search for")
    pattern = (params.name or "*").lower()
    needle = params.content.encode() if params.content else None
    matches: list[str] = []
    for root, _dirs, files in ctx.executor.walk(params.root):
        for name in files:
            if not fnmatch.fnmatch(name.lower(), pattern):
                continue
            path = posixpath.join(root, name)
            if needle is not None:
                try:
                    st = ctx.executor.stat(path)
                    if st.kind != "file" or st.size > 5 * 1024 * 1024:
                        continue
                    with ctx.executor.open_read(path) as fh:
                        if needle not in fh.read():
                            continue
                except (OpError, OSError):
                    continue
            matches.append(path)
            if len(matches) >= params.max_results:
                return SearchResult(matches=matches, truncated=True)
    return SearchResult(matches=matches, truncated=False)


@op("fs.compress", params=CompressParams, result=FileResult, timeout=7200, stream=True)
def fs_compress(params: CompressParams, ctx: OpContext) -> FileResult:
    """Create an archive (zip, tar.gz, tar.xz, tar.zst) from paths."""
    for path in params.paths:
        _require(ctx, path)
    if _exists(ctx, params.destination):
        raise OpError(
            "fs.exists", "Destination exists", {"path": params.destination}, status_code=409
        )
    size = ctx.executor.create_archive(
        params.paths, params.destination, params.format, ctx.emit_log
    )
    return FileResult(path=params.destination, size=size)


@op("fs.extract", params=ExtractParams, result=OkResult, timeout=7200, stream=True)
def fs_extract(params: ExtractParams, ctx: OpContext) -> OkResult:
    """Extract an archive safely (zip-slip and link escapes are rejected)."""
    _require(ctx, params.archive)
    ctx.executor.makedirs(params.destination)
    count = ctx.executor.extract_archive(params.archive, params.destination)
    owner = ctx.executor.stat(params.destination)
    if owner.uid != 0:  # e.g. a site root owned by www-data: extracted files follow it
        for path in _each_path(ctx, [params.destination], recursive=True):
            ctx.executor.chown(path, owner.uid, owner.gid)
    return OkResult(count=count)


def _check_url(url: str) -> None:
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise OpError("fs.fetch_failed", "Cannot resolve host", {"host": host}) from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if any(addr in net for net in BLOCKED_NETWORKS):
            raise OpError(
                "fs.fetch_blocked", "This address is not allowed", {"host": host}, status_code=403
            )


@op("fs.fetch", params=FetchParams, result=FileResult, timeout=7200, stream=True)
def fs_fetch(params: FetchParams, ctx: OpContext) -> FileResult:
    """Download a URL to a file (remote download), with a size limit."""
    if _exists(ctx, params.destination):
        raise OpError(
            "fs.exists", "Destination exists", {"path": params.destination}, status_code=409
        )
    _check_url(params.url)
    request = urllib.request.Request(params.url, headers={"User-Agent": "EasyDeploy"})  # noqa: S310
    try:
        response = urllib.request.urlopen(request, timeout=30)  # noqa: S310  # nosec B310 - http(s) only
    except OSError as exc:
        raise OpError("fs.fetch_failed", "Download failed", {"reason": str(exc)[:300]}) from exc
    total = int(response.headers.get("Content-Length") or 0)

    def chunks() -> Iterator[bytes]:
        done = 0
        with response:
            while block := response.read(1024 * 1024):
                done += len(block)
                if done > params.max_bytes:
                    raise OpError("fs.too_large", "Download exceeds the size limit")
                if total:
                    ctx.emit_progress(int(done * 100 / total))
                yield block

    size = ctx.executor.write_stream(params.destination, chunks())
    return FileResult(path=params.destination, size=size)
