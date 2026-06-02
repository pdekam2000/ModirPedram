"""
Phase 11G — multi-category runtime shell compatibility helpers.

Provides safe read/write normalization for per-category runtime slots without
executing voice, music, subtitle, or assembly providers.
"""

from __future__ import annotations

from typing import Any

from content_brain.execution.assembly_approval_guard import default_assembly_approval_block
from content_brain.execution.provider_categories import (
    ASSEMBLY_CANONICAL_CATEGORY,
    ASSEMBLY_CATEGORY_ALIASES,
    ASSEMBLY_LEGACY_CATEGORY,
    CATEGORY_ASSEMBLY,
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_MUSIC,
    CATEGORY_SUBTITLES,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
    LEGACY_MEDIA_CATEGORIES,
    MEDIA_CATEGORIES,
    RUNTIME_CATEGORY_PLANNED_DEFAULTS,
    SUBTITLE_CANONICAL_CATEGORY,
    SUBTITLE_CATEGORY_ALIASES,
    SUBTITLE_LEGACY_CATEGORY,
)

SHELL_VERSION = "11g_v1"
SUBTITLE_SLOT_VERSION = "11i2_v1"
SUBTITLE_PROVIDER = "local_subtitle_runtime"
SUBTITLE_SUPPORTED_FORMATS = ("srt", "ass", "vtt")
SUBTITLE_ARTIFACT_CATEGORY = SUBTITLE_CANONICAL_CATEGORY

ASSEMBLY_SLOT_VERSION = "11j2_v1"
ASSEMBLY_PROVIDER = "local_assembly_runtime"
ASSEMBLY_ARTIFACT_CATEGORY = ASSEMBLY_CANONICAL_CATEGORY

# Canonical category status values (11G shell).
STATUS_PLANNED = "planned"
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

CATEGORY_STATUSES = (
    STATUS_PLANNED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_SKIPPED,
)

# Short display names keyed by runtime category key.
CATEGORY_SHORT_NAMES: dict[str, str] = {
    CATEGORY_VIDEO: "video",
    CATEGORY_VOICE: "voice",
    CATEGORY_MUSIC: "music",
    CATEGORY_SUBTITLES: "subtitles",
    CATEGORY_SUBTITLE_GENERATION: "subtitle_generation",
    CATEGORY_ASSEMBLY: "assembly",
    CATEGORY_ASSEMBLY_GENERATION: "assembly_generation",
}

# Future routing hooks — documentation only; modules are not implemented in 11G.
FUTURE_CATEGORY_ROUTERS: dict[str, str] = {
    CATEGORY_VOICE: "content_brain.execution.voice_provider_router.VoiceProviderRouter",
    CATEGORY_MUSIC: "content_brain.execution.music_provider_router.MusicProviderRouter",
    CATEGORY_SUBTITLES: "content_brain.execution.subtitle_preflight_runtime_slot.apply_subtitle_preflight_dry_run",
    CATEGORY_SUBTITLE_GENERATION: "content_brain.execution.subtitle_preflight_runtime_slot.apply_subtitle_preflight_dry_run",
    CATEGORY_ASSEMBLY: "content_brain.execution.assembly_preflight_runtime_slot.apply_assembly_preflight_dry_run",
    CATEGORY_ASSEMBLY_GENERATION: "content_brain.execution.assembly_preflight_runtime_slot.apply_assembly_preflight_dry_run",
}

_LEGACY_STATE_TO_STATUS: dict[str, str] = {
    "not_started": STATUS_PLANNED,
    "DISPATCHED": STATUS_PENDING,
    "RUNNING": STATUS_RUNNING,
    "COMPLETED": STATUS_COMPLETED,
    "FAILED": STATUS_FAILED,
    "CANCELLED": STATUS_FAILED,
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def category_short_name(category_key: str) -> str:
    if category_key in SUBTITLE_CATEGORY_ALIASES:
        return CATEGORY_SUBTITLE_GENERATION
    if category_key in ASSEMBLY_CATEGORY_ALIASES:
        return CATEGORY_ASSEMBLY_GENERATION
    return CATEGORY_SHORT_NAMES.get(category_key, str(category_key or "unknown"))


def is_subtitle_category_key(category_key: str) -> bool:
    return str(category_key or "") in SUBTITLE_CATEGORY_ALIASES


def is_assembly_category_key(category_key: str) -> bool:
    return str(category_key or "") in ASSEMBLY_CATEGORY_ALIASES


def default_subtitle_category_slot(*, status: str = STATUS_PLANNED) -> dict[str, Any]:
    """Return the 11I-2 subtitle_generation slot schema defaults."""
    base = default_category_slot(CATEGORY_SUBTITLES, status=status, provider=SUBTITLE_PROVIDER)
    base["category_name"] = CATEGORY_SUBTITLE_GENERATION
    base["source_type"] = None
    base["source_ready"] = False
    base["supported_formats"] = list(SUBTITLE_SUPPORTED_FORMATS)
    base["validation_status"] = None
    base["created_at"] = None
    base["updated_at"] = None
    base["subtitle_preflight"] = None
    base["slot_version"] = SUBTITLE_SLOT_VERSION
    return base


def sync_subtitle_category_aliases(raw_slots: dict[str, Any]) -> dict[str, Any]:
    """
    Merge legacy `subtitles` and canonical `subtitle_generation` into one slot.

    Both keys reference the same dict object — no conflicting duplicates.
    """
    legacy = raw_slots.get(SUBTITLE_LEGACY_CATEGORY)
    canonical = raw_slots.get(SUBTITLE_CANONICAL_CATEGORY)

    if legacy is not None and canonical is not None and legacy is not canonical:
        merged = default_subtitle_category_slot(status=resolve_category_status(canonical or legacy))
        merged.update(dict(_dict(legacy)))
        merged.update(dict(_dict(canonical)))
        merged["category_name"] = CATEGORY_SUBTITLE_GENERATION
        raw_slots[SUBTITLE_LEGACY_CATEGORY] = merged
        raw_slots[SUBTITLE_CANONICAL_CATEGORY] = merged
    elif legacy is not None and canonical is None:
        slot = dict(_dict(legacy))
        normalized = normalize_category_slot(slot, category_key=CATEGORY_SUBTITLES)
        for key, value in normalized.items():
            if key not in slot or slot.get(key) in (None, "", []):
                slot[key] = value
        slot["category_name"] = CATEGORY_SUBTITLE_GENERATION
        slot.setdefault("supported_formats", list(SUBTITLE_SUPPORTED_FORMATS))
        raw_slots[SUBTITLE_LEGACY_CATEGORY] = slot
        raw_slots[SUBTITLE_CANONICAL_CATEGORY] = slot
    elif canonical is not None and legacy is None:
        slot = dict(_dict(canonical))
        slot["category_name"] = CATEGORY_SUBTITLE_GENERATION
        raw_slots[SUBTITLE_CANONICAL_CATEGORY] = slot
        raw_slots[SUBTITLE_LEGACY_CATEGORY] = slot
    elif SUBTITLE_LEGACY_CATEGORY not in raw_slots:
        slot = default_subtitle_category_slot()
        raw_slots[SUBTITLE_LEGACY_CATEGORY] = slot
        raw_slots[SUBTITLE_CANONICAL_CATEGORY] = slot
    else:
        slot = raw_slots[SUBTITLE_LEGACY_CATEGORY]
        raw_slots[SUBTITLE_CANONICAL_CATEGORY] = slot

    return raw_slots


def default_assembly_category_slot(*, status: str = STATUS_PLANNED) -> dict[str, Any]:
    """Return the 11J-2 assembly_generation slot schema defaults."""
    base = default_category_slot(CATEGORY_ASSEMBLY, status=status, provider=ASSEMBLY_PROVIDER)
    base["category_name"] = CATEGORY_ASSEMBLY_GENERATION
    base["validation_status"] = None
    base["input_summary"] = None
    base["output_summary"] = None
    base["assembly_mode"] = None
    base["subtitle_mode"] = None
    base["manifest_path"] = None
    base["created_at"] = None
    base["updated_at"] = None
    base["assembly_preflight"] = None
    base["executed"] = False
    base["dry_run"] = True
    base["real_assembly_requested"] = False
    base["slot_version"] = ASSEMBLY_SLOT_VERSION
    base["approval"] = default_assembly_approval_block()
    return base


def sync_assembly_category_aliases(raw_slots: dict[str, Any]) -> dict[str, Any]:
    """
    Merge legacy `assembly` and canonical `assembly_generation` into one slot.

    Both keys reference the same dict object — no conflicting duplicates.
    """
    legacy = raw_slots.get(ASSEMBLY_LEGACY_CATEGORY)
    canonical = raw_slots.get(ASSEMBLY_CANONICAL_CATEGORY)

    if legacy is not None and canonical is not None and legacy is not canonical:
        merged = default_assembly_category_slot(status=resolve_category_status(canonical or legacy))
        merged.update(dict(_dict(legacy)))
        merged.update(dict(_dict(canonical)))
        merged["category_name"] = CATEGORY_ASSEMBLY_GENERATION
        raw_slots[ASSEMBLY_LEGACY_CATEGORY] = merged
        raw_slots[ASSEMBLY_CANONICAL_CATEGORY] = merged
    elif legacy is not None and canonical is None:
        slot = dict(_dict(legacy))
        normalized = normalize_category_slot(slot, category_key=CATEGORY_ASSEMBLY)
        for key, value in normalized.items():
            if key not in slot or slot.get(key) in (None, "", []):
                slot[key] = value
        slot["category_name"] = CATEGORY_ASSEMBLY_GENERATION
        raw_slots[ASSEMBLY_LEGACY_CATEGORY] = slot
        raw_slots[ASSEMBLY_CANONICAL_CATEGORY] = slot
    elif canonical is not None and legacy is None:
        slot = dict(_dict(canonical))
        slot["category_name"] = CATEGORY_ASSEMBLY_GENERATION
        raw_slots[ASSEMBLY_CANONICAL_CATEGORY] = slot
        raw_slots[ASSEMBLY_LEGACY_CATEGORY] = slot
    elif ASSEMBLY_LEGACY_CATEGORY not in raw_slots:
        slot = default_assembly_category_slot()
        raw_slots[ASSEMBLY_LEGACY_CATEGORY] = slot
        raw_slots[ASSEMBLY_CANONICAL_CATEGORY] = slot
    else:
        slot = raw_slots[ASSEMBLY_LEGACY_CATEGORY]
        raw_slots[ASSEMBLY_CANONICAL_CATEGORY] = slot

    return raw_slots


def default_category_slot(
    category_key: str,
    *,
    status: str = STATUS_PLANNED,
    provider: str | None = None,
) -> dict[str, Any]:
    """Return a normalized empty slot for one media category."""
    planned = RUNTIME_CATEGORY_PLANNED_DEFAULTS.get(category_key, {})
    return {
        "category_name": category_short_name(category_key),
        "status": status,
        "provider": provider if provider is not None else planned.get("provider"),
        "artifacts": [],
        "error": None,
        "started_at": None,
        "completed_at": None,
        "duration_seconds": None,
        "cost_estimate": None,
        "runtime_notes": [],
        # Legacy 10I field — preserved for existing video dispatch paths.
        "state": "not_started",
        "executed": False,
        "dry_run": False,
        "live_tts": False,
    }


def default_category_runtime_slots() -> dict[str, dict[str, Any]]:
    """Build default multi-category shell slots (11G). Video remains the only active category."""
    slots: dict[str, dict[str, Any]] = {}
    for category in MEDIA_CATEGORIES:
        if category == CATEGORY_VIDEO:
            slots[category] = default_category_slot(category, status=STATUS_PENDING)
            slots[category]["state"] = "not_started"
        elif category == CATEGORY_SUBTITLES:
            slots[category] = default_subtitle_category_slot(status=STATUS_PLANNED)
        elif category == CATEGORY_ASSEMBLY:
            slots[category] = default_assembly_category_slot(status=STATUS_PLANNED)
        else:
            slots[category] = default_category_slot(category, status=STATUS_PLANNED)
    return slots


def default_artifacts_by_category() -> dict[str, list[Any]]:
    artifacts: dict[str, list[Any]] = {category: [] for category in MEDIA_CATEGORIES}
    for legacy in LEGACY_MEDIA_CATEGORIES:
        artifacts.setdefault(legacy, [])
    return artifacts


def resolve_category_status(raw_slot: dict[str, Any]) -> str:
    """Map legacy slot fields to canonical 11G status."""
    explicit = str(raw_slot.get("status") or "").strip().lower()
    if explicit in CATEGORY_STATUSES:
        return explicit

    legacy_status = str(raw_slot.get("status") or "").strip().lower()
    if legacy_status == "active":
        state = str(raw_slot.get("state") or "").strip()
        if state in _LEGACY_STATE_TO_STATUS:
            return _LEGACY_STATE_TO_STATUS[state]
        return STATUS_RUNNING

    state = str(raw_slot.get("state") or "").strip()
    return _LEGACY_STATE_TO_STATUS.get(state, STATUS_PLANNED)


def normalize_category_slot(
    raw_slot: dict[str, Any] | None,
    *,
    category_key: str,
    artifacts: list[Any] | None = None,
) -> dict[str, Any]:
    """Safely normalize one category slot; never raises on missing fields."""
    slot = dict(_dict(raw_slot))
    base = default_category_slot(category_key)
    merged: dict[str, Any] = {**base, **slot}
    merged["category_name"] = category_short_name(category_key)
    merged["status"] = resolve_category_status(slot)
    merged["provider"] = slot.get("provider") if slot.get("provider") not in (None, "") else base.get("provider")
    merged["artifacts"] = _list(artifacts if artifacts is not None else slot.get("artifacts"))
    merged["error"] = slot.get("error")
    merged["started_at"] = slot.get("started_at")
    merged["completed_at"] = slot.get("completed_at")
    merged["duration_seconds"] = slot.get("duration_seconds")
    merged["cost_estimate"] = slot.get("cost_estimate")
    merged["runtime_notes"] = _list(slot.get("runtime_notes"))
    merged["state"] = slot.get("state") or base.get("state")
    if "executed" in slot:
        merged["executed"] = bool(slot.get("executed"))
    if "dry_run" in slot:
        merged["dry_run"] = bool(slot.get("dry_run"))
    if "live_tts" in slot:
        merged["live_tts"] = bool(slot.get("live_tts"))
    if slot.get("voice_preflight") is not None:
        merged["voice_preflight"] = slot.get("voice_preflight")
    if slot.get("preflight_evaluated_at"):
        merged["preflight_evaluated_at"] = slot.get("preflight_evaluated_at")
    if slot.get("narration_adapter") is not None:
        merged["narration_adapter"] = slot.get("narration_adapter")
    if slot.get("segment_count") is not None:
        merged["segment_count"] = slot.get("segment_count")
    if slot.get("approval") is not None:
        merged["approval"] = slot.get("approval")
    if slot.get("live_tts_requested") is not None:
        merged["live_tts_requested"] = bool(slot.get("live_tts_requested"))
    if is_subtitle_category_key(category_key) or slot.get("source_type") is not None:
        merged["category_name"] = CATEGORY_SUBTITLE_GENERATION
        merged["source_type"] = slot.get("source_type")
        merged["source_ready"] = bool(slot.get("source_ready"))
        merged["supported_formats"] = _list(slot.get("supported_formats")) or list(SUBTITLE_SUPPORTED_FORMATS)
        merged["validation_status"] = slot.get("validation_status")
        merged["created_at"] = slot.get("created_at")
        merged["updated_at"] = slot.get("updated_at")
        if slot.get("subtitle_preflight") is not None:
            merged["subtitle_preflight"] = slot.get("subtitle_preflight")
        if slot.get("preflight_evaluated_at"):
            merged["preflight_evaluated_at"] = slot.get("preflight_evaluated_at")
        if slot.get("slot_version"):
            merged["slot_version"] = slot.get("slot_version")
    if is_assembly_category_key(category_key) or slot.get("assembly_mode") is not None or slot.get("assembly_preflight") is not None:
        merged["category_name"] = CATEGORY_ASSEMBLY_GENERATION
        merged["validation_status"] = slot.get("validation_status")
        merged["input_summary"] = slot.get("input_summary")
        merged["output_summary"] = slot.get("output_summary")
        merged["assembly_mode"] = slot.get("assembly_mode")
        merged["subtitle_mode"] = slot.get("subtitle_mode")
        merged["manifest_path"] = slot.get("manifest_path")
        merged["created_at"] = slot.get("created_at")
        merged["updated_at"] = slot.get("updated_at")
        merged.setdefault("executed", False)
        if "dry_run" not in slot:
            merged["dry_run"] = True
        if slot.get("assembly_preflight") is not None:
            merged["assembly_preflight"] = slot.get("assembly_preflight")
        if slot.get("preflight_evaluated_at"):
            merged["preflight_evaluated_at"] = slot.get("preflight_evaluated_at")
        if slot.get("slot_version"):
            merged["slot_version"] = slot.get("slot_version")
        if slot.get("real_assembly_requested") is not None:
            merged["real_assembly_requested"] = bool(slot.get("real_assembly_requested"))
        if slot.get("approval") is not None:
            merged["approval"] = dict(_dict(slot.get("approval")))
        elif is_assembly_category_key(category_key):
            merged["approval"] = default_assembly_approval_block()
    return merged


def normalize_category_runtime(
    execution_runtime: dict[str, Any] | None,
    *,
    include_legacy: bool = True,
) -> dict[str, dict[str, Any]]:
    """Return normalized category slots for all 11G media categories."""
    runtime = _dict(execution_runtime)
    raw_slots = dict(_dict(runtime.get("category_runtime")))
    sync_subtitle_category_aliases(raw_slots)
    sync_assembly_category_aliases(raw_slots)
    artifacts_by_category = _dict(runtime.get("artifacts_by_category"))
    normalized: dict[str, dict[str, Any]] = {}

    for category in MEDIA_CATEGORIES:
        normalized[category] = normalize_category_slot(
            raw_slots.get(category),
            category_key=category,
            artifacts=_list(artifacts_by_category.get(category)),
        )

    if include_legacy:
        for legacy_key in LEGACY_MEDIA_CATEGORIES:
            if legacy_key in raw_slots or legacy_key in artifacts_by_category:
                normalized[legacy_key] = normalize_category_slot(
                    raw_slots.get(legacy_key),
                    category_key=legacy_key,
                    artifacts=_list(artifacts_by_category.get(legacy_key)),
                )
                normalized[legacy_key]["status"] = STATUS_SKIPPED

    return normalized


def get_category_slot(
    session: dict[str, Any] | None,
    category_key: str,
    *,
    default_status: str = STATUS_PLANNED,
) -> dict[str, Any]:
    """Read one category slot from a session without raising on missing data."""
    runtime = _dict(_dict(session).get("execution_runtime"))
    raw_slots = dict(_dict(runtime.get("category_runtime")))
    if is_subtitle_category_key(category_key):
        sync_subtitle_category_aliases(raw_slots)
        storage_key = SUBTITLE_CANONICAL_CATEGORY
        artifacts = _list(
            _dict(runtime.get("artifacts_by_category")).get(SUBTITLE_CANONICAL_CATEGORY)
            or _dict(runtime.get("artifacts_by_category")).get(SUBTITLE_LEGACY_CATEGORY)
        )
        if storage_key in raw_slots or SUBTITLE_LEGACY_CATEGORY in raw_slots or artifacts:
            slot_key = storage_key if storage_key in raw_slots else SUBTITLE_LEGACY_CATEGORY
            return normalize_category_slot(raw_slots.get(slot_key), category_key=CATEGORY_SUBTITLES, artifacts=artifacts)
        return default_subtitle_category_slot(status=default_status)

    if is_assembly_category_key(category_key):
        sync_assembly_category_aliases(raw_slots)
        storage_key = ASSEMBLY_CANONICAL_CATEGORY
        artifacts = _list(
            _dict(runtime.get("artifacts_by_category")).get(ASSEMBLY_CANONICAL_CATEGORY)
            or _dict(runtime.get("artifacts_by_category")).get(ASSEMBLY_LEGACY_CATEGORY)
        )
        if storage_key in raw_slots or ASSEMBLY_LEGACY_CATEGORY in raw_slots or artifacts:
            slot_key = storage_key if storage_key in raw_slots else ASSEMBLY_LEGACY_CATEGORY
            return normalize_category_slot(raw_slots.get(slot_key), category_key=CATEGORY_ASSEMBLY, artifacts=artifacts)
        return default_assembly_category_slot(status=default_status)

    artifacts = _list(_dict(runtime.get("artifacts_by_category")).get(category_key))
    if category_key in raw_slots or artifacts:
        return normalize_category_slot(raw_slots.get(category_key), category_key=category_key, artifacts=artifacts)
    return default_category_slot(category_key, status=default_status)


def ensure_multi_category_shell(execution_runtime: dict[str, Any]) -> dict[str, Any]:
    """
    Merge 11G shell fields into execution_runtime in place.

    Does not alter video dispatch behavior — only ensures placeholder slots exist.
    """
    runtime = dict(_dict(execution_runtime))
    raw_slots = dict(_dict(runtime.get("category_runtime")))
    artifacts = dict(_dict(runtime.get("artifacts_by_category")))

    for category in MEDIA_CATEGORIES:
        if category not in raw_slots:
            if category == CATEGORY_SUBTITLES:
                raw_slots[category] = default_subtitle_category_slot(status=STATUS_PLANNED)
            elif category == CATEGORY_ASSEMBLY:
                raw_slots[category] = default_assembly_category_slot(status=STATUS_PLANNED)
            else:
                raw_slots[category] = default_category_slot(
                    category,
                    status=STATUS_PENDING if category == CATEGORY_VIDEO else STATUS_PLANNED,
                )
        else:
            normalized = normalize_category_slot(raw_slots[category], category_key=category)
            # Preserve legacy writer fields (state, artifact_count, etc.).
            merged = dict(raw_slots[category])
            for key, value in normalized.items():
                if key not in merged or merged.get(key) in (None, "", []):
                    merged[key] = value
            raw_slots[category] = merged
        artifacts.setdefault(category, [])

    for legacy in LEGACY_MEDIA_CATEGORIES:
        artifacts.setdefault(legacy, [])

    sync_subtitle_category_aliases(raw_slots)
    artifacts.setdefault(SUBTITLE_CANONICAL_CATEGORY, list(artifacts.get(CATEGORY_SUBTITLES, [])))

    sync_assembly_category_aliases(raw_slots)
    artifacts.setdefault(ASSEMBLY_CANONICAL_CATEGORY, list(artifacts.get(CATEGORY_ASSEMBLY, [])))

    runtime["category_runtime"] = raw_slots
    runtime["artifacts_by_category"] = artifacts
    runtime["multi_category_shell"] = {
        "shell_version": SHELL_VERSION,
        "media_categories": list(MEDIA_CATEGORIES),
        "future_routers": dict(FUTURE_CATEGORY_ROUTERS),
        "executable_categories_11g": [CATEGORY_VIDEO],
    }
    return runtime


def build_category_runtime_view(execution_runtime: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ordered list of category slots for API/UI consumption."""
    normalized = normalize_category_runtime(execution_runtime, include_legacy=False)

    def _canonical_key(key: str) -> str:
        if key == CATEGORY_SUBTITLES:
            return CATEGORY_SUBTITLE_GENERATION
        if key == CATEGORY_ASSEMBLY:
            return CATEGORY_ASSEMBLY_GENERATION
        return key

    return [
        {
            "category_key": _canonical_key(key),
            **normalized[key],
            "future_router": FUTURE_CATEGORY_ROUTERS.get(key)
            or FUTURE_CATEGORY_ROUTERS.get(_canonical_key(key)),
            "executable": key == CATEGORY_VIDEO,
            "executed": bool(normalized[key].get("executed")),
            "dry_run": bool(normalized[key].get("dry_run")),
        }
        for key in MEDIA_CATEGORIES
    ]


__all__ = [
    "SHELL_VERSION",
    "STATUS_PLANNED",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_SKIPPED",
    "CATEGORY_STATUSES",
    "CATEGORY_SHORT_NAMES",
    "FUTURE_CATEGORY_ROUTERS",
    "SUBTITLE_SLOT_VERSION",
    "SUBTITLE_PROVIDER",
    "SUBTITLE_SUPPORTED_FORMATS",
    "SUBTITLE_ARTIFACT_CATEGORY",
    "ASSEMBLY_SLOT_VERSION",
    "ASSEMBLY_PROVIDER",
    "ASSEMBLY_ARTIFACT_CATEGORY",
    "category_short_name",
    "is_subtitle_category_key",
    "is_assembly_category_key",
    "default_subtitle_category_slot",
    "sync_subtitle_category_aliases",
    "default_assembly_category_slot",
    "sync_assembly_category_aliases",
    "default_category_slot",
    "default_category_runtime_slots",
    "default_artifacts_by_category",
    "resolve_category_status",
    "normalize_category_slot",
    "normalize_category_runtime",
    "get_category_slot",
    "ensure_multi_category_shell",
    "build_category_runtime_view",
]
