from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.terminal.models import Snippet


class SnippetSerializer(serializers.ModelSerializer[Snippet]):
    command = serializers.CharField(max_length=10000, trim_whitespace=False)

    class Meta:
        model = Snippet
        fields = ["id", "name", "command", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_command(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("The command must not be empty.")
        return value


class TerminalCheckSerializer(serializers.Serializer[Any]):
    sudo_until = serializers.FloatField()
    idle_minutes = serializers.IntegerField()
