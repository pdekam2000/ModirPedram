"""Runway Runtime Bridge — prompt_package adapter for AI Content Factory (Phase 5A/5B)."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from content_brain.execution.kling_frame_to_video_models import (
    END_FRAME_GENERATED_TARGET,
    END_FRAME_NONE,
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_TO_VIDEO_MODE,
    KLING_FRAME_TO_VIDEO_PLAN_VERSION,
    KLING_MULTISHOT_MODE,
    KlingFrameToVideoClipPlan,
    KlingFrameToVideoPlan,
    validate_kling_frame_to_video_plan,
)
from content_brain.execution.kling_native_audio_models import (
    FIRST_FRAME_PRIOR_CLIP,
    FIRST_FRAME_PROMPT_ONLY,
    KLING_AUDIO_STRATEGY,
    KLING_PROVIDER_ID,
    NativeAudioDirectives,
)
from content_brain.execution.kling_starter_frame_generator import create_kling_frame_run_id

BRIDGE_ADAPTER_VERSION = "runway_runtime_bridge_adapter_v2"
DEFAULT_CLIP_DURATION_SECONDS = 10
KLING_CLIP_DURATION_SECONDS = 15
SUPPORTED_PROVIDER = "runway"
PROVIDER_KLING = "kling"
SUPPORTED_PROVIDERS = frozenset({SUPPORTED_PROVIDER, PROVIDER_KLING})
KLING_SUPPORTED_MODEL = "kling-3.0"
SUPPORTED_ASPECT_RATIO = "9:16"


class RunwayRuntimeBridgeValidationError(ValueError):
    """Invalid bridge request payload."""

    def __init__(self, message: str, *, code: str = "validation_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RunwayRuntimeGenerateContext:
    run_id: str
    project_id: str
    provider: str
    model: str
    story_idea: str
    aspect_ratio: str
    duration_seconds: int
    clip_count: int
    clip_duration_seconds: int
    e2e_result: dict[str, Any] | None = None
    kling_plan: KlingFrameToVideoPlan | None = None


def resolve_provider(provider: str) -> str:
    value = str(provider or SUPPORTED_PROVIDER).strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        raise RunwayRuntimeBridgeValidationError(
            f"provider must be one of {sorted(SUPPORTED_PROVIDERS)!r}",
            code="unsupported_provider",
        )
    return value


def validate_provider(provider: str) -> None:
    if resolve_provider(provider) != SUPPORTED_PROVIDER:
        raise RunwayRuntimeBridgeValidationError(
            f"provider must be {SUPPORTED_PROVIDER!r}",
            code="unsupported_provider",
        )


def validate_kling_model(model: str) -> str:
    value = str(model or "").strip().lower()
    if value != KLING_SUPPORTED_MODEL:
        raise RunwayRuntimeBridgeValidationError(
            f'model must be {KLING_SUPPORTED_MODEL!r} when provider is {PROVIDER_KLING!r}',
            code="unsupported_model",
        )
    return KLING_SUPPORTED_MODEL


def validate_aspect_ratio(aspect_ratio: str) -> str:
    value = str(aspect_ratio or "").strip()
    if value != SUPPORTED_ASPECT_RATIO:
        raise RunwayRuntimeBridgeValidationError(
            f"aspect_ratio must be {SUPPORTED_ASPECT_RATIO!r}",
            code="unsupported_aspect_ratio",
        )
    return value


def resolve_clip_count(*, duration_seconds: int, clip_duration_seconds: int = DEFAULT_CLIP_DURATION_SECONDS) -> int:
    duration = max(int(duration_seconds), int(clip_duration_seconds))
    step = max(int(clip_duration_seconds), 1)
    return max(1, math.ceil(duration / step))


def _sanitize_token(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return cleaned[:48] or "project"


def generate_run_id(project_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{_sanitize_token(project_id)}_{stamp}_{suffix}"


def _normalize_clip_prompts(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        raise RunwayRuntimeBridgeValidationError(
            "prompt_package.clip_prompts must be a list",
            code="invalid_clip_prompts",
        )
    prompts: list[str] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("video_prompt") or item.get("prompt") or "").strip()
        else:
            raise RunwayRuntimeBridgeValidationError(
                f"clip_prompts[{index - 1}] must be a string or object with video_prompt",
                code="invalid_clip_prompts",
            )
        if not text:
            raise RunwayRuntimeBridgeValidationError(
                f"clip_prompts[{index - 1}] must be non-empty",
                code="invalid_clip_prompts",
            )
        prompts.append(text)
    return prompts


def validate_kling_prompt_lengths(prompts: list[str]) -> None:
    for index, prompt in enumerate(prompts):
        length = len(prompt)
        if length > KLING_FRAME_PROMPT_MAX_CHARS:
            raise RunwayRuntimeBridgeValidationError(
                f"clip_prompts[{index}] length ({length}) exceeds "
                f"{KLING_FRAME_PROMPT_MAX_CHARS} characters",
                code="prompt_too_long",
            )


def normalize_prompt_package(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RunwayRuntimeBridgeValidationError(
            "prompt_package must be an object",
            code="invalid_prompt_package",
        )
    story_idea = str(raw.get("story_idea") or "").strip()
    if not story_idea:
        raise RunwayRuntimeBridgeValidationError(
            "prompt_package.story_idea is required",
            code="missing_story_idea",
        )
    starter_image_prompt = str(raw.get("starter_image_prompt") or "").strip()
    if not starter_image_prompt:
        raise RunwayRuntimeBridgeValidationError(
            "prompt_package.starter_image_prompt is required",
            code="missing_starter_image_prompt",
        )
    clip_duration_seconds = int(raw.get("clip_duration_seconds") or DEFAULT_CLIP_DURATION_SECONDS)
    if clip_duration_seconds < 1:
        raise RunwayRuntimeBridgeValidationError(
            "prompt_package.clip_duration_seconds must be >= 1",
            code="invalid_clip_duration_seconds",
        )
    clip_prompts = _normalize_clip_prompts(raw.get("clip_prompts"))
    anchors = raw.get("continuity_anchors")
    continuity_anchors = dict(anchors) if isinstance(anchors, dict) else {}
    optional_run_id = str(raw.get("run_id") or "").strip()
    return {
        "story_idea": story_idea,
        "starter_image_prompt": starter_image_prompt,
        "clip_prompts": clip_prompts,
        "continuity_anchors": continuity_anchors,
        "clip_duration_seconds": clip_duration_seconds,
        "run_id": optional_run_id,
    }


def prompt_package_to_e2e_result(
    prompt_package: dict[str, Any],
    *,
    run_id: str,
    story_idea: str,
) -> dict[str, Any]:
    clip_prompts = [
        {"clip_index": index, "video_prompt": prompt}
        for index, prompt in enumerate(prompt_package["clip_prompts"], start=1)
    ]
    return {
        "run_id": run_id,
        "input": {"topic": story_idea},
        "steps": [
            {
                "step_key": "prompt_cleanup",
                "starter_image_prompt": prompt_package["starter_image_prompt"],
                "clip_prompts": clip_prompts,
                "continuity_anchors": dict(prompt_package.get("continuity_anchors") or {}),
                "cleanup_applied": True,
                "prompt_noise_score": 0.0,
                "prompt_efficiency_score": 1.0,
            }
        ],
    }


def prompt_package_to_kling_frame_plan(
    prompt_package: dict[str, Any],
    *,
    duration_seconds: int,
    clip_count: int,
) -> KlingFrameToVideoPlan:
    story_idea = prompt_package["story_idea"]
    clip_prompts = prompt_package["clip_prompts"]
    planned_duration_seconds = clip_count * KLING_CLIP_DURATION_SECONDS
    empty_directives = NativeAudioDirectives()
    clips: list[KlingFrameToVideoClipPlan] = []

    for index, prompt in enumerate(clip_prompts, start=1):
        is_first = index <= 1
        is_last = index >= clip_count
        clips.append(
            KlingFrameToVideoClipPlan(
                clip_index=index,
                duration_seconds=KLING_CLIP_DURATION_SECONDS,
                first_frame_source=FIRST_FRAME_PROMPT_ONLY if is_first else FIRST_FRAME_PRIOR_CLIP,
                end_frame_source=END_FRAME_NONE if is_last else END_FRAME_GENERATED_TARGET,
                first_frame_path="" if is_first else "",
                prompt=prompt,
                character_continuity="",
                environment_continuity="",
                dialogue="",
                native_audio_directives=empty_directives,
                camera_direction="",
                continuity_anchor="",
                next_clip_reference_hint="",
                prior_clip_index=None if is_first else index - 1,
            )
        )

    plan = KlingFrameToVideoPlan(
        version=KLING_FRAME_TO_VIDEO_PLAN_VERSION,
        provider_mode=KLING_FRAME_TO_VIDEO_MODE,
        provider=KLING_PROVIDER_ID,
        audio_strategy=KLING_AUDIO_STRATEGY,
        generation_mode=KLING_FRAME_TO_VIDEO_MODE,
        fallback_mode=KLING_MULTISHOT_MODE,
        requested_duration_seconds=int(duration_seconds),
        planned_duration_seconds=planned_duration_seconds,
        clip_count=clip_count,
        clips=clips,
        topic=story_idea,
        native_audio_required=True,
        prompt_max_chars=KLING_FRAME_PROMPT_MAX_CHARS,
    )
    ok, errors = validate_kling_frame_to_video_plan(plan)
    if not ok:
        raise RunwayRuntimeBridgeValidationError(
            "; ".join(errors[:8]),
            code="validation_error",
        )
    return plan


def _build_runway_generate_context(
    *,
    project: str,
    normalized: dict[str, Any],
    resolved_aspect: str,
    duration_seconds: int,
) -> RunwayRuntimeGenerateContext:
    clip_duration_seconds = int(normalized["clip_duration_seconds"])
    clip_count = resolve_clip_count(
        duration_seconds=int(duration_seconds),
        clip_duration_seconds=clip_duration_seconds,
    )
    if len(normalized["clip_prompts"]) != clip_count:
        raise RunwayRuntimeBridgeValidationError(
            f"clip_prompts length ({len(normalized['clip_prompts'])}) must match "
            f"computed clip_count ({clip_count}) for duration_seconds={duration_seconds} "
            f"and clip_duration_seconds={clip_duration_seconds}",
            code="clip_prompt_count_mismatch",
        )

    story_idea = normalized["story_idea"]
    run_id = normalized["run_id"] or generate_run_id(project)
    e2e_result = prompt_package_to_e2e_result(normalized, run_id=run_id, story_idea=story_idea)
    return RunwayRuntimeGenerateContext(
        run_id=run_id,
        project_id=project,
        provider=SUPPORTED_PROVIDER,
        model="",
        story_idea=story_idea,
        aspect_ratio=resolved_aspect,
        duration_seconds=int(duration_seconds),
        clip_count=clip_count,
        clip_duration_seconds=clip_duration_seconds,
        e2e_result=e2e_result,
        kling_plan=None,
    )


def _build_kling_generate_context(
    *,
    project: str,
    model: str,
    normalized: dict[str, Any],
    resolved_aspect: str,
    duration_seconds: int,
) -> RunwayRuntimeGenerateContext:
    resolved_model = validate_kling_model(model)
    validate_kling_prompt_lengths(normalized["clip_prompts"])
    clip_duration_seconds = KLING_CLIP_DURATION_SECONDS
    clip_count = resolve_clip_count(
        duration_seconds=int(duration_seconds),
        clip_duration_seconds=clip_duration_seconds,
    )
    if len(normalized["clip_prompts"]) != clip_count:
        raise RunwayRuntimeBridgeValidationError(
            f"clip_prompts length ({len(normalized['clip_prompts'])}) must match "
            f"computed clip_count ({clip_count}) for duration_seconds={duration_seconds} "
            f"and clip_duration_seconds={clip_duration_seconds}",
            code="clip_prompt_count_mismatch",
        )

    story_idea = normalized["story_idea"]
    run_id = normalized["run_id"] or create_kling_frame_run_id()
    kling_plan = prompt_package_to_kling_frame_plan(
        normalized,
        duration_seconds=int(duration_seconds),
        clip_count=clip_count,
    )
    return RunwayRuntimeGenerateContext(
        run_id=run_id,
        project_id=project,
        provider=PROVIDER_KLING,
        model=resolved_model,
        story_idea=story_idea,
        aspect_ratio=resolved_aspect,
        duration_seconds=int(duration_seconds),
        clip_count=clip_count,
        clip_duration_seconds=clip_duration_seconds,
        e2e_result=None,
        kling_plan=kling_plan,
    )


def build_generate_context(
    *,
    project_id: str,
    provider: str,
    model: str = "",
    aspect_ratio: str,
    duration_seconds: int,
    prompt_package: dict[str, Any],
) -> RunwayRuntimeGenerateContext:
    project = str(project_id or "").strip()
    if not project:
        raise RunwayRuntimeBridgeValidationError("project_id is required", code="missing_project_id")

    resolved_provider = resolve_provider(provider)
    resolved_aspect = validate_aspect_ratio(aspect_ratio)
    normalized = normalize_prompt_package(prompt_package)

    if resolved_provider == SUPPORTED_PROVIDER:
        return _build_runway_generate_context(
            project=project,
            normalized=normalized,
            resolved_aspect=resolved_aspect,
            duration_seconds=int(duration_seconds),
        )

    return _build_kling_generate_context(
        project=project,
        model=model,
        normalized=normalized,
        resolved_aspect=resolved_aspect,
        duration_seconds=int(duration_seconds),
    )


__all__ = [
    "BRIDGE_ADAPTER_VERSION",
    "DEFAULT_CLIP_DURATION_SECONDS",
    "KLING_CLIP_DURATION_SECONDS",
    "KLING_SUPPORTED_MODEL",
    "PROVIDER_KLING",
    "RunwayRuntimeBridgeValidationError",
    "RunwayRuntimeGenerateContext",
    "SUPPORTED_PROVIDERS",
    "build_generate_context",
    "generate_run_id",
    "normalize_prompt_package",
    "prompt_package_to_e2e_result",
    "prompt_package_to_kling_frame_plan",
    "resolve_clip_count",
    "resolve_provider",
    "validate_aspect_ratio",
    "validate_kling_model",
    "validate_kling_prompt_lengths",
    "validate_provider",
]
