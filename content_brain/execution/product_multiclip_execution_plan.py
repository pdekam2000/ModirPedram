"""Product Studio — centralized duration planner and multi-clip execution plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PRODUCT_CLIP_SECONDS = 15
PRODUCT_DURATION_PRESETS: dict[int, int] = {
    15: 1,
    30: 2,
    40: 3,
    60: 4,
}
EXECUTION_MODE_SINGLE = "single_clip"
EXECUTION_MODE_USE_FRAME = "use_frame_chain"


@dataclass(frozen=True)
class MultiClipExecutionPlan:
    duration_seconds: int
    clip_count: int
    prompts: tuple[str, ...]
    provider: str
    aspect_ratio: str
    native_audio: bool
    execution_mode: str
    use_frame_enabled: bool
    requested_duration_seconds: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["prompts"] = list(self.prompts)
        payload["warnings"] = list(self.warnings)
        return payload


def calculate_product_clip_count(duration_seconds: int) -> int:
    """Clip count for custom durations — ceil(duration / 15), minimum 1."""
    requested = max(1, int(duration_seconds))
    if requested in PRODUCT_DURATION_PRESETS:
        return PRODUCT_DURATION_PRESETS[requested]
    return max(1, (requested + PRODUCT_CLIP_SECONDS - 1) // PRODUCT_CLIP_SECONDS)


def execution_mode_for_clip_count(clip_count: int) -> str:
    return EXECUTION_MODE_SINGLE if int(clip_count) <= 1 else EXECUTION_MODE_USE_FRAME


def plan_product_duration(duration_seconds: int) -> dict[str, Any]:
    """Centralized Product Studio duration planner."""
    requested = max(1, int(duration_seconds))
    clip_count = calculate_product_clip_count(requested)
    warnings: list[str] = []
    if requested not in PRODUCT_DURATION_PRESETS:
        warnings.append(
            f"custom_duration_seconds={requested} mapped to clip_count={clip_count}"
        )
    execution_mode = execution_mode_for_clip_count(clip_count)
    return {
        "duration_seconds": requested,
        "clip_count": clip_count,
        "execution_mode": execution_mode,
        "requested_duration_seconds": requested,
        "clip_duration_seconds": PRODUCT_CLIP_SECONDS,
        "use_frame_enabled": execution_mode == EXECUTION_MODE_USE_FRAME,
        "warnings": warnings,
    }


def extract_prompts_from_preflight_snapshot(preflight: dict[str, Any]) -> list[str]:
    frame_plan = preflight.get("kling_frame_to_video_plan") or preflight.get("kling_frame_plan") or {}
    clips = frame_plan.get("clips") if isinstance(frame_plan, dict) else None
    prompts: list[str] = []
    if isinstance(clips, list):
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            text = str(clip.get("prompt") or "").strip()
            if text:
                prompts.append(text)
    if not prompts:
        for item in preflight.get("kling_clip_prompts") or []:
            if isinstance(item, dict) and str(item.get("prompt") or "").strip():
                prompts.append(str(item["prompt"]).strip())
    if not prompts:
        topic = str(preflight.get("authoritative_topic") or "").strip()
        if topic:
            prompts = [topic]
    return prompts


def build_multiclip_execution_plan(
    preflight: dict[str, Any],
    *,
    native_audio: bool = True,
    duration_seconds: int | None = None,
) -> MultiClipExecutionPlan:
    requested = int(
        duration_seconds
        or (preflight.get("multiclip_execution_plan") or {}).get("duration_seconds")
        or (preflight.get("duration_plan") or {}).get("duration_seconds")
        or (preflight.get("duration_plan") or {}).get("requested_duration_seconds")
        or 30
    )
    product_plan = plan_product_duration(requested)
    clip_count = int(product_plan["clip_count"])
    prompts = extract_prompts_from_preflight_snapshot(preflight)
    if not prompts:
        raise ValueError("No prompts available from preflight or topic.")
    if len(prompts) < clip_count:
        seed = prompts[-1]
        while len(prompts) < clip_count:
            prompts.append(seed)
    elif len(prompts) > clip_count:
        prompts = prompts[:clip_count]
    provider = str(preflight.get("provider") or "kling_3_0_pro_native_audio")
    aspect_ratio = str(preflight.get("aspect_ratio") or "9:16")
    execution_mode = str(product_plan["execution_mode"])
    return MultiClipExecutionPlan(
        duration_seconds=int(product_plan["duration_seconds"]),
        clip_count=clip_count,
        prompts=tuple(prompts),
        provider=provider,
        aspect_ratio=aspect_ratio,
        native_audio=bool(native_audio),
        execution_mode=execution_mode,
        use_frame_enabled=execution_mode == EXECUTION_MODE_USE_FRAME,
        requested_duration_seconds=requested,
        warnings=tuple(product_plan.get("warnings") or ()),
    )


def apply_product_duration_to_preflight_dict(
    preflight: dict[str, Any],
    *,
    duration_seconds: int,
    native_audio: bool = True,
) -> dict[str, Any]:
    """Attach product duration plan and multiclip execution plan to a preflight payload."""
    product_plan = plan_product_duration(duration_seconds)
    updated = dict(preflight)
    duration_plan = dict(updated.get("duration_plan") or {})
    duration_plan["duration_seconds"] = product_plan["duration_seconds"]
    duration_plan["clip_count"] = product_plan["clip_count"]
    duration_plan["execution_mode"] = product_plan["execution_mode"]
    duration_plan["requested_duration_seconds"] = product_plan["requested_duration_seconds"]
    duration_plan["clip_duration_seconds"] = PRODUCT_CLIP_SECONDS
    duration_plan["use_frame_enabled"] = product_plan["use_frame_enabled"]
    updated["duration_plan"] = duration_plan

    kling_duration_plan = dict(updated.get("kling_duration_plan") or {})
    kling_duration_plan["clip_count"] = product_plan["clip_count"]
    kling_duration_plan["planned_duration_seconds"] = product_plan["duration_seconds"]
    kling_duration_plan["requested_duration_seconds"] = product_plan["requested_duration_seconds"]
    updated["kling_duration_plan"] = kling_duration_plan
    updated["kling_clip_count"] = product_plan["clip_count"]

    multiclip = build_multiclip_execution_plan(updated, native_audio=native_audio, duration_seconds=duration_seconds)
    updated["multiclip_execution_plan"] = multiclip.to_dict()
    updated["clip_execution_mode"] = multiclip.execution_mode
    return updated


def build_generation_runtime_status(
    *,
    clip_count: int,
    completed_clips: int,
    generation_state: str,
    clip_details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    planned = max(1, int(clip_count))
    completed = max(0, min(int(completed_clips), planned))
    current = completed if generation_state == "merge_complete" else min(completed + 1, planned)
    statuses: list[dict[str, Any]] = []
    details = clip_details or []
    for index in range(1, planned + 1):
        detail = next((item for item in details if int(item.get("clip") or 0) == index), {})
        if index <= completed:
            state = "completed"
            label = f"Clip {index}/{planned}"
        elif index == current and generation_state == "generating":
            state = "generating"
            label = f"Clip {index}/{planned}"
        else:
            state = "pending"
            label = f"Clip {index}/{planned}"
        statuses.append(
            {
                "clip": index,
                "status": state,
                "label": label,
                "used_frame_from_previous": bool(detail.get("used_frame_from_previous")),
            }
        )
    return {
        "planned_clip_count": planned,
        "current_clip": current,
        "completed_clips": completed,
        "generation_state": generation_state,
        "clip_statuses": statuses,
    }


__all__ = [
    "EXECUTION_MODE_SINGLE",
    "EXECUTION_MODE_USE_FRAME",
    "MultiClipExecutionPlan",
    "PRODUCT_CLIP_SECONDS",
    "PRODUCT_DURATION_PRESETS",
    "apply_product_duration_to_preflight_dict",
    "build_generation_runtime_status",
    "build_multiclip_execution_plan",
    "calculate_product_clip_count",
    "execution_mode_for_clip_count",
    "extract_prompts_from_preflight_snapshot",
    "plan_product_duration",
]
