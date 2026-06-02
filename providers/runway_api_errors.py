"""
Phase 11E-b — structured Runway API provider errors (taxonomy-integrated).
"""

from __future__ import annotations

from typing import Any

from providers.runway_error_classifier import classify_runway_failure

PROVIDER_VERSION = "11e_b_v1"


class RunwayProviderError(RuntimeError):
    """Runway API error with failure taxonomy code."""

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
        taxonomy = classify_runway_failure(message, http_status=http_status, context=details)
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


class RunwayCancelledError(RunwayProviderError):
    """Cooperative cancellation — not a failure; preserves partial artifacts."""

    def __init__(
        self,
        message: str = "Runway API generation cancelled",
        *,
        partial_paths: list[str] | None = None,
        phase: str = "unknown",
        details: dict[str, Any] | None = None,
    ):
        merged = dict(details or {})
        merged["cancelled"] = True
        merged["phase"] = phase
        merged["partial_paths"] = list(partial_paths or [])
        super().__init__(message, code="OPERATIONS_CANCELLED", details=merged)
        self.partial_paths = list(partial_paths or [])
        self.phase = phase
        self.cancelled = True


def raise_from_http(message: str, *, http_status: int, details: dict[str, Any] | None = None) -> None:
    raise RunwayProviderError(message, http_status=http_status, details=details)


__all__ = [
    "PROVIDER_VERSION",
    "RunwayProviderError",
    "RunwayCancelledError",
    "raise_from_http",
]
