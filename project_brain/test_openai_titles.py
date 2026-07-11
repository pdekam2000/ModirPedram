#!/usr/bin/env python3
"""Audit OpenAI SEO title generation for YouTube + Instagram ideation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from content_brain.execution.channel_story_ideation import apply_channel_story_ideation
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore


def _ideate(*, topic: str, platform: str, profile: dict, exclude_power_words: list[str] | None = None) -> dict:
    payload = {
        "topic_mode": "channel",
        "skip_story_memory_persist": True,
        "exclude_seo_power_words": list(exclude_power_words or []),
    }
    if platform == "youtube_shorts":
        style = str(profile.get("youtube_video_style") or profile.get("visual_style") or "cinematic")
        mood = str(profile.get("tone_style") or "mysterious")
        niche = str(profile.get("main_niche") or profile.get("sub_niche") or "science")
    else:
        style = str(profile.get("instagram_video_style") or "aesthetic")
        mood = str(profile.get("instagram_filter_mood") or profile.get("tone_style") or "warm")
        niche = str(profile.get("main_niche") or "skincare")

    return apply_channel_story_ideation(
        project_root=ROOT,
        payload=payload,
        channel_topic=topic,
        niche=niche,
        target_platform=platform,
        style=style,
        mood=mood,
        duration_seconds=30,
        clip_count=2,
    )


def main() -> int:
    profile = ProductChannelProfileStore(ROOT).load()
    openai_ready = bool(os.getenv("OPENAI_API_KEY", "").strip())
    print(f"OpenAI key: {'set' if openai_ready else 'MISSING — titles will fall back to local template'}")
    print()

    print("=" * 60)
    print("YOUTUBE — 5 title samples")
    print("=" * 60)
    used_power_words: list[str] = []
    youtube_openers: list[str] = []
    for i in range(5):
        result = _ideate(
            topic=str(profile.get("youtube_channel_topic") or profile.get("channel_topic") or ""),
            platform="youtube_shorts",
            profile=profile,
            exclude_power_words=used_power_words,
        )
        seo_meta = dict(result.get("seo_title_meta") or {})
        source = "openai" if seo_meta.get("openai_applied") else "local_fallback"
        power_word = str(seo_meta.get("power_word_used") or "")
        title = str(result.get("title", "NO TITLE"))
        opener = title.split(" ", 1)[0] if title else ""
        youtube_openers.append(opener)
        if power_word:
            used_power_words.append(power_word)
        print(f"{i + 1}. [{power_word}] {title}")
        print(f"   Source: {source}" + (f" ({seo_meta.get('openai_model')})" if seo_meta.get("openai_model") else ""))
        print(f"   Hook: {str(result.get('hook', ''))[:80]}")
        print()
    print(f"Unique openers: {len(set(youtube_openers))}/5 — {youtube_openers}")
    print()

    print("=" * 60)
    print("INSTAGRAM — 5 title samples")
    print("=" * 60)
    for i in range(5):
        result = _ideate(
            topic=str(profile.get("instagram_channel_brief") or profile.get("instagram_channel_topic") or ""),
            platform="instagram_reels",
            profile=profile,
        )
        seo_meta = dict(result.get("seo_title_meta") or {})
        source = "openai" if seo_meta.get("openai_applied") else "local_fallback"
        print(f"{i + 1}. {result.get('title', 'NO TITLE')}")
        print(f"   Source: {source}" + (f" ({seo_meta.get('openai_model')})" if seo_meta.get("openai_model") else ""))
        print(f"   Recipe: {str(result.get('hook', ''))[:80]}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
