"""
Phase 11H-2a/2c — eligibility policy for POST /voice/run.

Pure policy — never executes TTS or mutates sessions.
Live runtime execution remains disabled in 11H-2c.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_brain.execution.category_runtime_compat import STATUS_RUNNING
from content_brain.execution.provider_categories import CATEGORY_VOICE
from content_brain.execution.voice_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_CREDENTIALS_MISSING,
    BLOCK_LIVE_TTS_NOT_REQUESTED,
    BLOCK_NO_NARRATION,
    BLOCK_OPERATIONS_CANCELLED,
    BLOCK_PREFLIGHT_NOT_READY,
    BLOCK_VOICE_APPROVAL_REJECTED,
    BLOCK_VOICE_APPROVAL_REQUIRED,
    BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED,
    BLOCK_VOICE_COST_LIMIT_EXCEEDED,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_REJECTED,
    TIMESTAMP_FORMAT,
    can_run_live_voice_tts,
)
from content_brain.execution.voice_live_tts_safety_caps import (
    MAX_CHARACTERS_PER_RUN,
    MAX_ESTIMATED_COST_USD,
    MAX_SEGMENTS_PER_RUN,
)

ACTION_RUN = "run_voice_tts"

CODE_SESSION_ARCHIVED = "SESSION_ARCHIVED"
CODE_VOICE_SLOT_MISSING = "VOICE_SLOT_MISSING"
CODE_PROVIDER_NOT_SUPPORTED = "PROVIDER_NOT_SUPPORTED"
CODE_JOB_ALREADY_ACTIVE = "JOB_ALREADY_ACTIVE"
CODE_INVALID_VOICE_STATE = "INVALID_VOICE_STATE"
CODE_PRECONDITION_FAILED = "VOICE_RUN_PRECONDITION_FAILED"
CODE_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
CODE_APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
CODE_PRECKECK_FAILED = "PRECHECK_FAILED"
CODE_CANCELLED = "CANCELLED"
CODE_LIVE_TTS_DISABLED = "LIVE_TTS_DISABLED"
CODE_LIVE_TTS_NOT_CONFIRMED = "LIVE_TTS_NOT_CONFIRMED"
CODE_ESTIMATES_MISSING = "ESTIMATES_MISSING"

PROVIDER_MODE_MOCK = "mock"
PROVIDER_MODE_LIVE = "live_elevenlabs"

# Hard gate — live /voice/run execution not approved until 11H-2d.
LIVE_RUNTIME_EXECUTION_APPROVED = False

SUPPORTED_PROVIDERS = frozenset({"elevenlabs", "mock_elevenlabs"})

RUNNABLE_STATUSES = frozenset({"pending", "failed", "cancelled", "planned"})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" UTC", "")
    for fmt in (TIMESTAMP_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _session_archived(session: dict[str, Any]) -> bool:
    return bool(_dict(session.get("operations_control")).get("archived"))


def _session_cancel_requested(session: dict[str, Any]) -> bool:
    runtime = _dict(session.get("execution_runtime"))
    if _dict(runtime.get("operations_control")).get("cancel_requested"):
        return True
    return bool(_dict(session.get("operations_control")).get("cancel_requested"))


def _narration_skipped(voice_slot: dict[str, Any]) -> bool:
    adapter = _dict(voice_slot.get("narration_adapter"))
    if adapter.get("skipped"):
        return True
    if str(voice_slot.get("status") or "").lower() == "skipped":
        return True
    segment_count = int(voice_slot.get("segment_count") or adapter.get("segment_count") or 0)
    return segment_count <= 0


def _credentials_missing(voice_slot: dict[str, Any]) -> bool:
    error = _dict(voice_slot.get("error"))
    if str(error.get("code") or "").upper() == "CREDENTIALS_MISSING":
        return True
    preflight = _dict(voice_slot.get("voice_preflight"))
    return str(preflight.get("code") or "").upper() == "CREDENTIALS_MISSING"


def _preflight_ready(voice_slot: dict[str, Any]) -> bool:
    return bool(_dict(voice_slot.get("voice_preflight")).get("ready"))


def _provider_supported(voice_slot: dict[str, Any]) -> bool:
    provider = str(voice_slot.get("provider") or "elevenlabs").lower()
    return provider in SUPPORTED_PROVIDERS


def _effective_approval_state(voice_slot: dict[str, Any]) -> str:
    approval = _dict(voice_slot.get("approval"))
    state = str(approval.get("approval_state") or "not_required").lower()
    if state != STATE_APPROVED:
        return state
    expires_at = _parse_timestamp(approval.get("approval_expires_at"))
    if expires_at and datetime.utcnow() >= expires_at:
        return STATE_EXPIRED
    return state


def _map_guard_code(code: str) -> str:
    mapping = {
        BLOCK_VOICE_APPROVAL_REQUIRED: CODE_APPROVAL_REQUIRED,
        BLOCK_VOICE_APPROVAL_REJECTED: CODE_APPROVAL_REQUIRED,
        BLOCK_APPROVAL_EXPIRED: CODE_APPROVAL_EXPIRED,
        BLOCK_CREDENTIALS_MISSING: BLOCK_CREDENTIALS_MISSING,
        BLOCK_PREFLIGHT_NOT_READY: CODE_PRECKECK_FAILED,
        BLOCK_NO_NARRATION: CODE_PRECKECK_FAILED,
        BLOCK_LIVE_TTS_NOT_REQUESTED: BLOCK_LIVE_TTS_NOT_REQUESTED,
        BLOCK_OPERATIONS_CANCELLED: CODE_CANCELLED,
    }
    return mapping.get(code, CODE_PRECONDITION_FAILED)


@dataclass
class VoiceLiveTtsPolicyResult:
    allowed: bool
    action: str = ACTION_RUN
    reject_reasons: list[str] = field(default_factory=list)
    code: str | None = None
    message: str = ""
    guard_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "action": self.action,
            "reject_reasons": list(self.reject_reasons),
            "message": self.message,
        }
        if self.code:
            payload["code"] = self.code
        if self.guard_result is not None:
            payload["guard_result"] = self.guard_result
        return payload


def _blocked(
    reasons: list[str],
    *,
    code: str = CODE_PRECONDITION_FAILED,
    message: str = "",
    guard_result: dict[str, Any] | None = None,
) -> VoiceLiveTtsPolicyResult:
    return VoiceLiveTtsPolicyResult(
        allowed=False,
        reject_reasons=reasons,
        code=code,
        message=message or (reasons[0] if reasons else "Voice run blocked."),
        guard_result=guard_result,
    )


def is_voice_live_tts_enabled() -> bool:
    """Server env flag — enabling alone does not permit live execution in 11H-2c."""
    return os.getenv("MODIR_VOICE_LIVE_TTS_ENABLED", "false").strip().lower() == "true"


def is_live_real_http_permitted() -> bool:
    """True only when operator-approved live gates are both enabled (11H-2e+)."""
    return LIVE_RUNTIME_EXECUTION_APPROVED and is_voice_live_tts_enabled()


def evaluate_voice_run_mode_request(
    provider_mode: str,
    confirm_live_tts: bool,
) -> VoiceLiveTtsPolicyResult:
    """Validate requested provider mode before run (fail closed for live in 11H-2c)."""
    mode = str(provider_mode or PROVIDER_MODE_MOCK).strip().lower()
    if mode not in (PROVIDER_MODE_MOCK, PROVIDER_MODE_LIVE):
        return _blocked(
            ["INVALID_PROVIDER_MODE"],
            code=CODE_PRECONDITION_FAILED,
            message=f"Unsupported provider_mode: {provider_mode}",
        )
    if mode == PROVIDER_MODE_MOCK:
        return VoiceLiveTtsPolicyResult(
            allowed=True,
            message="Mock voice TTS run permitted.",
        )
    if not confirm_live_tts:
        return _blocked(
            [CODE_LIVE_TTS_NOT_CONFIRMED],
            code=CODE_LIVE_TTS_NOT_CONFIRMED,
            message="confirm_live_tts must be true for live_elevenlabs.",
        )
    if not LIVE_RUNTIME_EXECUTION_APPROVED:
        return _blocked(
            [CODE_LIVE_TTS_DISABLED],
            code=CODE_LIVE_TTS_DISABLED,
            message="Live ElevenLabs runtime execution is not approved (11H-2c).",
        )
    if not is_voice_live_tts_enabled():
        return _blocked(
            [CODE_LIVE_TTS_DISABLED],
            code=CODE_LIVE_TTS_DISABLED,
            message="MODIR_VOICE_LIVE_TTS_ENABLED is not set.",
        )
    return VoiceLiveTtsPolicyResult(
        allowed=True,
        message="Live ElevenLabs run mode permitted by policy.",
    )


def evaluate_voice_live_tts_live_caps(voice_slot: dict[str, Any]) -> VoiceLiveTtsPolicyResult:
    """Fail-closed live caps — used when live execution is approved (11H-2d+)."""
    slot = dict(_dict(voice_slot))
    approval = _dict(slot.get("approval"))
    adapter = _dict(slot.get("narration_adapter"))

    character_count = approval.get("estimated_character_count")
    segment_count = approval.get("estimated_segment_count")
    estimated_cost = approval.get("estimated_voice_cost")

    if character_count is None:
        character_count = int(adapter.get("total_text_length") or slot.get("segment_count") or 0)
    if segment_count is None:
        segment_count = int(slot.get("segment_count") or adapter.get("segment_count") or 0)

    if estimated_cost is None or character_count is None or segment_count is None:
        return _blocked(
            [CODE_ESTIMATES_MISSING],
            code=CODE_ESTIMATES_MISSING,
            message="Live run requires character, segment, and cost estimates.",
        )

    if int(segment_count) > MAX_SEGMENTS_PER_RUN:
        return _blocked(
            [CODE_PRECKECK_FAILED],
            code=CODE_PRECKECK_FAILED,
            message=f"Segment count exceeds cap ({MAX_SEGMENTS_PER_RUN}).",
        )
    if int(character_count) > MAX_CHARACTERS_PER_RUN:
        return _blocked(
            [BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED],
            code=BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED,
            message=f"Character count exceeds cap ({MAX_CHARACTERS_PER_RUN}).",
        )
    if float(estimated_cost) > MAX_ESTIMATED_COST_USD:
        return _blocked(
            [BLOCK_VOICE_COST_LIMIT_EXCEEDED],
            code=BLOCK_VOICE_COST_LIMIT_EXCEEDED,
            message=f"Estimated cost exceeds cap (${MAX_ESTIMATED_COST_USD}).",
        )

    return VoiceLiveTtsPolicyResult(allowed=True, message="Live caps satisfied.")


def evaluate_voice_live_tts_run(
    session: dict[str, Any],
    voice_slot: dict[str, Any] | None,
    *,
    force_retry: bool = False,
    project_root: str | None = None,
    provider_mode: str = PROVIDER_MODE_MOCK,
    confirm_live_tts: bool = False,
) -> VoiceLiveTtsPolicyResult:
    """Return whether POST /voice/run is permitted."""
    if _session_archived(session):
        return _blocked(
            [CODE_SESSION_ARCHIVED],
            code=CODE_SESSION_ARCHIVED,
            message="Session is archived.",
        )

    if voice_slot is None:
        return _blocked(
            [CODE_VOICE_SLOT_MISSING],
            code=CODE_VOICE_SLOT_MISSING,
            message="Voice generation slot is missing.",
        )

    slot = dict(_dict(voice_slot))

    if _session_cancel_requested(session):
        return _blocked(
            [BLOCK_OPERATIONS_CANCELLED],
            code=CODE_CANCELLED,
            message="Session cancellation requested.",
        )

    status = str(slot.get("status") or slot.get("state") or "").lower()
    if status == STATUS_RUNNING:
        return _blocked(
            [CODE_JOB_ALREADY_ACTIVE],
            code=CODE_JOB_ALREADY_ACTIVE,
            message="Voice TTS run is already active.",
        )

    if status == "completed" and not force_retry:
        return _blocked(
            [CODE_INVALID_VOICE_STATE],
            code=CODE_INVALID_VOICE_STATE,
            message="Voice run already completed; use force_retry to re-run.",
        )

    if status not in RUNNABLE_STATUSES and not force_retry:
        return _blocked(
            [CODE_INVALID_VOICE_STATE],
            code=CODE_INVALID_VOICE_STATE,
            message=f"Cannot run from voice status={status}.",
        )

    if _narration_skipped(slot):
        return _blocked(
            [BLOCK_NO_NARRATION],
            code=CODE_PRECKECK_FAILED,
            message="No narration available.",
        )

    if not _provider_supported(slot):
        return _blocked(
            [CODE_PROVIDER_NOT_SUPPORTED],
            code=CODE_PROVIDER_NOT_SUPPORTED,
            message="Voice provider is not supported for live TTS run.",
        )

    if _credentials_missing(slot):
        return _blocked(
            [BLOCK_CREDENTIALS_MISSING],
            code=BLOCK_CREDENTIALS_MISSING,
            message="ElevenLabs credentials missing.",
        )

    if not _preflight_ready(slot):
        return _blocked(
            [BLOCK_PREFLIGHT_NOT_READY],
            code=CODE_PRECKECK_FAILED,
            message="Voice preflight is not ready.",
        )

    effective = _effective_approval_state(slot)
    if effective == STATE_REJECTED:
        return _blocked(
            [BLOCK_VOICE_APPROVAL_REJECTED],
            code=CODE_APPROVAL_REQUIRED,
            message="Voice approval was rejected.",
        )
    if effective == STATE_EXPIRED:
        return _blocked(
            [BLOCK_APPROVAL_EXPIRED],
            code=CODE_APPROVAL_EXPIRED,
            message="Voice approval has expired.",
        )
    if effective != STATE_APPROVED:
        return _blocked(
            [BLOCK_VOICE_APPROVAL_REQUIRED],
            code=CODE_APPROVAL_REQUIRED,
            message="Voice approval is required before live TTS run.",
        )

    if not bool(slot.get("live_tts_requested")):
        return _blocked(
            [BLOCK_LIVE_TTS_NOT_REQUESTED],
            code=BLOCK_LIVE_TTS_NOT_REQUESTED,
            message="live_tts_requested must be true.",
        )

    guard = can_run_live_voice_tts(slot, session, project_root=project_root)
    guard_dict = guard.to_dict()
    if not guard.allowed:
        primary = guard.block_codes[0] if guard.block_codes else CODE_PRECONDITION_FAILED
        return _blocked(
            list(guard.block_codes),
            code=_map_guard_code(primary),
            message="can_run_live_voice_tts guard blocked run.",
            guard_result=guard_dict,
        )

    if str(provider_mode or PROVIDER_MODE_MOCK).lower() == PROVIDER_MODE_LIVE:
        mode_check = evaluate_voice_run_mode_request(provider_mode, confirm_live_tts)
        if not mode_check.allowed:
            return mode_check
        from content_brain.execution.voice_live_tts_smoke_profile import evaluate_voice_live_tts_smoke_caps

        caps = evaluate_voice_live_tts_smoke_caps(slot)
        if not caps.allowed:
            return caps

    label = "mock mode" if str(provider_mode or PROVIDER_MODE_MOCK).lower() == PROVIDER_MODE_MOCK else "live mode"
    return VoiceLiveTtsPolicyResult(
        allowed=True,
        message=f"Voice live TTS run permitted ({label}).",
        guard_result=guard_dict,
    )


__all__ = [
    "ACTION_RUN",
    "CODE_SESSION_ARCHIVED",
    "CODE_APPROVAL_REQUIRED",
    "CODE_APPROVAL_EXPIRED",
    "CODE_PRECKECK_FAILED",
    "CODE_CANCELLED",
    "CODE_JOB_ALREADY_ACTIVE",
    "CODE_LIVE_TTS_DISABLED",
    "CODE_LIVE_TTS_NOT_CONFIRMED",
    "CODE_ESTIMATES_MISSING",
    "PROVIDER_MODE_MOCK",
    "PROVIDER_MODE_LIVE",
    "LIVE_RUNTIME_EXECUTION_APPROVED",
    "VoiceLiveTtsPolicyResult",
    "is_voice_live_tts_enabled",
    "is_live_real_http_permitted",
    "evaluate_voice_run_mode_request",
    "evaluate_voice_live_tts_live_caps",
    "evaluate_voice_live_tts_run",
]
