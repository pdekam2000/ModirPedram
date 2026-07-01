"""Seamless continuity engine — per-clip state and cross-clip prompt chaining."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ENGINE_VERSION = "seamless_continuity_engine_v2"
CONTINUE_MARKER = "CONTINUE FROM PREVIOUS CLIP"
EXACT_FRAME_MARKER = "CONTINUE EXACTLY FROM PREVIOUS FRAME"


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _brief_value(story_brief: Any | None, key: str, fallback: str = "") -> str:
    if story_brief is None:
        return fallback
    if isinstance(story_brief, dict):
        return _normalize(str(story_brief.get(key) or fallback))
    return _normalize(str(getattr(story_brief, key, "") or fallback))


@dataclass
class ContinuityState:
    clip_index: int
    subject_state: str
    environment_state: str
    lighting_state: str
    camera_state: str
    motion_vector: str
    scene_composition: str
    emotional_state: str

    def to_dict(self) -> dict[str, str]:
        return {
            "clip_index": str(self.clip_index),
            "subject_state": self.subject_state,
            "environment_state": self.environment_state,
            "lighting_state": self.lighting_state,
            "camera_state": self.camera_state,
            "motion_vector": self.motion_vector,
            "scene_composition": self.scene_composition,
            "emotional_state": self.emotional_state,
        }


@dataclass
class SeamlessContinuityPlan:
    version: str = ENGINE_VERSION
    states: list[ContinuityState] = field(default_factory=list)
    clip_prompts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "states": [state.to_dict() for state in self.states],
            "clip_prompts": list(self.clip_prompts),
        }


def _phase_emotion(clip_index: int, clip_count: int) -> str:
    if clip_index == 1:
        return "curiosity and alert discovery"
    if clip_index >= clip_count:
        return "resolved payoff with held tension release"
    return "escalating commitment and rising stakes"


def _motion_vector(clip_index: int, clip_count: int) -> str:
    if clip_index == 1:
        return "slow discovery push-in toward subject"
    if clip_index >= clip_count:
        return "decelerating settle into final hero frame"
    return "continuous forward tracking through same blocking"


def _memory_subject_label(visual_memory: Any | None, fallback: str) -> str:
    if visual_memory is None:
        return fallback
    name = _normalize(str(getattr(visual_memory, "subject_name", "") or ""))
    if name:
        markings = _normalize(str(getattr(visual_memory, "markings", "") or ""))
        if markings:
            return f"{name} with {markings[:120]}"
        return name
    return fallback


def build_continuity_states(
    *,
    clip_count: int,
    story_brief: Any | None = None,
    anchors: Any | None = None,
    clip_beats: list[str] | None = None,
    visual_memory: Any | None = None,
) -> list[ContinuityState]:
    anchor = anchors.to_dict() if hasattr(anchors, "to_dict") else dict(anchors or {})
    subject = _memory_subject_label(
        visual_memory,
        _brief_value(story_brief, "subject") or _brief_value(story_brief, "main_character") or anchor.get("character", "primary subject"),
    )
    environment = _brief_value(story_brief, "environment") or _brief_value(story_brief, "setting") or anchor.get("location", "same location")
    if visual_memory is not None:
        environment = _normalize(getattr(visual_memory, "location", "") or environment)
    lighting = anchor.get("lighting") or "same motivated key direction and rim separation"
    if visual_memory is not None:
        lighting = _normalize(getattr(visual_memory, "lighting", "") or lighting)
    camera = anchor.get("camera") or "same lens family and vertical framing grammar"
    if visual_memory is not None:
        camera = _normalize(
            f"{getattr(visual_memory, 'camera_style', '') or camera} {getattr(visual_memory, 'lens', '')} {getattr(visual_memory, 'framing', '')}".strip()
        )
    beats = list(clip_beats or [])
    if not beats and isinstance(story_brief, dict):
        beats = list(story_brief.get("clip_beats") or [])
    elif not beats and story_brief is not None and hasattr(story_brief, "clip_beats"):
        beats = list(getattr(story_brief, "clip_beats") or [])

    states: list[ContinuityState] = []
    for index in range(1, clip_count + 1):
        beat = beats[index - 1] if index - 1 < len(beats) else f"story beat {index}"
        states.append(
            ContinuityState(
                clip_index=index,
                subject_state=_normalize(f"{subject} — identity locked; beat: {beat[:120]}"),
                environment_state=_normalize(f"{environment} — same spatial layout, props anchored, weather unchanged"),
                lighting_state=_normalize(lighting),
                camera_state=_normalize(camera),
                motion_vector=_motion_vector(index, clip_count),
                scene_composition="subject lower two-thirds, background depth preserved, eyeline matched, no jump cut",
                emotional_state=_phase_emotion(index, clip_count),
            )
        )
    return states


def _continuity_block(previous: ContinuityState, current: ContinuityState) -> str:
    subject_core = previous.subject_state.split(" —")[0]
    env_core = previous.environment_state.split(" —")[0]
    return _normalize(
        f"{CONTINUE_MARKER}. {EXACT_FRAME_MARKER}. "
        f"Maintain same subject identity ({subject_core}), same body position continuity, "
        f"same environment ({env_core}), same lighting ({previous.lighting_state}), "
        f"same weather, same motion continuity ({previous.motion_vector}), "
        f"same camera direction ({previous.camera_state}), same scene composition ({previous.scene_composition}). "
        f"No jump cuts. No subject replacement. No environment reset. No wardrobe swap. "
        f"Emotional progression: {previous.emotional_state} → {current.emotional_state}. "
        "Use Frame from previous clip last frame — continue exactly from previous frame pose and blocking."
    )


def apply_seamless_continuity(
    *,
    clip_prompts: list[str],
    story_brief: Any | None = None,
    anchors: Any | None = None,
    clip_beats: list[str] | None = None,
    visual_memory: Any | None = None,
    scene_recalls: list[Any] | None = None,
) -> SeamlessContinuityPlan:
    states = build_continuity_states(
        clip_count=len(clip_prompts),
        story_brief=story_brief,
        anchors=anchors,
        clip_beats=clip_beats,
        visual_memory=visual_memory,
    )
    recall_by_index = {
        int(getattr(item, "clip_index", 0) or (item.get("clip_index") if isinstance(item, dict) else 0)): item
        for item in list(scene_recalls or [])
    }
    updated: list[str] = []
    for index, prompt in enumerate(clip_prompts):
        if index == 0:
            updated.append(_normalize(prompt))
            continue
        block = _continuity_block(states[index - 1], states[index])
        recall = recall_by_index.get(index)
        recall_text = ""
        if recall is not None:
            if hasattr(recall, "recall_block"):
                recall_text = recall.recall_block()
            elif isinstance(recall, dict):
                recall_text = _normalize(str(recall.get("recall_block") or ""))
        updated.append(_normalize(f"{block} {recall_text} {prompt}"))
    return SeamlessContinuityPlan(states=states, clip_prompts=updated)


__all__ = [
    "CONTINUE_MARKER",
    "ENGINE_VERSION",
    "EXACT_FRAME_MARKER",
    "ContinuityState",
    "SeamlessContinuityPlan",
    "apply_seamless_continuity",
    "build_continuity_states",
]
