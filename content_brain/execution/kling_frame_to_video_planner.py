"""Kling Frame-to-Video Native Audio — rich single-prompt story planner."""

from __future__ import annotations

from typing import Any

from content_brain.execution.kling_frame_to_video_models import (
    END_FRAME_GENERATED_TARGET,
    END_FRAME_NONE,
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
    KLING_FRAME_TO_VIDEO_MODE,
    KLING_MULTISHOT_MODE,
    KlingFrameToVideoClipPlan,
    KlingFrameToVideoPlan,
    normalize_kling_frame_story_duration,
    select_kling_generation_mode,
    validate_kling_frame_to_video_plan,
)
from content_brain.execution.kling_native_audio_models import (
    FIRST_FRAME_PRIOR_CLIP,
    FIRST_FRAME_PROMPT_ONLY,
    FIRST_FRAME_USER_UPLOAD,
    KLING_AUDIO_STRATEGY,
    KLING_PROVIDER_ID,
    NativeAudioDirectives,
)
from content_brain.story.story_first_prompt_engine import compose_story_first_frame_prompt_primary
from content_brain.story.story_progression_engine import (
    StoryChapterClip,
    build_story_progression_plan,
    chapter_display_label,
)
from content_brain.execution.kling_native_audio_planner import (
    KlingContentPlannerInput,
    _character_phrase,
    _clean,
    _continuity_anchor,
    _emotion_for_clip,
    _extract_dialogue,
    _next_clip_reference_hint,
    _resolve_story_context,
)

PLANNER_VERSION = "kling_frame_to_video_planner_v3_openai_story_first"

FORBIDDEN_PROMPT_TOKENS: tuple[str, ...] = (
    "elevenlabs",
    "eleven labs",
    "external music",
    "background music track",
    "voiceover narrator",
    "ai dub",
    "tts voice",
)

DEFAULT_CAMERA_BY_CLIP: tuple[str, ...] = (
    "Slow push-in with shallow depth of field, gentle handheld drift, hold final frame",
    "Tracking shot following characters through environment, settle into bridge hold",
    "Low-angle emotional close coverage, rack focus to faces, end on still frame",
    "Wide-to-medium arc resolving the story beat, slow dolly out, final hold",
)


def _contains_forbidden(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in FORBIDDEN_PROMPT_TOKENS)


def _truncate_prompt(text: str, *, max_chars: int = KLING_FRAME_PROMPT_MAX_CHARS) -> str:
    normalized = _clean(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."


def _build_native_audio_block(directives: NativeAudioDirectives) -> str:
    parts: list[str] = []
    if directives.dialogue_lines:
        parts.append(f'Dialogue: "{directives.dialogue_lines[0]}"')
    if directives.ambience:
        parts.append(f"Ambience: {', '.join(directives.ambience[:4])}")
    if directives.foley:
        parts.append(f"Foley: {', '.join(directives.foley[:4])}")
    if directives.voice_acting:
        parts.append(f"Voice acting: {directives.voice_acting}")
    parts.append("Native cinematic in-video audio only — no external narration or music track")
    return ". ".join(parts)


def _compose_frame_prompt(
    *,
    context: Any,
    beat: str,
    clip_index: int,
    total_clips: int,
    prior_bridge_hint: str,
    bridge_hint: str,
    camera_direction: str,
    character_continuity: str,
    environment_continuity: str,
    dialogue: str,
    directives: NativeAudioDirectives,
    continuity_anchor: str,
    next_hint: str,
    chapter: StoryChapterClip | None = None,
    platform: str = "",
    youtube_genre: str = "",
    instagram_genre: str = "",
    tiktok_genre: str = "",
    genre: str = "",
) -> str:
    cast = _character_phrase(context.characters)
    emotion = chapter.emotion if chapter else _emotion_for_clip(clip_index, context.mood)
    chapter_role = chapter_display_label(chapter.chapter_role) if chapter else f"Chapter {clip_index}"
    story_objective = chapter.story_objective if chapter else beat
    visual_progression = chapter.visual_progression if chapter else ""
    dialogue_goal = chapter.dialogue_goal if chapter else "Advance the scene through in-scene speech and reaction"
    conflict_level = chapter.conflict_level if chapter else clip_index

    directives_summary = _build_native_audio_block(directives)

    prompt, authorship = compose_story_first_frame_prompt_primary(
        topic=context.topic,
        cast=cast,
        environment=context.environment,
        beat=beat,
        emotion=emotion,
        chapter_role=chapter_role,
        story_objective=story_objective,
        visual_progression=visual_progression,
        dialogue=dialogue,
        dialogue_goal=dialogue_goal,
        clip_index=clip_index,
        total_clips=total_clips,
        prior_bridge_hint=prior_bridge_hint if clip_index > 1 else "",
        bridge_hint=bridge_hint,
        conflict_level=conflict_level,
        mood=context.mood,
        style=context.style,
        camera_direction=chapter.camera_style if chapter else camera_direction,
        continuity_anchor=continuity_anchor,
        directives_summary=directives_summary,
        character_continuity=character_continuity,
        environment_continuity=environment_continuity,
        target_platform=platform,
        platform=platform,
        genre=genre,
        youtube_genre=youtube_genre,
        instagram_genre=instagram_genre,
        tiktok_genre=tiktok_genre,
    )
    return prompt, authorship


def _build_clip_plan(
    *,
    context: Any,
    beat: str,
    clip_index: int,
    total_clips: int,
    prior_bridge_hint: str,
    bridge_hint: str,
    next_beat: str,
    chapter: StoryChapterClip | None = None,
    platform: str = "",
    youtube_genre: str = "",
    instagram_genre: str = "",
    tiktok_genre: str = "",
    genre: str = "",
) -> KlingFrameToVideoClipPlan:
    emotion = chapter.emotion if chapter else _emotion_for_clip(clip_index, context.mood)
    cast = _character_phrase(context.characters)
    dialogue_lines = _extract_dialogue(None, context.characters)
    dialogue = dialogue_lines[clip_index - 1] if clip_index - 1 < len(dialogue_lines) else ""
    if not dialogue and dialogue_lines:
        dialogue = dialogue_lines[min(clip_index, len(dialogue_lines)) - 1]

    directives = NativeAudioDirectives(
        dialogue_lines=[dialogue] if dialogue else [],
        ambience=list(context.ambience),
        foley=list(context.foley),
        voice_acting="natural in-scene voices, breathing, no external narration",
    )

    character_continuity = _clean(
        f"Same {cast} with consistent appearance, scale, costume, and emotional through-line across clips"
    )
    environment_continuity = _clean(
        f"Same {context.environment}; preserve weather, lighting direction, and spatial layout"
    )
    camera = chapter.camera_style if chapter else DEFAULT_CAMERA_BY_CLIP[min(clip_index - 1, len(DEFAULT_CAMERA_BY_CLIP) - 1)]
    continuity = _continuity_anchor(
        characters=context.characters,
        environment=context.environment,
        bridge_hint=bridge_hint,
        emotion=emotion,
    )
    next_hint = ""
    if clip_index < total_clips:
        next_hint = _next_clip_reference_hint(
            bridge_hint=bridge_hint,
            characters=context.characters,
            next_beat=next_beat,
        )

    prompt, prompt_authorship = _compose_frame_prompt(
        context=context,
        beat=beat,
        clip_index=clip_index,
        total_clips=total_clips,
        prior_bridge_hint=prior_bridge_hint,
        bridge_hint=bridge_hint,
        camera_direction=camera,
        character_continuity=character_continuity,
        environment_continuity=environment_continuity,
        dialogue=dialogue,
        directives=directives,
        continuity_anchor=continuity,
        next_hint=next_hint,
        chapter=chapter,
        platform=platform,
        youtube_genre=youtube_genre,
        instagram_genre=instagram_genre,
        tiktok_genre=tiktok_genre,
        genre=genre,
    )

    chapter_progression = chapter.to_dict() if chapter else {}
    if prompt_authorship:
        chapter_progression = {**chapter_progression, "prompt_authorship": prompt_authorship}

    is_first = clip_index <= 1
    is_last = clip_index >= total_clips
    end_source = END_FRAME_NONE if is_last else END_FRAME_GENERATED_TARGET

    return KlingFrameToVideoClipPlan(
        clip_index=clip_index,
        duration_seconds=15,
        first_frame_source=FIRST_FRAME_PROMPT_ONLY if is_first else FIRST_FRAME_PRIOR_CLIP,
        end_frame_source=end_source,
        prompt=prompt,
        character_continuity=character_continuity,
        environment_continuity=environment_continuity,
        dialogue=dialogue,
        native_audio_directives=directives,
        camera_direction=camera,
        continuity_anchor=continuity,
        next_clip_reference_hint=next_hint,
        prior_clip_index=None if is_first else clip_index - 1,
        chapter_progression=chapter_progression,
    )


def plan_kling_frame_to_video_content(
    *,
    topic: str = "",
    story_package: dict[str, Any] | None = None,
    story_summary: str = "",
    platform: str = "",
    planned_duration_seconds: int = 30,
    clip_count: int | None = None,
    mood: str = "",
    style: str = "",
    characters: list[str] | None = None,
    environment: str = "",
    frame_mode_available: bool = True,
    explicit_mode: str = "",
    youtube_genre: str = "",
    instagram_genre: str = "",
    tiktok_genre: str = "",
    genre: str = "",
) -> KlingFrameToVideoPlan:
    """Convert story inputs into a Kling Frame-to-Video plan with rich per-clip prompts."""
    payload = KlingContentPlannerInput(
        topic=topic,
        story_package=story_package,
        story_summary=story_summary,
        platform=platform,
        planned_duration_seconds=planned_duration_seconds,
        clip_count=clip_count,
        mood=mood,
        style=style,
        characters=list(characters or []),
        environment=environment,
    )
    context = _resolve_story_context(payload)
    planned, resolved_clip_count, warnings = normalize_kling_frame_story_duration(payload.planned_duration_seconds)
    if payload.clip_count is not None and int(payload.clip_count) > 0:
        resolved_clip_count = int(payload.clip_count)

    generation_mode = select_kling_generation_mode(
        topic=context.topic,
        genre=context.genre,
        mood=context.mood,
        has_dialogue=bool(context.dialogue_lines),
        frame_mode_available=frame_mode_available,
        explicit_mode=explicit_mode,
    )

    bridge_hints = [
        "glowing path deeper into the scene",
        "hidden shelter entrance ahead",
        "warm light spilling from a safe corridor",
        "quiet clearing where the journey can rest",
    ]

    progression = build_story_progression_plan(
        planned_duration_seconds=planned,
        clip_count=resolved_clip_count,
        topic=context.topic,
        story_beats=list(context.beats[:resolved_clip_count]),
        mood=context.mood,
    )

    clips: list[KlingFrameToVideoClipPlan] = []
    prior_bridge_hint = ""
    for index in range(1, resolved_clip_count + 1):
        beat = context.beats[index - 1]
        bridge_hint = bridge_hints[min(index - 1, len(bridge_hints) - 1)]
        next_beat = context.beats[index] if index < resolved_clip_count else ""
        chapter = progression.chapters[index - 1] if index - 1 < len(progression.chapters) else None
        if index > 1:
            prior_bridge_hint = bridge_hints[min(index - 2, len(bridge_hints) - 1)]
        clips.append(
            _build_clip_plan(
                context=context,
                beat=beat,
                clip_index=index,
                total_clips=resolved_clip_count,
                prior_bridge_hint=prior_bridge_hint,
                bridge_hint=bridge_hint,
                next_beat=next_beat,
                chapter=chapter,
                platform=platform,
                youtube_genre=youtube_genre,
                instagram_genre=instagram_genre,
                tiktok_genre=tiktok_genre,
                genre=genre,
            )
        )

    return KlingFrameToVideoPlan(
        requested_duration_seconds=int(payload.planned_duration_seconds),
        planned_duration_seconds=planned,
        clip_count=resolved_clip_count,
        clips=clips,
        topic=context.topic,
        platform=_clean(platform),
        provider=KLING_PROVIDER_ID,
        audio_strategy=KLING_AUDIO_STRATEGY,
        generation_mode=generation_mode,
        fallback_mode=KLING_MULTISHOT_MODE,
        duration_warnings=warnings,
        story_progression=progression.to_dict(),
    )


def build_kling_frame_clip_prompts_preview(plan: KlingFrameToVideoPlan) -> list[dict[str, Any]]:
    from content_brain.story.story_first_prompt_engine import audit_story_first_prompt

    previews: list[dict[str, Any]] = []
    for clip in plan.clips:
        audit = audit_story_first_prompt(clip.prompt).to_dict()
        authorship = (clip.chapter_progression or {}).get("prompt_authorship") or {}
        previews.append(
            {
                "clip_index": clip.clip_index,
                "duration_seconds": clip.duration_seconds,
                "prompt_chars": len(clip.prompt),
                "prompt": clip.prompt,
                "first_frame_source": clip.first_frame_source,
                "end_frame_source": clip.end_frame_source,
                "character_continuity": clip.character_continuity,
                "environment_continuity": clip.environment_continuity,
                "dialogue": clip.dialogue,
                "camera_direction": clip.camera_direction,
                "continuity_anchor": clip.continuity_anchor,
                "next_clip_reference_hint": clip.next_clip_reference_hint,
                "chapter_progression": clip.chapter_progression,
                "prompt_authorship": authorship,
                "story_first_audit": audit,
            }
        )
    return previews


def validate_kling_frame_content_plan(plan: KlingFrameToVideoPlan) -> tuple[bool, list[str]]:
    ok, errors = validate_kling_frame_to_video_plan(plan)
    if not ok:
        return ok, errors

    from content_brain.story.story_first_prompt_engine import (
        STORY_FIRST_PROMPT_HARD_MIN,
        STORY_FIRST_PROMPT_MIN_CHARS,
        validate_kling_frame_plan_story_first,
    )

    story_ok, story_errors, _audits = validate_kling_frame_plan_story_first(plan)
    errors.extend(story_errors)

    for clip in plan.clips:
        label = f"clip {clip.clip_index}"
        if _contains_forbidden(clip.prompt):
            errors.append(f"{label}: forbidden external audio token in prompt")
        if clip.clip_index > 1 and "previous" not in clip.prompt.lower() and "resumes" not in clip.prompt.lower():
            errors.append(f"{label}: prompt must include prior-clip continuity language")
        story_part = clip.prompt.split("--- Technical execution ---", 1)[0] if "--- Technical execution ---" in clip.prompt else clip.prompt
        from content_brain.story.story_first_prompt_engine import validate_cinematic_story_body

        meta_ok, meta_errors = validate_cinematic_story_body(story_part)
        if not meta_ok:
            errors.extend(f"{label}: {err}" for err in meta_errors)
        if len(clip.prompt) < STORY_FIRST_PROMPT_HARD_MIN:
            errors.append(f"{label}: prompt below hard minimum {STORY_FIRST_PROMPT_HARD_MIN} chars")
        if len(clip.prompt) < STORY_FIRST_PROMPT_MIN_CHARS:
            errors.append(f"{label}: prompt below story-first minimum {STORY_FIRST_PROMPT_MIN_CHARS} chars")

    return story_ok and not errors, errors


__all__ = [
    "PLANNER_VERSION",
    "build_kling_frame_clip_prompts_preview",
    "plan_kling_frame_to_video_content",
    "validate_kling_frame_content_plan",
]
