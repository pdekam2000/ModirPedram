"""Story-First prompt architecture for Kling Frame-to-Video (2500 char capacity)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

STORY_FIRST_VERSION = "story_first_prompt_engine_v1"

KLING_FRAME_PROMPT_MAX_CHARS = 2500
STORY_FIRST_PROMPT_HARD_MIN = 2000
STORY_FIRST_PROMPT_MIN_CHARS = 2300
STORY_FIRST_PROMPT_TARGET_MIN = 2400
STORY_FIRST_PROMPT_TARGET_MAX = 2500

STORY_FIRST_TARGET_STORY_RATIO = 0.80
STORY_FIRST_MAX_TECHNICAL_RATIO = 0.20
STORY_FIRST_GENERATION_FAIL_STORY_RATIO = 0.70

TECHNICAL_SECTION_MARKER = "--- Technical execution ---"

FORBIDDEN_STORY_METADATA_PHRASES: tuple[str, ...] = (
    "chapter role:",
    "story objective:",
    "dialogue goal:",
    "conflict level",
    "visual progression:",
    "narrative context:",
    "emotional temperature:",
    "the chapter opens",
    "dialogue goal for",
    "dialogue moment:",
    "character behavior stays specific",
    "environmental interaction is not decoration",
    "story progression requires",
    "conflict progression escalates",
    "resolution beat:",
    "opening beat is",
    "this chapter role",
    "native in-video audio carries the performance",
)

EMOTION_TOKENS: frozenset[str] = frozenset(
    {
        "afraid",
        "anxious",
        "breath",
        "breathing",
        "calm",
        "courage",
        "curious",
        "desperate",
        "determined",
        "emotion",
        "emotional",
        "fear",
        "fragile",
        "grief",
        "heart",
        "hope",
        "hopeful",
        "joy",
        "lonely",
        "love",
        "panic",
        "quiet",
        "relief",
        "sad",
        "scared",
        "shock",
        "silence",
        "soft",
        "sorrow",
        "surprise",
        "tender",
        "tension",
        "terrified",
        "trust",
        "urgency",
        "warm",
        "whisper",
        "wonder",
        "worry",
    }
)

SENSORY_TOKENS: frozenset[str] = frozenset(
    {
        "air",
        "ambient",
        "cold",
        "damp",
        "dark",
        "drizzle",
        "echo",
        "glow",
        "heat",
        "light",
        "mist",
        "murmur",
        "neon",
        "rain",
        "rumble",
        "rustle",
        "scent",
        "shadow",
        "smell",
        "sound",
        "steam",
        "thunder",
        "warmth",
        "wet",
        "wind",
    }
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"[a-zA-Z']+", text))


def _split_story_and_technical(prompt: str) -> tuple[str, str]:
    text = str(prompt or "")
    marker = TECHNICAL_SECTION_MARKER
    if marker in text:
        story, technical = text.split(marker, 1)
        return story.strip(), technical.strip()
    return text.strip(), ""


def _dialogue_density(prompt: str) -> float:
    words = max(_word_count(prompt), 1)
    quoted = re.findall(r'"([^"]+)"', prompt)
    dialogue_words = sum(_word_count(q) for q in quoted)
    return round(dialogue_words / words, 4)


def _emotion_density(prompt: str) -> float:
    words = max(_word_count(prompt), 1)
    lowered = prompt.lower()
    hits = sum(1 for token in EMOTION_TOKENS if token in lowered)
    return round(hits / words, 4)


@dataclass
class StoryFirstPromptAudit:
    story_percent: float
    technical_percent: float
    character_count: int
    dialogue_density: float
    emotion_density: float
    prompt_length: int
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STORY_FIRST_VERSION,
            "story_percent": self.story_percent,
            "technical_percent": self.technical_percent,
            "character_count": self.character_count,
            "dialogue_density": self.dialogue_density,
            "emotion_density": self.emotion_density,
            "prompt_length": self.prompt_length,
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def audit_story_first_prompt(prompt: str) -> StoryFirstPromptAudit:
    text = _clean(prompt)
    story_part, technical_part = _split_story_and_technical(text)
    total = max(len(text), 1)
    story_chars = len(story_part)
    technical_chars = len(technical_part) if technical_part else max(total - story_chars, 0)
    story_percent = round((story_chars / total) * 100, 2)
    technical_percent = round((technical_chars / total) * 100, 2)

    errors: list[str] = []
    warnings: list[str] = []

    if len(text) < STORY_FIRST_PROMPT_HARD_MIN:
        errors.append(f"prompt_length {len(text)} < hard minimum {STORY_FIRST_PROMPT_HARD_MIN}")
    if len(text) < STORY_FIRST_PROMPT_MIN_CHARS:
        warnings.append(f"prompt_length {len(text)} below recommended minimum {STORY_FIRST_PROMPT_MIN_CHARS}")
    if story_percent < STORY_FIRST_GENERATION_FAIL_STORY_RATIO * 100:
        errors.append(
            f"story_percent {story_percent} < generation floor {STORY_FIRST_GENERATION_FAIL_STORY_RATIO * 100:.0f}%"
        )
    if story_percent < STORY_FIRST_TARGET_STORY_RATIO * 100:
        warnings.append(f"story_percent {story_percent} below target {STORY_FIRST_TARGET_STORY_RATIO * 100:.0f}%")
    if technical_percent > STORY_FIRST_MAX_TECHNICAL_RATIO * 100:
        warnings.append(
            f"technical_percent {technical_percent} exceeds target max {STORY_FIRST_MAX_TECHNICAL_RATIO * 100:.0f}%"
        )

    return StoryFirstPromptAudit(
        story_percent=story_percent,
        technical_percent=technical_percent,
        character_count=len(text),
        dialogue_density=_dialogue_density(text),
        emotion_density=_emotion_density(text),
        prompt_length=len(text),
        ok=not errors,
        errors=errors,
        warnings=warnings,
    )


def validate_story_first_prompt_for_generation(prompt: str) -> tuple[bool, StoryFirstPromptAudit]:
    audit = audit_story_first_prompt(prompt)
    return audit.ok, audit


def _pad_story_paragraph(base: str, *, topic: str, index: int) -> str:
    """Expand a paragraph with additional narrative texture without metadata labels."""
    sensory = (
        f"The air carries layered texture around {topic}: distant motion, surface detail, and shifting light "
        f"that makes every small gesture readable. Micro-movements in the scene — breath, fabric, dust, and "
        f"reflected color — keep the moment alive rather than static."
    )
    stakes = (
        f"Each second raises the emotional cost of hesitation. What happens next must feel inevitable because "
        f"the characters have already committed — their choices are visible in posture, pace, and where their "
        f"attention locks."
    )
    variants = [sensory, stakes]
    return _clean(f"{base} {variants[index % len(variants)]}")


def find_forbidden_story_metadata(story_body: str) -> list[str]:
    lowered = str(story_body or "").lower()
    return [phrase for phrase in FORBIDDEN_STORY_METADATA_PHRASES if phrase in lowered]


def validate_cinematic_story_body(story_body: str) -> tuple[bool, list[str]]:
    hits = find_forbidden_story_metadata(story_body)
    if hits:
        return False, [f"forbidden metadata phrase: {phrase}" for phrase in hits]
    return True, []


def build_prompt_composition_trace(
    *,
    openai_system_prompt: str = "",
    openai_user_prompt: str = "",
    openai_raw_response: str = "",
    final_prompt: str = "",
) -> dict[str, Any]:
    """Forensic diff payload: request → raw response → final prompt."""
    story_final, technical_final = _split_story_and_technical(final_prompt)
    story_raw, technical_raw = _split_story_and_technical(_strip_fences(openai_raw_response))
    return {
        "openai_request": {
            "system_prompt": openai_system_prompt,
            "user_prompt": openai_user_prompt,
        },
        "openai_raw_response": openai_raw_response,
        "final_prompt": final_prompt,
        "diff_summary": {
            "raw_length": len(openai_raw_response or ""),
            "final_length": len(final_prompt or ""),
            "raw_story_length": len(story_raw),
            "final_story_length": len(story_final),
            "technical_footer_rebuilt": technical_raw.strip() != technical_final.strip(),
            "metadata_stripped_or_rewritten": bool(find_forbidden_story_metadata(story_raw))
            and not find_forbidden_story_metadata(story_final),
        },
    }


def _strip_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def _cinematic_length_booster(index: int) -> str:
    variants = (
        " A passerby flinches at a distant sound; steam hisses from a vent; wet fabric clings to skin; "
        "every micro-gesture — a swallowed breath, a tightened jaw, a hand that almost reaches out — "
        "keeps the moment alive and irreversible.",
        " Light shifts across faces as they move; footsteps splash in rhythm; metal groans somewhere above; "
        "the world keeps reacting to them instead of waiting politely for the next cut.",
        " Background motion never stops — signage flickers, rain streaks the lens, a door slams two blocks away — "
        "and the characters answer with real physical choices that raise the cost of hesitation.",
    )
    return variants[index % len(variants)]


def _build_story_paragraphs(
    *,
    topic: str,
    cast: str,
    environment: str,
    beat: str,
    emotion: str,
    chapter_role: str,
    story_objective: str,
    visual_progression: str,
    dialogue: str,
    dialogue_goal: str,
    clip_index: int,
    total_clips: int,
    prior_bridge_hint: str,
    bridge_hint: str,
    conflict_level: int,
    mood: str,
    style: str,
) -> list[str]:
    paragraphs: list[str] = []

    if clip_index > 1 and prior_bridge_hint:
        paragraphs.append(
            _clean(
                f"Without a cut, the chase resumes, continuing immediately from {prior_bridge_hint}. "
                f"{cast} burst out of the same frame they just left — same rain on the previous alley walls, "
                f"same practical light catching their faces, same {emotion} wired through their bodies. "
                f"They do not pause to explain; they run, stumble, recover, and keep moving while the world "
                f"continues to push back."
            )
        )
    else:
        paragraphs.append(
            _clean(
                f"Inside {environment}, {cast} are already in motion around {topic}. "
                f"We meet them mid-beat: {beat}. No title card, no narrator — only behavior. Where they look, what they protect, how their breath breaks, "
                f"and what they flinch from tells us everything before anyone speaks."
            )
        )

    paragraphs.append(
        _clean(
            f"{cast} touch the world constantly — testing footing on wet stone, brushing rain from their eyes, "
            f"adjusting grip on what matters, reacting to sounds that arrive a half-second before we see the source. "
            f"{visual_progression or 'The camera tracks their choices in close, readable detail'}. "
            f"Every prop and surface pushes the next decision instead of sitting pretty in the background."
        )
    )

    paragraphs.append(
        _clean(
            f"Tension climbs through action, not notes. {story_objective or beat}. "
            f"Pacing tightens as stakes rise — shorter reactions, sharper turns, choices that cannot be casually undone. "
            f"{cast} carry {emotion} in posture and pace under a {mood} {style} atmosphere."
        )
    )

    if dialogue:
        paragraphs.append(
            _clean(
                f'{cast} speak in-scene — "{dialogue}" — with breath caught in the throat and rain or wind '
                f"in the same native audio bed. The line lands because their bodies already showed the cost; "
                f"the words confirm it and force the scene into its next turn."
            )
        )
    else:
        paragraphs.append(
            _clean(
                f"Words are sparse but audible: a whispered vow, a broken syllable, an inhalation before speaking "
                f"that sells {emotion}. {dialogue_goal}. Nothing is explained by a narrator — only breath, "
                f"footsteps, and the environment answering every movement."
            )
        )

    paragraphs.append(
        _clean(
            f"The wider story remains {topic}, and this clip must advance it without repeating what we already saw. "
            f"Sensory detail stays dense — rain texture, distant echoes, shifting light, cold air on skin, "
            f"and subtle foley woven through the moment until the frame feels inhabited and urgent."
        )
    )

    if clip_index < total_clips:
        paragraphs.append(
            _clean(
                f"The pressure builds toward {bridge_hint}. By the exit frame, positions, lighting, and emotional "
                f"direction must hand off cleanly to what comes next — the last image should ask a question the "
                f"next clip answers immediately."
            )
        )
    else:
        paragraphs.append(
            _clean(
                f"Tension finally releases into closure without resetting the world. The last frame holds completion "
                f"for {topic} while the scene still breathes — rain, breath, and native sound keeping it alive."
            )
        )

    return paragraphs


def has_prior_clip_continuity_language(prompt: str) -> bool:
    """Match validate_kling_frame_content_plan: clip 2+ requires 'previous' or 'resumes'."""
    lowered = str(prompt or "").lower()
    return "previous" in lowered or "resumes" in lowered


def build_prior_clip_continuity_opener(
    *,
    prior_bridge_hint: str,
    cast: str,
    emotion: str,
) -> str:
    bridge = _clean(prior_bridge_hint) or "the prior clip ending frame"
    return _clean(
        f"Without a cut, the chase resumes, continuing immediately from {bridge}. "
        f"{cast} spill from the previous ending frame — same rain-slick surfaces, same practical light, "
        f"same {emotion} on their faces — and push forward before the world can catch up."
    )


def ensure_prior_clip_continuity_language(
    prompt: str,
    *,
    clip_index: int,
    prior_bridge_hint: str,
    cast: str,
    emotion: str,
    style: str = "",
    mood: str = "",
    camera_direction: str = "",
    continuity_anchor: str = "",
) -> str:
    """Inject canonical prior-clip handoff language when clip 2+ prompts omit planner-required markers."""
    if int(clip_index) <= 1:
        return _clean(prompt)
    if has_prior_clip_continuity_language(prompt):
        return _clean(prompt)

    story_part, technical_part = _split_story_and_technical(str(prompt or ""))
    if not technical_part:
        technical_part = _build_technical_footer(
            style=style or "cinematic",
            mood=mood or "dramatic",
            camera_direction=camera_direction or "motivated cinematic camera",
            continuity_anchor=continuity_anchor or "preserve character and environment",
            directives_summary="",
        )
    opener = build_prior_clip_continuity_opener(
        prior_bridge_hint=prior_bridge_hint,
        cast=cast,
        emotion=emotion,
    )
    story_body = _clean(f"{opener} {story_part}")
    return _fit_story_first_length(story_body, technical_part)


def _build_technical_footer(
    *,
    style: str,
    mood: str,
    camera_direction: str,
    continuity_anchor: str,
    directives_summary: str,
) -> str:
    return _clean(
        f"{TECHNICAL_SECTION_MARKER} "
        f"Visual style: cinematic {style}, {mood}. "
        f"Audio style: native in-scene only. "
        f"Camera style: {camera_direction}. "
        f"Continuity anchor: {continuity_anchor}."
    )


def _fit_story_first_length(story_body: str, technical_footer: str) -> str:
    separator = "\n\n"
    technical = technical_footer.strip()
    story = story_body.strip()

    def _assemble() -> str:
        return _clean(f"{story}{separator}{technical}")

    full = _assemble()
    if len(full) > KLING_FRAME_PROMPT_MAX_CHARS:
        overflow = len(full) - STORY_FIRST_PROMPT_TARGET_MAX
        if overflow > 0 and len(story) > overflow + 200:
            story = story[: len(story) - overflow].rsplit(" ", 1)[0].rstrip(".,;:") + "."
        full = _assemble()

    expand_index = 0
    while len(_assemble()) < STORY_FIRST_PROMPT_MIN_CHARS:
        story = _clean(story + _cinematic_length_booster(expand_index))
        expand_index += 1
        if expand_index > 6:
            break

    full = _assemble()
    if len(full) > KLING_FRAME_PROMPT_MAX_CHARS:
        full = full[: KLING_FRAME_PROMPT_MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return full


def build_story_first_technical_footer(
    *,
    style: str,
    mood: str,
    camera_direction: str,
    continuity_anchor: str,
    directives_summary: str = "",
) -> str:
    return _build_technical_footer(
        style=style,
        mood=mood,
        camera_direction=camera_direction,
        continuity_anchor=continuity_anchor,
        directives_summary=directives_summary,
    )


def fit_story_first_prompt_length(story_body: str, technical_footer: str) -> str:
    return _fit_story_first_length(story_body, technical_footer)


def compose_story_first_frame_prompt_primary(
    *,
    prefer_openai: bool = True,
    dry_run: bool = False,
    character_continuity: str = "",
    environment_continuity: str = "",
    **kwargs: Any,
) -> tuple[str, dict[str, Any]]:
    """OpenAI primary story-first prompt with local template fallback."""
    authorship: dict[str, Any] = {
        "source": "local_template",
        "openai_applied": False,
        "openai_model": "",
        "notes": [],
    }
    if prefer_openai:
        from content_brain.story.kling_story_first_openai_writer import try_write_story_first_prompt_openai

        openai_prompt, openai_meta = try_write_story_first_prompt_openai(
            dry_run=dry_run,
            character_continuity=character_continuity,
            environment_continuity=environment_continuity,
            **kwargs,
        )
        authorship.update(openai_meta)
        if openai_prompt:
            authorship["source"] = "openai"
            authorship["openai_applied"] = True
            prompt = ensure_prior_clip_continuity_language(
                openai_prompt,
                clip_index=int(kwargs.get("clip_index") or 1),
                prior_bridge_hint=str(kwargs.get("prior_bridge_hint") or ""),
                cast=str(kwargs.get("cast") or ""),
                emotion=str(kwargs.get("emotion") or ""),
                style=str(kwargs.get("style") or ""),
                mood=str(kwargs.get("mood") or ""),
                camera_direction=str(kwargs.get("camera_direction") or ""),
                continuity_anchor=str(kwargs.get("continuity_anchor") or ""),
            )
            if prompt != openai_prompt:
                authorship.setdefault("notes", []).append("prior_clip_continuity_injected")
            return prompt, authorship

    local_prompt = compose_story_first_frame_prompt(**kwargs)
    authorship.setdefault("notes", []).append("local_template_fallback")
    prompt = ensure_prior_clip_continuity_language(
        local_prompt,
        clip_index=int(kwargs.get("clip_index") or 1),
        prior_bridge_hint=str(kwargs.get("prior_bridge_hint") or ""),
        cast=str(kwargs.get("cast") or ""),
        emotion=str(kwargs.get("emotion") or ""),
        style=str(kwargs.get("style") or ""),
        mood=str(kwargs.get("mood") or ""),
        camera_direction=str(kwargs.get("camera_direction") or ""),
        continuity_anchor=str(kwargs.get("continuity_anchor") or ""),
    )
    return prompt, authorship


def compose_story_first_frame_prompt(
    *,
    topic: str,
    cast: str,
    environment: str,
    beat: str,
    emotion: str,
    chapter_role: str,
    story_objective: str,
    visual_progression: str,
    dialogue: str,
    dialogue_goal: str,
    clip_index: int,
    total_clips: int,
    prior_bridge_hint: str,
    bridge_hint: str,
    conflict_level: int,
    mood: str,
    style: str,
    camera_direction: str,
    continuity_anchor: str,
    directives_summary: str,
) -> str:
    paragraphs = _build_story_paragraphs(
        topic=topic,
        cast=cast,
        environment=environment,
        beat=beat,
        emotion=emotion,
        chapter_role=chapter_role,
        story_objective=story_objective,
        visual_progression=visual_progression,
        dialogue=dialogue,
        dialogue_goal=dialogue_goal,
        clip_index=clip_index,
        total_clips=total_clips,
        prior_bridge_hint=prior_bridge_hint,
        bridge_hint=bridge_hint,
        conflict_level=conflict_level,
        mood=mood,
        style=style,
    )
    story_body = "\n\n".join(paragraphs)
    technical = _build_technical_footer(
        style=style,
        mood=mood,
        camera_direction=camera_direction,
        continuity_anchor=continuity_anchor,
        directives_summary=directives_summary,
    )
    prompt = _fit_story_first_length(story_body, technical)
    ok_meta, _ = validate_cinematic_story_body(_split_story_and_technical(prompt)[0])
    if not ok_meta:
        extra = _cinematic_length_booster(clip_index)
        story_body = _clean(story_body + extra)
        prompt = _fit_story_first_length(story_body, technical)
    return prompt


def audit_kling_frame_plan_prompts(plan: Any) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for clip in getattr(plan, "clips", []) or []:
        audit = audit_story_first_prompt(str(getattr(clip, "prompt", "") or ""))
        payload = audit.to_dict()
        payload["clip_index"] = int(getattr(clip, "clip_index", 0) or 0)
        audits.append(payload)
    return audits


def validate_kling_frame_plan_story_first(plan: Any) -> tuple[bool, list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    audits = audit_kling_frame_plan_prompts(plan)
    for item in audits:
        label = f"clip {item.get('clip_index')}"
        if not item.get("ok"):
            errors.extend(f"{label}: {err}" for err in item.get("errors") or [])
    return not errors, errors, audits


__all__ = [
    "STORY_FIRST_VERSION",
    "STORY_FIRST_PROMPT_HARD_MIN",
    "STORY_FIRST_PROMPT_MIN_CHARS",
    "STORY_FIRST_PROMPT_TARGET_MIN",
    "STORY_FIRST_PROMPT_TARGET_MAX",
    "STORY_FIRST_GENERATION_FAIL_STORY_RATIO",
    "TECHNICAL_SECTION_MARKER",
    "StoryFirstPromptAudit",
    "audit_kling_frame_plan_prompts",
    "audit_story_first_prompt",
    "find_forbidden_story_metadata",
    "validate_cinematic_story_body",
    "build_prompt_composition_trace",
    "has_prior_clip_continuity_language",
    "build_prior_clip_continuity_opener",
    "ensure_prior_clip_continuity_language",
    "build_story_first_technical_footer",
    "fit_story_first_prompt_length",
    "compose_story_first_frame_prompt_primary",
    "compose_story_first_frame_prompt",
    "validate_kling_frame_plan_story_first",
    "validate_story_first_prompt_for_generation",
]
