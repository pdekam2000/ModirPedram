"""Voice live TTS run API schemas (Phase 11H-2a/2c)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class VoiceRunRequest(BaseModel):
    triggered_by: str = "local_user"
    reason: str = ""
    force_retry: bool = False
    provider_mode: Literal["mock", "live_elevenlabs"] = "mock"
    confirm_live_tts: bool = False

    @model_validator(mode="after")
    def live_requires_confirm(self) -> "VoiceRunRequest":
        if self.provider_mode == "live_elevenlabs" and not self.confirm_live_tts:
            raise ValueError("confirm_live_tts must be true when provider_mode is live_elevenlabs")
        return self


class VoiceRunResponse(BaseModel):
    success: bool
    session_id: str
    status: str
    message: str = ""
    code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    voice_slot: Optional[dict[str, Any]] = None
    guard_result: Optional[dict[str, Any]] = None
    manifest_path: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    panel_excerpt: Optional[dict[str, Any]] = None
    audit_event: Optional[dict[str, Any]] = None
    provider_mode: str = "mock"
    tts_executed: bool = False
    real_provider_called: bool = False
    video_mutated: bool = False
    api_version: str = "0.7.1"
