"""YouTube category name → API categoryId mapping."""

from __future__ import annotations

YOUTUBE_CATEGORY_IDS: dict[str, str] = {
    "film & animation": "1",
    "autos & vehicles": "2",
    "music": "10",
    "pets & animals": "15",
    "sports": "17",
    "travel & events": "19",
    "gaming": "20",
    "people & blogs": "22",
    "comedy": "23",
    "entertainment": "24",
    "news & politics": "25",
    "howto & style": "26",
    "education": "27",
    "science & technology": "28",
    "nonprofits & activism": "29",
}


def resolve_youtube_category_id(category: str, *, default: str = "22") -> str:
    text = str(category or "").strip().lower()
    if text.isdigit():
        return text
    return YOUTUBE_CATEGORY_IDS.get(text, default)


__all__ = ["YOUTUBE_CATEGORY_IDS", "resolve_youtube_category_id"]
