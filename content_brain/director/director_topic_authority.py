"""Director Layer — topic authority guard."""

from __future__ import annotations

import re
from typing import Any

from content_brain.execution.content_brain_topic_authority import (
    FORBIDDEN_TOPIC_DRIFT,
    audit_story_brief_preservation,
    audit_topic_preservation,
)

DIRECTOR_FORBIDDEN_DRIFT: tuple[str, ...] = FORBIDDEN_TOPIC_DRIFT + (
    "gpu",
    "graphics card",
    "gaming",
    "tech lab",
    "server room",
    "cyber cafe",
    "esports",
    "video game",
    "technology",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _topic_tokens(topic: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _normalize(topic)) if len(token) >= 3}


def audit_director_topic_authority(
    *,
    topic: str,
    storyboard: dict[str, Any],
    scene_breakdown: dict[str, Any] | None = None,
) -> dict[str, Any]:
    combined_text = " ".join(str(storyboard.get(key, "")) for key in (
        "title", "logline", "main_character", "setting", "visual_style", "emotional_arc",
    ))
    for clip in storyboard.get("clips") or []:
        if isinstance(clip, dict):
            combined_text += " " + " ".join(str(clip.get(k, "")) for k in clip)
    if scene_breakdown:
        for clip in scene_breakdown.get("clips") or []:
            if not isinstance(clip, dict):
                continue
            for scene in clip.get("scenes") or []:
                if isinstance(scene, dict):
                    combined_text += " " + " ".join(str(scene.get(k, "")) for k in scene)

    topic_audit = audit_topic_preservation(topic, generated_texts=[combined_text])
    brief_audit = audit_story_brief_preservation(topic, storyboard)
    lowered = _normalize(combined_text)
    drift_hits = [term for term in DIRECTOR_FORBIDDEN_DRIFT if term in lowered and term not in _normalize(topic)]
    topic_hits = _topic_tokens(topic)
    topic_present = any(token in lowered for token in topic_hits) if topic_hits else topic_audit.topic_preservation_score >= 0.5

    score = max(float(topic_audit.topic_preservation_score), float(brief_audit.topic_preservation_score))
    if drift_hits:
        score = min(score, 0.35)
    if topic_present and not drift_hits:
        score = max(score, 0.85)

    passed = bool(topic_present and not drift_hits and score >= 0.7)
    return {
        "pass": passed,
        "score": round(score, 3),
        "topic_present": topic_present,
        "drift_hits": drift_hits,
        "topic_audit": topic_audit.to_dict(),
        "brief_audit": brief_audit.to_dict(),
    }
