"""
Shared active-job registry cleanup for phase validation suites.

Validation scripts that register RuntimeJobRegistry entries must clear
validation-scoped jobs on entry and exit so nested subprocess regressions
do not pollute each other via active_jobs.json.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from content_brain.execution.runtime_job_registry import RuntimeJobRegistry
from content_brain.execution.session_store import ExecutionSessionStore

VALIDATION_SESSION_PREFIXES = (
    "exec_10k_val_",
    "exec_10kd_",
    "exec_11ee_",
    "exec_11fd_",
    "exec_11fe_",
)

VALIDATION_JOB_IDS = frozenset(
    {
        "disp_10k_val_running",
        "disp_10k_val_cancel",
        "disp_validate_active",
    }
)


def _matches_validation_session(session_id: str) -> bool:
    cleaned = str(session_id or "").strip()
    if not cleaned:
        return False
    return any(cleaned.startswith(prefix) for prefix in VALIDATION_SESSION_PREFIXES)


def cleanup_validation_registry(
    store: ExecutionSessionStore | None = None,
    *,
    project_root: str | Path = ".",
    extra_session_ids: Iterable[str] | None = None,
    extra_job_ids: Iterable[str] | None = None,
) -> list[str]:
    """Remove validation-scoped active jobs from the registry index."""
    if store is None:
        store = ExecutionSessionStore(project_root)
    registry = RuntimeJobRegistry(store)
    extra_sessions = {str(item).strip() for item in (extra_session_ids or []) if str(item).strip()}
    extra_jobs = {str(item).strip() for item in (extra_job_ids or []) if str(item).strip()}
    removed: list[str] = []
    for record in registry.list_active():
        if record.job_id in extra_jobs or record.job_id in VALIDATION_JOB_IDS:
            registry.remove(record.job_id)
            removed.append(record.job_id)
            continue
        if record.session_id in extra_sessions or _matches_validation_session(record.session_id):
            registry.remove(record.job_id)
            removed.append(record.job_id)
    return removed


__all__ = [
    "VALIDATION_SESSION_PREFIXES",
    "VALIDATION_JOB_IDS",
    "cleanup_validation_registry",
]
