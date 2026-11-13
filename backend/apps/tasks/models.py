"""Tracked background work (§5.4)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        FAILED = "failed"
        CANCELLED = "cancelled"

    ACTIVE = (Status.PENDING, Status.RUNNING)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=100, db_index=True)  # e.g. "panel.diagnostics"
    title_key = models.CharField(max_length=150)  # i18n key, rendered by the UI
    title_params = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    progress = models.PositiveSmallIntegerField(default=0)
    progress_message = models.CharField(max_length=300, blank=True)
    resource_type = models.CharField(max_length=50, blank=True)
    resource_id = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    celery_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    log_path = models.CharField(max_length=500, blank=True)
    result = models.JSONField(null=True, blank=True)
    error = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["resource_type", "resource_id"])]

    def __str__(self) -> str:
        return f"{self.kind} {self.id} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE

    @property
    def group_name(self) -> str:
        return f"task.{self.id}"
