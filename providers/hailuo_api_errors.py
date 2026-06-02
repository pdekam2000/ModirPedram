"""
Phase 11F-b — structured Hailuo browser provider errors (taxonomy-integrated).
"""

from __future__ import annotations

from typing import Any

from providers.hailuo_error_classifier import classify_hailuo_failure

PROVIDER_VERSION = "11f_c_v1"


class HailuoProviderError(RuntimeError):
    """Hailuo browser error with failure taxonomy code."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ):
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause
        taxonomy = classify_hailuo_failure(message, http_status=http_status, context=details)
        self.code = str(code or taxonomy["code"])
        self.http_status = http_status
        self.details = dict(details or {})
        self.taxonomy = taxonomy

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "code": self.code,
            "http_status": self.http_status,
            "details": self.details,
            "taxonomy": self.taxonomy,
            "provider_version": PROVIDER_VERSION,
        }


class HailuoCancelledError(HailuoProviderError):
    """Cooperative cancellation — preserves partial artifacts."""

    def __init__(
        self,
        message: str = "Hailuo browser generation cancelled",
        *,
        partial_paths: list[str] | None = None,
        clip_results: list[dict[str, Any]] | None = None,
        phase: str = "unknown",
        details: dict[str, Any] | None = None,
    ):
        merged = dict(details or {})
        merged["cancelled"] = True
        merged["phase"] = phase
        merged["partial_paths"] = list(partial_paths or [])
        merged["artifact_preserved"] = True
        if clip_results:
            merged["clip_results"] = list(clip_results)
        super().__init__(message, code="OPERATIONS_CANCELLED", details=merged)
        self.partial_paths = list(partial_paths or [])
        self.clip_results = list(clip_results or [])
        self.phase = phase
        self.cancelled = True


__all__ = [
    "PROVIDER_VERSION",
    "HailuoProviderError",
    "HailuoCancelledError",
]
