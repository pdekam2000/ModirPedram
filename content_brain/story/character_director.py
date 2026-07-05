"""Character Director — named cast with personality and voice direction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.story.story_architect import StoryBlueprint
from content_brain.story.story_niche import detect_genre

CHARACTER_DIRECTOR_VERSION = "character_director_v1"


@dataclass
class CharacterProfile:
    name: str
    role: str
    age: str
    gender: str
    personality: list[str]
    visual_traits: list[str]
    voice_style: str
    emotional_traits: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "age": self.age,
            "gender": self.gender,
            "personality": list(self.personality),
            "visual_traits": list(self.visual_traits),
            "voice_style": self.voice_style,
            "emotional_traits": list(self.emotional_traits),
        }


def _cartoon_cast(topic: str) -> list[CharacterProfile]:
    haystack = topic.lower()
    friend = "Sage"
    if "fox" in haystack:
        friend = "Sage"
    elif "rabbit" in haystack:
        friend = "Bunny"
    return [
        CharacterProfile(
            name="Whiskers",
            role="protagonist",
            age="young",
            gender="neutral",
            personality=["playful", "curious", "optimistic", "brave"],
            visual_traits=["small orange tabby cat", "explorer backpack", "bright green eyes"],
            voice_style="child friendly",
            emotional_traits=["wonder", "excitement", "determination"],
        ),
        CharacterProfile(
            name=friend,
            role="mentor",
            age="young adult",
            gender="female" if friend == "Sage" else "neutral",
            personality=["smart", "careful", "protective", "warm"],
            visual_traits=["sleek fox companion" if friend == "Sage" else "soft rabbit companion", "calm posture"],
            voice_style="young female" if friend == "Sage" else "gentle friend",
            emotional_traits=["caution", "loyalty", "relief"],
        ),
        CharacterProfile(
            name="Narrator",
            role="narrator",
            age="adult",
            gender="neutral",
            personality=["warm", "storytelling", "cinematic"],
            visual_traits=["voice only"],
            voice_style="warm storyteller",
            emotional_traits=["wonder", "tension", "relief"],
        ),
    ]


def _generic_cast(genre: str) -> list[CharacterProfile]:
    if genre == "wildlife":
        return [
            CharacterProfile("Asha", "protagonist", "adult", "female", ["instinctive", "loyal"], ["grey wolf"], "calm narrator", ["resolve"]),
            CharacterProfile("Narrator", "narrator", "adult", "neutral", ["observant"], ["voice only"], "documentary warm", ["awe"]),
        ]
    if genre == "horror":
        return [
            CharacterProfile("Mara", "protagonist", "adult", "female", ["skeptical", "brave"], ["dark hair", "flashlight"], "tense whisper", ["fear", "defiance"]),
            CharacterProfile("Narrator", "narrator", "adult", "neutral", ["ominous"], ["voice only"], "deep dramatic", ["dread"]),
        ]
    return [
        CharacterProfile("Alex", "protagonist", "teen", "neutral", ["curious", "determined"], ["student explorer"], "youthful clear", ["focus"]),
        CharacterProfile("Narrator", "narrator", "adult", "neutral", ["clear", "friendly"], ["voice only"], "warm educator", ["clarity"]),
    ]


def _human_cast_from_brief(topic: str, story_brief: dict[str, Any], genre: str) -> list[CharacterProfile]:
    main = str(story_brief.get("main_character") or "").strip()
    if not main:
        if "boy" in topic.lower():
            main = "Boy"
        elif "girl" in topic.lower():
            main = "Girl"
        else:
            main = "Protagonist"
    companion = str(story_brief.get("companion") or "").strip()
    profiles = [
        CharacterProfile(
            name=main,
            role="protagonist",
            age="child" if any(k in main.lower() for k in ("boy", "girl", "child")) else "young",
            gender="neutral",
            personality=["curious", "brave", "determined"],
            visual_traits=[main.lower(), "story protagonist"],
            voice_style="youthful clear",
            emotional_traits=["wonder", "caution", "resolve"],
        ),
        CharacterProfile(
            name="Narrator",
            role="narrator",
            age="adult",
            gender="neutral",
            personality=["warm", "storytelling", "cinematic"],
            visual_traits=["voice only"],
            voice_style="warm storyteller",
            emotional_traits=["wonder", "tension", "relief"],
        ),
    ]
    if companion:
        profiles.insert(
            1,
            CharacterProfile(
                name=companion,
                role="companion",
                age="young",
                gender="neutral",
                personality=["supportive", "watchful"],
                visual_traits=[companion.lower()],
                voice_style="expressive character",
                emotional_traits=["loyalty", "concern"],
            ),
        )
    elif "dragon" in topic.lower():
        profiles.insert(
            1,
            CharacterProfile(
                name="Dragon",
                role="companion",
                age="young",
                gender="neutral",
                personality=["mysterious", "gentle"],
                visual_traits=["dragon egg", "magical creature"],
                voice_style="soft magical",
                emotional_traits=["wonder", "trust"],
            ),
        )
    return profiles


def _is_cartoon_template_topic(topic: str, story_brief: dict[str, Any] | None = None) -> bool:
    haystack = topic.lower()
    brief = dict(story_brief or {})
    if str(brief.get("genre") or "").lower() == "cartoon":
        return True
    return any(k in haystack for k in ("cartoon", "whiskers", "sage", "kitten"))


def build_character_profiles(
    *,
    blueprint: StoryBlueprint,
    topic: str,
    story_brief: dict[str, Any] | None = None,
) -> list[CharacterProfile]:
    brief = dict(story_brief or {})
    cartoon_topic = _is_cartoon_template_topic(topic, brief)
    effective_genre = str(blueprint.genre or "").lower()
    if effective_genre == "cartoon" and not cartoon_topic:
        effective_genre = detect_genre(topic, brief)
        if effective_genre == "cartoon":
            effective_genre = "educational"
    if not cartoon_topic and effective_genre != "cartoon":
        if brief.get("main_character") or any(k in topic.lower() for k in ("boy", "girl", "dragon", "finds")):
            return _human_cast_from_brief(topic, brief, effective_genre)
        return _generic_cast(effective_genre)
    if effective_genre == "cartoon" or cartoon_topic:
        return _cartoon_cast(topic)
    return _generic_cast(effective_genre)


__all__ = ["CHARACTER_DIRECTOR_VERSION", "CharacterProfile", "build_character_profiles"]
