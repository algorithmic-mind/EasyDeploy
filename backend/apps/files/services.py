"""Upload bookkeeping and long-running file operations (§9.9)."""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
import shutil
from pathlib import Path
from typing import Any

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.agent_client import get_agent
from apps.core.conf import ed_path
from apps.core.errors import Conflict, NotFound, ValidationFailed
from apps.files.models import Upload
from apps.panel.services import get_setting

CHUNK_SIZE = 4 * 1024 * 1024
_BAD_NAME = re.compile(r"[\x00/\\]")


def clean_filename(name: str) -> str:
    name = name.strip()
    if not name or name in {".", ".."} or _BAD_NAME.search(name) or len(name.encode()) > 255:
        raise ValidationFailed(details={"filename": [str(_("Invalid file name."))]})
    return name


def upload_dir(upload: Upload) -> Path:
    return ed_path("UPLOAD_DIR") / upload.id.hex


def create_upload(
    user: Any, directory: str, filename: str, size: int, overwrite: bool = False
) -> Upload:
    max_bytes = int(get_setting("files.max_upload_mb")) * 1024 * 1024
    if size > max_bytes:
        raise ValidationFailed(
            details={"size": [str(_("The file is larger than the upload limit."))]}
        )
    destination = posixpath.join(directory, clean_filename(filename))
    upload = Upload.objects.create(
        user=user,
        destination=destination,
        size=size,
        chunk_size=CHUNK_SIZE,
        total_chunks=max(1, -(-size // CHUNK_SIZE)),
        overwrite=overwrite,
    )
    upload_dir(upload).mkdir(parents=True, exist_ok=True)
    return upload


def received_chunks(upload: Upload) -> list[int]:
    folder = upload_dir(upload)
    if not folder.exists():
        return []
    return sorted(int(p.stem) for p in folder.glob("*.part") if p.stem.isdigit())


def expected_chunk_size(upload: Upload, index: int) -> int:
    if index < upload.total_chunks - 1:
        return upload.chunk_size
    return upload.size - upload.chunk_size * (upload.total_chunks - 1)


def store_chunk(upload: Upload, index: int, data: bytes, sha256: str | None) -> None:
    if upload.completed_at:
        raise Conflict(_("This upload is already complete."), code="files.upload_complete")
    if not 0 <= index < upload.total_chunks:
        raise ValidationFailed(details={"index": [str(_("Chunk index out of range."))]})
    if len(data) != expected_chunk_size(upload, index):
        raise ValidationFailed(details={"chunk": [str(_("Unexpected chunk size."))]})
    if sha256 and hashlib.sha256(data).hexdigest() != sha256.lower():
        raise ValidationFailed(
            details={"chunk": [str(_("Chunk checksum mismatch."))]}, code="files.chunk_checksum"
        )
    folder = upload_dir(upload)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"{index:06d}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, folder / f"{index:06d}.part")


def complete_upload(upload: Upload, actor: str) -> dict[str, Any]:
    missing = sorted(set(range(upload.total_chunks)) - set(received_chunks(upload)))
    if missing:
        raise Conflict(
            _("Some chunks are missing."),
            code="files.upload_incomplete",
            details={"missing": missing[:50]},
        )
    result = get_agent().call(
        "fs.upload_finalize",
        {
            "upload_dir": str(upload_dir(upload)).replace("\\", "/"),
            "destination": upload.destination,
            "chunks": upload.total_chunks,
            "size": upload.size,
            "overwrite": upload.overwrite,
        },
        actor=actor,
        timeout=1800,
    )
    upload.completed_at = timezone.now()
    upload.save(update_fields=["completed_at", "updated_at"])
    shutil.rmtree(upload_dir(upload), ignore_errors=True)  # normally already removed by the agent
    return result


def cancel_upload(upload: Upload) -> None:
    shutil.rmtree(upload_dir(upload), ignore_errors=True)
    upload.delete()


def get_upload(user: Any, upload_id: str) -> Upload:
    upload = Upload.objects.filter(pk=upload_id, user=user).first()
    if upload is None:
        raise NotFound()
    return upload
