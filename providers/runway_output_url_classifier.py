"""
Phase 12J-E1 — Classify Runway browser output URLs vs UI placeholder assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from providers.runway_api_errors import RunwayProviderError

RUNWAY_REAL_OUTPUT_NOT_DETECTED = "RUNWAY_REAL_OUTPUT_NOT_DETECTED"
RUNWAY_PLACEHOLDER_OUTPUT_REJECTED = "RUNWAY_PLACEHOLDER_OUTPUT_REJECTED"

# Substrings in URL path/host that indicate UI shell assets, not generation output.
_REJECT_URL_SUBSTRINGS: tuple[str, ...] = (
    "empty-states",
    "edit-studio-empty-state",
    "empty_state",
    "empty-state",
    "/placeholder",
    "placeholder.",
    "/loading",
    "loading-state",
    "loading_state",
    "thumbnail-only",
    "thumbnail_only",
    "/ui-demo",
    "/demo-asset",
    "/static/demo",
    "sample-video",
    "onboarding",
)

# Path segments that are never treated as generated clip media.
_REJECT_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "empty-states",
        "placeholders",
        "placeholder",
        "loading",
        "loading-states",
        "thumbnails",
    }
)

# Known Runway app shell CDN layout (audit session exec_uat_20260602_190032).
_REJECT_PATH_PREFIXES: tuple[str, ...] = (
    "/app/mira/empty-states/",
    "app/mira/empty-states/",
)


def _normalized_url(url: str) -> str:
    return str(url or "").strip()


def _url_path_lower(url: str) -> str:
    parsed = urlparse(_normalized_url(url))
    return (parsed.path or "").lower()


def runway_output_rejection_reason(url: str) -> str | None:
    """
    Return a rejection reason string, or None if the URL may be real output.
    """
    text = _normalized_url(url)
    if not text:
        return "empty_url"

    lower = text.lower()
    path_lower = _url_path_lower(text)

    for prefix in _REJECT_PATH_PREFIXES:
        if prefix in lower:
            return f"reject_path_prefix:{prefix}"

    for marker in _REJECT_URL_SUBSTRINGS:
        if marker in lower:
            return f"reject_substring:{marker}"

    segments = [segment for segment in path_lower.split("/") if segment]
    for segment in segments:
        if segment in _REJECT_PATH_SEGMENTS:
            return f"reject_segment:{segment}"

    if path_lower.endswith(".webm") and (
        "empty-states" in path_lower
        or "empty-state" in path_lower
        or "edit-studio-empty-state" in path_lower
    ):
        return "reject_webm_app_shell"

    if "edit-studio-empty-state" in lower:
        return "reject_edit_studio_empty_state"

    filename = Path(path_lower).name
    if "empty-state" in filename or "empty_state" in filename:
        return "reject_filename_empty_state"

    if lower.startswith("data:") and "image" in lower[:32]:
        return "reject_data_image"

    return None


def is_real_runway_output_url(url: str) -> bool:
    """True when URL is not a known Runway UI placeholder / empty-state asset."""
    return runway_output_rejection_reason(url) is None


def assert_real_runway_output_source(
    source_url: str | None,
    *,
    file_path: str | Path | None = None,
    clip_index: int | None = None,
) -> None:
    """Raise if source URL or saved filename indicates a placeholder asset."""
    url = _normalized_url(source_url or "")
    path_str = str(file_path or "")

    if path_str:
        path_name = Path(path_str).name.lower()
        if "empty-state" in path_name or "empty_state" in path_name:
            raise RunwayProviderError(
                f"[Runway] Placeholder artifact filename rejected: {path_name}",
                code=RUNWAY_PLACEHOLDER_OUTPUT_REJECTED,
                details={
                    "clip_index": clip_index,
                    "file_path": path_str,
                    "source_url": url[:512] if url else None,
                },
            )

    if not url:
        raise RunwayProviderError(
            "[Runway] Missing source URL for output validation",
            code=RUNWAY_PLACEHOLDER_OUTPUT_REJECTED,
            details={"clip_index": clip_index, "file_path": path_str or None},
        )

    reason = runway_output_rejection_reason(url)
    if reason:
        raise RunwayProviderError(
            f"[Runway] Placeholder or UI asset URL rejected: {reason}",
            code=RUNWAY_PLACEHOLDER_OUTPUT_REJECTED,
            details={
                "clip_index": clip_index,
                "source_url": url[:512],
                "rejection_reason": reason,
                "file_path": path_str or None,
            },
        )


def build_rejected_candidate_entry(url: str, reason: str, *, source: str) -> dict[str, Any]:
    return {
        "url": _normalized_url(url)[:512],
        "reason": str(reason),
        "source": str(source),
    }


__all__ = [
    "RUNWAY_REAL_OUTPUT_NOT_DETECTED",
    "RUNWAY_PLACEHOLDER_OUTPUT_REJECTED",
    "is_real_runway_output_url",
    "runway_output_rejection_reason",
    "assert_real_runway_output_source",
    "build_rejected_candidate_entry",
]
