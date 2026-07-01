"""Story progression engine — cinematic chapter arcs for multi-clip Frame-to-Video stories."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

STORY_PROGRESSION_VERSION = "story_progression_engine_v1"

CHAPTER_ROLES_BY_CLIP_COUNT: dict[int, tuple[str, ...]] = {
    1: ("hook",),
    2: ("hook", "payoff"),
    3: ("hook", "escalation", "resolution"),
    4: ("hook", "escalation", "conflict", "resolution"),
    5: ("hook", "escalation", "conflict", "twist", "resolution"),
    6: ("hook", "escalation", "conflict", "twist", "climax", "resolution"),
}

ROLE_DISPLAY_LABELS: dict[str, str] = {
    "hook": "Hook",
    "payoff": "Payoff",
    "escalation": "Escalation",
    "conflict": "Conflict",
    "twist": "Twist",
    "climax": "Climax",
    "resolution": "Resolution",
}

ROLE_CONFLICT_LEVEL: dict[str, int] = {
    "hook": 1,
    "payoff": 2,
    "escalation": 2,
    "conflict": 3,
    "twist": 4,
    "climax": 5,
    "resolution": 1,
}

ROLE_EMOTION: dict[str, str] = {
    "hook": "curiosity and intrigue",
    "payoff": "satisfaction and wonder",
    "escalation": "rising tension and urgency",
    "conflict": "fear, pressure, and stakes",
    "twist": "shock and reorientation",
    "climax": "peak emotional intensity",
    "resolution": "relief, closure, and hope",
}

ROLE_CAMERA: dict[str, str] = {
    "hook": "Dramatic opening push-in, shallow depth of field, arresting first image",
    "payoff": "Rewarding medium-wide reveal, gentle dolly out, emotional payoff hold",
    "escalation": "Tracking shot building momentum, environment opens, forward motion",
    "conflict": "Dynamic angles, close coverage, handheld urgency, rack focus on faces",
    "twist": "Sudden angle shift, reveal framing, whip-pan into unexpected beat",
    "climax": "Intense close coverage, low-angle hero framing, peak visual energy",
    "resolution": "Wide resolving arc, slow dolly out, calm final hold on closure",
}

ROLE_DIALOGUE_GOAL: dict[str, str] = {
    "hook": "Plant a question or wonder that pulls the viewer in",
    "payoff": "Deliver the promised emotional reward without repeating the hook",
    "escalation": "Raise stakes with a line that commits characters to the next danger",
    "conflict": "Express fear, defiance, or impossible choice under pressure",
    "twist": "Reveal information that reframes everything the audience assumed",
    "climax": "Peak spoken beat — courage, sacrifice, or decisive action",
    "resolution": "Quiet closure line — gratitude, relief, or forward-looking hope",
}

ROLE_STORY_OBJECTIVE: dict[str, str] = {
    "hook": "Open with a visually arresting moment that establishes wonder and stakes",
    "payoff": "Deliver the emotional payoff promised by the hook — do not repeat the opening",
    "escalation": "Advance the journey — new obstacle, deeper location, higher stakes",
    "conflict": "Force a confrontation or impossible choice — story must change here",
    "twist": "Reveal a surprise that reframes the story direction",
    "climax": "Reach the highest-stakes action beat before closure",
    "resolution": "Resolve tension with emotional closure — story completes, do not repeat prior beats",
}

ROLE_VISUAL_PROGRESSION: dict[str, str] = {
    "hook": "Establish world, characters, and visual hook — fresh opening imagery",
    "payoff": "Shift camera and action to deliver payoff — new composition, not a replay",
    "escalation": "Move deeper into environment, widen or narrow scope to show escalation",
    "conflict": "Tighten framing, increase motion, visual chaos or confrontation",
    "twist": "Visual reveal — lighting shift, new element, perspective change",
    "climax": "Maximum visual intensity — closest framing, strongest motion",
    "resolution": "Open framing, calmer motion, visual rest after peak",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def chapter_roles_for_clip_count(clip_count: int) -> tuple[str, ...]:
    count = max(1, min(6, int(clip_count)))
    return CHAPTER_ROLES_BY_CLIP_COUNT[count]


def chapter_display_label(chapter_role: str) -> str:
    return ROLE_DISPLAY_LABELS.get(chapter_role.lower(), chapter_role.replace("_", " ").title())


def story_chapter_for_clip(clip_index: int, *, clip_count: int | None = None) -> str:
    """Display label for a clip chapter (backward-compatible helper)."""
    if clip_count is None:
        clip_count = max(clip_index, 1)
    roles = chapter_roles_for_clip_count(clip_count)
    if clip_index <= 0 or clip_index > len(roles):
        return f"Chapter {clip_index}"
    return chapter_display_label(roles[clip_index - 1])


@dataclass
class StoryChapterClip:
    clip_index: int
    chapter_role: str
    story_objective: str
    emotion: str
    conflict_level: int
    camera_style: str
    dialogue_goal: str
    next_chapter_hint: str
    visual_progression: str = ""
    story_beat: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "chapter_role": self.chapter_role,
            "chapter_label": chapter_display_label(self.chapter_role),
            "story_objective": self.story_objective,
            "emotion": self.emotion,
            "conflict_level": self.conflict_level,
            "camera_style": self.camera_style,
            "dialogue_goal": self.dialogue_goal,
            "next_chapter_hint": self.next_chapter_hint,
            "visual_progression": self.visual_progression,
            "story_beat": self.story_beat,
        }


@dataclass
class StoryProgressionPlan:
    version: str = STORY_PROGRESSION_VERSION
    planned_duration_seconds: int = 30
    clip_count: int = 2
    chapters: list[StoryChapterClip] = field(default_factory=list)
    validation_status: str = "PASS"
    validation_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "planned_duration_seconds": self.planned_duration_seconds,
            "clip_count": self.clip_count,
            "chapters": [chapter.to_dict() for chapter in self.chapters],
            "validation_status": self.validation_status,
            "validation_notes": list(self.validation_notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StoryProgressionPlan:
        chapters = [
            StoryChapterClip(
                clip_index=int(item.get("clip_index") or 0),
                chapter_role=str(item.get("chapter_role") or ""),
                story_objective=str(item.get("story_objective") or ""),
                emotion=str(item.get("emotion") or ""),
                conflict_level=int(item.get("conflict_level") or 1),
                camera_style=str(item.get("camera_style") or ""),
                dialogue_goal=str(item.get("dialogue_goal") or ""),
                next_chapter_hint=str(item.get("next_chapter_hint") or ""),
                visual_progression=str(item.get("visual_progression") or ""),
                story_beat=str(item.get("story_beat") or ""),
            )
            for item in list(payload.get("chapters") or [])
        ]
        return cls(
            version=str(payload.get("version") or STORY_PROGRESSION_VERSION),
            planned_duration_seconds=int(payload.get("planned_duration_seconds") or 0),
            clip_count=int(payload.get("clip_count") or len(chapters)),
            chapters=chapters,
            validation_status=str(payload.get("validation_status") or "PASS"),
            validation_notes=[str(x) for x in list(payload.get("validation_notes") or [])],
        )


def _next_chapter_hint(current_role: str, next_role: str | None, *, topic: str) -> str:
    if not next_role:
        return "Final chapter — hold emotional closure on the last frame"
    subject = _clean(topic) or "the characters"
    return (
        f"Bridge toward {chapter_display_label(next_role)}: {ROLE_STORY_OBJECTIVE[next_role]} "
        f"for {subject} — do not repeat {chapter_display_label(current_role)} imagery or action"
    )


def _compose_story_objective(*, role: str, beat: str, topic: str) -> str:
    base = ROLE_STORY_OBJECTIVE.get(role, "Advance the story")
    beat_text = _clean(beat)
    topic_text = _clean(topic)
    if beat_text:
        return f"{base}. Beat: {beat_text}"
    if topic_text:
        return f"{base}. Story: {topic_text}"
    return base


def build_story_progression_plan(
    *,
    planned_duration_seconds: int,
    clip_count: int | None = None,
    topic: str = "",
    story_beats: list[str] | None = None,
    mood: str = "",
) -> StoryProgressionPlan:
    """Build per-clip chapter progression for a Frame-to-Video story arc."""
    from content_brain.execution.kling_frame_to_video_models import normalize_kling_frame_story_duration

    planned, resolved_clip_count, _ = normalize_kling_frame_story_duration(planned_duration_seconds)
    if clip_count is not None and int(clip_count) > 0:
        resolved_clip_count = int(clip_count)

    roles = chapter_roles_for_clip_count(resolved_clip_count)
    beats = list(story_beats or [])
    while len(beats) < resolved_clip_count:
        beats.append("")

    chapters: list[StoryChapterClip] = []
    for index, role in enumerate(roles, start=1):
        next_role = roles[index] if index < len(roles) else None
        beat = beats[index - 1] if index - 1 < len(beats) else ""
        emotion = ROLE_EMOTION.get(role, _clean(mood) or "cinematic emotion")
        chapters.append(
            StoryChapterClip(
                clip_index=index,
                chapter_role=role,
                story_objective=_compose_story_objective(role=role, beat=beat, topic=topic),
                emotion=emotion,
                conflict_level=ROLE_CONFLICT_LEVEL.get(role, 1),
                camera_style=ROLE_CAMERA.get(role, ROLE_CAMERA["hook"]),
                dialogue_goal=ROLE_DIALOGUE_GOAL.get(role, "Advance dialogue naturally"),
                next_chapter_hint=_next_chapter_hint(role, next_role, topic=topic),
                visual_progression=ROLE_VISUAL_PROGRESSION.get(role, ""),
                story_beat=beat,
            )
        )

    plan = StoryProgressionPlan(
        planned_duration_seconds=planned,
        clip_count=resolved_clip_count,
        chapters=chapters,
    )
    ok, notes = validate_story_progression_plan(plan)
    plan.validation_status = "PASS" if ok else "FAIL"
    plan.validation_notes = notes
    return plan


def validate_story_progression_plan(plan: StoryProgressionPlan) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not plan.chapters:
        return False, ["no chapters generated"]

    roles = [chapter.chapter_role for chapter in plan.chapters]
    expected = chapter_roles_for_clip_count(plan.clip_count)
    if tuple(roles) != expected:
        notes.append(f"chapter roles {roles} != expected {list(expected)}")

    if len(set(roles)) != len(roles):
        notes.append("duplicate chapter roles in sequence")

    if roles[-1] != "resolution" and plan.clip_count > 1:
        if roles[-1] not in {"payoff", "resolution"}:
            notes.append("final chapter is not resolution or payoff")

    pre_resolution = [c.conflict_level for c in plan.chapters[:-1]]
    if pre_resolution and max(pre_resolution) < 2 and plan.clip_count > 2:
        notes.append("conflict did not rise before final chapter")

    rising = [c for c in plan.chapters if c.chapter_role not in {"resolution", "payoff"}]
    for prev, curr in zip(rising, rising[1:]):
        if curr.conflict_level < prev.conflict_level:
            notes.append(
                f"conflict decreased from {prev.chapter_role}({prev.conflict_level}) "
                f"to {curr.chapter_role}({curr.conflict_level}) before resolution"
            )

    last = plan.chapters[-1]
    if plan.clip_count > 1 and last.chapter_role not in {"resolution", "payoff"}:
        notes.append(f"last chapter role is {last.chapter_role}, expected resolution or payoff")

    return not notes, notes


def chapter_for_clip_index(plan: StoryProgressionPlan, clip_index: int) -> StoryChapterClip | None:
    for chapter in plan.chapters:
        if chapter.clip_index == clip_index:
            return chapter
    return None


def progression_summary_lines(plan: StoryProgressionPlan) -> list[str]:
    return [f"Clip {c.clip_index}: {chapter_display_label(c.chapter_role)}" for c in plan.chapters]


__all__ = [
    "CHAPTER_ROLES_BY_CLIP_COUNT",
    "STORY_PROGRESSION_VERSION",
    "StoryChapterClip",
    "StoryProgressionPlan",
    "build_story_progression_plan",
    "chapter_display_label",
    "chapter_for_clip_index",
    "chapter_roles_for_clip_count",
    "progression_summary_lines",
    "story_chapter_for_clip",
    "validate_story_progression_plan",
]
