"""Story visual orchestrator — diversity, emotion, progression, reactions, repetition."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.story.character_emotion_engine import (
    CharacterEmotionPlan,
    build_character_emotion_plan,
    save_character_emotion_plan,
)
from content_brain.story.dialogue_engine import DialoguePlan
from content_brain.story.reaction_shot_planner import ReactionShotPlan, build_reaction_shot_plan
from content_brain.story.scene_diversity_engine import SceneDiversityPlan, build_scene_diversity_plan
from content_brain.story.story_architect import StoryBlueprint
from content_brain.story.visual_repetition_detector import (
    VisualRepetitionReport,
    detect_visual_repetition,
    save_visual_repetition_report,
)
from content_brain.story.visual_story_progression_engine import (
    VisualStoryProgressionPlan,
    build_visual_story_progression_plan,
)

STORY_VISUAL_ORCHESTRATOR_VERSION = "story_visual_orchestrator_v1"


@dataclass
class StoryVisualBundle:
    scene_diversity: SceneDiversityPlan
    character_emotion: CharacterEmotionPlan
    visual_progression: VisualStoryProgressionPlan
    reaction_shots: ReactionShotPlan
    repetition_report: VisualRepetitionReport
    scene_progression: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STORY_VISUAL_ORCHESTRATOR_VERSION,
            "scene_diversity": self.scene_diversity.to_dict(),
            "character_emotion": self.character_emotion.to_dict(),
            "visual_progression": self.visual_progression.to_dict(),
            "reaction_shots": self.reaction_shots.to_dict(),
            "repetition_report": self.repetition_report.to_dict(),
            "scene_progression": list(self.scene_progression),
            "story_visual_quality": self.results_panel(),
            "metadata": dict(self.metadata),
        }

    def results_panel(self) -> dict[str, Any]:
        return {
            "scene_diversity_score": self.scene_diversity.scene_diversity_score,
            "emotion_coverage_score": self.character_emotion.emotion_coverage_score,
            "story_progression_score": self.visual_progression.story_progression_score,
            "repetition_score": self.repetition_report.repetition_score,
            "reaction_coverage_score": self.reaction_shots.reaction_coverage_score,
            "pass_visual_diversity": self.repetition_report.pass_visual_diversity,
            "unique_locations": self.scene_diversity.unique_locations,
            "clip_objectives": [item.to_dict() for item in self.scene_diversity.clip_objectives],
        }


def build_story_visual_bundle(
    *,
    blueprint: StoryBlueprint,
    dialogue_plan: DialoguePlan,
    clip_count: int = 3,
    story_brief: dict[str, Any] | None = None,
) -> StoryVisualBundle:
    diversity = build_scene_diversity_plan(blueprint=blueprint, clip_count=clip_count, story_brief=story_brief)
    emotion = build_character_emotion_plan(blueprint=blueprint, dialogue_plan=dialogue_plan, clip_count=clip_count)
    progression = build_visual_story_progression_plan(
        blueprint=blueprint,
        diversity_plan=diversity,
        clip_count=clip_count,
    )
    reactions = build_reaction_shot_plan(progression_plan=progression)
    repetition = detect_visual_repetition(
        diversity_plan=diversity,
        progression_plan=progression,
        reaction_plan=reactions,
    )

    scene_progression = [
        f"{beat.role.title()}: {beat.visual_objective} ({beat.location})"
        for beat in progression.beats
    ]

    return StoryVisualBundle(
        scene_diversity=diversity,
        character_emotion=emotion,
        visual_progression=progression,
        reaction_shots=reactions,
        repetition_report=repetition,
        scene_progression=scene_progression,
        metadata={"clip_count": clip_count, "genre": blueprint.genre},
    )


def save_story_visual_artifacts(
    *,
    project_root: str | Path,
    run_id: str,
    bundle: StoryVisualBundle,
    run_dir: str | Path | None = None,
) -> dict[str, str]:
    root = Path(project_root).resolve()
    paths: dict[str, str] = {}

    emotion_path = root / "project_brain" / "runtime_state" / f"character_emotion_plan_{run_id}.json"
    save_character_emotion_plan(emotion_path, bundle.character_emotion)
    paths["character_emotion_plan"] = str(emotion_path)

    repetition_path = root / "project_brain" / "runtime_state" / f"visual_repetition_report_{run_id}.json"
    save_visual_repetition_report(repetition_path, bundle.repetition_report)
    paths["visual_repetition_report"] = str(repetition_path)

    if run_dir:
        run_path = Path(run_dir).resolve()
        debug_dir = run_path / "debug" / "story_visual_1"
        debug_dir.mkdir(parents=True, exist_ok=True)
        diversity_path = debug_dir / "scene_diversity_report.json"
        diversity_path.write_text(json.dumps(bundle.scene_diversity.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        paths["scene_diversity_report"] = str(diversity_path)

        run_emotion = run_path / "metadata" / "character_emotion_plan.json"
        save_character_emotion_plan(run_emotion, bundle.character_emotion)
        paths["run_character_emotion_plan"] = str(run_emotion)

        run_repetition = run_path / "metadata" / "visual_repetition_report.json"
        save_visual_repetition_report(run_repetition, bundle.repetition_report)
        paths["run_visual_repetition_report"] = str(run_repetition)

        summary_path = debug_dir / "story_visual_summary.json"
        summary_path.write_text(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        paths["story_visual_summary"] = str(summary_path)

    return paths


__all__ = [
    "STORY_VISUAL_ORCHESTRATOR_VERSION",
    "StoryVisualBundle",
    "build_story_visual_bundle",
    "save_story_visual_artifacts",
]
