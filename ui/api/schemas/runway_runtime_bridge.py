"""Runway Runtime Bridge API schemas (Phase 5A/5B — AI Content Factory)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from content_brain.execution.runway_runtime_bridge_adapter import (
    DEFAULT_CLIP_DURATION_SECONDS,
    KLING_SUPPORTED_MODEL,
    PROVIDER_KLING,
    SUPPORTED_ASPECT_RATIO,
    SUPPORTED_PROVIDER,
    SUPPORTED_PROVIDERS,
)


class RunwayPromptPackageDTO(BaseModel):
    story_idea: str = Field(min_length=1)
    starter_image_prompt: str = Field(min_length=1)
    clip_prompts: list[str | dict[str, Any]] = Field(min_length=1)
    continuity_anchors: dict[str, str] = Field(default_factory=dict)
    clip_duration_seconds: int = Field(default=DEFAULT_CLIP_DURATION_SECONDS, ge=1)
    run_id: str = ""


class RunwayRuntimeGenerateRequest(BaseModel):
    project_id: str = Field(min_length=1)
    provider: str = Field(default=SUPPORTED_PROVIDER)
    model: str = ""
    aspect_ratio: Literal["9:16"] = SUPPORTED_ASPECT_RATIO
    duration_seconds: int = Field(ge=10)
    prompt_package: RunwayPromptPackageDTO

    @field_validator("provider")
    @classmethod
    def _provider_must_be_supported(cls, value: str) -> str:
        normalized = str(value or SUPPORTED_PROVIDER).strip().lower()
        if normalized not in SUPPORTED_PROVIDERS:
            raise ValueError(f"provider must be one of {sorted(SUPPORTED_PROVIDERS)!r}")
        return normalized

    @model_validator(mode="after")
    def _validate_provider_model(self) -> RunwayRuntimeGenerateRequest:
        if self.provider == PROVIDER_KLING:
            model = str(self.model or "").strip().lower()
            if model != KLING_SUPPORTED_MODEL:
                raise ValueError(
                    f'provider="{PROVIDER_KLING}" requires model="{KLING_SUPPORTED_MODEL}"'
                )
        return self


class RunwayRuntimeGenerateResponse(BaseModel):
    ok: bool
    run_id: str | None = None
    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str | None = None
    clip_count: int | None = None
    aspect_ratio: str | None = None
    poll_url: str | None = None
    message: str | None = None
    error_code: str | None = None
    bridge_version: str | None = None
    adapter_version: str | None = None


class RunwayRuntimeStatusResponse(BaseModel):
    ok: bool
    run_id: str | None = None
    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str | None = None
    active: bool | None = None
    clip_count: int | None = None
    aspect_ratio: str | None = None
    clips_completed: int | None = None
    downloaded_file_paths: list[str] | None = None
    download_dir: str | None = None
    report: dict[str, Any] | None = None
    errors: list[str] | None = None
    message: str | None = None
    error_code: str | None = None
