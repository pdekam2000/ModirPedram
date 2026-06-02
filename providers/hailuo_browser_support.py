"""
Phase 11F-b — Hailuo browser mode config and error helpers.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from providers.hailuo_api_errors import HailuoCancelledError, HailuoProviderError
from providers.hailuo_artifact_utils import MIN_ARTIFACT_BYTES
from providers.hailuo_error_classifier import classify_hailuo_error

BROWSER_PROVIDER_VERSION = "11f_b_v1"

CancelCheck = Callable[[], bool]


def browser_max_wait_seconds() -> int:
    return max(1, int(os.getenv("HAILUO_BROWSER_MAX_WAIT_SECONDS", "900")))


def browser_poll_interval() -> float:
    return max(0.5, float(os.getenv("HAILUO_BROWSER_POLL_INTERVAL", "10")))


def browser_page_settle_seconds() -> float:
    return min(30.0, max(0.0, float(os.getenv("HAILUO_BROWSER_PAGE_SETTLE_SECONDS", "8"))))


def browser_assets_settle_seconds() -> float:
    return min(30.0, max(0.0, float(os.getenv("HAILUO_BROWSER_ASSETS_SETTLE_SECONDS", "10"))))


def browser_step_timeout_ms() -> int:
    return max(1000, int(os.getenv("HAILUO_BROWSER_STEP_TIMEOUT_MS", "20000")))


def check_cancel(
    cancel_check: CancelCheck | None,
    phase: str,
    *,
    partial_paths: list[str] | None = None,
    clip_results: list[dict[str, Any]] | None = None,
) -> None:
    if cancel_check and cancel_check():
        raise HailuoCancelledError(
            f"Hailuo browser cancelled during {phase}",
            partial_paths=list(partial_paths or []),
            clip_results=list(clip_results or []),
            phase=phase,
        )


def wrap_browser_error(
    error: BaseException | str,
    *,
    http_status: int | None = None,
    details: dict[str, Any] | None = None,
    default_code: str | None = None,
) -> HailuoProviderError:
    if isinstance(error, HailuoCancelledError):
        return error
    if isinstance(error, HailuoProviderError):
        return error
    code = default_code or classify_hailuo_error(error, http_status=http_status, context=details)
    return HailuoProviderError(
        str(error),
        code=code,
        http_status=http_status,
        details=details,
        cause=error if isinstance(error, BaseException) else None,
    )


__all__ = [
    "BROWSER_PROVIDER_VERSION",
    "MIN_ARTIFACT_BYTES",
    "CancelCheck",
    "browser_max_wait_seconds",
    "browser_poll_interval",
    "browser_page_settle_seconds",
    "browser_assets_settle_seconds",
    "browser_step_timeout_ms",
    "check_cancel",
    "wrap_browser_error",
]
