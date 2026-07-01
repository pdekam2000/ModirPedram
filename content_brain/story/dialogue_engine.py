"""Dialogue Engine — scene conversations, not director stage directions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.story.character_director import CharacterProfile
from content_brain.story.story_architect import StoryBlueprint

DIALOGUE_ENGINE_VERSION = "dialogue_engine_v1"


@dataclass
class SceneDialogue:
    scene_index: int
    scene_title: str
    dialogue_lines: list[dict[str, str]]
    narration: str
    emotional_intent: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_index": self.scene_index,
            "scene_title": self.scene_title,
            "dialogue_lines": list(self.dialogue_lines),
            "narration": self.narration,
            "emotional_intent": self.emotional_intent,
        }


@dataclass
class DialoguePlan:
    scenes: list[SceneDialogue]
    genre: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DIALOGUE_ENGINE_VERSION,
            "genre": self.genre,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    def all_spoken_lines(self) -> list[str]:
        lines: list[str] = []
        for scene in self.scenes:
            for item in scene.dialogue_lines:
                line = str(item.get("line") or "").strip()
                if line:
                    lines.append(line)
            if scene.narration.strip():
                lines.append(scene.narration.strip())
        return lines


def _speaker_map(characters: list[CharacterProfile]) -> dict[str, CharacterProfile]:
    return {profile.name.lower(): profile for profile in characters}


def _cartoon_scene_dialogue(
    index: int,
    beat: str,
    *,
    cat_name: str = "Whiskers",
    friend_name: str = "Sage",
) -> SceneDialogue:
    presets = [
        {
            "scene_title": "The Glowing Path",
            "dialogue_lines": [
                {"speaker": cat_name, "line": "Wow! What is that?", "emotion": "curiosity"},
                {"speaker": friend_name, "line": "Be careful, Whiskers!", "emotion": "tension"},
            ],
            "narration": "The adventure had begun beneath the ancient jungle arch.",
            "emotional_intent": "curiosity with cautious wonder",
        },
        {
            "scene_title": "Split in the Trail",
            "dialogue_lines": [
                {"speaker": friend_name, "line": "That stone is moving!", "emotion": "fear"},
                {"speaker": cat_name, "line": "I think something is calling us.", "emotion": "surprise"},
            ],
            "narration": "Roots shifted and the path ahead stopped making sense.",
            "emotional_intent": "rising fear and discovery",
        },
        {
            "scene_title": "The Hidden Spark",
            "dialogue_lines": [
                {"speaker": cat_name, "line": "I can carry it! I know I can!", "emotion": "excitement"},
                {"speaker": friend_name, "line": "Then I am with you.", "emotion": "relief"},
            ],
            "narration": "The crystal seed pulsed like a heartbeat of light.",
            "emotional_intent": "excitement and courage",
        },
        {
            "scene_title": "Bridge of Light",
            "dialogue_lines": [
                {"speaker": cat_name, "line": "We did it!", "emotion": "joy"},
                {"speaker": friend_name, "line": "The jungle remembers us now.", "emotion": "relief"},
            ],
            "narration": "Warm light spilled across the mossy stones like a sunrise.",
            "emotional_intent": "joy and resolution",
        },
    ]
    preset = presets[min(index, len(presets) - 1)]
    return SceneDialogue(
        scene_index=index,
        scene_title=str(beat or preset["scene_title"])[:80] or preset["scene_title"],
        dialogue_lines=list(preset["dialogue_lines"]),
        narration=str(preset["narration"]),
        emotional_intent=str(preset["emotional_intent"]),
    )


def build_dialogue_plan(
    *,
    blueprint: StoryBlueprint,
    characters: list[CharacterProfile],
    clip_count: int = 3,
) -> DialoguePlan:
    cast = _speaker_map(characters)
    cat = next((c.name for c in characters if c.role == "protagonist"), "Whiskers")
    friend = next((c.name for c in characters if c.role == "mentor"), "Sage")
    scenes: list[SceneDialogue] = []
    beats = blueprint.scene_progression or [blueprint.hook, blueprint.conflict, blueprint.climax, blueprint.resolution]
    for index in range(max(1, clip_count)):
        beat = beats[index] if index < len(beats) else blueprint.resolution
        if blueprint.genre == "cartoon":
            scenes.append(_cartoon_scene_dialogue(index, beat, cat_name=cat, friend_name=friend))
        else:
            lead = cat if cat in cast else characters[0].name
            scenes.append(
                SceneDialogue(
                    scene_index=index,
                    scene_title=str(beat)[:80] or f"Scene {index + 1}",
                    dialogue_lines=[
                        {"speaker": lead, "line": "We have to keep going.", "emotion": "determination"},
                        {"speaker": "Narrator", "line": "", "emotion": "tension"},
                    ],
                    narration=str(beat),
                    emotional_intent="forward momentum",
                )
            )
    return DialoguePlan(scenes=scenes, genre=blueprint.genre)


__all__ = ["DIALOGUE_ENGINE_VERSION", "DialoguePlan", "SceneDialogue", "build_dialogue_plan"]
