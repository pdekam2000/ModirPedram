from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AssemblyApproveRequest(BaseModel):
    request_real_assembly: bool = True
    reason: str = ""
    ttl_minutes: Optional[int] = None
    approved_by: str = "local_user"


class AssemblyRejectRequest(BaseModel):
    reason: str = ""
    rejected_by: str = "local_user"


class AssemblyExpireRequest(BaseModel):
    reason: str = ""
    expired_by: str = "local_user"


class AssemblyResetApprovalRequest(BaseModel):
    reason: str = ""
    reset_by: str = "local_user"


class AssemblyApprovalActionResponse(BaseModel):
    success: bool
    session_id: str
    action: str
    message: str = ""
    code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    assembly_slot: Optional[dict[str, Any]] = None
    guard_result: Optional[dict[str, Any]] = None
    panel_excerpt: Optional[dict[str, Any]] = None
    audit_event: Optional[dict[str, Any]] = None
    real_assembly_executed: bool = False
    api_version: str = "0.7.5"
