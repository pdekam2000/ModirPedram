"""
Phase 11E-a — Runway-specific error → failure taxonomy code mapping.

Extends existing 10J taxonomy; does not replace it. No provider execution.
"""

from __future__ import annotations

import re
from typing import Any

from content_brain.execution.failure_taxonomy import classify_failure

CLASSIFIER_VERSION = "11e_a_v1"

# Patterns grouped by taxonomy code (first match wins).
_PATTERN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CREDENTIALS_MISSING", (
        r"runway_api_key not found",
        r"missing environment variable:\s*runway_api_key",
        r"api key env not configured",
        r"credentials missing",
        r"no api key",
    )),
    ("CREDENTIALS_INVALID", (
        r"401",
        r"403",
        r"unauthorized",
        r"invalid api key",
        r"invalid credential",
        r"authentication failed",
        r"forbidden",
    )),
    ("API_QUOTA_EXCEEDED", (
        r"429",
        r"rate limit",
        r"quota exceeded",
        r"too many requests",
        r"402",
    )),
    ("PROVIDER_TIMEOUT", (
        r"timeouterror",
        r"timeout waiting",
        r"timed out",
        r"deadline exceeded",
    )),
    ("DOWNLOAD_FAILED", (
        r"failed to download",
        r"download failed",
        r"runway download",
    )),
    ("ARTIFACT_TOO_SMALL", (
        r"file too small",
        r"artifact_too_small",
        r"probably invalid",
    )),
    ("ARTIFACT_VALIDATION_FAILED", (
        r"artifact validation failed",
        r"artifact_invalid",
        r"invalid artifact",
        r"artifact_invalid_type",
    )),
    ("CAPABILITY_RUNTIME_UNSUPPORTED", (
        r"unsupported capability",
        r"capability_runtime_unsupported",
        r"image_to_video",
        r"image-to-video",
        r"not implemented",
    )),
    ("PROVIDER_DISABLED", (
        r"provider disabled",
        r"api mode disabled",
        r"enabled:\s*false",
    )),
    ("BROWSER_SESSION_INVALID", (
        r"browser session invalid",
        r"login required",
        r"not authenticated",
        r"session expired",
    )),
    ("BROWSER_UNAVAILABLE", (
        r"browser unavailable",
        r"cdp not reachable",
        r"chrome is not running",
        r"remote debugging",
        r"playwright cdp attach failed",
    )),
    ("PROVIDER_TASK_FAILED", (
        r"task failed",
        r"cancelled",
        r"runway task failed",
        r"no generated video url",
    )),
    ("API_CONNECTIVITY_FAILED", (
        r"connectivity",
        r"connection refused",
        r"api connectivity",
    )),
    ("API_ENDPOINT_NOT_CONFIGURED", (
        r"endpoint not configured",
        r"invalid base url",
        r"no api endpoint",
    )),
    ("BROWSER_AUTOMATION_NOT_READY", (
        r"could not click",
        r"could not fill prompt",
        r"browser automation",
    )),
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseException):
        parts = [str(value), repr(value)]
        return " ".join(parts).lower()
    return str(value).lower()


def classify_runway_error(
    error: BaseException | str | None,
    *,
    http_status: int | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Map a Runway error to an existing failure taxonomy code."""
    ctx = context or {}
    if ctx.get("capability") == "image_to_video" and ctx.get("runtime_supported") is False:
        return "CAPABILITY_RUNTIME_UNSUPPORTED"
    if ctx.get("provider_disabled"):
        return "PROVIDER_DISABLED"

    if http_status == 401:
        return "CREDENTIALS_INVALID"
    if http_status == 403:
        return "CREDENTIALS_INVALID"
    if http_status in {402, 429}:
        return "API_QUOTA_EXCEEDED"

    text = _normalize_text(error)
    if not text:
        return "PROVIDER_RUNTIME_ERROR"

    for code, patterns in _PATTERN_RULES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return code

    if isinstance(error, TimeoutError):
        return "PROVIDER_TIMEOUT"

    return "PROVIDER_RUNTIME_ERROR"


def classify_runway_failure(
    error: BaseException | str | None,
    *,
    http_status: int | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return full taxonomy metadata for a Runway error."""
    code = classify_runway_error(error, http_status=http_status, context=context)
    meta = classify_failure(code)
    return {
        "classifier_version": CLASSIFIER_VERSION,
        "code": meta["code"],
        "category": meta["category"],
        "retriable": meta["retriable"],
        "http_status": meta["http_status"],
    }


__all__ = [
    "CLASSIFIER_VERSION",
    "classify_runway_error",
    "classify_runway_failure",
]
