"""Scheduling — duration planning and clip count calculation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content_brain.execution.kling_multishot_config import (
    CLIP_DURATION_SECONDS,
    MULTISHOT_STRATEGY,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_native_audio_models import (
    KLING_AUDIO_STRATEGY,
    KLING_PROVIDER_ID,
    KLING_SHOT_PROMPT_MAX_CHARS,
    normalize_kling_duration,
)

PRESET_DURATIONS = (6, 8, 10, 20, 30, 40)
MIN_DURATION_SECONDS = 6
MAX_DURATION_SOFT_WARN = 120
MAX_DURATION_HARD = 600

PROVIDER_CLIP_LIMIT_SECONDS: dict[str, int] = {
    "runway": 10,
    "hailuo": 8,
    "default": 10,
    "kling_3_0_pro_native_audio": CLIP_DURATION_SECONDS,
    "kling_3_pro_native": CLIP_DURATION_SECONDS,
    "kling": CLIP_DURATION_SECONDS,
}

KLING_PROVIDER_ALIASES: frozenset[str] = frozenset(
    {
        "kling_3_0_pro_native_audio",
        "kling_3_pro_native",
        "kling",
        "kling_native_audio",
    }
)

SINGLE_CLIP_PRESETS = {6, 8, 10}


@dataclass(frozen=True)
class DurationPlan:
    duration_seconds: int
    clip_count: int
    provider: str
    clip_limit_seconds: int
    warnings: tuple[str, ...] = ()
    requested_duration_seconds: int = 0
    kling_native_audio: bool = False
    audio_strategy: str = ""
    shot_mode: str = ""
    shot_1_duration_seconds: int = 0
    shot_2_duration_seconds: int = 0
    native_audio_required: bool = False
    use_elevenlabs: bool = True
    use_external_music: bool = True
    subtitle_required: bool = True
    shot_prompt_max_chars: int = 0


def is_kling_native_audio_route(*, provider: str, audio_strategy: str | None = None) -> bool:
    strategy = str(audio_strategy or "").strip().lower()
    if strategy == KLING_AUDIO_STRATEGY:
        return True
    key = str(provider or "").strip().lower()
    return key in KLING_PROVIDER_ALIASES


def provider_clip_limit(provider: str) -> int:
    key = str(provider or "runway").strip().lower()
    if key in KLING_PROVIDER_ALIASES:
        return CLIP_DURATION_SECONDS
    return PROVIDER_CLIP_LIMIT_SECONDS.get(key, PROVIDER_CLIP_LIMIT_SECONDS["default"])


def validate_duration_seconds(duration_seconds: int) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    value = int(duration_seconds)
    if value < MIN_DURATION_SECONDS:
        return False, [f"duration must be at least {MIN_DURATION_SECONDS} seconds"]
    if value > MAX_DURATION_SOFT_WARN:
        warnings.append(f"duration {value}s exceeds recommended max {MAX_DURATION_SOFT_WARN}s")
    if value > MAX_DURATION_HARD:
        return False, [f"duration must not exceed {MAX_DURATION_HARD} seconds"]
    return True, warnings


def calculate_clip_count(*, duration_seconds: int, provider: str = "runway") -> int:
    if is_kling_native_audio_route(provider=provider):
        _, clip_count, _ = normalize_kling_duration(duration_seconds)
        return clip_count

    duration = max(MIN_DURATION_SECONDS, int(duration_seconds))
    limit = provider_clip_limit(provider)
    if duration in SINGLE_CLIP_PRESETS:
        return 1
    if duration in {20, 30, 40}:
        return max(1, (duration + limit - 1) // limit)
    return max(1, (duration + limit - 1) // limit)


def plan_kling_duration(*, duration_seconds: int) -> DurationPlan:
    requested = int(duration_seconds)
    ok, messages = validate_duration_seconds(requested)
    if not ok:
        raise ValueError(messages[0] if messages else "invalid duration")

    planned, clip_count, kling_warnings = normalize_kling_duration(requested)
    warnings = tuple(list(messages) + list(kling_warnings))
    return DurationPlan(
        duration_seconds=planned,
        clip_count=clip_count,
        provider=KLING_PROVIDER_ID,
        clip_limit_seconds=CLIP_DURATION_SECONDS,
        warnings=warnings,
        requested_duration_seconds=requested,
        kling_native_audio=True,
        audio_strategy=KLING_AUDIO_STRATEGY,
        shot_mode=MULTISHOT_STRATEGY,
        shot_1_duration_seconds=SHOT_1_DURATION_SECONDS,
        shot_2_duration_seconds=SHOT_2_DURATION_SECONDS,
        native_audio_required=True,
        use_elevenlabs=False,
        use_external_music=False,
        subtitle_required=True,
        shot_prompt_max_chars=KLING_SHOT_PROMPT_MAX_CHARS,
    )


def kling_duration_preflight_metadata(plan: DurationPlan) -> dict[str, Any]:
    requested = plan.requested_duration_seconds or plan.duration_seconds
    return {
        "provider": KLING_PROVIDER_ID,
        "audio_strategy": KLING_AUDIO_STRATEGY,
        "requested_duration_seconds": requested,
        "planned_duration_seconds": plan.duration_seconds,
        "clip_count": plan.clip_count,
        "shot_mode": plan.shot_mode or MULTISHOT_STRATEGY,
        "shot_1_duration_seconds": plan.shot_1_duration_seconds or SHOT_1_DURATION_SECONDS,
        "shot_2_duration_seconds": plan.shot_2_duration_seconds or SHOT_2_DURATION_SECONDS,
        "clip_duration_seconds": CLIP_DURATION_SECONDS,
        "native_audio_required": plan.native_audio_required,
        "use_elevenlabs": plan.use_elevenlabs,
        "use_external_music": plan.use_external_music,
        "subtitle_required": plan.subtitle_required,
        "shot_prompt_max_chars": plan.shot_prompt_max_chars or KLING_SHOT_PROMPT_MAX_CHARS,
        "warnings": list(plan.warnings),
    }


def duration_plan_to_dict(plan: DurationPlan) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "duration_seconds": plan.duration_seconds,
        "clip_count": plan.clip_count,
        "provider": plan.provider,
        "clip_limit_seconds": plan.clip_limit_seconds,
        "warnings": list(plan.warnings),
    }
    if plan.kling_native_audio:
        payload.update(
            {
                "requested_duration_seconds": plan.requested_duration_seconds or plan.duration_seconds,
                "planned_duration_seconds": plan.duration_seconds,
                "kling_native_audio": True,
                "audio_strategy": plan.audio_strategy,
                "shot_mode": plan.shot_mode,
                "shot_1_duration_seconds": plan.shot_1_duration_seconds,
                "shot_2_duration_seconds": plan.shot_2_duration_seconds,
                "native_audio_required": plan.native_audio_required,
                "use_elevenlabs": plan.use_elevenlabs,
                "use_external_music": plan.use_external_music,
                "subtitle_required": plan.subtitle_required,
                "shot_prompt_max_chars": plan.shot_prompt_max_chars,
            }
        )
    return payload


def plan_duration(
    *,
    duration_seconds: int,
    provider: str = "runway",
    audio_strategy: str | None = None,
) -> DurationPlan:
    if is_kling_native_audio_route(provider=provider, audio_strategy=audio_strategy):
        return plan_kling_duration(duration_seconds=duration_seconds)

    ok, messages = validate_duration_seconds(duration_seconds)
    if not ok:
        raise ValueError(messages[0] if messages else "invalid duration")
    limit = provider_clip_limit(provider)
    clip_count = calculate_clip_count(duration_seconds=duration_seconds, provider=provider)
    return DurationPlan(
        duration_seconds=int(duration_seconds),
        clip_count=clip_count,
        provider=str(provider or "runway").lower(),
        clip_limit_seconds=limit,
        warnings=tuple(messages),
        requested_duration_seconds=int(duration_seconds),
    )
