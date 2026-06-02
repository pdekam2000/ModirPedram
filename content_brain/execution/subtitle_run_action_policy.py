"""
Phase 11I-8 — eligibility policy for POST /subtitle/run.

Pure policy — never generates cues, writes files, or mutates sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import (
    STATUS_COMPLETED,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    SUBTITLE_SUPPORTED_FORMATS,
)
from content_brain.execution.operations_cancel import is_cancellation_requested
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VOICE,
)
from content_brain.execution.subtitle_format_writer import (
    DEFAULT_FILENAMES,
    MANIFEST_FILENAME,
)
from content_brain.execution.subtitle_preflight_runtime_slot import (
    SOURCE_UNAVAILABLE,
    resolve_subtitle_source_type,
)

ACTION_RUN = "run_subtitle_generation"

CODE_SESSION_ARCHIVED = "SESSION_ARCHIVED"
CODE_SUBTITLE_SLOT_MISSING = "SUBTITLE_SLOT_MISSING"
CODE_SOURCE_NOT_READY = "SOURCE_NOT_READY"
CODE_SUBTITLE_RUN_IN_PROGRESS = "SUBTITLE_RUN_IN_PROGRESS"
CODE_OPERATIONS_CANCELLED = "OPERATIONS_CANCELLED"
CODE_OVERWRITE_REQUIRED = "OVERWRITE_REQUIRED"
CODE_TIMING_STRATEGY_UNAVAILABLE = "TIMING_STRATEGY_UNAVAILABLE"
CODE_UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
CODE_PRECONDITION_FAILED = "SUBTITLE_RUN_PRECONDITION_FAILED"

RUNNABLE_STATUSES = frozenset({"pending", "failed", "cancelled", "planned", "completed"})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _session_archived(session: dict[str, Any]) -> bool:
    return bool(_dict(session.get("operations_control")).get("archived"))


def _subtitle_slot(session: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict(session.get("execution_runtime"))
    category_runtime = _dict(runtime.get("category_runtime"))
    return dict(
        _dict(
            category_runtime.get(CATEGORY_SUBTITLE_GENERATION)
            or category_runtime.get("subtitles")
        )
    )


def _voice_slot(session: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict(session.get("execution_runtime"))
    category_runtime = _dict(runtime.get("category_runtime"))
    return dict(_dict(category_runtime.get(CATEGORY_VOICE)))


def _artifact_dir_exists_with_files(session_id: str, project_root: str | Path | None) -> bool:
    from content_brain.execution.category_runtime_compat import SUBTITLE_ARTIFACT_CATEGORY
    from content_brain.execution.session_store import ExecutionSessionStore

    root = Path(project_root or ".").resolve()
    store = ExecutionSessionStore(root)
    artifact_dir = store.artifact_dir(session_id, SUBTITLE_ARTIFACT_CATEGORY)
    if not artifact_dir.is_dir():
        return False
    for name in (*DEFAULT_FILENAMES.values(), MANIFEST_FILENAME):
        if (artifact_dir / name).is_file():
            return True
    return False


def _voice_has_timing(session: dict[str, Any], voice_slot: dict[str, Any]) -> bool:
    return resolve_subtitle_source_type(session, voice_slot) == "narration_with_timing"


@dataclass
class SubtitleRunPolicyResult:
    allowed: bool
    action: str = ACTION_RUN
    reject_reasons: list[str] = field(default_factory=list)
    code: str | None = None
    message: str = ""
    guard_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "action": self.action,
            "reject_reasons": list(self.reject_reasons),
            "message": self.message,
        }
        if self.code:
            payload["code"] = self.code
        if self.guard_result is not None:
            payload["guard_result"] = dict(self.guard_result)
        return payload


def evaluate_subtitle_run_request(
    session: dict[str, Any],
    subtitle_slot: dict[str, Any],
    *,
    session_id: str,
    formats: list[str] | None = None,
    timing_strategy: str = "auto",
    overwrite: bool = False,
    force_retry: bool = False,
    project_root: str | Path | None = None,
) -> SubtitleRunPolicyResult:
    """Evaluate whether a subtitle run is allowed for the session."""
    checks: list[dict[str, Any]] = []
    voice_slot = _voice_slot(session)

    if _session_archived(session):
        checks.append({"check": "session_archived", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_SESSION_ARCHIVED,
            message="Session is archived.",
            reject_reasons=["Session is archived."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "session_archived", "passed": True})

    if not subtitle_slot:
        checks.append({"check": "subtitle_slot", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_SUBTITLE_SLOT_MISSING,
            message="Subtitle runtime slot is missing.",
            reject_reasons=["Subtitle runtime slot is missing."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "subtitle_slot", "passed": True})

    if is_cancellation_requested(session):
        checks.append({"check": "operations_cancelled", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_OPERATIONS_CANCELLED,
            message="Operations cancel requested.",
            reject_reasons=["Operations cancel requested."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "operations_cancelled", "passed": True})

    status = str(subtitle_slot.get("status") or "").lower()
    if status == STATUS_RUNNING:
        checks.append({"check": "no_active_run", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_SUBTITLE_RUN_IN_PROGRESS,
            message="Subtitle run already in progress.",
            reject_reasons=["Subtitle run already in progress."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "no_active_run", "passed": True})

    source_type = resolve_subtitle_source_type(session, voice_slot)
    source_ready = bool(subtitle_slot.get("source_ready")) or source_type != SOURCE_UNAVAILABLE
    if not source_ready or source_type == SOURCE_UNAVAILABLE:
        checks.append({"check": "source_ready", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_SOURCE_NOT_READY,
            message="No subtitle source available (narration or voice timing).",
            reject_reasons=["No subtitle source available (narration or voice timing)."],
            guard_result={"checks": checks, "source_type": source_type},
        )
    checks.append({"check": "source_ready", "passed": True, "source_type": source_type})

    requested_timing = str(timing_strategy or "auto").lower()
    if requested_timing == "audio_duration" and not _voice_has_timing(session, voice_slot):
        checks.append({"check": "timing_strategy", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_TIMING_STRATEGY_UNAVAILABLE,
            message="audio_duration timing requires completed voice manifest with durations.",
            reject_reasons=["audio_duration timing requires completed voice manifest with durations."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "timing_strategy", "passed": True})

    fmt_list = [str(fmt).lower().strip() for fmt in (formats or list(SUBTITLE_SUPPORTED_FORMATS))]
    unsupported = [fmt for fmt in fmt_list if fmt not in SUBTITLE_SUPPORTED_FORMATS]
    if unsupported:
        checks.append({"check": "supported_formats", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_UNSUPPORTED_FORMAT,
            message=f"Unsupported format(s): {', '.join(unsupported)}",
            reject_reasons=[f"Unsupported format(s): {', '.join(unsupported)}"],
            guard_result={"checks": checks},
        )
    checks.append({"check": "supported_formats", "passed": True})

    if status == STATUS_SKIPPED:
        checks.append({"check": "runnable_status", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_SOURCE_NOT_READY,
            message="Subtitle slot is skipped — no source available.",
            reject_reasons=["Subtitle slot is skipped — no source available."],
            guard_result={"checks": checks},
        )

    if status not in RUNNABLE_STATUSES:
        checks.append({"check": "runnable_status", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_PRECONDITION_FAILED,
            message=f"Subtitle slot status '{status}' is not runnable.",
            reject_reasons=[f"Subtitle slot status '{status}' is not runnable."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "runnable_status", "passed": True})

    if (
        status == STATUS_COMPLETED
        and not overwrite
        and not force_retry
        and _artifact_dir_exists_with_files(session_id, project_root)
    ):
        checks.append({"check": "overwrite", "passed": False})
        return SubtitleRunPolicyResult(
            allowed=False,
            code=CODE_OVERWRITE_REQUIRED,
            message="Subtitle artifacts already exist — set overwrite=true to rewrite.",
            reject_reasons=["Subtitle artifacts already exist — set overwrite=true to rewrite."],
            guard_result={"checks": checks},
        )
    checks.append({"check": "overwrite", "passed": True})

    return SubtitleRunPolicyResult(
        allowed=True,
        message="Subtitle run allowed.",
        guard_result={"checks": checks, "source_type": source_type},
    )


__all__ = [
    "ACTION_RUN",
    "CODE_SESSION_ARCHIVED",
    "CODE_SUBTITLE_SLOT_MISSING",
    "CODE_SOURCE_NOT_READY",
    "CODE_SUBTITLE_RUN_IN_PROGRESS",
    "CODE_OPERATIONS_CANCELLED",
    "CODE_OVERWRITE_REQUIRED",
    "CODE_TIMING_STRATEGY_UNAVAILABLE",
    "CODE_UNSUPPORTED_FORMAT",
    "CODE_PRECONDITION_FAILED",
    "RUNNABLE_STATUSES",
    "SubtitleRunPolicyResult",
    "evaluate_subtitle_run_request",
]
