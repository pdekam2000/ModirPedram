"""Product Studio audio source — Runway native vs ElevenLabs narration."""

from __future__ import annotations

from typing import Any

AUDIO_SOURCE_RUNWAY_NATIVE = "runway_native"
AUDIO_SOURCE_ELEVENLABS = "elevenlabs_narration"

_ELEVENLABS_ALIASES = frozenset(
    {"elevenlabs", "elevenlabs_narration", "narration", "eleven_labs"}
)


def normalize_audio_source(value: str | None) -> str:
    key = str(value or "").strip().lower()
    if key in _ELEVENLABS_ALIASES:
        return AUDIO_SOURCE_ELEVENLABS
    return AUDIO_SOURCE_RUNWAY_NATIVE


def resolve_audio_source(project_root: str | Any, preflight: dict[str, Any] | None = None) -> str:
    preflight_data = dict(preflight or {})
    if preflight_data.get("audio_source"):
        return normalize_audio_source(str(preflight_data.get("audio_source")))
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    profile = ProductChannelProfileStore(project_root).load()
    return normalize_audio_source(str(profile.get("audio_source") or AUDIO_SOURCE_RUNWAY_NATIVE))


def use_elevenlabs_narration(project_root: str | Any, preflight: dict[str, Any] | None = None) -> bool:
    return resolve_audio_source(project_root, preflight) == AUDIO_SOURCE_ELEVENLABS


def strip_runway_audio_during_assembly(project_root: str | Any, preflight: dict[str, Any] | None = None) -> bool:
    """Strip native Runway audio only when replacing with ElevenLabs narration."""
    return use_elevenlabs_narration(project_root, preflight)


__all__ = [
    "AUDIO_SOURCE_ELEVENLABS",
    "AUDIO_SOURCE_RUNWAY_NATIVE",
    "normalize_audio_source",
    "resolve_audio_source",
    "strip_runway_audio_during_assembly",
    "use_elevenlabs_narration",
]
