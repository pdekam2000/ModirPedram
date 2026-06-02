"""
Seed three Phase 10G readiness demo sessions (READY / READY_WITH_WARNINGS / NOT_READY).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.approval_budget_governance_engine import (
    ApprovalBudgetGovernanceEngine,
    GovernancePolicy,
)
from content_brain.execution.execution_readiness_gate import ExecutionReadinessGate
from content_brain.execution.seed_governance_demo_sessions import _base_session
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.simulation_report_builder import SimulationReportBuilder

TIMESTAMP = "2026-05-29 23:30:00"


def _pipeline(session: dict[str, Any], policy: GovernancePolicy | None = None) -> dict[str, Any]:
    session = SimulationReportBuilder().enrich_session(session)
    session = ApprovalBudgetGovernanceEngine().enrich_session(session, policy=policy)
    return ExecutionReadinessGate().enrich_session(session)


def seed_readiness_demo_sessions(project_root: str | Path = ".") -> list[dict[str, Any]]:
    store = ExecutionSessionStore(project_root)
    results: list[dict[str, Any]] = []

    # 1 — READY (low stitch complexity, clean path)
    ready = _base_session("exec_10g_ready_demo", "ready")
    ready["brief_snapshot"]["video_format_plan"]["clip_count"] = 2
    ready["story_quality"]["composite_score"] = 86.0
    ready["story_quality"]["score"] = 86.0
    ready["execution_confidence_score"] = 78.0
    ready["provider_selection"]["expected_retry_risk"] = "low"
    ready = _pipeline(ready)
    store.save_session(ready, overwrite=True)
    results.append(_summary(ready))

    # 2 — READY_WITH_WARNINGS (high stitch complexity warning, still governed)
    warnings = _base_session("exec_10g_ready_warnings_demo", "ready_warnings")
    warnings["story_quality"]["composite_score"] = 86.0
    warnings["story_quality"]["score"] = 86.0
    warnings["execution_confidence_score"] = 78.0
    warnings["provider_selection"]["expected_retry_risk"] = "low"
    warnings = _pipeline(warnings)
    store.save_session(warnings, overwrite=True)
    results.append(_summary(warnings))

    # 3 — NOT_READY (governance rejects / awaiting)
    not_ready = _base_session("exec_10g_not_ready_demo", "not_ready")
    not_ready["story_quality"]["composite_score"] = 62.0
    not_ready["story_quality"]["score"] = 62.0
    not_ready["story_quality"]["decision"] = "PROCEED"
    not_ready["execution_confidence_score"] = 55.0
    not_ready["provider_selection"]["expected_retry_risk"] = "high"
    not_ready = SimulationReportBuilder().enrich_session(not_ready)
    not_ready = ApprovalBudgetGovernanceEngine().enrich_session(not_ready)
    not_ready = ExecutionReadinessGate().enrich_session(not_ready)
    store.save_session(not_ready, overwrite=True)
    results.append(_summary(not_ready))

    return results


def _summary(session: dict[str, Any]) -> dict[str, Any]:
    readiness = session.get("execution_readiness") or {}
    return {
        "execution_session_id": session["execution_session_id"],
        "state": session["state"],
        "governance_state_before_readiness": "GOVERNED or blocked",
        "readiness_decision": readiness.get("decision"),
        "readiness_score": readiness.get("readiness_score"),
        "failures": readiness.get("readiness_failures"),
        "warnings": readiness.get("readiness_warnings"),
        "schema": session.get("session_schema_version"),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    for row in seed_readiness_demo_sessions(root):
        print(row)
