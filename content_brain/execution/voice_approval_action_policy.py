"""
Phase 11H-1g — eligibility and precondition checks for voice approval write actions.

Pure policy — never executes TTS or mutates sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VOICE
from content_brain.execution.voice_approval_guard import (
    BLOCK_CREDENTIALS_MISSING,
    BLOCK_LIVE_TTS_NOT_REQUESTED,
    BLOCK_NO_NARRATION,
    BLOCK_OPERATIONS_CANCELLED,
    BLOCK_PREFLIGHT_NOT_READY,
    BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED,
    BLOCK_VOICE_COST_LIMIT_EXCEEDED,
    DEFAULT_MAX_CHARACTERS,
    DEFAULT_MAX_COST_USD,
    GATE_VERSION,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_REJECTED,
    STATE_REQUIRED,
    TIMESTAMP_FORMAT,
)

ACTION_APPROVE = "approve_voice"
ACTION_REJECT = "reject_voice"
ACTION_EXPIRE = "expire_voice"
ACTION_RESET = "reset_approval"

CODE_PRECONDITION_FAILED = "VOICE_APPROVAL_PRECONDITION_FAILED"
CODE_ALREADY_APPROVED = "ALREADY_APPROVED"
CODE_SESSION_ARCHIVED = "SESSION_ARCHIVED"
CODE_VOICE_SLOT_MISSING = "VOICE_SLOT_MISSING"
CODE_PROVIDER_NOT_SUPPORTED = "PROVIDER_NOT_SUPPORTED"
CODE_ESTIMATE_MISSING = "ESTIMATE_MISSING"
CODE_INVALID_STATE = "VOICE_APPROVAL_INVALID_STATE"

SUPPORTED_PROVIDER = "elevenlabs"


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
    provider = str(voice_slot.get("provider") or SUPPORTED_PROVIDER).lower()
    return provider == SUPPORTED_PROVIDER


def _resolve_counts(voice_slot: dict[str, Any]) -> tuple[int, int]:
    adapter = _dict(voice_slot.get("narration_adapter"))
    segment_count = int(voice_slot.get("segment_count") or adapter.get("segment_count") or 0)
    character_count = int(adapter.get("total_text_length") or 0)
    approval = _dict(voice_slot.get("approval"))
    if approval.get("estimated_character_count") is not None:
        character_count = int(approval.get("estimated_character_count") or 0)
    if approval.get("estimated_segment_count") is not None:
        segment_count = int(approval.get("estimated_segment_count") or 0)
    return character_count, segment_count


def _effective_approval_state(voice_slot: dict[str, Any]) -> str:
    approval = _dict(voice_slot.get("approval"))
    state = str(approval.get("approval_state") or "not_required").lower()
    if state != STATE_APPROVED:
        return state
    expires_at = _parse_timestamp(approval.get("approval_expires_at"))
    if expires_at and datetime.utcnow() >= expires_at:
        return STATE_EXPIRED
    return state


@dataclass
class VoiceApprovalPolicyResult:
    allowed: bool
    action: str
    reject_reasons: list[str] = field(default_factory=list)
    code: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "action": self.action,
            "reject_reasons": list(self.reject_reasons),
            "message": self.message,
        }
        if self.code:
            payload["code"] = self.code
        return payload


def _blocked(
    action: str,
    reasons: list[str],
    *,
    code: str = CODE_PRECONDITION_FAILED,
    message: str = "",
) -> VoiceApprovalPolicyResult:
    return VoiceApprovalPolicyResult(
        allowed=False,
        action=action,
        reject_reasons=reasons,
        code=code,
        message=message or (reasons[0] if reasons else "Voice approval action blocked."),
    )


def _allowed(action: str, message: str = "") -> VoiceApprovalPolicyResult:
    return VoiceApprovalPolicyResult(allowed=True, action=action, message=message or "Allowed.")


def evaluate_voice_approval_action(
    session: dict[str, Any],
    voice_slot: dict[str, Any] | None,
    action: str,
    *,
    request_live_tts: bool = False,
) -> VoiceApprovalPolicyResult:
    """Return whether a voice approval write action is permitted."""
    if _session_archived(session):
        return _blocked(
            action,
            [CODE_SESSION_ARCHIVED],
            code=CODE_SESSION_ARCHIVED,
            message="Session is archived.",
        )

    if voice_slot is None:
        return _blocked(
            action,
            [CODE_VOICE_SLOT_MISSING],
            code=CODE_VOICE_SLOT_MISSING,
            message="Voice generation slot is missing.",
        )

    slot = dict(_dict(voice_slot))

    if action == ACTION_RESET:
        return _allowed(action, "Reset voice approval metadata.")

    if _session_cancel_requested(session) and action == ACTION_APPROVE:
        return _blocked(
            action,
            [BLOCK_OPERATIONS_CANCELLED],
            message="Session cancellation requested.",
        )

    if action == ACTION_APPROVE:
        if _narration_skipped(slot):
            return _blocked(action, [BLOCK_NO_NARRATION], message="No narration available.")
        if not _provider_supported(slot):
            return _blocked(
                action,
                [CODE_PROVIDER_NOT_SUPPORTED],
                code=CODE_PROVIDER_NOT_SUPPORTED,
                message="Voice provider is not elevenlabs.",
            )
        if _credentials_missing(slot):
            return _blocked(action, [BLOCK_CREDENTIALS_MISSING], message="ElevenLabs credentials missing.")
        if not _preflight_ready(slot):
            return _blocked(action, [BLOCK_PREFLIGHT_NOT_READY], message="Voice preflight is not ready.")
        if not request_live_tts:
            return _blocked(
                action,
                [BLOCK_LIVE_TTS_NOT_REQUESTED],
                message="request_live_tts must be true to approve live TTS.",
            )

        character_count, segment_count = _resolve_counts(slot)
        if character_count <= 0 or segment_count <= 0:
            return _blocked(
                action,
                [CODE_ESTIMATE_MISSING],
                code=CODE_ESTIMATE_MISSING,
                message="Estimated character/segment counts are missing.",
            )

        approval = _dict(slot.get("approval"))
        estimated_cost = approval.get("estimated_voice_cost")
        if character_count > DEFAULT_MAX_CHARACTERS:
            return _blocked(
                action,
                [BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED],
                message="Estimated character count exceeds limit.",
            )
        if estimated_cost is not None and float(estimated_cost) > DEFAULT_MAX_COST_USD:
            return _blocked(
                action,
                [BLOCK_VOICE_COST_LIMIT_EXCEEDED],
                message="Estimated voice cost exceeds limit.",
            )

        effective = _effective_approval_state(slot)
        if effective == STATE_APPROVED:
            return _blocked(
                action,
                [CODE_ALREADY_APPROVED],
                code=CODE_ALREADY_APPROVED,
                message="Voice approval is already active and not expired.",
            )
        if effective not in (STATE_REQUIRED, STATE_EXPIRED, STATE_REJECTED, "not_required"):
            return _blocked(
                action,
                [CODE_INVALID_STATE],
                code=CODE_INVALID_STATE,
                message=f"Cannot approve from approval_state={effective}.",
            )
        return _allowed(action, "Approve voice generation for future live TTS.")

    if action in (ACTION_REJECT, ACTION_EXPIRE):
        if _narration_skipped(slot) and action == ACTION_REJECT:
            return _blocked(action, [BLOCK_NO_NARRATION], message="No narration available.")
        effective = _effective_approval_state(slot)
        if action == ACTION_EXPIRE and effective not in (STATE_APPROVED, STATE_REQUIRED):
            return _blocked(
                action,
                [CODE_INVALID_STATE],
                code=CODE_INVALID_STATE,
                message=f"Cannot expire from approval_state={effective}.",
            )
        return _allowed(action)

    return _blocked(action, ["UNKNOWN_ACTION"], message=f"Unknown action: {action}")


__all__ = [
    "ACTION_APPROVE",
    "ACTION_REJECT",
    "ACTION_EXPIRE",
    "ACTION_RESET",
    "CODE_PRECONDITION_FAILED",
    "CODE_ALREADY_APPROVED",
    "CODE_SESSION_ARCHIVED",
    "CODE_VOICE_SLOT_MISSING",
    "VoiceApprovalPolicyResult",
    "evaluate_voice_approval_action",
]
