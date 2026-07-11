"""Platform metadata agent — OpenAI primary with rule-based fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from content_brain.publish.youtube_metadata_generator import (
    INSTAGRAM_BASE_HASHTAGS,
    build_upload_youtube_description,
    _build_hashtags,
)
from content_brain.upload.upload_models import (
    PLATFORM_INSTAGRAM,
    PLATFORM_TIKTOK,
    PLATFORM_YOUTUBE,
    PRIVACY_PRIVATE,
)

PLATFORM_METADATA_AGENT_VERSION = "platform_metadata_agent_v2_structured_captions"

YOUTUBE_CATEGORY_DEFAULT = "Science & Technology"


def _slug_hashtags(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        if not text.startswith("#"):
            text = f"#{text.lstrip('#')}"
        cleaned.append(text)
    return cleaned


def _topic_words(topic: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", str(topic or "").lower())
    return [word for word in words if len(word) > 2][:6]


def _dedupe_hashtags(items: list[str], *, max_count: int = 25) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        raw = str(item or "").strip().lstrip("#")
        if not raw:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(f"#{raw}")
        if len(cleaned) >= max_count:
            break
    return cleaned


def _parse_instagram_recipe_fields(
    video_topic: str,
    narration_script: str,
) -> tuple[str, str]:
    text = f"{video_topic}\n{narration_script}"
    benefit_match = re.search(r"Benefits?:\s*([^.\n]+)", text, flags=re.IGNORECASE)
    skin_benefit = benefit_match.group(1).strip() if benefit_match else "healthy glow and smoother skin"

    ingredients_match = re.search(r"You need\s+([^.\n]+)", text, flags=re.IGNORECASE)
    if ingredients_match:
        ingredients = ingredients_match.group(1).strip()
    else:
        teaches_match = re.search(r"teaches\s+([^—\-]+)\s*[—\-]\s*([^.\n]+)", text, flags=re.IGNORECASE)
        if teaches_match:
            ingredients = teaches_match.group(2).strip()
        else:
            ingredients = "natural pantry ingredients shown in the reel"
    return ingredients, skin_benefit


def _build_instagram_hashtags(video_topic: str) -> list[str]:
    tags = list(INSTAGRAM_BASE_HASHTAGS)
    tags.extend(_slug_hashtags(_topic_words(video_topic)))
    return _dedupe_hashtags(tags, max_count=25)


def _rule_based_youtube(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    narration_script: str,
    content_language: str,
) -> dict[str, Any]:
    channel = str(channel_profile.get("channel_name") or "Channel").strip()
    title = str(video_topic or channel_profile.get("channel_topic") or "Short").strip()[:95]
    description = build_upload_youtube_description(
        video_topic=video_topic,
        channel_profile=channel_profile,
        narration_script=narration_script,
    )
    hashtags = _build_hashtags(topic=video_topic, channel_profile=channel_profile, is_short=True)
    tags = _topic_words(video_topic) + ["shorts", "science facts", "mind blowing", channel.lower()]
    pinned = (
        "Thanks for watching! What should we cover next?\n"
        f"👍 Like if this blew your mind!\n"
        f"🔔 Subscribe to {channel} for daily science facts."
    )
    if narration_script:
        pinned = f"{pinned}\n\nKey takeaway: {narration_script[:180].strip()}..."
    return {
        "platform": PLATFORM_YOUTUBE,
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": sorted(set(tags))[:15],
        "category": YOUTUBE_CATEGORY_DEFAULT,
        "privacy": str(channel_profile.get("youtube_privacy") or PRIVACY_PRIVATE),
        "thumbnail_text": title[:40],
        "pinned_comment": pinned,
        "source": "rule_based",
        "language": content_language,
    }


def _rule_based_tiktok(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    content_language: str,
) -> dict[str, Any]:
    hook = f"POV: {video_topic}"[:100]
    caption = f"{video_topic} — follow for more {channel_profile.get('main_niche', 'tips')}."
    hashtags = _slug_hashtags(["fyp", "foryou", "viral"] + _topic_words(video_topic))
    return {
        "platform": PLATFORM_TIKTOK,
        "caption": caption,
        "hashtags": hashtags,
        "cover_text": str(video_topic or "Watch this")[:32],
        "hook_text": hook,
        "pinned_comment": f"What part of {video_topic} should we explain next?",
        "source": "rule_based",
        "language": content_language,
    }


def _rule_based_instagram(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    narration_script: str = "",
    content_language: str,
) -> dict[str, Any]:
    channel = str(channel_profile.get("channel_name") or "our skincare page").strip()
    ingredients, skin_benefit = _parse_instagram_recipe_fields(video_topic, narration_script)
    hashtags = _build_instagram_hashtags(video_topic)
    caption = (
        f"{video_topic}\n\n"
        f"🧴 Ingredients:\n{ingredients}\n\n"
        f"✨ Skin benefit: {skin_benefit}\n\n"
        f"👀 Follow {channel} for daily skincare recipes!\n\n"
        f"{' '.join(hashtags)}"
    )
    return {
        "platform": PLATFORM_INSTAGRAM,
        "caption": caption,
        "hashtags": hashtags,
        "alt_text": f"Skincare reel about {video_topic} from {channel}.",
        "cover_text": str(video_topic or "Reel")[:32],
        "pinned_comment": f"Save this reel for {skin_benefit}. What recipe should we post next?",
        "source": "rule_based",
        "language": content_language,
    }


def _openai_metadata(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    platform: str,
    final_video_path: str,
    narration_script: str,
    prompts: list[str],
    content_language: str,
) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None

    schema_hint = {
        PLATFORM_YOUTUBE: [
            "title",
            "description",
            "hashtags",
            "tags",
            "category",
            "privacy",
            "thumbnail_text",
            "pinned_comment",
        ],
        PLATFORM_TIKTOK: ["caption", "hashtags", "cover_text", "hook_text", "pinned_comment"],
        PLATFORM_INSTAGRAM: ["caption", "hashtags", "alt_text", "cover_text", "pinned_comment"],
    }
    prompt = {
        "platform": platform,
        "video_topic": video_topic,
        "channel_profile": {
            "channel_name": channel_profile.get("channel_name"),
            "main_niche": channel_profile.get("main_niche"),
            "tone_style": channel_profile.get("tone_style"),
            "target_audience": channel_profile.get("target_audience"),
        },
        "final_video_path": final_video_path,
        "narration_script": narration_script[:2000],
        "prompts": prompts[:8],
        "content_language": content_language,
        "required_fields": schema_hint.get(platform, []),
        "constraints": [
            "Return JSON only.",
            "privacy must default to private for YouTube.",
            "pinned_comment is a draft only — never claim it was posted.",
            "YouTube descriptions must be 800-1500 characters with hook, branding, SEO keywords, 15-20 hashtags, and CTA.",
            "Instagram captions must include ingredients list, skin benefit, follow CTA, and 25 skincare hashtags.",
        ],
    }
    try:
        client = OpenAI(api_key=api_key, timeout=45.0)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You generate upload metadata for short-form video platforms. Output valid JSON with the requested fields.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.4,
            max_tokens=900,
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed["platform"] = platform
            parsed["source"] = "openai"
            parsed["language"] = content_language
            if platform == PLATFORM_YOUTUBE:
                parsed.setdefault("privacy", PRIVACY_PRIVATE)
                parsed["hashtags"] = _slug_hashtags(list(parsed.get("hashtags") or []))
                parsed["tags"] = [str(item).strip() for item in (parsed.get("tags") or []) if str(item).strip()]
            else:
                parsed["hashtags"] = _slug_hashtags(list(parsed.get("hashtags") or []))
            return parsed
    except Exception:
        return None
    return None


def generate_platform_metadata(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    platform: str,
    final_video_path: str = "",
    narration_script: str = "",
    prompts: list[str] | None = None,
    content_language: str = "",
    use_openai: bool = True,
) -> dict[str, Any]:
    normalized = str(platform or PLATFORM_YOUTUBE).strip().lower()
    language = str(content_language or channel_profile.get("language") or "English").strip()
    prompt_list = [str(item).strip() for item in (prompts or []) if str(item).strip()]

    if use_openai:
        ai_payload = _openai_metadata(
            video_topic=video_topic,
            channel_profile=channel_profile,
            platform=normalized,
            final_video_path=final_video_path,
            narration_script=narration_script,
            prompts=prompt_list,
            content_language=language,
        )
        if ai_payload:
            ai_payload["version"] = PLATFORM_METADATA_AGENT_VERSION
            return ai_payload

    if normalized == PLATFORM_TIKTOK:
        payload = _rule_based_tiktok(
            video_topic=video_topic,
            channel_profile=channel_profile,
            content_language=language,
        )
    elif normalized == PLATFORM_INSTAGRAM:
        payload = _rule_based_instagram(
            video_topic=video_topic,
            channel_profile=channel_profile,
            narration_script=narration_script,
            content_language=language,
        )
    else:
        payload = _rule_based_youtube(
            video_topic=video_topic,
            channel_profile=channel_profile,
            narration_script=narration_script,
            content_language=language,
        )
    payload["version"] = PLATFORM_METADATA_AGENT_VERSION
    return payload


def generate_all_platform_metadata(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    platform_targets: list[str],
    final_video_path: str = "",
    narration_script: str = "",
    prompts: list[str] | None = None,
    content_language: str = "",
    use_openai: bool = True,
) -> dict[str, Any]:
    platforms = platform_targets or list(channel_profile.get("upload_platforms") or [PLATFORM_YOUTUBE])
    metadata_by_platform: dict[str, dict[str, Any]] = {}
    for platform in platforms:
        normalized = str(platform or "").strip().lower()
        if not normalized:
            continue
        metadata_by_platform[normalized] = generate_platform_metadata(
            video_topic=video_topic,
            channel_profile=channel_profile,
            platform=normalized,
            final_video_path=final_video_path,
            narration_script=narration_script,
            prompts=prompts,
            content_language=content_language,
            use_openai=use_openai,
        )
    return {
        "version": PLATFORM_METADATA_AGENT_VERSION,
        "video_topic": video_topic,
        "final_video_path": final_video_path,
        "platforms": metadata_by_platform,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


__all__ = [
    "PLATFORM_METADATA_AGENT_VERSION",
    "generate_all_platform_metadata",
    "generate_platform_metadata",
]
