"""OpenAI + rule-based channel profile suggestions for Smart Channel Setup."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

# Dropdown presets (must match Settings UI)
LANGUAGE_PRESETS = {"english", "german", "persian", "turkish", "arabic", "custom"}
TONE_PRESETS = {
    "cinematic",
    "documentary",
    "educational",
    "mysterious",
    "horror",
    "motivational",
    "calm/relaxing",
    "luxury",
    "funny",
    "custom",
}
VISUAL_STYLE_PRESETS = {
    "cinematic realistic",
    "nature documentary",
    "dark mystery",
    "soft relaxing",
    "product ad",
    "educational explainer",
    "anime-inspired",
    "papercraft",
    "custom",
}
PLATFORM_PRESETS = {"tiktok", "instagram_reels", "youtube_shorts", "multi"}
DURATION_PRESETS = {6, 8, 10, 20, 30, 40}
PROVIDER_PRESETS = {"runway", "hailuo", "auto"}
NARRATION_PRESETS = {"disabled", "none", "elevenlabs"}
MUSIC_PRESETS = {"none", "local_mp3", "suno_future_placeholder"}
UPLOAD_PLATFORM_PRESETS = {"tiktok", "instagram_reels", "youtube_shorts"}


@dataclass
class ChannelProfileSuggestion:
    channel_name: str = ""
    main_niche: str = ""
    sub_niche: str = ""
    channel_topic: str = ""
    target_audience: str = ""
    language: str = "English"
    tone_style: str = "cinematic"
    visual_style: str = "cinematic realistic"
    default_platform: str = "youtube_shorts"
    default_duration_seconds: int = 30
    default_provider: str = "runway"
    default_narration_provider: str = "elevenlabs"
    default_voice: str = ""
    music_provider: str = "none"
    preferred_topics: list[str] = field(default_factory=list)
    forbidden_topics: list[str] = field(default_factory=list)
    content_formats: list[str] = field(default_factory=list)
    upload_platforms: list[str] = field(
        default_factory=lambda: ["tiktok", "instagram_reels", "youtube_shorts"]
    )
    use_ai_director_default: bool = True
    use_prompt_critic_default: bool = True
    reasoning: str = ""
    source: str = "rule_based"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slug_words(text: str) -> list[str]:
    return [w for w in re.split(r"[^\w]+", (text or "").lower()) if len(w) > 2]


def _pick_tone(topic: str) -> str:
    t = topic.lower()
    if any(k in t for k in ("relax", "calm", "nature", "meditation", "sleep")):
        return "calm/relaxing"
    if any(k in t for k in ("horror", "scary", "dark", "mystery", "crime")):
        return "mysterious"
    if any(k in t for k in ("funny", "comedy", "meme", "humor")):
        return "funny"
    if any(k in t for k in ("learn", "education", "tutorial", "beginner", "how to")):
        return "educational"
    if any(k in t for k in ("luxury", "premium", "fashion")):
        return "luxury"
    if any(k in t for k in ("motivat", "success", "mindset")):
        return "motivational"
    if any(k in t for k in ("documentary", "wildlife", "animal", "desert", "ocean")):
        return "documentary"
    return "cinematic"


def _pick_visual(tone: str, topic: str) -> str:
    t = topic.lower()
    if tone in ("calm/relaxing",):
        return "soft relaxing"
    if tone in ("mysterious", "horror"):
        return "dark mystery"
    if tone == "educational":
        return "educational explainer"
    if any(k in t for k in ("nature", "wildlife", "animal", "desert", "ocean", "forest")):
        return "nature documentary"
    if any(k in t for k in ("product", "review", "tool", "saas", "app")):
        return "product ad"
    if tone == "documentary":
        return "nature documentary"
    return "cinematic realistic"


def _pick_platform(pref: str | None) -> str:
    if not pref:
        return "youtube_shorts"
    p = pref.strip().lower().replace(" ", "_")
    if p in PLATFORM_PRESETS:
        return p
    if "tiktok" in p:
        return "tiktok"
    if "instagram" in p or "reels" in p:
        return "instagram_reels"
    if "multi" in p:
        return "multi"
    return "youtube_shorts"


def _pick_language(pref: str | None) -> str:
    if not pref:
        return "English"
    p = pref.strip().lower()
    mapping = {
        "english": "English",
        "german": "German",
        "persian": "Persian",
        "turkish": "Turkish",
        "arabic": "Arabic",
        "custom": "Custom",
    }
    return mapping.get(p, pref.strip().title())


def _rule_based_suggestion(
    channel_topic: str,
    *,
    language_preference: str | None = None,
    platform_preference: str | None = None,
) -> ChannelProfileSuggestion:
    topic = (channel_topic or "").strip()
    words = _slug_words(topic)
    main = " ".join(words[:2]).title() if words else "General"
    sub = " ".join(words[2:4]).title() if len(words) > 2 else main
    tone = _pick_tone(topic)
    visual = _pick_visual(tone, topic)
    platform = _pick_platform(platform_preference)
    language = _pick_language(language_preference)

    name_bits = [w.capitalize() for w in words[:3]] or ["Channel"]
    channel_name = " ".join(name_bits) + " Shorts"

    audience = "Short-form viewers interested in " + (topic or "engaging vertical content")
    if any(k in topic.lower() for k in ("beginner", "women", "kids", "student")):
        if "women" in topic.lower():
            audience = "Women seeking practical, uplifting short-form content"
        elif "beginner" in topic.lower():
            audience = "Beginners who want clear, approachable explanations"

    preferred = [topic] if topic else []
    forbidden = ["politics", "explicit violence", "medical claims without sources"]
    formats = ["short fact", "listicle hook", "visual explainer"]

    if tone == "calm/relaxing":
        formats = ["ambient fact", "slow visual story", "nature highlight"]
    elif tone == "educational":
        formats = ["how-it-works", "quick tip", "myth vs fact"]

    duration = 30
    if platform == "tiktok":
        duration = 20
    elif platform == "instagram_reels":
        duration = 20

    narration = "elevenlabs" if tone not in ("calm/relaxing",) else "disabled"
    music = "local_mp3" if tone in ("calm/relaxing", "cinematic", "documentary") else "none"

    upload = ["tiktok", "instagram_reels", "youtube_shorts"]
    if platform == "tiktok":
        upload = ["tiktok"]
    elif platform == "instagram_reels":
        upload = ["instagram_reels"]
    elif platform == "youtube_shorts":
        upload = ["youtube_shorts"]

    return ChannelProfileSuggestion(
        channel_name=channel_name,
        main_niche=main or topic,
        sub_niche=sub or main,
        channel_topic=topic,
        target_audience=audience,
        language=language,
        tone_style=tone,
        visual_style=visual,
        default_platform=platform,
        default_duration_seconds=duration,
        default_provider="runway",
        default_narration_provider=narration,
        default_voice="",
        music_provider=music,
        preferred_topics=preferred,
        forbidden_topics=forbidden,
        content_formats=formats,
        upload_platforms=upload,
        use_ai_director_default=True,
        use_prompt_critic_default=True,
        reasoning=(
            f"Rule-based profile from topic keywords: tone={tone}, visual={visual}, "
            f"platform={platform}. Review and edit before saving."
        ),
        source="rule_based",
    )


def _openai_suggestion(
    channel_topic: str,
    *,
    language_preference: str | None = None,
    platform_preference: str | None = None,
) -> ChannelProfileSuggestion | None:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        prefs = []
        if language_preference:
            prefs.append(f"language_preference: {language_preference}")
        if platform_preference:
            prefs.append(f"platform_preference: {platform_preference}")
        pref_block = "\n".join(prefs) if prefs else "none"

        system = (
            "You suggest YouTube Shorts / TikTok channel profiles. "
            "Return ONLY valid JSON with keys: "
            "channel_name, main_niche, sub_niche, channel_topic, target_audience, "
            "language, tone_style, visual_style, default_platform, default_duration_seconds, "
            "default_provider, default_narration_provider, default_voice, music_provider, "
            "preferred_topics (array), forbidden_topics (array), content_formats (array), "
            "upload_platforms (array), reasoning. "
            "Use preset-friendly values: tone_style one of cinematic/documentary/educational/"
            "mysterious/horror/motivational/calm/relaxing/luxury/funny; "
            "visual_style one of cinematic realistic/nature documentary/dark mystery/"
            "soft relaxing/product ad/educational explainer/anime-inspired/papercraft; "
            "default_platform tiktok|instagram_reels|youtube_shorts|multi; "
            "default_provider runway|hailuo|auto; default_narration_provider disabled|elevenlabs; "
            "music_provider none|local_mp3|suno_future_placeholder."
        )
        user = f"Channel topic/niche: {channel_topic}\nUser preferences:\n{pref_block}"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        base = _rule_based_suggestion(
            channel_topic,
            language_preference=language_preference,
            platform_preference=platform_preference,
        )
        merged = {**base.to_dict(), **{k: v for k, v in data.items() if v is not None}}
        merged["source"] = "openai"
        merged.setdefault("use_ai_director_default", True)
        merged.setdefault("use_prompt_critic_default", True)
        return normalize_suggestion(merged)
    except Exception:
        return None


def normalize_suggestion(data: dict[str, Any] | ChannelProfileSuggestion) -> ChannelProfileSuggestion:
    if isinstance(data, ChannelProfileSuggestion):
        raw = data.to_dict()
    else:
        raw = dict(data or {})

    tone = str(raw.get("tone_style") or "cinematic").strip().lower()
    if tone not in TONE_PRESETS and tone != "custom":
        tone = _pick_tone(str(raw.get("channel_topic") or ""))

    visual = str(raw.get("visual_style") or "cinematic realistic").strip().lower()
    if visual not in VISUAL_STYLE_PRESETS and visual != "custom":
        visual = _pick_visual(tone, str(raw.get("channel_topic") or ""))

    platform = str(raw.get("default_platform") or "youtube_shorts").strip().lower()
    if platform not in PLATFORM_PRESETS:
        platform = _pick_platform(platform)

    try:
        duration = int(raw.get("default_duration_seconds") or 30)
    except (TypeError, ValueError):
        duration = 30
    if duration not in DURATION_PRESETS:
        duration = 30 if duration <= 0 else min(max(duration, 6), 60)

    provider = str(raw.get("default_provider") or "runway").strip().lower()
    if provider not in PROVIDER_PRESETS:
        provider = "runway"

    narration = str(raw.get("default_narration_provider") or "elevenlabs").strip().lower()
    if narration in ("none", "disabled", ""):
        narration = "disabled"
    elif narration not in NARRATION_PRESETS:
        narration = "elevenlabs"

    music = str(raw.get("music_provider") or "none").strip().lower()
    if music not in MUSIC_PRESETS:
        music = "none"

    lang = str(raw.get("language") or "English").strip()
    if lang.lower() in LANGUAGE_PRESETS and lang.lower() != "custom":
        lang = _pick_language(lang)

    uploads: list[str] = []
    for item in raw.get("upload_platforms") or []:
        u = str(item).strip().lower()
        if u in UPLOAD_PLATFORM_PRESETS and u not in uploads:
            uploads.append(u)
    if not uploads:
        uploads = ["tiktok", "instagram_reels", "youtube_shorts"]

    def _str_list(key: str) -> list[str]:
        val = raw.get(key) or []
        if isinstance(val, str):
            val = [v.strip() for v in val.split(",") if v.strip()]
        return [str(x).strip() for x in val if str(x).strip()]

    return ChannelProfileSuggestion(
        channel_name=str(raw.get("channel_name") or "").strip(),
        main_niche=str(raw.get("main_niche") or "").strip(),
        sub_niche=str(raw.get("sub_niche") or "").strip(),
        channel_topic=str(raw.get("channel_topic") or "").strip(),
        target_audience=str(raw.get("target_audience") or "").strip(),
        language=lang,
        tone_style=tone,
        visual_style=visual,
        default_platform=platform,
        default_duration_seconds=duration,
        default_provider=provider,
        default_narration_provider=narration,
        default_voice=str(raw.get("default_voice") or "").strip(),
        music_provider=music,
        preferred_topics=_str_list("preferred_topics"),
        forbidden_topics=_str_list("forbidden_topics"),
        content_formats=_str_list("content_formats"),
        upload_platforms=uploads,
        use_ai_director_default=bool(raw.get("use_ai_director_default", True)),
        use_prompt_critic_default=bool(raw.get("use_prompt_critic_default", True)),
        reasoning=str(raw.get("reasoning") or "").strip(),
        source=str(raw.get("source") or "rule_based"),
    )


def generate_channel_profile_suggestion(
    channel_topic_or_niche: str,
    *,
    language_preference: str | None = None,
    platform_preference: str | None = None,
    force_rule_based: bool = False,
) -> ChannelProfileSuggestion:
    topic = (channel_topic_or_niche or "").strip()
    if not topic:
        return normalize_suggestion(
            _rule_based_suggestion("", language_preference=language_preference).to_dict()
        )

    if not force_rule_based:
        ai = _openai_suggestion(
            topic,
            language_preference=language_preference,
            platform_preference=platform_preference,
        )
        if ai is not None:
            return ai

    return normalize_suggestion(
        _rule_based_suggestion(
            topic,
            language_preference=language_preference,
            platform_preference=platform_preference,
        ).to_dict()
    )
