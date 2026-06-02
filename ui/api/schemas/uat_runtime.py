"""UAT runtime API schemas (Phase 12D)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from content_brain.execution.uat_runtime_profile import (
    UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS,
    UAT_MAX_DURATION_SECONDS,
    normalize_video_provider,
    uat_default_duration_seconds,
)


UatPlatform = Literal["youtube_shorts", "tiktok", "instagram_reels"]
UatVideoProvider = Literal["runway_browser", "hailuo_browser", "mock"]
UatVoiceProvider = Literal["elevenlabs", "mock"]
UatRunStatus = Literal["running", "completed", "failed", "cancelled", "unknown"]


class UatRunRequest(BaseModel):
    topic: str
    platform: UatPlatform = "youtube_shorts"
    duration_seconds: int | None = Field(
        default=None,
        ge=UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS,
        le=UAT_MAX_DURATION_SECONDS,
    )
    video_provider: UatVideoProvider = "runway_browser"
    voice_provider: UatVoiceProvider = "elevenlabs"
    confirm_real_voice: bool = False
    confirm_real_video: bool = False
    confirm_real_assembly: bool = False
    open_folder: bool = False
    niche: str = "general"

    @model_validator(mode="before")
    @classmethod
    def apply_provider_default_duration(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("duration_seconds") is None:
            provider = normalize_video_provider(str(data.get("video_provider") or "runway_browser"))
            data = {**data, "duration_seconds": uat_default_duration_seconds(provider)}
        return data

    @field_validator("topic")
    @classmethod
    def topic_non_empty(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("topic is required")
        return cleaned


class UatProgressEntry(BaseModel):
    timestamp: str
    stage: str
    level: str = "info"
    message: str = ""


class RunwayControlledPageObs(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_index: Optional[int] = None
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    is_runway_url: Optional[bool] = None


class RunwayBrowserObsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    step: Optional[str] = None
    step_updated_at: Optional[str] = None
    step_detail: Optional[str] = None
    clip_index: Optional[int] = None
    controlled_page: Optional[RunwayControlledPageObs] = None
    open_pages: list[dict[str, Any]] = Field(default_factory=list)
    failure_message: Optional[str] = None


class UatVideoRuntimeObs(BaseModel):
    model_config = ConfigDict(extra="allow")

    state: Optional[str] = None
    provider: Optional[str] = None
    runway_step: Optional[str] = None
    controlled_tab_url: Optional[str] = None
    controlled_tab_title: Optional[str] = None
    is_runway_url: Optional[bool] = None
    open_pages: list[dict[str, Any]] = Field(default_factory=list)


class UatRunResponse(BaseModel):
    session_id: str
    status: UatRunStatus
    current_stage: Optional[str] = None
    failed_stage: Optional[str] = None
    stages: dict[str, Any] = Field(default_factory=dict)
    progress_log: list[UatProgressEntry] = Field(default_factory=list)
    artifact_folder: Optional[str] = None
    final_video_path: Optional[str] = None
    report_path: Optional[str] = None
    review_template_path: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    flags_active: dict[str, bool] = Field(default_factory=dict)
    api_version: str = "12d_v1"
    runway_browser_obs: RunwayBrowserObsPayload = Field(default_factory=RunwayBrowserObsPayload)
    video_runtime: UatVideoRuntimeObs = Field(default_factory=UatVideoRuntimeObs)


class UatReviewRequest(BaseModel):
    story_quality_score: int = Field(ge=0, le=10)
    visual_quality_score: int = Field(ge=0, le=10)
    voice_quality_score: int = Field(ge=0, le=10)
    subtitle_quality_score: int = Field(ge=0, le=10)
    continuity_score: int = Field(ge=0, le=10)
    overall_quality_score: int = Field(ge=0, le=10)
    comments: str = ""
    publishable: bool = False
    submitted_by: str = "operator_uat"


class UatReviewResponse(BaseModel):
    success: bool = True
    session_id: str
    review_path: str
    submitted_at: str
    api_version: str = "12d_v1"
