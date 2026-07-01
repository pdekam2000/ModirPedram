"""Camera language engine — movement, lens, framing, and composition by topic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content_brain.director.shot_library import get_shot
from content_brain.director.shot_planner import PlannedShot

CAMERA_LANGUAGE_VERSION = "camera_language_engine_v1"

DIRECTOR_CAMERA_PLAN_MARKER = "DIRECTOR CAMERA PLAN"


@dataclass
class CameraLanguagePlan:
    clip_index: int
    shot_type: str
    camera_movement: str
    lens: str
    framing: str
    composition: str
    visual_objective: str
    domain: str = "general"

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "shot_type": self.shot_type,
            "camera_movement": self.camera_movement,
            "lens": self.lens,
            "framing": self.framing,
            "composition": self.composition,
            "visual_objective": self.visual_objective,
            "domain": self.domain,
        }

    def prompt_block(self) -> str:
        return (
            f"{DIRECTOR_CAMERA_PLAN_MARKER}. "
            f"Shot type: {self.shot_type}. "
            f"Camera movement: {self.camera_movement}. "
            f"Lens: {self.lens}. "
            f"Composition: {self.composition}. "
            f"Framing: {self.framing}. "
            f"Visual objective: {self.visual_objective}."
        )


def _domain_profile(domain: str) -> dict[str, str]:
    profiles = {
        "wildlife": {
            "lens_default": "telephoto 85–135mm equivalent",
            "movement_default": "documentary tracking with natural handheld stability",
            "composition_default": "subject in lower two-thirds with habitat depth",
            "objective_default": "capture authentic animal behavior with cinematic tension",
        },
        "technology": {
            "lens_default": "35mm product lens with macro capability",
            "movement_default": "cinematic product reveal with controlled orbit or dolly",
            "composition_default": "center-weighted hero product with negative space",
            "objective_default": "showcase design detail and performance cues",
        },
        "history": {
            "lens_default": "50mm anamorphic-style dramatic lens",
            "movement_default": "slow dramatic push-in with reverent pacing",
            "composition_default": "symmetrical framing with depth layers and practical light",
            "objective_default": "evoke period weight and narrative gravitas",
        },
        "general": {
            "lens_default": "50mm cinematic prime",
            "movement_default": "motivated dolly or tracking matched to story beat",
            "composition_default": "rule-of-thirds vertical hero framing",
            "objective_default": "advance story beat with clear visual hierarchy",
        },
    }
    return profiles.get(domain, profiles["general"])


def _movement_for_shot(shot_type: str, domain: str) -> str:
    definition = get_shot(shot_type)
    behavior = definition.camera_behavior
    if domain == "wildlife" and "tracking" in shot_type:
        return f"telephoto documentary tracking — {behavior}"
    if domain == "technology" and shot_type in {"macro_detail", "reveal_shot", "hero_shot"}:
        return f"cinematic product reveal movement — {behavior}"
    if domain == "history" and shot_type in {"dolly_in", "close_up", "establishing_shot"}:
        return f"slow dramatic push-in — {behavior}"
    return behavior


def generate_camera_language(
    *,
    planned_shot: PlannedShot,
    topic_category: str = "general",
) -> CameraLanguagePlan:
    profile = _domain_profile(topic_category)
    shot_type = planned_shot.shot_type
    movement = _movement_for_shot(shot_type, topic_category)
    lens = profile["lens_default"]
    if shot_type in {"close_up", "extreme_close_up", "macro_detail"}:
        lens = "85mm macro-detail lens" if topic_category == "technology" else "85–100mm portrait-macro lens"
    if shot_type in {"aerial_shot", "establishing_shot", "wide_shot"}:
        lens = "24mm wide establishing lens"
    if shot_type == "hero_shot":
        lens = "35–50mm hero lens with subtle compression"

    framing = {
        "establishing_shot": "wide vertical establishing frame",
        "tracking_shot": "mid-wide tracking frame with lead room",
        "hero_shot": "centered hero frame with chin-safe headroom",
        "reveal_shot": "partial occlusion to full reveal framing",
        "macro_detail": "extreme close product/texture frame",
    }.get(shot_type, profile["composition_default"])

    composition = profile["composition_default"]
    objective = f"{planned_shot.scene_progression} — {profile['objective_default']}"

    return CameraLanguagePlan(
        clip_index=planned_shot.clip_index,
        shot_type=shot_type,
        camera_movement=movement,
        lens=lens,
        framing=framing if isinstance(framing, str) else profile["composition_default"],
        composition=composition,
        visual_objective=objective,
        domain=topic_category,
    )


def generate_camera_language_for_plan(
    *,
    shot_plan: Any,
    topic_category: str = "general",
) -> list[CameraLanguagePlan]:
    shots = list(getattr(shot_plan, "shots", []) or [])
    return [generate_camera_language(planned_shot=shot, topic_category=topic_category) for shot in shots]


__all__ = [
    "CAMERA_LANGUAGE_VERSION",
    "DIRECTOR_CAMERA_PLAN_MARKER",
    "CameraLanguagePlan",
    "generate_camera_language",
    "generate_camera_language_for_plan",
]
