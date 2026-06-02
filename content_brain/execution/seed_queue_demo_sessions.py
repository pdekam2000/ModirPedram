"""
Seed Phase 10H queue demo sessions (QUEUED / DEQUEUED / CANCELLED).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.approval_budget_governance_engine import GovernancePolicy
from content_brain.execution.execution_queue_engine import ExecutionQueueEngine
from content_brain.execution.execution_readiness_gate import ExecutionReadinessGate
from content_brain.execution.seed_governance_demo_sessions import _base_session
from content_brain.execution.seed_readiness_demo_sessions import _pipeline
from content_brain.execution.session_store import ExecutionSessionStore


def _ready_session(exec_id: str, label: str) -> dict[str, Any]:
    session = _base_session(exec_id, label)
    session["priority_band"] = "high"
    session["priority_decision"] = {
        "priority_band": "high",
        "priority_score": 86.0,
        "queue_position": None,
        "decision_source": "queue_demo_seed",
    }
    session["brief_snapshot"]["video_format_plan"]["clip_count"] = 2
    session["story_quality"]["composite_score"] = 86.0
    session["story_quality"]["score"] = 86.0
    session["execution_confidence_score"] = 78.0
    session["provider_selection"]["expected_retry_risk"] = "low"
    return _pipeline(session, policy=GovernancePolicy())


def seed_queue_demo_sessions(project_root: str | Path = ".") -> list[dict[str, Any]]:
    store = ExecutionSessionStore(project_root)
    engine = ExecutionQueueEngine(store)
    results: list[dict[str, Any]] = []

    # 1 — QUEUED
    queued = _ready_session("exec_10h_queued_demo", "queued")
    enqueue_result = engine.enqueue(queued, actor="seed")
    results.append(_summary(enqueue_result.session, "enqueued"))

    # 2 — DEQUEUED (enqueue then targeted dequeue)
    dequeued_base = _ready_session("exec_10h_dequeued_demo", "dequeued")
    engine.enqueue(dequeued_base, actor="seed")
    dequeue_result = engine.dequeue_by_id("exec_10h_dequeued_demo", actor="seed")
    results.append(_summary(dequeue_result.session, "dequeued"))

    # 3 — CANCELLED (enqueue then cancel)
    cancelled_base = _ready_session("exec_10h_cancelled_demo", "cancelled")
    engine.enqueue(cancelled_base, actor="seed")
    cancelled = engine.cancel_by_id("exec_10h_cancelled_demo", reason="demo_cancel", actor="seed")
    results.append(_summary(cancelled, "cancelled"))

    # Rebuild index after all seeds
    engine.rebuild_index()
    return results


def _summary(session: dict[str, Any] | None, label: str) -> dict[str, Any]:
    session = session or {}
    queue_item = session.get("queue_item") or {}
    metadata = (queue_item.get("metadata") or {}) if isinstance(queue_item, dict) else {}
    return {
        "label": label,
        "execution_session_id": session.get("execution_session_id"),
        "state": session.get("state"),
        "queue_state": queue_item.get("queue_state"),
        "queue_position": (queue_item.get("priority") or {}).get("queue_position"),
        "queue_fingerprint": metadata.get("queue_fingerprint"),
        "schema": session.get("session_schema_version"),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    for row in seed_queue_demo_sessions(root):
        print(row)
