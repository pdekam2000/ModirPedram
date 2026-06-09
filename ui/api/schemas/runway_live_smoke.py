"""Runway live smoke approval runtime API schemas (Phase H.5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunwayLiveSmokeStartRequest(BaseModel):
    story_idea: str = Field(min_length=1)
    project_id: str = "live_smoke_h"
    operator: str = "operator"
    simulate: bool = False
    clip_count: int = Field(default=1, ge=1, le=6)
    execution_mode: str = "FULL_AUTO"


class RunwayLiveSmokeActionRequest(BaseModel):
    operator: str = "operator"
    reason: str = ""


class RunwayLiveSmokeRuntimeResponse(BaseModel):
    ok: bool
    api_version: str | None = None
    approval_runtime_version: str | None = None
    message: str | None = None
    project_id: str | None = None
    simulate: bool | None = None
    active: bool | None = None
    snapshot: dict | None = None
    report: dict | None = None
    handoff_preview: dict | None = None
