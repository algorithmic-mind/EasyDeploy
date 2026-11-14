"""File manager endpoints under ``/api/v1/files/`` (§9.9); host access goes through the agent."""

from __future__ import annotations

import posixpath
from typing import Any
from urllib.parse import quote

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.parsers import BaseParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import RequireSudo
from apps.audit.services import record
from apps.core.agent_client import get_agent
from apps.core.permissions import IsPanelAdmin
from apps.files import services
from apps.files.tasks import run_agent_op
from apps.tasks.services import start_task
from easydeploy_agent.fs_safety import is_protected

Dict = inline_serializer("FilesResult", {"result": serializers.DictField()})
TaskAccepted = inline_serializer("FilesTaskAccepted", {"task_id": serializers.UUIDField()})


def path_field() -> serializers.CharField:
    # DRF binds field instances to one serializer, so every use needs a fresh field.
    return serializers.CharField(max_length=4096)


class OctetStreamParser(BaseParser):
    media_type = "application/octet-stream"

    def parse(
        self, stream: Any, media_type: str | None = None, parser_context: Any = None
    ) -> Any:
        return bytes(stream.read()) if stream is not None else b""


def _actor(request: Request) -> str:
    return str(request.user.pk)


def _agent(request: Request, op: str, params: dict[str, Any], **kw: Any) -> dict[str, Any]:
    return get_agent().call(op, params, actor=_actor(request), **kw)


def _audit(request: Request, action: str, **details: Any) -> None:
    record(f"files.{action}", request=request._request, resource_type="path", details=details)


class FilesView(APIView):
    api_module = "files"


# ------------------------------------------------------------------ browsing and editing
class ListView(FilesView):
    @extend_schema(
        parameters=[OpenApiParameter("path", str, required=True), OpenApiParameter("hidden", bool)],
        responses=Dict,
    )
    def get(self, request: Request) -> Response:
        path = request.query_params.get("path", "/")
        hidden = request.query_params.get("hidden", "true") != "false"
        result = _agent(request, "fs.list", {"path": path, "show_hidden": hidden})
        for entry in result["entries"]:
            entry["protected"] = is_protected(entry["path"])
        result["protected"] = is_protected(result["path"])
        return Response(result)


class ContentSerializer(serializers.Serializer[Any]):
    path = path_field()
    content = serializers.CharField(
        allow_blank=True, trim_whitespace=False, max_length=5 * 1024 * 1024
    )
    expected_sha256 = serializers.RegexField(r"^[0-9a-f]{64}$", required=False)
    create_only = serializers.BooleanField(default=False)


class ContentView(FilesView):
    @extend_schema(parameters=[OpenApiParameter("path", str, required=True)], responses=Dict)
    def get(self, request: Request) -> Response:
        return Response(_agent(request, "fs.read", {"path": request.query_params.get("path", "")}))

    @extend_schema(request=ContentSerializer, responses=Dict)
    def put(self, request: Request) -> Response:
        data = ContentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        params = {k: v for k, v in data.validated_data.items() if v not in (None, "")}
        params["content"] = data.validated_data["content"]
        result = _agent(request, "fs.write", params)
        _audit(request, "write", path=result["path"], size=result["size"])
        return Response(result)


class PathSerializer(serializers.Serializer[Any]):
    path = path_field()


class MkdirView(FilesView):
    @extend_schema(request=PathSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = PathSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.mkdir", {"path": data.validated_data["path"]})
        _audit(request, "mkdir", path=data.validated_data["path"])
        return Response(result, status=status.HTTP_201_CREATED)


class TransferSerializer(serializers.Serializer[Any]):
    sources = serializers.ListField(child=path_field(), min_length=1, max_length=1000)
    destination = path_field()
    rename = serializers.BooleanField(default=False)
    overwrite = serializers.BooleanField(default=False)
    confirm_protected = serializers.BooleanField(default=False)


class MoveView(FilesView):
    @extend_schema(request=TransferSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = TransferSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.move", dict(data.validated_data), timeout=600)
        _audit(request, "move", **data.validated_data)
        return Response(result)


class DeleteSerializer(serializers.Serializer[Any]):
    paths = serializers.ListField(child=path_field(), min_length=1, max_length=1000)
    confirm_protected = serializers.BooleanField(default=False)


class DeleteView(FilesView):
    """Move to the recycle bin (restorable)."""

    @extend_schema(request=DeleteSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = DeleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.delete", dict(data.validated_data), timeout=600)
        _audit(request, "delete", paths=data.validated_data["paths"])
        return Response(result)


class ChmodSerializer(serializers.Serializer[Any]):
    paths = serializers.ListField(child=path_field(), min_length=1, max_length=1000)
    mode = serializers.RegexField(r"^[0-7]{3,4}$")
    recursive = serializers.BooleanField(default=False)
    confirm_protected = serializers.BooleanField(default=False)


class ChmodView(FilesView):
    @extend_schema(request=ChmodSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = ChmodSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.chmod", dict(data.validated_data), timeout=600)
        _audit(request, "chmod", **data.validated_data)
        return Response(result)


class ChownSerializer(serializers.Serializer[Any]):
    paths = serializers.ListField(child=path_field(), min_length=1, max_length=1000)
    user = serializers.RegexField(r"^[a-z_][a-z0-9_-]{0,31}$")
    group = serializers.RegexField(r"^[a-z_][a-z0-9_-]{0,31}$")
    recursive = serializers.BooleanField(default=False)
    confirm_protected = serializers.BooleanField(default=False)


class ChownView(FilesView):
    @extend_schema(request=ChownSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = ChownSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.chown", dict(data.validated_data), timeout=600)
        _audit(request, "chown", **data.validated_data)
        return Response(result)


class SymlinkSerializer(serializers.Serializer[Any]):
    target = path_field()
    link = path_field()


class SymlinkView(FilesView):
    @extend_schema(request=SymlinkSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = SymlinkSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.symlink", dict(data.validated_data))
        _audit(request, "symlink", **data.validated_data)
        return Response(result, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------------ recycle bin
class RecycleView(FilesView):
    @extend_schema(responses=Dict)
    def get(self, request: Request) -> Response:
        return Response(_agent(request, "fs.recycle_list", {}))


class RecycleIdsSerializer(serializers.Serializer[Any]):
    ids = serializers.ListField(child=serializers.RegexField(r"^[0-9a-f]{32}$"), default=list)
    all = serializers.BooleanField(default=False)


class RecycleRestoreView(FilesView):
    @extend_schema(request=RecycleIdsSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = RecycleIdsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(request, "fs.recycle_restore", dict(data.validated_data), timeout=600)
        _audit(request, "restore", **data.validated_data)
        return Response(result)


class RecyclePurgeView(FilesView):
    """Permanent deletion: sudo mode (§9.9)."""

    permission_classes = [IsAuthenticated, IsPanelAdmin, RequireSudo]

    @extend_schema(request=RecycleIdsSerializer, responses=Dict)
    def post(self, request: Request) -> Response:
        data = RecycleIdsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = _agent(
            request, "fs.recycle_purge", dict(data.validated_data), sudo=True, timeout=3600
        )
        _audit(request, "purge", **data.validated_data)
        return Response(result)


# ------------------------------------------------------------------ long operations (tasks)
class CompressSerializer(serializers.Serializer[Any]):
    paths = serializers.ListField(child=path_field(), min_length=1, max_length=1000)
    destination = path_field()
    format = serializers.ChoiceField(choices=["zip", "tar.gz", "tar.xz", "tar.zst"], default="zip")


class ExtractSerializer(serializers.Serializer[Any]):
    archive = path_field()
    destination = path_field()


class FetchSerializer(serializers.Serializer[Any]):
    url = serializers.RegexField(r"^https?://\S+$", max_length=2000)
    destination = path_field()


class SearchSerializer(serializers.Serializer[Any]):
    # Not "root": that name is a property of every DRF field.
    directory = path_field()
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    content = serializers.CharField(required=False, allow_blank=True, max_length=200)


TASK_OPS: dict[str, tuple[str, type[serializers.Serializer[Any]]]] = {
    "compress": ("fs.compress", CompressSerializer),
    "extract": ("fs.extract", ExtractSerializer),
    "fetch": ("fs.fetch", FetchSerializer),
    "copy": ("fs.copy", TransferSerializer),
    "du": ("fs.du", PathSerializer),
    "search": ("fs.search", SearchSerializer),
}


class TaskOpView(FilesView):
    """Starts a long file operation as a Task and returns 202 {task_id}."""

    @extend_schema(request=None, responses={202: TaskAccepted})
    def post(self, request: Request, action: str) -> Response:
        if action not in TASK_OPS:
            from apps.core.errors import NotFound

            raise NotFound()
        op, serializer_cls = TASK_OPS[action]
        data = serializer_cls(data=request.data)
        data.is_valid(raise_exception=True)
        params = {k: v for k, v in data.validated_data.items() if v not in (None, "")}
        if action == "search":
            params["root"] = params.pop("directory")
        task = start_task(
            run_agent_op,
            kind=f"files.{action}",
            title_key=f"files.tasks.{action}",
            title_params={
                "path": str(
                    params.get("destination") or params.get("path") or params.get("root") or ""
                )
            },
            user=request.user,
            kwargs={"op": op, "params": params, "actor": _actor(request)},
        )
        if action not in {"du", "search"}:
            _audit(request, action, **params)
        return Response({"task_id": str(task.id)}, status=status.HTTP_202_ACCEPTED)


# ------------------------------------------------------------------ download
class DownloadView(FilesView):
    @extend_schema(
        parameters=[OpenApiParameter("path", str, required=True)],
        responses={(200, "application/octet-stream"): bytes},
    )
    def get(self, request: Request) -> StreamingHttpResponse:
        path = request.query_params.get("path", "")
        chunks, size = get_agent().download(path, actor=_actor(request))
        name = posixpath.basename(path) or "download"
        response = StreamingHttpResponse(chunks, content_type="application/octet-stream")
        response["Content-Length"] = str(size)
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
        response["X-Content-Type-Options"] = "nosniff"
        return response


# ------------------------------------------------------------------ uploads
class UploadCreateSerializer(serializers.Serializer[Any]):
    directory = path_field()
    filename = serializers.CharField(max_length=255)
    size = serializers.IntegerField(min_value=0)
    overwrite = serializers.BooleanField(default=False)


UploadStatus = inline_serializer(
    "UploadStatus",
    {
        "id": serializers.UUIDField(),
        "destination": serializers.CharField(),
        "size": serializers.IntegerField(),
        "chunk_size": serializers.IntegerField(),
        "total_chunks": serializers.IntegerField(),
        "received": serializers.ListField(child=serializers.IntegerField()),
        "completed": serializers.BooleanField(),
    },
)


def _status(upload: services.Upload) -> dict[str, Any]:
    return {
        "id": str(upload.id),
        "destination": upload.destination,
        "size": upload.size,
        "chunk_size": upload.chunk_size,
        "total_chunks": upload.total_chunks,
        "received": services.received_chunks(upload),
        "completed": upload.completed_at is not None,
    }


class UploadCreateView(FilesView):
    @extend_schema(request=UploadCreateSerializer, responses={201: UploadStatus})
    def post(self, request: Request) -> Response:
        data = UploadCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        upload = services.create_upload(request.user, **data.validated_data)
        return Response(_status(upload), status=status.HTTP_201_CREATED)


class UploadDetailView(FilesView):
    @extend_schema(responses=UploadStatus)
    def get(self, request: Request, upload_id: str) -> Response:
        return Response(_status(services.get_upload(request.user, upload_id)))

    @extend_schema(responses={204: None})
    def delete(self, request: Request, upload_id: str) -> Response:
        services.cancel_upload(services.get_upload(request.user, upload_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadChunkView(FilesView):
    parser_classes = [OctetStreamParser, JSONParser]

    @extend_schema(
        request={"application/octet-stream": bytes},
        parameters=[OpenApiParameter("X-Chunk-SHA256", str, OpenApiParameter.HEADER)],
        responses={204: None},
    )
    def put(self, request: Request, upload_id: str, index: int) -> Response:
        upload = services.get_upload(request.user, upload_id)
        body = request.data if isinstance(request.data, bytes) else b""
        services.store_chunk(upload, index, body, request.headers.get("X-Chunk-SHA256"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadCompleteView(FilesView):
    @extend_schema(request=None, responses=Dict)
    def post(self, request: Request, upload_id: str) -> Response:
        upload = services.get_upload(request.user, upload_id)
        result = services.complete_upload(upload, _actor(request))
        _audit(request, "upload", path=upload.destination, size=upload.size)
        return Response(result)
