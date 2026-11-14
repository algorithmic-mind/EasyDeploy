from __future__ import annotations

import hashlib
import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

from easydeploy_agent.errors import OpError
from easydeploy_agent.executor import DryRunExecutor, SandboxExecutor
from easydeploy_agent.locks import LockManager
from easydeploy_agent.registry import OpContext, registry


def call(ctx: OpContext, op: str, **params: object) -> object:
    return registry.invoke(op, params, ctx)


def test_read_write_conflict(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/srv/app/config.ini", "a=1\n")
    read = call(ctx, "fs.read", path="/srv/app/config.ini")
    assert read.content == "a=1\n"  # type: ignore[attr-defined]
    sha = read.sha256  # type: ignore[attr-defined]
    result = call(ctx, "fs.write", path="/srv/app/config.ini", content="a=2\n", expected_sha256=sha)
    assert result.sha256 == hashlib.sha256(b"a=2\n").hexdigest()  # type: ignore[attr-defined]
    with pytest.raises(OpError) as info:  # stale hash → conflict
        call(ctx, "fs.write", path="/srv/app/config.ini", content="a=3\n", expected_sha256=sha)
    assert info.value.code == "fs.conflict"


def test_read_rejects_binary(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.local_path("/srv/bin.dat").parent.mkdir(parents=True, exist_ok=True)
    sandbox.local_path("/srv/bin.dat").write_bytes(b"\x7fELF\x00\x00\x01")
    with pytest.raises(OpError) as info:
        call(ctx, "fs.read", path="/srv/bin.dat")
    assert info.value.code == "fs.binary"


def test_read_detects_legacy_encoding(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.local_path("/srv/fa.txt").parent.mkdir(parents=True, exist_ok=True)
    sandbox.local_path("/srv/fa.txt").write_bytes("سلام".encode("cp1256"))
    read = call(ctx, "fs.read", path="/srv/fa.txt")
    assert read.content == "سلام"  # type: ignore[attr-defined]
    assert read.encoding == "cp1256"  # type: ignore[attr-defined]


def test_mkdir_move_copy(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    call(ctx, "fs.mkdir", path="/srv/a/b")
    sandbox.write_text("/srv/a/b/f.txt", "x")
    call(ctx, "fs.copy", sources=["/srv/a/b"], destination="/srv")
    assert sandbox.local_path("/srv/b/f.txt").read_text() == "x"
    call(ctx, "fs.move", sources=["/srv/b/f.txt"], destination="/srv/g.txt", rename=True)
    assert sandbox.local_path("/srv/g.txt").exists()
    with pytest.raises(OpError) as info:
        call(ctx, "fs.copy", sources=["/srv/a"], destination="/srv/a/b")
    assert info.value.code == "fs.invalid"
    with pytest.raises(OpError) as info:
        call(ctx, "fs.copy", sources=["/srv/g.txt"], destination="/srv/g.txt", rename=True)
    assert info.value.code in {"fs.invalid", "fs.exists"}


def test_recycle_bin_roundtrip(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/srv/site/index.html", "<h1>")
    call(ctx, "fs.delete", paths=["/srv/site/index.html"])
    assert not sandbox.local_path("/srv/site/index.html").exists()
    items = call(ctx, "fs.recycle_list").items  # type: ignore[attr-defined]
    assert items[0].original_path == "/srv/site/index.html"
    call(ctx, "fs.recycle_restore", ids=[items[0].id])
    assert sandbox.local_path("/srv/site/index.html").read_text() == "<h1>"
    assert call(ctx, "fs.recycle_list").items == []  # type: ignore[attr-defined]


def test_purge_is_sensitive() -> None:
    assert registry.get("fs.recycle_purge").sensitive is True


@pytest.mark.parametrize("path", ["/", "/etc", "/opt/easydeploy", "/var/lib/docker"])
def test_never_delete(ctx: OpContext, sandbox: SandboxExecutor, path: str) -> None:
    sandbox.local_path(path).mkdir(parents=True, exist_ok=True)
    with pytest.raises(OpError) as info:
        call(ctx, "fs.delete", paths=[path])
    assert info.value.code == "fs.forbidden"


def test_protected_needs_confirmation(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/etc/nginx/old.conf", "x")
    with pytest.raises(OpError) as info:
        call(ctx, "fs.delete", paths=["/etc/nginx/old.conf"])
    assert info.value.code == "fs.protected"
    call(ctx, "fs.delete", paths=["/etc/nginx/old.conf"], confirm_protected=True)
    assert not sandbox.local_path("/etc/nginx/old.conf").exists()


def test_chmod_recursive(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/srv/d/x.sh", "#!/bin/sh")
    result = call(ctx, "fs.chmod", paths=["/srv/d"], mode="0750", recursive=True)
    assert result.count == 2  # type: ignore[attr-defined]
    if os.name == "posix":
        assert (sandbox.local_path("/srv/d/x.sh").stat().st_mode & 0o777) == 0o750


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _put(sandbox: SandboxExecutor, path: str, data: bytes) -> None:
    local = sandbox.local_path(path)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(data)


def test_extract_zip(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    _put(sandbox, "/srv/up/site.zip", _zip({"site/index.html": b"hi", "site/css/a.css": b"a{}"}))
    result = call(ctx, "fs.extract", archive="/srv/up/site.zip", destination="/srv/www")
    assert result.count == 2  # type: ignore[attr-defined]
    assert sandbox.local_path("/srv/www/site/css/a.css").read_bytes() == b"a{}"


@pytest.mark.parametrize("evil", ["../../etc/passwd", "/etc/passwd", "a/../../x", "..\\..\\x"])
def test_extract_zip_slip_rejected(sandbox: SandboxExecutor, ctx: OpContext, evil: str) -> None:
    _put(sandbox, "/srv/up/evil.zip", _zip({"ok.txt": b"1", evil: b"pwned"}))
    with pytest.raises(OpError) as info:
        call(ctx, "fs.extract", archive="/srv/up/evil.zip", destination="/srv/www")
    assert info.value.code == "fs.unsafe_archive"
    # Nothing was written: validation happens before extraction.
    assert not sandbox.local_path("/srv/www/ok.txt").exists()


def test_extract_tar_symlink_escape_rejected(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../../etc"
        tf.addfile(link)
    _put(sandbox, "/srv/up/evil.tar.gz", buf.getvalue())
    with pytest.raises(OpError) as info:
        call(ctx, "fs.extract", archive="/srv/up/evil.tar.gz", destination="/srv/www")
    assert info.value.code == "fs.unsafe_archive"


def test_compress_then_extract_tar(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/srv/proj/a.txt", "A")
    sandbox.write_text("/srv/proj/sub/b.txt", "B")
    for fmt, name in (("zip", "p.zip"), ("tar.gz", "p.tar.gz"), ("tar.xz", "p.tar.xz")):
        res = call(
            ctx, "fs.compress", paths=["/srv/proj"], destination=f"/srv/out/{name}", format=fmt
        )
        assert res.size > 0  # type: ignore[attr-defined]
        call(ctx, "fs.extract", archive=f"/srv/out/{name}", destination=f"/srv/x-{fmt}")
        assert sandbox.local_path(f"/srv/x-{fmt}/proj/sub/b.txt").read_text() == "B"


def test_upload_finalize(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    upload = "/opt/easydeploy/tmp/uploads/u1"
    for i, part in enumerate([b"hello ", b"world"]):
        _put(sandbox, f"{upload}/{i:06d}.part", part)
    sandbox.local_path("/srv/files").mkdir(parents=True)
    res = call(
        ctx,
        "fs.upload_finalize",
        upload_dir=upload,
        destination="/srv/files/h.txt",
        chunks=2,
        size=11,
    )
    assert res.size == 11  # type: ignore[attr-defined]
    assert sandbox.local_path("/srv/files/h.txt").read_bytes() == b"hello world"
    assert not sandbox.local_path(upload).exists()


def test_upload_finalize_rejects_foreign_dir(ctx: OpContext) -> None:
    with pytest.raises(OpError) as info:
        call(ctx, "fs.upload_finalize", upload_dir="/etc", destination="/srv/x", chunks=1, size=1)
    assert info.value.code == "fs.invalid"


def test_du_and_search(sandbox: SandboxExecutor, ctx: OpContext) -> None:
    sandbox.write_text("/srv/s/a.py", "import os\n")
    sandbox.write_text("/srv/s/b/c.py", "print('needle')\n")
    sandbox.write_text("/srv/s/b/d.txt", "needle\n")
    du = call(ctx, "fs.du", path="/srv/s")
    assert du.files == 3  # type: ignore[attr-defined]
    found = call(ctx, "fs.search", root="/srv/s", name="*.py", content="needle")
    assert found.matches == ["/srv/s/b/c.py"]  # type: ignore[attr-defined]


def test_dry_run_never_touches_disk(tmp_path: Path) -> None:
    target = tmp_path / "keep.txt"
    target.write_text("original")
    dry = DryRunExecutor()
    ctx = OpContext(executor=dry, locks=LockManager())
    registry.invoke(
        "fs.delete", {"paths": [str(target).replace("\\", "/")]}, ctx
    ) if os.name == "posix" else None
    dry.remove(str(target))
    dry.write_stream(str(target), [b"changed"])
    assert target.read_text() == "original"
    assert ("remove", str(target)) in dry.mutations
