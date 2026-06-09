"""
Phase I.5 — story progression validation for Runway 3-clip continuity.

Checks discovery → escalation → payoff beats while preserving continuity anchors.
"""

from __future__ import annotations

import re
from typing import Any

DISCOVERY_MARKERS: tuple[str, ...] = (
    "discover",
    "discovery",
    "notice",
    "notices",
    "turn",
    "turns",
    "alert",
    "spot",
    "signal",
    "first clue",
    "react",
)

ESCALATION_MARKERS: tuple[str, ...] = (
    "escalat",
    "advance",
    "advances",
    "walk",
    "walks",
    "track",
    "tracking",
    "intensif",
    "movement",
    "edge",
    "pressure",
    "pursu",
)

PAYOFF_MARKERS: tuple[str, ...] = (
    "payoff",
    "reveal",
    "reach",
    "reaches",
    "hand",
    "touch",
    "cradle",
    "decisive",
    "closes",
    "consequence",
    "final",
)

CONTINUITY_MARKERS: tuple[str, ...] = (
    "continuity lock",
    "same character",
    "same location",
    "wardrobe",
    "use frame",
    "use to video",
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = _normalize(text).lower()
    return any(marker in lowered for marker in markers)


def beats_are_unique(beats: list[str]) -> bool:
    cleaned = [_normalize(beat).lower() for beat in beats if _normalize(beat)]
    return len(cleaned) == len(set(cleaned))


def validate_clip_beat_progression(beats: list[str]) -> dict[str, bool]:
    if len(beats) < 3:
        return {
            "three_unique_beats": False,
            "discovery_present": False,
            "escalation_present": False,
            "payoff_present": False,
        }
    first, second, third = beats[0], beats[1], beats[2]
    return {
        "three_unique_beats": beats_are_unique(beats[:3]),
        "discovery_present": _contains_any(first, DISCOVERY_MARKERS),
        "escalation_present": _contains_any(second, ESCALATION_MARKERS),
        "payoff_present": _contains_any(third, PAYOFF_MARKERS),
    }


def validate_prompt_progression(bundle: Any) -> dict[str, bool]:
    prompts = list(getattr(bundle, "clip_prompts", []) or [])
    if len(prompts) < 3:
        return {
            "prompts_three_unique": False,
            "prompt_discovery_language": False,
            "prompt_escalation_language": False,
            "prompt_payoff_language": False,
            "continuity_preserved_all_clips": False,
        }
    return {
        "prompts_three_unique": beats_are_unique([_normalize(p) for p in prompts[:3]]),
        "prompt_discovery_language": _contains_any(prompts[0], DISCOVERY_MARKERS),
        "prompt_escalation_language": _contains_any(prompts[1], ESCALATION_MARKERS),
        "prompt_payoff_language": _contains_any(prompts[2], PAYOFF_MARKERS),
        "continuity_preserved_all_clips": all(
            _contains_any(prompt, CONTINUITY_MARKERS) for prompt in prompts[:3]
        ),
    }


def validate_story_progression(brief: Any, bundle: Any) -> dict[str, Any]:
    beats = list(getattr(brief, "clip_beats", []) or [])
    beat_checks = validate_clip_beat_progression(beats)
    prompt_checks = validate_prompt_progression(bundle)
    character = _normalize(getattr(brief, "main_character", "") or "")
    setting = _normalize(getattr(brief, "setting", "") or "")
    wardrobe = ""
    anchors = getattr(brief, "continuity_anchors", None)
    if anchors is not None:
        wardrobe = _normalize(getattr(anchors, "wardrobe", "") or "")

    prompts = list(getattr(bundle, "clip_prompts", []) or [])
    character_locked = bool(character) and all(
        character.lower() in _normalize(prompt).lower() for prompt in prompts[:3]
    ) if prompts else False
    setting_locked = bool(setting) and all(
        any(token in _normalize(prompt).lower() for token in setting.lower().split()[:3])
        for prompt in prompts[:3]
    ) if setting and prompts else bool(setting)

    return {
        **beat_checks,
        **prompt_checks,
        "character_locked": character_locked,
        "setting_locked": setting_locked,
        "wardrobe_locked": not wardrobe or all(
            "wardrobe" in _normalize(prompt).lower() for prompt in prompts[:3]
        ),
        "all_pass": (
            beat_checks["three_unique_beats"]
            and beat_checks["discovery_present"]
            and beat_checks["escalation_present"]
            and beat_checks["payoff_present"]
            and prompt_checks["continuity_preserved_all_clips"]
            and character_locked
        ),
    }


__all__ = [
    "DISCOVERY_MARKERS",
    "ESCALATION_MARKERS",
    "PAYOFF_MARKERS",
    "beats_are_unique",
    "validate_clip_beat_progression",
    "validate_prompt_progression",
    "validate_story_progression",
]
