from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class VoiceApproveRequest(BaseModel):
    request_live_tts: bool = False
    reason: str = ""
    ttl_minutes: Optional[int] = None
    approved_by: str = "local_user"


class VoiceRejectRequest(BaseModel):
    reason: str = ""
    rejected_by: str = "local_user"


class VoiceExpireRequest(BaseModel):
    reason: str = ""
    expired_by: str = "local_user"


class VoiceResetApprovalRequest(BaseModel):
    reason: str = ""
    reset_by: str = "local_user"
    clear_live_tts_request: bool = False


class VoiceApprovalActionResponse(BaseModel):
    success: bool
    session_id: str
    action: str
    message: str = ""
    code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    voice_slot: Optional[dict[str, Any]] = None
    guard_result: Optional[dict[str, Any]] = None
    panel_excerpt: Optional[dict[str, Any]] = None
    audit_event: Optional[dict[str, Any]] = None
    tts_executed: bool = False
    api_version: str = "0.6.0"
