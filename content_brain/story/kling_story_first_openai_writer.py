"""OpenAI primary writer for Kling Frame-to-Video story-first prompts."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from content_brain.story.story_first_prompt_engine import (
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_PROMPT_TARGET_MAX,
    STORY_FIRST_PROMPT_TARGET_MIN,
    TECHNICAL_SECTION_MARKER,
    audit_story_first_prompt,
    build_prompt_composition_trace,
    build_story_first_technical_footer,
    ensure_prior_clip_continuity_language,
    fit_story_first_prompt_length,
    has_prior_clip_continuity_language,
    validate_cinematic_story_body,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)

OPENAI_WRITER_VERSION = "kling_story_first_openai_writer_v5_narrator_timing"
DEFAULT_MODEL_FALLBACK = "gpt-4.1-mini"
MODEL_PREFERENCE = ("gpt-4.1", DEFAULT_MODEL_FALLBACK)
REQUEST_TIMEOUT_SECONDS = 90.0
MAX_ATTEMPTS = 2
OPENAI_MIN_STORY_RATIO = 0.60

MAX_WORDS_PER_CLIP = 35
MAX_WORDS_TOTAL = 70

TIMING_RULES_BLOCK = """TIMING RULES — CRITICAL:
- Total video = 30 seconds
- Clip 1 = 15 seconds = MAX 35 words spoken
- Clip 2 = 15 seconds = MAX 35 words spoken
- Count words carefully before finalizing
- Script must END completely before clip ends
- Last 2 seconds = silence or music only
- NEVER cut off mid-sentence"""

HORROR_THRILLER_LENGTH_BOOSTER = (
    " A passerby flinches at a distant sound; steam hisses from a vent; wet fabric clings to skin; "
    "every micro-gesture — a swallowed breath, a tightened jaw, a hand that almost reaches out — "
    "keeps the moment alive and irreversible."
)

SCIENCE_CLOSING_TEMPLATE = (
    " The presenter maintains eye contact with camera, "
    "her expression conveying wonder and scientific curiosity. "
    "The final frame shows her gesturing toward the next "
    "discovery, inviting the viewer to follow."
)

SYSTEM_PROMPT_COMEDY = """You write Kling Frame-to-Video prompts as cinematic scene prose for native in-scene audio.

Return ONLY the final prompt text — no JSON, no markdown fences, no commentary.

Structure:
1) STORY BODY — read like a real movie scene in present-tense cinematic prose:
   actual events, actions, dialogue in quotes, emotions shown through behavior, sensory detail.
2) TECHNICAL FOOTER — after a line exactly reading:
--- Technical execution ---
Include ONLY: visual style, audio style (native in-scene), camera style, continuity anchor.

Hard rules:
- Total length MUST be 2400–2500 characters.
- Story body MUST be at least 80% of total length.
- NEVER put prompt-design metadata in the story body.
- FORBIDDEN in story body (never write these labels or phrases):
  Chapter role:, Story objective:, Dialogue goal:, Conflict level, Visual progression:,
  Narrative context:, Emotional temperature:, The chapter opens, Dialogue moment:,
  Character behavior stays specific, Environmental interaction is not decoration.
- Use the INTERNAL BRIEFING only as guidance — do not copy field names or planning notes into output.
- Write actual scenes, not planning documents.
- Native in-scene audio only — no external narration, no background music track, no ElevenLabs.
- Clip 2+ must include prior-clip handoff with the words "previous" or "resumes" woven into natural prose.
- Preserve character and environment continuity through action, not metadata labels.

CRITICAL — Story must FULLY COMPLETE in 2 clips:

Clip 1 (15s): Hook + Setup
- Open with arresting visual (3s)
- Build the situation (10s)
- End on clear tension (2s)

Clip 2 (15s): Payoff + Clear Ending
- Deliver the funny moment fully (8s)
- Show character reactions (4s)
- HARD ENDING: freeze frame, laugh, or clear visual resolution (3s)
- NEVER end mid-action or mid-sentence
- Viewer must feel satisfied and complete

""" + TIMING_RULES_BLOCK

SYSTEM_PROMPT_SCIENCE = """You write Kling Frame-to-Video prompts as premium cinematic science-documentary scene prose for native in-scene audio.

Write cinematic prose describing a SCIENCE FACT visualization. The presenter explains the fact while stunning visuals play. Each sentence must describe what the viewer SEES on screen. Minimum 80% of text must be scene description.

Return ONLY the final prompt text — no JSON, no markdown fences, no commentary.

Structure:
1) STORY BODY — present-tense cinematic prose with a recurring female science presenter integrated into dynamic scientific visuals:
   holographic displays, animated diagrams, macro/micro footage, space simulations, molecular visualizations.
2) TECHNICAL FOOTER — after a line exactly reading:
--- Technical execution ---
Include ONLY: visual style, audio style (native in-scene), camera style, continuity anchor.

Hard rules:
- Total length MUST be 2400–2500 characters.
- Story body MUST be at least 80% of total length.
- Presenter: confident, intelligent, elegant modern science host — expressive but natural spoken English.
- Visuals must surround, transition with, or appear beside the presenter — not boring static split-screen.
- Native in-scene audio only — presenter speaks the science hook, setup, explanation, and payoff.
- Clip 2+ must include prior-clip handoff with the words "previous" or "resumes" woven into natural prose.
- Preserve presenter face, hair, styling, and wardrobe continuity through action.

CRITICAL — Science Short must FULLY COMPLETE in 2 clips (25-35s total):

Clip 1 (15s): Hook + Setup
- Open with impossible scientific hook (0-2s) — no "Did you know?"
- Presenter setup (2-8s) — one clear phenomenon in simple spoken English
- Begin visual explanation (8-15s) — cinematic scientific visuals integrate dynamically
- End on curiosity gap — setup COMPLETE

Clip 2 (15s): Payoff + Twist + CTA
- Continue visual explanation (8s) — mechanism made vivid
- Deliver strangest payoff (4s) — more surprising than the hook when possible
- Presenter finishes speaking, then 2-3 second silent reaction/pause shot (3s)
- HARD ENDING — natural short CTA or memorable closing line
- NEVER end mid-sentence. Visual resolution before cut

""" + TIMING_RULES_BLOCK + """

CONTENT SAFETY RULES — NEVER include:
- Any reference to skin, body, flesh, glowing skin
- Romantic or intimate language about the presenter
- Body scan or body data visualization on person
- Any phrase that could be sexual
- Words: glowing (when describing person), her skin, body scan, flesh, sensual

SAFE alternatives:
- Instead of 'holographic body scan on her': use 'holographic molecular diagram beside her'
- Instead of 'glowing right now': use 'the science reveals itself'
- Instead of body-focused: focus on the SCIENCE FACT visualization

The presenter is a SCIENCE HOST — describe her ACTIONS and GESTURES only,
never her physical appearance or body.

CLOSING TEMPLATE — end the story body with this documentary tone (adapt naturally):
"The presenter maintains eye contact with camera, her expression conveying wonder and scientific curiosity. The final frame shows her gesturing toward the next discovery, inviting the viewer to follow."

FORBIDDEN closing filler — never use horror/thriller micro-gesture prose such as:
"A passerby flinches at a distant sound; steam hisses from a vent; wet fabric clings to skin; every micro-gesture — a swallowed breath, a tightened jaw, a hand that almost reaches out — keeps the moment alive and irreversible."""

SYSTEM_PROMPT_BEAUTY = """You write Kling Frame-to-Video prompts as cinematic skincare-tutorial scene prose for native in-scene audio.

Write cinematic prose for a skincare tutorial. Show ingredients, mixing process, and application. Presenter teaches with exact quantities. Each sentence describes what viewer SEES.

Return ONLY the final prompt text — no JSON, no markdown fences, no commentary.

Structure:
1) STORY BODY — present-tense cinematic prose in a bright, clean aesthetic kitchen or bathroom:
   close-ups of ingredients, measuring spoons, mixing bowls, texture on skin, presenter demonstrating each step.
2) TECHNICAL FOOTER — after a line exactly reading:
--- Technical execution ---
Include ONLY: visual style, audio style (native in-scene), camera style, continuity anchor.

Hard rules:
- Total length MUST be 2400–2500 characters.
- Story body MUST be at least 80% of total length.
- Presenter speaks exact ingredient quantities naturally (e.g. "two tablespoons honey").
- Native in-scene audio only — presenter teaches on camera, no external narration.
- Clip 2+ must include prior-clip handoff with the words "previous" or "resumes" woven into natural prose.
- Preserve presenter appearance, workspace, and ingredient layout continuity through action.

CRITICAL — Skincare Reel must FULLY COMPLETE in 2 clips (25-35s total):

Clip 1 (15s): Ingredients + Mix
- Show every ingredient with close-ups (0-5s)
- Presenter names recipe and exact quantities while mixing (5-15s)
- End with mixture ready to apply

Clip 2 (15s): Apply + Result + CTA
- Application on face or skin with close-ups (8s)
- Visible result or glow moment (4s)
- HARD ENDING (3s) — "Follow for daily skincare recipes" or natural variant
- NEVER end mid-sentence. Viewer must feel the tutorial is complete

""" + TIMING_RULES_BLOCK

SYSTEM_PROMPT_PERFUMERY = """
You write Kling video prompts for Instagram 
perfumery education content.

STYLE: Elegant, luxurious, beautiful, educational.
NOT cinematic thriller. NOT running characters.
NOT drama or action scenes.

WHAT TO SHOW:
- Close-up macro shots of the ingredient 
  (flower petals, wood, resin, crystals)
- Hands of an elegant woman holding/smelling 
  the ingredient
- Laboratory distillation equipment with 
  steam and glass bottles
- Perfume bottles with golden light
- Nature scenes: rose fields, forest, ocean
- Text overlay showing ingredient name and origin

PRESENTER: An elegant, knowledgeable woman who 
presents like a luxury brand ambassador.
She holds ingredients, smells them, explains 
their properties with passion.
She NEVER runs. She NEVER has dramatic encounters.
She speaks directly to camera in a warm, 
educational tone.

VISUAL STYLE:
- Warm golden lighting
- Macro close-up shots
- Luxury aesthetic
- Soft focus background
- Rich colors: deep rose, amber, gold, cream

FORBIDDEN:
- Running characters
- Dramatic chases or action
- Dark mysterious atmosphere  
- Horror or thriller elements
- Multiple characters interacting dramatically
- Any narrative conflict or tension

Return ONLY the final prompt text — no JSON, no markdown fences, no commentary.

Structure:
1) STORY BODY — present-tense educational prose in an elegant fragrance atelier,
   botanical lab, or nature/macro ingredient setting. Describe what the viewer SEES.
2) TECHNICAL FOOTER — after a line exactly reading:
--- Technical execution ---
Include ONLY: visual style, audio style (native in-scene), camera style, continuity anchor.

Hard rules:
- Total length MUST be 2400–2500 characters.
- Story body MUST be at least 80% of total length.
- Presenter teaches one ingredient: name, origin, scent profile, perfume role, famous perfume examples, fun fact.
- Native in-scene audio only — presenter teaches on camera, no external narration.
- Clip 2+ must include prior-clip handoff with the words "previous" or "resumes" woven into natural prose.
- Preserve presenter appearance, atelier/ingredient continuity through calm educational action.
- NEVER invent running, chase, boy/girl drama, horror, or thriller filler.

CRITICAL — Perfumery Reel must FULLY COMPLETE in 2 clips (25-35s total):

Clip 1 (15s): Ingredient + Origin + Scent
- Macro of raw ingredient texture/color (0-5s)
- Presenter: "Today we explore [ingredient]" + origin + scent profile (5-15s)
- End with curiosity about perfume use

Clip 2 (15s): Role + Famous Perfumes + Fun Fact + CTA
- Extraction/blending visuals + perfume role (8s)
- Famous perfume examples + amazing fun fact (4s)
- HARD ENDING (3s) — "Follow for daily fragrance secrets" or natural variant
- NEVER end mid-sentence. Viewer must feel the lesson is complete

""" + TIMING_RULES_BLOCK


def _resolve_platform_genre(**kwargs: Any) -> str:
    platform = str(kwargs.get("target_platform") or kwargs.get("platform") or "").lower()
    if platform in {"instagram_reels", "instagram"}:
        return str(kwargs.get("instagram_genre") or "perfumery").lower()
    if platform in {"youtube_shorts", "youtube"}:
        return str(kwargs.get("youtube_genre") or "science").lower()
    if platform == "tiktok":
        return str(kwargs.get("tiktok_genre") or "entertainment").lower()
    return str(kwargs.get("genre") or kwargs.get("niche") or "").lower()


def _resolve_system_prompt(**kwargs: Any) -> str:
    platform = str(kwargs.get("target_platform") or kwargs.get("platform") or "").lower()
    genre = _resolve_platform_genre(**kwargs)
    topic = str(kwargs.get("topic") or "").lower()

    if platform in {"instagram_reels", "instagram"}:
        if "beauty" in genre or "skincare" in genre:
            return SYSTEM_PROMPT_BEAUTY
        if (
            "perfumery" in genre
            or "perfume" in genre
            or "fragrance" in genre
            or "perfume" in topic
            or "fragrance" in topic
            or "perfumery" in topic
        ):
            return SYSTEM_PROMPT_PERFUMERY
        return SYSTEM_PROMPT_PERFUMERY
    if platform in {"youtube_shorts", "youtube"}:
        return SYSTEM_PROMPT_SCIENCE
    if platform == "tiktok":
        return SYSTEM_PROMPT_COMEDY

    if "perfumery" in genre or "perfume" in genre or "fragrance" in genre:
        return SYSTEM_PROMPT_PERFUMERY
    if "beauty" in genre or "skincare" in genre:
        return SYSTEM_PROMPT_BEAUTY
    if "science" in genre:
        return SYSTEM_PROMPT_SCIENCE

    if "science" in topic or "impossible" in topic:
        return SYSTEM_PROMPT_SCIENCE
    if "perfume" in topic or "fragrance" in topic or "perfumery" in topic:
        return SYSTEM_PROMPT_PERFUMERY
    return SYSTEM_PROMPT_COMEDY


SYSTEM_PROMPT = SYSTEM_PROMPT_COMEDY


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def narrator_word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:'\w+)?\b", str(text or "")))


def trim_narrator_line(text: str, *, max_words: int = MAX_WORDS_PER_CLIP) -> str:
    cleaned = _clean(text)
    if not cleaned:
        return ""
    words = re.findall(r"\b\w+(?:'\w+)?\b", cleaned)
    if len(words) <= max_words:
        return cleaned

    trimmed_words = words[:max_words]
    candidate = " ".join(trimmed_words)
    sentence_end = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_end > len(candidate) * 0.45:
        return candidate[: sentence_end + 1].strip()

    partial = cleaned
    for _ in range(len(words) - max_words + 1):
        cut = partial.rfind(" ")
        if cut <= 0:
            break
        partial = partial[:cut].rstrip(" ,;:-")
        if narrator_word_count(partial) <= max_words:
            sentence_end = max(partial.rfind("."), partial.rfind("!"), partial.rfind("?"))
            if sentence_end > 0:
                return partial[: sentence_end + 1].strip()
            return f"{partial}."
    return f"{candidate}."


def validate_narrator_lines(lines: list[str]) -> list[str]:
    trimmed: list[str] = []
    total_words = 0
    for raw in lines:
        line = trim_narrator_line(raw, max_words=MAX_WORDS_PER_CLIP)
        if not line:
            continue
        words = narrator_word_count(line)
        remaining = MAX_WORDS_TOTAL - total_words
        if remaining <= 0:
            break
        if words > remaining:
            line = trim_narrator_line(line, max_words=remaining)
            words = narrator_word_count(line)
        if line:
            trimmed.append(line)
            total_words += words
    return trimmed


def _strip_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def get_openai_client(*, project_root: str | Path | None = None) -> OpenAI:
    """Lazy OpenAI client — bootstraps .env on first use if the key is not loaded yet."""
    if OpenAI is None:
        raise ValueError("openai package not installed")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        try:
            from core.env_bootstrap import bootstrap_project_env

            bootstrap_project_env(project_root=project_root)
        except Exception as exc:
            logger.debug("env bootstrap during OpenAI client init failed: %s", exc)
        key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key, timeout=REQUEST_TIMEOUT_SECONDS)


def resolve_openai_writer_models() -> list[str]:
    configured = os.getenv("OPENAI_KLING_PROMPT_MODEL", "").strip() or os.getenv("OPENAI_DIRECTOR_MODEL", "").strip()
    models: list[str] = []
    if configured:
        models.append(configured)
    for model in MODEL_PREFERENCE:
        if model not in models:
            models.append(model)
    return models


def _technical_footer_from_context(**kwargs: Any) -> str:
    return build_story_first_technical_footer(
        style=str(kwargs.get("style") or "cinematic"),
        mood=str(kwargs.get("mood") or "dramatic"),
        camera_direction=str(kwargs.get("camera_direction") or "motivated cinematic camera"),
        continuity_anchor=str(kwargs.get("continuity_anchor") or "preserve character and environment"),
        directives_summary=str(kwargs.get("directives_summary") or ""),
    )


def _strip_horror_thriller_booster(story_body: str) -> str:
    cleaned = str(story_body or "")
    cleaned = cleaned.replace(HORROR_THRILLER_LENGTH_BOOSTER.strip(), " ")
    cleaned = re.sub(
        r"A passerby flinches at a distant sound;.*?keeps the moment alive and irreversible\.?",
        " ",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _fit_science_story_first_length(story_body: str, technical_footer: str) -> str:
    separator = "\n\n"
    technical = technical_footer.strip()
    story = _strip_horror_thriller_booster(story_body)

    def _assemble() -> str:
        return re.sub(r"\s+", " ", f"{story}{separator}{technical}").strip()

    full = _assemble()
    if len(full) > STORY_FIRST_PROMPT_TARGET_MAX:
        overflow = len(full) - STORY_FIRST_PROMPT_TARGET_MAX
        if overflow > 0 and len(story) > overflow + 200:
            story = story[: len(story) - overflow].rsplit(" ", 1)[0].rstrip(".,;:") + "."

    expand_index = 0
    while len(_assemble()) < STORY_FIRST_PROMPT_MIN_CHARS:
        story = re.sub(r"\s+", " ", f"{story}{SCIENCE_CLOSING_TEMPLATE}").strip()
        expand_index += 1
        if expand_index > 3:
            break

    full = _assemble()
    if len(full) > STORY_FIRST_PROMPT_TARGET_MAX:
        full = full[: STORY_FIRST_PROMPT_TARGET_MAX - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return full


def _normalize_openai_prompt(raw: str, **kwargs: Any) -> str:
    text = _strip_fences(raw)
    technical = _technical_footer_from_context(**kwargs)
    marker = TECHNICAL_SECTION_MARKER

    if marker in text:
        story_body, _existing_technical = text.split(marker, 1)
        story_body = story_body.strip()
    else:
        story_body = text.strip()

    science_mode = _resolve_system_prompt(**kwargs) == SYSTEM_PROMPT_SCIENCE
    if science_mode:
        return _fit_science_story_first_length(story_body, technical)
    return fit_story_first_prompt_length(story_body, technical)


def _validate_openai_prompt(
    prompt: str,
    *,
    clip_index: int,
    cast: str,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    story_part, _ = prompt.split(TECHNICAL_SECTION_MARKER, 1) if TECHNICAL_SECTION_MARKER in prompt else (prompt, "")
    ok_meta, meta_errors = validate_cinematic_story_body(story_part)
    if not ok_meta:
        errors.extend(meta_errors)

    audit = audit_story_first_prompt(prompt)
    if not audit.ok:
        errors.extend(audit.errors)
    if audit.prompt_length < STORY_FIRST_PROMPT_MIN_CHARS:
        errors.append(f"prompt_length {audit.prompt_length} < {STORY_FIRST_PROMPT_MIN_CHARS}")
    if audit.story_percent < OPENAI_MIN_STORY_RATIO * 100:
        errors.append(f"story_percent {audit.story_percent} < {OPENAI_MIN_STORY_RATIO * 100:.0f}%")
    if "native" not in prompt.lower():
        errors.append("missing native audio instruction")
    if cast:
        first_cast = cast.split(" and ")[0].split(",")[0].strip().lower()
        if first_cast and first_cast[:6] not in prompt.lower():
            errors.append("cast not reflected in prompt")
    if clip_index > 1 and not has_prior_clip_continuity_language(prompt):
        errors.append("missing prior-clip continuity language (requires 'previous' or 'resumes')")
    if TECHNICAL_SECTION_MARKER not in prompt:
        errors.append("missing technical section marker")
    return not errors, errors


def _openai_text_completion(*, system_prompt: str, user_content: str, dry_run: bool = False) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    if dry_run:
        notes.append("openai_kling_prompt_dry_run")
        return "", "", notes

    try:
        client = get_openai_client()
    except ValueError as exc:
        logger.error("OpenAI client unavailable for Kling prompt writer: %s", exc)
        notes.append(f"openai_client_unavailable:{exc}")
        return "", "", notes

    last_error = ""
    for model in resolve_openai_writer_models():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.65,
                max_tokens=1800,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                last_error = f"empty_response:{model}"
                continue
            notes.append(f"openai_kling_prompt_applied:{model}")
            return content, model, notes
        except Exception as exc:  # pragma: no cover
            last_error = f"{model}:{exc}"
            logger.error("OpenAI Kling prompt request failed (%s): %s", model, exc)
            continue
    notes.append(f"openai_kling_prompt_failed:{last_error or 'unknown'}")
    return "", "", notes


def _build_openai_brief(
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
    character_continuity: str,
    environment_continuity: str,
    target_platform: str = "",
    instagram_genre: str = "",
    youtube_genre: str = "",
    tiktok_genre: str = "",
) -> dict[str, Any]:
    """Internal metadata for OpenAI — must NOT appear as labels in output."""
    brief: dict[str, Any] = {
        "_instruction": "INTERNAL BRIEFING ONLY. Do not copy field names into the story body.",
        "topic": topic,
        "cast": cast,
        "environment": environment,
        "story_beat": beat,
        "chapter_role": chapter_role,
        "story_objective": story_objective,
        "visual_progression": visual_progression,
        "emotion": emotion,
        "mood": mood,
        "style": style,
        "conflict_level": conflict_level,
        "clip_index": clip_index,
        "total_clips": total_clips,
        "character_continuity": character_continuity,
        "environment_continuity": environment_continuity,
        "camera_direction": camera_direction,
        "continuity_anchor": continuity_anchor,
        "native_audio_directives": directives_summary,
    }
    if dialogue:
        brief["dialogue_line_to_quote"] = trim_narrator_line(dialogue)
        brief["dialogue_word_count"] = narrator_word_count(brief["dialogue_line_to_quote"])
        brief["dialogue_max_words"] = MAX_WORDS_PER_CLIP
    else:
        brief["dialogue_intent"] = dialogue_goal
    if clip_index > 1:
        brief["prior_handoff_from"] = prior_bridge_hint
    if clip_index < total_clips:
        brief["bridge_toward_next"] = bridge_hint
    brief["length_target"] = f"{STORY_FIRST_PROMPT_TARGET_MIN}-{STORY_FIRST_PROMPT_TARGET_MAX} characters"
    if int(total_clips) == 2:
        platform = str(target_platform or "").lower()
        genre = str(instagram_genre or "").lower()
        topic_l = str(topic or "").lower()
        perfumery_mode = (
            platform in {"instagram_reels", "instagram"}
            and (
                genre in {"perfumery", "perfume", "fragrance"}
                or any(token in topic_l for token in ("perfume", "fragrance", "perfumery"))
                or genre not in {"beauty", "skincare"}
            )
        )
        beauty_mode = (not perfumery_mode) and (
            platform in {"instagram_reels", "instagram"}
            or genre in {"beauty", "skincare"}
        )
        science_mode = (
            platform in {"youtube_shorts", "youtube"}
            or str(youtube_genre or "").lower() == "science"
            or (
                not beauty_mode
                and not perfumery_mode
                and not platform
                and any(
                    marker in topic_l
                    for marker in ("science", "impossible", "physics", "brain", "quantum")
                )
            )
        )
        if int(clip_index) <= 1:
            if perfumery_mode:
                brief["clip_timing_structure"] = (
                    "Clip 1 (15s) Ingredient+Origin+Scent: raw ingredient macro 0-5s, presenter names "
                    "ingredient + origin + scent profile 5-15s, curiosity gap into perfume use"
                )
            elif beauty_mode:
                brief["clip_timing_structure"] = (
                    "Clip 1 (15s) Ingredients+Mix: ingredient close-ups 0-5s, presenter names exact "
                    "quantities while mixing 5-15s, mixture ready to apply"
                )
            elif science_mode:
                brief["clip_timing_structure"] = (
                    "Clip 1 (15s) Hook+Setup: impossible hook 0-2s, presenter setup 2-8s, "
                    "visual explanation begins 8-15s, curiosity gap ending"
                )
            else:
                brief["clip_timing_structure"] = (
                    "Clip 1 (15s) Hook+Setup: arresting visual 3s, build situation 10s, clear tension 2s"
                )
        elif perfumery_mode:
            brief["clip_timing_structure"] = (
                "Clip 2 (15s) Role+Famous Perfumes+Fun Fact+CTA: extraction/blending 8s, "
                "famous perfume example + shocking fun fact 4s, presenter finishes then 2-3s "
                "silent pause, HARD ENDING with fragrance-secrets CTA — NEVER mid-sentence"
            )
        elif beauty_mode:
            brief["clip_timing_structure"] = (
                "Clip 2 (15s) Apply+Result+CTA: application close-ups 8s, visible glow 4s, "
                "presenter finishes speaking then 2-3s silent reaction/pause on result, "
                "HARD ENDING with follow-for-recipes CTA — NEVER mid-sentence"
            )
        elif science_mode:
            brief["clip_timing_structure"] = (
                "Clip 2 (15s) Payoff+Twist+CTA: visual explanation 8s, strangest payoff 4s, "
                "presenter finishes speaking then 2-3s silent reaction/pause shot, HARD ENDING — "
                "NEVER mid-sentence, visual resolution before cut"
            )
        else:
            brief["clip_timing_structure"] = (
                "Clip 2 (15s) Payoff+Clear Ending: funny moment fully 8s, character reactions 4s, "
                "HARD ENDING freeze/laugh/resolution 3s — NEVER mid-action or mid-sentence"
            )
        brief["two_clip_completion_rule"] = (
            "Story must FULLY COMPLETE in 2 clips. Viewer must feel satisfied and complete. "
            f"Spoken dialogue per clip: max {MAX_WORDS_PER_CLIP} words; total max {MAX_WORDS_TOTAL} words."
        )
        brief["timing_rules"] = TIMING_RULES_BLOCK
    return brief


def _build_user_prompt(**kwargs: Any) -> str:
    excluded = {
        "character_continuity",
        "environment_continuity",
        "dry_run",
        "prefer_openai",
        "platform",
        "target_platform",
        "genre",
        "niche",
        "regeneration_feedback",
    }
    brief = _build_openai_brief(
        character_continuity=str(kwargs.get("character_continuity") or ""),
        environment_continuity=str(kwargs.get("environment_continuity") or ""),
        target_platform=str(kwargs.get("target_platform") or kwargs.get("platform") or ""),
        **{k: v for k, v in kwargs.items() if k not in excluded},
    )
    return (
        "Write cinematic scene prose for Kling Frame-to-Video using this INTERNAL BRIEFING.\n"
        "Do NOT echo briefing field names in the output.\n\n"
        f"{json.dumps(brief, ensure_ascii=False, indent=2)}\n\n"
        f"End with the technical footer after '{TECHNICAL_SECTION_MARKER}'."
    )


def try_write_story_first_prompt_openai(
    *,
    dry_run: bool = False,
    character_continuity: str = "",
    environment_continuity: str = "",
    **kwargs: Any,
) -> tuple[str | None, dict[str, Any]]:
    """Attempt OpenAI story-first prompt; return None to trigger local fallback."""
    meta: dict[str, Any] = {
        "version": OPENAI_WRITER_VERSION,
        "openai_applied": False,
        "openai_model": "",
        "notes": [],
        "validation_errors": [],
    }
    clip_index = int(kwargs.get("clip_index") or 1)
    cast = str(kwargs.get("cast") or "")
    resolved_system_prompt = _resolve_system_prompt(**kwargs)

    user_prompt = _build_user_prompt(
        character_continuity=character_continuity,
        environment_continuity=environment_continuity,
        **kwargs,
    )
    feedback = ""
    raw_response = ""
    regeneration_feedback = str(kwargs.get("regeneration_feedback") or "").strip()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_prompt = user_prompt
        extra_feedback = feedback or regeneration_feedback
        if extra_feedback:
            attempt_prompt = (
                f"{user_prompt}\n\nPrevious attempt failed validation:\n{extra_feedback}\n"
                "Rewrite as pure cinematic scene prose with zero metadata labels."
            )

        raw, model, notes = _openai_text_completion(
            system_prompt=resolved_system_prompt,
            user_content=attempt_prompt,
            dry_run=dry_run,
        )
        meta["notes"].extend(notes)
        if not raw:
            return None, meta

        raw_response = raw
        prompt = _normalize_openai_prompt(raw, **kwargs)
        prompt = ensure_prior_clip_continuity_language(
            prompt,
            clip_index=clip_index,
            prior_bridge_hint=str(kwargs.get("prior_bridge_hint") or ""),
            cast=cast,
            emotion=str(kwargs.get("emotion") or ""),
            style=str(kwargs.get("style") or ""),
            mood=str(kwargs.get("mood") or ""),
            camera_direction=str(kwargs.get("camera_direction") or ""),
            continuity_anchor=str(kwargs.get("continuity_anchor") or ""),
        )
        ok, errors = _validate_openai_prompt(
            prompt,
            clip_index=clip_index,
            cast=cast,
        )
        audit = audit_story_first_prompt(prompt)
        meta["story_first_audit"] = audit.to_dict()
        meta["composition_trace"] = build_prompt_composition_trace(
            openai_system_prompt=resolved_system_prompt,
            openai_user_prompt=attempt_prompt,
            openai_raw_response=raw_response,
            final_prompt=prompt,
        )
        if ok:
            meta["openai_applied"] = True
            meta["openai_model"] = model
            meta["attempt"] = attempt
            return prompt, meta

        meta["validation_errors"] = errors
        feedback = "; ".join(errors)
        meta["notes"].append(f"validation_failed_attempt_{attempt}")

    meta["notes"].append("openai_kling_prompt_exhausted_retries")
    return None, meta


__all__ = [
    "OPENAI_WRITER_VERSION",
    "OPENAI_MIN_STORY_RATIO",
    "MAX_WORDS_PER_CLIP",
    "MAX_WORDS_TOTAL",
    "TIMING_RULES_BLOCK",
    "narrator_word_count",
    "trim_narrator_line",
    "validate_narrator_lines",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_BEAUTY",
    "SYSTEM_PROMPT_PERFUMERY",
    "SYSTEM_PROMPT_SCIENCE",
    "try_write_story_first_prompt_openai",
    "get_openai_client",
    "_build_openai_brief",
    "_resolve_system_prompt",
]
