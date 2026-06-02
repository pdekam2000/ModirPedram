"""
Phase 11I-2 — dry-run subtitle preflight wiring for subtitle_generation runtime slot.

Evaluates voice/narration source availability only.
Never generates subtitle files, calls FFmpeg, or modifies voice/video execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import (
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    SUBTITLE_ARTIFACT_CATEGORY,
    SUBTITLE_PROVIDER,
    SUBTITLE_SUPPORTED_FORMATS,
    sync_subtitle_category_aliases,
)
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_narration_adapter import SessionNarrationAdapter

SLOT_VERSION = "11i2_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

SOURCE_NARRATION_WITH_TIMING = "narration_with_timing"
SOURCE_NARRATION_TEXT_ONLY = "narration_text_only"
SOURCE_UNAVAILABLE = "unavailable"

NOTE_NO_SOURCE = "No subtitle source available"
NOTE_TEXT_SOURCE = "Narration text available for subtitle generation"
NOTE_TIMING_SOURCE = "Voice manifest available with timing metadata"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _load_voice_manifest(voice_slot: dict[str, Any]) -> dict[str, Any] | None:
    manifest = _dict(voice_slot.get("voice_manifest"))
    if manifest:
        return manifest

    manifest_path = str(voice_slot.get("voice_manifest_path") or "").strip()
    if not manifest_path:
        return None

    path = Path(manifest_path)
    if not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _voice_has_timing_source(voice_slot: dict[str, Any]) -> bool:
    status = str(voice_slot.get("status") or "").lower()
    if status != STATUS_COMPLETED:
        return False

    manifest = _load_voice_manifest(voice_slot)
    if not manifest:
        return False

    files = manifest.get("files")
    if isinstance(files, list) and files:
        return True

    if manifest.get("duration_seconds") is not None:
        return True

    return bool(manifest.get("tts_executed"))


def resolve_subtitle_source_type(session: dict[str, Any], voice_slot: dict[str, Any]) -> str:
    """Determine subtitle source mode without generating files."""
    if _voice_has_timing_source(voice_slot):
        return SOURCE_NARRATION_WITH_TIMING

    adapter = SessionNarrationAdapter()
    bundle = adapter.build(session)
    if not bundle.skipped and bundle.segment_count > 0:
        return SOURCE_NARRATION_TEXT_ONLY

    return SOURCE_UNAVAILABLE


def _is_completed_executed_subtitle_run(subtitle_slot: dict[str, Any]) -> bool:
    return (
        str(subtitle_slot.get("status") or "").lower() == STATUS_COMPLETED
        and subtitle_slot.get("executed") is True
    )


def apply_subtitle_preflight_dry_run(
    session: dict[str, Any],
    execution_runtime: dict[str, Any],
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Evaluate subtitle preflight and update subtitle_generation slot metadata only.

    Does not modify voice_generation, video_generation, or other category slots.
    """
    _ = project_root  # reserved for future path resolution
    runtime = dict(_dict(execution_runtime))
    category_runtime = dict(_dict(runtime.get("category_runtime")))
    sync_subtitle_category_aliases(category_runtime)

    video_slot_before = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
    voice_slot_before = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
    subtitle_slot = dict(
        _dict(
            category_runtime.get(CATEGORY_SUBTITLE_GENERATION)
            or category_runtime.get("subtitles")
        )
    )
    completed_run = _is_completed_executed_subtitle_run(subtitle_slot)

    evaluated_at = _now()
    voice_status = str(voice_slot_before.get("status") or "").lower()
    source_type = resolve_subtitle_source_type(session, voice_slot_before)
    source_ready = source_type != SOURCE_UNAVAILABLE

    subtitle_slot["category_name"] = CATEGORY_SUBTITLE_GENERATION
    subtitle_slot["provider"] = SUBTITLE_PROVIDER
    subtitle_slot["supported_formats"] = list(SUBTITLE_SUPPORTED_FORMATS)
    if not completed_run:
        subtitle_slot["executed"] = False
        subtitle_slot["dry_run"] = True
    subtitle_slot["preflight_evaluated_at"] = evaluated_at
    subtitle_slot["slot_version"] = SLOT_VERSION
    subtitle_slot["updated_at"] = evaluated_at
    subtitle_slot.setdefault("created_at", evaluated_at)
    if not completed_run:
        subtitle_slot["artifacts"] = list(subtitle_slot.get("artifacts") or [])
        subtitle_slot["validation_status"] = None
        subtitle_slot["error"] = None

    preflight_summary = {
        "slot_version": SLOT_VERSION,
        "evaluated_at": evaluated_at,
        "voice_status": voice_status,
        "source_type": source_type,
        "source_ready": source_ready,
        "artifact_category": SUBTITLE_ARTIFACT_CATEGORY,
        "supported_formats": list(SUBTITLE_SUPPORTED_FORMATS),
        "files_generated": bool(completed_run),
    }
    subtitle_slot["subtitle_preflight"] = preflight_summary

    if completed_run:
        subtitle_slot["source_type"] = subtitle_slot.get("source_type") or source_type
        subtitle_slot["source_ready"] = True
    elif source_ready:
        subtitle_slot["status"] = STATUS_PENDING
        subtitle_slot["source_type"] = source_type
        subtitle_slot["source_ready"] = True
        subtitle_slot["runtime_notes"] = [
            NOTE_TIMING_SOURCE if source_type == SOURCE_NARRATION_WITH_TIMING else NOTE_TEXT_SOURCE
        ]
    else:
        subtitle_slot["status"] = STATUS_SKIPPED
        subtitle_slot["source_type"] = SOURCE_UNAVAILABLE
        subtitle_slot["source_ready"] = False
        subtitle_slot["runtime_notes"] = [NOTE_NO_SOURCE]

    category_runtime[CATEGORY_SUBTITLE_GENERATION] = subtitle_slot
    category_runtime["subtitles"] = subtitle_slot
    category_runtime[CATEGORY_VIDEO] = video_slot_before
    category_runtime[CATEGORY_VOICE] = voice_slot_before
    runtime["category_runtime"] = category_runtime

    operations = dict(_dict(runtime.get("operations")))
    operations["subtitle_preflight_dry_run"] = {
        **preflight_summary,
        "status": subtitle_slot.get("status"),
        "executed": bool(subtitle_slot.get("executed")) if completed_run else False,
        "dry_run": subtitle_slot.get("dry_run") if completed_run else True,
        "completed_run_preserved": completed_run,
    }
    runtime["operations"] = operations
    return runtime


__all__ = [
    "SLOT_VERSION",
    "SOURCE_NARRATION_WITH_TIMING",
    "SOURCE_NARRATION_TEXT_ONLY",
    "SOURCE_UNAVAILABLE",
    "NOTE_NO_SOURCE",
    "NOTE_TEXT_SOURCE",
    "NOTE_TIMING_SOURCE",
    "resolve_subtitle_source_type",
    "apply_subtitle_preflight_dry_run",
]
