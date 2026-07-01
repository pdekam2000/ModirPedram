"""Visual rhythm engine — score framing and movement variety across clips."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content_brain.director.camera_language_engine import CameraLanguagePlan
from content_brain.director.shot_planner import ShotPlan

RHYTHM_ENGINE_VERSION = "visual_rhythm_engine_v1"
PASS_THRESHOLD = 65.0


@dataclass
class VisualRhythmScore:
    rhythm_score: float = 0.0
    framing_variety: float = 0.0
    angle_variety: float = 0.0
    movement_variety: float = 0.0
    pacing_variety: float = 0.0
    pass_: bool = False
    warnings: list[str] | None = None
    version: str = RHYTHM_ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "rhythm_score": round(self.rhythm_score, 2),
            "framing_variety": round(self.framing_variety, 2),
            "angle_variety": round(self.angle_variety, 2),
            "movement_variety": round(self.movement_variety, 2),
            "pacing_variety": round(self.pacing_variety, 2),
            "pass": self.pass_,
            "pass_threshold": PASS_THRESHOLD,
            "warnings": list(self.warnings or []),
        }


_ANGLE_SHOTS = {"low_angle", "high_angle", "aerial_shot", "over_shoulder"}
_WIDE_SHOTS = {"establishing_shot", "wide_shot", "aerial_shot"}
_TIGHT_SHOTS = {"close_up", "extreme_close_up", "macro_detail"}


def _variety_ratio(values: list[str]) -> float:
    if not values:
        return 0.0
    unique = len(set(values))
    return min(100.0, (unique / len(values)) * 100.0)


def _adjacent_duplicate_penalty(values: list[str]) -> float:
    penalty = 0.0
    for left, right in zip(values, values[1:]):
        if left == right:
            penalty += 20.0
    return penalty


def score_visual_rhythm(
    *,
    shot_plan: ShotPlan,
    camera_plans: list[CameraLanguagePlan],
    pacing_curve: list[str] | None = None,
) -> VisualRhythmScore:
    shot_types = [shot.shot_type for shot in shot_plan.shots]
    framings = [plan.framing for plan in camera_plans]
    movements = [plan.camera_movement for plan in camera_plans]
    pacing = list(pacing_curve or [])

    framing_variety = _variety_ratio(shot_types + framings)
    angle_variety = _variety_ratio([shot for shot in shot_types if shot in _ANGLE_SHOTS] or shot_types)
    movement_variety = _variety_ratio(movements)
    pacing_variety = _variety_ratio(pacing) if pacing else _variety_ratio(["open", "build", "payoff"][: len(shot_types)])

    penalties = _adjacent_duplicate_penalty(shot_types)
    penalties += _adjacent_duplicate_penalty(movements) * 0.5

    rhythm_score = max(
        0.0,
        min(
            100.0,
            framing_variety * 0.30
            + angle_variety * 0.20
            + movement_variety * 0.30
            + pacing_variety * 0.20
            - penalties,
        ),
    )

    warnings: list[str] = []
    if _adjacent_duplicate_penalty(shot_types) > 0:
        warnings.append("adjacent_duplicate_shot_types")
    if len(set(shot_types)) < max(1, len(shot_types) - 1):
        warnings.append("low_shot_type_variety")

    wide_count = sum(1 for shot in shot_types if shot in _WIDE_SHOTS)
    tight_count = sum(1 for shot in shot_types if shot in _TIGHT_SHOTS)
    if wide_count == len(shot_types) or tight_count == len(shot_types):
        warnings.append("repetitive_framing_scale")

    return VisualRhythmScore(
        rhythm_score=round(rhythm_score, 2),
        framing_variety=round(framing_variety, 2),
        angle_variety=round(angle_variety, 2),
        movement_variety=round(movement_variety, 2),
        pacing_variety=round(pacing_variety, 2),
        pass_=rhythm_score >= PASS_THRESHOLD,
        warnings=warnings,
    )


__all__ = [
    "PASS_THRESHOLD",
    "RHYTHM_ENGINE_VERSION",
    "VisualRhythmScore",
    "score_visual_rhythm",
]
