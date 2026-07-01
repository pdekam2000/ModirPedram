"""Clip count authority — one requested count propagated through the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from content_brain.scheduling.duration_planner import calculate_clip_count

CLIP_COUNT_AUTHORITY_VERSION = "clip_count_authority_v1"
MAX_CLIP_COUNT = 6
MIN_CLIP_COUNT = 1


class ClipCountAuthorityError(ValueError):
    """Raised when a downstream stage invents a different clip count."""


@dataclass(frozen=True)
class ClipCountAuthority:
    requested_clip_count: int
    duration_seconds: int
    provider: str = "runway"
    source: str = "ui_override"

    @property
    def aligned_duration_seconds(self) -> int:
        clip_limit = 10
        return max(self.duration_seconds, self.requested_clip_count * clip_limit)


def resolve_requested_clip_count(payload: dict[str, Any], preflight: dict[str, Any]) -> int:
    """Resolve authoritative clip count from UI payload or duration preflight."""
    if payload.get("clip_count") not in (None, ""):
        return max(MIN_CLIP_COUNT, min(MAX_CLIP_COUNT, int(payload.get("clip_count"))))
    duration_plan = dict(preflight.get("duration_plan") or {})
    return max(
        MIN_CLIP_COUNT,
        min(MAX_CLIP_COUNT, int(duration_plan.get("clip_count") or 1)),
    )


def expected_clip_count_for_duration(duration_seconds: int, *, provider: str = "runway") -> int:
    """Scheduling authority: 40s @ 10s Runway clips = 4."""
    return calculate_clip_count(duration_seconds=int(duration_seconds), provider=provider)


def infer_format_planner_clip_count(
    *,
    duration_seconds: int,
    provider: str = "runway",
    clip_length_preference: int | None = 10,
) -> int:
    """Mirror Content Brain e2e duration step (video_format_planner) for pre-validation."""
    from content_brain.engines.video_format_planner import VideoFormatPlanner
    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import Platform

    planner = VideoFormatPlanner()
    profile = ProfileLoader().resolve(niche="general")
    plan = planner.plan(
        profile=profile,
        platform=Platform.YOUTUBE_SHORTS,
        user_duration_seconds=int(duration_seconds),
        provider_name=provider,
        provider_clip_duration_seconds=clip_length_preference,
    )
    return int(plan.clip_count)


def assert_clip_count_authority(
    *,
    requested: int,
    actual: int,
    stage: str,
) -> None:
    if int(requested) <= 0:
        return
    if int(actual) != int(requested):
        raise ClipCountAuthorityError(
            f"{stage}: clip_count mismatch ({actual} != {requested})"
        )


def validate_before_content_brain_planning(
    *,
    requested_clip_count: int,
    duration_seconds: int,
    provider: str = "runway",
) -> None:
    """Fail closed before planning if internal planner would invent a different count."""
    if requested_clip_count <= 0:
        return
    inferred = infer_format_planner_clip_count(
        duration_seconds=duration_seconds,
        provider=provider,
    )
    if inferred != requested_clip_count:
        raise ClipCountAuthorityError(
            "content_brain_format_planner: clip_count mismatch "
            f"({inferred} != {requested_clip_count}) for duration {duration_seconds}s"
        )


def apply_authoritative_clip_count(
    duration_plan: dict[str, Any],
    authority: ClipCountAuthority,
) -> dict[str, Any]:
    """Force duration plan payload to carry the requested clip count unchanged."""
    plan = dict(duration_plan or {})
    clip_duration = int(plan.get("clip_duration_seconds") or 10)
    plan["clip_count"] = int(authority.requested_clip_count)
    plan["requested_clip_count"] = int(authority.requested_clip_count)
    plan["duration_seconds"] = int(authority.duration_seconds)
    plan["target_duration_seconds"] = int(authority.requested_clip_count * clip_duration)
    plan["clip_count_authority_source"] = authority.source
    plan["clip_count_authority_version"] = CLIP_COUNT_AUTHORITY_VERSION
    return plan


def build_clip_count_authority(
    *,
    requested_clip_count: int,
    duration_seconds: int,
    provider: str = "runway",
    source: str = "ui_override",
) -> ClipCountAuthority:
    count = max(MIN_CLIP_COUNT, min(MAX_CLIP_COUNT, int(requested_clip_count)))
    return ClipCountAuthority(
        requested_clip_count=count,
        duration_seconds=max(MIN_CLIP_COUNT * 10, int(duration_seconds)),
        provider=str(provider or "runway"),
        source=source,
    )


__all__ = [
    "CLIP_COUNT_AUTHORITY_VERSION",
    "ClipCountAuthority",
    "ClipCountAuthorityError",
    "apply_authoritative_clip_count",
    "assert_clip_count_authority",
    "build_clip_count_authority",
    "expected_clip_count_for_duration",
    "infer_format_planner_clip_count",
    "resolve_requested_clip_count",
    "validate_before_content_brain_planning",
]
