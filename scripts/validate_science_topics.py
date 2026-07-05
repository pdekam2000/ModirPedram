"""Validate fresh YouTube science topic generation (no publish)."""

from __future__ import annotations

import json
from pathlib import Path

from content_brain.automation.platform_upload_guard import validate_topic_for_platform
from content_brain.execution.channel_story_ideation import generate_channel_story_idea
from content_brain.execution.youtube_science_channel import get_youtube_channel_topic_text
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    profile = ProductChannelProfileStore(root).load()
    ig = profile.get("instagram_channel_topic") or ""
    yt = profile.get("youtube_channel_topic") or ""

    print("=== PROFILE CHECK ===")
    print("YouTube channel:", profile.get("channel_name"))
    print("YouTube topic starts:", yt[:80])
    print("Instagram topic starts:", ig[:80])
    print(
        "Instagram unchanged (skincare):",
        "skincare" in ig.lower() and "Science That Feels Impossible" not in ig,
    )
    print()

    topics = []
    for i in range(10):
        idea = generate_channel_story_idea(
            channel_topic=get_youtube_channel_topic_text(),
            niche="Science That Feels Impossible",
            target_platform="youtube_shorts",
            style="premium cinematic science documentary",
            mood="intellectual wonder",
            duration_seconds=30,
            clip_count=2,
            attempt_offset=i * 3,
        )
        ok, reason = validate_topic_for_platform("youtube_shorts", idea.title + " " + idea.logline)
        topics.append(
            {
                "title": idea.title,
                "hook": idea.visual_hook.split(" — ")[0] if " — " in idea.visual_hook else idea.visual_hook[:80],
                "pillar": idea.novelty_tags[0] if idea.novelty_tags else "",
                "presenter": "female science presenter" in idea.main_character.lower(),
                "guard_ok": ok,
                "guard_reason": reason,
            }
        )

    print("=== 10 FRESH YOUTUBE TOPICS ===")
    for n, t in enumerate(topics, 1):
        print(f"{n}. {t['title']}")
        print(f"   hook: {t['hook'][:70]}")
        print(f"   pillar: {t['pillar']} | presenter: {t['presenter']} | guard: {t['guard_ok']}")

    bad = [
        t
        for t in topics
        if any(x in t["title"].lower() for x in ("animal", "skincare", "dark fantasy", "husky"))
    ]
    print("Old niche leaks:", len(bad))

    out = root / "project_brain" / "validation_science_topics.json"
    out.write_text(json.dumps(topics, indent=2), encoding="utf-8")
    print("Wrote", out)


if __name__ == "__main__":
    main()
