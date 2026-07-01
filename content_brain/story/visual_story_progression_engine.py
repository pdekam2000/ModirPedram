"""Visual story progression — discovery → escalation → reward without repeated objectives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.story.scene_diversity_engine import ClipVisualObjective, SceneDiversityPlan
from content_brain.story.story_architect import StoryBlueprint

VISUAL_PROGRESSION_VERSION = "visual_story_progression_engine_v1"

ROLE_SEQUENCE = ("discovery", "escalation", "reward")


@dataclass
class ClipProgressionBeat:
    clip_index: int
    role: str
    narrative_goal: str
    visual_objective: str
    location: str
    must_not_repeat: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "role": self.role,
            "narrative_goal": self.narrative_goal,
            "visual_objective": self.visual_objective,
            "location": self.location,
            "must_not_repeat": list(self.must_not_repeat),
        }


@dataclass
class VisualStoryProgressionPlan:
    beats: list[ClipProgressionBeat]
    story_progression_score: int
    repeated_roles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VISUAL_PROGRESSION_VERSION,
            "beats": [beat.to_dict() for beat in self.beats],
            "story_progression_score": self.story_progression_score,
            "repeated_roles": list(self.repeated_roles),
            "metadata": dict(self.metadata),
        }


def _narrative_goal(role: str, blueprint: StoryBlueprint) -> str:
    mapping = {
        "discovery": blueprint.discovery or blueprint.hook,
        "escalation": blueprint.escalation or blueprint.conflict,
        "reward": blueprint.resolution or blueprint.climax,
    }
    return str(mapping.get(role) or "")


def build_visual_story_progression_plan(
    *,
    blueprint: StoryBlueprint,
    diversity_plan: SceneDiversityPlan,
    clip_count: int = 3,
) -> VisualStoryProgressionPlan:
    beats: list[ClipProgressionBeat] = []
    seen_roles: list[str] = []
    seen_objectives: list[str] = []
    repeated_roles: list[str] = []

    objectives: list[ClipVisualObjective] = diversity_plan.clip_objectives[:clip_count]
    while len(objectives) < clip_count:
        objectives.append(
            ClipVisualObjective(
                clip_index=len(objectives) + 1,
                location=f"beat {len(objectives) + 1}",
                visual_objective=f"Unique beat {len(objectives) + 1}",
                setting_type="generic",
            )
        )

    for index, objective in enumerate(objectives):
        role = ROLE_SEQUENCE[min(index, len(ROLE_SEQUENCE) - 1)]
        if role in seen_roles:
            repeated_roles.append(role)
        seen_roles.append(role)

        objective_key = objective.visual_objective.lower().strip()
        must_not_repeat = [item for item in seen_objectives if item != objective_key]
        if objective_key in seen_objectives:
            repeated_roles.append(f"objective:{objective_key}")
        seen_objectives.append(objective_key)

        beats.append(
            ClipProgressionBeat(
                clip_index=objective.clip_index,
                role=role,
                narrative_goal=_narrative_goal(role, blueprint),
                visual_objective=objective.visual_objective,
                location=objective.location,
                must_not_repeat=must_not_repeat,
            )
        )

    role_ok = len(set(beat.role for beat in beats)) == len(beats)
    objective_ok = len(set(beat.visual_objective.lower() for beat in beats)) == len(beats)
    score = 100 if role_ok and objective_ok and not repeated_roles else max(40, 100 - (len(repeated_roles) * 20))

    return VisualStoryProgressionPlan(
        beats=beats,
        story_progression_score=score,
        repeated_roles=repeated_roles,
        metadata={"title": blueprint.title, "genre": blueprint.genre},
    )


__all__ = [
    "VISUAL_PROGRESSION_VERSION",
    "ClipProgressionBeat",
    "VisualStoryProgressionPlan",
    "build_visual_story_progression_plan",
]
