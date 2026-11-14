"""Resumable chunked uploads (§9.9). Chunks live in ``EASYDEPLOY['UPLOAD_DIR']/<id>/``."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Upload(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    destination = models.CharField(max_length=4096)  # full target path (directory + file name)
    size = models.BigIntegerField()
    chunk_size = models.PositiveIntegerField()
    total_chunks = models.PositiveIntegerField()
    overwrite = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"upload {self.destination} ({self.size} B)"
