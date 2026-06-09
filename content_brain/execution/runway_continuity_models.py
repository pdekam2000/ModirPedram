"""
Phase RUNWAY-STARTER-TO-VIDEO-D/E — Runway continuity plan and semi-auto models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.runway_image_generation_config import (
    DEFAULT_IMAGE_ASPECT_RATIO,
    DEFAULT_IMAGE_COUNT,
    DEFAULT_IMAGE_QUALITY,
)

DEFAULT_DURATION_SECONDS = 10
DEFAULT_MAX_WAIT_MINUTES_PER_CLIP = 20
DEFAULT_TARGET_PLATFORM = "shorts"
DEFAULT_ASPECT_RATIO = DEFAULT_IMAGE_ASPECT_RATIO
COMPLETION_RULE_EXPRESSION = "download_mp4_button_visible OR use_frame_button_visible"


@dataclass(frozen=True)
class StarterImagePlan:
    prompt: str
    aspect_ratio: str = DEFAULT_IMAGE_ASPECT_RATIO
    image_quality: str = DEFAULT_IMAGE_QUALITY
    image_count: int = DEFAULT_IMAGE_COUNT

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "aspect_ratio": self.aspect_ratio,
            "image_quality": self.image_quality,
            "image_count": self.image_count,
        }


@dataclass(frozen=True)
class VideoClipPlan:
    clip_index: int
    prompt: str
    duration_seconds: int = DEFAULT_DURATION_SECONDS
    aspect_ratio: str = DEFAULT_ASPECT_RATIO
    is_final: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "prompt": self.prompt,
            "duration_seconds": self.duration_seconds,
            "aspect_ratio": self.aspect_ratio,
            "is_final": self.is_final,
        }


@dataclass(frozen=True)
class RunwayContinuityPlan:
    project_id: str
    starter_image: StarterImagePlan
    clip_prompts: tuple[str, ...]
    target_platform: str = DEFAULT_TARGET_PLATFORM
    aspect_ratio: str = DEFAULT_ASPECT_RATIO
    duration_seconds: int = DEFAULT_DURATION_SECONDS
    image_quality: str = DEFAULT_IMAGE_QUALITY
    image_count: int = DEFAULT_IMAGE_COUNT
    max_wait_minutes_per_clip: int = DEFAULT_MAX_WAIT_MINUTES_PER_CLIP
    completion_rule: str = COMPLETION_RULE_EXPRESSION

    @property
    def starter_image_prompt(self) -> str:
        return self.starter_image.prompt

    @property
    def clips(self) -> tuple[VideoClipPlan, ...]:
        total = len(self.clip_prompts)
        return tuple(
            VideoClipPlan(
                clip_index=index,
                prompt=prompt,
                duration_seconds=self.duration_seconds,
                aspect_ratio=self.aspect_ratio,
                is_final=index == total,
            )
            for index, prompt in enumerate(self.clip_prompts, start=1)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "target_platform": self.target_platform,
            "aspect_ratio": self.aspect_ratio,
            "duration_seconds": self.duration_seconds,
            "image_quality": self.image_quality,
            "image_count": self.image_count,
            "starter_image_prompt": self.starter_image_prompt,
            "starter_image": self.starter_image.to_dict(),
            "clip_prompts": list(self.clip_prompts),
            "clips": [clip.to_dict() for clip in self.clips],
            "max_wait_minutes_per_clip": self.max_wait_minutes_per_clip,
            "completion_rule": self.completion_rule,
        }


@dataclass(frozen=True)
class RunwayContinuityStep:
    step_id: str
    phase: str
    action: str
    control_key: str | None = None
    simulated: bool = True
    manual_required: bool = False
    requires_operator_approval: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "action": self.action,
            "control_key": self.control_key,
            "simulated": self.simulated,
            "manual_required": self.manual_required,
            "requires_operator_approval": self.requires_operator_approval,
            "notes": self.notes,
        }


@dataclass
class RunwayDryRunResult:
    ok: bool
    plan: RunwayContinuityPlan
    steps: list[RunwayContinuityStep] = field(default_factory=list)
    controls_present: dict[str, str] = field(default_factory=dict)
    controls_missing: list[str] = field(default_factory=list)
    controls_invalid: list[dict[str, str]] = field(default_factory=list)
    controls_weak: list[dict[str, str]] = field(default_factory=list)
    safety_gates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan": self.plan.to_dict(),
            "step_count": len(self.steps),
            "steps": [step.to_dict() for step in self.steps],
            "controls_present": dict(self.controls_present),
            "controls_missing": list(self.controls_missing),
            "controls_invalid": list(self.controls_invalid),
            "controls_weak": list(self.controls_weak),
            "safety_gates": list(self.safety_gates),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


SEMI_AUTO_STATUS_IDLE = "idle"
SEMI_AUTO_STATUS_PREPARING = "preparing"
SEMI_AUTO_STATUS_AWAITING_APPROVAL = "awaiting_approval"
SEMI_AUTO_STATUS_WAITING_COMPLETION = "waiting_completion"
SEMI_AUTO_STATUS_MANUAL_HOLD = "manual_hold"
SEMI_AUTO_STATUS_COMPLETED = "completed"
SEMI_AUTO_STATUS_FAILED = "failed"

SEMI_AUTO_STEP_PENDING = "pending"
SEMI_AUTO_STEP_RUNNING = "running"
SEMI_AUTO_STEP_DONE = "done"
SEMI_AUTO_STEP_SKIPPED = "skipped"
SEMI_AUTO_STEP_BLOCKED = "blocked"


@dataclass(frozen=True)
class RunwayContinuityApprovalRecord:
    control_key: str
    step_id: str
    approved_by: str
    approved_at: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_key": self.control_key,
            "step_id": self.step_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "reason": self.reason,
        }


@dataclass
class RunwaySemiAutoStepResult:
    step_id: str
    action: str
    control_key: str | None = None
    status: str = SEMI_AUTO_STEP_PENDING
    executed: bool = False
    simulated: bool = False
    requires_operator_approval: bool = False
    approval_granted: bool = False
    error: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "control_key": self.control_key,
            "status": self.status,
            "executed": self.executed,
            "simulated": self.simulated,
            "requires_operator_approval": self.requires_operator_approval,
            "approval_granted": self.approval_granted,
            "error": self.error,
            "notes": self.notes,
        }


@dataclass
class RunwaySemiAutoSession:
    plan: RunwayContinuityPlan
    steps: list[RunwayContinuityStep]
    current_step_index: int = 0
    status: str = SEMI_AUTO_STATUS_IDLE
    approvals: dict[str, RunwayContinuityApprovalRecord] = field(default_factory=dict)
    step_results: list[RunwaySemiAutoStepResult] = field(default_factory=list)
    awaiting_control_key: str | None = None
    awaiting_step_id: str | None = None
    completion_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "status": self.status,
            "current_step_index": self.current_step_index,
            "step_count": len(self.steps),
            "awaiting_control_key": self.awaiting_control_key,
            "awaiting_step_id": self.awaiting_step_id,
            "approvals": {key: rec.to_dict() for key, rec in self.approvals.items()},
            "step_results": [item.to_dict() for item in self.step_results],
            "completion_signals": list(self.completion_signals),
        }


@dataclass
class RunwaySemiAutoResult:
    ok: bool
    session: RunwaySemiAutoSession
    safety_gates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session": self.session.to_dict(),
            "safety_gates": list(self.safety_gates),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
