"""
Phase 10J-a — Provider Operations policy (extends 10I RuntimePolicy fields).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.failure_taxonomy import DEFAULT_RETRIABLE_CODES
from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.provider_runtime_engine import RuntimePolicy

OPERATIONS_POLICY_VERSION = "10j_v1"


@dataclass
class OperationsPolicy:
    """10J operations policy — composes 10I runtime dispatch rules with worker/preflight settings."""

    policy_id: str = "default_local"
    operations_policy_version: str = OPERATIONS_POLICY_VERSION
    provider_category: str = CATEGORY_VIDEO
    require_queue_fingerprint: bool = True
    require_readiness: bool = True
    skip_provider_execution: bool = False
    max_clips_cap: int = 30
    max_dispatch_attempts: int = 3
    retriable_failure_codes: frozenset[str] = field(default_factory=lambda: DEFAULT_RETRIABLE_CODES)
    max_concurrent_browser_jobs: int = 1
    heartbeat_interval_seconds: int = 30
    stale_after_seconds: int = 120
    min_artifact_bytes: int = 100_000
    allow_partial_artifacts: bool = False
    auto_requeue_on_retriable_failure: bool = False
    worker_log_capture: bool = True
    free_credit_first: bool = True
    operator_paid_approval: bool = False

    def to_runtime_policy(self) -> RuntimePolicy:
        """Map to 10I RuntimePolicy for unchanged dispatch paths."""
        return RuntimePolicy(
            policy_id=self.policy_id,
            policy_version=OPERATIONS_POLICY_VERSION,
            provider_category=self.provider_category,
            require_queue_fingerprint=self.require_queue_fingerprint,
            require_readiness=self.require_readiness,
            skip_provider_execution=self.skip_provider_execution,
            max_clips_cap=self.max_clips_cap,
        )

    def is_retriable_code(self, code: str | None) -> bool:
        key = str(code or "").strip().upper()
        return key in self.retriable_failure_codes

    def snapshot(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "operations_policy_version": self.operations_policy_version,
            "provider_category": self.provider_category,
            "require_queue_fingerprint": self.require_queue_fingerprint,
            "require_readiness": self.require_readiness,
            "skip_provider_execution": self.skip_provider_execution,
            "max_clips_cap": self.max_clips_cap,
            "max_dispatch_attempts": self.max_dispatch_attempts,
            "retriable_failure_codes": sorted(self.retriable_failure_codes),
            "max_concurrent_browser_jobs": self.max_concurrent_browser_jobs,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "stale_after_seconds": self.stale_after_seconds,
            "min_artifact_bytes": self.min_artifact_bytes,
            "allow_partial_artifacts": self.allow_partial_artifacts,
            "auto_requeue_on_retriable_failure": self.auto_requeue_on_retriable_failure,
            "worker_log_capture": self.worker_log_capture,
            "free_credit_first": self.free_credit_first,
            "operator_paid_approval": self.operator_paid_approval,
        }


__all__ = ["OperationsPolicy", "OPERATIONS_POLICY_VERSION"]
