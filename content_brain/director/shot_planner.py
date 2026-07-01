"""Shot planner — assign varied cinematic shot sequences per clip."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.director.shot_library import (
    AERIAL_SHOT,
    CLOSE_UP,
    DOLLY_IN,
    ESTABLISHING_SHOT,
    HERO_SHOT,
    MACRO_DETAIL,
    MEDIUM_SHOT,
    ORBIT_SHOT,
    REVEAL_SHOT,
    TRACKING_SHOT,
    WIDE_SHOT,
    get_shot,
)

PLANNER_VERSION = "shot_planner_v1"

THREE_CLIP_ARC: tuple[str, ...] = (ESTABLISHING_SHOT, TRACKING_SHOT, HERO_SHOT)
FOUR_CLIP_ARC: tuple[str, ...] = (ESTABLISHING_SHOT, MEDIUM_SHOT, TRACKING_SHOT, REVEAL_SHOT)
FIVE_CLIP_ARC: tuple[str, ...] = (WIDE_SHOT, DOLLY_IN, TRACKING_SHOT, CLOSE_UP, HERO_SHOT)
SIX_CLIP_ARC: tuple[str, ...] = (ESTABLISHING_SHOT, MEDIUM_SHOT, TRACKING_SHOT, ORBIT_SHOT, REVEAL_SHOT, HERO_SHOT)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _brief_value(story_brief: Any | None, key: str, fallback: str = "") -> str:
    if story_brief is None:
        return fallback
    if isinstance(story_brief, dict):
        return _normalize(str(story_brief.get(key) or fallback))
    return _normalize(str(getattr(story_brief, key, "") or fallback))


def _topic_category(topic: str) -> str:
    lowered = topic.lower()
    if re.search(r"\b(lion|wildlife|animal|nature|savanna|forest|ocean|bird|scorpion|snake)\b", lowered):
        return "wildlife"
    if re.search(r"\b(gpu|rtx|tech|software|hardware|product|benchmark|ai|computer)\b", lowered):
        return "technology"
    if re.search(r"\b(history|war|ancient|empire|century|documentary|biography)\b", lowered):
        return "history"
    return "general"


def _arc_for_clip_count(clip_count: int) -> tuple[str, ...]:
    if clip_count <= 1:
        return (HERO_SHOT,)
    if clip_count == 2:
        return (ESTABLISHING_SHOT, REVEAL_SHOT)
    if clip_count == 3:
        return THREE_CLIP_ARC
    if clip_count == 4:
        return FOUR_CLIP_ARC
    if clip_count == 5:
        return FIVE_CLIP_ARC
    return SIX_CLIP_ARC[:clip_count] if clip_count <= 6 else _extended_arc(clip_count)


def _extended_arc(clip_count: int) -> tuple[str, ...]:
    pool = list(SIX_CLIP_ARC)
    extras = [MEDIUM_SHOT, WIDE_SHOT, DOLLY_IN, TRACKING_SHOT, CLOSE_UP, ORBIT_SHOT, REVEAL_SHOT, MACRO_DETAIL, AERIAL_SHOT]
    index = 0
    while len(pool) < clip_count:
        pool.append(extras[index % len(extras)])
        index += 1
    return tuple(pool[:clip_count])


def _category_adjustments(category: str, shots: list[str]) -> list[str]:
    adjusted = list(shots)
    if category == "wildlife" and len(adjusted) >= 2:
        if adjusted[1] not in {TRACKING_SHOT, MEDIUM_SHOT, WIDE_SHOT}:
            adjusted[1] = TRACKING_SHOT
        if len(adjusted) >= 3 and adjusted[-1] not in {HERO_SHOT, REVEAL_SHOT, CLOSE_UP}:
            adjusted[-1] = HERO_SHOT
    if category == "technology" and len(adjusted) >= 1:
        adjusted[0] = WIDE_SHOT if adjusted[0] == ESTABLISHING_SHOT else adjusted[0]
        if len(adjusted) >= 2:
            adjusted[1] = MACRO_DETAIL if adjusted[1] == TRACKING_SHOT else adjusted[1]
        if len(adjusted) >= 3:
            adjusted[-1] = REVEAL_SHOT if adjusted[-1] == HERO_SHOT else adjusted[-1]
    if category == "history" and len(adjusted) >= 2:
        adjusted[1] = DOLLY_IN if adjusted[1] != DOLLY_IN else adjusted[1]
    return adjusted


def _dedupe_adjacent(shots: list[str]) -> list[str]:
    if not shots:
        return shots
    result = [shots[0]]
    fallback_cycle = [MEDIUM_SHOT, TRACKING_SHOT, CLOSE_UP, WIDE_SHOT, REVEAL_SHOT, ORBIT_SHOT]
    cycle_index = 0
    for shot in shots[1:]:
        if shot == result[-1]:
            replacement = fallback_cycle[cycle_index % len(fallback_cycle)]
            while replacement == result[-1]:
                cycle_index += 1
                replacement = fallback_cycle[cycle_index % len(fallback_cycle)]
            result.append(replacement)
            cycle_index += 1
        else:
            result.append(shot)
    return result


def _scene_progression_labels(clip_count: int) -> list[str]:
    if clip_count == 1:
        return ["payoff"]
    if clip_count == 2:
        return ["establish world", "reveal payoff"]
    if clip_count == 3:
        return ["establish world", "build tension", "reveal payoff"]
    labels = ["establish world", "develop stakes"]
    for index in range(2, clip_count - 1):
        labels.append(f"escalate beat {index - 1}")
    labels.append("reveal payoff")
    return labels[:clip_count]


@dataclass
class PlannedShot:
    clip_index: int
    shot_type: str
    purpose: str
    scene_progression: str
    emotional_beat: str
    transition_out: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "shot_type": self.shot_type,
            "purpose": self.purpose,
            "scene_progression": self.scene_progression,
            "emotional_beat": self.emotional_beat,
            "transition_out": self.transition_out,
        }


@dataclass
class ShotPlan:
    version: str = PLANNER_VERSION
    clip_count: int = 0
    topic_category: str = "general"
    shots: list[PlannedShot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "clip_count": self.clip_count,
            "topic_category": self.topic_category,
            "shots": [shot.to_dict() for shot in self.shots],
        }


def plan_shot_sequence(
    *,
    clip_count: int,
    topic: str = "",
    story_brief: Any | None = None,
    emotional_arc: str = "",
    scene_progression: list[str] | None = None,
) -> ShotPlan:
    count = max(1, min(6, int(clip_count)))
    category = _topic_category(topic)
    base_arc = list(_arc_for_clip_count(count))
    base_arc = _category_adjustments(category, base_arc)
    base_arc = _dedupe_adjacent(base_arc)

    progression = list(scene_progression or [])
    if not progression and story_brief is not None:
        if isinstance(story_brief, dict):
            progression = list(story_brief.get("scene_progression") or [])
        elif hasattr(story_brief, "scene_progression"):
            progression = list(getattr(story_brief, "scene_progression") or [])
    if not progression:
        progression = _scene_progression_labels(count)

    emotional = _normalize(emotional_arc or _brief_value(story_brief, "emotional_arc", "rising cinematic arc"))
    planned: list[PlannedShot] = []
    for index, shot_type in enumerate(base_arc[:count], start=1):
        definition = get_shot(shot_type)
        transition = definition.recommended_transitions[0] if definition.recommended_transitions else "cut"
        planned.append(
            PlannedShot(
                clip_index=index,
                shot_type=shot_type,
                purpose=definition.purpose,
                scene_progression=progression[index - 1] if index - 1 < len(progression) else f"beat {index}",
                emotional_beat=emotional,
                transition_out=transition,
            )
        )
    return ShotPlan(clip_count=count, topic_category=category, shots=planned)


def has_duplicate_adjacent_shots(plan: ShotPlan) -> bool:
    types = [shot.shot_type for shot in plan.shots]
    return any(left == right for left, right in zip(types, types[1:]))


__all__ = [
    "PLANNER_VERSION",
    "PlannedShot",
    "ShotPlan",
    "has_duplicate_adjacent_shots",
    "plan_shot_sequence",
]
