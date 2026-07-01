"""Genre detection and niche templates for story/audio directors."""

from __future__ import annotations

import re
from typing import Any

SUPPORTED_GENRES = ("cartoon", "wildlife", "technology", "history", "horror", "educational")
HUMAN_NARRATIVE_MARKERS = (
    "boy",
    "girl",
    "man",
    "woman",
    "child",
    "dragon",
    "person",
    "human",
    "finds",
    "hides",
    "forest",
)

GENRE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cartoon": ("cartoon", "cat", "kitten", "cute", "animated", "explorer", "magical", "fairy"),
    "wildlife": ("wildlife", "lion", "wolf", "bear", "safari", "habitat", "nature documentary"),
    "technology": ("technology", "robot", "ai", "software", "computer", "cyber", "future"),
    "history": ("history", "ancient", "medieval", "war", "empire", "past", "century"),
    "horror": ("horror", "ghost", "haunted", "dark", "nightmare", "creepy", "monster"),
    "educational": ("learn", "education", "science", "how to", "explained", "tutorial", "facts"),
}


def detect_genre(topic: str, story_brief: dict[str, Any] | None = None) -> str:
    haystack = " ".join(
        [
            str(topic or ""),
            str((story_brief or {}).get("title") or ""),
            str((story_brief or {}).get("main_character") or ""),
            str((story_brief or {}).get("setting") or ""),
            " ".join(str(item) for item in ((story_brief or {}).get("scene_progression") or [])),
        ]
    ).lower()
    scores: dict[str, int] = {genre: 0 for genre in SUPPORTED_GENRES}
    for genre, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in haystack or re.search(rf"\b{re.escape(keyword)}\b", haystack):
                scores[genre] += 1
    best = max(scores.items(), key=lambda item: item[1])
    if best[1] > 0:
        if best[0] == "cartoon" and any(marker in haystack for marker in HUMAN_NARRATIVE_MARKERS):
            if "cartoon" not in haystack and "animated" not in haystack:
                non_cartoon = sorted(
                    ((genre, score) for genre, score in scores.items() if genre != "cartoon" and score > 0),
                    key=lambda item: item[1],
                    reverse=True,
                )
                if non_cartoon:
                    return non_cartoon[0][0]
                return "educational"
        return best[0]
    return "cartoon" if any(k in haystack for k in ("cat", "animated", "cute")) else "educational"


__all__ = ["GENRE_KEYWORDS", "SUPPORTED_GENRES", "detect_genre"]
