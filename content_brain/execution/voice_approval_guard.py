"""
Phase 11H-1e — read-only voice approval gate metadata and live TTS guard helper.

Computes approval block fields on voice_generation slot without executing TTS.
Never imports or calls ElevenLabsVoiceProvider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import STATUS_SKIPPED
from content_brain.providers.provider_cost_catalog import (
    CAPABILITY_NARRATION,
    ProviderCostEstimator,
)
from providers.elevenlabs_preflight import CODE_CREDENTIALS_MISSING

GATE_VERSION = "11h1e_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATE_NOT_REQUIRED = "not_required"
STATE_REQUIRED = "required"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_EXPIRED = "expired"

BLOCK_LIVE_TTS_NOT_REQUESTED = "LIVE_TTS_NOT_REQUESTED"
BLOCK_NO_NARRATION = "NO_NARRATION"
BLOCK_CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
BLOCK_VOICE_APPROVAL_REQUIRED = "VOICE_APPROVAL_REQUIRED"
BLOCK_APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
BLOCK_VOICE_APPROVAL_REJECTED = "VOICE_APPROVAL_REJECTED"
BLOCK_PREFLIGHT_NOT_READY = "PREFLIGHT_NOT_READY"
BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED = "VOICE_CHARACTER_LIMIT_EXCEEDED"
BLOCK_VOICE_COST_LIMIT_EXCEEDED = "VOICE_COST_LIMIT_EXCEEDED"
BLOCK_BUDGET_BLOCKED = "BUDGET_BLOCKED"
BLOCK_OPERATIONS_CANCELLED = "OPERATIONS_CANCELLED"

DEFAULT_MAX_CHARACTERS = 5000
DEFAULT_MAX_COST_USD = 5.0
DEFAULT_APPROVAL_TTL_HOURS = 4


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _now() -> datetime:
    return datetime.now()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (TIMESTAMP_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _format_timestamp(value: datetime) -> str:
    return value.strftime(TIMESTAMP_FORMAT)


def _estimate_voice_cost(
    provider: str,
    character_count: int,
    *,
    project_root: str | Path | None = None,
) -> tuple[float | None, str, str]:
    if not provider or character_count <= 0:
        return None, "USD", "low"
    try:
        catalog = ProviderCostEstimator.load(project_root=project_root)
        result = catalog.estimate_voice(provider, characters=float(character_count), capability=CAPABILITY_NARRATION)
        confidence = str(result.confidence or "low").lower()
        return result.estimated_cost, str(result.currency or "USD"), confidence
    except Exception:
        return None, "USD", "low"


def _voice_policy_snapshot() -> dict[str, Any]:
    return {
        "max_characters_per_run": DEFAULT_MAX_CHARACTERS,
        "max_estimated_voice_cost_usd": DEFAULT_MAX_COST_USD,
        "approval_ttl_hours": DEFAULT_APPROVAL_TTL_HOURS,
    }


def _narration_skipped(voice_slot: dict[str, Any]) -> bool:
    adapter = _dict(voice_slot.get("narration_adapter"))
    if adapter.get("skipped"):
        return True
    if str(voice_slot.get("status") or "").lower() == STATUS_SKIPPED:
        return True
    segment_count = voice_slot.get("segment_count")
    if segment_count is not None and int(segment_count) <= 0:
        return True
    if adapter.get("segment_count") is not None and int(adapter.get("segment_count") or 0) <= 0:
        return True
    return False


def _credentials_missing(voice_slot: dict[str, Any]) -> bool:
    error = _dict(voice_slot.get("error"))
    if str(error.get("code") or "").upper() == CODE_CREDENTIALS_MISSING:
        return True
    preflight = _dict(voice_slot.get("voice_preflight"))
    return str(preflight.get("code") or "").upper() == CODE_CREDENTIALS_MISSING


def _preflight_ready(voice_slot: dict[str, Any]) -> bool:
    return bool(_dict(voice_slot.get("voice_preflight")).get("ready"))


def _resolve_character_and_segment_counts(voice_slot: dict[str, Any]) -> tuple[int, int]:
    adapter = _dict(voice_slot.get("narration_adapter"))
    segment_count = int(voice_slot.get("segment_count") or adapter.get("segment_count") or 0)
    character_count = int(adapter.get("total_text_length") or 0)
    return character_count, segment_count


def _resolve_effective_approval_state(
    existing: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    state = str(existing.get("approval_state") or STATE_NOT_REQUIRED).lower()
    if state != STATE_APPROVED:
        return state
    expires_at = _parse_timestamp(existing.get("approval_expires_at"))
    if expires_at and (now or _now()) >= expires_at:
        return STATE_EXPIRED
    return state


def _session_budget_allowed(session: dict[str, Any] | None) -> bool:
    if not session:
        return True
    budget = _dict(session.get("budget_decision"))
    if not budget:
        return True
    allowed = budget.get("budget_allowed")
    if allowed is None:
        return True
    return bool(allowed)


def _session_cancel_requested(session: dict[str, Any] | None) -> bool:
    if not session:
        return False
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations_control"))
    if operations.get("cancel_requested"):
        return True
    return bool(_dict(session.get("operations_control")).get("cancel_requested"))


def _build_approval_base(
    existing: dict[str, Any],
    *,
    character_count: int,
    segment_count: int,
    estimated_cost: float | None,
    cost_currency: str,
    cost_confidence: str,
) -> dict[str, Any]:
    return {
        "gate_version": GATE_VERSION,
        "approval_required": bool(existing.get("approval_required", False)),
        "approval_state": str(existing.get("approval_state") or STATE_NOT_REQUIRED),
        "approved_by": existing.get("approved_by"),
        "approved_at": existing.get("approved_at"),
        "approval_reason": existing.get("approval_reason"),
        "estimated_voice_cost": estimated_cost,
        "estimated_voice_cost_currency": cost_currency,
        "estimated_voice_cost_confidence": cost_confidence,
        "estimated_character_count": character_count,
        "estimated_segment_count": segment_count,
        "approval_expires_at": existing.get("approval_expires_at"),
        "live_tts_eligible": False,
        "live_tts_blocked_reasons": [],
    }


def evaluate_voice_approval_gate(
    voice_slot: dict[str, Any],
    session: dict[str, Any] | None = None,
    *,
    live_tts_requested: bool | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Compute read-only approval metadata for a voice_generation slot.

    Preserves existing approval fields (approved_by, approved_at, etc.) when present.
    """
    slot = dict(_dict(voice_slot))
    existing = dict(_dict(slot.get("approval")))
    requested = (
        bool(live_tts_requested)
        if live_tts_requested is not None
        else bool(slot.get("live_tts_requested"))
    )

    provider = str(slot.get("provider") or "elevenlabs")
    character_count, segment_count = _resolve_character_and_segment_counts(slot)
    estimated_cost, cost_currency, cost_confidence = _estimate_voice_cost(
        provider,
        character_count,
        project_root=project_root,
    )

    approval = _build_approval_base(
        existing,
        character_count=character_count,
        segment_count=segment_count,
        estimated_cost=estimated_cost,
        cost_currency=cost_currency,
        cost_confidence=cost_confidence,
    )
    blocked: list[str] = []

    if _narration_skipped(slot):
        approval.update(
            {
                "approval_required": False,
                "approval_state": STATE_NOT_REQUIRED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_NO_NARRATION],
            }
        )
        return approval

    if _credentials_missing(slot):
        approval.update(
            {
                "approval_required": False,
                "approval_state": STATE_NOT_REQUIRED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_CREDENTIALS_MISSING],
            }
        )
        return approval

    if not _preflight_ready(slot):
        approval.update(
            {
                "approval_required": False,
                "approval_state": STATE_NOT_REQUIRED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_PREFLIGHT_NOT_READY],
            }
        )
        return approval

    if not requested:
        approval.update(
            {
                "approval_required": False,
                "approval_state": STATE_NOT_REQUIRED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_LIVE_TTS_NOT_REQUESTED],
            }
        )
        return approval

    effective_state = _resolve_effective_approval_state(existing)
    approval["approval_required"] = True

    if effective_state == STATE_REJECTED:
        approval.update(
            {
                "approval_state": STATE_REJECTED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_VOICE_APPROVAL_REJECTED],
            }
        )
        return approval

    if effective_state == STATE_EXPIRED:
        approval.update(
            {
                "approval_state": STATE_EXPIRED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_APPROVAL_EXPIRED],
            }
        )
        return approval

    if effective_state != STATE_APPROVED:
        approval.update(
            {
                "approval_state": STATE_REQUIRED,
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_VOICE_APPROVAL_REQUIRED],
            }
        )
        return approval

    approval["approval_state"] = STATE_APPROVED
    approval["approved_by"] = existing.get("approved_by")
    approval["approved_at"] = existing.get("approved_at")
    approval["approval_reason"] = existing.get("approval_reason")
    approval["approval_expires_at"] = existing.get("approval_expires_at")

    guard = can_run_live_voice_tts({**slot, "approval": approval}, session=session, project_root=project_root)
    approval["live_tts_eligible"] = guard.allowed
    approval["live_tts_blocked_reasons"] = guard.block_codes if guard.blocked else []
    return approval


def build_voice_approval_operations_mirror(
    voice_slot: dict[str, Any],
    *,
    live_tts_requested: bool,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    approval = _dict(voice_slot.get("approval"))
    return {
        "gate_version": GATE_VERSION,
        "evaluated_at": evaluated_at,
        "approval_required": approval.get("approval_required"),
        "approval_state": approval.get("approval_state"),
        "live_tts_requested": live_tts_requested,
        "live_tts_eligible": approval.get("live_tts_eligible"),
        "blocked_reasons": list(approval.get("live_tts_blocked_reasons") or []),
        "policy_snapshot": _voice_policy_snapshot(),
    }


@dataclass
class VoiceLiveTtsGuardResult:
    allowed: bool
    blocked: bool
    block_codes: list[str] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    approval_state: str = STATE_NOT_REQUIRED
    live_tts_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocked": self.blocked,
            "block_codes": list(self.block_codes),
            "block_reasons": list(self.block_reasons),
            "approval_state": self.approval_state,
            "live_tts_eligible": self.live_tts_eligible,
        }


def can_run_live_voice_tts(
    slot: dict[str, Any],
    session: dict[str, Any] | None = None,
    *,
    project_root: str | Path | None = None,
) -> VoiceLiveTtsGuardResult:
    """
    Structured guard for future live TTS execution (11H-2+).

    Returns allowed=True only when all checks pass. Does not call TTS providers.
    """
    voice_slot = dict(_dict(slot))
    approval = _dict(voice_slot.get("approval"))
    block_codes: list[str] = []
    approval_state = str(approval.get("approval_state") or STATE_NOT_REQUIRED)

    live_tts_requested = bool(voice_slot.get("live_tts_requested"))

    if _narration_skipped(voice_slot):
        block_codes.append(BLOCK_NO_NARRATION)
    elif _credentials_missing(voice_slot):
        block_codes.append(BLOCK_CREDENTIALS_MISSING)
    elif not _preflight_ready(voice_slot):
        block_codes.append(BLOCK_PREFLIGHT_NOT_READY)
    elif not live_tts_requested:
        block_codes.append(BLOCK_LIVE_TTS_NOT_REQUESTED)
    else:
        effective_state = _resolve_effective_approval_state(approval)
        approval_state = effective_state
        if effective_state == STATE_REJECTED:
            block_codes.append(BLOCK_VOICE_APPROVAL_REJECTED)
        elif effective_state == STATE_EXPIRED:
            block_codes.append(BLOCK_APPROVAL_EXPIRED)
        elif effective_state != STATE_APPROVED:
            block_codes.append(BLOCK_VOICE_APPROVAL_REQUIRED)
        else:
            character_count, _ = _resolve_character_and_segment_counts(voice_slot)
            if character_count > DEFAULT_MAX_CHARACTERS:
                block_codes.append(BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED)

            estimated_cost = approval.get("estimated_voice_cost")
            if estimated_cost is None:
                estimated_cost, _, _ = _estimate_voice_cost(
                    str(voice_slot.get("provider") or "elevenlabs"),
                    character_count,
                    project_root=project_root,
                )
            if estimated_cost is not None and float(estimated_cost) > DEFAULT_MAX_COST_USD:
                block_codes.append(BLOCK_VOICE_COST_LIMIT_EXCEEDED)

            if not _session_budget_allowed(session):
                block_codes.append(BLOCK_BUDGET_BLOCKED)

            if _session_cancel_requested(session):
                block_codes.append(BLOCK_OPERATIONS_CANCELLED)

    allowed = len(block_codes) == 0
    return VoiceLiveTtsGuardResult(
        allowed=allowed,
        blocked=not allowed,
        block_codes=block_codes,
        block_reasons=block_codes,
        approval_state=approval_state,
        live_tts_eligible=allowed,
    )


__all__ = [
    "GATE_VERSION",
    "STATE_NOT_REQUIRED",
    "STATE_REQUIRED",
    "STATE_APPROVED",
    "STATE_REJECTED",
    "STATE_EXPIRED",
    "BLOCK_LIVE_TTS_NOT_REQUESTED",
    "BLOCK_NO_NARRATION",
    "BLOCK_CREDENTIALS_MISSING",
    "BLOCK_VOICE_APPROVAL_REQUIRED",
    "BLOCK_APPROVAL_EXPIRED",
    "VoiceLiveTtsGuardResult",
    "evaluate_voice_approval_gate",
    "build_voice_approval_operations_mirror",
    "can_run_live_voice_tts",
]
