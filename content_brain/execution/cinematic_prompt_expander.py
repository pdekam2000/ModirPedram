"""Cinematic prompt expansion — structured 8-section clip prompts (2400–2500 chars)."""

from __future__ import annotations

import re
from typing import Any

EXPANDER_VERSION = "cinematic_prompt_expander_v2"
TARGET_MIN_CHARS = 2400
TARGET_MAX_CHARS = 2500

NEGATIVE_PROMPT_BLOCK = (
    "Strict negatives: no subtitles, no captions, no logos, no watermarks, no title cards, "
    "no on-screen text, no UI overlays, no scene jump, no unrelated location change, "
    "no wardrobe swap, no character replacement, no aspect ratio drift."
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _brief_value(story_brief: Any | None, key: str, fallback: str = "") -> str:
    if story_brief is None:
        return fallback
    if isinstance(story_brief, dict):
        return _normalize(str(story_brief.get(key) or fallback))
    return _normalize(str(getattr(story_brief, key, "") or fallback))


def _anchors_dict(anchors: Any | None) -> dict[str, str]:
    if anchors is None:
        return {}
    if hasattr(anchors, "to_dict"):
        return dict(anchors.to_dict())
    if isinstance(anchors, dict):
        return dict(anchors)
    return {
        "character": str(getattr(anchors, "character", "") or ""),
        "location": str(getattr(anchors, "location", "") or ""),
        "lighting": str(getattr(anchors, "lighting", "") or ""),
        "camera": str(getattr(anchors, "camera", "") or ""),
        "palette": str(getattr(anchors, "palette", "") or ""),
        "wardrobe": str(getattr(anchors, "wardrobe", "") or ""),
    }


def _second_by_second_action(*, beat: str, clip_index: int) -> str:
    beat_text = _normalize(beat) or "motivated discovery and escalation"
    return (
        f"Seconds 0–3: establish spatial read and first micro-movement tied to {beat_text}. "
        f"Seconds 3–7: execute the primary action beat with continuous forward motion — no hard cuts. "
        f"Seconds 7–10: decelerate into a stable end pose for clip {clip_index} handoff."
    )


def _continuity_note(*, clip_index: int, clip_count: int, aspect_label: str) -> str:
    if clip_index <= 1:
        return (
            f"Opens from the approved starter reference via Use to Video — preserve identity, wardrobe, "
            f"and environment from the hero frame. Sets up clip 2 with readable end-frame pose. {aspect_label}."
        )
    if clip_index >= clip_count:
        return (
            "Resolves the narrative arc from prior clips — same character, location, and wardrobe. "
            "Final clip holds payoff frame for publish assembly."
        )
    return (
        "Seamless continuation from the previous clip last frame via Use Frame — "
        "do not reset location or character identity. Match lighting vector and screen direction."
    )


def build_structured_prompt_sections(
    *,
    base_prompt: str,
    clip_index: int,
    clip_count: int,
    beat: str = "",
    story_brief: Any | None = None,
    anchors: Any | None = None,
    visual_style: str = "cinematic realistic",
    aspect_label: str = "vertical 9:16",
) -> dict[str, str]:
    anchor = _anchors_dict(anchors)
    subject = (
        _brief_value(story_brief, "subject")
        or _brief_value(story_brief, "main_character")
        or anchor.get("character", "")
        or "primary on-screen subject"
    )
    environment = (
        _brief_value(story_brief, "environment")
        or _brief_value(story_brief, "setting")
        or anchor.get("location", "")
        or "single continuous location"
    )
    lighting = anchor.get("lighting") or "motivated cinematic key with stable direction and soft rim separation"
    camera_base = anchor.get("camera") or "35mm vertical cinematic lens personality"
    wardrobe = anchor.get("wardrobe") or "consistent outfit locked across all clips"
    emotional_arc = _brief_value(story_brief, "emotional_arc", "rising cinematic tension")
    visual_hook = _brief_value(story_brief, "visual_hook", "one scroll-stopping focal element")
    conflict = _brief_value(story_brief, "conflict") or _brief_value(story_brief, "conflict_tension", "")
    style_direction = _brief_value(story_brief, "style_direction", visual_style)
    time_of_day = _brief_value(story_brief, "time_of_day") or "golden-hour transition with readable contrast"

    base_excerpt = _normalize(base_prompt)[:600]

    return {
        "scene_setup": (
            f"1. SCENE SETUP: {aspect_label} framing in {environment}. "
            f"Camera angle: medium-wide establishing read with subject in lower two-thirds. "
            f"Lighting: {lighting}. Time of day: {time_of_day}. "
            f"Clip {clip_index} of {clip_count}. Exactly 10 seconds continuous motion. {base_excerpt}"
        ),
        "subject": (
            f"2. SUBJECT: {subject} — detailed appearance with {wardrobe}, natural skin and fabric texture, "
            f"expressive face readable at mobile resolution, micro-expressions showing {emotional_arc}. "
            f"Movement: purposeful motivated blocking — never static mannequin posing. "
            f"Silhouette and identity remain locked; no character replacement."
        ),
        "action": (
            f"3. ACTION: {_second_by_second_action(beat=beat or base_excerpt[:200], clip_index=clip_index)} "
            f"Primary story beat: {beat or base_excerpt[:180]}. "
            f"Hook detail: {visual_hook}. Conflict pressure: {conflict or 'stakes escalate visually'}."
        ),
        "camera_movement": (
            f"4. CAMERA MOVEMENT: {camera_base}. "
            "Motivated dolly or tracking move — gentle push-in for discovery, lateral track for escalation, "
            "controlled deceleration for payoff. No unmotivated whip pans or reverse blocking. "
            "Handheld drift only if it serves documentary urgency."
        ),
        "visual_style": (
            f"5. VISUAL STYLE: {visual_style}. {style_direction}. "
            "Color grade: cohesive cinematic teal-amber or naturalistic documentary grade — no random LUT shifts. "
            "Film stock look: premium digital with subtle grain, photoreal materials, no plastic CGI skin."
        ),
        "atmosphere": (
            f"6. ATMOSPHERE: Mood arc — {emotional_arc}. "
            f"Palette: {anchor.get('palette') or 'cohesive cinematic grade'}. "
            "Weather and particulates reinforce stakes without obscuring the subject. "
            "Sound design hints: ambient bed, subtle foley, environmental resonance — native in-scene audio only."
        ),
        "technical": (
            f"7. TECHNICAL: Aspect ratio {aspect_label}. Shallow depth of field — subject sharp, background soft. "
            "Lens: 35mm equivalent vertical Shorts personality. Frame rate feel: 24fps cinematic motion blur. "
            "Mobile-safe composition with headroom and no chin/forehead crop."
        ),
        "continuity": (
            f"8. CONTINUITY NOTE: {_continuity_note(clip_index=clip_index, clip_count=clip_count, aspect_label=aspect_label)} "
            f"{NEGATIVE_PROMPT_BLOCK}"
        ),
    }


def _assemble_sections(sections: dict[str, str]) -> str:
    order = (
        "scene_setup",
        "subject",
        "action",
        "camera_movement",
        "visual_style",
        "atmosphere",
        "technical",
        "continuity",
    )
    return _normalize(" ".join(sections[key] for key in order))


def enforce_prompt_length(
    prompt: str,
    *,
    clip_index: int = 1,
    clip_count: int = 3,
    sections: dict[str, str] | None = None,
) -> str:
    """Ensure prompt is 2400–2500 chars; expand subject/action/atmosphere or trim continuity."""
    if sections is None:
        text = _normalize(prompt)
        if len(text) >= TARGET_MIN_CHARS:
            if len(text) > TARGET_MAX_CHARS:
                trimmed = text[: TARGET_MAX_CHARS - len(NEGATIVE_PROMPT_BLOCK) - 2].rsplit(" ", 1)[0]
                return _normalize(f"{trimmed} {NEGATIVE_PROMPT_BLOCK}")
            return text
        return text

    working = dict(sections)
    text = _assemble_sections(working)

    subject_expanders = [
        "Additional subject detail: fabric weave, pore-level skin texture, eye catchlight, hair movement in ambient air.",
        "Expression shifts from curiosity to urgency — brows, breath, posture tell the story without dialogue.",
        "Wardrobe continuity: same garments, same wear patterns, same accessories in every frame.",
    ]
    action_expanders = [
        "Second-by-second escalation: hands interact with environment props; feet shift weight; gaze leads camera.",
        "Micro-beats within the 10 seconds: react, commit, follow-through — no idle filler frames.",
        "Cause-and-effect chain visible on screen — every motion motivates the next beat.",
    ]
    atmosphere_expanders = [
        "Atmospheric depth: haze layers, dust motes in light beams, distant environmental motion.",
        "Emotional temperature rises through color temperature shift and tighter framing pressure.",
        "Ambient sound implied: wind, distant traffic, nature bed, room tone — all native to the scene.",
    ]

    expand_index = 0
    while len(_assemble_sections(working)) < TARGET_MIN_CHARS and expand_index < 12:
        working["subject"] = _normalize(
            f"{working['subject']} {subject_expanders[expand_index % len(subject_expanders)]}"
        )
        working["action"] = _normalize(
            f"{working['action']} {action_expanders[expand_index % len(action_expanders)]}"
        )
        working["atmosphere"] = _normalize(
            f"{working['atmosphere']} {atmosphere_expanders[expand_index % len(atmosphere_expanders)]}"
        )
        expand_index += 1

    text = _assemble_sections(working)
    if len(text) > TARGET_MAX_CHARS:
        budget = max(120, len(working["continuity"]) - (len(text) - TARGET_MAX_CHARS))
        working["continuity"] = _normalize(working["continuity"][:budget].rsplit(" ", 1)[0] + f" {NEGATIVE_PROMPT_BLOCK}")
        text = _assemble_sections(working)

    if len(text) > TARGET_MAX_CHARS:
        text = text[: TARGET_MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."

    if len(text) < TARGET_MIN_CHARS:
        working["subject"] = _normalize(f"{working['subject']} {subject_expanders[0]} {subject_expanders[1]}")
        working["action"] = _normalize(f"{working['action']} {action_expanders[0]}")
        working["atmosphere"] = _normalize(f"{working['atmosphere']} {atmosphere_expanders[0]}")
        text = _assemble_sections(working)
        if len(text) > TARGET_MAX_CHARS:
            text = text[:TARGET_MAX_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "."

    return text


def expand_clip_prompt(
    *,
    base_prompt: str,
    clip_index: int,
    clip_count: int,
    beat: str = "",
    story_brief: Any | None = None,
    anchors: Any | None = None,
    visual_style: str = "cinematic realistic",
    aspect_label: str = "vertical 9:16",
    continuity_block: str = "",
) -> str:
    sections = build_structured_prompt_sections(
        base_prompt=base_prompt,
        clip_index=clip_index,
        clip_count=clip_count,
        beat=beat,
        story_brief=story_brief,
        anchors=anchors,
        visual_style=visual_style,
        aspect_label=aspect_label,
    )
    if continuity_block:
        sections["continuity"] = _normalize(f"8. CONTINUITY NOTE: {continuity_block} {NEGATIVE_PROMPT_BLOCK}")

    return enforce_prompt_length(
        "",
        clip_index=clip_index,
        clip_count=clip_count,
        sections=sections,
    )


def expand_starter_prompt(
    *,
    base_prompt: str,
    story_brief: Any | None = None,
    anchors: Any | None = None,
    visual_style: str = "cinematic realistic",
    aspect_label: str = "vertical 9:16",
) -> str:
    return expand_clip_prompt(
        base_prompt=base_prompt,
        clip_index=1,
        clip_count=1,
        beat=_brief_value(story_brief, "opening_hook") or _brief_value(story_brief, "visual_hook"),
        story_brief=story_brief,
        anchors=anchors,
        visual_style=visual_style,
        aspect_label=aspect_label,
        continuity_block=(
            "Hero starter frame for Use to Video chain — establish subject, environment, lighting, "
            "and wardrobe that all subsequent clips inherit."
        ),
    )


def average_prompt_length(prompts: list[str]) -> float:
    if not prompts:
        return 0.0
    return round(sum(len(p) for p in prompts) / len(prompts), 1)


__all__ = [
    "EXPANDER_VERSION",
    "TARGET_MAX_CHARS",
    "TARGET_MIN_CHARS",
    "average_prompt_length",
    "build_structured_prompt_sections",
    "enforce_prompt_length",
    "expand_clip_prompt",
    "expand_starter_prompt",
]
