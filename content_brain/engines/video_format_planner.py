"""
Video Format / Duration Planner for the Viral Content Brain.

Decides target duration, clip structure, and pacing before story/retention generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Any, Optional

from content_brain.schemas.content_brief import Platform


class ContentType(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONGFORM = "longform"


class FormatType(str, Enum):
    SINGLE_SHORT = "single_short"
    MULTI_CLIP = "multi_clip"
    MULTI_CLIP_HAILUO = "multi_clip_hailuo"
    LONGFORM_RESERVED = "longform_reserved"


class PacingProfile(str, Enum):
    ULTRA_FAST = "ultra_fast"
    FAST = "fast"
    BALANCED = "balanced"
    SLOW_BURN = "slow_burn"


SUPPORTED_SHORT_DURATIONS = [15, 30, 45, 60]

STANDARD_STORY_BEATS = [
    "HOOK_BEAT",
    "CONTEXT_BEAT",
    "ESCALATION_BEAT",
    "PATTERN_BREAK",
    "PAYOFF_BEAT",
    "LOOP_SEED",
]

COMPACT_STORY_BEATS = [
    "HOOK_BEAT",
    "ESCALATION_BEAT",
    "PAYOFF_BEAT",
    "LOOP_SEED",
]

EXTENDED_STORY_BEATS = [
    "HOOK_BEAT",
    "CONTEXT_BEAT",
    "ESCALATION_BEAT",
    "PATTERN_BREAK",
    "PAYOFF_BEAT",
    "AFTERSHOCK",
    "LOOP_SEED",
]

PROVIDER_CLIP_LIMITS: dict[str, dict[str, Any]] = {
    "hailuo": {
        "default_clip_duration_seconds": 6,
        "allowed_clip_duration_seconds": [6, 8],
        "max_clip_duration_seconds": 8,
        "min_clip_duration_seconds": 6,
        "supports_multi_clip": True,
    },
    "hailuo_browser": {
        "default_clip_duration_seconds": 6,
        "allowed_clip_duration_seconds": [6, 8],
        "max_clip_duration_seconds": 8,
        "min_clip_duration_seconds": 6,
        "supports_multi_clip": True,
    },
    "runway": {
        "default_clip_duration_seconds": 10,
        "allowed_clip_duration_seconds": [10],
        "max_clip_duration_seconds": 10,
        "min_clip_duration_seconds": 10,
        "supports_multi_clip": True,
    },
    "runway_browser": {
        "default_clip_duration_seconds": 10,
        "allowed_clip_duration_seconds": [10],
        "max_clip_duration_seconds": 10,
        "min_clip_duration_seconds": 10,
        "supports_multi_clip": True,
    },
    "generic": {
        "default_clip_duration_seconds": 10,
        "allowed_clip_duration_seconds": [10],
        "max_clip_duration_seconds": 10,
        "min_clip_duration_seconds": 10,
        "supports_multi_clip": True,
    },
}


@dataclass
class RecommendedStoryBeat:
    beat_id: str
    start_second: float
    end_second: float
    act: int
    goal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "start_second": self.start_second,
            "end_second": self.end_second,
            "act": self.act,
            "goal": self.goal,
        }


@dataclass
class VideoFormatPlan:
    target_duration_seconds: int
    clip_count: int
    clip_duration_seconds: int
    format_type: FormatType
    pacing_profile: PacingProfile
    content_type: ContentType
    platform: Platform
    platform_limits: dict[str, Any]
    provider_name: str
    provider_limits: dict[str, Any]
    recommended_story_beats: list[RecommendedStoryBeat]
    selection_reason: str = ""
    user_duration_requested: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_duration_seconds": self.target_duration_seconds,
            "clip_count": self.clip_count,
            "clip_duration_seconds": self.clip_duration_seconds,
            "format_type": self.format_type.value,
            "pacing_profile": self.pacing_profile.value,
            "content_type": self.content_type.value,
            "platform": self.platform.value,
            "platform_limits": self.platform_limits,
            "provider_name": self.provider_name,
            "provider_limits": self.provider_limits,
            "recommended_story_beats": [
                beat.to_dict() for beat in self.recommended_story_beats
            ],
            "selection_reason": self.selection_reason,
            "user_duration_requested": self.user_duration_requested,
            "metadata": self.metadata,
        }


class VideoFormatPlanner:
    """
    Plan video duration and clip structure before story/retention engines run.

    Usage:
        planner = VideoFormatPlanner()
        plan = planner.plan(profile, platform=Platform.TIKTOK, user_duration_seconds=30)
    """

    CONTENT_TYPE_DEFAULTS = {
        ContentType.SHORT: 30,
        ContentType.MEDIUM: 45,
        ContentType.LONGFORM: 0,
    }

    PLATFORM_PREFERRED_DURATIONS = {
        Platform.TIKTOK: [30, 15, 45],
        Platform.YOUTUBE_SHORTS: [45, 60, 30],
        Platform.INSTAGRAM_REELS: [30, 15, 45],
    }

    def plan(
        self,
        profile: dict[str, Any],
        platform: Platform | str,
        content_type: ContentType | str = ContentType.SHORT,
        user_duration_seconds: Optional[int] = None,
        provider_name: Optional[str] = None,
        provider_clip_duration_seconds: Optional[int] = None,
    ) -> VideoFormatPlan:
        resolved_platform = platform if isinstance(platform, Platform) else Platform(str(platform))
        resolved_content_type = (
            content_type
            if isinstance(content_type, ContentType)
            else ContentType(str(content_type))
        )
        provider = self._resolve_provider_name(profile, provider_name)
        provider_limits = self._resolve_provider_limits(
            provider,
            profile,
            provider_clip_duration_seconds=provider_clip_duration_seconds,
        )
        platform_limits = self._resolve_platform_limits(profile, resolved_platform)

        if resolved_content_type == ContentType.LONGFORM:
            return self._build_longform_reserved_plan(
                profile=profile,
                platform=resolved_platform,
                platform_limits=platform_limits,
                provider_name=provider,
                provider_limits=provider_limits,
                user_duration_requested=user_duration_seconds,
            )

        target_duration = self._resolve_target_duration(
            profile=profile,
            platform=resolved_platform,
            content_type=resolved_content_type,
            user_duration_seconds=user_duration_seconds,
            platform_limits=platform_limits,
        )

        clip_duration = int(provider_limits["clip_duration_seconds"])
        clip_count, format_type, aligned_duration = self._resolve_clip_structure(
            target_duration=target_duration,
            clip_duration=clip_duration,
            provider_name=provider,
            provider_limits=provider_limits,
        )

        pacing_profile = self._resolve_pacing_profile(
            duration_seconds=aligned_duration,
            platform=resolved_platform,
            content_type=resolved_content_type,
        )
        story_beats = self._build_recommended_story_beats(
            duration_seconds=aligned_duration,
            pacing_profile=pacing_profile,
        )

        reason = self._build_selection_reason(
            user_duration_seconds=user_duration_seconds,
            requested_duration=target_duration,
            aligned_duration=aligned_duration,
            platform=resolved_platform,
            content_type=resolved_content_type,
            provider=provider,
            clip_count=clip_count,
            clip_duration=clip_duration,
        )

        return VideoFormatPlan(
            target_duration_seconds=aligned_duration,
            clip_count=clip_count,
            clip_duration_seconds=clip_duration,
            format_type=format_type,
            pacing_profile=pacing_profile,
            content_type=resolved_content_type,
            platform=resolved_platform,
            platform_limits=platform_limits,
            provider_name=provider,
            provider_limits=provider_limits,
            recommended_story_beats=story_beats,
            selection_reason=reason,
            user_duration_requested=user_duration_seconds,
            metadata={
                "supported_short_durations": SUPPORTED_SHORT_DURATIONS,
                "profile_default_duration": profile.get("content_format", {}).get(
                    "default_duration_seconds"
                ),
                "requested_duration_seconds": target_duration,
                "aligned_duration_seconds": aligned_duration,
                "provider_clip_duration_seconds": clip_duration,
            },
        )

    def _resolve_target_duration(
        self,
        profile: dict[str, Any],
        platform: Platform,
        content_type: ContentType,
        user_duration_seconds: Optional[int],
        platform_limits: dict[str, Any],
    ) -> int:
        content_format = profile.get("content_format", {})
        min_duration = int(content_format.get("min_duration_seconds", 15))
        max_duration = int(content_format.get("max_duration_seconds", 58))

        if user_duration_seconds is not None:
            duration = self._snap_duration(
                user_duration_seconds,
                min_duration=min_duration,
                max_duration=max_duration,
            )
            return duration

        ideal = platform_limits.get("ideal_duration_seconds", {})
        if isinstance(ideal, dict):
            sweet_spot = ideal.get("sweet_spot")
            if sweet_spot:
                return self._snap_duration(
                    int(sweet_spot),
                    min_duration=min_duration,
                    max_duration=max_duration,
                )

        preferred = self.PLATFORM_PREFERRED_DURATIONS.get(platform, [30])
        default_for_type = self.CONTENT_TYPE_DEFAULTS.get(content_type, 30)
        candidate = preferred[0] if default_for_type not in preferred else default_for_type

        profile_default = int(content_format.get("default_duration_seconds", candidate))
        return self._snap_duration(
            profile_default,
            min_duration=min_duration,
            max_duration=max_duration,
        )

    def _resolve_clip_structure(
        self,
        target_duration: int,
        clip_duration: int,
        provider_name: str,
        provider_limits: dict[str, Any],
    ) -> tuple[int, FormatType, int]:
        supports_multi = bool(provider_limits.get("supports_multi_clip", True))

        if not supports_multi or clip_duration <= 0:
            return 1, FormatType.SINGLE_SHORT, target_duration

        clip_count = max(1, ceil(target_duration / clip_duration))
        aligned_duration = clip_count * clip_duration

        if clip_count == 1:
            return clip_count, FormatType.SINGLE_SHORT, aligned_duration

        if "hailuo" in provider_name.lower():
            return clip_count, FormatType.MULTI_CLIP_HAILUO, aligned_duration

        return clip_count, FormatType.MULTI_CLIP, aligned_duration

    def _resolve_pacing_profile(
        self,
        duration_seconds: int,
        platform: Platform,
        content_type: ContentType,
    ) -> PacingProfile:
        if content_type == ContentType.MEDIUM or duration_seconds >= 45:
            return PacingProfile.BALANCED
        if duration_seconds <= 15:
            return PacingProfile.ULTRA_FAST
        if platform == Platform.TIKTOK:
            return PacingProfile.FAST
        if platform == Platform.YOUTUBE_SHORTS and duration_seconds >= 42:
            return PacingProfile.SLOW_BURN
        return PacingProfile.FAST

    def _build_recommended_story_beats(
        self,
        duration_seconds: int,
        pacing_profile: PacingProfile,
    ) -> list[RecommendedStoryBeat]:
        if duration_seconds <= 15:
            beat_ids = COMPACT_STORY_BEATS
        elif duration_seconds >= 60 or pacing_profile == PacingProfile.SLOW_BURN:
            beat_ids = EXTENDED_STORY_BEATS
        else:
            beat_ids = STANDARD_STORY_BEATS

        ratios = self._beat_ratios(beat_ids)
        beats: list[RecommendedStoryBeat] = []
        act_map = {
            "HOOK_BEAT": 1,
            "CONTEXT_BEAT": 1,
            "ESCALATION_BEAT": 2,
            "PATTERN_BREAK": 2,
            "PAYOFF_BEAT": 3,
            "AFTERSHOCK": 3,
            "LOOP_SEED": 3,
        }
        goals = {
            "HOOK_BEAT": "Pattern interrupt and immediate stakes",
            "CONTEXT_BEAT": "Establish context without over-explaining",
            "ESCALATION_BEAT": "Increase tension or value",
            "PATTERN_BREAK": "Shift angle before payoff",
            "PAYOFF_BEAT": "Deliver payoff that matches the hook",
            "AFTERSHOCK": "Emotional echo after the peak",
            "LOOP_SEED": "Open loop for comments or next episode",
        }

        for beat_id, (start_ratio, end_ratio) in zip(beat_ids, ratios):
            start = round(duration_seconds * start_ratio, 1)
            end = round(duration_seconds * end_ratio, 1)
            if end <= start:
                end = start + 0.5
            beats.append(
                RecommendedStoryBeat(
                    beat_id=beat_id,
                    start_second=start,
                    end_second=end,
                    act=act_map.get(beat_id, 2),
                    goal=goals.get(beat_id, "Retention beat"),
                )
            )

        return beats

    def _beat_ratios(self, beat_ids: list[str]) -> list[tuple[float, float]]:
        if len(beat_ids) == 4:
            return [
                (0.0, 0.15),
                (0.15, 0.45),
                (0.45, 0.82),
                (0.82, 1.0),
            ]
        if len(beat_ids) == 7:
            return [
                (0.0, 0.08),
                (0.08, 0.18),
                (0.18, 0.35),
                (0.35, 0.48),
                (0.48, 0.72),
                (0.72, 0.86),
                (0.86, 1.0),
            ]
        return [
            (0.0, 0.09),
            (0.09, 0.20),
            (0.20, 0.42),
            (0.42, 0.54),
            (0.54, 0.82),
            (0.82, 1.0),
        ]

    def _resolve_platform_limits(
        self,
        profile: dict[str, Any],
        platform: Platform,
    ) -> dict[str, Any]:
        rules = profile.get("platform_rules", {}).get(platform.value, {})
        content_format = profile.get("content_format", {})

        return {
            "platform_id": platform.value,
            "ideal_duration_seconds": rules.get("ideal_duration_seconds", {}),
            "hook_window_seconds": rules.get("hook_window_seconds"),
            "min_project_duration": content_format.get("min_duration_seconds", 15),
            "max_project_duration": content_format.get("max_duration_seconds", 58),
            "caption_style": rules.get("caption_style"),
            "pacing_note": rules.get("pacing_note"),
        }

    def _resolve_provider_name(
        self,
        profile: dict[str, Any],
        provider_name: Optional[str],
    ) -> str:
        if provider_name:
            return provider_name.strip().lower()

        metadata_provider = profile.get("metadata", {}).get("video_provider")
        if metadata_provider:
            return str(metadata_provider).lower()

        return "hailuo"

    def _resolve_provider_limits(
        self,
        provider_name: str,
        profile: dict[str, Any],
        provider_clip_duration_seconds: Optional[int] = None,
    ) -> dict[str, Any]:
        provider_key = provider_name.lower()
        base_limits = self._lookup_provider_defaults(provider_key, profile)
        allowed = list(base_limits.get("allowed_clip_duration_seconds", [10]))

        if provider_clip_duration_seconds is not None:
            clip_duration = int(provider_clip_duration_seconds)
            if clip_duration not in allowed:
                raise ValueError(
                    f"Provider '{provider_name}' does not support "
                    f"{clip_duration}s clips. Allowed: {allowed}."
                )
        else:
            clip_duration = int(base_limits.get("default_clip_duration_seconds", allowed[0]))

        resolved = dict(base_limits)
        resolved["clip_duration_seconds"] = clip_duration
        resolved["allowed_clip_duration_seconds"] = allowed
        return resolved

    def _lookup_provider_defaults(
        self,
        provider_key: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        if provider_key in PROVIDER_CLIP_LIMITS:
            return dict(PROVIDER_CLIP_LIMITS[provider_key])

        for key, limits in PROVIDER_CLIP_LIMITS.items():
            if key in provider_key:
                return dict(limits)

        content_format = profile.get("content_format", {})
        generic_duration = int(content_format.get("clip_duration_seconds", 10))
        return dict(PROVIDER_CLIP_LIMITS["generic"]) | {
            "default_clip_duration_seconds": generic_duration,
            "allowed_clip_duration_seconds": [generic_duration],
        }

    def _snap_duration(
        self,
        requested: int,
        min_duration: int,
        max_duration: int,
    ) -> int:
        clamped = max(min_duration, min(max_duration, int(requested)))

        if clamped in SUPPORTED_SHORT_DURATIONS:
            return clamped

        return min(
            SUPPORTED_SHORT_DURATIONS,
            key=lambda value: abs(value - clamped),
        )

    def _build_longform_reserved_plan(
        self,
        profile: dict[str, Any],
        platform: Platform,
        platform_limits: dict[str, Any],
        provider_name: str,
        provider_limits: dict[str, Any],
        user_duration_requested: Optional[int],
    ) -> VideoFormatPlan:
        del profile
        return VideoFormatPlan(
            target_duration_seconds=0,
            clip_count=0,
            clip_duration_seconds=int(provider_limits.get("clip_duration_seconds", 10)),
            format_type=FormatType.LONGFORM_RESERVED,
            pacing_profile=PacingProfile.SLOW_BURN,
            content_type=ContentType.LONGFORM,
            platform=platform,
            platform_limits=platform_limits,
            provider_name=provider_name,
            provider_limits=provider_limits,
            recommended_story_beats=[],
            selection_reason=(
                "Longform mode is reserved for a future pipeline stage and is not "
                "generated in V1."
            ),
            user_duration_requested=user_duration_requested,
            metadata={"implemented": False},
        )

    def _build_selection_reason(
        self,
        user_duration_seconds: Optional[int],
        requested_duration: int,
        aligned_duration: int,
        platform: Platform,
        content_type: ContentType,
        provider: str,
        clip_count: int,
        clip_duration: int,
    ) -> str:
        alignment_note = ""
        if aligned_duration != requested_duration:
            alignment_note = (
                f" Aligned from {requested_duration}s to {aligned_duration}s "
                f"using {clip_count}x{clip_duration}s clips."
            )

        if user_duration_seconds is not None:
            return (
                f"Used user-requested duration {user_duration_seconds}s for "
                f"{platform.value} ({content_type.value}) with {clip_count}x"
                f"{clip_duration}s clips via {provider}.{alignment_note}"
            )
        return (
            f"Auto-selected {requested_duration}s for {platform.value} "
            f"({content_type.value}) with {clip_count}x{clip_duration}s clips "
            f"via {provider}.{alignment_note}"
        )


__all__ = [
    "ContentType",
    "FormatType",
    "PacingProfile",
    "RecommendedStoryBeat",
    "SUPPORTED_SHORT_DURATIONS",
    "VideoFormatPlan",
    "VideoFormatPlanner",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    planner = VideoFormatPlanner()
    profile = loader.resolve(niche="general")

    provider_cases = [
        {
            "label": "30s Hailuo 6s",
            "provider": "hailuo",
            "clip_duration": 6,
            "duration": 30,
        },
        {
            "label": "30s Hailuo 8s",
            "provider": "hailuo",
            "clip_duration": 8,
            "duration": 30,
        },
        {
            "label": "60s Hailuo 6s",
            "provider": "hailuo",
            "clip_duration": 6,
            "duration": 60,
        },
        {
            "label": "60s Runway 10s",
            "provider": "runway",
            "clip_duration": 10,
            "duration": 60,
        },
    ]

    for case in provider_cases:
        plan = planner.plan(
            profile=profile,
            platform=Platform.TIKTOK,
            user_duration_seconds=case["duration"],
            provider_name=case["provider"],
            provider_clip_duration_seconds=case["clip_duration"],
        )
        print("\n" + "=" * 72)
        print(case["label"])
        print(
            f"RESULT: {plan.target_duration_seconds}s | "
            f"{plan.clip_count}x{plan.clip_duration_seconds}s | "
            f"{plan.format_type.value}"
        )
        print(f"REASON: {plan.selection_reason}")
