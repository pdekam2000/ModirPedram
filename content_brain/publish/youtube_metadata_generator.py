"""YouTube metadata generator — publish-ready metadata without upload or API calls."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

YOUTUBE_METADATA_VERSION = "youtube_metadata_generator_v3_seo_tags"
YOUTUBE_METADATA_FILENAME = "youtube_metadata.json"
SHORTS_MAX_DURATION_SECONDS = 60
LONG_FORM_MIN_DURATION_SECONDS = 61
DESCRIPTION_MIN_CHARS = 800
DESCRIPTION_TARGET_CHARS = 1200
DESCRIPTION_MAX_CHARS = 1500

YOUTUBE_SCIENCE_BRANDING_LINE = (
    "🔬 Science That Feels Impossible — new mind-blowing fact every day. "
    "Subscribe for daily science shorts!"
)
YOUTUBE_BASE_HASHTAGS = (
    "#ScienceFacts",
    "#MindBlowing",
    "#DidYouKnow",
    "#ScienceShorts",
    "#LearnSomethingNew",
    "#SpaceFacts",
    "#NatureFacts",
    "#ScienceIsAmazing",
    "#Shorts",
    "#YouTubeShorts",
)
YOUTUBE_SEO_BASE_TAGS: tuple[str, ...] = (
    "science",
    "facts",
    "did you know",
    "mind blowing",
    "shorts",
    "youtube shorts",
    "science shorts",
    "amazing facts",
    "learn something new",
    "science facts",
    "impossible science",
)
YOUTUBE_TRENDING_TAGS: tuple[str, ...] = (
    "shorts",
    "viral",
    "trending",
    "2025",
    "2026",
)
YOUTUBE_TITLE_POWER_WORDS: tuple[str, ...] = (
    "Why",
    "How",
    "What Happens When",
    "Never",
    "Finally",
    "Scientists Discovered",
    "The Truth About",
    "This Is Why",
    "Nobody Talks About",
    "The Real Reason",
)
SCIENCE_TOPIC_TAG_HINTS: dict[str, tuple[str, ...]] = {
    "atom": ("atoms", "quantum physics", "physics facts", "atomic theory", "matter", "particles"),
    "touch": ("atoms", "quantum physics", "physics facts", "atomic theory", "matter", "particles"),
    "brain": ("brain science", "neuroscience", "psychology facts", "memory", "human brain"),
    "memory": ("false memory", "psychology", "brain science", "neuroscience", "human mind"),
    "space": ("space facts", "astrophysics", "universe", "cosmos", "nasa"),
    "earth": ("earth science", "planet earth", "geology", "natural disasters"),
    "time": ("time dilation", "relativity", "physics facts", "einstein", "spacetime"),
    "quantum": ("quantum physics", "quantum mechanics", "particle physics", "science facts"),
    "ocean": ("ocean facts", "deep sea", "marine biology", "ocean mysteries"),
    "animal": ("strange animals", "biology facts", "wildlife", "nature facts"),
    "tardigrade": ("tardigrade", "extremophile", "microscopic animals", "survival science"),
    "light": ("bioluminescence", "human body", "science facts", "biology"),
    "immune": ("immune system", "human body", "biology facts", "health science"),
    "black hole": ("black hole", "astrophysics", "space facts", "universe"),
    "jupiter": ("jupiter", "space facts", "planets", "solar system"),
}
INSTAGRAM_BASE_HASHTAGS = (
    "#skincare",
    "#diybeauty",
    "#skincarerecipe",
    "#naturalskincare",
    "#glowingskin",
    "#skintips",
    "#beautyroutine",
    "#selfcare",
    "#skincarecommunity",
    "#facemask",
    "#organicskincare",
    "#skincareproducts",
    "#beautyhacks",
    "#skincaretips",
    "#healthyskin",
    "#skincareaddict",
    "#skincareroutine",
    "#cleanbeauty",
    "#skincarelover",
    "#beautytips",
    "#skincareobsessed",
    "#glowup",
    "#skincarejunkie",
    "#homemadebeauty",
    "#skincaregoals",
)

SPAM_PATTERNS = (
    r"\b(you won't believe|shocking|100% free|click now|must watch|gone wrong)\b",
    r"!{3,}",
    r"\?{3,}",
)

NICHE_CATEGORY_MAP: dict[str, str] = {
    "tech": "Science & Technology",
    "technology": "Science & Technology",
    "gaming": "Gaming",
    "education": "Education",
    "howto": "Howto & Style",
    "how to": "Howto & Style",
    "beauty": "Howto & Style",
    "skincare": "Howto & Style",
    "fitness": "Sports",
    "sports": "Sports",
    "music": "Music",
    "comedy": "Comedy",
    "entertainment": "Entertainment",
    "animation": "Film & Animation",
    "film": "Film & Animation",
    "news": "News & Politics",
    "pets": "Pets & Animals",
    "dog": "Pets & Animals",
    "travel": "Travel & Events",
    "food": "Howto & Style",
    "finance": "People & Blogs",
    "business": "People & Blogs",
}

def _is_science_channel(channel_profile: dict[str, Any], topic: str) -> bool:
    haystack = " ".join(
        [
            str(channel_profile.get("youtube_genre") or ""),
            str(channel_profile.get("main_niche") or ""),
            str(channel_profile.get("channel_name") or ""),
            str(channel_profile.get("youtube_channel_topic") or "")[:200],
            topic,
        ]
    ).lower()
    return any(marker in haystack for marker in ("science", "impossible", "physics", "space", "brain"))


def _topic_hashtag_tags(topic: str, *, limit: int = 8) -> list[str]:
    tags: list[str] = []
    for word in _topic_words(topic):
        if len(word) < 4:
            continue
        tags.append(f"#{word.title()}")
    return tags[:limit]


def _build_youtube_description_hashtags(*, topic: str, channel_profile: dict[str, Any]) -> list[str]:
    tags = list(YOUTUBE_BASE_HASHTAGS)
    tags.extend(_topic_hashtag_tags(topic, limit=10))
    channel = str(channel_profile.get("channel_name") or "").strip()
    if channel:
        compact = re.sub(r"[^a-zA-Z0-9]", "", channel)
        if compact:
            tags.append(f"#{compact}")
    return _dedupe_hashtags(tags, min_count=15, max_count=20)


def _expand_hook_paragraph(
    *,
    hook: str,
    topic: str,
    narration_script: str,
    target_chars: int = 320,
) -> str:
    paragraphs: list[str] = []
    lead = str(hook or "").strip()
    if lead:
        paragraphs.append(lead if lead.endswith(".") else f"{lead}.")
    excerpt = " ".join(str(narration_script or "").split())
    if excerpt and excerpt.lower() not in lead.lower():
        sentences = re.split(r"(?<=[.!?])\s+", excerpt)
        for sentence in sentences[:3]:
            text = sentence.strip()
            if text and text not in paragraphs:
                paragraphs.append(text)
            if sum(len(item) for item in paragraphs) >= target_chars:
                break
    if not paragraphs:
        paragraphs.append(
            f"This Short breaks down {topic} with cinematic visuals and a fast, curiosity-driven science hook."
        )
    body = " ".join(paragraphs)
    if len(body) < 180 and excerpt:
        body = f"{body} {excerpt[: max(0, target_chars - len(body) - 1)]}".strip()
    return body[: max(220, target_chars)].strip()


def _ensure_shorts_title(title: str, *, is_short: bool) -> str:
    cleaned = _clean_title(title)
    if not is_short:
        return cleaned
    if "#shorts" in cleaned.lower():
        return cleaned
    suffix = " #Shorts"
    if len(cleaned) + len(suffix) > 95:
        cleaned = cleaned[: max(1, 95 - len(suffix))].rstrip(" -|:")
    return f"{cleaned}{suffix}"


def _shorts_description_lead() -> str:
    return "#Shorts #ScienceFacts"


def _build_structured_youtube_description(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    story_hook: str,
    narration_script: str,
    seo_keywords: list[str],
    hashtags: list[str],
    is_short: bool,
) -> str:
    channel = str(channel_profile.get("channel_name") or "Science That Feels Impossible").strip()
    hook = _build_hook(topic, story_hook, narration_script)
    hook_paragraph = _expand_hook_paragraph(
        hook=hook,
        topic=topic,
        narration_script=narration_script,
        target_chars=340,
    )
    branding = YOUTUBE_SCIENCE_BRANDING_LINE
    if not _is_science_channel(channel_profile, topic):
        branding = f"🔬 {channel} — subscribe for more cinematic shorts like this."

    keyword_bits = [str(item).strip() for item in seo_keywords if str(item).strip()]
    keyword_bits.extend(_topic_words(topic))
    keyword_line = ", ".join(dict.fromkeys(keyword_bits))[:240]
    if not keyword_line:
        keyword_line = ", ".join(_topic_words(topic)) or topic

    tag_line = " ".join(hashtags or _build_youtube_description_hashtags(topic=topic, channel_profile=channel_profile))
    cta_block = (
        "👍 Like if this blew your mind!\n"
        "🔔 Subscribe for daily science facts\n"
        "💬 Comment what you want to learn next"
    )
    lines = [
        _shorts_description_lead() if is_short else hook_paragraph,
        hook_paragraph if is_short else "",
        "",
        branding,
        "",
        f"🔑 Topics: {keyword_line}",
        "",
        tag_line,
        "",
        cta_block,
    ]
    if is_short:
        lines.extend(["", "Built for YouTube Shorts — fast hook, cinematic pacing, native in-scene audio."])
    disclosure = _ai_disclosure_block(channel_profile)
    if disclosure:
        lines.extend(["", disclosure])

    description = "\n".join(line for line in lines if line is not None).strip()
    if len(description) < DESCRIPTION_MIN_CHARS and narration_script:
        extra = " ".join(str(narration_script).split())[:600]
        if extra and extra not in description:
            description = f"{description}\n\n{extra}".strip()
    if len(description) > DESCRIPTION_MAX_CHARS:
        description = description[: DESCRIPTION_MAX_CHARS - 3].rstrip() + "..."
    return description




def _openai_json_completion(*, system: str, user_payload: dict[str, Any], max_tokens: int = 1400) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    try:
        client = OpenAI(api_key=api_key, timeout=45.0)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.55,
            max_tokens=max_tokens,
        )
        raw = (response.choices[0].message.content or "").strip()
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _channel_name_tag_variants(channel_name: str) -> list[str]:
    name = re.sub(r"\s+", " ", str(channel_name or "").strip())
    if not name:
        return []
    compact = re.sub(r"[^a-zA-Z0-9]", "", name)
    tags = [name]
    if compact and compact.lower() != name.lower():
        tags.append(compact)
    if compact:
        tags.append(f"#{compact}")
    return tags


def _ai_generate_title(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    story_hook: str,
    is_short: bool,
) -> str:
    channel = str(channel_profile.get("channel_name") or "Channel").strip()
    niche = str(channel_profile.get("main_niche") or channel_profile.get("channel_topic") or "").strip()
    payload = _openai_json_completion(
        system=(
            "Return JSON {\"title\": \"...\", \"candidates\": [\"...\"]}. "
            "Write 3 curiosity-driven YouTube titles under 95 characters. "
            "Avoid spam clickbait (no ALL CAPS, no triple punctuation). Pick the best in title."
        ),
        user_payload={
            "topic": topic,
            "channel_name": channel,
            "main_niche": niche,
            "story_hook": story_hook,
            "format": "shorts" if is_short else "long",
        },
        max_tokens=350,
    )
    if not payload:
        return ""
    title = str(payload.get("title") or "").strip()
    if not title:
        candidates = payload.get("candidates") or []
        if isinstance(candidates, list):
            for item in candidates:
                text = str(item or "").strip()
                if text:
                    title = text
                    break
    return _clean_title(title) if title else ""


def _title_starts_with_power_word(title: str) -> bool:
    cleaned = _clean_title(title)
    lowered = cleaned.lower()
    return any(lowered.startswith(word.lower()) for word in YOUTUBE_TITLE_POWER_WORDS)


def _enhance_title_clickthrough(title: str) -> str:
    cleaned = _clean_title(title)
    if not cleaned or _title_starts_with_power_word(cleaned):
        return cleaned
    for prefix in ("Why", "How", "The Truth About"):
        if cleaned.lower().startswith(prefix.lower()):
            return cleaned
        candidate = _clean_title(f"{prefix} {cleaned}")
        if len(candidate) <= 95:
            return candidate
    return cleaned


def _topic_tags_from_title(title: str) -> list[str]:
    lowered = str(title or "").lower()
    tags: list[str] = []
    for keyword, hints in SCIENCE_TOPIC_TAG_HINTS.items():
        if keyword in lowered:
            tags.extend(hints)
    for word in _topic_words(title):
        if len(word) >= 4:
            tags.append(word)
    return tags


def _ai_generate_topic_tags(title: str) -> list[str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        from openai import OpenAI
    except ImportError:
        return []
    try:
        client = OpenAI(api_key=api_key, timeout=30.0)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Generate 5 YouTube search tags for a video titled: {title}. "
                        "Return only comma-separated tags, no hashtags."
                    ),
                }
            ],
            temperature=0.45,
            max_tokens=120,
        )
        raw = (response.choices[0].message.content or "").strip()
        return [item.strip() for item in raw.split(",") if item.strip()][:5]
    except Exception:
        return []


def _dedupe_search_tags(items: list[str], *, min_count: int = 20, max_count: int = 30) -> list[str]:
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
        cleaned.append(raw[:40])
        if len(cleaned) >= max_count:
            break
    if len(cleaned) < min_count:
        for filler in YOUTUBE_SEO_BASE_TAGS + list(YOUTUBE_TRENDING_TAGS):
            key = filler.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(filler)
            if len(cleaned) >= min_count:
                break
    return cleaned[:max_count]


def _ai_generate_description(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    story_hook: str,
    narration_script: str,
    hashtags: list[str],
    cta_text: str,
    is_short: bool,
    duration_seconds: float | int | None,
    seo_keywords: list[str],
) -> str:
    channel = str(channel_profile.get("channel_name") or "Channel").strip()
    niche = str(channel_profile.get("main_niche") or channel_profile.get("channel_topic") or "").strip()
    disclosure = _ai_disclosure_block(channel_profile)
    payload = _openai_json_completion(
        system=(
            "Return JSON {\"description\": \"...\"}. Write a YouTube description between 800-1500 characters. "
            "Structure exactly: (1) hook paragraph 2-3 sentences about the video topic, "
            "(2) channel branding line for Science That Feels Impossible, "
            "(3) SEO line starting with '🔑 Topics:' and comma-separated keywords, "
            "(4) 15-20 hashtags including #ScienceFacts #MindBlowing #ScienceShorts plus topic tags, "
            "(5) CTA block with like/subscribe/comment lines. "
            "Natural prose — no spam, no misleading claims."
        ),
        user_payload={
            "topic": topic,
            "channel_name": channel,
            "main_niche": niche,
            "story_hook": story_hook,
            "narration_excerpt": narration_script[:1200],
            "cta_text": cta_text,
            "hashtags": hashtags,
            "seo_keywords": seo_keywords[:20],
            "format": "shorts" if is_short else "long",
            "duration_seconds": duration_seconds,
            "ai_disclosure": disclosure,
            "target_chars": DESCRIPTION_TARGET_CHARS,
        },
        max_tokens=1800,
    )
    if not payload:
        return ""
    description = str(payload.get("description") or "").strip()
    if len(description) > DESCRIPTION_MAX_CHARS:
        description = description[: DESCRIPTION_MAX_CHARS - 3].rstrip() + "..."
    if description and len(description) >= DESCRIPTION_MIN_CHARS:
        return description
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_language(value: str) -> str:
    text = str(value or "en").strip().lower()
    mapping = {
        "english": "en",
        "en-us": "en",
        "en_us": "en",
        "german": "de",
        "deutsch": "de",
        "spanish": "es",
        "french": "fr",
    }
    if text in mapping:
        return mapping[text]
    if len(text) == 2:
        return text
    return "en"


def _topic_words(topic: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", str(topic or "").lower())
    return [word for word in words if len(word) > 2][:8]


def _clean_title(text: str, *, max_len: int = 95) -> str:
    title = re.sub(r"\s+", " ", str(text or "").strip())
    title = re.sub(r"[^\w\s\-|:&'!?,.]", "", title)
    for pattern in SPAM_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" -|:")
    if not title:
        title = "New Video"
    if title.isupper() and len(title) > 12:
        title = title.title()
    return title[:max_len].rstrip(" -|:")


def _dedupe_hashtags(items: list[str], *, min_count: int = 3, max_count: int = 10) -> list[str]:
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
    if len(cleaned) < min_count:
        for filler in ("shorts", "viral", "trending", "ai", "video", "youtube"):
            tag = f"#{filler}"
            key = filler.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(tag)
            if len(cleaned) >= min_count:
                break
    return cleaned[:max_count]


def _resolve_category(channel_profile: dict[str, Any], topic: str) -> str:
    explicit = str(channel_profile.get("youtube_category") or "").strip()
    if explicit:
        return explicit
    haystack = " ".join(
        [
            str(channel_profile.get("main_niche") or ""),
            str(channel_profile.get("channel_topic") or ""),
            str(channel_profile.get("content_style") or ""),
            topic,
        ]
    ).lower()
    for key, category in NICHE_CATEGORY_MAP.items():
        if key in haystack:
            return category
    return "People & Blogs"


def is_youtube_shorts(*, duration_seconds: float | int | None, platform_targets: list[str] | None = None) -> bool:
    targets = [str(item).lower() for item in (platform_targets or [])]
    if any("short" in item for item in targets):
        return True
    if duration_seconds is None:
        return True
    return float(duration_seconds) <= SHORTS_MAX_DURATION_SECONDS


def _build_hook(topic: str, story_hook: str, narration_script: str) -> str:
    if story_hook.strip():
        return story_hook.strip()
    if narration_script.strip():
        return narration_script.strip().split("\n")[0][:220]
    words = _topic_words(topic)
    if words:
        return f"A focused look at {' '.join(words[:4])} — told in a cinematic short-form story."
    return "A cinematic story built for quick, high-impact viewing."


def _ai_disclosure_block(channel_profile: dict[str, Any]) -> str:
    enabled = bool(
        channel_profile.get("ai_creation_disclosure_enabled")
        or channel_profile.get("youtube_ai_disclosure_enabled")
        or channel_profile.get("include_ai_disclosure", True)
    )
    if not enabled:
        return ""
    custom = str(
        channel_profile.get("ai_disclosure_text")
        or channel_profile.get("youtube_ai_disclosure")
        or ""
    ).strip()
    if custom:
        return custom
    return "This video includes AI-assisted visuals and editing."


def _build_title(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    is_short: bool,
    story_hook: str,
) -> tuple[str, str]:
    channel = str(channel_profile.get("channel_name") or "Channel").strip()
    niche = str(channel_profile.get("main_niche") or channel_profile.get("channel_topic") or "story").strip()
    hook = _build_hook(topic, story_hook, "")
    hook_phrase = hook.split(".")[0].split("—")[0].strip()
    if len(hook_phrase) > 48:
        hook_phrase = hook_phrase[:48].rsplit(" ", 1)[0]

    if is_short:
        candidates = [
            f"{topic}: {hook_phrase}" if hook_phrase and hook_phrase.lower() not in topic.lower() else topic,
            f"{topic} | {niche} Short",
            f"{channel} — {topic}",
        ]
    else:
        candidates = [
            f"{topic} — Full Story",
            f"{topic}: {hook_phrase}" if hook_phrase else f"{topic} | {channel}",
            f"Why {topic} Matters | {niche}",
        ]

    ai_title = _ai_generate_title(
        topic=topic,
        channel_profile=channel_profile,
        story_hook=story_hook,
        is_short=is_short,
    )
    if ai_title:
        title = _ensure_shorts_title(_enhance_title_clickthrough(ai_title), is_short=is_short)
        return title, _clean_title(title, max_len=42)

    title = _clean_title(next((item for item in candidates if item.strip()), topic))
    title = _ensure_shorts_title(_enhance_title_clickthrough(title), is_short=is_short)
    short_title = _clean_title(title, max_len=42)
    return title, short_title


def _build_description(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    story_hook: str,
    narration_script: str,
    hashtags: list[str],
    cta_text: str,
    is_short: bool,
    duration_seconds: float | int | None,
) -> str:
    seo_keywords = _build_seo_keywords(topic=topic, tags=[], hashtags=hashtags)
    structured = _build_structured_youtube_description(
        topic=topic,
        channel_profile=channel_profile,
        story_hook=story_hook,
        narration_script=narration_script,
        seo_keywords=seo_keywords,
        hashtags=hashtags,
        is_short=is_short,
    )
    ai_description = _ai_generate_description(
        topic=topic,
        channel_profile=channel_profile,
        story_hook=story_hook,
        narration_script=narration_script,
        hashtags=hashtags,
        cta_text=cta_text,
        is_short=is_short,
        duration_seconds=duration_seconds,
        seo_keywords=seo_keywords,
    )
    if ai_description:
        return ai_description
    return structured


def _build_tags(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    is_short: bool,
    prompts: list[str],
    title: str = "",
) -> list[str]:
    search_title = str(title or topic or "").strip()
    channel_name = str(channel_profile.get("channel_name") or "").strip()
    tags: list[str] = []
    tags.extend(YOUTUBE_SEO_BASE_TAGS)
    tags.extend(_topic_tags_from_title(search_title))
    tags.extend(_ai_generate_topic_tags(search_title))
    tags.extend(_channel_name_tag_variants(channel_name))
    tags.extend(list(YOUTUBE_TRENDING_TAGS))
    if is_short:
        tags.extend(["vertical video", "short form", "science channel"])
    for prompt in prompts[:2]:
        tags.extend(_topic_words(prompt)[:3])
    return _dedupe_search_tags(tags, min_count=20, max_count=30)


def _build_hashtags(*, topic: str, channel_profile: dict[str, Any], is_short: bool) -> list[str]:
    return _build_youtube_description_hashtags(topic=topic, channel_profile=channel_profile)


def build_upload_youtube_description(
    *,
    video_topic: str,
    channel_profile: dict[str, Any],
    narration_script: str = "",
    story_hook: str = "",
) -> str:
    hashtags = _build_hashtags(topic=video_topic, channel_profile=channel_profile, is_short=True)
    seo_keywords = _build_seo_keywords(topic=video_topic, tags=[], hashtags=hashtags)
    return _build_structured_youtube_description(
        topic=video_topic,
        channel_profile=channel_profile,
        story_hook=story_hook,
        narration_script=narration_script,
        seo_keywords=seo_keywords,
        hashtags=hashtags,
        is_short=True,
    )


def _build_thumbnail_prompt(
    *,
    topic: str,
    channel_profile: dict[str, Any],
    story_hook: str,
    is_short: bool,
) -> str:
    tone = str(channel_profile.get("tone_style") or "cinematic").strip()
    niche = str(channel_profile.get("main_niche") or "story").strip()
    hook = _build_hook(topic, story_hook, "")
    aspect = "9:16 vertical" if is_short else "16:9 cinematic"
    return (
        f"YouTube thumbnail, {aspect}, {tone} lighting, subject inspired by '{topic}', "
        f"{niche} niche, expressive focal character, bold readable composition, "
        f"high contrast, no text overlay, no watermark, story mood: {hook[:120]}"
    )


def _build_cta_text(channel_profile: dict[str, Any], topic: str) -> str:
    custom = str(channel_profile.get("cta_text") or channel_profile.get("youtube_cta_text") or "").strip()
    if custom:
        return custom
    channel = str(channel_profile.get("channel_name") or "this channel").strip()
    return f"Subscribe to {channel} for more stories like this. Comment your take on {topic}."


def _build_seo_keywords(*, topic: str, tags: list[str], hashtags: list[str]) -> list[str]:
    words = _topic_words(topic)
    tag_words = [tag.lower() for tag in tags[:12]]
    hash_words = [item.lstrip("#").lower() for item in hashtags]
    merged = words + tag_words + hash_words
    deduped: list[str] = []
    seen: set[str] = set()
    for item in merged:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:20]


def _build_publish_summary(
    *,
    title: str,
    is_short: bool,
    duration_seconds: float | int | None,
    clip_count: int,
    category: str,
) -> str:
    form = "Short" if is_short else "Long-form"
    dur = int(duration_seconds or 0)
    clips = max(1, int(clip_count))
    return (
        f"{form} YouTube package ready: '{title}' ({dur}s, {clips} clip{'s' if clips != 1 else ''}, "
        f"category {category}). Metadata only — upload runtime not invoked."
    )


def generate_youtube_metadata(
    *,
    topic: str,
    channel_profile: dict[str, Any] | None = None,
    story_hook: str = "",
    narration_script: str = "",
    prompts: list[str] | None = None,
    duration_seconds: float | int | None = None,
    clip_count: int = 1,
    platform_targets: list[str] | None = None,
    final_video_path: str = "",
) -> dict[str, Any]:
    """Generate publish-ready YouTube metadata. No YouTube API calls."""
    profile = dict(channel_profile or {})
    prompt_list = [str(item).strip() for item in (prompts or []) if str(item).strip()]
    short = is_youtube_shorts(duration_seconds=duration_seconds, platform_targets=platform_targets)
    hashtags = _build_hashtags(topic=topic, channel_profile=profile, is_short=short)
    title, short_title = _build_title(
        topic=topic,
        channel_profile=profile,
        is_short=short,
        story_hook=story_hook,
    )
    cta_text = _build_cta_text(profile, topic)
    tags = _build_tags(
        topic=topic,
        channel_profile=profile,
        is_short=short,
        prompts=prompt_list,
        title=title,
    )
    category = _resolve_category(profile, topic)
    language = _normalize_language(str(profile.get("language") or profile.get("content_language") or "en"))
    made_for_kids = bool(profile.get("youtube_made_for_kids", False))
    description = _build_description(
        topic=topic,
        channel_profile=profile,
        story_hook=story_hook,
        narration_script=narration_script,
        hashtags=hashtags,
        cta_text=cta_text,
        is_short=short,
        duration_seconds=duration_seconds,
    )
    thumbnail_prompt = _build_thumbnail_prompt(
        topic=topic,
        channel_profile=profile,
        story_hook=story_hook,
        is_short=short,
    )
    seo_keywords = _build_seo_keywords(topic=topic, tags=tags, hashtags=hashtags)
    publish_summary = _build_publish_summary(
        title=title,
        is_short=short,
        duration_seconds=duration_seconds,
        clip_count=clip_count,
        category=category,
    )
    return {
        "version": YOUTUBE_METADATA_VERSION,
        "generated_at": _now_iso(),
        "video_format": "shorts" if short else "long",
        "duration_seconds": duration_seconds,
        "clip_count": clip_count,
        "final_video_path": final_video_path,
        "title": title,
        "short_title": short_title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "category": category,
        "language": language,
        "made_for_kids": made_for_kids,
        "thumbnail_prompt": thumbnail_prompt,
        "cta_text": cta_text,
        "seo_keywords": seo_keywords,
        "publish_summary": publish_summary,
    }


def save_youtube_metadata(publish_dir: Path, metadata: dict[str, Any]) -> Path:
    publish_dir.mkdir(parents=True, exist_ok=True)
    target = publish_dir / YOUTUBE_METADATA_FILENAME
    target.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def load_youtube_metadata(publish_dir: str | Path) -> dict[str, Any] | None:
    path = Path(publish_dir) / YOUTUBE_METADATA_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def generate_and_save_youtube_metadata(
    *,
    publish_dir: str | Path,
    topic: str,
    channel_profile: dict[str, Any] | None = None,
    story_hook: str = "",
    narration_script: str = "",
    prompts: list[str] | None = None,
    duration_seconds: float | int | None = None,
    clip_count: int = 1,
    platform_targets: list[str] | None = None,
    final_video_path: str = "",
) -> dict[str, Any]:
    metadata = generate_youtube_metadata(
        topic=topic,
        channel_profile=channel_profile,
        story_hook=story_hook,
        narration_script=narration_script,
        prompts=prompts,
        duration_seconds=duration_seconds,
        clip_count=clip_count,
        platform_targets=platform_targets,
        final_video_path=final_video_path,
    )
    path = save_youtube_metadata(Path(publish_dir), metadata)
    metadata["metadata_path"] = str(path.resolve()).replace("\\", "/")
    return metadata


def _read_narration_script(publish_dir: Path) -> str:
    script_path = publish_dir / "narration" / "narration_script.txt"
    if script_path.is_file():
        try:
            return script_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def _read_prompts(publish_dir: Path, fallback_prompts: list[str] | None = None) -> list[str]:
    if fallback_prompts:
        return fallback_prompts
    prompts_path = publish_dir / "prompts" / "runway_prompts.txt"
    if not prompts_path.is_file():
        return []
    try:
        lines = [
            line.strip()
            for line in prompts_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except OSError:
        return []
    return lines


def ensure_product_studio_publish_metadata(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    topic: str,
    video_path: str,
    channel_profile: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    duration_seconds: float | int | None = None,
    clip_count: int = 1,
    prompts: list[str] | None = None,
    story_hook: str = "",
) -> dict[str, Any]:
    """Create run_dir/publish with video artifact and youtube_metadata.json for Product Studio runs."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    publish_dir = run_path / "publish"
    publish_dir.mkdir(parents=True, exist_ok=True)

    source_video = Path(video_path)
    if source_video.is_file():
        package_video = publish_dir / "FINAL_PRODUCT_STUDIO_VIDEO.mp4"
        if source_video.resolve() != package_video.resolve():
            shutil.copy2(source_video, package_video)
        final_video_path = str(package_video.resolve()).replace("\\", "/")
    else:
        final_video_path = ""

    preflight = dict(preflight or {})
    if channel_profile is None:
        try:
            from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

            channel_profile = ProductChannelProfileStore(root).load()
        except Exception:
            channel_profile = {}

    story = str(
        story_hook
        or preflight.get("story_hook")
        or (preflight.get("story_brief") or {}).get("hook")
        or ""
    )
    narration_script = _read_narration_script(publish_dir)
    prompt_list = prompts or list(preflight.get("prompts") or [])
    if not prompt_list:
        job_path = run_path / "job.json"
        if job_path.is_file():
            try:
                job = json.loads(job_path.read_text(encoding="utf-8"))
                prompt_list = [str(item).strip() for item in (job.get("prompts") or []) if str(item).strip()]
            except (OSError, json.JSONDecodeError):
                prompt_list = []

    platform_targets = list(
        preflight.get("upload_platforms")
        or (channel_profile or {}).get("upload_platforms")
        or ["youtube_shorts"]
    )
    metadata = generate_and_save_youtube_metadata(
        publish_dir=publish_dir,
        topic=topic,
        channel_profile=channel_profile,
        story_hook=story,
        narration_script=narration_script,
        prompts=prompt_list,
        duration_seconds=duration_seconds,
        clip_count=clip_count,
        platform_targets=platform_targets,
        final_video_path=final_video_path,
    )
    package_meta_path = publish_dir / "metadata.json"
    package_meta = {
        "version": YOUTUBE_METADATA_VERSION,
        "run_id": run_path.name,
        "topic": topic,
        "clip_count": clip_count,
        "duration_seconds": duration_seconds,
        "final_video_path": final_video_path,
        "youtube_metadata_path": metadata.get("metadata_path"),
        "created_at": _now_iso(),
    }
    package_meta_path.write_text(json.dumps(package_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "publish_package_path": str(publish_dir.resolve()).replace("\\", "/"),
        "youtube_metadata": metadata,
        "youtube_metadata_path": metadata.get("metadata_path"),
    }


__all__ = [
    "DESCRIPTION_MAX_CHARS",
    "DESCRIPTION_MIN_CHARS",
    "INSTAGRAM_BASE_HASHTAGS",
    "LONG_FORM_MIN_DURATION_SECONDS",
    "SHORTS_MAX_DURATION_SECONDS",
    "YOUTUBE_METADATA_FILENAME",
    "YOUTUBE_METADATA_VERSION",
    "build_upload_youtube_description",
    "ensure_product_studio_publish_metadata",
    "generate_and_save_youtube_metadata",
    "generate_youtube_metadata",
    "is_youtube_shorts",
    "load_youtube_metadata",
    "save_youtube_metadata",
]
