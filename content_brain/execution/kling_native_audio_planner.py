"""Kling Native Audio Content Planner — topic/story → 2-shot continuity clip plans (P3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.kling_multishot_config import (
    MULTISHOT_STRATEGY,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_native_audio_models import (
    KLING_AUDIO_STRATEGY,
    KLING_PROVIDER_ID,
    KLING_SHOT_PROMPT_MAX_CHARS,
    KlingClipPlan,
    KlingNativeAudioPlan,
    KlingShotPlan,
    NativeAudioDirectives,
    SHOT_ROLE_MAIN_ACTION,
    SHOT_ROLE_TRANSITION_BRIDGE,
    build_clip_plan_skeleton,
    normalize_kling_duration,
    validate_kling_native_audio_plan,
)

PLANNER_VERSION = "kling_native_audio_planner_v1"

FORBIDDEN_PROMPT_TOKENS: tuple[str, ...] = (
    "elevenlabs",
    "eleven labs",
    "external music",
    "background music track",
    "music track overlay",
    "voiceover narrator",
    "ai dub",
    "tts voice",
)

NATIVE_AUDIO_CUE_TOKENS: tuple[str, ...] = (
    "breathing",
    "whisper",
    "growl",
    "footsteps",
    "thunder",
    "ambience",
    "ambient",
    "wind",
    "dialogue",
    "voice",
    "native cinematic audio",
    "forest ambience",
    "leaves",
    "softly",
    "rolls in the distance",
)

BEAT_KEYS_BY_CLIP_COUNT: dict[int, tuple[str, ...]] = {
    1: ("setup",),
    2: ("setup", "escalation"),
    3: ("setup", "conflict", "discovery"),
    4: ("hook", "conflict", "discovery", "resolution"),
}

DEFAULT_BRIDGE_HINTS: tuple[str, ...] = (
    "glowing path deeper in the forest",
    "hidden cave entrance ahead",
    "warm light spilling from a stone chamber",
    "quiet clearing where the journey can rest",
)

DEFAULT_EMOTIONS: tuple[str, ...] = (
    "tender wonder",
    "rising tension",
    "fragile hope",
    "earned trust",
)


@dataclass
class KlingContentPlannerInput:
    topic: str = ""
    story_package: dict[str, Any] | None = None
    story_summary: str = ""
    platform: str = ""
    planned_duration_seconds: int = 30
    clip_count: int | None = None
    mood: str = ""
    style: str = ""
    characters: list[str] = field(default_factory=list)
    environment: str = ""


@dataclass
class StoryContext:
    topic: str
    summary: str
    genre: str
    mood: str
    style: str
    environment: str
    characters: list[str]
    beats: list[str]
    dialogue_lines: list[str]
    ambience: list[str]
    foley: list[str]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _contains_forbidden(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in FORBIDDEN_PROMPT_TOKENS)


def _has_native_audio_cues(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in NATIVE_AUDIO_CUE_TOKENS)


def _compact_audio_suffix(directives: NativeAudioDirectives | None = None) -> str:
    parts = ["soft breathing", "forest ambience", "natural voices", "native cinematic audio"]
    if directives:
        if directives.foley:
            parts.insert(0, directives.foley[0])
        if directives.ambience:
            parts.insert(1, directives.ambience[0])
    return ", ".join(dict.fromkeys(_clean(part) for part in parts if _clean(part)))


def _truncate_prompt(
    text: str,
    *,
    max_chars: int = KLING_SHOT_PROMPT_MAX_CHARS,
    audio_suffix: str = "",
) -> str:
    normalized = _clean(text)
    suffix = _clean(audio_suffix)
    if suffix and "native cinematic audio" not in normalized.lower():
        normalized = f"{normalized}. {suffix}".strip()

    if len(normalized) <= max_chars:
        return normalized

    reserved = f". {suffix}" if suffix else ""
    room = max_chars - len(reserved)
    if room <= 0:
        return suffix[:max_chars].rsplit(" ", 1)[0].strip()

    body = normalized[:room].rsplit(" ", 1)[0].rstrip(".,;:")
    if suffix:
        return f"{body}.{reserved}".strip()
    return body.strip()


def _extract_characters(payload: dict[str, Any] | None, explicit: list[str] | None, topic: str) -> list[str]:
    if explicit:
        return [_clean(name) for name in explicit if _clean(name)]

    names: list[str] = []
    if payload:
        for profile in list(payload.get("character_profiles") or []):
            if isinstance(profile, dict):
                name = _clean(profile.get("name") or "")
                if name:
                    names.append(name)

    if not names:
        lowered = topic.lower()
        if "boy" in lowered and "dragon" in lowered:
            names = ["young boy", "baby dragon"]
        elif "boy" in lowered:
            names = ["young boy"]
        elif "dragon" in lowered:
            names = ["dragon"]

    return names


def _extract_environment(payload: dict[str, Any] | None, explicit: str, topic: str) -> str:
    if explicit:
        return _clean(explicit)

    if payload:
        env_plan = dict(payload.get("environment_plan") or {})
        for key in ("primary_setting", "setting", "location", "environment"):
            value = _clean(env_plan.get(key) or "")
            if value:
                return value
        locations = list(env_plan.get("locations") or [])
        if locations:
            first = locations[0]
            if isinstance(first, dict):
                return _clean(first.get("name") or first.get("description") or "")
            return _clean(first)

    lowered = topic.lower()
    if any(word in lowered for word in ("forest", "dragon", "fantasy")):
        return "twisted fantasy forest with mossy roots and drifting mist"
    if "cave" in lowered:
        return "shadowed cave corridor with damp stone and echoing air"
    return "cinematic natural environment"


def _extract_beats(payload: dict[str, Any] | None, summary: str, topic: str, clip_count: int) -> list[str]:
    progression: list[str] = []
    if payload:
        blueprint = dict(payload.get("story_blueprint") or {})
        progression = [_clean(item) for item in list(blueprint.get("scene_progression") or []) if _clean(item)]
        if not progression:
            for key in BEAT_KEYS_BY_CLIP_COUNT.get(clip_count, BEAT_KEYS_BY_CLIP_COUNT[4]):
                value = _clean(blueprint.get(key) or "")
                if value:
                    progression.append(value)

    if not progression and summary:
        parts = [part.strip() for part in re.split(r"[.;]\s+", summary) if part.strip()]
        progression = parts[:clip_count]

    if not progression:
        progression = _default_beats(topic=topic, clip_count=clip_count)

    if len(progression) < clip_count:
        defaults = _default_beats(topic=topic, clip_count=clip_count)
        progression.extend(defaults[len(progression) : clip_count])

    return progression[:clip_count]


def _default_beats(*, topic: str, clip_count: int) -> list[str]:
    lowered = topic.lower()
    if "boy" in lowered and "dragon" in lowered:
        catalog = [
            "A young boy kneels beside an injured baby dragon hidden under twisted forest roots",
            "The boy gently covers the baby dragon and follows a glowing path toward a cave entrance",
            "Inside the damp cave, warm light reveals a safe nest where trust begins to grow",
            "The boy and baby dragon rest together as moonlight filters through the trees, bonded and calm",
        ]
        return catalog[:clip_count]

    generic = [
        f"Main story action begins for: {topic}",
        "Tension rises as characters move toward the next story turn",
        "A discovery shifts emotion and momentum in the scene",
        "The arc resolves with a visual hold that completes the story beat",
    ]
    return generic[:clip_count]


def _extract_dialogue(payload: dict[str, Any] | None, characters: list[str]) -> list[str]:
    lines: list[str] = []
    if not payload:
        if "boy" in " ".join(characters).lower():
            lines.append("Don't worry... I won't hurt you.")
        return lines

    dialogue_plan = dict(payload.get("dialogue_plan") or {})
    for entry in list(dialogue_plan.get("lines") or dialogue_plan.get("dialogue_lines") or []):
        if isinstance(entry, dict):
            text = _clean(entry.get("text") or entry.get("line") or "")
            if text:
                lines.append(text)
        elif entry:
            lines.append(_clean(entry))
    return lines[:4]


def _extract_audio_cues(payload: dict[str, Any] | None, environment: str) -> tuple[list[str], list[str]]:
    ambience = ["forest ambience", "distant wind"]
    foley = ["soft breathing", "leaves moving"]

    if payload:
        env_plan = dict(payload.get("environment_plan") or {})
        for item in list(env_plan.get("ambience") or env_plan.get("ambient_layers") or []):
            text = _clean(item if isinstance(item, str) else (item.get("label") if isinstance(item, dict) else ""))
            if text:
                ambience.append(text)
        for item in list(env_plan.get("foley") or env_plan.get("sound_effects") or []):
            text = _clean(item if isinstance(item, str) else (item.get("label") if isinstance(item, dict) else ""))
            if text:
                foley.append(text)

    if "cave" in environment.lower():
        ambience.append("cave echo")
        foley.append("dripping water")
    if "forest" in environment.lower():
        ambience.append("rustling canopy")
    return ambience[:4], foley[:4]


def _resolve_story_context(payload: KlingContentPlannerInput) -> StoryContext:
    package = dict(payload.story_package or {})
    topic = _clean(payload.topic or package.get("topic") or "")
    summary = _clean(payload.story_summary)
    if not summary:
        blueprint = dict(package.get("story_blueprint") or {})
        summary = _clean(blueprint.get("hook") or blueprint.get("setup") or topic)

    planned, clip_count, _ = normalize_kling_duration(payload.planned_duration_seconds)
    if payload.clip_count is not None and int(payload.clip_count) > 0:
        clip_count = int(payload.clip_count)

    characters = _extract_characters(package or None, payload.characters or None, topic)
    environment = _extract_environment(package or None, payload.environment, topic)
    beats = _extract_beats(package or None, summary, topic, clip_count)
    dialogue_lines = _extract_dialogue(package or None, characters)
    ambience, foley = _extract_audio_cues(package or None, environment)

    genre = _clean(dict(package.get("story_blueprint") or {}).get("genre") or "")
    mood = _clean(payload.mood)
    if not mood:
        mood = _clean(dict(package.get("emotion_plan") or {}).get("dominant_emotion") or "emotional")
    style = _clean(payload.style or payload.mood or genre or "cinematic fantasy")

    return StoryContext(
        topic=topic,
        summary=summary,
        genre=genre or "fantasy",
        mood=mood,
        style=style,
        environment=environment,
        characters=characters,
        beats=beats,
        dialogue_lines=dialogue_lines,
        ambience=ambience,
        foley=foley,
    )


def _character_phrase(characters: list[str]) -> str:
    if not characters:
        return "The characters"
    if len(characters) == 1:
        return characters[0].capitalize()
    if len(characters) == 2:
        return f"{characters[0]} and {characters[1]}"
    return ", ".join(characters[:-1]) + f", and {characters[-1]}"


def _emotion_for_clip(index: int, mood: str) -> str:
    if mood:
        return mood
    return DEFAULT_EMOTIONS[min(index - 1, len(DEFAULT_EMOTIONS) - 1)]


def _build_directives(
    *,
    dialogue_lines: list[str],
    ambience: list[str],
    foley: list[str],
    clip_index: int,
    shot_index: int,
) -> NativeAudioDirectives:
    line = dialogue_lines[clip_index - 1] if clip_index - 1 < len(dialogue_lines) else ""
    if shot_index == 2 and not line and dialogue_lines:
        line = dialogue_lines[min(clip_index, len(dialogue_lines)) - 1]

    voice = "natural in-scene voices, no external narration"
    if line:
        voice = f'character speaks naturally: "{line}"'

    return NativeAudioDirectives(
        dialogue_lines=[line] if line else [],
        ambience=list(ambience),
        foley=list(foley),
        voice_acting=voice,
    )


def _continuity_anchor(
    *,
    characters: list[str],
    environment: str,
    bridge_hint: str,
    emotion: str,
) -> str:
    cast = _character_phrase(characters)
    return _clean(
        f"{cast} held at the edge of {bridge_hint} in {environment}, {emotion}, final frame ready for handoff"
    )


def _next_clip_reference_hint(*, bridge_hint: str, characters: list[str], next_beat: str) -> str:
    cast = _character_phrase(characters)
    return _clean(f"Same {cast} continue toward {bridge_hint} to begin: {next_beat}")


def _compose_shot_1_prompt(
    *,
    context: StoryContext,
    beat: str,
    clip_index: int,
    total_clips: int,
    prior_bridge_hint: str,
    directives: NativeAudioDirectives,
) -> str:
    cast = _character_phrase(context.characters)
    emotion = _emotion_for_clip(clip_index, context.mood)
    style = f"Cinematic {context.style}, emotional fantasy framing"

    if clip_index > 1 and prior_bridge_hint:
        lead = (
            f"Continuing from the previous bridge, same {cast} move toward {prior_bridge_hint}. {beat}"
        )
    else:
        lead = beat

    prompt = (
        f"{lead}. {cast} express {emotion} within {context.environment}. "
        f"{style}."
    )
    suffix_bits = [_compact_audio_suffix(directives)]
    if directives.dialogue_lines:
        suffix_bits.insert(0, directives.dialogue_lines[0])
    return _truncate_prompt(prompt, audio_suffix=". ".join(_clean(x) for x in suffix_bits if _clean(x)))


def _compose_shot_2_prompt(
    *,
    context: StoryContext,
    beat: str,
    clip_index: int,
    total_clips: int,
    bridge_hint: str,
    directives: NativeAudioDirectives,
) -> str:
    cast = _character_phrase(context.characters)
    emotion = _emotion_for_clip(clip_index, context.mood)
    style = f"Cinematic {context.style}, emotional fantasy framing"

    if clip_index >= total_clips:
        bridge_action = (
            f"{cast} settle into a calm final pose after {beat.lower()}, holding emotional closure"
        )
        tail = "Hold final frame for story completion"
    else:
        bridge_action = (
            f"{cast} gently transition toward {bridge_hint}, setting up the next scene after {beat.lower()}"
        )
        tail = f"Hold final frame facing {bridge_hint}"

    prompt = f"{bridge_action}. {tail}. {style}."
    suffix_bits = [_compact_audio_suffix(directives)]
    if directives.dialogue_lines:
        suffix_bits.insert(0, directives.dialogue_lines[0])
    suffix_bits.append(f"{emotion}, native cinematic audio")
    return _truncate_prompt(prompt, audio_suffix=". ".join(_clean(x) for x in suffix_bits if _clean(x)))


def _fill_clip_plan(
    *,
    skeleton: KlingClipPlan,
    context: StoryContext,
    beat: str,
    clip_index: int,
    total_clips: int,
    prior_bridge_hint: str,
    bridge_hint: str,
    next_beat: str,
) -> KlingClipPlan:
    emotion = _emotion_for_clip(clip_index, context.mood)
    shot_1_directives = _build_directives(
        dialogue_lines=context.dialogue_lines,
        ambience=context.ambience,
        foley=context.foley,
        clip_index=clip_index,
        shot_index=1,
    )
    shot_2_directives = _build_directives(
        dialogue_lines=context.dialogue_lines,
        ambience=context.ambience,
        foley=[*context.foley, "soft breathing"],
        clip_index=clip_index,
        shot_index=2,
    )

    shot_1_prompt = _compose_shot_1_prompt(
        context=context,
        beat=beat,
        clip_index=clip_index,
        total_clips=total_clips,
        prior_bridge_hint=prior_bridge_hint,
        directives=shot_1_directives,
    )
    shot_2_prompt = _compose_shot_2_prompt(
        context=context,
        beat=beat,
        clip_index=clip_index,
        total_clips=total_clips,
        bridge_hint=bridge_hint,
        directives=shot_2_directives,
    )

    continuity = _continuity_anchor(
        characters=context.characters,
        environment=context.environment,
        bridge_hint=bridge_hint,
        emotion=emotion,
    )
    next_hint = ""
    prior_reference = ""
    if clip_index < total_clips:
        next_hint = _next_clip_reference_hint(
            bridge_hint=bridge_hint,
            characters=context.characters,
            next_beat=next_beat,
        )
    if clip_index > 1:
        prior_reference = _next_clip_reference_hint(
            bridge_hint=prior_bridge_hint,
            characters=context.characters,
            next_beat=beat,
        )

    skeleton.shot_1 = KlingShotPlan(
        shot_index=1,
        duration_seconds=SHOT_1_DURATION_SECONDS,
        role=SHOT_ROLE_MAIN_ACTION,
        prompt=shot_1_prompt,
        native_audio_directives=shot_1_directives,
        continuity_anchor="",
        emotion=emotion,
        environment=context.environment,
        characters_present=list(context.characters),
    )
    skeleton.shot_2 = KlingShotPlan(
        shot_index=2,
        duration_seconds=SHOT_2_DURATION_SECONDS,
        role=SHOT_ROLE_TRANSITION_BRIDGE,
        prompt=shot_2_prompt,
        native_audio_directives=shot_2_directives,
        continuity_anchor=continuity,
        emotion=emotion,
        environment=context.environment,
        characters_present=list(context.characters),
    )
    skeleton.next_clip_reference_hint = next_hint
    skeleton.prior_clip_reference = prior_reference
    skeleton.continuity_bridge = continuity
    skeleton.expected_native_audio = "dialogue, ambience, foley, breathing — native in-video audio only"
    return skeleton


def plan_kling_native_audio_content(
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
) -> KlingNativeAudioPlan:
    """Convert topic/story inputs into a populated ``KlingNativeAudioPlan``."""
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
    planned, resolved_clip_count, warnings = normalize_kling_duration(payload.planned_duration_seconds)
    if payload.clip_count is not None and int(payload.clip_count) > 0:
        resolved_clip_count = int(payload.clip_count)

    clips: list[KlingClipPlan] = []
    prior_bridge_hint = ""
    for index in range(1, resolved_clip_count + 1):
        beat = context.beats[index - 1]
        bridge_hint = DEFAULT_BRIDGE_HINTS[min(index - 1, len(DEFAULT_BRIDGE_HINTS) - 1)]
        next_beat = context.beats[index] if index < resolved_clip_count else ""
        skeleton = build_clip_plan_skeleton(clip_index=index, total_clips=resolved_clip_count)
        if index > 1:
            prior_bridge_hint = DEFAULT_BRIDGE_HINTS[min(index - 2, len(DEFAULT_BRIDGE_HINTS) - 1)]
        clip = _fill_clip_plan(
            skeleton=skeleton,
            context=context,
            beat=beat,
            clip_index=index,
            total_clips=resolved_clip_count,
            prior_bridge_hint=prior_bridge_hint,
            bridge_hint=bridge_hint,
            next_beat=next_beat,
        )
        clips.append(clip)

    return KlingNativeAudioPlan(
        requested_duration_seconds=int(payload.planned_duration_seconds),
        planned_duration_seconds=planned,
        clip_count=resolved_clip_count,
        clips=clips,
        topic=context.topic,
        platform=_clean(platform),
        provider=KLING_PROVIDER_ID,
        strategy=MULTISHOT_STRATEGY,
        audio_strategy=KLING_AUDIO_STRATEGY,
        native_audio_required=True,
        use_elevenlabs=False,
        use_external_music=False,
        subtitle_required=True,
        duration_warnings=warnings,
    )


def plan_kling_from_audio_route(
    *,
    topic: str,
    audio_route: Any,
    story_package: dict[str, Any] | None = None,
    story_summary: str = "",
    platform: str = "",
    mood: str = "",
    style: str = "",
    characters: list[str] | None = None,
    environment: str = "",
) -> KlingNativeAudioPlan:
    """Build a content plan using duration metadata from the audio strategy router."""
    if hasattr(audio_route, "kling_native_audio"):
        kling_meta = getattr(audio_route, "kling_native_audio") or {}
    elif isinstance(audio_route, dict):
        kling_meta = dict(audio_route.get("kling_native_audio") or {})
    else:
        kling_meta = {}

    planned_duration = int(
        kling_meta.get("planned_duration_seconds")
        or kling_meta.get("requested_duration_seconds")
        or 30
    )
    clip_total = int(kling_meta.get("clip_count") or 0) or None
    return plan_kling_native_audio_content(
        topic=topic,
        story_package=story_package,
        story_summary=story_summary,
        platform=platform,
        planned_duration_seconds=planned_duration,
        clip_count=clip_total,
        mood=mood,
        style=style,
        characters=characters,
        environment=environment,
    )


def build_kling_clip_prompts_preview(plan: KlingNativeAudioPlan) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for clip in plan.clips:
        prompts.append(
            {
                "clip_index": clip.clip_index,
                "shot_1_duration_seconds": clip.shot_1.duration_seconds,
                "shot_1_prompt": clip.shot_1.prompt,
                "shot_2_duration_seconds": clip.shot_2.duration_seconds,
                "shot_2_prompt": clip.shot_2.prompt,
                "continuity_anchor": clip.shot_2.continuity_anchor,
                "next_clip_reference_hint": clip.next_clip_reference_hint,
                "prior_clip_reference": clip.prior_clip_reference,
            }
        )
    return prompts


def _clip_prompt_length_warnings(clip: Any) -> list[str]:
    """Collect prompt-length warnings for multishot or frame-to-video clip schemas."""
    warnings: list[str] = []
    if hasattr(clip, "shot_1") and hasattr(clip, "shot_2"):
        for shot_name, shot in (("shot_1", clip.shot_1), ("shot_2", clip.shot_2)):
            prompt = str(getattr(shot, "prompt", "") or "")
            if len(prompt) > KLING_SHOT_PROMPT_MAX_CHARS:
                warnings.append(
                    f"prompt_too_long:clip_{clip.clip_index}_{shot_name}={len(prompt)}"
                )
        return warnings

    if hasattr(clip, "prompt"):
        from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_PROMPT_MAX_CHARS

        prompt = str(clip.prompt or "")
        if len(prompt) > KLING_FRAME_PROMPT_MAX_CHARS:
            warnings.append(
                f"prompt_too_long:clip_{clip.clip_index}_frame={len(prompt)}"
            )
        return warnings

    warnings.append(f"unknown_clip_schema:clip_{getattr(clip, 'clip_index', '?')}")
    return warnings


def collect_kling_preflight_warnings(
    *,
    plan: KlingNativeAudioPlan | Any,
    authoritative_topic: str,
    story_package: dict[str, Any] | None = None,
    story_summary: str = "",
    require_story_package: bool = False,
) -> list[str]:
    warnings = list(getattr(plan, "duration_warnings", ()) or [])
    if require_story_package and not story_package:
        warnings.append("missing_story_field:story_package")
    if require_story_package and isinstance(story_package, dict) and not story_package:
        warnings.append("missing_story_field:story_package_empty")
    if not _clean(authoritative_topic):
        warnings.append("missing_story_field:topic")
    for clip in plan.clips:
        warnings.extend(_clip_prompt_length_warnings(clip))
    return warnings


def plan_kling_frame_from_audio_route(
    *,
    topic: str,
    audio_route: Any,
    story_package: dict[str, Any] | None = None,
    story_summary: str = "",
    platform: str = "",
    mood: str = "",
    style: str = "",
    characters: list[str] | None = None,
    environment: str = "",
) -> Any:
    """Build Frame-to-Video plan (primary production path) from audio router metadata."""
    from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE
    from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content

    if hasattr(audio_route, "kling_native_audio"):
        kling_meta = getattr(audio_route, "kling_native_audio") or {}
    elif isinstance(audio_route, dict):
        kling_meta = dict(audio_route.get("kling_native_audio") or {})
    else:
        kling_meta = {}

    planned_duration = int(
        kling_meta.get("planned_duration_seconds")
        or kling_meta.get("requested_duration_seconds")
        or 30
    )
    clip_total = int(kling_meta.get("clip_count") or 0) or None
    return plan_kling_frame_to_video_content(
        topic=topic,
        story_package=story_package,
        story_summary=story_summary,
        platform=platform,
        planned_duration_seconds=planned_duration,
        clip_count=clip_total,
        mood=mood,
        style=style,
        characters=characters,
        environment=environment,
        frame_mode_available=True,
        explicit_mode=KLING_FRAME_TO_VIDEO_MODE,
    )


def build_kling_frame_preflight_api_payload(
    *,
    plan: Any,
    kling_duration_plan: dict[str, Any],
) -> dict[str, Any]:
    from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE
    from content_brain.execution.kling_frame_to_video_planner import build_kling_frame_clip_prompts_preview

    return {
        "kling_frame_to_video_plan": plan.to_dict(),
        "kling_duration_plan": dict(kling_duration_plan),
        "kling_clip_count": plan.clip_count,
        "kling_shot_mode": KLING_FRAME_TO_VIDEO_MODE,
        "kling_clip_prompts": build_kling_frame_clip_prompts_preview(plan),
        "use_elevenlabs": False,
        "use_external_music": False,
        "native_audio_required": True,
        "subtitle_required": False,
        "primary_generation_mode": KLING_FRAME_TO_VIDEO_MODE,
        "continuity_method": "use_frame",
        "clip1_generation_mode": "text_to_video_prompt_only",
        "clip1_starter_frame_required": False,
        "story_progression": dict(getattr(plan, "story_progression", None) or {}),
        "story_progression_status": str(
            (getattr(plan, "story_progression", None) or {}).get("validation_status") or "PASS"
        ),
    }


def build_kling_preflight_api_payload(
    *,
    plan: KlingNativeAudioPlan,
    kling_duration_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kling_native_audio_plan": plan.to_dict(),
        "kling_duration_plan": dict(kling_duration_plan),
        "kling_clip_count": plan.clip_count,
        "kling_shot_mode": plan.strategy,
        "kling_clip_prompts": build_kling_clip_prompts_preview(plan),
        "use_elevenlabs": plan.use_elevenlabs,
        "use_external_music": plan.use_external_music,
        "native_audio_required": plan.native_audio_required,
        "subtitle_required": plan.subtitle_required,
    }


def validate_kling_content_plan(plan: KlingNativeAudioPlan) -> tuple[bool, list[str]]:
    """Validate structural + content rules for planner output."""
    ok, errors = validate_kling_native_audio_plan(plan)
    if not ok:
        return ok, errors

    for clip in plan.clips:
        for shot_name, shot in (("shot_1", clip.shot_1), ("shot_2", clip.shot_2)):
            label = f"clip {clip.clip_index} {shot_name}"
            if not _clean(shot.prompt):
                errors.append(f"{label}: prompt must be non-empty")
            if len(shot.prompt) > KLING_SHOT_PROMPT_MAX_CHARS:
                errors.append(f"{label}: prompt exceeds {KLING_SHOT_PROMPT_MAX_CHARS} chars")
            if _contains_forbidden(shot.prompt):
                errors.append(f"{label}: forbidden external audio token in prompt")
            if not _has_native_audio_cues(shot.prompt):
                errors.append(f"{label}: missing native audio cues")

        if clip.clip_index < plan.clip_count:
            if not _clean(clip.shot_2.continuity_anchor):
                errors.append(f"clip {clip.clip_index}: shot_2 continuity_anchor required")
            if not _clean(clip.next_clip_reference_hint):
                errors.append(f"clip {clip.clip_index}: next_clip_reference_hint required")

        if clip.clip_index > 1:
            prior = plan.clips[clip.clip_index - 2]
            hint = _clean(prior.next_clip_reference_hint or prior.shot_2.continuity_anchor)
            prompt = clip.shot_1.prompt.lower()
            if hint and "continuing from" not in prompt and "same " not in prompt:
                errors.append(f"clip {clip.clip_index}: shot_1 must reference prior bridge")

    return not errors, errors


__all__ = [
    "KlingContentPlannerInput",
    "PLANNER_VERSION",
    "StoryContext",
    "build_kling_clip_prompts_preview",
    "build_kling_frame_preflight_api_payload",
    "build_kling_preflight_api_payload",
    "collect_kling_preflight_warnings",
    "plan_kling_frame_from_audio_route",
    "plan_kling_from_audio_route",
    "plan_kling_native_audio_content",
    "validate_kling_content_plan",
]
