"""OpenAI primary writer for Kling Frame-to-Video story-first prompts."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from content_brain.story.story_first_prompt_engine import (
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_PROMPT_TARGET_MAX,
    STORY_FIRST_PROMPT_TARGET_MIN,
    STORY_FIRST_TARGET_STORY_RATIO,
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

OPENAI_WRITER_VERSION = "kling_story_first_openai_writer_v3_science"
DEFAULT_MODEL_FALLBACK = "gpt-4.1-mini"
MODEL_PREFERENCE = ("gpt-4.1", DEFAULT_MODEL_FALLBACK)
REQUEST_TIMEOUT_SECONDS = 90.0
MAX_ATTEMPTS = 2

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
- Viewer must feel satisfied and complete"""

SYSTEM_PROMPT_SCIENCE = """You write Kling Frame-to-Video prompts as premium cinematic science-documentary scene prose for native in-scene audio.

Return ONLY the final prompt text — no JSON, no markdown fences, no commentary.

Structure:
1) STORY BODY — present-tense cinematic prose with a recurring female science presenter integrated into dynamic scientific visuals:
   holographic displays, animated diagrams, macro/micro footage, space simulations, body visualizations, molecular animation.
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
- HARD ENDING (3s) — natural short CTA or memorable closing line
- NEVER end mid-sentence. Viewer rewarded for watching to the end"""


def _resolve_system_prompt(**kwargs: Any) -> str:
    topic = str(kwargs.get("topic") or "").lower()
    genre = str(kwargs.get("genre") or kwargs.get("niche") or "").lower()
    platform = str(kwargs.get("target_platform") or kwargs.get("platform") or "").lower()
    if platform in {"youtube_shorts", "youtube"} or "science" in topic or "impossible" in topic or "science" in genre:
        return SYSTEM_PROMPT_SCIENCE
    return SYSTEM_PROMPT_COMEDY


SYSTEM_PROMPT = SYSTEM_PROMPT_COMEDY


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _strip_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


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


def _normalize_openai_prompt(raw: str, **kwargs: Any) -> str:
    text = _strip_fences(raw)
    technical = _technical_footer_from_context(**kwargs)
    marker = TECHNICAL_SECTION_MARKER

    if marker in text:
        story_body, _existing_technical = text.split(marker, 1)
        story_body = story_body.strip()
    else:
        story_body = text.strip()

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
    if audit.story_percent < STORY_FIRST_TARGET_STORY_RATIO * 100:
        errors.append(f"story_percent {audit.story_percent} < {STORY_FIRST_TARGET_STORY_RATIO * 100:.0f}%")
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

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        notes.append("openai_client_unavailable")
        return "", "", notes

    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
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
        brief["dialogue_line_to_quote"] = dialogue
    else:
        brief["dialogue_intent"] = dialogue_goal
    if clip_index > 1:
        brief["prior_handoff_from"] = prior_bridge_hint
    if clip_index < total_clips:
        brief["bridge_toward_next"] = bridge_hint
    brief["length_target"] = f"{STORY_FIRST_PROMPT_TARGET_MIN}-{STORY_FIRST_PROMPT_TARGET_MAX} characters"
    if int(total_clips) == 2:
        science_mode = any(
            marker in str(topic or "").lower()
            for marker in ("science", "impossible", "physics", "brain", "quantum")
        ) or str(target_platform or "").lower() in {
            "youtube_shorts",
            "youtube",
        }
        if int(clip_index) <= 1:
            if science_mode:
                brief["clip_timing_structure"] = (
                    "Clip 1 (15s) Hook+Setup: impossible hook 0-2s, presenter setup 2-8s, "
                    "visual explanation begins 8-15s, curiosity gap ending"
                )
            else:
                brief["clip_timing_structure"] = (
                    "Clip 1 (15s) Hook+Setup: arresting visual 3s, build situation 10s, clear tension 2s"
                )
        elif science_mode:
            brief["clip_timing_structure"] = (
                "Clip 2 (15s) Payoff+Twist+CTA: visual explanation 8s, strangest payoff 4s, "
                "HARD ENDING with natural CTA 3s — NEVER mid-sentence"
            )
        else:
            brief["clip_timing_structure"] = (
                "Clip 2 (15s) Payoff+Clear Ending: funny moment fully 8s, character reactions 4s, "
                "HARD ENDING freeze/laugh/resolution 3s — NEVER mid-action or mid-sentence"
            )
        brief["two_clip_completion_rule"] = (
            "Story must FULLY COMPLETE in 2 clips. Viewer must feel satisfied and complete."
        )
    return brief


def _build_user_prompt(**kwargs: Any) -> str:
    brief = _build_openai_brief(
        character_continuity=str(kwargs.get("character_continuity") or ""),
        environment_continuity=str(kwargs.get("environment_continuity") or ""),
        **{k: v for k, v in kwargs.items() if k not in {"character_continuity", "environment_continuity", "dry_run", "prefer_openai"}},
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

    user_prompt = _build_user_prompt(
        character_continuity=character_continuity,
        environment_continuity=environment_continuity,
        **kwargs,
    )
    feedback = ""
    raw_response = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_prompt = user_prompt
        if feedback:
            attempt_prompt = (
                f"{user_prompt}\n\nPrevious attempt failed validation:\n{feedback}\n"
                "Rewrite as pure cinematic scene prose with zero metadata labels."
            )

        raw, model, notes = _openai_text_completion(
            system_prompt=_resolve_system_prompt(**kwargs),
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
            openai_system_prompt=SYSTEM_PROMPT,
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
    "SYSTEM_PROMPT",
    "try_write_story_first_prompt_openai",
    "_build_openai_brief",
]
