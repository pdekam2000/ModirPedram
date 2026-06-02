from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class RuntimeDispatchRequest(BaseModel):
    skip_provider_execution: bool = False


class RuntimeActionResponse(BaseModel):
    success: bool
    accepted: bool = False
    async_mode: bool = False
    dispatch_mode: Optional[str] = None
    session_id: Optional[str] = None
    dispatch_id: Optional[str] = None
    state: Optional[str] = None
    execution_runtime: Optional[dict[str, Any]] = None
    reject_code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    api_version: str = "0.5.0"


class RuntimeJobStatus(BaseModel):
    active: bool = False
    phase: Optional[str] = None
    dispatch_id: Optional[str] = None
    accepted_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    elapsed_seconds: Optional[int] = None
    stale: bool = False
    stale_reason: Optional[str] = None
    stale_after_seconds: int = 120
    thread_alive: Optional[bool] = None
    provider_family: Optional[str] = None
    provider_execution_mode: Optional[str] = None


class RuntimeHeartbeatStatus(BaseModel):
    heartbeat_at: Optional[str] = None
    elapsed_seconds: Optional[int] = None
    stale: bool = False
    stale_reason: Optional[str] = None
    stale_after_seconds: int = 120
    clip_target: Optional[int] = None
    clip_observed: Optional[int] = None


class RuntimeProgressStatus(BaseModel):
    clip_target: Optional[int] = None
    clip_artifact_count: int = 0
    clip_validated_count: int = 0


class CategoryRuntimeSlotStatus(BaseModel):
    category_key: str
    category_name: str
    status: str = "planned"
    provider: Optional[str] = None
    artifact_count: int = 0
    error: Optional[Any] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    cost_estimate: Optional[Any] = None
    executable: bool = False
    future_router: Optional[str] = None


class RuntimeStatusResponse(BaseModel):
    session_id: str
    state: Optional[str] = None
    category_runtime_slots: list[dict[str, Any]] = Field(default_factory=list)
    runtime_state: Optional[str] = None
    provider_category: Optional[str] = None
    provider_resolved: Optional[str] = None
    provider_family: Optional[str] = None
    provider_execution_mode: Optional[str] = None
    learning_key: Optional[str] = None
    operations_phase: Optional[str] = None
    dispatch_id: Optional[str] = None
    dispatched_at: Optional[str] = None
    running_at: Optional[str] = None
    completed_at: Optional[str] = None
    clip_artifact_count: int = 0
    failure: Optional[dict[str, Any]] = None
    preflight: Optional[dict[str, Any]] = None
    cost_telemetry: Optional[dict[str, Any]] = None
    job: Optional[RuntimeJobStatus] = None
    heartbeat: Optional[RuntimeHeartbeatStatus] = None
    progress: Optional[RuntimeProgressStatus] = None
    execution_runtime: Optional[dict[str, Any]] = None
    api_version: str = "0.5.0"
