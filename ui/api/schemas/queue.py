from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class QueueActionResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    state: Optional[str] = None
    queue_item: Optional[dict[str, Any]] = None
    reject_code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)


class QueuePeekResponse(BaseModel):
    item: Optional[dict[str, Any]] = None


class QueueStatusResponse(BaseModel):
    depth: int = 0
    max_depth: int = 100
    oldest_enqueued_at: Optional[str] = None
    bands: dict[str, int] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)
