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
    "cartoon": ("cartoon", "kitten", "cute", "animated", "whiskers", "magical", "fairy"),
    "wildlife": ("wildlife", "lion", "wolf", "bear", "safari", "habitat", "nature documentary"),
    "technology": ("technology", "robot", "software", "computer", "cyber", "future"),
    "history": ("history", "ancient", "medieval", "war", "empire", "past", "century"),
    "horror": ("horror", "ghost", "haunted", "dark", "nightmare", "creepy", "monster"),
    "educational": ("learn", "education", "science", "how to", "explained", "tutorial", "facts"),
}


def _keyword_matches(haystack: str, keyword: str) -> bool:
    """Match whole words/phrases only — avoid 'cat' inside 'technician'."""
    pattern = rf"\b{re.escape(keyword)}\b"
    return bool(re.search(pattern, haystack, flags=re.IGNORECASE))


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
            if _keyword_matches(haystack, keyword):
                scores[genre] += 1
    best = max(scores.items(), key=lambda item: item[1])
    if best[1] > 0:
        if best[0] == "cartoon" and any(_keyword_matches(haystack, marker) for marker in HUMAN_NARRATIVE_MARKERS):
            if not _keyword_matches(haystack, "cartoon") and not _keyword_matches(haystack, "animated"):
                non_cartoon = sorted(
                    ((genre, score) for genre, score in scores.items() if genre != "cartoon" and score > 0),
                    key=lambda item: item[1],
                    reverse=True,
                )
                if non_cartoon:
                    return non_cartoon[0][0]
                return "educational"
        return best[0]
    if _keyword_matches(haystack, "cat") or _keyword_matches(haystack, "animated") or _keyword_matches(haystack, "cute"):
        return "cartoon"
    return "educational"


__all__ = ["GENRE_KEYWORDS", "SUPPORTED_GENRES", "detect_genre"]
