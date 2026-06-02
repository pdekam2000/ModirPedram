"""
Phase 11E-e — runtime cancel_check wiring helpers.

Passes cooperative cancel signals from ProviderRuntimeEngine into providers
that opt in via a cancel_check parameter (Runway API/browser).
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from content_brain.execution.operations_cancel import is_cancellation_requested
from content_brain.execution.session_store import ExecutionSessionStore

CancelCheck = Callable[[], bool]

RUNWAY_CANCEL_AWARE_PROVIDERS = frozenset({"runway", "runway_api", "runway_browser"})
HAILUO_CANCEL_AWARE_PROVIDERS = frozenset({"hailuo", "hailuo_browser"})
CANCEL_AWARE_PROVIDERS = RUNWAY_CANCEL_AWARE_PROVIDERS | HAILUO_CANCEL_AWARE_PROVIDERS


def supports_cancel_check(callable_obj: Any) -> bool:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return False
    return "cancel_check" in signature.parameters


def call_with_optional_cancel_check(
    fn: Callable[..., Any],
    /,
    *args: Any,
    cancel_check: CancelCheck | None = None,
    **kwargs: Any,
) -> Any:
    if cancel_check is not None and supports_cancel_check(fn):
        kwargs = {**kwargs, "cancel_check": cancel_check}
    return fn(*args, **kwargs)


def build_runtime_cancel_check(store: ExecutionSessionStore, session_id: str) -> CancelCheck:
    def _check() -> bool:
        try:
            session = store.load_session(session_id)
        except FileNotFoundError:
            return False
        return is_cancellation_requested(session)

    return _check


def provider_accepts_runtime_cancel(provider: str) -> bool:
    normalized = str(provider or "").strip().lower()
    if normalized == "runway_api":
        normalized = "runway"
    if normalized == "hailuo":
        normalized = "hailuo_browser"
    return normalized in CANCEL_AWARE_PROVIDERS


def extract_cancel_partial_artifacts(exc: BaseException) -> tuple[list[str], list[dict[str, Any]]]:
    details: dict[str, Any] = {}
    partial_paths: list[str] = []
    clip_results: list[dict[str, Any]] = []

    if hasattr(exc, "details") and isinstance(getattr(exc, "details"), dict):
        details = dict(getattr(exc, "details"))
    if hasattr(exc, "partial_paths"):
        partial_paths = list(getattr(exc, "partial_paths") or [])

    if not partial_paths:
        raw_paths = details.get("partial_paths")
        if isinstance(raw_paths, list):
            partial_paths = [str(item) for item in raw_paths if item]

    raw_results = details.get("clip_results")
    if isinstance(raw_results, list):
        clip_results = [dict(item) for item in raw_results if isinstance(item, dict)]

    return partial_paths, clip_results


def is_provider_cooperative_cancel(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    if code == "OPERATIONS_CANCELLED":
        return True
    if exc.__class__.__name__ == "RunwayCancelledError":
        return True
    if exc.__class__.__name__ == "HailuoCancelledError":
        return True
    return bool(getattr(exc, "cancelled", False))


__all__ = [
    "CancelCheck",
    "RUNWAY_CANCEL_AWARE_PROVIDERS",
    "HAILUO_CANCEL_AWARE_PROVIDERS",
    "CANCEL_AWARE_PROVIDERS",
    "supports_cancel_check",
    "call_with_optional_cancel_check",
    "build_runtime_cancel_check",
    "provider_accepts_runtime_cancel",
    "extract_cancel_partial_artifacts",
    "is_provider_cooperative_cancel",
]
