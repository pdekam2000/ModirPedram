"""Story emotion arc — Hook → Discovery → Conflict → Emotion → Reward."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.story.dialogue_engine import DialoguePlan
from content_brain.story.emotion_engine import EmotionPlan, SceneEmotionProfile, build_emotion_plan
from content_brain.story.story_architect import StoryBlueprint

STORY_EMOTION_ENGINE_VERSION = "story_emotion_engine_v1"

STORY_BEAT_SEQUENCE = ("hook", "discovery", "conflict", "emotion", "reward")


@dataclass
class StoryEmotionArc:
    beats: list[dict[str, Any]]
    arc_summary: str
    emotion_plan: EmotionPlan
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STORY_EMOTION_ENGINE_VERSION,
            "beats": list(self.beats),
            "arc_summary": self.arc_summary,
            "emotion_plan": self.emotion_plan.to_dict(),
            "metadata": dict(self.metadata),
        }


def _beat_for_index(index: int, total: int) -> str:
    if total <= 1:
        return "hook"
    ratio = index / max(1, total - 1)
    if ratio <= 0.15:
        return "hook"
    if ratio <= 0.35:
        return "discovery"
    if ratio <= 0.55:
        return "conflict"
    if ratio <= 0.8:
        return "emotion"
    return "reward"


def _scores_for_beat(beat: str) -> dict[str, int]:
    presets: dict[str, dict[str, int]] = {
        "hook": {"curiosity": 90, "surprise": 55, "excitement": 50, "joy": 30},
        "discovery": {"curiosity": 85, "surprise": 70, "excitement": 60, "wonder": 80},
        "conflict": {"fear": 65, "tension": 75, "surprise": 50, "excitement": 45},
        "emotion": {"excitement": 85, "joy": 70, "tension": 40, "relief": 35},
        "reward": {"joy": 95, "relief": 90, "excitement": 65, "curiosity": 40},
    }
    base = {emotion: 10 for emotion in ("joy", "curiosity", "fear", "surprise", "sadness", "excitement", "tension", "relief")}
    base.update(presets.get(beat, presets["discovery"]))
    return base


def build_story_emotion_arc(
    *,
    blueprint: StoryBlueprint,
    dialogue_plan: DialoguePlan,
) -> StoryEmotionArc:
    base_plan = build_emotion_plan(dialogue_plan=dialogue_plan)
    total = max(1, len(dialogue_plan.scenes))
    beats: list[dict[str, Any]] = []
    profiles: list[SceneEmotionProfile] = []

    for index, scene in enumerate(dialogue_plan.scenes):
        beat = _beat_for_index(index, total)
        scores = _scores_for_beat(beat)
        dominant = max(scores.items(), key=lambda item: item[1])[0]
        pacing = {
            "hook": "snap",
            "discovery": "rising",
            "conflict": "tight",
            "emotion": "peak",
            "reward": "release",
        }.get(beat, "rising")
        profiles.append(
            SceneEmotionProfile(
                scene_index=scene.scene_index,
                dominant_emotion=dominant,
                scores=scores,
                pacing=pacing,
            )
        )
        beats.append(
            {
                "scene_index": scene.scene_index,
                "story_beat": beat,
                "dominant_emotion": dominant,
                "scene_title": scene.scene_title,
                "intent": scene.emotional_intent,
            }
        )

    arc = " → ".join(STORY_BEAT_SEQUENCE[: min(len(beats), len(STORY_BEAT_SEQUENCE))])
    emotion_plan = EmotionPlan(scenes=profiles, arc_summary=arc)
    return StoryEmotionArc(
        beats=beats,
        arc_summary=arc,
        emotion_plan=emotion_plan,
        metadata={"genre": blueprint.genre, "title": blueprint.title},
    )


__all__ = [
    "STORY_BEAT_SEQUENCE",
    "STORY_EMOTION_ENGINE_VERSION",
    "StoryEmotionArc",
    "build_story_emotion_arc",
]
