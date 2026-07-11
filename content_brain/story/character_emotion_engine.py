"""Character emotion engine — per-scene emotional palette for visual storytelling."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.story.dialogue_engine import DialoguePlan
from content_brain.story.story_architect import StoryBlueprint

CHARACTER_EMOTION_VERSION = "character_emotion_engine_v1"

EMOTION_AXES = ("curiosity", "fear", "surprise", "excitement", "relief", "wonder")

SCENE_EMOTION_PRESETS: list[dict[str, int]] = [
    {"curiosity": 90, "surprise": 45, "excitement": 55, "wonder": 70, "fear": 15, "relief": 10},
    {"curiosity": 60, "fear": 70, "surprise": 65, "excitement": 50, "wonder": 40, "relief": 20},
    {"curiosity": 55, "surprise": 80, "excitement": 90, "wonder": 95, "relief": 85, "fear": 10},
]


@dataclass
class SceneCharacterEmotion:
    clip_index: int
    scene_label: str
    dominant_emotion: str
    emotions: dict[str, int]
    character_notes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "scene_label": self.scene_label,
            "dominant_emotion": self.dominant_emotion,
            "emotions": dict(self.emotions),
            "character_notes": dict(self.character_notes),
        }


@dataclass
class CharacterEmotionPlan:
    scenes: list[SceneCharacterEmotion]
    emotion_coverage_score: int
    covered_axes: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CHARACTER_EMOTION_VERSION,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "emotion_coverage_score": self.emotion_coverage_score,
            "covered_axes": list(self.covered_axes),
            "metadata": dict(self.metadata),
        }


def _dominant(emotions: dict[str, int]) -> str:
    return max(emotions.items(), key=lambda item: item[1])[0]


def _coverage_score(scenes: list[SceneCharacterEmotion]) -> tuple[int, list[str]]:
    covered: set[str] = set()
    for scene in scenes:
        for axis, value in scene.emotions.items():
            if value >= 40:
                covered.add(axis)
    ratio = len(covered) / max(1, len(EMOTION_AXES))
    return max(0, min(100, int(round(ratio * 100)))), sorted(covered)


def build_character_emotion_plan(
    *,
    blueprint: StoryBlueprint,
    dialogue_plan: DialoguePlan,
    clip_count: int = 3,
) -> CharacterEmotionPlan:
    scenes: list[SceneCharacterEmotion] = []
    total = max(clip_count, len(dialogue_plan.scenes), 1)

    for index in range(total):
        preset = dict(SCENE_EMOTION_PRESETS[min(index, len(SCENE_EMOTION_PRESETS) - 1)])
        scene_label = blueprint.scene_progression[index] if index < len(blueprint.scene_progression) else f"Scene {index + 1}"
        scenes.append(
            SceneCharacterEmotion(
                clip_index=index + 1,
                scene_label=str(scene_label),
                dominant_emotion=_dominant(preset),
                emotions={axis: int(preset.get(axis, 10)) for axis in EMOTION_AXES},
                character_notes={
                    "hero": f"Express {_dominant(preset)} through eyes, posture, and reaction timing.",
                    "companion": "Mirror tension then contrast with calmer relief beats.",
                },
            )
        )

    coverage, covered = _coverage_score(scenes)
    return CharacterEmotionPlan(
        scenes=scenes,
        emotion_coverage_score=coverage,
        covered_axes=covered,
        metadata={"title": blueprint.title, "genre": blueprint.genre},
    )


def save_character_emotion_plan(path: str | Path, plan: CharacterEmotionPlan) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target


__all__ = [
    "CHARACTER_EMOTION_VERSION",
    "CharacterEmotionPlan",
    "SceneCharacterEmotion",
    "build_character_emotion_plan",
    "save_character_emotion_plan",
]
