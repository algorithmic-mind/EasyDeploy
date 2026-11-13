from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for all op params/results: unknown fields are rejected, instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Empty(StrictModel):
    pass


class ErrorBody(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = {}
