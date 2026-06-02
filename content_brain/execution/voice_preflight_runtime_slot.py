"""
Phase 11H-1b — dry-run voice preflight wiring for voice_generation runtime slot.

Evaluates narration availability and ElevenLabs preflight only.
Never calls live TTS or ElevenLabsVoiceProvider.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    category_short_name,
)
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_narration_adapter import SessionNarrationAdapter
from content_brain.execution.voice_approval_guard import (
    build_voice_approval_operations_mirror,
    evaluate_voice_approval_gate,
)
from providers.elevenlabs_preflight import CODE_CREDENTIALS_MISSING, ElevenLabsPreflight

SLOT_VERSION = "11h1b_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

NOTE_NO_NARRATION = "No narration text available"
NOTE_PREFLIGHT_READY = "Voice preflight ready"
NOTE_KEY_MISSING = "ElevenLabs API key missing"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _narration_adapter_summary(bundle_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_count": bundle_dict.get("segment_count", 0),
        "total_text_length": bundle_dict.get("total_text_length", 0),
        "source_path": bundle_dict.get("source_path"),
        "skipped": bool(bundle_dict.get("skipped")),
        "warnings": list(bundle_dict.get("warnings") or []),
    }


def _is_completed_executed_voice_run(voice_slot: dict[str, Any]) -> bool:
    return (
        str(voice_slot.get("status") or "").lower() == "completed"
        and voice_slot.get("executed") is True
    )


def apply_voice_preflight_dry_run(
    session: dict[str, Any],
    execution_runtime: dict[str, Any],
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Evaluate voice preflight and update voice_generation slot metadata only.

    Does not modify video_generation or other category slots.
    """
    runtime = dict(_dict(execution_runtime))
    category_runtime = dict(_dict(runtime.get("category_runtime")))
    video_slot_before = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
    voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
    completed_run = _is_completed_executed_voice_run(voice_slot)

    adapter = SessionNarrationAdapter()
    bundle = adapter.build(session)
    bundle_dict = bundle.to_dict()
    evaluated_at = _now()

    voice_slot["category_name"] = category_short_name(CATEGORY_VOICE)
    if not completed_run:
        voice_slot["executed"] = False
        voice_slot["dry_run"] = True
        voice_slot["live_tts"] = False
    voice_slot.setdefault("live_tts_requested", False)
    voice_slot["preflight_evaluated_at"] = evaluated_at
    voice_slot["slot_version"] = SLOT_VERSION
    voice_slot["narration_adapter"] = _narration_adapter_summary(bundle_dict)

    if bundle.skipped:
        if not completed_run:
            voice_slot["status"] = STATUS_SKIPPED
            voice_slot["state"] = "skipped"
            voice_slot["runtime_notes"] = [NOTE_NO_NARRATION]
            voice_slot["error"] = None
            voice_slot["voice_preflight"] = None
            voice_slot["segment_count"] = 0
    else:
        preflight = ElevenLabsPreflight(project_root).run(session, narration_skipped=False)
        preflight_dict = preflight.to_dict()
        voice_slot["voice_preflight"] = preflight_dict
        voice_slot["segment_count"] = bundle.segment_count
        if not completed_run:
            voice_slot["provider"] = "elevenlabs"

            if preflight.ready:
                voice_slot["status"] = STATUS_PENDING
                voice_slot["state"] = "pending"
                voice_slot["runtime_notes"] = [NOTE_PREFLIGHT_READY]
                voice_slot["error"] = None
            elif preflight.code == CODE_CREDENTIALS_MISSING:
                voice_slot["status"] = STATUS_FAILED
                voice_slot["state"] = "FAILED"
                voice_slot["runtime_notes"] = [NOTE_KEY_MISSING]
                voice_slot["error"] = {
                    "code": CODE_CREDENTIALS_MISSING,
                    "message": preflight.message,
                    "category": "PREFLIGHT_REJECT",
                }
            else:
                voice_slot["status"] = STATUS_FAILED
                voice_slot["state"] = "FAILED"
                voice_slot["runtime_notes"] = [preflight.message or "Voice preflight failed."]
                voice_slot["error"] = {
                    "code": preflight.code or "PREFLIGHT_FAILED",
                    "message": preflight.message,
                    "category": "PREFLIGHT_REJECT",
                }

    live_tts_requested = bool(voice_slot.get("live_tts_requested"))
    voice_slot["approval"] = evaluate_voice_approval_gate(
        voice_slot,
        session,
        live_tts_requested=live_tts_requested,
        project_root=project_root,
    )

    category_runtime[CATEGORY_VOICE] = voice_slot
    category_runtime[CATEGORY_VIDEO] = video_slot_before
    runtime["category_runtime"] = category_runtime

    operations = dict(_dict(runtime.get("operations")))
    operations["voice_preflight_dry_run"] = {
        "slot_version": SLOT_VERSION,
        "evaluated_at": evaluated_at,
        "status": voice_slot.get("status"),
        "executed": bool(voice_slot.get("executed")) if completed_run else False,
        "dry_run": voice_slot.get("dry_run") if completed_run else True,
        "live_tts": voice_slot.get("live_tts") if completed_run else False,
        "provider": voice_slot.get("provider"),
        "segment_count": voice_slot.get("segment_count", 0),
        "narration_skipped": bundle.skipped,
        "preflight_ready": bool(_dict(voice_slot.get("voice_preflight")).get("ready")),
        "reject_code": _dict(voice_slot.get("error")).get("code"),
        "completed_run_preserved": completed_run,
    }
    operations["voice_approval_gate"] = build_voice_approval_operations_mirror(
        voice_slot,
        live_tts_requested=live_tts_requested,
        evaluated_at=evaluated_at,
    )
    runtime["operations"] = operations
    return runtime


__all__ = [
    "SLOT_VERSION",
    "NOTE_NO_NARRATION",
    "NOTE_PREFLIGHT_READY",
    "NOTE_KEY_MISSING",
    "apply_voice_preflight_dry_run",
]
