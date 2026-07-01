"""Kling Frame-to-Video Native Audio — schema models and mode constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.kling_multishot_config import CLIP_DURATION_SECONDS
from content_brain.execution.kling_native_audio_models import (
    FIRST_FRAME_PRIOR_CLIP,
    FIRST_FRAME_PROMPT_ONLY,
    FIRST_FRAME_USER_UPLOAD,
    KLING_AUDIO_STRATEGY,
    KLING_CONTINUITY_CHAIN_VERSION,
    KLING_DURATION_STEP_SECONDS,
    KLING_PROVIDER_ID,
    NativeAudioDirectives,
    normalize_kling_duration,
)

KLING_FRAME_TO_VIDEO_PLAN_VERSION = "kling_frame_to_video_plan_v1"
KLING_FRAME_TO_VIDEO_MODE = "kling_frame_to_video_native_audio"
KLING_MULTISHOT_MODE = "kling_multishot_native_audio"

FRAME_STORY_SUPPORTED_DURATIONS: tuple[int, ...] = (15, 30, 45, 60, 75, 90)
FRAME_STORY_MAX_SECONDS = 90

KLING_FRAME_PROMPT_MAX_CHARS = 2500
from content_brain.story.story_first_prompt_engine import (  # noqa: E402
    STORY_FIRST_PROMPT_TARGET_MAX as KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
    STORY_FIRST_PROMPT_TARGET_MIN as KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
)

END_FRAME_USER_UPLOAD = "user_upload"
END_FRAME_PRIOR_CLIP = "prior_clip_final_frame"
END_FRAME_GENERATED_TARGET = "generated_target_frame"
END_FRAME_NONE = "none"

FRAME_MODE_PREFERRED_GENRES: frozenset[str] = frozenset(
    {
        "cinematic",
        "dialogue",
        "fantasy",
        "animal",
        "emotional",
        "sci-fi",
        "character",
    }
)


@dataclass
class KlingFrameToVideoClipPlan:
    clip_index: int
    duration_seconds: int
    first_frame_source: str
    end_frame_source: str
    prompt: str
    character_continuity: str
    environment_continuity: str
    dialogue: str
    native_audio_directives: NativeAudioDirectives
    camera_direction: str
    continuity_anchor: str
    next_clip_reference_hint: str
    prior_clip_index: int | None = None
    end_frame_path: str = ""
    first_frame_path: str = ""
    chapter_progression: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        directives = self.native_audio_directives
        if isinstance(directives, dict):
            directives = NativeAudioDirectives.from_dict(directives)
        return {
            "clip_index": self.clip_index,
            "duration_seconds": self.duration_seconds,
            "first_frame_source": self.first_frame_source,
            "end_frame_source": self.end_frame_source,
            "first_frame_path": self.first_frame_path,
            "end_frame_path": self.end_frame_path,
            "prompt": self.prompt,
            "character_continuity": self.character_continuity,
            "environment_continuity": self.environment_continuity,
            "dialogue": self.dialogue,
            "native_audio_directives": directives.to_dict(),
            "camera_direction": self.camera_direction,
            "continuity_anchor": self.continuity_anchor,
            "next_clip_reference_hint": self.next_clip_reference_hint,
            "prior_clip_index": self.prior_clip_index,
            "chapter_progression": dict(self.chapter_progression),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingFrameToVideoClipPlan:
        return cls(
            clip_index=int(payload.get("clip_index") or 0),
            duration_seconds=int(payload.get("duration_seconds") or CLIP_DURATION_SECONDS),
            first_frame_source=str(payload.get("first_frame_source") or ""),
            end_frame_source=str(payload.get("end_frame_source") or ""),
            first_frame_path=str(payload.get("first_frame_path") or ""),
            end_frame_path=str(payload.get("end_frame_path") or ""),
            prompt=str(payload.get("prompt") or ""),
            character_continuity=str(payload.get("character_continuity") or ""),
            environment_continuity=str(payload.get("environment_continuity") or ""),
            dialogue=str(payload.get("dialogue") or ""),
            native_audio_directives=NativeAudioDirectives.from_dict(
                payload.get("native_audio_directives")  # type: ignore[arg-type]
            ),
            camera_direction=str(payload.get("camera_direction") or ""),
            continuity_anchor=str(payload.get("continuity_anchor") or ""),
            next_clip_reference_hint=str(payload.get("next_clip_reference_hint") or ""),
            prior_clip_index=(
                int(payload["prior_clip_index"])
                if payload.get("prior_clip_index") is not None
                else None
            ),
            chapter_progression=dict(payload.get("chapter_progression") or {}),
        )


@dataclass
class KlingFrameToVideoPlan:
    requested_duration_seconds: int
    planned_duration_seconds: int
    clip_count: int
    clips: list[KlingFrameToVideoClipPlan]
    topic: str = ""
    platform: str = ""
    version: str = KLING_FRAME_TO_VIDEO_PLAN_VERSION
    provider_mode: str = KLING_FRAME_TO_VIDEO_MODE
    provider: str = KLING_PROVIDER_ID
    audio_strategy: str = KLING_AUDIO_STRATEGY
    generation_mode: str = KLING_FRAME_TO_VIDEO_MODE
    fallback_mode: str = KLING_MULTISHOT_MODE
    native_audio_required: bool = True
    prompt_max_chars: int = KLING_FRAME_PROMPT_MAX_CHARS
    duration_warnings: tuple[str, ...] = ()
    story_progression: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "provider_mode": self.provider_mode,
            "provider": self.provider,
            "audio_strategy": self.audio_strategy,
            "generation_mode": self.generation_mode,
            "fallback_mode": self.fallback_mode,
            "requested_duration_seconds": self.requested_duration_seconds,
            "planned_duration_seconds": self.planned_duration_seconds,
            "clip_count": self.clip_count,
            "clips": [clip.to_dict() for clip in self.clips],
            "topic": self.topic,
            "platform": self.platform,
            "native_audio_required": self.native_audio_required,
            "prompt_max_chars": self.prompt_max_chars,
            "prompt_target_min_chars": KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
            "prompt_target_max_chars": KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
            "duration_warnings": list(self.duration_warnings),
            "story_progression": dict(self.story_progression),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingFrameToVideoPlan:
        return cls(
            version=str(payload.get("version") or KLING_FRAME_TO_VIDEO_PLAN_VERSION),
            provider_mode=str(payload.get("provider_mode") or KLING_FRAME_TO_VIDEO_MODE),
            provider=str(payload.get("provider") or KLING_PROVIDER_ID),
            audio_strategy=str(payload.get("audio_strategy") or KLING_AUDIO_STRATEGY),
            generation_mode=str(payload.get("generation_mode") or KLING_FRAME_TO_VIDEO_MODE),
            fallback_mode=str(payload.get("fallback_mode") or KLING_MULTISHOT_MODE),
            requested_duration_seconds=int(payload.get("requested_duration_seconds") or 0),
            planned_duration_seconds=int(payload.get("planned_duration_seconds") or 0),
            clip_count=int(payload.get("clip_count") or 0),
            clips=[
                KlingFrameToVideoClipPlan.from_dict(dict(item))
                for item in list(payload.get("clips") or [])
            ],
            topic=str(payload.get("topic") or ""),
            platform=str(payload.get("platform") or ""),
            native_audio_required=bool(payload.get("native_audio_required", True)),
            prompt_max_chars=int(payload.get("prompt_max_chars") or KLING_FRAME_PROMPT_MAX_CHARS),
            duration_warnings=tuple(str(w) for w in list(payload.get("duration_warnings") or [])),
            story_progression=dict(payload.get("story_progression") or {}),
        )


def select_kling_generation_mode(
    *,
    topic: str = "",
    genre: str = "",
    mood: str = "",
    has_dialogue: bool = False,
    frame_mode_available: bool = True,
    explicit_mode: str = "",
) -> str:
    """Return preferred Kling generation mode; multishot is fallback when frame mode unavailable."""
    mode = str(explicit_mode or "").strip().lower()
    if mode == KLING_MULTISHOT_MODE:
        return KLING_MULTISHOT_MODE
    if mode == KLING_FRAME_TO_VIDEO_MODE:
        return KLING_FRAME_TO_VIDEO_MODE if frame_mode_available else KLING_MULTISHOT_MODE
    if not frame_mode_available:
        return KLING_MULTISHOT_MODE

    haystack = " ".join([topic, genre, mood]).lower()
    if has_dialogue:
        return KLING_FRAME_TO_VIDEO_MODE
    if any(token in haystack for token in FRAME_MODE_PREFERRED_GENRES):
        return KLING_FRAME_TO_VIDEO_MODE
    if any(token in haystack for token in ("dragon", "boy", "girl", "woman", "robot", "dog", "whisper")):
        return KLING_FRAME_TO_VIDEO_MODE
    return KLING_FRAME_TO_VIDEO_MODE


def normalize_kling_frame_story_duration(requested_duration_seconds: int) -> tuple[int, int, tuple[str, ...]]:
    """Map requested story duration to planned seconds and 15s clip count (up to 90s / 6 clips)."""
    requested = max(1, int(requested_duration_seconds))
    warnings: list[str] = []

    if requested in FRAME_STORY_SUPPORTED_DURATIONS:
        planned = requested
    else:
        planned = (
            (requested + KLING_DURATION_STEP_SECONDS - 1) // KLING_DURATION_STEP_SECONDS
        ) * KLING_DURATION_STEP_SECONDS
        planned = max(KLING_DURATION_STEP_SECONDS, planned)
        if planned > FRAME_STORY_MAX_SECONDS:
            planned = FRAME_STORY_MAX_SECONDS
            warnings.append(
                f"requested_duration_seconds={requested} capped at {FRAME_STORY_MAX_SECONDS}s maximum story pack"
            )
        if planned != requested:
            warnings.append(
                f"requested_duration_seconds={requested} rounded up to planned_duration_seconds={planned}"
            )

    clip_count = planned // KLING_DURATION_STEP_SECONDS
    return planned, clip_count, tuple(warnings)


def validate_kling_frame_to_video_plan(plan: KlingFrameToVideoPlan) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if plan.version != KLING_FRAME_TO_VIDEO_PLAN_VERSION:
        errors.append(f"unexpected plan version: {plan.version}")
    if plan.provider_mode != KLING_FRAME_TO_VIDEO_MODE:
        errors.append(f"unexpected provider_mode: {plan.provider_mode}")
    if plan.fallback_mode != KLING_MULTISHOT_MODE:
        errors.append(f"fallback_mode must be {KLING_MULTISHOT_MODE}")
    if plan.prompt_max_chars != KLING_FRAME_PROMPT_MAX_CHARS:
        errors.append(f"prompt_max_chars must be {KLING_FRAME_PROMPT_MAX_CHARS}")
    if not plan.native_audio_required:
        errors.append("native_audio_required must be true")

    expected_clips = plan.planned_duration_seconds // CLIP_DURATION_SECONDS
    if plan.clip_count != expected_clips:
        errors.append(f"clip_count {plan.clip_count} != expected {expected_clips}")
    if len(plan.clips) != plan.clip_count:
        errors.append(f"clips length {len(plan.clips)} != clip_count {plan.clip_count}")

    for clip in plan.clips:
        if clip.duration_seconds != CLIP_DURATION_SECONDS:
            errors.append(f"clip {clip.clip_index}: duration_seconds must be {CLIP_DURATION_SECONDS}")
        if not clip.prompt.strip():
            errors.append(f"clip {clip.clip_index}: prompt must be non-empty")
        if len(clip.prompt) > KLING_FRAME_PROMPT_MAX_CHARS:
            errors.append(
                f"clip {clip.clip_index}: prompt exceeds {KLING_FRAME_PROMPT_MAX_CHARS} chars"
            )
        if clip.clip_index == 1 and clip.first_frame_source not in (
            FIRST_FRAME_PROMPT_ONLY,
            FIRST_FRAME_USER_UPLOAD,
            "",
        ):
            errors.append(
                f"clip 1: first_frame_source must be {FIRST_FRAME_PROMPT_ONLY} or {FIRST_FRAME_USER_UPLOAD}"
            )
        if clip.clip_index > 1 and clip.first_frame_source != FIRST_FRAME_PRIOR_CLIP:
            errors.append(f"clip {clip.clip_index}: first_frame_source must be {FIRST_FRAME_PRIOR_CLIP}")

    return not errors, errors


__all__ = [
    "FRAME_STORY_MAX_SECONDS",
    "FRAME_STORY_SUPPORTED_DURATIONS",
    "END_FRAME_GENERATED_TARGET",
    "END_FRAME_NONE",
    "END_FRAME_PRIOR_CLIP",
    "END_FRAME_USER_UPLOAD",
    "FRAME_MODE_PREFERRED_GENRES",
    "KLING_FRAME_PROMPT_MAX_CHARS",
    "KLING_FRAME_PROMPT_TARGET_MAX_CHARS",
    "KLING_FRAME_PROMPT_TARGET_MIN_CHARS",
    "KLING_FRAME_TO_VIDEO_MODE",
    "KLING_FRAME_TO_VIDEO_PLAN_VERSION",
    "KLING_MULTISHOT_MODE",
    "KlingFrameToVideoClipPlan",
    "KlingFrameToVideoPlan",
    "normalize_kling_frame_story_duration",
    "select_kling_generation_mode",
    "validate_kling_frame_to_video_plan",
]
