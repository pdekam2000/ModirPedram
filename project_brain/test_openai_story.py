#!/usr/bin/env python3
"""Audit OpenAI story ideation + clip prompt generation (no video)."""

from __future__ import annotations

import json
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

PROFILE_PATH = ROOT / "project_brain" / "product_settings" / "channel_profile.json"


def _preview(text: str, limit: int = 200) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _run_platform_audit(*, label: str, topic: str, platform: str, profile: dict) -> None:
    from content_brain.execution.channel_story_ideation import ideate_and_persist_channel_story
    from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content
    from content_brain.story.kling_story_first_openai_writer import _resolve_system_prompt

    if platform == "youtube_shorts":
        style = str(profile.get("youtube_video_style") or profile.get("visual_style") or "cinematic")
    else:
        style = str(profile.get("instagram_video_style") or "aesthetic")

    mood = str(profile.get("tone_style") or profile.get("instagram_filter_mood") or "warm")
    niche = str(profile.get("main_niche") or profile.get("sub_niche") or "")

    print("=" * 72)
    print(label)
    print("=" * 72)
    print(f"Platform:     {platform}")
    print(f"Topic chars:  {len(topic)}")
    print(f"OpenAI key:   {'set' if os.getenv('OPENAI_API_KEY', '').strip() else 'MISSING — prompts may fall back to local template'}")
    print()

    ideation = ideate_and_persist_channel_story(
        project_root=ROOT,
        channel_topic=topic,
        niche=niche,
        target_platform=platform,
        style=style,
        mood=mood,
        duration_seconds=30,
        clip_count=2,
        persist=False,
    )

    idea = dict(ideation.get("channel_story_idea") or {})
    story_package = dict(ideation.get("story_package") or {})
    authoritative_topic = str(ideation.get("authoritative_topic") or idea.get("title") or topic)

    title = str(ideation.get("story_title") or idea.get("title") or "")
    hook = str(idea.get("visual_hook") or "")
    story = str(ideation.get("story_summary") or idea.get("logline") or "")

    print(f"Generated title:  {title}")
    print(f"Generated hook:   {_preview(hook, 300)}")
    print(f"Generated story:  {_preview(story, 400)}")
    print(f"Ideation version: {ideation.get('story_ideation_version') or idea.get('diversity_mode')}")
    if idea.get("novelty_tags"):
        print(f"Novelty tags:     {', '.join(str(t) for t in idea.get('novelty_tags', [])[:6])}")
    print()

    system_prompt_kind = "UNKNOWN"
    resolved = _resolve_system_prompt(
        topic=authoritative_topic[:500],
        target_platform=platform,
        platform=platform,
        genre=str(profile.get("genre") or ""),
        youtube_genre=str(profile.get("youtube_genre") or ""),
        instagram_genre=str(profile.get("instagram_genre") or ""),
        tiktok_genre=str(profile.get("tiktok_genre") or ""),
        niche=niche,
    ).lower()
    if "skincare tutorial" in resolved or "skincare-tutorial" in resolved:
        system_prompt_kind = "BEAUTY"
    elif "science fact" in resolved or "science-documentary" in resolved:
        system_prompt_kind = "SCIENCE"
    else:
        system_prompt_kind = "COMEDY/OTHER"
    print(f"OpenAI system prompt branch (inferred): {system_prompt_kind}")
    print()

    plan = plan_kling_frame_to_video_content(
        topic=authoritative_topic,
        story_package=story_package,
        story_summary=story,
        platform=platform,
        planned_duration_seconds=30,
        clip_count=2,
        mood=mood,
        style=style,
        characters=[str(idea.get("main_character") or "presenter")],
        environment=str(idea.get("setting") or ""),
        youtube_genre=str(profile.get("youtube_genre") or ""),
        instagram_genre=str(profile.get("instagram_genre") or ""),
        tiktok_genre=str(profile.get("tiktok_genre") or ""),
        genre=str(profile.get("genre") or ""),
    )

    for clip in plan.clips:
        authorship = dict((clip.chapter_progression or {}).get("prompt_authorship") or {})
        source = str(authorship.get("source") or "unknown")
        model = str(authorship.get("openai_model") or "")
        prompt = str(clip.prompt or "")
        print(f"--- Clip {clip.clip_index} ---")
        print(f"Prompt source:  {source}" + (f" ({model})" if model else ""))
        print(f"Char count:     {len(prompt)}")
        print(f"First 200 chars: {_preview(prompt, 200)}")
        if authorship.get("validation_errors"):
            print(f"Validation:     {authorship.get('validation_errors')}")
        print()


def main() -> int:
    profile = _load_profile()

    youtube_topic = str(profile.get("youtube_channel_topic") or profile.get("channel_topic") or "").strip()
    instagram_topic = str(profile.get("instagram_channel_brief") or profile.get("instagram_channel_topic") or "").strip()

    if not youtube_topic:
        print("ERROR: youtube_channel_topic is empty in channel_profile.json")
        return 1
    if not instagram_topic:
        print("ERROR: instagram_channel_brief is empty in channel_profile.json")
        return 1

    print("OpenAI Story + Prompt Audit")
    print(f"Profile: {PROFILE_PATH}")
    print()

    _run_platform_audit(
        label="YOUTUBE — channel_story_ideation + OpenAI clip prompts",
        topic=youtube_topic,
        platform="youtube_shorts",
        profile=profile,
    )

    _run_platform_audit(
        label="INSTAGRAM — channel_story_ideation + OpenAI clip prompts",
        topic=instagram_topic,
        platform="instagram_reels",
        profile=profile,
    )

    print("Done. No video generation was triggered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
