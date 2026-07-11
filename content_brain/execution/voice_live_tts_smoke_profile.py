"""
Phase 11H-2d — strict smoke-test caps for first live ElevenLabs runs.

Applied when provider_mode=live_elevenlabs (fail closed before real HTTP).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from content_brain.execution.voice_approval_guard import (
    BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED,
    BLOCK_VOICE_COST_LIMIT_EXCEEDED,
)
from content_brain.execution.voice_live_tts_action_policy import (
    CODE_ESTIMATES_MISSING,
    CODE_PRECKECK_FAILED,
    VoiceLiveTtsPolicyResult,
    _blocked,
)

SMOKE_PROFILE_VERSION = "11h2d_v1"
SMOKE_MAX_SEGMENTS = 1
SMOKE_MAX_CHARACTERS = 300
SMOKE_MAX_ESTIMATED_COST_USD = 0.10
SMOKE_MAX_RETRY_ATTEMPTS = 1
SMOKE_TIMEOUT_SECONDS = 60


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def smoke_caps_snapshot() -> dict[str, float | int]:
    return {
        "max_segments_per_run": SMOKE_MAX_SEGMENTS,
        "max_characters_per_run": SMOKE_MAX_CHARACTERS,
        "max_estimated_cost_usd": SMOKE_MAX_ESTIMATED_COST_USD,
        "max_retry_attempts": SMOKE_MAX_RETRY_ATTEMPTS,
        "timeout_seconds": SMOKE_TIMEOUT_SECONDS,
        "profile_version": SMOKE_PROFILE_VERSION,
    }


def evaluate_voice_live_tts_smoke_caps(
    voice_slot: dict[str, Any],
    *,
    narration_segment_count: int | None = None,
    narration_character_count: int | None = None,
) -> VoiceLiveTtsPolicyResult:
    """Fail-closed smoke caps for live_elevenlabs runs."""
    slot = dict(_dict(voice_slot))
    approval = _dict(slot.get("approval"))
    adapter = _dict(slot.get("narration_adapter"))

    character_count = narration_character_count
    if character_count is None:
        character_count = approval.get("estimated_character_count")
    if character_count is None:
        character_count = int(adapter.get("total_text_length") or 0)

    segment_count = narration_segment_count
    if segment_count is None:
        segment_count = approval.get("estimated_segment_count")
    if segment_count is None:
        segment_count = int(slot.get("segment_count") or adapter.get("segment_count") or 0)

    estimated_cost = approval.get("estimated_voice_cost")

    if estimated_cost is None:
        return _blocked(
            [CODE_ESTIMATES_MISSING],
            code=CODE_ESTIMATES_MISSING,
            message="Live smoke run requires estimated_voice_cost on approval block.",
        )

    logger.warning(
        "[UAT_SMOKE_CAP_PRECHECK] %s",
        json.dumps(
            {
                "smoke_cap": SMOKE_MAX_SEGMENTS,
                "resolved_segment_count": int(segment_count),
                "narration_segment_count_arg": narration_segment_count,
                "approval_estimated_segment_count": approval.get("estimated_segment_count"),
                "slot_segment_count": slot.get("segment_count"),
                "adapter_segment_count": adapter.get("segment_count"),
                "resolved_character_count": int(character_count),
                "estimated_voice_cost": estimated_cost,
            },
            sort_keys=True,
                ensure_ascii=False,
            ),
    )

    if int(segment_count) > SMOKE_MAX_SEGMENTS:
        return _blocked(
            [CODE_PRECKECK_FAILED],
            code=CODE_PRECKECK_FAILED,
            message=f"Smoke segment count exceeds cap ({SMOKE_MAX_SEGMENTS}).",
        )
    if int(character_count) > SMOKE_MAX_CHARACTERS:
        return _blocked(
            [BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED],
            code=BLOCK_VOICE_CHARACTER_LIMIT_EXCEEDED,
            message=f"Smoke character count exceeds cap ({SMOKE_MAX_CHARACTERS}).",
        )
    if float(estimated_cost) > SMOKE_MAX_ESTIMATED_COST_USD:
        return _blocked(
            [BLOCK_VOICE_COST_LIMIT_EXCEEDED],
            code=BLOCK_VOICE_COST_LIMIT_EXCEEDED,
            message=f"Smoke estimated cost exceeds cap (${SMOKE_MAX_ESTIMATED_COST_USD}).",
        )

    return VoiceLiveTtsPolicyResult(allowed=True, message="Live smoke caps satisfied.")


__all__ = [
    "SMOKE_PROFILE_VERSION",
    "SMOKE_MAX_SEGMENTS",
    "SMOKE_MAX_CHARACTERS",
    "SMOKE_MAX_ESTIMATED_COST_USD",
    "SMOKE_MAX_RETRY_ATTEMPTS",
    "SMOKE_TIMEOUT_SECONDS",
    "smoke_caps_snapshot",
    "evaluate_voice_live_tts_smoke_caps",
]
