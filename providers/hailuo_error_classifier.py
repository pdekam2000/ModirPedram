"""
Phase 11F-a — Hailuo / MiniMax error → failure taxonomy code mapping.

Extends existing 10J taxonomy; does not replace it. No provider execution.
"""

from __future__ import annotations

import re
from typing import Any

from content_brain.execution.failure_taxonomy import classify_failure

CLASSIFIER_VERSION = "11f_c_v1"

_PATTERN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("OPERATIONS_CANCELLED", (
        r"cancel requested",
        r"cancelled by operator",
        r"hailuo.*cancelled",
        r"operation.*cancelled",
        r"cooperative cancel",
        r"cancel during download",
    )),
    ("PROVIDER_NOT_IMPLEMENTED", (
        r"notimplementederror",
        r"not implemented",
        r"metadata-only",
        r"hailuo api.*not implemented",
        r"minimax.*stub",
        r"provider not implemented",
    )),
    ("CREDENTIALS_MISSING", (
        r"hailuo_api_key",
        r"minimax_api_key",
        r"missing environment variable",
        r"api credential missing",
        r"credentials missing",
        r"no api key",
    )),
    ("BROWSER_SESSION_INVALID", (
        r"browser session invalid",
        r"session expired",
        r"login required",
        r"not authenticated",
        r"auth wall",
    )),
    ("CREDENTIALS_INVALID", (
        r"401",
        r"403",
        r"unauthorized",
        r"invalid api key",
        r"authentication failed",
    )),
    ("PROVIDER_DISABLED", (
        r"provider disabled",
        r"api disabled",
        r"enabled:\s*false",
    )),
    ("CAPABILITY_RUNTIME_UNSUPPORTED", (
        r"unsupported capability",
        r"capability_runtime_unsupported",
        r"image_to_video",
        r"image-to-video",
    )),
    ("PROVIDER_TIMEOUT", (
        r"timeouterror",
        r"timeout waiting",
        r"generation timeout",
        r"timed out",
        r"deadline exceeded",
        r"wait_seconds exceeded",
    )),
    ("DOWNLOAD_FAILED", (
        r"failed to download",
        r"download failed",
        r"hailuo download",
        r"could not extract video",
        r"video extraction failed",
        r"invalid.*source url",
        r"invalid hailuo download source",
        r"no video element found",
    )),
    ("ARTIFACT_NULL_PATH", (
        r"artifact file_path is missing",
        r"artifact_null_path",
        r"missing file_path",
        r"clip_results entry missing file_path",
    )),
    ("ARTIFACT_PATH_MISSING", (
        r"artifact path does not exist",
        r"artifact_path_missing",
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
        r"artifact invalid",
    )),
    ("BROWSER_UNAVAILABLE", (
        r"browser unavailable",
        r"cdp not reachable",
        r"chrome is not running",
        r"remote debugging",
        r"playwright cdp attach failed",
    )),
    ("BROWSER_AUTOMATION_NOT_READY", (
        r"could not click create",
        r"create button not found",
        r"selector not found",
        r"browser automation",
        r"contenteditable",
    )),
    ("API_ENDPOINT_NOT_CONFIGURED", (
        r"endpoint not configured",
        r"invalid base url",
        r"no api endpoint",
    )),
    ("API_CONNECTIVITY_FAILED", (
        r"connectivity",
        r"connection refused",
        r"api connectivity",
    )),
    ("PROVIDER_TASK_FAILED", (
        r"task failed",
        r"generation failed",
        r"no generated video",
    )),
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseException):
        parts = [str(value), repr(value)]
        return " ".join(parts).lower()
    return str(value).lower()


def classify_hailuo_error(
    error: BaseException | str | None,
    *,
    http_status: int | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Map a Hailuo/MiniMax error to an existing failure taxonomy code."""
    ctx = context or {}
    if ctx.get("cancel_requested"):
        return "OPERATIONS_CANCELLED"
    if ctx.get("provider_not_implemented"):
        return "PROVIDER_NOT_IMPLEMENTED"
    if ctx.get("provider_disabled"):
        return "PROVIDER_DISABLED"
    if ctx.get("capability") == "image_to_video" and ctx.get("runtime_supported") is False:
        return "CAPABILITY_RUNTIME_UNSUPPORTED"

    if http_status == 401:
        return "CREDENTIALS_INVALID"
    if http_status == 403:
        return "CREDENTIALS_INVALID"

    text = _normalize_text(error)
    if not text:
        return "PROVIDER_RUNTIME_ERROR"

    for code, patterns in _PATTERN_RULES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return code

    if isinstance(error, TimeoutError):
        return "PROVIDER_TIMEOUT"
    if isinstance(error, NotImplementedError):
        return "PROVIDER_NOT_IMPLEMENTED"

    return "PROVIDER_RUNTIME_ERROR"


def classify_hailuo_failure(
    error: BaseException | str | None,
    *,
    http_status: int | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return full taxonomy metadata for a Hailuo/MiniMax error."""
    code = classify_hailuo_error(error, http_status=http_status, context=context)
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
    "classify_hailuo_error",
    "classify_hailuo_failure",
]
