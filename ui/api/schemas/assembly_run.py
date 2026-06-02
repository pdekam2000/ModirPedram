"""Assembly run API schemas (Phase 11J-19)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AssemblyRunRequest(BaseModel):
    dry_run: bool = True
    confirm_real_assembly: bool = False
    overwrite: bool = False
    timeout_seconds: int = 120
    triggered_by: str = "operator"
    reason: str = ""


class AssemblyRunResponse(BaseModel):
    session_id: str
    status: str
    success: bool = False
    message: str = ""
    code: Optional[str] = None
    reject_reasons: list[str] = Field(default_factory=list)
    assembly_slot: Optional[dict[str, Any]] = None
    guard_result: Optional[dict[str, Any]] = None
    validation_status: str = "FAILED"
    assembly_mode: Optional[str] = None
    subtitle_mode: Optional[str] = None
    planned_steps: list[dict[str, Any]] = Field(default_factory=list)
    expected_output: Optional[str] = None
    input_summary: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)

    output_created: bool = False
    real_assembly_executed: bool = False
    video_mutated: bool = False
    voice_mutated: bool = False
    subtitle_mutated: bool = False

    api_version: str = "0.7.5"
