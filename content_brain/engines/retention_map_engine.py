"""
Retention Map Engine for the Viral Content Brain.

Converts StoryBlueprint + VideoFormatPlan into a clip-aware retention map.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional

from content_brain.schemas.content_brief import RetentionBeat, RetentionMap, StoryBlueprint, StoryBeat
from content_brain.engines.video_format_planner import VideoFormatPlan


@dataclass
class ClipWindow:
    clip_index: int
    start_second: float
    end_second: float

    @property
    def duration(self) -> float:
        return self.end_second - self.start_second


@dataclass
class RetentionBeatPlan:
    beat_id: str
    start_second: float
    end_second: float
    retention_mechanic: str
    visual_instruction: str
    audio_instruction: str
    caption_instruction: str
    intensity_score: float
    risk_note: str
    clip_index: int
    clip_start_second: float
    clip_end_second: float
    story_beat_id: str = ""
    required: bool = True

    def to_retention_beat(self) -> RetentionBeat:
        implementation_note = (
            f"VISUAL: {self.visual_instruction} | "
            f"AUDIO: {self.audio_instruction} | "
            f"CAPTION: {self.caption_instruction} | "
            f"CLIP: {self.clip_index} [{self.clip_start_second}-{self.clip_end_second}] | "
            f"INTENSITY: {self.intensity_score:.2f} | "
            f"RISK: {self.risk_note}"
        )
        if self.story_beat_id:
            implementation_note += f" | STORY: {self.story_beat_id}"

        return RetentionBeat(
            block_label=self.beat_id,
            start_second=self.start_second,
            end_second=self.end_second,
            mechanic=self.retention_mechanic,
            implementation_note=implementation_note,
            required=self.required,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "start_second": self.start_second,
            "end_second": self.end_second,
            "retention_mechanic": self.retention_mechanic,
            "visual_instruction": self.visual_instruction,
            "audio_instruction": self.audio_instruction,
            "caption_instruction": self.caption_instruction,
            "intensity_score": self.intensity_score,
            "risk_note": self.risk_note,
            "clip_index": self.clip_index,
            "clip_start_second": self.clip_start_second,
            "clip_end_second": self.clip_end_second,
            "story_beat_id": self.story_beat_id,
            "required": self.required,
        }


@dataclass
class RetentionMapResult:
    retention_map: RetentionMap
    beat_plans: list[RetentionBeatPlan]
    clip_windows: list[ClipWindow]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasoning": self.reasoning,
            "retention_map": self.retention_map.to_dict(),
            "clip_windows": [
                {
                    "clip_index": clip.clip_index,
                    "start_second": clip.start_second,
                    "end_second": clip.end_second,
                }
                for clip in self.clip_windows
            ],
            "beat_plans": [beat.to_dict() for beat in self.beat_plans],
        }


class RetentionMapEngine:
    """
    Build retention-optimized beat maps aligned to provider clip boundaries.

    Usage:
        engine = RetentionMapEngine()
        result = engine.build(profile, story_blueprint, format_plan)
    """

    PATTERN_BREAK_MECHANICS = [
        "perspective_shift",
        "sound_drop",
        "object_focus",
        "false_resolution",
    ]

    def build(
        self,
        profile: dict[str, Any],
        story_blueprint: StoryBlueprint,
        format_plan: VideoFormatPlan,
    ) -> RetentionMapResult:
        clip_windows = self._build_clip_windows(format_plan)
        story_context = self._extract_story_context(story_blueprint)
        retention_rules = profile.get("retention_rules", {})
        max_gap = float(retention_rules.get("max_seconds_without_beat", 5))

        beats: list[RetentionBeatPlan] = []
        beats.extend(self._build_story_retention_beats(story_context, clip_windows, profile))
        beats.extend(self._build_clip_boundary_beats(story_context, clip_windows, format_plan))
        beats.extend(self._build_opening_sequence(story_context, clip_windows, profile))
        beats = self._densify_beats(
            beats=beats,
            total_duration=format_plan.target_duration_seconds,
            max_gap=max_gap,
            clip_windows=clip_windows,
            story_context=story_context,
        )
        beats.extend(
            self._build_pattern_break_beats(
                total_duration=format_plan.target_duration_seconds,
                clip_windows=clip_windows,
                story_context=story_context,
                existing_beats=beats,
            )
        )

        beats = self._merge_and_sort_beats(beats)
        beats = self._boost_first_three_seconds(beats, clip_windows, story_context)

        score = self._estimate_retention_score(beats, profile, format_plan)
        pattern_break_count = sum(
            1 for beat in beats if beat.retention_mechanic in self.PATTERN_BREAK_MECHANICS
        )
        loop_seed_present = any(
            beat.story_beat_id == "LOOP_SEED" or beat.retention_mechanic == "open_loop"
            for beat in beats
        )

        retention_map = RetentionMap(
            beats=[beat.to_retention_beat() for beat in beats],
            retention_score_estimate=score,
            pattern_break_count=pattern_break_count,
            loop_seed_present=loop_seed_present,
        )

        reasoning = (
            f"Built {len(beats)} retention beats across {format_plan.clip_count} "
            f"{format_plan.clip_duration_seconds}s clips ({format_plan.provider_name}) "
            f"for {format_plan.target_duration_seconds}s total."
        )

        return RetentionMapResult(
            retention_map=retention_map,
            beat_plans=beats,
            clip_windows=clip_windows,
            reasoning=reasoning,
        )

    def build_retention_map(
        self,
        profile: dict[str, Any],
        story_blueprint: StoryBlueprint,
        format_plan: VideoFormatPlan,
    ) -> RetentionMap:
        return self.build(profile, story_blueprint, format_plan).retention_map

    def _build_clip_windows(self, format_plan: VideoFormatPlan) -> list[ClipWindow]:
        windows: list[ClipWindow] = []
        clip_duration = format_plan.clip_duration_seconds
        total = format_plan.target_duration_seconds

        for index in range(format_plan.clip_count):
            start = float(index * clip_duration)
            end = float(min(total, (index + 1) * clip_duration))
            if end <= start:
                continue
            windows.append(
                ClipWindow(
                    clip_index=index,
                    start_second=start,
                    end_second=end,
                )
            )

        if not windows and total > 0:
            windows.append(ClipWindow(clip_index=0, start_second=0.0, end_second=float(total)))

        return windows

    def _extract_story_context(self, story_blueprint: StoryBlueprint) -> dict[str, Any]:
        beats: dict[str, dict[str, str]] = {}
        for beat in story_blueprint.beats:
            beat_key = self._normalize_story_beat_id(beat.beat_id)
            parsed = _parse_story_beat_fields(beat)
            beats[beat_key] = {
                "start_second": str(beat.start_second),
                "end_second": str(beat.end_second),
                "purpose": parsed["purpose"],
                "narration": parsed["narration"],
                "visual": parsed["visual"],
                "retention_mechanic": beat.retention_mechanic,
                "emotional_tone": beat.emotional_tone,
            }

        return {
            "beats": beats,
            "loop_seed": story_blueprint.loop_seed,
            "sensory_anchor": story_blueprint.sensory_anchor,
            "reveal_type": story_blueprint.reveal_type,
            "duration": story_blueprint.total_duration_seconds,
        }

    def _build_story_retention_beats(
        self,
        story_context: dict[str, Any],
        clip_windows: list[ClipWindow],
        profile: dict[str, Any],
    ) -> list[RetentionBeatPlan]:
        beats: list[RetentionBeatPlan] = []

        for story_id, data in story_context["beats"].items():
            start = float(data["start_second"])
            end = float(data["end_second"])
            clip = self._clip_for_second(start, clip_windows)
            intensity = _story_intensity(story_id)

            beats.append(
                RetentionBeatPlan(
                    beat_id=f"story_{story_id.lower()}",
                    start_second=start,
                    end_second=end,
                    retention_mechanic=data["retention_mechanic"] or _default_mechanic(story_id),
                    visual_instruction=data["visual"] or f"Visual support for {story_id}.",
                    audio_instruction=_audio_for_story(story_id, data["narration"]),
                    caption_instruction=_caption_for_story(story_id, data["narration"], profile),
                    intensity_score=intensity,
                    risk_note=_risk_for_story(story_id),
                    clip_index=clip.clip_index,
                    clip_start_second=clip.start_second,
                    clip_end_second=clip.end_second,
                    story_beat_id=story_id,
                )
            )

        return beats

    def _build_clip_boundary_beats(
        self,
        story_context: dict[str, Any],
        clip_windows: list[ClipWindow],
        format_plan: VideoFormatPlan,
    ) -> list[RetentionBeatPlan]:
        beats: list[RetentionBeatPlan] = []
        clip_duration = format_plan.clip_duration_seconds
        mini_hook_span = min(1.5, max(0.8, clip_duration * 0.22))
        mini_payoff_span = min(1.8, max(1.0, clip_duration * 0.28))

        for clip in clip_windows:
            hook_end = min(clip.end_second, clip.start_second + mini_hook_span)
            payoff_start = max(clip.start_second, clip.end_second - mini_payoff_span)

            beats.append(
                RetentionBeatPlan(
                    beat_id=f"clip_{clip.clip_index}_mini_hook",
                    start_second=clip.start_second,
                    end_second=hook_end,
                    retention_mechanic="pattern_interrupt",
                    visual_instruction=(
                        f"Clip {clip.clip_index + 1} opens with immediate motion or new detail; "
                        f"do not fade in from black."
                    ),
                    audio_instruction=(
                        "Hard audio start or sudden contrast against previous clip ending."
                        if clip.clip_index > 0
                        else "Open with voice or sound in frame 0."
                    ),
                    caption_instruction=(
                        "On-screen text only if it adds tension or clarity in the first second."
                    ),
                    intensity_score=0.88 if clip.clip_index == 0 else 0.78,
                    risk_note="Weak clip openings cause multi-clip drop-off.",
                    clip_index=clip.clip_index,
                    clip_start_second=clip.start_second,
                    clip_end_second=clip.end_second,
                )
            )

            if payoff_start < clip.end_second:
                beats.append(
                    RetentionBeatPlan(
                        beat_id=f"clip_{clip.clip_index}_mini_payoff",
                        start_second=payoff_start,
                        end_second=clip.end_second,
                        retention_mechanic="small_reveal",
                        visual_instruction=(
                            f"Close clip {clip.clip_index + 1} with one concrete visual turn "
                            f"that makes the next clip necessary."
                        ),
                        audio_instruction="End with a line, sound spike, or silence that pulls forward.",
                        caption_instruction="If used, one short line that tees up the next clip.",
                        intensity_score=0.74,
                        risk_note="Clip ends that feel complete kill continuity.",
                        clip_index=clip.clip_index,
                        clip_start_second=clip.start_second,
                        clip_end_second=clip.end_second,
                    )
                )

        if story_context.get("sensory_anchor"):
            first_clip = clip_windows[0]
            beats.append(
                RetentionBeatPlan(
                    beat_id="sensory_anchor",
                    start_second=first_clip.start_second,
                    end_second=min(first_clip.end_second, first_clip.start_second + 2.0),
                    retention_mechanic="object_focus",
                    visual_instruction=story_context["sensory_anchor"],
                    audio_instruction="Let the sensory detail have one clean audio moment.",
                    caption_instruction="No caption needed unless it names the sensory detail.",
                    intensity_score=0.82,
                    risk_note="Missing sensory anchor makes the story feel generic.",
                    clip_index=first_clip.clip_index,
                    clip_start_second=first_clip.start_second,
                    clip_end_second=first_clip.end_second,
                )
            )

        return beats

    def _build_opening_sequence(
        self,
        story_context: dict[str, Any],
        clip_windows: list[ClipWindow],
        profile: dict[str, Any],
    ) -> list[RetentionBeatPlan]:
        if not clip_windows:
            return []

        first_clip = clip_windows[0]
        hook_story = story_context["beats"].get("HOOK_BEAT", {})
        narration = hook_story.get("narration", "Deliver the hook immediately.")

        blocks = profile.get("retention_rules", {}).get("beat_blocks", [])
        opening_templates = {
            0.0: ("visual_hook", "pattern_interrupt", 0.95),
            1.0: ("verbal_hook_completion", "curiosity_gap", 0.90),
            2.0: ("opening_stakes_lock", "stakes_lock", 0.86),
        }

        beats: list[RetentionBeatPlan] = []
        for start_offset, (beat_id, mechanic, intensity) in opening_templates.items():
            start = first_clip.start_second + start_offset
            end = min(first_clip.end_second, start + 1.0)
            if start >= 3.0:
                continue

            template = next((item for item in blocks if item.get("block_label") == beat_id), None)
            visual = template.get("implementation", "Strong opening visual contrast.") if template else (
                "Tight close-up or immediate motion in frame 0."
            )

            beats.append(
                RetentionBeatPlan(
                    beat_id=f"opening_{beat_id}",
                    start_second=start,
                    end_second=end,
                    retention_mechanic=mechanic,
                    visual_instruction=visual,
                    audio_instruction="Front-load the most important spoken line or sound.",
                    caption_instruction=narration[:80],
                    intensity_score=intensity,
                    risk_note="First 3 seconds must not feel slow.",
                    clip_index=first_clip.clip_index,
                    clip_start_second=first_clip.start_second,
                    clip_end_second=first_clip.end_second,
                    story_beat_id="HOOK_BEAT" if start_offset <= 1.0 else "",
                )
            )

        return beats

    def _densify_beats(
        self,
        beats: list[RetentionBeatPlan],
        total_duration: int,
        max_gap: float,
        clip_windows: list[ClipWindow],
        story_context: dict[str, Any],
    ) -> list[RetentionBeatPlan]:
        if total_duration <= 0:
            return beats

        anchors = sorted({round(beat.start_second, 1) for beat in beats} | {0.0, float(total_duration)})
        filler: list[RetentionBeatPlan] = []
        filler_index = 1

        for index in range(len(anchors) - 1):
            start = anchors[index]
            end = anchors[index + 1]
            gap = end - start
            if gap <= max_gap:
                continue

            subdivisions = int(gap // max_gap)
            step = gap / (subdivisions + 1)
            for sub in range(1, subdivisions + 1):
                beat_start = round(start + step * sub, 1)
                beat_end = round(min(total_duration, beat_start + min(1.5, max_gap - 0.5)), 1)
                clip = self._clip_for_second(beat_start, clip_windows)
                filler.append(
                    RetentionBeatPlan(
                        beat_id=f"density_{filler_index}",
                        start_second=beat_start,
                        end_second=beat_end,
                        retention_mechanic="object_focus",
                        visual_instruction=(
                            f"Insert a new detail tied to {story_context.get('reveal_type', 'the story')}."
                        ),
                        audio_instruction="Keep voice or sound active; avoid dead air.",
                        caption_instruction="Optional micro-caption if it adds clarity.",
                        intensity_score=0.62,
                        risk_note="Gap created risk of scroll-away.",
                        clip_index=clip.clip_index,
                        clip_start_second=clip.start_second,
                        clip_end_second=clip.end_second,
                    )
                )
                filler_index += 1

        return beats + filler

    def _build_pattern_break_beats(
        self,
        total_duration: int,
        clip_windows: list[ClipWindow],
        story_context: dict[str, Any],
        existing_beats: list[RetentionBeatPlan],
    ) -> list[RetentionBeatPlan]:
        if total_duration <= 0:
            return []

        interval = 8.0 if total_duration <= 32 else 9.0
        existing_starts = {round(beat.start_second, 1) for beat in existing_beats}
        breaks: list[RetentionBeatPlan] = []
        cursor = interval
        break_index = 1

        while cursor < total_duration - 2:
            if any(abs(cursor - start) < 1.5 for start in existing_starts):
                cursor += interval
                continue

            clip = self._clip_for_second(cursor, clip_windows)
            mechanic = self.PATTERN_BREAK_MECHANICS[(break_index - 1) % len(self.PATTERN_BREAK_MECHANICS)]
            breaks.append(
                RetentionBeatPlan(
                    beat_id=f"pattern_break_{break_index}",
                    start_second=cursor,
                    end_second=min(total_duration, cursor + 1.5),
                    retention_mechanic=mechanic,
                    visual_instruction=_visual_for_mechanic(mechanic),
                    audio_instruction=_audio_for_mechanic(mechanic),
                    caption_instruction="Use only if the break needs one clarifying line.",
                    intensity_score=0.76,
                    risk_note="Predictable pacing without breaks loses retention.",
                    clip_index=clip.clip_index,
                    clip_start_second=clip.start_second,
                    clip_end_second=clip.end_second,
                )
            )
            break_index += 1
            cursor += interval

        return breaks

    def _boost_first_three_seconds(
        self,
        beats: list[RetentionBeatPlan],
        clip_windows: list[ClipWindow],
        story_context: dict[str, Any],
    ) -> list[RetentionBeatPlan]:
        boosted: list[RetentionBeatPlan] = []
        hook_narration = story_context["beats"].get("HOOK_BEAT", {}).get("narration", "")

        for beat in beats:
            updated = beat
            if beat.start_second < 3.0:
                updated = RetentionBeatPlan(
                    **{
                        **beat.__dict__,
                        "intensity_score": min(1.0, beat.intensity_score + 0.05),
                    }
                )
            boosted.append(updated)

        if clip_windows and not any(beat.start_second <= 0.1 for beat in boosted):
            first_clip = clip_windows[0]
            boosted.insert(
                0,
                RetentionBeatPlan(
                    beat_id="opening_frame_zero",
                    start_second=0.0,
                    end_second=min(1.0, first_clip.end_second),
                    retention_mechanic="pattern_interrupt",
                    visual_instruction="Frame 0 must contain motion, contrast, or human focus.",
                    audio_instruction="Start audio immediately; no silent intro.",
                    caption_instruction=hook_narration[:70],
                    intensity_score=0.98,
                    risk_note="Blank frame zero is a retention failure.",
                    clip_index=first_clip.clip_index,
                    clip_start_second=first_clip.start_second,
                    clip_end_second=first_clip.end_second,
                    story_beat_id="HOOK_BEAT",
                ),
            )

        return boosted

    def _merge_and_sort_beats(self, beats: list[RetentionBeatPlan]) -> list[RetentionBeatPlan]:
        by_id: dict[str, RetentionBeatPlan] = {}

        for beat in beats:
            existing = by_id.get(beat.beat_id)
            if existing is None or beat.intensity_score > existing.intensity_score:
                by_id[beat.beat_id] = beat

        return sorted(by_id.values(), key=lambda item: (item.start_second, item.beat_id))

    def _estimate_retention_score(
        self,
        beats: list[RetentionBeatPlan],
        profile: dict[str, Any],
        format_plan: VideoFormatPlan,
    ) -> float:
        if not beats:
            return 0.0

        total = max(format_plan.target_duration_seconds, 1)
        max_gap = float(profile.get("retention_rules", {}).get("max_seconds_without_beat", 5))
        anchors = sorted({round(beat.start_second, 1) for beat in beats} | {0.0, float(total)})

        largest_gap = max(anchors[index + 1] - anchors[index] for index in range(len(anchors) - 1))
        gap_score = max(0.0, 100.0 - max(0.0, largest_gap - max_gap) * 18.0)

        opening_score = min(
            100.0,
            len([beat for beat in beats if beat.start_second < 3.0]) * 20.0,
        )

        clip_boundary_score = 100.0
        expected_boundaries = format_plan.clip_count * 2
        actual_boundaries = sum(
            1 for beat in beats if "mini_hook" in beat.beat_id or "mini_payoff" in beat.beat_id
        )
        if expected_boundaries:
            clip_boundary_score = min(100.0, (actual_boundaries / expected_boundaries) * 100.0)

        pattern_breaks = sum(
            1 for beat in beats if beat.retention_mechanic in self.PATTERN_BREAK_MECHANICS
        )
        min_breaks = int(profile.get("retention_rules", {}).get("minimum_pattern_breaks", 2))
        pattern_score = min(100.0, (pattern_breaks / max(min_breaks, 1)) * 85.0)

        score = (
            gap_score * 0.30
            + opening_score * 0.25
            + clip_boundary_score * 0.25
            + pattern_score * 0.20
        )
        return round(min(100.0, max(0.0, score)), 2)

    def _clip_for_second(self, second: float, clip_windows: list[ClipWindow]) -> ClipWindow:
        for clip in clip_windows:
            if clip.start_second <= second < clip.end_second:
                return clip
        return clip_windows[-1]

    def _normalize_story_beat_id(self, beat_id: str) -> str:
        normalized = beat_id.upper().replace("STORY_", "")
        if normalized.endswith("_BEAT"):
            return normalized
        return f"{normalized}_BEAT" if normalized else "HOOK_BEAT"


def _parse_story_beat_fields(beat: StoryBeat) -> dict[str, str]:
    purpose = ""
    narration = ""
    visual = ""

    if "PURPOSE:" in beat.description:
        parts = beat.description.split("|")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("PURPOSE:"):
                purpose = cleaned[len("PURPOSE:"):].strip()
            elif cleaned.startswith("NARRATION:"):
                narration = cleaned[len("NARRATION:"):].strip()
            elif cleaned.startswith("VISUAL:"):
                visual = cleaned[len("VISUAL:"):].strip()
    else:
        narration = beat.description

    return {
        "purpose": purpose or beat.emotional_tone,
        "narration": narration or beat.description,
        "visual": visual,
    }


def _story_intensity(story_beat_id: str) -> float:
    mapping = {
        "HOOK_BEAT": 0.90,
        "CONTEXT_BEAT": 0.58,
        "ESCALATION_BEAT": 0.72,
        "PATTERN_BREAK": 0.78,
        "PAYOFF_BEAT": 0.92,
        "AFTERSHOCK": 0.80,
        "LOOP_SEED": 0.66,
    }
    return mapping.get(story_beat_id, 0.65)


def _default_mechanic(story_beat_id: str) -> str:
    mapping = {
        "HOOK_BEAT": "pattern_interrupt",
        "CONTEXT_BEAT": "curiosity_gap",
        "ESCALATION_BEAT": "stakes_increase",
        "PATTERN_BREAK": "perspective_shift",
        "PAYOFF_BEAT": "peak_moment",
        "AFTERSHOCK": "aftershock_silence",
        "LOOP_SEED": "open_loop",
    }
    return mapping.get(story_beat_id, "object_focus")


def _audio_for_story(story_beat_id: str, narration: str) -> str:
    if story_beat_id == "HOOK_BEAT":
        return "Lead with the hook line in the first second."
    if story_beat_id == "LOOP_SEED":
        return "End on a question or unresolved sound."
    if narration:
        return "Keep narration concise and synced to the visual turn."
    return "Use sound contrast to mark the beat."


def _caption_for_story(story_beat_id: str, narration: str, profile: dict[str, Any]) -> str:
    platform_rules = profile.get("platform_rules", {})
    caption_style = ""
    for rules in platform_rules.values():
        caption_style = str(rules.get("caption_style", caption_style))

    if story_beat_id == "HOOK_BEAT":
        return narration[:90] or "Hook text on screen in first 2 seconds."
    if "minimal" in caption_style.lower():
        return "One short line max."
    return "Caption only if it adds clarity or retention."


def _risk_for_story(story_beat_id: str) -> str:
    mapping = {
        "HOOK_BEAT": "Slow hook delivery causes immediate swipe.",
        "CONTEXT_BEAT": "Over-explaining here collapses curiosity.",
        "ESCALATION_BEAT": "Repeating the hook without new info causes drop-off.",
        "PATTERN_BREAK": "Missing the break makes the middle feel flat.",
        "PAYOFF_BEAT": "Weak payoff breaks trust with the hook.",
        "LOOP_SEED": "Closed endings reduce comments and saves.",
    }
    return mapping.get(story_beat_id, "Beat lacks specificity or pacing.")


def _visual_for_mechanic(mechanic: str) -> str:
    mapping = {
        "perspective_shift": "Change camera angle, subject distance, or scene location.",
        "sound_drop": "Pair a visual turn with a sudden audio reduction.",
        "object_focus": "Cut to one object that reframes the story.",
        "false_resolution": "Show a temporary answer that will collapse in the next beat.",
    }
    return mapping.get(mechanic, "Introduce a visible change in the frame.")


def _audio_for_mechanic(mechanic: str) -> str:
    mapping = {
        "perspective_shift": "Use a subtle whoosh or cut-point accent.",
        "sound_drop": "Drop music and keep one clean voice or ambient detail.",
        "object_focus": "Isolate foley on the object moment.",
        "false_resolution": "Sound briefly resolves, then reintroduce tension.",
    }
    return mapping.get(mechanic, "Use contrast against the previous beat.")


__all__ = [
    "ClipWindow",
    "RetentionBeatPlan",
    "RetentionMapEngine",
    "RetentionMapResult",
]


if __name__ == "__main__":
    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine
    from content_brain.engines.story_architecture_engine import StoryArchitectureEngine
    from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
    from content_brain.engines.video_format_planner import VideoFormatPlanner
    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import Platform

    loader = ProfileLoader()
    trend_engine = TrendDiscoveryEngine()
    hook_engine = HookEngineeringEngine()
    story_engine = StoryArchitectureEngine()
    format_planner = VideoFormatPlanner()
    retention_engine = RetentionMapEngine()

    cases = [
        ("football", 30, "hailuo", 6),
        ("perfume", 30, "hailuo", 8),
        ("horror", 60, "runway", 10),
    ]

    for niche, duration, provider, clip_duration in cases:
        profile = loader.resolve(niche=niche)
        trend = trend_engine.discover_best_signal(profile, niche=niche, topic=f"{niche} trend topic")
        hooks = hook_engine.generate_hook_package(profile, topic=trend.topic)
        format_plan = format_planner.plan(
            profile,
            platform=Platform.TIKTOK,
            user_duration_seconds=duration,
            provider_name=provider,
            provider_clip_duration_seconds=clip_duration,
        )
        story = story_engine.build_blueprint(profile, trend, hooks)
        story.total_duration_seconds = format_plan.target_duration_seconds
        result = retention_engine.build(profile, story, format_plan)

        print("\n" + "=" * 72)
        print(
            f"{niche.upper()} | {format_plan.clip_count}x{format_plan.clip_duration_seconds}s "
            f"{provider} | total {format_plan.target_duration_seconds}s"
        )
        print(f"RETENTION BEATS: {len(result.beat_plans)}")
        print(f"SCORE: {result.retention_map.retention_score_estimate}")
        print(f"PATTERN BREAKS: {result.retention_map.pattern_break_count}")
        print(f"VALID: {result.retention_map.validate().is_valid}")
        print(
            "CLIP 0 BEATS:",
            sum(1 for beat in result.beat_plans if beat.clip_index == 0),
        )
