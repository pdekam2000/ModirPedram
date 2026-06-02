"""
Seed Phase 10I provider runtime demo sessions (dry-run dispatch, no browser).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.approval_budget_governance_engine import GovernancePolicy
from content_brain.execution.execution_queue_engine import ExecutionQueueEngine
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine, RuntimePolicy
from content_brain.execution.seed_governance_demo_sessions import _base_session
from content_brain.execution.seed_readiness_demo_sessions import _pipeline
from content_brain.execution.session_store import ExecutionSessionStore


def _inject_director_shots(session: dict[str, Any], clip_count: int = 2) -> dict[str, Any]:
    brief = session.setdefault("brief_snapshot", {})
    run_context = brief.setdefault("run_context", {})
    story_intelligence = run_context.setdefault("story_intelligence", {})
    story_intelligence["schema_director_shots"] = [
        {
            "clip_number": index,
            "duration_seconds": 6,
            "prompt": f"Demo clip {index} for provider runtime dry-run validation.",
            "camera_shot": "Medium-wide establishing",
            "camera_movement": "Static hold",
            "lighting": "Low-key motivated practical",
            "pacing": "tension",
            "continuity_notes": f"Demo continuity for clip {index}.",
        }
        for index in range(1, clip_count + 1)
    ]
    return session


def _ready_dequeued_session(store: ExecutionSessionStore, exec_id: str, label: str) -> dict[str, Any]:
    session = _base_session(exec_id, label)
    session["priority_band"] = "high"
    session["priority_decision"] = {
        "priority_band": "high",
        "priority_score": 86.0,
        "queue_position": None,
        "decision_source": "runtime_demo_seed",
    }
    session["brief_snapshot"]["video_format_plan"]["clip_count"] = 2
    session = _inject_director_shots(session, clip_count=2)
    session["story_quality"]["composite_score"] = 86.0
    session["story_quality"]["score"] = 86.0
    session["execution_confidence_score"] = 78.0
    session["provider_selection"]["expected_retry_risk"] = "low"
    session = _pipeline(session, policy=GovernancePolicy())
    store.save_session(session, overwrite=True)
    queue = ExecutionQueueEngine(store)
    queue.enqueue_by_id(exec_id, actor="seed")
    result = queue.dequeue_by_id(exec_id, actor="seed")
    return result.session or store.load_session(exec_id)


def seed_runtime_demo_sessions(project_root: str | Path = ".") -> list[dict[str, Any]]:
    store = ExecutionSessionStore(project_root)
    runtime = ProviderRuntimeEngine(store)
    policy = RuntimePolicy(skip_provider_execution=True)
    results: list[dict[str, Any]] = []

    completed_base = _ready_dequeued_session(store, "exec_10i_completed_demo", "completed")
    completed = runtime.dispatch(completed_base, actor="seed", policy=policy).session
    results.append(_summary(completed, "completed_dry_run"))

    failed = _pipeline(_base_session("exec_10i_failed_demo", "failed"), policy=GovernancePolicy())
    store.save_session(failed, overwrite=True)
    fail_result = runtime.dispatch_by_id("exec_10i_failed_demo", actor="seed", policy=policy)
    results.append(_summary(fail_result.session, fail_result.reject_code or "failed"))

    dequeued = _ready_dequeued_session(store, "exec_10i_dequeued_demo", "dequeued")
    results.append(_summary(dequeued, "dequeued_ready"))

    return results


def _summary(session: dict[str, Any] | None, label: str) -> dict[str, Any]:
    session = session or {}
    runtime = session.get("execution_runtime") or {}
    return {
        "label": label,
        "execution_session_id": session.get("execution_session_id"),
        "state": session.get("state"),
        "runtime_state": runtime.get("state"),
        "provider_category": runtime.get("provider_category"),
        "clip_artifacts": len((runtime.get("artifacts_by_category") or {}).get("video_generation") or []),
        "schema": session.get("session_schema_version"),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    for row in seed_runtime_demo_sessions(root):
        print(row)
