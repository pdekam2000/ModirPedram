"""Visual repetition detector — flag repeated locations, angles, compositions, actions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.story.reaction_shot_planner import ReactionShotPlan
from content_brain.story.scene_diversity_engine import SceneDiversityPlan
from content_brain.story.visual_story_progression_engine import VisualStoryProgressionPlan

VISUAL_REPETITION_VERSION = "visual_repetition_detector_v1"


@dataclass
class RepetitionFinding:
    category: str
    severity: str
    clip_indices: list[int]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "clip_indices": list(self.clip_indices),
            "detail": self.detail,
        }


@dataclass
class VisualRepetitionReport:
    findings: list[RepetitionFinding]
    repetition_score: int
    repeated_locations: list[str] = field(default_factory=list)
    repeated_objectives: list[str] = field(default_factory=list)
    pass_visual_diversity: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VISUAL_REPETITION_VERSION,
            "findings": [item.to_dict() for item in self.findings],
            "repetition_score": self.repetition_score,
            "repeated_locations": list(self.repeated_locations),
            "repeated_objectives": list(self.repeated_objectives),
            "pass_visual_diversity": self.pass_visual_diversity,
            "metadata": dict(self.metadata),
        }


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", str(text or "").lower()))


def detect_visual_repetition(
    *,
    diversity_plan: SceneDiversityPlan,
    progression_plan: VisualStoryProgressionPlan,
    reaction_plan: ReactionShotPlan,
) -> VisualRepetitionReport:
    findings: list[RepetitionFinding] = []
    repeated_locations: list[str] = []
    repeated_objectives: list[str] = []

    locations = [obj.location.lower() for obj in diversity_plan.clip_objectives]
    for index, loc in enumerate(locations):
        for other_index, other in enumerate(locations):
            if other_index <= index:
                continue
            shared = _tokens(loc) & _tokens(other)
            if loc == other or len(shared) >= 2:
                repeated_locations.append(loc)
                findings.append(
                    RepetitionFinding(
                        category="location",
                        severity="high",
                        clip_indices=[index + 1, other_index + 1],
                        detail=f"Repeated location family: {loc!r} vs {other!r}",
                    )
                )

    objectives = [obj.visual_objective.lower() for obj in diversity_plan.clip_objectives]
    for index, objective in enumerate(objectives):
        for other_index, other in enumerate(objectives):
            if other_index <= index or objective != other:
                continue
            repeated_objectives.append(objective)
            findings.append(
                RepetitionFinding(
                    category="composition",
                    severity="high",
                    clip_indices=[index + 1, other_index + 1],
                    detail=f"Repeated visual objective: {objective!r}",
                )
            )

    roles = [beat.role for beat in progression_plan.beats]
    for index, role in enumerate(roles):
        for other_index, other in enumerate(roles):
            if other_index <= index or role != other:
                continue
            findings.append(
                RepetitionFinding(
                    category="story_progression",
                    severity="medium",
                    clip_indices=[index + 1, other_index + 1],
                    detail=f"Repeated progression role: {role}",
                )
            )

    reaction_types = [moment.reaction_type for moment in reaction_plan.moments]
    seen_reactions: dict[str, list[int]] = {}
    for moment in reaction_plan.moments:
        seen_reactions.setdefault(moment.reaction_type, []).append(moment.clip_index)
    for reaction_type, clips in seen_reactions.items():
        if len(clips) >= 3:
            findings.append(
                RepetitionFinding(
                    category="action",
                    severity="low",
                    clip_indices=sorted(set(clips)),
                    detail=f"Reaction {reaction_type!r} reused across multiple clips",
                )
            )

    framing = [moment.framing for moment in reaction_plan.moments]
    if len(framing) != len(set(framing)) and len(framing) >= 3:
        findings.append(
            RepetitionFinding(
                category="camera_angle",
                severity="low",
                clip_indices=sorted({moment.clip_index for moment in reaction_plan.moments}),
                detail="Some reaction framings repeat across clips",
            )
        )

    penalty = sum(25 if item.severity == "high" else 12 if item.severity == "medium" else 5 for item in findings)
    repetition_score = max(0, min(100, 100 - penalty))
    return VisualRepetitionReport(
        findings=findings,
        repetition_score=repetition_score,
        repeated_locations=sorted(set(repeated_locations)),
        repeated_objectives=sorted(set(repeated_objectives)),
        pass_visual_diversity=repetition_score >= 70 and not repeated_locations,
        metadata={
            "scene_diversity_score": diversity_plan.scene_diversity_score,
            "story_progression_score": progression_plan.story_progression_score,
        },
    )


def save_visual_repetition_report(path: str | Path, report: VisualRepetitionReport) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return target


__all__ = [
    "VISUAL_REPETITION_VERSION",
    "VisualRepetitionReport",
    "detect_visual_repetition",
    "save_visual_repetition_report",
]
