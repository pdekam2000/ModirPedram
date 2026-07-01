"""Scene diversity engine — unique visual objective per clip."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.story.story_architect import StoryBlueprint

SCENE_DIVERSITY_VERSION = "scene_diversity_engine_v1"

CARTOON_VISUAL_OBJECTIVES = (
    {"clip_index": 1, "location": "forest entrance", "visual_objective": "Sunlit jungle trail with vines and golden dust motes", "setting_type": "exterior_nature"},
    {"clip_index": 2, "location": "ancient ruins", "visual_objective": "Crumbling stone arches covered in moss and carved symbols", "setting_type": "interior_ruins"},
    {"clip_index": 3, "location": "hidden glowing chamber", "visual_objective": "Underground crystal cavern pulsing with warm amber light", "setting_type": "interior_magical"},
)

PROGRESSION_ROLES = ("discovery", "escalation", "reward")


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]{3,}", str(text or "").lower()) if token}


@dataclass
class ClipVisualObjective:
    clip_index: int
    location: str
    visual_objective: str
    setting_type: str
    story_beat: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "location": self.location,
            "visual_objective": self.visual_objective,
            "setting_type": self.setting_type,
            "story_beat": self.story_beat,
        }


@dataclass
class SceneDiversityPlan:
    clip_objectives: list[ClipVisualObjective]
    scene_diversity_score: int
    unique_locations: list[str]
    unique_setting_types: list[str]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCENE_DIVERSITY_VERSION,
            "clip_objectives": [item.to_dict() for item in self.clip_objectives],
            "scene_diversity_score": self.scene_diversity_score,
            "unique_locations": list(self.unique_locations),
            "unique_setting_types": list(self.unique_setting_types),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


def _objectives_for_genre(genre: str, clip_count: int) -> list[dict[str, Any]]:
    if genre == "cartoon":
        base = list(CARTOON_VISUAL_OBJECTIVES)
    else:
        base = [
            {"clip_index": 1, "location": "opening landscape", "visual_objective": "Wide establishing view of the journey beginning", "setting_type": "exterior_wide"},
            {"clip_index": 2, "location": "conflict zone", "visual_objective": "Tight dramatic space where obstacles intensify", "setting_type": "interior_tension"},
            {"clip_index": 3, "location": "payoff reveal", "visual_objective": "Reward space with clear visual transformation", "setting_type": "interior_payoff"},
        ]
    while len(base) < clip_count:
        index = len(base) + 1
        base.append(
            {
                "clip_index": index,
                "location": f"story beat {index}",
                "visual_objective": f"Distinct story beat {index} with new composition",
                "setting_type": f"beat_{index}",
            }
        )
    return base[:clip_count]


def _score_diversity(objectives: list[ClipVisualObjective]) -> tuple[int, list[str]]:
    warnings: list[str] = []
    locations = [obj.location.lower().strip() for obj in objectives]
    settings = [obj.setting_type.lower().strip() for obj in objectives]
    unique_locations = list(dict.fromkeys(locations))
    unique_settings = list(dict.fromkeys(settings))

    location_ratio = len(unique_locations) / max(1, len(locations))
    setting_ratio = len(unique_settings) / max(1, len(settings))

    overlap_penalty = 0
    for index, loc in enumerate(locations):
        for other in locations[index + 1 :]:
            shared = _tokenize(loc) & _tokenize(other)
            if loc == other or len(shared) >= 2:
                overlap_penalty += 25
                warnings.append(f"Repeated location family between clips: {loc!r} vs {other!r}")

    raw = int(round((location_ratio * 55) + (setting_ratio * 35) + 10 - overlap_penalty))
    score = max(0, min(100, raw))
    if score < 70:
        warnings.append("Scene diversity below target — clips may look visually similar.")
    return score, warnings


def build_scene_diversity_plan(
    *,
    blueprint: StoryBlueprint,
    clip_count: int = 3,
    story_brief: dict[str, Any] | None = None,
) -> SceneDiversityPlan:
    brief = dict(story_brief or {})
    objectives_raw = list(brief.get("visual_objectives") or [])
    if not objectives_raw:
        objectives_raw = _objectives_for_genre(blueprint.genre, clip_count)

    clip_objectives: list[ClipVisualObjective] = []
    for index, raw in enumerate(objectives_raw[:clip_count], start=1):
        if isinstance(raw, dict):
            clip_objectives.append(
                ClipVisualObjective(
                    clip_index=int(raw.get("clip_index") or index),
                    location=str(raw.get("location") or f"scene {index}"),
                    visual_objective=str(raw.get("visual_objective") or raw.get("location") or ""),
                    setting_type=str(raw.get("setting_type") or "generic"),
                    story_beat=str(raw.get("story_beat") or PROGRESSION_ROLES[min(index - 1, 2)]),
                )
            )
        else:
            clip_objectives.append(
                ClipVisualObjective(
                    clip_index=index,
                    location=str(raw),
                    visual_objective=str(raw),
                    setting_type="custom",
                    story_beat=PROGRESSION_ROLES[min(index - 1, 2)],
                )
            )

    score, warnings = _score_diversity(clip_objectives)
    return SceneDiversityPlan(
        clip_objectives=clip_objectives,
        scene_diversity_score=score,
        unique_locations=list(dict.fromkeys(obj.location for obj in clip_objectives)),
        unique_setting_types=list(dict.fromkeys(obj.setting_type for obj in clip_objectives)),
        warnings=warnings,
        metadata={"genre": blueprint.genre, "clip_count": clip_count, "title": blueprint.title},
    )


__all__ = [
    "SCENE_DIVERSITY_VERSION",
    "ClipVisualObjective",
    "SceneDiversityPlan",
    "build_scene_diversity_plan",
]
