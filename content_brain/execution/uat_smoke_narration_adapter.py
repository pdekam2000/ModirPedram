"""
Phase 12G — UAT-only smoke-safe narration merge for live ElevenLabs runs.

Merges multi-beat story narration into one segment so 11H-2d smoke cap (max 1 segment)
passes without changing Content Brain, production voice runtime, or SMOKE_MAX_SEGMENTS.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from content_brain.execution.session_narration_adapter import (
    NarrationSegment,
    SessionNarrationAdapter,
)
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.uat_runtime_profile import (
    UatRuntimeConfig,
    is_e2e_full_duration_validation,
    requires_live_voice_smoke_guard,
)
from content_brain.execution.voice_live_tts_smoke_profile import SMOKE_MAX_CHARACTERS

logger = logging.getLogger(__name__)

UAT_SMOKE_NARRATION_PROFILE_VERSION = "12g_v1"
UAT_SMOKE_NARRATION_TARGET_SEGMENTS = 1
UAT_MODE = "user_acceptance_test"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_uat_smoke_narration_session(session: dict[str, Any]) -> bool:
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    uat_run = _dict(operations.get("uat_run"))
    return str(uat_run.get("mode") or "") == UAT_MODE


def requires_uat_smoke_narration_merge(
    config: UatRuntimeConfig,
    *,
    session: dict[str, Any] | None = None,
) -> bool:
    if is_e2e_full_duration_validation():
        return False
    if not requires_live_voice_smoke_guard(config):
        return False
    if session is not None and not is_uat_smoke_narration_session(session):
        return False
    return True


def merge_narration_segments_for_smoke(
    segments: list[NarrationSegment],
    *,
    max_characters: int = SMOKE_MAX_CHARACTERS,
    duration_seconds: int | None = None,
) -> str:
    """Combine beat narrations into one concise line suitable for ~10s smoke UAT."""
    texts = [segment.text.strip() for segment in segments if segment.text.strip()]
    if not texts:
        return ""

    if len(texts) == 1:
        combined = texts[0]
    else:
        hook = texts[0]
        payoff = texts[-1]
        combined = hook if hook == payoff else f"{hook} {payoff}"

    cap = max(40, min(int(max_characters), 300))
    if duration_seconds is not None and duration_seconds > 0:
        cap = min(cap, max(40, int(duration_seconds) * 22))

    if len(combined) <= cap:
        return combined

    trimmed = combined[:cap]
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed.strip()


def _single_smoke_beat(*, merged_text: str, duration_seconds: int) -> dict[str, Any]:
    end_second = float(max(duration_seconds, 6))
    return {
        "beat_id": "UAT_SMOKE_NARRATION",
        "act": 1,
        "start_second": 0.0,
        "end_second": end_second,
        "description": (
            "PURPOSE: UAT live-voice smoke single narration | "
            f"NARRATION: {merged_text} | "
            "VISUAL: single-clip supervised smoke run"
        ),
        "emotional_tone": "uat_smoke",
        "retention_mechanic": "smoke_single_segment",
    }


def _single_smoke_beat_plan(*, merged_text: str, duration_seconds: int) -> dict[str, Any]:
    end_second = float(max(duration_seconds, 6))
    return {
        "beat_id": "UAT_SMOKE_NARRATION",
        "clip_number": 1,
        "start_second": 0.0,
        "end_second": end_second,
        "narration": merged_text,
        "source": "uat_smoke_narration_adapter",
    }


def patch_brief_snapshot_for_smoke_narration(
    brief_snapshot: dict[str, Any],
    *,
    merged_text: str,
    duration_seconds: int,
) -> dict[str, Any]:
    """Return a patched brief snapshot; does not mutate the input."""
    brief = copy.deepcopy(brief_snapshot)
    story_blueprint = dict(_dict(brief.get("story_blueprint")))
    story_blueprint["beats"] = [_single_smoke_beat(merged_text=merged_text, duration_seconds=duration_seconds)]
    story_blueprint["total_duration_seconds"] = duration_seconds
    brief["story_blueprint"] = story_blueprint

    run_context = dict(_dict(brief.get("run_context")))
    story_intelligence = dict(_dict(run_context.get("story_intelligence")))
    story_architecture = dict(_dict(story_intelligence.get("story_architecture")))
    story_architecture["beat_plans"] = [
        _single_smoke_beat_plan(merged_text=merged_text, duration_seconds=duration_seconds)
    ]
    story_intelligence["story_architecture"] = story_architecture
    run_context["story_intelligence"] = story_intelligence
    brief["run_context"] = run_context
    return brief


def apply_uat_smoke_narration(
    session: dict[str, Any],
    config: UatRuntimeConfig,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Patch session brief narration for smoke UAT when live ElevenLabs is confirmed.

    Returns (session, metadata) where metadata is None when merge was skipped.
    """
    if not requires_uat_smoke_narration_merge(config, session=session):
        return session, None

    adapter = SessionNarrationAdapter()
    bundle = adapter.build(session)
    original_count = int(bundle.segment_count)
    if original_count <= UAT_SMOKE_NARRATION_TARGET_SEGMENTS:
        metadata = {
            "profile_version": UAT_SMOKE_NARRATION_PROFILE_VERSION,
            "applied": False,
            "skipped_reason": "already_single_segment",
            "original_narration_segment_count": original_count,
            "smoke_narration_segment_count": original_count,
        }
        return session, metadata

    merged_text = merge_narration_segments_for_smoke(
        list(bundle.segments),
        duration_seconds=config.duration_seconds,
    )
    if not merged_text:
        metadata = {
            "profile_version": UAT_SMOKE_NARRATION_PROFILE_VERSION,
            "applied": False,
            "skipped_reason": "no_narration_text",
            "original_narration_segment_count": original_count,
            "smoke_narration_segment_count": 0,
        }
        return session, metadata

    updated = copy.deepcopy(session)
    brief_snapshot = _dict(updated.get("brief_snapshot"))
    updated["brief_snapshot"] = patch_brief_snapshot_for_smoke_narration(
        brief_snapshot,
        merged_text=merged_text,
        duration_seconds=config.duration_seconds,
    )

    verify = SessionNarrationAdapter().build(updated)
    smoke_count = int(verify.segment_count)
    metadata = {
        "profile_version": UAT_SMOKE_NARRATION_PROFILE_VERSION,
        "applied": True,
        "original_narration_segment_count": original_count,
        "smoke_narration_segment_count": smoke_count,
        "merged_text_length": len(merged_text),
        "merged_text_preview": merged_text[:120],
    }

    logger.warning(
        "[UAT_SMOKE_NARRATION] original_narration_segment_count=%s smoke_narration_segment_count=%s duration_seconds=%s",
        original_count,
        smoke_count,
        config.duration_seconds,
    )
    return updated, metadata


def apply_uat_smoke_narration_session(
    store: ExecutionSessionStore,
    session_id: str,
    config: UatRuntimeConfig,
) -> dict[str, Any] | None:
    """Load session, apply smoke narration merge, persist metadata on uat_run."""
    session = store.load_session(session_id)
    updated, metadata = apply_uat_smoke_narration(session, config)
    if metadata is None:
        return None

    runtime = _dict(updated.get("execution_runtime"))
    operations = dict(_dict(runtime.get("operations")))
    uat_run = dict(_dict(operations.get("uat_run")))
    uat_run["smoke_narration"] = metadata
    operations["uat_run"] = uat_run
    runtime["operations"] = operations
    updated["execution_runtime"] = runtime
    store.save_session(updated, overwrite=True)
    return metadata


__all__ = [
    "UAT_SMOKE_NARRATION_PROFILE_VERSION",
    "UAT_SMOKE_NARRATION_TARGET_SEGMENTS",
    "is_uat_smoke_narration_session",
    "requires_uat_smoke_narration_merge",
    "merge_narration_segments_for_smoke",
    "patch_brief_snapshot_for_smoke_narration",
    "apply_uat_smoke_narration",
    "apply_uat_smoke_narration_session",
]
