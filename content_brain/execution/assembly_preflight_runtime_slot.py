"""
Phase 11J-2 — dry-run assembly preflight wiring for the assembly_generation slot.

Inspects existing video/voice/subtitle category slots (read-only), detects which
upstream artifacts are present on disk, builds an input summary, and updates ONLY
the assembly_generation slot. Never generates media, never calls FFmpeg, and never
mutates the video/voice/subtitle slots.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from content_brain.execution.assembly_approval_guard import (
    AssemblyRunRequestContext,
    evaluate_assembly_approval_gate,
)
from content_brain.execution.assembly_artifact_validator import AssemblyArtifactValidator
from content_brain.execution.assembly_models import (
    ASSEMBLY_PROVIDER,
    EXPECTED_OUTPUT,
    MODE_VIDEO_VOICE_SUBTITLE,
    SUBTITLE_MODE_BURN_IN,
    VALIDATION_FAILED,
    VALIDATION_PARTIAL,
    VALIDATION_READY,
)
from content_brain.execution.category_runtime_compat import (
    ASSEMBLY_ARTIFACT_CATEGORY,
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    sync_assembly_category_aliases,
    sync_subtitle_category_aliases,
)
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)

SLOT_VERSION = "11j2_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

NOTE_READY = "Video, voice, and subtitle artifacts available for assembly"
NOTE_PARTIAL = "Some upstream artifacts available; assembly not yet ready"
NOTE_NO_INPUTS = "No upstream video/voice/subtitle artifacts available"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _collect_artifacts(slot: dict[str, Any], by_category: dict[str, Any], *keys: str) -> list[Any]:
    artifacts: list[Any] = []
    for key in keys:
        artifacts.extend(_list(by_category.get(key)))
    artifacts.extend(_list(slot.get("artifacts")))
    return artifacts


def _manifest_path(slot: dict[str, Any], *fields: str) -> str | None:
    for field_name in fields:
        value = str(slot.get(field_name) or "").strip()
        if value:
            return value
    return None


def _is_completed_executed_assembly(slot: dict[str, Any]) -> bool:
    return (
        str(slot.get("status") or "").lower() == STATUS_COMPLETED
        and slot.get("executed") is True
    )


def apply_assembly_preflight_dry_run(
    session: dict[str, Any],
    execution_runtime: dict[str, Any],
    *,
    require_subtitles: bool = True,
) -> dict[str, Any]:
    """
    Evaluate assembly preflight and update the assembly_generation slot only.

    Does not modify video_generation, voice_generation, or subtitle_generation slots.
    """
    _ = session  # reserved; current readiness derives from runtime artifacts only
    runtime = dict(_dict(execution_runtime))
    category_runtime = dict(_dict(runtime.get("category_runtime")))
    sync_subtitle_category_aliases(category_runtime)
    sync_assembly_category_aliases(category_runtime)
    by_category = _dict(runtime.get("artifacts_by_category"))

    video_slot_before = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
    voice_slot_before = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
    subtitle_slot_before = dict(
        _dict(
            category_runtime.get(CATEGORY_SUBTITLE_GENERATION)
            or category_runtime.get("subtitles")
        )
    )
    assembly_slot = dict(
        _dict(
            category_runtime.get(CATEGORY_ASSEMBLY_GENERATION)
            or category_runtime.get("assembly")
        )
    )
    completed_run = _is_completed_executed_assembly(assembly_slot)

    video_artifacts = _collect_artifacts(video_slot_before, by_category, CATEGORY_VIDEO)
    voice_artifacts = _collect_artifacts(voice_slot_before, by_category, CATEGORY_VOICE)
    subtitle_artifacts = _collect_artifacts(
        subtitle_slot_before, by_category, CATEGORY_SUBTITLE_GENERATION, "subtitles"
    )

    video_manifest_path = _manifest_path(video_slot_before, "video_manifest_path", "manifest_path")
    voice_manifest_path = _manifest_path(voice_slot_before, "voice_manifest_path", "manifest_path")
    subtitle_manifest_path = _manifest_path(subtitle_slot_before, "manifest_path")

    validator = AssemblyArtifactValidator()
    result = validator.validate(
        video_artifacts=video_artifacts,
        voice_artifacts=voice_artifacts,
        subtitle_artifacts=subtitle_artifacts,
        video_manifest_path=video_manifest_path,
        voice_manifest_path=voice_manifest_path,
        subtitle_manifest_path=subtitle_manifest_path,
        require_subtitles=require_subtitles,
    )

    evaluated_at = _now()
    input_summary = {
        "video_count": result.video_count,
        "voice_count": result.voice_count,
        "subtitle_count": result.subtitle_count,
        "video_ok": result.video_ok,
        "voice_ok": result.voice_ok,
        "subtitle_ok": result.subtitle_ok,
        "missing": list(result.missing),
    }

    assembly_slot["category_name"] = CATEGORY_ASSEMBLY_GENERATION
    assembly_slot["provider"] = ASSEMBLY_PROVIDER
    assembly_slot["assembly_mode"] = assembly_slot.get("assembly_mode") or MODE_VIDEO_VOICE_SUBTITLE
    assembly_slot["subtitle_mode"] = assembly_slot.get("subtitle_mode") or SUBTITLE_MODE_BURN_IN
    assembly_slot["validation_status"] = result.status
    assembly_slot["input_summary"] = input_summary
    assembly_slot.setdefault("output_summary", None)
    assembly_slot.setdefault("manifest_path", None)
    assembly_slot["expected_output"] = assembly_slot.get("expected_output") or EXPECTED_OUTPUT
    assembly_slot["preflight_evaluated_at"] = evaluated_at
    assembly_slot["slot_version"] = SLOT_VERSION
    assembly_slot["updated_at"] = evaluated_at
    assembly_slot.setdefault("created_at", evaluated_at)
    if not completed_run:
        assembly_slot["executed"] = False
        assembly_slot["dry_run"] = True
        assembly_slot["artifacts"] = list(assembly_slot.get("artifacts") or [])
        assembly_slot["error"] = None

    preflight_summary = {
        "slot_version": SLOT_VERSION,
        "evaluated_at": evaluated_at,
        "validation_status": result.status,
        "artifact_category": ASSEMBLY_ARTIFACT_CATEGORY,
        "input_summary": input_summary,
        "warnings": list(result.warnings),
        "reject_reasons": list(result.reject_reasons),
        "files_generated": bool(completed_run),
    }
    assembly_slot["assembly_preflight"] = preflight_summary

    request = AssemblyRunRequestContext(
        dry_run=True,
        real_assembly_requested=bool(assembly_slot.get("real_assembly_requested")),
    )
    assembly_slot["approval"] = evaluate_assembly_approval_gate(
        assembly_slot,
        None,
        request,
        session=session,
    )

    if completed_run:
        pass
    elif result.status == VALIDATION_READY:
        assembly_slot["status"] = STATUS_PENDING
        assembly_slot["runtime_notes"] = [NOTE_READY]
    elif result.status == VALIDATION_PARTIAL:
        assembly_slot["status"] = STATUS_SKIPPED
        assembly_slot["runtime_notes"] = [NOTE_PARTIAL]
    else:  # VALIDATION_FAILED
        assembly_slot["status"] = STATUS_SKIPPED
        assembly_slot["runtime_notes"] = [NOTE_NO_INPUTS]

    category_runtime[CATEGORY_ASSEMBLY_GENERATION] = assembly_slot
    category_runtime["assembly"] = assembly_slot
    category_runtime[CATEGORY_VIDEO] = video_slot_before
    category_runtime[CATEGORY_VOICE] = voice_slot_before
    if CATEGORY_SUBTITLE_GENERATION in category_runtime or "subtitles" in category_runtime:
        category_runtime[CATEGORY_SUBTITLE_GENERATION] = subtitle_slot_before
        category_runtime["subtitles"] = subtitle_slot_before
    runtime["category_runtime"] = category_runtime

    operations = dict(_dict(runtime.get("operations")))
    operations["assembly_preflight_dry_run"] = {
        **preflight_summary,
        "status": assembly_slot.get("status"),
        "executed": bool(assembly_slot.get("executed")),
        "dry_run": bool(assembly_slot.get("dry_run")),
        "completed_run_preserved": completed_run,
    }
    runtime["operations"] = operations
    return runtime


__all__ = [
    "SLOT_VERSION",
    "NOTE_READY",
    "NOTE_PARTIAL",
    "NOTE_NO_INPUTS",
    "apply_assembly_preflight_dry_run",
]
