"""Executors: the only place where the agent touches processes and the filesystem.

* ``RealExecutor``    — production: runs commands, uses the real filesystem.
* ``DryRunExecutor``  — development: records argv and returns canned results; reads come from the
  real filesystem, writes are kept in memory and never reach the disk.
* ``SandboxExecutor`` — tests: records argv like DryRun, all file operations are rooted under a
  temporary directory so ops can be exercised end to end without touching the host.

Ops never call ``subprocess`` or ``open`` directly; they go through ``OpContext.executor``.
"""

from __future__ import annotations

import os
import shutil
import stat as stat_mod
import subprocess
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, ClassVar, Literal

import structlog

from easydeploy_agent.errors import CommandError, CommandTimeoutError, NotFoundError, OpError

log = structlog.get_logger(__name__)

FileKind = Literal["file", "dir", "symlink", "other"]

MINIMAL_ENV = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
}
MAX_READ_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def check(self) -> CommandResult:
        if self.returncode != 0:
            raise CommandError(list(self.argv), self.returncode, self.stderr)
        return self


@dataclass(frozen=True, slots=True)
class FileStat:
    path: str
    name: str
    kind: FileKind
    size: int
    mode: int
    uid: int
    gid: int
    mtime: float
    link_target: str | None = None


def _kind(st_mode: int) -> FileKind:
    if stat_mod.S_ISLNK(st_mode):
        return "symlink"
    if stat_mod.S_ISDIR(st_mode):
        return "dir"
    if stat_mod.S_ISREG(st_mode):
        return "file"
    return "other"


def _tar_writer(path: Path, fmt: str) -> tarfile.TarFile:
    if fmt == "tar.gz":
        return tarfile.open(path, "w:gz")
    if fmt == "tar.xz":
        return tarfile.open(path, "w:xz")
    return tarfile.open(path, "w")  # tar.zst: compressed afterwards with the zstd CLI


def _check_argv(argv: Sequence[str]) -> tuple[str, ...]:
    if isinstance(argv, str) or not argv:
        raise OpError("agent.bad_argv", "argv must be a non-empty list of strings")
    items = tuple(argv)
    for item in items:
        if not isinstance(item, str) or "\x00" in item:
            raise OpError("agent.bad_argv", "argv items must be strings without NUL bytes")
    return items


class Executor(ABC):
    """Abstract executor. Paths passed to it are always absolute *host* paths (POSIX style)."""

    name: ClassVar[str]

    # ------------------------------------------------------------------ processes
    @abstractmethod
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 30.0,
        input_data: bytes | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
    ) -> CommandResult: ...

    # ------------------------------------------------------------------ filesystem
    @abstractmethod
    def local_path(self, path: str) -> Path:
        """Map a host path to the path this process should open."""

    def exists(self, path: str) -> bool:
        return os.path.lexists(self.local_path(path))

    def stat(self, path: str) -> FileStat:
        local = self.local_path(path)
        try:
            st = local.lstat()
        except FileNotFoundError as exc:
            raise NotFoundError("fs.not_found", "Path does not exist", {"path": path}) from exc
        target = os.readlink(local) if stat_mod.S_ISLNK(st.st_mode) else None
        name = PurePosixPath(path).name or "/"
        return FileStat(
            path=path,
            name=name,
            kind=_kind(st.st_mode),
            size=st.st_size,
            mode=stat_mod.S_IMODE(st.st_mode),
            uid=getattr(st, "st_uid", 0),
            gid=getattr(st, "st_gid", 0),
            mtime=st.st_mtime,
            link_target=target,
        )

    def scandir(self, path: str) -> list[FileStat]:
        local = self.local_path(path)
        if not local.is_dir():
            raise NotFoundError("fs.not_a_directory", "Path is not a directory", {"path": path})
        base = PurePosixPath(path)
        result: list[FileStat] = []
        try:
            entries = list(os.scandir(local))
        except PermissionError as exc:
            raise OpError("fs.permission_denied", "Permission denied", {"path": path}) from exc
        for entry in entries:
            try:
                result.append(self.stat(str(base / entry.name)))
            except (NotFoundError, PermissionError):
                continue  # vanished or unreadable between scandir and lstat
        return result

    def read_text(self, path: str, *, max_bytes: int = MAX_READ_BYTES) -> str:
        local = self.local_path(path)
        try:
            with local.open("rb") as fh:
                data = fh.read(max_bytes + 1)
        except FileNotFoundError as exc:
            raise NotFoundError("fs.not_found", "File does not exist", {"path": path}) from exc
        if len(data) > max_bytes:
            raise OpError("fs.too_large", "File is too large to read", {"max_bytes": max_bytes})
        return data.decode("utf-8", errors="replace")

    def write_text(self, path: str, content: str, *, mode: int = 0o644) -> None:
        """Atomically replace ``path`` with ``content`` (temp file + fsync + rename)."""
        local = self.local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=local.parent, prefix=f".{local.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, mode)
            os.replace(tmp, local)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------ mutations
    # DryRunExecutor overrides every method below so development never changes the host.

    def host_path(self, local: Path) -> str:
        """Inverse of ``local_path`` (identity outside the sandbox)."""
        return str(local)

    def realpath(self, path: str) -> str:
        """Resolve symlinks; the result is a host path."""
        return self.host_path(self.local_path(path).resolve())

    def open_read(self, path: str) -> BinaryIO:
        local = self.local_path(path)
        if not local.is_file():
            raise NotFoundError("fs.not_a_file", "Not a regular file", {"path": path})
        return local.open("rb")

    def write_stream(self, path: str, chunks: Iterable[bytes], *, mode: int = 0o644) -> int:
        """Atomically write ``chunks`` to ``path``; returns the number of bytes written."""
        local = self.local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=local.parent, prefix=f".{local.name}.", suffix=".part")
        written = 0
        try:
            with os.fdopen(fd, "wb") as fh:
                for chunk in chunks:
                    fh.write(chunk)
                    written += len(chunk)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, mode)
            os.replace(tmp, local)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return written

    def makedirs(self, path: str, mode: int = 0o755) -> None:
        self.local_path(path).mkdir(parents=True, exist_ok=True, mode=mode)

    def move(self, src: str, dst: str) -> None:
        shutil.move(self.local_path(src), self.local_path(dst))

    def copy(self, src: str, dst: str) -> None:
        source, target = self.local_path(src), self.local_path(dst)
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)

    def remove(self, path: str) -> None:
        local = self.local_path(path)
        if local.is_dir() and not local.is_symlink():
            shutil.rmtree(local)
        else:
            local.unlink()

    def chmod(self, path: str, mode: int) -> None:
        local = self.local_path(path)
        if not local.is_symlink():  # Linux cannot chmod a symlink itself
            os.chmod(local, mode)

    def chown(self, path: str, uid: int, gid: int) -> None:
        if hasattr(os, "chown"):  # absent on Windows development machines
            os.chown(self.local_path(path), uid, gid, follow_symlinks=False)

    def symlink(self, target: str, link: str) -> None:
        os.symlink(target, self.local_path(link))

    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]:
        for root, dirs, files in os.walk(self.local_path(path)):
            yield self.host_path(Path(root)), dirs, files

    def create_archive(
        self, sources: Sequence[str], dest: str, fmt: str, log_line: Callable[[str], None]
    ) -> int:
        """Write a zip / tar.gz / tar.xz / tar.zst archive atomically; returns its size."""
        target = self.local_path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.part")
        try:
            if fmt == "zip":
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                    for src in sources:
                        base = self.local_path(src)
                        if base.is_dir() and not base.is_symlink():
                            for root, _dirs, files in os.walk(base):
                                for name in files:
                                    file = Path(root) / name
                                    zf.write(file, file.relative_to(base.parent).as_posix())
                                log_line(str(Path(root).relative_to(base.parent)))
                        else:
                            zf.write(base, base.name)
            else:
                tar_path = tmp.with_suffix(".tar") if fmt == "tar.zst" else tmp
                with _tar_writer(tar_path, fmt) as tf:
                    for src in sources:
                        base = self.local_path(src)
                        tf.add(base, arcname=base.name)
                        log_line(base.name)
                if fmt == "tar.zst":
                    self.run(
                        ["zstd", "-q", "-f", "-T0", str(tar_path), "-o", str(tmp)], timeout=7200
                    ).check()
                    tar_path.unlink(missing_ok=True)
            os.replace(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return target.stat().st_size

    def extract_archive(self, archive: str, dest: str) -> int:
        """Safely extract zip / tar.* archives into ``dest``; returns the number of entries."""
        from easydeploy_agent.fs_safety import safe_extract_tar, safe_extract_zip

        src, target = self.local_path(archive), self.local_path(dest)
        name = src.name.lower()
        if name.endswith(".zip"):
            return safe_extract_zip(src, target)
        if name.endswith((".tar.zst", ".tzst")):
            tmp = target / f".{src.name}.tar"
            self.run(["zstd", "-d", "-q", "-f", str(src), "-o", str(tmp)], timeout=7200).check()
            try:
                return safe_extract_tar(tmp, target)
            finally:
                tmp.unlink(missing_ok=True)
        if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")):
            return safe_extract_tar(src, target)
        raise OpError("fs.bad_archive", "Unsupported archive type", {"path": archive})


class RealExecutor(Executor):
    name = "real"

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 30.0,
        input_data: bytes | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        args = _check_argv(argv)
        full_env = {**MINIMAL_ENV, **(env or {})}
        log.debug("exec", argv=args)
        try:
            proc = subprocess.run(
                list(args),
                input=input_data,
                capture_output=True,
                timeout=timeout,
                env=full_env,
                cwd=cwd,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandTimeoutError(list(args), timeout) from exc
        except FileNotFoundError as exc:
            raise OpError(
                "agent.binary_missing", f"Program not found: {args[0]}", {"argv": list(args)}
            ) from exc
        return CommandResult(
            argv=args,
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
        )

    def local_path(self, path: str) -> Path:
        return Path(path)


Responder = Callable[[tuple[str, ...]], CommandResult | None]


@dataclass
class _Rule:
    prefix: tuple[str, ...]
    result: CommandResult


@dataclass
class _Recorder:
    calls: list[tuple[str, ...]] = field(default_factory=list)
    rules: list[_Rule] = field(default_factory=list)
    responder: Responder | None = None


class _RecordingMixin:
    """Command recording + canned results shared by DryRun and Sandbox executors."""

    _rec: _Recorder

    @property
    def calls(self) -> list[tuple[str, ...]]:
        return self._rec.calls

    def expect(self, *prefix: str, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        """Register a canned result for commands whose argv starts with ``prefix``."""
        self._rec.rules.insert(0, _Rule(prefix, CommandResult(prefix, returncode, stdout, stderr)))

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 30.0,
        input_data: bytes | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        args = _check_argv(argv)
        self._rec.calls.append(args)
        log.info("dry-run exec", argv=args)
        for rule in self._rec.rules:
            if args[: len(rule.prefix)] == rule.prefix:
                return CommandResult(
                    args, rule.result.returncode, rule.result.stdout, rule.result.stderr
                )
        if self._rec.responder is not None:
            canned = self._rec.responder(args)
            if canned is not None:
                return canned
        return CommandResult(args, 0, "", "")


class DryRunExecutor(_RecordingMixin, Executor):
    """Reads the real filesystem, never writes to it and never runs commands."""

    name = "dryrun"

    def __init__(self, responder: Responder | None = None) -> None:
        self._rec = _Recorder(responder=responder)
        self.writes: dict[str, str] = {}
        self.mutations: list[tuple[Any, ...]] = []

    def local_path(self, path: str) -> Path:
        return Path(path)

    def read_text(self, path: str, *, max_bytes: int = MAX_READ_BYTES) -> str:
        if path in self.writes:
            return self.writes[path]
        return super().read_text(path, max_bytes=max_bytes)

    def write_text(self, path: str, content: str, *, mode: int = 0o644) -> None:
        log.info("dry-run write", path=path, bytes=len(content), mode=oct(mode))
        self.writes[path] = content

    # Mutations are recorded and logged, never applied to the developer's machine.
    def _record(self, action: str, *args: Any) -> None:
        log.info("dry-run fs", action=action, args=args)
        self.mutations.append((action, *args))

    def write_stream(self, path: str, chunks: Iterable[bytes], *, mode: int = 0o644) -> int:
        size = sum(len(c) for c in chunks)
        self._record("write", path, size)
        return size

    def makedirs(self, path: str, mode: int = 0o755) -> None:
        self._record("makedirs", path)

    def move(self, src: str, dst: str) -> None:
        self._record("move", src, dst)

    def copy(self, src: str, dst: str) -> None:
        self._record("copy", src, dst)

    def remove(self, path: str) -> None:
        self._record("remove", path)

    def chmod(self, path: str, mode: int) -> None:
        self._record("chmod", path, oct(mode))

    def chown(self, path: str, uid: int, gid: int) -> None:
        self._record("chown", path, uid, gid)

    def symlink(self, target: str, link: str) -> None:
        self._record("symlink", target, link)

    def create_archive(
        self, sources: Sequence[str], dest: str, fmt: str, log_line: Callable[[str], None]
    ) -> int:
        self._record("create_archive", tuple(sources), dest, fmt)
        return 0

    def extract_archive(self, archive: str, dest: str) -> int:
        self._record("extract_archive", archive, dest)
        return 0


class SandboxExecutor(_RecordingMixin, Executor):
    """All file operations are rooted under ``root``; commands are recorded, never executed."""

    name = "sandbox"

    def __init__(self, root: Path | None = None, responder: Responder | None = None) -> None:
        self._rec = _Recorder(responder=responder)
        self.root = (root or Path(tempfile.mkdtemp(prefix="easydeploy-sandbox-"))).resolve()

    def local_path(self, path: str) -> Path:
        pure = PurePosixPath(path)
        if not pure.is_absolute():
            raise OpError("fs.path_not_absolute", "Path must be absolute", {"path": path})
        if len(pure.parts) == 1:  # "/"
            return self.root
        local = self.root.joinpath(*pure.parts[1:])
        # Resolve symlinks and refuse anything that escapes the sandbox root.
        resolved_parent = local.parent.resolve()
        if resolved_parent != self.root and self.root not in resolved_parent.parents:
            raise OpError("fs.sandbox_escape", "Path escapes the sandbox", {"path": path})
        return local

    def host_path(self, local: Path) -> str:
        try:
            rel = local.resolve().relative_to(self.root)
        except ValueError as exc:
            raise OpError("fs.sandbox_escape", "Path escapes the sandbox", {}) from exc
        return "/" + rel.as_posix() if rel.parts else "/"


def build_executor(kind: str, sandbox_root: Path | None = None) -> Executor:
    if kind == "real":
        return RealExecutor()
    if kind == "dryrun":
        from easydeploy_agent.dev_fixtures import dev_responder

        return DryRunExecutor(responder=dev_responder)
    if kind == "sandbox":
        return SandboxExecutor(root=sandbox_root)
    raise ValueError(f"unknown executor kind: {kind}")
