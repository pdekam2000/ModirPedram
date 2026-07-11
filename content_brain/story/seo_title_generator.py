"""OpenAI SEO title generator for channel story ideation."""

from __future__ import annotations

import logging
import os
import random
import re
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)

SEO_TITLE_GENERATOR_VERSION = "seo_title_generator_v4_dedup_50_facts"
MAX_TITLE_CHARS = 60
REQUEST_TIMEOUT_SECONDS = 45.0
MODEL_PREFERENCE = ("gpt-4.1-mini", "gpt-4.1")
DEDUP_WINDOW = 50
MAX_GENERATION_ATTEMPTS = 8
VARIETY_CHECK_COUNT = 3

YOUTUBE_POWER_WORDS: tuple[str, ...] = (
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

INSTAGRAM_POWER_WORDS: tuple[str, ...] = (
    "Secret",
    "Hidden",
    "This Changes",
    "Try This",
    "Stop Using",
    "The Only",
    "Game-Changing",
    "Dermatologists Use",
    "Viral",
    "Actually Works",
)

SYSTEM_PROMPT = """You are a YouTube/Instagram SEO expert.
Generate ONE viral, click-worthy title for a short video. Rules:
- Under 60 characters
- MUST begin with the exact required opener phrase provided in the user message
- Creates curiosity gap — viewer MUST click
- No clickbait lies — must match content
- For science: mysterious and mind-blowing
- For beauty: aspirational and practical
Return ONLY the title, nothing else."""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _strip_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def _trim_title(title: str, *, max_chars: int = MAX_TITLE_CHARS) -> str:
    cleaned = _clean(title)
    if len(cleaned) <= max_chars:
        return cleaned
    trimmed = cleaned[: max_chars - 1].rsplit(" ", 1)[0].rstrip(".,;:!?")
    return trimmed or cleaned[:max_chars]


def _is_beauty_platform(platform: str) -> bool:
    return str(platform or "").lower() in {"instagram_reels", "instagram"}


def _platform_key(platform: str) -> str:
    normalized = str(platform or "").lower()
    if normalized in {"instagram_reels", "instagram"}:
        return "instagram"
    if normalized in {"youtube_shorts", "youtube"}:
        return "youtube"
    return normalized or "youtube"


def _load_story_memory(project_root: str | Path | None) -> list[dict[str, Any]]:
    if not project_root:
        return []
    try:
        from content_brain.execution.channel_story_ideation import load_story_memory

        return load_story_memory(project_root)
    except Exception:
        return []


def _titles_from_memory_rows(
    rows: list[dict[str, Any]],
    *,
    platform: str,
    limit: int,
) -> list[str]:
    normalized_platform = _platform_key(platform)
    titles: list[str] = []
    for row in reversed(rows):
        row_platform = _platform_key(str(row.get("target_platform") or row.get("platform") or ""))
        if row_platform and normalized_platform and row_platform != normalized_platform:
            continue
        title = _clean(str(row.get("title") or ""))
        if title:
            titles.append(title)
        if len(titles) >= limit:
            break
    titles.reverse()
    return titles


def get_last_n_titles(
    n: int,
    platform: str,
    *,
    story_memory: list[dict[str, Any]] | None = None,
    project_root: str | Path | None = None,
) -> list[str]:
    """Return the last n titles for a platform from story memory (chronological)."""
    memory = list(story_memory or _load_story_memory(project_root))
    return _titles_from_memory_rows(memory, platform=platform, limit=max(0, int(n)))


def _power_words_for_platform(platform: str) -> tuple[str, ...]:
    if _is_beauty_platform(platform):
        return INSTAGRAM_POWER_WORDS
    return YOUTUBE_POWER_WORDS


def _first_token(text: str) -> str:
    cleaned = _clean(text)
    return cleaned.split(" ", 1)[0].lower() if cleaned else ""


def _pick_random_power_word(
    platform: str,
    *,
    exclude: set[str] | None = None,
    exclude_first_tokens: set[str] | None = None,
) -> str:
    blocked = {word.lower() for word in (exclude or set())}
    blocked_tokens = {token.lower() for token in (exclude_first_tokens or set())}
    pool = [
        word
        for word in _power_words_for_platform(platform)
        if word.lower() not in blocked and _first_token(word) not in blocked_tokens
    ]
    if not pool:
        pool = [
            word for word in _power_words_for_platform(platform) if word.lower() not in blocked
        ]
    if not pool:
        pool = list(_power_words_for_platform(platform))
    return random.choice(pool)


def _build_forced_opener_prompt(
    *,
    target_platform: str,
    power_word: str,
    content_title: str,
    logline: str,
    visual_hook: str,
    niche: str,
    genre_hint: str,
) -> str:
    label = "Instagram Reel" if _is_beauty_platform(target_platform) else "YouTube Short"
    topic = _clean(content_title or logline or visual_hook)
    return (
        f"Create a {label} title using '{power_word}' as the opener about: {topic}\n"
        f'The title MUST start with "{power_word}".\n'
        f"Story context: {logline}\n"
        f"Visual hook: {visual_hook}\n"
        f"Niche: {niche or genre_hint}\n"
    )


def _title_starts_with_power_word(title: str, power_word: str) -> bool:
    lowered_title = _clean(title).lower()
    lowered_word = _clean(power_word).lower()
    return lowered_title.startswith(lowered_word)


def _request_openai_title(
    *,
    client: OpenAI,
    model: str,
    user_content: str,
    avoid_titles: list[str] | None = None,
) -> str:
    prompt = user_content
    if avoid_titles:
        joined = "; ".join(avoid_titles[:12])
        prompt += f"\nDo NOT reuse or closely mimic these recent titles: {joined}\n"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.75,
        max_tokens=80,
    )
    raw = _strip_fences((response.choices[0].message.content or "").strip())
    return _trim_title(raw)


def generate_seo_title(
    *,
    content_title: str,
    logline: str = "",
    visual_hook: str = "",
    target_platform: str = "youtube_shorts",
    niche: str = "",
    dry_run: bool = False,
    project_root: str | Path | None = None,
    story_memory: list[dict[str, Any]] | None = None,
    exclude_power_words: list[str] | None = None,
) -> dict[str, Any]:
    """Generate one SEO-optimized title via OpenAI; fall back to content_title."""
    meta: dict[str, Any] = {
        "version": SEO_TITLE_GENERATOR_VERSION,
        "openai_applied": False,
        "openai_model": "",
        "seo_title": _trim_title(content_title),
        "source_title": _clean(content_title),
        "force_different_opener": False,
        "dedup_attempts": 0,
        "notes": [],
    }
    if dry_run:
        meta["notes"].append("seo_title_dry_run")
        return meta

    try:
        from content_brain.story.kling_story_first_openai_writer import get_openai_client

        client = get_openai_client(project_root=project_root)
    except ValueError as exc:
        meta["notes"].append(f"openai_unavailable:{exc}")
        if _is_beauty_platform(target_platform):
            logger.error("OpenAI SEO title client unavailable for Instagram: %s", exc)
        return meta

    memory = list(story_memory or _load_story_memory(project_root))
    recent_science_facts: set[str] = set()
    if not _is_beauty_platform(target_platform):
        try:
            from content_brain.execution.channel_story_ideation import get_last_n_science_facts

            recent_science_facts = {
                key.lower()
                for key in get_last_n_science_facts(DEDUP_WINDOW, target_platform, history=memory)
            }
            fact_key = _clean(content_title).lower()
            if fact_key and fact_key in recent_science_facts:
                meta["notes"].append(f"seo_title_science_fact_recently_used:{fact_key[:48]}")
        except Exception:
            pass

    recent_titles = get_last_n_titles(VARIETY_CHECK_COUNT, target_platform, story_memory=memory)
    force_different_opener = len(recent_titles) >= VARIETY_CHECK_COUNT and all(
        "Shocking" in title for title in recent_titles
    )
    meta["force_different_opener"] = force_different_opener
    if force_different_opener:
        meta["notes"].append("seo_title_variety_forced_different_opener")

    used_titles = {
        title.lower()
        for title in get_last_n_titles(DEDUP_WINDOW, target_platform, story_memory=memory)
    }
    genre_hint = "beauty skincare tutorial" if _is_beauty_platform(target_platform) else "science short"

    last_error = ""
    tried_power_words: set[str] = {word.lower() for word in (exclude_power_words or [])}
    used_first_tokens: set[str] = {_first_token(word) for word in (exclude_power_words or [])}
    for row in memory[-10:]:
        if _platform_key(str(row.get("target_platform") or "")) != _platform_key(target_platform):
            continue
        prior_word = _clean(str(row.get("seo_power_word") or ""))
        if prior_word:
            tried_power_words.add(prior_word.lower())
            used_first_tokens.add(_first_token(prior_word))
    if force_different_opener:
        tried_power_words.add("shocking")
        used_first_tokens.add("shocking")

    for model in MODEL_PREFERENCE:
        for attempt in range(MAX_GENERATION_ATTEMPTS):
            power_word = _pick_random_power_word(
                target_platform,
                exclude=tried_power_words,
                exclude_first_tokens=used_first_tokens,
            )
            tried_power_words.add(power_word.lower())
            used_first_tokens.add(_first_token(power_word))
            user_content = _build_forced_opener_prompt(
                target_platform=target_platform,
                power_word=power_word,
                content_title=content_title,
                logline=logline,
                visual_hook=visual_hook,
                niche=niche,
                genre_hint=genre_hint,
            )
            try:
                title = _request_openai_title(
                    client=client,
                    model=model,
                    user_content=user_content,
                    avoid_titles=list(used_titles) if used_titles else None,
                )
                if not title:
                    last_error = f"empty_response:{model}"
                    continue
                if not _title_starts_with_power_word(title, power_word):
                    meta["notes"].append(f"seo_title_opener_mismatch:{power_word}")
                    continue
                meta["dedup_attempts"] = attempt + 1
                if title.lower() in used_titles:
                    meta["notes"].append(f"seo_title_duplicate_rejected:{title[:48]}")
                    continue
                meta["openai_applied"] = True
                meta["openai_model"] = model
                meta["seo_title"] = title
                meta["power_word_used"] = power_word
                meta["notes"].append(f"seo_title_openai:{model}")
                if attempt > 0:
                    meta["notes"].append(f"seo_title_regenerated_attempt_{attempt + 1}")
                return meta
            except Exception as exc:  # pragma: no cover
                last_error = f"{model}:{exc}"
                if _is_beauty_platform(target_platform):
                    logger.error("OpenAI SEO title request failed for Instagram (%s): %s", model, exc)
                break

    meta["notes"].append(f"seo_title_failed:{last_error or 'dedup_exhausted'}")
    if _is_beauty_platform(target_platform) and not meta.get("openai_applied"):
        logger.error("OpenAI SEO title failed for Instagram: %s", last_error or "dedup_exhausted")
    return meta


__all__ = [
    "DEDUP_WINDOW",
    "INSTAGRAM_POWER_WORDS",
    "SEO_TITLE_GENERATOR_VERSION",
    "SYSTEM_PROMPT",
    "VARIETY_CHECK_COUNT",
    "YOUTUBE_POWER_WORDS",
    "generate_seo_title",
    "get_last_n_titles",
]
