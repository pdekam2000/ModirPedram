"""Character performance profiles — age, personality, energy, emotion, speaking style."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.story.character_director import CharacterProfile

CHARACTER_PERFORMANCE_VERSION = "character_performance_engine_v1"

DEFAULT_PERFORMANCE: dict[str, dict[str, Any]] = {
    "whiskers": {
        "age_profile": "young",
        "personality_profile": ["playful", "curious", "brave", "excitable"],
        "energy_profile": "high",
        "emotion_profile": ["wonder", "surprise", "joy"],
        "speaking_style": "fast_excited_cartoon",
        "speed_multiplier": 1.12,
        "pitch_shift": 1.08,
        "stability": 0.28,
        "style": 0.78,
        "similarity_boost": 0.82,
    },
    "sage": {
        "age_profile": "older",
        "personality_profile": ["calm", "protective", "wise", "gentle"],
        "energy_profile": "low",
        "emotion_profile": ["caution", "warmth", "relief"],
        "speaking_style": "slow_caring_mentor",
        "speed_multiplier": 0.94,
        "pitch_shift": 0.98,
        "stability": 0.58,
        "style": 0.48,
        "similarity_boost": 0.84,
    },
    "narrator": {
        "age_profile": "adult",
        "personality_profile": ["warm", "cinematic", "storyteller"],
        "energy_profile": "medium",
        "emotion_profile": ["wonder", "tension", "relief"],
        "speaking_style": "warm_storyteller",
        "speed_multiplier": 0.98,
        "pitch_shift": 1.0,
        "stability": 0.52,
        "style": 0.50,
        "similarity_boost": 0.86,
    },
}


@dataclass
class CharacterPerformanceProfile:
    name: str
    age_profile: str
    personality_profile: list[str]
    energy_profile: str
    emotion_profile: list[str]
    speaking_style: str
    voice_modifiers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "age_profile": self.age_profile,
            "personality_profile": list(self.personality_profile),
            "energy_profile": self.energy_profile,
            "emotion_profile": list(self.emotion_profile),
            "speaking_style": self.speaking_style,
            "voice_modifiers": dict(self.voice_modifiers),
        }


def _lookup_key(name: str) -> str:
    lowered = str(name or "").strip().lower()
    if "whisker" in lowered or lowered == "cat":
        return "whiskers"
    if lowered in {"sage", "fox", "mentor"}:
        return "sage"
    if lowered == "narrator":
        return "narrator"
    return lowered


def build_character_performance_profiles(
    characters: list[CharacterProfile],
) -> list[CharacterPerformanceProfile]:
    profiles: list[CharacterPerformanceProfile] = []
    for character in characters:
        key = _lookup_key(character.name)
        base = dict(DEFAULT_PERFORMANCE.get(key) or DEFAULT_PERFORMANCE["narrator"])
        if character.age == "young":
            base["speed_multiplier"] = max(float(base.get("speed_multiplier") or 1.0), 1.05)
        if "playful" in character.personality:
            base["style"] = min(1.0, float(base.get("style") or 0.5) + 0.08)
        profiles.append(
            CharacterPerformanceProfile(
                name=character.name,
                age_profile=str(base.get("age_profile") or character.age),
                personality_profile=list(base.get("personality_profile") or character.personality),
                energy_profile=str(base.get("energy_profile") or "medium"),
                emotion_profile=list(base.get("emotion_profile") or character.emotional_traits),
                speaking_style=str(base.get("speaking_style") or character.voice_style),
                voice_modifiers={
                    "speed_multiplier": float(base.get("speed_multiplier") or 1.0),
                    "pitch_shift": float(base.get("pitch_shift") or 1.0),
                    "stability": float(base.get("stability") or 0.45),
                    "style": float(base.get("style") or 0.45),
                    "similarity_boost": float(base.get("similarity_boost") or 0.85),
                },
            )
        )
    return profiles


def performance_lookup(profiles: list[CharacterPerformanceProfile]) -> dict[str, CharacterPerformanceProfile]:
    return {profile.name.lower(): profile for profile in profiles}


def apply_performance_to_voice_settings(
    *,
    speaker: str,
    base_settings: dict[str, Any],
    performance_profiles: list[CharacterPerformanceProfile] | dict[str, CharacterPerformanceProfile],
) -> dict[str, Any]:
    lookup = performance_profiles if isinstance(performance_profiles, dict) else performance_lookup(performance_profiles)
    profile = lookup.get(str(speaker or "").lower()) or lookup.get(_lookup_key(speaker))
    if not profile:
        return dict(base_settings)
    mods = dict(profile.voice_modifiers)
    settings = dict(base_settings)
    settings["speed"] = round(float(settings.get("speed") or 1.0) * float(mods.get("speed_multiplier") or 1.0), 3)
    settings["pitch_shift"] = round(float(settings.get("pitch_shift") or 1.0) * float(mods.get("pitch_shift") or 1.0), 3)
    settings["stability"] = float(mods.get("stability") or settings.get("stability") or 0.45)
    settings["style"] = float(mods.get("style") or settings.get("style") or 0.45)
    settings["similarity_boost"] = float(mods.get("similarity_boost") or settings.get("similarity_boost") or 0.85)
    settings["speaking_style"] = profile.speaking_style
    settings["energy_profile"] = profile.energy_profile
    return settings


__all__ = [
    "CHARACTER_PERFORMANCE_VERSION",
    "CharacterPerformanceProfile",
    "apply_performance_to_voice_settings",
    "build_character_performance_profiles",
    "performance_lookup",
]
