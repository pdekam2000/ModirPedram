"""Schemas for Topic Universe / SEO Title Bank API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TopicUniverseGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2)
    language_code: str | None = None
    platform: str = "youtube_shorts"
    audience_level: str = "general"
    niche_style: str = "general"
    title_target: int = Field(100, ge=1, le=200)
    use_live_trends: bool = True
    suggested_duration: int = Field(30, ge=5, le=600)


class TopicUniverseGenerateResponse(BaseModel):
    ok: bool = True
    message: str = ""
    result: dict[str, Any] = Field(default_factory=dict)


class TopicUniverseHandoffRequest(BaseModel):
    selected_title: str = Field(..., min_length=3)
    source_run_id: str | None = None
    duration_seconds: int = Field(30, ge=5, le=600)
    platform: str = "youtube_shorts"
    niche: str = "general"
    mood: str = "instructional"
    clip_length_preference: int | None = None


class TopicUniverseHandoffResponse(BaseModel):
    ok: bool = True
    message: str = ""
    selected_title: str = ""
    source_run_id: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class TopicUniverseOpenExportRequest(BaseModel):
    path: str | None = None


class TopicUniverseOpenExportResponse(BaseModel):
    ok: bool = True
    path: str = ""
    message: str = ""


class TopicUniversePreflightResponse(BaseModel):
    ok: bool = True
    trend_mode: str = "mock_fallback"
    live_trend_providers_ready: list[str] = Field(default_factory=list)
    openai_story_ready: bool = False
    recommended_mode: str = ""
    title_bank_ready: bool = True
    checks: dict[str, Any] = Field(default_factory=dict)
