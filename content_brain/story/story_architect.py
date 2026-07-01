"""Story Architect — full narrative arc before screenwriting and production."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.story.story_niche import detect_genre

STORY_ARCHITECT_VERSION = "story_architect_v1"

ARC_BEATS = ("hook", "setup", "conflict", "discovery", "escalation", "climax", "resolution", "ending_cta")


@dataclass
class StoryBlueprint:
    title: str
    genre: str
    hook: str
    setup: str
    conflict: str
    discovery: str
    escalation: str
    climax: str
    resolution: str
    ending_cta: str
    scene_progression: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STORY_ARCHITECT_VERSION,
            "title": self.title,
            "genre": self.genre,
            "hook": self.hook,
            "setup": self.setup,
            "conflict": self.conflict,
            "discovery": self.discovery,
            "escalation": self.escalation,
            "climax": self.climax,
            "resolution": self.resolution,
            "ending_cta": self.ending_cta,
            "scene_progression": list(self.scene_progression),
            "metadata": dict(self.metadata),
        }


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _templates(genre: str) -> dict[str, str]:
    if genre == "cartoon":
        return {
            "title": "Whiskers and the Hidden Spark",
            "hook": "A tiny orange explorer spots something impossible glowing beneath the vines.",
            "setup": "Whiskers the cat and Sage the fox enter a sunlit jungle path full of wonder.",
            "conflict": "The trail splits, the ground trembles, and the glow disappears behind ancient stones.",
            "discovery": "They uncover a crystal seed that hums with warm golden light.",
            "escalation": "Shadows stretch, roots shift, and the path home starts to vanish.",
            "climax": "Whiskers must choose courage over fear to carry the spark to safety.",
            "resolution": "The jungle brightens as the spark blooms into a bridge of light.",
            "ending_cta": "Follow for more magical adventures with Whiskers and Sage.",
        }
    if genre == "wildlife":
        return {
            "title": "Echoes on the Ridge",
            "hook": "At dawn, a lone wolf hears a call no map has ever recorded.",
            "setup": "She crosses misty ridges toward a valley hidden from human eyes.",
            "conflict": "A rival pack blocks the only pass before nightfall.",
            "discovery": "She finds a sheltered spring that could save her family.",
            "escalation": "Storm winds rise and the pass crumbles under her paws.",
            "climax": "She leads with a howl that turns fear into unity.",
            "resolution": "Both packs drink together as the storm breaks.",
            "ending_cta": "Subscribe for more wild journeys.",
        }
    if genre == "technology":
        return {
            "title": "Signal in the Static",
            "hook": "A dormant drone wakes to a message buried in cosmic noise.",
            "setup": "Engineers trace the ping to a forgotten orbital relay.",
            "conflict": "Power fails and the window to respond closes in minutes.",
            "discovery": "The signal carries coordinates to a missing colony ship.",
            "escalation": "Solar flare risk threatens every system online.",
            "climax": "They reroute through a manual antenna at the last second.",
            "resolution": "The colony answers — alive, waiting, grateful.",
            "ending_cta": "Follow for more future-tech stories.",
        }
    if genre == "history":
        return {
            "title": "The Lantern at the Gate",
            "hook": "A merchant sees the city gates close before the festival begins.",
            "setup": "Crowds gather while rumors of invasion spread through the market.",
            "conflict": "Guards refuse entry without a seal no one can find.",
            "discovery": "An old lantern reveals a hidden passage under the wall.",
            "escalation": "Invaders reach the outer fields as drums grow louder.",
            "climax": "The merchant lights the lantern and opens the gate for refugees.",
            "resolution": "The city survives the night united.",
            "ending_cta": "Follow for more historical tales.",
        }
    if genre == "horror":
        return {
            "title": "The Room That Breathes",
            "hook": "Every night at 3:07, the hallway exhales cold air.",
            "setup": "Mara returns to her childhood home to settle an estate.",
            "conflict": "Doors unlock themselves and whispers mimic her voice.",
            "discovery": "A mirror shows a second house layered beneath the first.",
            "escalation": "The breathing grows louder, closer, hungry.",
            "climax": "Mara faces the reflection and speaks her true name.",
            "resolution": "Silence returns — but the mirror still fogs when she passes.",
            "ending_cta": "Follow for more dark stories.",
        }
    return {
        "title": "Questions in the Light",
        "hook": "A curious student notices a pattern no textbook explains.",
        "setup": "In a bright lab, simple tools reveal a surprising result.",
        "conflict": "The experiment fails twice and doubt spreads.",
        "discovery": "A tiny change in temperature unlocks the answer.",
        "escalation": "Time runs out before the science fair.",
        "climax": "They present the finding with clear, honest proof.",
        "resolution": "Understanding spreads and questions multiply.",
        "ending_cta": "Follow for more learning adventures.",
    }


def build_story_blueprint(
    *,
    topic: str,
    clip_count: int = 3,
    story_brief: dict[str, Any] | None = None,
    genre: str = "",
) -> StoryBlueprint:
    brief = dict(story_brief or {})
    resolved_genre = str(genre or brief.get("genre") or detect_genre(topic, brief)).lower()
    if resolved_genre not in {"cartoon", "wildlife", "technology", "history", "horror", "educational"}:
        resolved_genre = detect_genre(topic, brief)

    template = _templates(resolved_genre)
    clip_beats = [_clean(str(item)) for item in (brief.get("clip_beats") or []) if _clean(str(item))]
    title = _clean(brief.get("title") or "")
    if not title and topic:
        title = _clean(topic.split(".")[0][:96])
    if not title:
        title = template["title"]
    if topic and title == template["title"] and resolved_genre != "cartoon":
        title = _clean(topic.split(".")[0][:96]) or title

    progression = [str(item) for item in (brief.get("scene_progression") or []) if str(item).strip()]
    if clip_beats:
        progression = clip_beats
    elif not progression:
        progression = [
            template["hook"],
            template["conflict"],
            template["climax"],
            template["resolution"],
        ]
    progression = progression[: max(clip_count, 3)]

    hook = _clean(brief.get("hook") or (clip_beats[0] if clip_beats else template["hook"]))
    conflict = _clean(brief.get("conflict") or (clip_beats[1] if len(clip_beats) > 1 else template["conflict"]))
    discovery = _clean(brief.get("discovery") or (clip_beats[2] if len(clip_beats) > 2 else template["discovery"]))
    escalation = _clean(brief.get("escalation") or (clip_beats[3] if len(clip_beats) > 3 else template["escalation"]))
    climax = _clean(brief.get("climax") or (clip_beats[-2] if len(clip_beats) > 1 else template["climax"]))
    resolution = _clean(brief.get("resolution") or (clip_beats[-1] if clip_beats else template["resolution"]))

    return StoryBlueprint(
        title=title,
        genre=resolved_genre,
        hook=hook,
        setup=_clean(brief.get("setup") or template["setup"]),
        conflict=conflict,
        discovery=discovery,
        escalation=escalation,
        climax=climax,
        resolution=resolution,
        ending_cta=_clean(brief.get("ending_cta") or template["ending_cta"]),
        scene_progression=progression,
        metadata={
            "topic": topic,
            "clip_count": clip_count,
            "source_brief_keys": sorted(brief.keys()),
            "topic_authoritative": bool(topic),
            "clip_beats_used": bool(clip_beats),
        },
    )


__all__ = ["ARC_BEATS", "STORY_ARCHITECT_VERSION", "StoryBlueprint", "build_story_blueprint"]
