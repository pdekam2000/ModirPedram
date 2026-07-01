"""Scheduling package."""

from content_brain.scheduling.duration_planner import (
    PRESET_DURATIONS,
    DurationPlan,
    calculate_clip_count,
    duration_plan_to_dict,
    is_kling_native_audio_route,
    kling_duration_preflight_metadata,
    plan_duration,
    validate_duration_seconds,
)
from content_brain.scheduling.schedule_models import ScheduledVideoJob, VideoSchedulePlan

__all__ = [
    "PRESET_DURATIONS",
    "DurationPlan",
    "ScheduledVideoJob",
    "VideoSchedulePlan",
    "calculate_clip_count",
    "duration_plan_to_dict",
    "is_kling_native_audio_route",
    "kling_duration_preflight_metadata",
    "plan_duration",
    "validate_duration_seconds",
]
