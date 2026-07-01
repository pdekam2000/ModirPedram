"""Kling Native Audio — schema models and duration planning (P0 foundation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.kling_multishot_config import (
    CLIP_DURATION_SECONDS,
    MULTISHOT_STRATEGY,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)

KLING_NATIVE_AUDIO_PLAN_VERSION = "kling_native_audio_plan_v1"
KLING_CONTINUITY_CHAIN_VERSION = "kling_continuity_chain_v1"

KLING_PROVIDER_ID = "kling_3_0_pro_native_audio"
KLING_AUDIO_STRATEGY = "kling_native_audio"
KLING_SHOT_PROMPT_MAX_CHARS = 512

SUPPORTED_KLING_DURATIONS: tuple[int, ...] = (15, 30, 45, 60)
KLING_DURATION_STEP_SECONDS = 15

SHOT_ROLE_MAIN_ACTION = "main_action"
SHOT_ROLE_TRANSITION_BRIDGE = "transition_bridge"

FIRST_FRAME_USER_UPLOAD = "user_upload"
FIRST_FRAME_PROMPT_ONLY = "prompt_only"
FIRST_FRAME_PRIOR_CLIP = "prior_clip_shot2_final_frame"

HANDOFF_STATUS_PENDING = "pending"


@dataclass
class NativeAudioDirectives:
    dialogue_lines: list[str] = field(default_factory=list)
    ambience: list[str] = field(default_factory=list)
    foley: list[str] = field(default_factory=list)
    voice_acting: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dialogue_lines": list(self.dialogue_lines),
            "ambience": list(self.ambience),
            "foley": list(self.foley),
            "voice_acting": self.voice_acting,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> NativeAudioDirectives:
        data = dict(payload or {})
        return cls(
            dialogue_lines=[str(x) for x in list(data.get("dialogue_lines") or [])],
            ambience=[str(x) for x in list(data.get("ambience") or [])],
            foley=[str(x) for x in list(data.get("foley") or [])],
            voice_acting=str(data.get("voice_acting") or ""),
        )


@dataclass
class KlingShotPlan:
    shot_index: int
    duration_seconds: int
    role: str
    prompt: str
    native_audio_directives: NativeAudioDirectives = field(default_factory=NativeAudioDirectives)
    continuity_anchor: str = ""
    emotion: str = ""
    environment: str = ""
    characters_present: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        directives = self.native_audio_directives
        if isinstance(directives, dict):
            directives = NativeAudioDirectives.from_dict(directives)
        return {
            "shot_index": self.shot_index,
            "duration_seconds": self.duration_seconds,
            "role": self.role,
            "prompt": self.prompt,
            "native_audio_directives": directives.to_dict(),
            "continuity_anchor": self.continuity_anchor,
            "emotion": self.emotion,
            "environment": self.environment,
            "characters_present": list(self.characters_present),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingShotPlan:
        return cls(
            shot_index=int(payload.get("shot_index") or 0),
            duration_seconds=int(payload.get("duration_seconds") or 0),
            role=str(payload.get("role") or ""),
            prompt=str(payload.get("prompt") or ""),
            native_audio_directives=NativeAudioDirectives.from_dict(
                payload.get("native_audio_directives")  # type: ignore[arg-type]
            ),
            continuity_anchor=str(payload.get("continuity_anchor") or ""),
            emotion=str(payload.get("emotion") or ""),
            environment=str(payload.get("environment") or ""),
            characters_present=[str(x) for x in list(payload.get("characters_present") or [])],
        )


@dataclass
class KlingClipPlan:
    clip_index: int
    shot_1: KlingShotPlan
    shot_2: KlingShotPlan
    first_frame_source: str
    prior_clip_index: int | None
    prior_clip_reference: str
    next_clip_reference_hint: str
    continuity_bridge: str
    expected_native_audio: str
    clip_duration_seconds: int = CLIP_DURATION_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "clip_duration_seconds": self.clip_duration_seconds,
            "shot_1": self.shot_1.to_dict(),
            "shot_2": self.shot_2.to_dict(),
            "first_frame_source": self.first_frame_source,
            "prior_clip_index": self.prior_clip_index,
            "prior_clip_reference": self.prior_clip_reference,
            "next_clip_reference_hint": self.next_clip_reference_hint,
            "continuity_bridge": self.continuity_bridge,
            "expected_native_audio": self.expected_native_audio,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingClipPlan:
        return cls(
            clip_index=int(payload.get("clip_index") or 0),
            clip_duration_seconds=int(payload.get("clip_duration_seconds") or CLIP_DURATION_SECONDS),
            shot_1=KlingShotPlan.from_dict(dict(payload.get("shot_1") or {})),
            shot_2=KlingShotPlan.from_dict(dict(payload.get("shot_2") or {})),
            first_frame_source=str(payload.get("first_frame_source") or ""),
            prior_clip_index=(
                int(payload["prior_clip_index"])
                if payload.get("prior_clip_index") is not None
                else None
            ),
            prior_clip_reference=str(payload.get("prior_clip_reference") or ""),
            next_clip_reference_hint=str(payload.get("next_clip_reference_hint") or ""),
            continuity_bridge=str(payload.get("continuity_bridge") or ""),
            expected_native_audio=str(payload.get("expected_native_audio") or ""),
        )


@dataclass
class KlingNativeAudioPlan:
    requested_duration_seconds: int
    planned_duration_seconds: int
    clip_count: int
    clips: list[KlingClipPlan]
    topic: str = ""
    platform: str = ""
    version: str = KLING_NATIVE_AUDIO_PLAN_VERSION
    provider: str = KLING_PROVIDER_ID
    strategy: str = MULTISHOT_STRATEGY
    audio_strategy: str = KLING_AUDIO_STRATEGY
    native_audio_required: bool = True
    use_elevenlabs: bool = False
    use_external_music: bool = False
    subtitle_required: bool = True
    duration_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "provider": self.provider,
            "strategy": self.strategy,
            "requested_duration_seconds": self.requested_duration_seconds,
            "planned_duration_seconds": self.planned_duration_seconds,
            "clip_count": self.clip_count,
            "clips": [clip.to_dict() for clip in self.clips],
            "topic": self.topic,
            "platform": self.platform,
            "audio_strategy": self.audio_strategy,
            "native_audio_required": self.native_audio_required,
            "use_elevenlabs": self.use_elevenlabs,
            "use_external_music": self.use_external_music,
            "subtitle_required": self.subtitle_required,
            "duration_warnings": list(self.duration_warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingNativeAudioPlan:
        return cls(
            version=str(payload.get("version") or KLING_NATIVE_AUDIO_PLAN_VERSION),
            provider=str(payload.get("provider") or KLING_PROVIDER_ID),
            strategy=str(payload.get("strategy") or MULTISHOT_STRATEGY),
            requested_duration_seconds=int(payload.get("requested_duration_seconds") or 0),
            planned_duration_seconds=int(payload.get("planned_duration_seconds") or 0),
            clip_count=int(payload.get("clip_count") or 0),
            clips=[KlingClipPlan.from_dict(dict(item)) for item in list(payload.get("clips") or [])],
            topic=str(payload.get("topic") or ""),
            platform=str(payload.get("platform") or ""),
            audio_strategy=str(payload.get("audio_strategy") or KLING_AUDIO_STRATEGY),
            native_audio_required=bool(payload.get("native_audio_required", True)),
            use_elevenlabs=bool(payload.get("use_elevenlabs", False)),
            use_external_music=bool(payload.get("use_external_music", False)),
            subtitle_required=bool(payload.get("subtitle_required", True)),
            duration_warnings=tuple(str(w) for w in list(payload.get("duration_warnings") or [])),
        )


@dataclass
class KlingContinuityLink:
    from_clip_index: int
    to_clip_index: int
    frame_source_path: str = ""
    handoff_status: str = HANDOFF_STATUS_PENDING
    continuity_anchor: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_clip_index": self.from_clip_index,
            "to_clip_index": self.to_clip_index,
            "frame_source_path": self.frame_source_path,
            "handoff_status": self.handoff_status,
            "continuity_anchor": self.continuity_anchor,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingContinuityLink:
        return cls(
            from_clip_index=int(payload.get("from_clip_index") or 0),
            to_clip_index=int(payload.get("to_clip_index") or 0),
            frame_source_path=str(payload.get("frame_source_path") or ""),
            handoff_status=str(payload.get("handoff_status") or HANDOFF_STATUS_PENDING),
            continuity_anchor=str(payload.get("continuity_anchor") or ""),
        )


@dataclass
class KlingFrameSource:
    clip_index: int
    source: str
    prior_clip_index: int | None = None
    asset_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "source": self.source,
            "prior_clip_index": self.prior_clip_index,
            "asset_path": self.asset_path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingFrameSource:
        return cls(
            clip_index=int(payload.get("clip_index") or 0),
            source=str(payload.get("source") or ""),
            prior_clip_index=(
                int(payload["prior_clip_index"])
                if payload.get("prior_clip_index") is not None
                else None
            ),
            asset_path=str(payload.get("asset_path") or ""),
        )


@dataclass
class KlingContinuityChain:
    run_id: str
    clip_count: int
    links: list[KlingContinuityLink] = field(default_factory=list)
    frame_sources: list[KlingFrameSource] = field(default_factory=list)
    continuity_notes: list[str] = field(default_factory=list)
    version: str = KLING_CONTINUITY_CHAIN_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "clip_count": self.clip_count,
            "links": [link.to_dict() for link in self.links],
            "frame_sources": [source.to_dict() for source in self.frame_sources],
            "continuity_notes": list(self.continuity_notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KlingContinuityChain:
        return cls(
            version=str(payload.get("version") or KLING_CONTINUITY_CHAIN_VERSION),
            run_id=str(payload.get("run_id") or ""),
            clip_count=int(payload.get("clip_count") or 0),
            links=[KlingContinuityLink.from_dict(dict(item)) for item in list(payload.get("links") or [])],
            frame_sources=[
                KlingFrameSource.from_dict(dict(item)) for item in list(payload.get("frame_sources") or [])
            ],
            continuity_notes=[str(x) for x in list(payload.get("continuity_notes") or [])],
        )


def normalize_kling_duration(requested_duration_seconds: int) -> tuple[int, int, tuple[str, ...]]:
    """Map requested duration to planned Kling duration and clip count.

    Supported exact tiers: 15, 30, 45, 60.
    Unsupported values round **up** to the nearest 15s tier (minimum 15).
    """
    requested = max(1, int(requested_duration_seconds))
    warnings: list[str] = []

    if requested in SUPPORTED_KLING_DURATIONS:
        planned = requested
    else:
        planned = ((requested + KLING_DURATION_STEP_SECONDS - 1) // KLING_DURATION_STEP_SECONDS) * KLING_DURATION_STEP_SECONDS
        planned = max(KLING_DURATION_STEP_SECONDS, planned)
        if planned > 60:
            planned = 60
            warnings.append(f"requested_duration_seconds={requested} capped at 60s maximum pack")
        if planned != requested:
            warnings.append(
                f"requested_duration_seconds={requested} rounded up to planned_duration_seconds={planned}"
            )

    clip_count = planned // KLING_DURATION_STEP_SECONDS
    return planned, clip_count, tuple(warnings)


def kling_clip_count_for_duration(duration_seconds: int) -> int:
    planned, clip_count, _ = normalize_kling_duration(duration_seconds)
    if planned != duration_seconds and duration_seconds not in SUPPORTED_KLING_DURATIONS:
        pass
    return clip_count


def default_shot_plans(*, clip_index: int) -> tuple[KlingShotPlan, KlingShotPlan]:
    shot_1 = KlingShotPlan(
        shot_index=1,
        duration_seconds=SHOT_1_DURATION_SECONDS,
        role=SHOT_ROLE_MAIN_ACTION,
        prompt="",
        native_audio_directives=NativeAudioDirectives(),
    )
    shot_2 = KlingShotPlan(
        shot_index=2,
        duration_seconds=SHOT_2_DURATION_SECONDS,
        role=SHOT_ROLE_TRANSITION_BRIDGE,
        prompt="",
        native_audio_directives=NativeAudioDirectives(),
        continuity_anchor="",
    )
    return shot_1, shot_2


def build_clip_plan_skeleton(*, clip_index: int, total_clips: int) -> KlingClipPlan:
    shot_1, shot_2 = default_shot_plans(clip_index=clip_index)
    is_first = clip_index <= 1
    is_last = clip_index >= total_clips
    return KlingClipPlan(
        clip_index=clip_index,
        clip_duration_seconds=CLIP_DURATION_SECONDS,
        shot_1=shot_1,
        shot_2=shot_2,
        first_frame_source=FIRST_FRAME_USER_UPLOAD if is_first else FIRST_FRAME_PRIOR_CLIP,
        prior_clip_index=None if is_first else clip_index - 1,
        prior_clip_reference="" if is_first else "",
        next_clip_reference_hint="" if is_last else "",
        continuity_bridge=shot_2.role,
        expected_native_audio="dialogue, ambience, foley, breathing — native in-video audio",
    )


def build_kling_native_audio_plan(
    *,
    requested_duration_seconds: int,
    topic: str = "",
    platform: str = "",
) -> KlingNativeAudioPlan:
    planned, clip_count, warnings = normalize_kling_duration(requested_duration_seconds)
    clips = [build_clip_plan_skeleton(clip_index=index, total_clips=clip_count) for index in range(1, clip_count + 1)]
    return KlingNativeAudioPlan(
        requested_duration_seconds=int(requested_duration_seconds),
        planned_duration_seconds=planned,
        clip_count=clip_count,
        clips=clips,
        topic=str(topic or ""),
        platform=str(platform or ""),
        duration_warnings=warnings,
    )


def build_continuity_chain_from_plan(plan: KlingNativeAudioPlan, *, run_id: str) -> KlingContinuityChain:
    frame_sources: list[KlingFrameSource] = []
    links: list[KlingContinuityLink] = []
    notes: list[str] = []

    for clip in plan.clips:
        frame_sources.append(
            KlingFrameSource(
                clip_index=clip.clip_index,
                source=clip.first_frame_source,
                prior_clip_index=clip.prior_clip_index,
            )
        )

    for index in range(len(plan.clips) - 1):
        current = plan.clips[index]
        nxt = plan.clips[index + 1]
        anchor = current.shot_2.continuity_anchor or current.continuity_bridge
        links.append(
            KlingContinuityLink(
                from_clip_index=current.clip_index,
                to_clip_index=nxt.clip_index,
                continuity_anchor=anchor,
            )
        )
        notes.append(
            f"Clip {current.clip_index} Shot 2 final frame → Clip {nxt.clip_index} first frame upload"
        )

    return KlingContinuityChain(
        run_id=str(run_id),
        clip_count=plan.clip_count,
        links=links,
        frame_sources=frame_sources,
        continuity_notes=notes,
    )


def validate_kling_native_audio_plan(plan: KlingNativeAudioPlan) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if plan.version != KLING_NATIVE_AUDIO_PLAN_VERSION:
        errors.append(f"unexpected plan version: {plan.version}")
    if plan.provider != KLING_PROVIDER_ID:
        errors.append(f"unexpected provider: {plan.provider}")
    if plan.strategy != MULTISHOT_STRATEGY:
        errors.append(f"unexpected strategy: {plan.strategy}")
    if plan.audio_strategy != KLING_AUDIO_STRATEGY:
        errors.append(f"unexpected audio_strategy: {plan.audio_strategy}")
    if not plan.native_audio_required:
        errors.append("native_audio_required must be true")
    if plan.use_elevenlabs:
        errors.append("use_elevenlabs must be false for Kling native audio plans")
    if plan.use_external_music:
        errors.append("use_external_music must be false for Kling native audio plans")
    if not plan.subtitle_required:
        errors.append("subtitle_required must be true")

    expected_clips = plan.planned_duration_seconds // KLING_DURATION_STEP_SECONDS
    if plan.clip_count != expected_clips:
        errors.append(f"clip_count {plan.clip_count} != expected {expected_clips}")
    if len(plan.clips) != plan.clip_count:
        errors.append(f"clips length {len(plan.clips)} != clip_count {plan.clip_count}")

    for clip in plan.clips:
        if clip.clip_duration_seconds != CLIP_DURATION_SECONDS:
            errors.append(f"clip {clip.clip_index}: clip_duration_seconds must be {CLIP_DURATION_SECONDS}")
        if clip.shot_1.duration_seconds != SHOT_1_DURATION_SECONDS:
            errors.append(f"clip {clip.clip_index}: shot_1 must be {SHOT_1_DURATION_SECONDS}s")
        if clip.shot_2.duration_seconds != SHOT_2_DURATION_SECONDS:
            errors.append(f"clip {clip.clip_index}: shot_2 must be {SHOT_2_DURATION_SECONDS}s")
        if clip.shot_1.role != SHOT_ROLE_MAIN_ACTION:
            errors.append(f"clip {clip.clip_index}: shot_1 role must be {SHOT_ROLE_MAIN_ACTION}")
        if clip.shot_2.role != SHOT_ROLE_TRANSITION_BRIDGE:
            errors.append(f"clip {clip.clip_index}: shot_2 role must be {SHOT_ROLE_TRANSITION_BRIDGE}")

    return not errors, errors


__all__ = [
    "FIRST_FRAME_PRIOR_CLIP",
    "FIRST_FRAME_USER_UPLOAD",
    "KLING_AUDIO_STRATEGY",
    "KLING_CONTINUITY_CHAIN_VERSION",
    "KLING_DURATION_STEP_SECONDS",
    "KLING_NATIVE_AUDIO_PLAN_VERSION",
    "KLING_PROVIDER_ID",
    "KLING_SHOT_PROMPT_MAX_CHARS",
    "KlingClipPlan",
    "KlingContinuityChain",
    "KlingContinuityLink",
    "KlingFrameSource",
    "KlingNativeAudioPlan",
    "KlingShotPlan",
    "MULTISHOT_STRATEGY",
    "NativeAudioDirectives",
    "SUPPORTED_KLING_DURATIONS",
    "build_clip_plan_skeleton",
    "build_continuity_chain_from_plan",
    "build_kling_native_audio_plan",
    "default_shot_plans",
    "kling_clip_count_for_duration",
    "normalize_kling_duration",
    "validate_kling_native_audio_plan",
]
