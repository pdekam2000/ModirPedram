"""Subtitle run API schemas (Phase 11I-8)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SubtitleRunRequest(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["srt", "ass", "vtt"])
    timing_strategy: str = "auto"
    overwrite: bool = False
    language: str = "auto"
    triggered_by: str = "operator"
    force_retry: bool = False


class SubtitleRunResponse(BaseModel):
    success: bool
    session_id: str
    status: str
    message: str = ""
    code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    subtitle_slot: Optional[dict[str, Any]] = None
    guard_result: Optional[dict[str, Any]] = None
    formats_written: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    manifest_path: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None
    cue_count: int = 0
    validation_status: str = "invalid"
    source_type: Optional[str] = None
    timing_strategy: Optional[str] = None
    subtitles_executed: bool = False
    real_provider_called: bool = False
    video_mutated: bool = False
    voice_mutated: bool = False
    api_version: str = "0.7.3"
