"""YouTube metadata generator — publish-ready metadata without upload or API calls."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

YOUTUBE_METADATA_VERSION = "youtube_metadata_generator_v1"
YOUTUBE_METADATA_FILENAME = "youtube_metadata.json"
SHORTS_MAX_DURATION_SECONDS = 60
LONG_FORM_MIN_DURATION_SECONDS = 61

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

PLATFORM_TAGS = ("youtube", "shorts", "short video", "ai video", "generative video")
GENRE_TAGS = ("storytelling", "cinematic", "viral", "trending")


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

    title = _clean_title(next((item for item in candidates if item.strip()), topic))
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
    channel = str(channel_profile.get("channel_name") or "Channel").strip()
    summary = _build_hook(topic, story_hook, narration_script)
    lines = [summary, ""]
    if is_short:
        lines.append("Built for YouTube Shorts — fast hook, cinematic pacing, native audio.")
    else:
        dur = int(duration_seconds or 0)
        lines.append(f"Long-form story video (~{dur}s) with multi-clip continuity.")
    lines.extend(["", f"Channel: {channel}"])
    disclosure = _ai_disclosure_block(channel_profile)
    if disclosure:
        lines.extend(["", disclosure])
    lines.extend(["", cta_text, "", " ".join(hashtags)])
    return "\n".join(line for line in lines if line is not None).strip()


def _build_tags(*, topic: str, channel_profile: dict[str, Any], is_short: bool, prompts: list[str]) -> list[str]:
    topic_tags = _topic_words(topic)
    niche = str(channel_profile.get("main_niche") or "").lower()
    niche_tags = _topic_words(niche)
    prompt_tags: list[str] = []
    for prompt in prompts[:3]:
        prompt_tags.extend(_topic_words(prompt)[:3])
    tags = topic_tags + niche_tags + list(GENRE_TAGS) + list(PLATFORM_TAGS) + prompt_tags
    if is_short:
        tags.extend(["youtube shorts", "vertical video", "short form"])
    else:
        tags.extend(["long form", "multi clip", "story video"])
    tags.extend(["ai generated", "ai video", "generative ai"])
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = tag.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(tag[:40])
    return deduped[:30]


def _build_hashtags(*, topic: str, channel_profile: dict[str, Any], is_short: bool) -> list[str]:
    base = list(channel_profile.get("youtube_default_hashtags") or [])
    topic_tags = _topic_words(topic)
    generated = base + topic_tags + (["shorts"] if is_short else ["longform"])
    niche = str(channel_profile.get("main_niche") or "")
    generated.extend(_topic_words(niche))
    generated.extend(["AIVideo", "YouTube"])
    return _dedupe_hashtags([str(item) for item in generated])


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
    tags = _build_tags(topic=topic, channel_profile=profile, is_short=short, prompts=prompt_list)
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
    "LONG_FORM_MIN_DURATION_SECONDS",
    "SHORTS_MAX_DURATION_SECONDS",
    "YOUTUBE_METADATA_FILENAME",
    "YOUTUBE_METADATA_VERSION",
    "ensure_product_studio_publish_metadata",
    "generate_and_save_youtube_metadata",
    "generate_youtube_metadata",
    "is_youtube_shorts",
    "load_youtube_metadata",
    "save_youtube_metadata",
]
