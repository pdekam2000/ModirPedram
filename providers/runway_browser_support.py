"""
Phase 11E-c — Runway browser mode config and error helpers.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from providers.runway_api_errors import RunwayCancelledError, RunwayProviderError
from providers.runway_error_classifier import classify_runway_error

BROWSER_PROVIDER_VERSION = "11e_c_v1"
from providers.runway_artifact_utils import MIN_ARTIFACT_BYTES

CancelCheck = Callable[[], bool]

DEFAULT_BROWSER_MAX_WAIT_SECONDS = 900
BROWSER_MAX_WAIT_FLOOR_SECONDS = 60
BROWSER_MAX_WAIT_CEILING_SECONDS = 1800
RUNWAY_BROWSER_FAMILY = "runway"

# Phase 12J-E0 — prompt injection verification (browser provider).
PROMPT_MIN_LENGTH_RATIO = 0.90
PROMPT_EDGE_COMPARE_CHARS = 50
PROMPT_PLACEHOLDER_MARKERS = (
    "describe your shot",
    "describe the shot",
    "first video frame",
)
PROMPT_INJECTION_INCOMPLETE = "PROMPT_INJECTION_INCOMPLETE"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def clamp_browser_max_wait_seconds(value: int) -> int:
    return max(BROWSER_MAX_WAIT_FLOOR_SECONDS, min(BROWSER_MAX_WAIT_CEILING_SECONDS, int(value)))


def _catalog_browser_max_wait_seconds() -> int | None:
    try:
        from content_brain.execution.provider_mode_catalog import ProviderModeCatalog

        entry = ProviderModeCatalog.load().get_family(RUNWAY_BROWSER_FAMILY) or {}
        raw = entry.get("browser_generation_max_wait_seconds")
        if raw is None:
            return None
        return int(raw)
    except Exception:
        return None


def _session_browser_max_wait_seconds(session: dict[str, Any] | None) -> int | None:
    if session is None:
        return None
    operations = _dict(session.get("operations"))
    raw = operations.get("runway_browser_max_wait_seconds")
    if raw is None:
        execution_runtime = _dict(session.get("execution_runtime"))
        operations = _dict(execution_runtime.get("operations"))
        raw = operations.get("runway_browser_max_wait_seconds")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def resolve_runway_browser_max_wait_seconds(
    session: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """
    Authoritative Runway browser generation wait (seconds).

    Precedence: env → session operations → provider_mode_catalog → default.
    Clamped to [60, 1800].
    """
    env_raw = os.getenv("RUNWAY_BROWSER_MAX_WAIT_SECONDS", "").strip()
    if env_raw:
        return (
            clamp_browser_max_wait_seconds(int(env_raw)),
            "env:RUNWAY_BROWSER_MAX_WAIT_SECONDS",
        )

    session_raw = _session_browser_max_wait_seconds(session)
    if session_raw is not None:
        return (
            clamp_browser_max_wait_seconds(session_raw),
            "session:operations.runway_browser_max_wait_seconds",
        )

    catalog_raw = _catalog_browser_max_wait_seconds()
    if catalog_raw is not None:
        return (
            clamp_browser_max_wait_seconds(catalog_raw),
            "catalog:provider_mode_catalog.runway.browser_generation_max_wait_seconds",
        )

    return DEFAULT_BROWSER_MAX_WAIT_SECONDS, "default:900"


def browser_max_wait_seconds(session: dict[str, Any] | None = None) -> int:
    seconds, _ = resolve_runway_browser_max_wait_seconds(session)
    return seconds


def log_runway_wait_config(session: dict[str, Any] | None = None) -> tuple[int, str]:
    wait_seconds, source = resolve_runway_browser_max_wait_seconds(session)
    print(f"[RUNWAY_WAIT_CONFIG] wait_seconds={wait_seconds} source={source}")
    return wait_seconds, source


def browser_poll_interval() -> float:
    return max(0.5, float(os.getenv("RUNWAY_BROWSER_POLL_INTERVAL", "10")))


def browser_page_settle_seconds() -> float:
    return min(30.0, max(0.0, float(os.getenv("RUNWAY_BROWSER_PAGE_SETTLE_SECONDS", "8"))))


def browser_ratio_duration_post_settle_seconds() -> float:
    """Sleep after ratio/duration clicks before stability polling."""
    return min(5.0, max(0.25, float(os.getenv("RUNWAY_BROWSER_RATIO_DURATION_POST_SETTLE_SECONDS", "1.25"))))


def browser_ratio_duration_stable_poll_interval() -> float:
    return max(0.15, float(os.getenv("RUNWAY_BROWSER_RATIO_DURATION_STABLE_POLL_SECONDS", "0.4")))


def browser_ratio_duration_stable_polls() -> int:
    return max(1, int(os.getenv("RUNWAY_BROWSER_RATIO_DURATION_STABLE_POLLS", "2")))


def browser_ratio_duration_stabilize_timeout_seconds() -> float:
    return min(30.0, max(1.0, float(os.getenv("RUNWAY_BROWSER_RATIO_DURATION_STABILIZE_TIMEOUT_SECONDS", "8"))))


def browser_generate_click_wait_seconds() -> float:
    return min(30.0, max(0.0, float(os.getenv("RUNWAY_BROWSER_GENERATE_CLICK_WAIT", "5"))))


def browser_prepare_step_timeout_ms() -> int:
    return max(1000, int(os.getenv("RUNWAY_BROWSER_PREPARE_STEP_TIMEOUT_MS", "15000")))


def browser_generate_editor_wait_seconds() -> float:
    return min(120.0, max(5.0, float(os.getenv("RUNWAY_BROWSER_EDITOR_WAIT_SECONDS", "30"))))


RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS = 10


def capture_runway_prep_debug(page: Any) -> dict[str, Any]:
    """Safe DOM probe for prep failures (no credentials)."""
    if page is None:
        return {"error": "page_missing"}
    try:
        return page.evaluate(
            """
            () => {
                const body = document.body ? (document.body.innerText || "") : "";
                const buttons = Array.from(document.querySelectorAll("button"));
                const generateButtons = buttons.filter((b) => {
                    const label = (b.innerText || b.textContent || b.getAttribute("aria-label") || "").trim();
                    return /generate/i.test(label);
                });
                return {
                    url: location.href || "",
                    mode_apps: (location.href || "").includes("mode=apps"),
                    textarea_count: document.querySelectorAll("textarea").length,
                    contenteditable_count: document.querySelectorAll("[contenteditable='true']").length,
                    prompt_box_count: document.querySelectorAll("textarea, [contenteditable='true']").length,
                    generate_button_count: generateButtons.length,
                    generate_enabled_count: generateButtons.filter((b) => !b.disabled).length,
                    gen45_visible: body.includes("Gen-4.5"),
                    describe_shot_visible: body.includes("Describe your shot"),
                    first_video_frame_visible: body.includes("First Video Frame"),
                    try_it_now_visible: /try it now/i.test(body),
                    apps_landing_visible: body.includes("Everything you need to make"),
                };
            }
            """
        )
    except Exception as exc:
        return {"error": str(exc)[:240]}


def check_cancel(cancel_check: CancelCheck | None, phase: str, *, partial_paths: list[str] | None = None) -> None:
    if cancel_check and cancel_check():
        raise RunwayCancelledError(
            f"Runway browser cancelled during {phase}",
            partial_paths=list(partial_paths or []),
            phase=phase,
        )


def wrap_browser_error(
    error: BaseException | str,
    *,
    http_status: int | None = None,
    details: dict[str, Any] | None = None,
    default_code: str | None = None,
) -> RunwayProviderError:
    if isinstance(error, RunwayCancelledError):
        return error
    if isinstance(error, RunwayProviderError):
        return error
    code = default_code or classify_runway_error(error, http_status=http_status, context=details)
    return RunwayProviderError(str(error), code=code, http_status=http_status, details=details, cause=error if isinstance(error, BaseException) else None)


__all__ = [
    "BROWSER_PROVIDER_VERSION",
    "MIN_ARTIFACT_BYTES",
    "CancelCheck",
    "DEFAULT_BROWSER_MAX_WAIT_SECONDS",
    "BROWSER_MAX_WAIT_FLOOR_SECONDS",
    "BROWSER_MAX_WAIT_CEILING_SECONDS",
    "clamp_browser_max_wait_seconds",
    "resolve_runway_browser_max_wait_seconds",
    "log_runway_wait_config",
    "browser_max_wait_seconds",
    "browser_poll_interval",
    "browser_page_settle_seconds",
    "browser_ratio_duration_post_settle_seconds",
    "browser_ratio_duration_stable_poll_interval",
    "browser_ratio_duration_stable_polls",
    "browser_ratio_duration_stabilize_timeout_seconds",
    "browser_generate_click_wait_seconds",
    "browser_generate_editor_wait_seconds",
    "RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS",
    "capture_runway_prep_debug",
    "browser_prepare_step_timeout_ms",
    "check_cancel",
    "wrap_browser_error",
]
