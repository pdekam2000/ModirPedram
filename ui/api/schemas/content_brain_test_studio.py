"""Schemas for Content Brain E2E Micro Test Studio API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContentBrainTestStudioRunRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    duration_seconds: int = Field(30, ge=5, le=600)
    platform: str = "youtube_shorts"
    niche: str = "general"
    mood: str = "emotional"
    clip_length_preference: int | None = None


class ContentBrainTestStudioRunResponse(BaseModel):
    ok: bool = True
    message: str = ""
    result: dict[str, Any] = Field(default_factory=dict)


class ContentBrainTestStudioPreflightResponse(BaseModel):
    ok: bool = True
    trend_mode: str = "mock_fallback"
    live_trend_providers_ready: list[str] = Field(default_factory=list)
    openai_story_ready: bool = False
    recommended_mode: str = ""
    checks: dict[str, Any] = Field(default_factory=dict)


class ContentBrainTestStudioOpenExportRequest(BaseModel):
    path: str | None = None


class ContentBrainTestStudioOpenExportResponse(BaseModel):
    ok: bool = True
    path: str = ""
    message: str = ""
