from __future__ import annotations

from django.db import models


class Setting(models.Model):
    """Runtime setting edited from the UI or ``edctl``; typed by ``settings_registry``."""

    key = models.CharField(max_length=100, primary_key=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.key
