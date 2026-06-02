"""
Provider category constants for category-agnostic Provider Runtime (Phase 10I / 11G).

10I executes video_generation only; 11G adds multi-category shell placeholders for
voice, music, subtitles, and assembly without executing those categories.
"""

from __future__ import annotations

from typing import Any

CATEGORY_VIDEO = "video_generation"
CATEGORY_VOICE = "voice_generation"
CATEGORY_MUSIC = "music_generation"
CATEGORY_SUBTITLES = "subtitles"
CATEGORY_SUBTITLE_GENERATION = "subtitle_generation"
CATEGORY_ASSEMBLY = "assembly"
CATEGORY_ASSEMBLY_GENERATION = "assembly_generation"

# Canonical subtitle storage / artifact path key (11I-2).
SUBTITLE_CANONICAL_CATEGORY = CATEGORY_SUBTITLE_GENERATION
SUBTITLE_LEGACY_CATEGORY = CATEGORY_SUBTITLES
SUBTITLE_CATEGORY_ALIASES = frozenset({CATEGORY_SUBTITLES, CATEGORY_SUBTITLE_GENERATION})

# Canonical assembly storage / artifact path key (11J-2).
ASSEMBLY_CANONICAL_CATEGORY = CATEGORY_ASSEMBLY_GENERATION
ASSEMBLY_LEGACY_CATEGORY = CATEGORY_ASSEMBLY
ASSEMBLY_CATEGORY_ALIASES = frozenset({CATEGORY_ASSEMBLY, CATEGORY_ASSEMBLY_GENERATION})

# Legacy 10I slots — preserved for backward-compatible reads only.
CATEGORY_IMAGE = "image_generation"
CATEGORY_PUBLISHING = "publishing"

MEDIA_CATEGORIES = (
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
    CATEGORY_MUSIC,
    CATEGORY_SUBTITLES,
    CATEGORY_ASSEMBLY,
)

LEGACY_MEDIA_CATEGORIES = (
    CATEGORY_IMAGE,
    CATEGORY_PUBLISHING,
)

PROVIDER_CATEGORIES = MEDIA_CATEGORIES + LEGACY_MEDIA_CATEGORIES

REGISTRY_TO_RUNTIME_CATEGORY = {
    "video": CATEGORY_VIDEO,
    "voice": CATEGORY_VOICE,
    "music": CATEGORY_MUSIC,
    "subtitles": CATEGORY_SUBTITLES,
    "subtitle_generation": CATEGORY_SUBTITLE_GENERATION,
    "assembly": CATEGORY_ASSEMBLY,
    "assembly_generation": CATEGORY_ASSEMBLY_GENERATION,
}

RUNTIME_CATEGORY_PLANNED_DEFAULTS: dict[str, dict[str, str]] = {
    CATEGORY_VOICE: {"provider": "elevenlabs", "mode": "api", "status": "planned"},
    CATEGORY_MUSIC: {"provider": "suno", "mode": "api", "status": "planned"},
    CATEGORY_SUBTITLES: {"provider": "local_subtitle_runtime", "mode": "local", "status": "planned"},
    CATEGORY_ASSEMBLY: {"provider": "local_assembly_runtime", "mode": "local", "status": "planned"},
    CATEGORY_IMAGE: {"provider": "generic", "mode": "api", "status": "planned"},
    CATEGORY_PUBLISHING: {"provider": "generic", "mode": "api", "status": "planned"},
}

PROVIDER_ALIASES: dict[str, str] = {
    "hailuo": "hailuo_browser",
    "hailuo_browser": "hailuo_browser",
    "runway_browser": "runway_browser",
    "runway_api": "runway",
    "runway": "runway",
    "minimax_api": "minimax_api",
    "kling": "kling",
    "veo": "veo",
}


def normalize_provider_key(provider: str) -> str:
    key = str(provider or "").strip().lower()
    return PROVIDER_ALIASES.get(key, key)


def default_category_runtime_slots() -> dict[str, dict[str, Any]]:
    """Delegate to 11G shell defaults (lazy import avoids circular dependency)."""
    from content_brain.execution.category_runtime_compat import default_category_runtime_slots as _shell_defaults

    return _shell_defaults()


def default_artifacts_by_category() -> dict[str, list[Any]]:
    from content_brain.execution.category_runtime_compat import default_artifacts_by_category as _shell_artifacts

    return _shell_artifacts()


__all__ = [
    "CATEGORY_VIDEO",
    "CATEGORY_VOICE",
    "CATEGORY_MUSIC",
    "CATEGORY_SUBTITLES",
    "CATEGORY_SUBTITLE_GENERATION",
    "CATEGORY_ASSEMBLY_GENERATION",
    "SUBTITLE_CANONICAL_CATEGORY",
    "SUBTITLE_LEGACY_CATEGORY",
    "SUBTITLE_CATEGORY_ALIASES",
    "ASSEMBLY_CANONICAL_CATEGORY",
    "ASSEMBLY_LEGACY_CATEGORY",
    "ASSEMBLY_CATEGORY_ALIASES",
    "CATEGORY_ASSEMBLY",
    "CATEGORY_IMAGE",
    "CATEGORY_PUBLISHING",
    "MEDIA_CATEGORIES",
    "LEGACY_MEDIA_CATEGORIES",
    "PROVIDER_CATEGORIES",
    "REGISTRY_TO_RUNTIME_CATEGORY",
    "RUNTIME_CATEGORY_PLANNED_DEFAULTS",
    "PROVIDER_ALIASES",
    "normalize_provider_key",
    "default_category_runtime_slots",
    "default_artifacts_by_category",
]
