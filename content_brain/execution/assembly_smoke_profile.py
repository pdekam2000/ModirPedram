"""
Phase 11J-19 — strict smoke-test caps for first real FFmpeg assembly runs.

Applied when ``triggered_by=operator_smoke_test`` (fail closed before subprocess).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.assembly_models import (
    AssemblyPlan,
    ROLE_CLIP,
    ROLE_NARRATION,
    ROLE_SUBTITLE_ASS,
    ROLE_SUBTITLE_SRT,
    ROLE_SUBTITLE_VTT,
)

SMOKE_PROFILE_VERSION = "11j19_v1"
SMOKE_MAX_VIDEO_CLIPS = 2
SMOKE_MAX_VOICE_SEGMENTS = 1
SMOKE_MAX_SUBTITLE_FILES = 1
SMOKE_MAX_DURATION_SECONDS = 15
SMOKE_MAX_OUTPUT_BYTES = 5_000_000
SMOKE_TIMEOUT_SECONDS = 120
SMOKE_SESSION_PREFIX = "exec_11j19_smoke_"
SMOKE_TRIGGER = "operator_smoke_test"

CODE_SMOKE_CAP_EXCEEDED = "ASSEMBLY_SMOKE_CAP_EXCEEDED"

_SUBTITLE_ROLES = frozenset({ROLE_SUBTITLE_ASS, ROLE_SUBTITLE_SRT, ROLE_SUBTITLE_VTT})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class AssemblySmokeCapsResult:
    allowed: bool
    code: str | None = None
    message: str = ""
    reject_reasons: list[str] = field(default_factory=list)
    caps: dict[str, int | float | str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "message": self.message,
            "reject_reasons": list(self.reject_reasons),
            "caps": dict(self.caps),
        }
        if self.code:
            payload["code"] = self.code
        return payload


def smoke_caps_snapshot() -> dict[str, int | float | str]:
    return {
        "max_video_clips": SMOKE_MAX_VIDEO_CLIPS,
        "max_voice_segments": SMOKE_MAX_VOICE_SEGMENTS,
        "max_subtitle_files": SMOKE_MAX_SUBTITLE_FILES,
        "max_duration_seconds": SMOKE_MAX_DURATION_SECONDS,
        "max_output_bytes": SMOKE_MAX_OUTPUT_BYTES,
        "timeout_seconds": SMOKE_TIMEOUT_SECONDS,
        "profile_version": SMOKE_PROFILE_VERSION,
    }


def is_smoke_trigger(triggered_by: str | None, session_id: str | None = None) -> bool:
    if str(triggered_by or "").strip() == SMOKE_TRIGGER:
        return True
    sid = str(session_id or "")
    return sid.startswith(SMOKE_SESSION_PREFIX)


def evaluate_assembly_smoke_caps(
    plan: AssemblyPlan | None,
    *,
    triggered_by: str = "",
    session_id: str | None = None,
    timeout_seconds: int | None = None,
) -> AssemblySmokeCapsResult:
    """Fail-closed smoke caps for operator_smoke_test runs."""
    caps = smoke_caps_snapshot()
    if not is_smoke_trigger(triggered_by, session_id):
        return AssemblySmokeCapsResult(allowed=True, caps=caps)

    if timeout_seconds is not None and int(timeout_seconds) > SMOKE_TIMEOUT_SECONDS:
        msg = f"Smoke timeout exceeds cap ({SMOKE_TIMEOUT_SECONDS}s)."
        return AssemblySmokeCapsResult(
            allowed=False,
            code=CODE_SMOKE_CAP_EXCEEDED,
            message=msg,
            reject_reasons=[msg],
            caps=caps,
        )

    if not isinstance(plan, AssemblyPlan):
        msg = "Smoke run requires a valid AssemblyPlan."
        return AssemblySmokeCapsResult(
            allowed=False,
            code=CODE_SMOKE_CAP_EXCEEDED,
            message=msg,
            reject_reasons=[msg],
            caps=caps,
        )

    clips = [a for a in plan.video_inputs if a.role == ROLE_CLIP and a.exists]
    narration = [a for a in plan.audio_inputs if a.role == ROLE_NARRATION and a.exists]
    subtitles = [
        a for a in plan.subtitle_inputs if a.role in _SUBTITLE_ROLES and a.exists and not a.is_manifest
    ]

    if len(clips) > SMOKE_MAX_VIDEO_CLIPS:
        msg = f"Smoke video clip count exceeds cap ({SMOKE_MAX_VIDEO_CLIPS})."
        return AssemblySmokeCapsResult(
            allowed=False,
            code=CODE_SMOKE_CAP_EXCEEDED,
            message=msg,
            reject_reasons=[msg],
            caps=caps,
        )
    if len(narration) > SMOKE_MAX_VOICE_SEGMENTS:
        msg = f"Smoke voice segment count exceeds cap ({SMOKE_MAX_VOICE_SEGMENTS})."
        return AssemblySmokeCapsResult(
            allowed=False,
            code=CODE_SMOKE_CAP_EXCEEDED,
            message=msg,
            reject_reasons=[msg],
            caps=caps,
        )
    if len(subtitles) > SMOKE_MAX_SUBTITLE_FILES:
        msg = f"Smoke subtitle file count exceeds cap ({SMOKE_MAX_SUBTITLE_FILES})."
        return AssemblySmokeCapsResult(
            allowed=False,
            code=CODE_SMOKE_CAP_EXCEEDED,
            message=msg,
            reject_reasons=[msg],
            caps=caps,
        )

    return AssemblySmokeCapsResult(allowed=True, message="Smoke caps satisfied.", caps=caps)


__all__ = [
    "SMOKE_PROFILE_VERSION",
    "SMOKE_MAX_VIDEO_CLIPS",
    "SMOKE_MAX_VOICE_SEGMENTS",
    "SMOKE_MAX_SUBTITLE_FILES",
    "SMOKE_MAX_DURATION_SECONDS",
    "SMOKE_MAX_OUTPUT_BYTES",
    "SMOKE_TIMEOUT_SECONDS",
    "SMOKE_SESSION_PREFIX",
    "SMOKE_TRIGGER",
    "CODE_SMOKE_CAP_EXCEEDED",
    "AssemblySmokeCapsResult",
    "smoke_caps_snapshot",
    "is_smoke_trigger",
    "evaluate_assembly_smoke_caps",
]
