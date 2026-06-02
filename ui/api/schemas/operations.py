from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionEligibilityDTO(BaseModel):
    allowed: bool
    reason: str


class OperationsEligibilityResponse(BaseModel):
    session_id: str
    current_state: str
    actions: dict[str, ActionEligibilityDTO]
    api_version: str = "0.6.0"


class OperationsActionRequest(BaseModel):
    reason: str = ""
    actor: str = "operator"


class OperationsActionResponse(BaseModel):
    ok: bool
    session_id: str
    action: str
    previous_state: Optional[str] = None
    next_state: Optional[str] = None
    audit_event_id: Optional[str] = None
    message: str = ""
    code: Optional[str] = None
    current_state: Optional[str] = None
    reason: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    api_version: str = "0.6.0"


class OperationsActionErrorResponse(BaseModel):
    ok: bool = False
    code: str
    action: str
    session_id: Optional[str] = None
    current_state: Optional[str] = None
    reason: str
    reject_reasons: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)
