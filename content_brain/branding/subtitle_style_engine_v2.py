"""Subtitle style v2 — viral Shorts styling with highlights, emoji, accent colors."""

from __future__ import annotations

import re
from typing import Any

from content_brain.branding.subtitle_format_engine import (
    HIGHLIGHT_COLOURS_BGR,
    PREFERRED_BURN_FONT_SIZE,
    break_cue_into_short_lines,
    normalize_platform,
)

SUBTITLE_STYLE_V2_VERSION = "subtitle_style_engine_v2"

ACCENT_WORDS = {
    "whoa",
    "wow",
    "look",
    "hear",
    "see",
    "go",
    "did",
    "that",
    "magic",
    "spark",
    "glowing",
    "jungle",
}

EMOJI_BY_EMOTION: dict[str, str] = {
    "surprise": "WOW",
    "excitement": "GO",
    "joy": "YAY",
    "fear": "WAIT",
    "curiosity": "LOOK",
    "tension": "SHH",
    "relief": "YES",
}


def _strip_speaker_prefix(text: str) -> str:
    cleaned = re.sub(r"^[^\w\s]+\s*", "", str(text or "").strip())
    return re.sub(r"^[A-Za-z][A-Za-z0-9 _-]{0,20}:\s*", "", cleaned).strip()


def _highlight_word(word: str, colour_index: int) -> str:
    clean = re.sub(r"[^\w!?']", "", word)
    if clean.lower() not in ACCENT_WORDS and "!" not in word:
        return word
    colour = HIGHLIGHT_COLOURS_BGR[colour_index % len(HIGHLIGHT_COLOURS_BGR)]
    return f"{{\\c{colour}&}}{word}{{\\c&H00FFFFFF&}}"


def _style_line_for_ass(text: str, *, emotion: str = "", add_emoji: bool = True) -> str:
    plain = _strip_speaker_prefix(text)
    words = plain.split()
    styled_words = [_highlight_word(word, index) for index, word in enumerate(words)]
    line = " ".join(styled_words)
    if add_emoji:
        prefix = EMOJI_BY_EMOTION.get(str(emotion or "").lower(), "")
        if prefix and prefix not in line.upper():
            line = f"{prefix}! {line}"
    return line


def style_srt_content_v2(
    raw_srt: str,
    *,
    platform: str = "tiktok",
    emotion_by_index: dict[int, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return ASS-friendly styled cues with highlight tags preserved for burn pipeline."""
    platform_key = normalize_platform(platform)
    emotion_by_index = emotion_by_index or {}
    blocks = re.split(r"\n\s*\n", raw_srt.strip())
    out_blocks: list[str] = []
    cue_index = 1
    styled_cues: list[dict[str, Any]] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        timing = lines[1]
        text = "\n".join(lines[2:])
        emotion = emotion_by_index.get(cue_index - 1, "curiosity")
        short_lines = break_cue_into_short_lines(_strip_speaker_prefix(text), platform=platform_key)
        if not short_lines:
            continue
        styled = [_style_line_for_ass(line, emotion=emotion) for line in short_lines]
        formatted = "\n".join(styled)
        out_blocks.extend([str(cue_index), timing, formatted, ""])
        styled_cues.append({"cue_index": cue_index, "emotion": emotion, "styled_text": formatted})
        cue_index += 1

    meta = {
        "version": SUBTITLE_STYLE_V2_VERSION,
        "platform": platform_key,
        "font_size": PREFERRED_BURN_FONT_SIZE + 4,
        "highlight_colours": list(HIGHLIGHT_COLOURS_BGR),
        "emoji_enabled": True,
        "pop_animation": "karaoke_emphasis",
        "cue_count": max(0, cue_index - 1),
        "styled_cues": styled_cues,
    }
    return "\n".join(out_blocks).strip() + "\n", meta


def style_plain_srt_for_drawtext(raw_srt: str, *, platform: str = "tiktok") -> tuple[str, dict[str, Any]]:
    """Plain-text viral styling for drawtext burn — ASCII emphasis only."""
    platform_key = normalize_platform(platform)
    blocks = re.split(r"\n\s*\n", raw_srt.strip())
    out_blocks: list[str] = []
    cue_index = 1
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        timing = lines[1]
        text = _strip_speaker_prefix(" ".join(lines[2:]).strip())
        upper_bits = []
        for word in text.split():
            if re.sub(r"[^\w]", "", word).lower() in ACCENT_WORDS:
                upper_bits.append(word.upper())
            else:
                upper_bits.append(word)
        styled = " ".join(upper_bits)
        if "!" not in styled and any(w in styled.upper() for w in ("WHOA", "WOW", "LOOK")):
            styled = styled.rstrip(".") + "!"
        if cue_index == 1 and not styled.upper().startswith("WOW"):
            styled = f"WOW! {styled}"
        out_blocks.extend([str(cue_index), timing, styled, ""])
        cue_index += 1
    meta = {
        "version": SUBTITLE_STYLE_V2_VERSION,
        "platform": platform_key,
        "drawtext_mode": True,
        "cue_count": max(0, cue_index - 1),
    }
    return "\n".join(out_blocks).strip() + "\n", meta


__all__ = [
    "ACCENT_WORDS",
    "EMOJI_BY_EMOTION",
    "SUBTITLE_STYLE_V2_VERSION",
    "style_plain_srt_for_drawtext",
    "style_srt_content_v2",
]
