"""Protected paths and safe archive extraction for the ``fs.*`` ops (§9.9).

* Some directories can never be deleted, moved or recursively chmod/chowned (``NEVER``).
* Paths under ``PROTECTED_ROOTS`` need ``confirm_protected=true`` for destructive actions; the UI
  asks the admin to type the path first.
* Archive extraction rejects absolute paths, ``..`` components, links and device files that
  would escape the destination (zip-slip).
"""

from __future__ import annotations

import posixpath
import stat
import tarfile
import zipfile
from pathlib import Path

from easydeploy_agent.errors import OpError
from easydeploy_agent.validators.path import is_under, is_under_any

NEVER = frozenset(
    {
        "/",
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/lib32",
        "/lib64",
        "/opt",
        "/proc",
        "/root",
        "/run",
        "/sbin",
        "/srv",
        "/sys",
        "/tmp",  # noqa: S108 - a path to protect, not a temp file
        "/usr",
        "/var",
        "/var/lib",
        "/var/log",
        "/var/lib/docker",
        "/opt/easydeploy",
        "/opt/easydeploy/data",
        "/opt/easydeploy/recycle",
        "/etc/easydeploy",
    }
)
PROTECTED_ROOTS = (
    "/etc",
    "/boot",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/proc",
    "/sys",
    "/dev",
    "/var/lib/docker",
    "/opt/easydeploy/data",
    "/opt/easydeploy/current",
    "/opt/easydeploy/releases",
    "/opt/easydeploy/venvs",
    "/opt/easydeploy/python",
)
RECYCLE_ROOT = "/opt/easydeploy/recycle"
UPLOAD_ROOT = "/opt/easydeploy/tmp/uploads"


def is_protected(path: str) -> bool:
    return path in NEVER or is_under_any(path, PROTECTED_ROOTS)


def check_destructive(path: str, *, confirmed: bool) -> None:
    """Raise unless a destructive action on ``path`` is allowed."""
    if path in NEVER:
        raise OpError(
            "fs.forbidden", "This path cannot be changed this way", {"path": path}, status_code=403
        )
    if is_under_any(path, PROTECTED_ROOTS) and not confirmed:
        raise OpError(
            "fs.protected",
            "This path is protected; confirm the action explicitly",
            {"path": path},
            status_code=409,
        )


def _member_target(dest: Path, name: str) -> Path:
    normalized = posixpath.normpath(name.replace("\\", "/"))
    if normalized == ".." or normalized.startswith(("/", "../")) or ":" in normalized.split("/")[0]:
        raise OpError("fs.unsafe_archive", "Archive entry escapes the destination", {"entry": name})
    target = (dest / normalized).resolve()
    if target != dest and dest not in target.parents:
        raise OpError("fs.unsafe_archive", "Archive entry escapes the destination", {"entry": name})
    return target


def safe_extract_zip(archive: Path, dest: Path) -> int:
    """Extract a zip after validating every entry; returns the number of entries."""
    dest = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        for info in infos:  # validate everything before writing anything
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise OpError(
                    "fs.unsafe_archive",
                    "Archives with symlinks are not allowed",
                    {"entry": info.filename},
                )
            _member_target(dest, info.filename)
        for info in infos:
            target = _member_target(dest, info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                while chunk := src.read(1024 * 1024):
                    out.write(chunk)
            perms = (info.external_attr >> 16) & 0o777
            if perms:
                target.chmod(perms & 0o755 | 0o600)
    return len(infos)


def safe_extract_tar(archive: Path, dest: Path) -> int:
    """Extract a tar (any compression tarfile knows) with Python's ``data`` filter."""
    dest = dest.resolve()
    try:
        with tarfile.open(archive, mode="r:*") as tf:
            members = tf.getmembers()
            for m in members:
                _member_target(dest, m.name)
                if m.issym() or m.islnk():
                    link_target = posixpath.normpath(
                        posixpath.join(posixpath.dirname(m.name), m.linkname)
                        if m.issym()
                        else m.linkname
                    )
                    _member_target(dest, link_target)
            tf.extractall(dest, filter="data")
    except tarfile.FilterError as exc:
        raise OpError("fs.unsafe_archive", "Unsafe archive entry", {"reason": str(exc)}) from exc
    except tarfile.TarError as exc:
        raise OpError("fs.bad_archive", "Not a valid archive", {"reason": str(exc)}) from exc
    return len(members)


def under(path: str, root: str) -> bool:
    return is_under(path, root)
