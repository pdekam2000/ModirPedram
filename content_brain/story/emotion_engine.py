"""Emotion Engine — per-scene emotional profiles for cinematic pacing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.story.dialogue_engine import DialoguePlan

EMOTION_ENGINE_VERSION = "emotion_engine_v1"

SUPPORTED_EMOTIONS = (
    "joy",
    "curiosity",
    "fear",
    "surprise",
    "sadness",
    "excitement",
    "tension",
    "relief",
)


@dataclass
class SceneEmotionProfile:
    scene_index: int
    dominant_emotion: str
    scores: dict[str, int]
    pacing: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_index": self.scene_index,
            "dominant_emotion": self.dominant_emotion,
            "scores": dict(self.scores),
            "pacing": self.pacing,
        }


@dataclass
class EmotionPlan:
    scenes: list[SceneEmotionProfile]
    arc_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": EMOTION_ENGINE_VERSION,
            "arc_summary": self.arc_summary,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }


def _scores_from_intent(intent: str, index: int, total: int) -> dict[str, int]:
    base = {emotion: 5 for emotion in SUPPORTED_EMOTIONS}
    intent_lower = intent.lower()
    if "curiosity" in intent_lower or index == 0:
        base.update({"curiosity": 80, "surprise": 35, "excitement": 40})
    if "fear" in intent_lower or "tension" in intent_lower:
        base.update({"fear": 70, "tension": 75, "surprise": 45})
    if "excitement" in intent_lower or "courage" in intent_lower:
        base.update({"excitement": 95, "joy": 55, "tension": 40})
    if "joy" in intent_lower or "resolution" in intent_lower or index >= total - 1:
        base.update({"joy": 90, "relief": 85, "excitement": 60})
    if index == 1 and base["curiosity"] < 50:
        base["curiosity"] = 65
    dominant = max(base.items(), key=lambda item: item[1])[0]
    base["_dominant"] = 0  # type: ignore[assignment]
    base.pop("_dominant", None)
    return base


def build_emotion_plan(*, dialogue_plan: DialoguePlan) -> EmotionPlan:
    total = max(1, len(dialogue_plan.scenes))
    profiles: list[SceneEmotionProfile] = []
    for scene in dialogue_plan.scenes:
        scores = _scores_from_intent(scene.emotional_intent, scene.scene_index, total)
        dominant = max(scores.items(), key=lambda item: item[1])[0]
        pacing = "slow-build" if scene.scene_index == 0 else "rising" if scene.scene_index < total - 1 else "release"
        profiles.append(
            SceneEmotionProfile(
                scene_index=scene.scene_index,
                dominant_emotion=dominant,
                scores=scores,
                pacing=pacing,
            )
        )
    arc = " → ".join(profile.dominant_emotion for profile in profiles)
    return EmotionPlan(scenes=profiles, arc_summary=arc)


__all__ = ["EMOTION_ENGINE_VERSION", "EmotionPlan", "SceneEmotionProfile", "SUPPORTED_EMOTIONS", "build_emotion_plan"]
