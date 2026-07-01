"""Cinematic shot library — typed shots with purpose, behavior, and transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SHOT_LIBRARY_VERSION = "shot_library_v1"

ESTABLISHING_SHOT = "establishing_shot"
WIDE_SHOT = "wide_shot"
MEDIUM_SHOT = "medium_shot"
CLOSE_UP = "close_up"
EXTREME_CLOSE_UP = "extreme_close_up"
TRACKING_SHOT = "tracking_shot"
DOLLY_IN = "dolly_in"
DOLLY_OUT = "dolly_out"
ORBIT_SHOT = "orbit_shot"
OVER_SHOULDER = "over_shoulder"
REVEAL_SHOT = "reveal_shot"
HERO_SHOT = "hero_shot"
CINEMATIC_PAN = "cinematic_pan"
LOW_ANGLE = "low_angle"
HIGH_ANGLE = "high_angle"
AERIAL_SHOT = "aerial_shot"
MACRO_DETAIL = "macro_detail"

ALL_SHOT_TYPES: tuple[str, ...] = (
    ESTABLISHING_SHOT,
    WIDE_SHOT,
    MEDIUM_SHOT,
    CLOSE_UP,
    EXTREME_CLOSE_UP,
    TRACKING_SHOT,
    DOLLY_IN,
    DOLLY_OUT,
    ORBIT_SHOT,
    OVER_SHOULDER,
    REVEAL_SHOT,
    HERO_SHOT,
    CINEMATIC_PAN,
    LOW_ANGLE,
    HIGH_ANGLE,
    AERIAL_SHOT,
    MACRO_DETAIL,
)


@dataclass(frozen=True)
class ShotDefinition:
    shot_type: str
    purpose: str
    camera_behavior: str
    emotional_effect: str
    recommended_transitions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_type": self.shot_type,
            "purpose": self.purpose,
            "camera_behavior": self.camera_behavior,
            "emotional_effect": self.emotional_effect,
            "recommended_transitions": list(self.recommended_transitions),
        }


SHOT_LIBRARY: dict[str, ShotDefinition] = {
    ESTABLISHING_SHOT: ShotDefinition(
        shot_type=ESTABLISHING_SHOT,
        purpose="Establish world, location, and scale before subject focus.",
        camera_behavior="Slow wide push or locked wide frame with environmental depth layers.",
        emotional_effect="Orientation, awe, and narrative grounding.",
        recommended_transitions=("cut_to_medium", "motivated_pan_into_subject"),
    ),
    WIDE_SHOT: ShotDefinition(
        shot_type=WIDE_SHOT,
        purpose="Show subject in full environmental context.",
        camera_behavior="Static or gentle lateral drift; subject readable in frame thirds.",
        emotional_effect="Context, isolation, or epic scale.",
        recommended_transitions=("tracking_shot", "dolly_in"),
    ),
    MEDIUM_SHOT: ShotDefinition(
        shot_type=MEDIUM_SHOT,
        purpose="Balance subject performance with surrounding context.",
        camera_behavior="Waist-up or mid-body framing with stable handheld or tripod base.",
        emotional_effect="Connection and conversational intimacy.",
        recommended_transitions=("close_up", "over_shoulder"),
    ),
    CLOSE_UP: ShotDefinition(
        shot_type=CLOSE_UP,
        purpose="Focus attention on face, detail, or emotional reaction.",
        camera_behavior="Tight framing with shallow depth of field and minimal drift.",
        emotional_effect="Intensity, empathy, and stakes.",
        recommended_transitions=("extreme_close_up", "dolly_out"),
    ),
    EXTREME_CLOSE_UP: ShotDefinition(
        shot_type=EXTREME_CLOSE_UP,
        purpose="Isolate a critical detail — eyes, texture, mechanism.",
        camera_behavior="Macro-adjacent tight frame; micro-movement only.",
        emotional_effect="Suspense, discovery, or visceral impact.",
        recommended_transitions=("reveal_shot", "pull_back_to_medium"),
    ),
    TRACKING_SHOT: ShotDefinition(
        shot_type=TRACKING_SHOT,
        purpose="Follow subject through space to build momentum.",
        camera_behavior="Lateral or forward tracking matched to subject speed.",
        emotional_effect="Urgency, pursuit, and rising tension.",
        recommended_transitions=("hero_shot", "dolly_in"),
    ),
    DOLLY_IN: ShotDefinition(
        shot_type=DOLLY_IN,
        purpose="Escalate focus toward subject or revelation.",
        camera_behavior="Smooth forward dolly push with tightening composition.",
        emotional_effect="Discovery, commitment, and mounting pressure.",
        recommended_transitions=("close_up", "reveal_shot"),
    ),
    DOLLY_OUT: ShotDefinition(
        shot_type=DOLLY_OUT,
        purpose="Reveal broader context or release tension.",
        camera_behavior="Controlled backward dolly revealing environment.",
        emotional_effect="Relief, consequence, or scale reframe.",
        recommended_transitions=("wide_shot", "establishing_shot"),
    ),
    ORBIT_SHOT: ShotDefinition(
        shot_type=ORBIT_SHOT,
        purpose="Show subject from changing angles while maintaining focus.",
        camera_behavior="Arc movement around subject with constant eyeline priority.",
        emotional_effect="Dynamism, heroism, and dimensional depth.",
        recommended_transitions=("hero_shot", "low_angle"),
    ),
    OVER_SHOULDER: ShotDefinition(
        shot_type=OVER_SHOULDER,
        purpose="Create POV tension or observational intimacy.",
        camera_behavior="Shoulder foreground occluder with subject in deep plane.",
        emotional_effect="Participation, mystery, or confrontation.",
        recommended_transitions=("medium_shot", "tracking_shot"),
    ),
    REVEAL_SHOT: ShotDefinition(
        shot_type=REVEAL_SHOT,
        purpose="Uncover key information or payoff element.",
        camera_behavior="Motivated move from partial occlusion to full reveal.",
        emotional_effect="Surprise, satisfaction, and narrative payoff.",
        recommended_transitions=("hero_shot", "close_up"),
    ),
    HERO_SHOT: ShotDefinition(
        shot_type=HERO_SHOT,
        purpose="Present subject at peak visual power for final impression.",
        camera_behavior="Low or centered hero framing with controlled push-in or hold.",
        emotional_effect="Triumph, resolution, and memorability.",
        recommended_transitions=("hold_end_frame", "soft_dolly_out"),
    ),
    CINEMATIC_PAN: ShotDefinition(
        shot_type=CINEMATIC_PAN,
        purpose="Scan environment or connect spatial elements.",
        camera_behavior="Slow horizontal or vertical pan with motivated start/end points.",
        emotional_effect="Exploration, passage of time, or world-building.",
        recommended_transitions=("medium_shot", "tracking_shot"),
    ),
    LOW_ANGLE: ShotDefinition(
        shot_type=LOW_ANGLE,
        purpose="Empower subject or increase dramatic dominance.",
        camera_behavior="Upward tilt from below subject plane.",
        emotional_effect="Power, threat, or grandeur.",
        recommended_transitions=("hero_shot", "tracking_shot"),
    ),
    HIGH_ANGLE: ShotDefinition(
        shot_type=HIGH_ANGLE,
        purpose="Diminish subject or expose vulnerability.",
        camera_behavior="Downward tilt from elevated position.",
        emotional_effect="Vulnerability, overview, or fate.",
        recommended_transitions=("wide_shot", "aerial_shot"),
    ),
    AERIAL_SHOT: ShotDefinition(
        shot_type=AERIAL_SHOT,
        purpose="Show geography, journey, or epic scope.",
        camera_behavior="Elevated drift or descent with horizon control.",
        emotional_effect="Scale, destiny, and cinematic scope.",
        recommended_transitions=("establishing_shot", "tracking_shot"),
    ),
    MACRO_DETAIL: ShotDefinition(
        shot_type=MACRO_DETAIL,
        purpose="Highlight texture, mechanism, or product craft.",
        camera_behavior="Extreme close macro with rack focus optional.",
        emotional_effect="Precision, curiosity, and tactile fascination.",
        recommended_transitions=("dolly_out", "reveal_shot"),
    ),
}


def get_shot(shot_type: str) -> ShotDefinition:
    key = str(shot_type or "").strip().lower()
    if key not in SHOT_LIBRARY:
        return SHOT_LIBRARY[MEDIUM_SHOT]
    return SHOT_LIBRARY[key]


def list_shots() -> list[ShotDefinition]:
    return [SHOT_LIBRARY[key] for key in ALL_SHOT_TYPES]


__all__ = [
    "ALL_SHOT_TYPES",
    "SHOT_LIBRARY",
    "SHOT_LIBRARY_VERSION",
    "ShotDefinition",
    "get_shot",
    "list_shots",
]
