"""Strict platform/topic guards for automation uploads — no cross-platform bleed."""

from __future__ import annotations

import logging
import re
from typing import Any

GUARD_VERSION = "platform_upload_guard_v7_instagram_perfumery_bypass"
_logger = logging.getLogger(__name__)

YOUTUBE_PLATFORMS = frozenset({"youtube_shorts", "youtube"})
INSTAGRAM_PLATFORMS = frozenset({"instagram_reels", "instagram"})
TIKTOK_PLATFORMS = frozenset({"tiktok"})

YOUTUBE_TOPIC_REQUIRED = (
    "science",
    "physics",
    "brain",
    "body",
    "space",
    "quantum",
    "biology",
    "human",
    "earth",
    "atom",
    "light",
    "time",
    "impossible",
    "mystery",
    "cellular",
    "cosmic",
    "perception",
    "evolution",
    "ocean",
    "microscopic",
    "gravity",
    "relativity",
    "molecular",
    "astronaut",
    "galaxy",
    "organism",
    "survival",
    "magnetic",
    "radiation",
)
YOUTUBE_SKINCARE_BLOCK_KEYWORDS = (
    "skincare",
    "moisturizer",
    "face mask",
    "serum",
    "beauty routine",
)
YOUTUBE_SCIENCE_SAFE_PHRASES = (
    "skin cells",
    "skin deep",
    "human skin",
    "glowing",
    "glow",
)
YOUTUBE_TOPIC_FORBIDDEN = YOUTUBE_SKINCARE_BLOCK_KEYWORDS + (
    "hilarious fail",
    "pet fail",
    "dark fantasy",
    "cinematic miniature",
)
INSTAGRAM_TOPIC_REQUIRED = (
    # Legacy beauty lane
    "skincare",
    "beauty",
    "routine",
    "glow",
    "self-care",
    # Perfumery education lane
    "perfume",
    "fragrance",
    "perfumery",
    "scent",
    "ingredient",
    "aroma",
    "cologne",
    "oud",
    "absolute",
    "essential oil",
    "essential",
    "distillation",
    "extraction",
)
INSTAGRAM_TOPIC_FORBIDDEN = ("animal", "dog", "cat", "funny", "fail", "husky", "pet", "comedy")
INSTAGRAM_PERFUMERY_BYPASS_MARKERS = ("perfumery", "fragrance", "perfume", "scent")


def _contains_keyword(text: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword)}\b", str(text or ""), flags=re.IGNORECASE) is not None


def _youtube_has_skincare_contamination(text: str) -> bool:
    """Block only clear skincare/beauty terms; never block science skin/glow phrasing."""
    cleaned = str(text or "")
    for phrase in YOUTUBE_SCIENCE_SAFE_PHRASES:
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
    return any(_contains_keyword(cleaned, keyword) for keyword in YOUTUBE_SKINCARE_BLOCK_KEYWORDS)


def blocked_youtube_skincare_keyword(text: str) -> str:
    """Return the first skincare block keyword matched in text, or empty string."""
    cleaned = str(text or "")
    for phrase in YOUTUBE_SCIENCE_SAFE_PHRASES:
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
    for keyword in YOUTUBE_SKINCARE_BLOCK_KEYWORDS:
        if _contains_keyword(cleaned, keyword):
            return keyword
    return ""


def normalize_platform(platform: str) -> str:
    key = str(platform or "").strip().lower()
    if key in {"youtube", "youtube_shorts"}:
        return "youtube_shorts"
    if key in {"instagram", "instagram_reels"}:
        return "instagram_reels"
    if key == "tiktok":
        return "tiktok"
    return key


def validate_topic_for_platform(
    platform: str,
    topic: str,
    *,
    source: str = "content",
) -> tuple[bool, str]:
    """Block upload when topic does not match the target platform lane.

    source:
      - content: generated titles/stories — enforce required + forbidden keywords
      - channel_brief: profile topic briefs — required keywords only (briefs may
        mention other platforms in setup/cleanup instructions)
    """
    normalized = normalize_platform(platform)
    if normalized == "youtube_shorts":
        # YouTube accepts all science content; cross-platform guard is Instagram-only.
        return True, "ok"

    text = str(topic or "").strip()
    if not text:
        return False, "upload_topic_missing"

    check_forbidden = str(source or "content").lower() != "channel_brief"

    if normalized == "instagram_reels":
        lowered = text.lower()
        # Perfumery / fragrance education is always allowed on Instagram.
        if any(marker in lowered for marker in INSTAGRAM_PERFUMERY_BYPASS_MARKERS):
            return True, "ok"
        if check_forbidden and any(_contains_keyword(text, keyword) for keyword in INSTAGRAM_TOPIC_FORBIDDEN):
            return False, "youtube_keywords_in_instagram_upload"
        if not any(_contains_keyword(text, keyword) for keyword in INSTAGRAM_TOPIC_REQUIRED):
            return False, "instagram_topic_missing_channel_keywords"
        return True, "ok"

    return True, ""


def upload_platform_allowed(*, job_platform: str, upload_platform: str) -> bool:
    """Return True only when upload platform matches the automation job platform."""
    job_key = normalize_platform(job_platform)
    upload_key = normalize_platform(upload_platform)
    if not job_key or not upload_key:
        return False
    return job_key == upload_key


def resolve_job_upload_targets(platform_targets: list[str] | None) -> list[str]:
    """Automation jobs upload to exactly one platform — their own target."""
    targets = [str(item).strip() for item in (platform_targets or []) if str(item).strip()]
    if not targets:
        return []
    primary = normalize_platform(targets[0])
    if primary == "youtube_shorts":
        return ["youtube_shorts"]
    if primary == "instagram_reels":
        return ["instagram_reels"]
    if primary == "tiktok":
        return ["tiktok"]
    return [targets[0]]


def guard_upload_or_block(
    *,
    job_platform: str,
    upload_platform: str,
    topic: str,
) -> tuple[bool, str]:
    if not upload_platform_allowed(job_platform=job_platform, upload_platform=upload_platform):
        reason = f"cross_platform_upload_blocked:{normalize_platform(job_platform)}->{normalize_platform(upload_platform)}"
        _logger.error("Upload blocked: %s topic=%s", reason, str(topic or "")[:120])
        return False, reason
    ok, reason = validate_topic_for_platform(upload_platform, topic)
    if not ok:
        _logger.error(
            "Upload blocked: topic/platform mismatch platform=%s reason=%s topic=%s",
            normalize_platform(upload_platform),
            reason,
            str(topic or "")[:120],
        )
    return ok, reason


class PlatformMatchError(ValueError):
    """Topic does not match the target upload platform."""


def validate_platform_match(job: dict[str, Any] | Any, platform: str) -> None:
    """Raise PlatformMatchError when job topic does not belong on the upload platform."""
    if isinstance(job, dict):
        topic = str(job.get("topic") or job.get("title") or "")
        job_platform = str(
            job.get("platform")
            or (job.get("platform_targets") or [""])[0]
            or platform
        )
    else:
        topic = str(getattr(job, "topic", "") or getattr(job, "title", "") or "")
        targets = getattr(job, "platform_targets", None) or []
        job_platform = str(getattr(job, "platform", "") or (targets[0] if targets else platform))

    upload_platform = normalize_platform(platform or job_platform)
    if upload_platform == "youtube_shorts":
        return
    lowered = topic.lower()
    if upload_platform == "instagram_reels" and any(
        marker in lowered for marker in ("hilarious fail", "pet fail", "animal comedy")
    ):
        raise PlatformMatchError("WRONG TOPIC for Instagram")

    ok, reason = validate_topic_for_platform(upload_platform, topic)
    if not ok:
        label = "YouTube" if upload_platform == "youtube_shorts" else "Instagram"
        raise PlatformMatchError(f"WRONG TOPIC for {label}: {reason}")


def guard_from_preflight(preflight: dict[str, Any], upload_platform: str, topic: str) -> tuple[bool, str]:
    job_platform = str(
        preflight.get("platform")
        or (preflight.get("platform_targets") or [""])[0]
        or ""
    )
    return guard_upload_or_block(
        job_platform=job_platform,
        upload_platform=upload_platform,
        topic=topic,
    )


__all__ = [
    "GUARD_VERSION",
    "PlatformMatchError",
    "guard_from_preflight",
    "guard_upload_or_block",
    "normalize_platform",
    "resolve_job_upload_targets",
    "upload_platform_allowed",
    "validate_platform_match",
    "validate_topic_for_platform",
]
