"""Reaction shot planner — inject character reactions to story discoveries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.story.visual_story_progression_engine import VisualStoryProgressionPlan

REACTION_SHOT_VERSION = "reaction_shot_planner_v1"

REACTION_TYPES = ("look_left", "look_up", "surprise", "smile", "fear", "excitement")

ROLE_REACTIONS: dict[str, list[str]] = {
    "discovery": ["look_left", "curiosity_widen_eyes", "surprise"],
    "escalation": ["look_up", "fear", "surprise"],
    "reward": ["smile", "excitement", "wonder_gasp"],
}


@dataclass
class ReactionMoment:
    clip_index: int
    trigger: str
    reaction_type: str
    character: str
    framing: str
    duration_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "trigger": self.trigger,
            "reaction_type": self.reaction_type,
            "character": self.character,
            "framing": self.framing,
            "duration_hint": self.duration_hint,
        }


@dataclass
class ReactionShotPlan:
    moments: list[ReactionMoment]
    reaction_coverage_score: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": REACTION_SHOT_VERSION,
            "moments": [moment.to_dict() for moment in self.moments],
            "reaction_coverage_score": self.reaction_coverage_score,
            "metadata": dict(self.metadata),
        }


def _normalize_reaction(raw: str) -> str:
    lowered = str(raw or "").lower().replace(" ", "_")
    for candidate in REACTION_TYPES:
        if candidate in lowered:
            return candidate
    return lowered


def build_reaction_shot_plan(*, progression_plan: VisualStoryProgressionPlan) -> ReactionShotPlan:
    moments: list[ReactionMoment] = []
    used_types: set[str] = set()

    for beat in progression_plan.beats:
        reactions = ROLE_REACTIONS.get(beat.role, ["surprise"])
        for reaction in reactions[:2]:
            normalized = _normalize_reaction(reaction)
            used_types.add(normalized)
            moments.append(
                ReactionMoment(
                    clip_index=beat.clip_index,
                    trigger=f"Character reacts to {beat.role}: {beat.visual_objective}",
                    reaction_type=normalized,
                    character="hero",
                    framing="medium_close_reaction",
                    duration_hint="0.8-1.5s",
                )
            )
        moments.append(
            ReactionMoment(
                clip_index=beat.clip_index,
                trigger=f"Companion reacts after hero discovers {beat.location}",
                reaction_type="look_left" if beat.role == "discovery" else "excitement",
                character="companion",
                framing="over_shoulder_reaction",
                duration_hint="0.6-1.2s",
            )
        )

    coverage = max(0, min(100, int(round(len(used_types) / max(1, len(REACTION_TYPES)) * 100))))
    return ReactionShotPlan(
        moments=moments,
        reaction_coverage_score=coverage,
        metadata={"moment_count": len(moments)},
    )


__all__ = [
    "REACTION_SHOT_VERSION",
    "ReactionMoment",
    "ReactionShotPlan",
    "build_reaction_shot_plan",
]
