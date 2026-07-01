"""Cinematic prompt expansion — rich multi-section clip prompts (2000–4000 chars)."""

from __future__ import annotations

import re
from typing import Any

EXPANDER_VERSION = "cinematic_prompt_expander_v1"
TARGET_MIN_CHARS = 2000
TARGET_MAX_CHARS = 4000

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
    anchor = _anchors_dict(anchors)
    subject = _brief_value(story_brief, "subject") or _brief_value(story_brief, "main_character") or anchor.get("character", "")
    environment = _brief_value(story_brief, "environment") or _brief_value(story_brief, "setting") or anchor.get("location", "")
    conflict = _brief_value(story_brief, "conflict") or _brief_value(story_brief, "conflict_tension", "")
    stakes = _brief_value(story_brief, "stakes", conflict)
    emotional_arc = _brief_value(story_brief, "emotional_arc", "")
    visual_hook = _brief_value(story_brief, "visual_hook", "")
    style_direction = _brief_value(story_brief, "style_direction", visual_style)

    sections = {
        "A_subject": (
            f"SUBJECT BLOCK: Primary subject {subject} remains the unmistakable hero of every frame. "
            f"Anatomy, silhouette, wardrobe ({anchor.get('wardrobe') or 'consistent outfit'}), and emotional intent stay locked. "
            f"Story beat: {beat or base_prompt[:240]}."
        ),
        "B_environment": (
            f"ENVIRONMENT BLOCK: Single continuous location — {environment}. "
            "Depth layers: foreground texture, mid-ground action plane, background atmosphere with readable vertical framing. "
            "Weather, particulates, and set dressing remain coherent across the full 10 seconds."
        ),
        "C_lighting": (
            f"LIGHTING BLOCK: {anchor.get('lighting') or 'motivated cinematic key with stable direction'}. "
            "Practical sources motivate shadows; rim light separates subject from background; "
            "no random exposure shifts or white-balance drift between seconds."
        ),
        "D_camera": (
            f"CAMERA BLOCK: {anchor.get('camera') or '35mm cinematic vertical lens personality'}. "
            "Framing: subject occupies lower two-thirds with headroom for Shorts safe zone. "
            "Depth of field: subject sharp, background softly separated. "
            "Camera movement must feel motivated and continuous — no unmotivated whip pans."
        ),
        "E_motion": (
            "MOTION BLOCK: Seconds 0–2 establish micro-movement and continuity read; "
            "seconds 2–7 execute the primary motivated action without hard cuts; "
            "seconds 7–10 decelerate into a stable end pose for Use Frame handoff. "
            "Motion direction flows forward through the scene — no reverse blocking."
        ),
        "F_atmosphere": (
            f"ATMOSPHERE BLOCK: Mood arc — {emotional_arc or 'rising cinematic tension'}. "
            f"Palette: {anchor.get('palette') or 'cohesive cinematic grade'}. "
            "Air density, haze, and environmental motion reinforce stakes without obscuring the subject."
        ),
        "G_visual_detail": (
            f"VISUAL DETAIL BLOCK: Material fidelity on skin, fabric, and surfaces. "
            f"Hook detail: {visual_hook or 'one scroll-stopping focal element'}. "
            f"Conflict pressure: {conflict}. Stakes if unresolved: {stakes}. "
            "Textures readable at mobile resolution; no mushy CGI plastic skin."
        ),
        "H_continuity": continuity_block or (
            f"CONTINUITY BLOCK: Same subject, same environment, same lighting vector, same camera language, "
            f"same composition grammar as prior clips. {aspect_label} {style_direction}."
        ),
        "I_style": (
            f"STYLE BLOCK: {visual_style}. {style_direction}. "
            "Cinematic references: premium documentary realism, motivated blocking, naturalistic performance energy. "
            "Vertical Shorts composition with subject never cropped at chin or forehead."
        ),
        "J_negative": NEGATIVE_PROMPT_BLOCK,
    }

    header = _normalize(
        f"Clip {clip_index} of {clip_count}. Exactly 10 seconds continuous on-screen motion. "
        f"{_normalize(base_prompt)[:900]}"
    )
    body = " ".join(sections.values())
    expanded = _normalize(f"{header} {body}")

    filler_snippets = [
        "Maintain photoreal edge detail and stable horizon orientation.",
        "Preserve eyeline continuity and screen-direction consistency.",
        "Keep background architecture and props spatially anchored.",
        "Allow only story-energy escalation — never world identity change.",
        "End frame holds readable pose for seamless Use Frame transition.",
    ]
    index = 0
    while len(expanded) < TARGET_MIN_CHARS and index < 24:
        expanded = _normalize(f"{expanded} {filler_snippets[index % len(filler_snippets)]}")
        index += 1

    if len(expanded) > TARGET_MAX_CHARS:
        expanded = expanded[: TARGET_MAX_CHARS - len(NEGATIVE_PROMPT_BLOCK) - 2].rstrip()
        expanded = _normalize(f"{expanded} {NEGATIVE_PROMPT_BLOCK}")

    return expanded


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
            "CONTINUITY BLOCK: Hero starter frame for Use to Video chain — "
            "establish subject, environment, lighting, and wardrobe that all subsequent clips inherit."
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
    "expand_clip_prompt",
    "expand_starter_prompt",
]
