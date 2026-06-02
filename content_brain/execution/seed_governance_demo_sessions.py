"""
Seed three Phase 10F governance demo sessions (approved / awaiting / budget blocked).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

from content_brain.execution.approval_budget_governance_engine import (
    ApprovalBudgetGovernanceEngine,
    GovernancePolicy,
)
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.simulation_report_builder import SimulationReportBuilder

TIMESTAMP = "2026-05-29 23:00:00"


def _base_session(exec_id: str, label: str) -> dict[str, Any]:
    return {
        "session_schema_version": "10d_v1",
        "session_uuid": str(uuid.uuid4()),
        "source_session_uuid": None,
        "execution_session_id": exec_id,
        "brief_id": f"brief_10f_{label}",
        "state": "PLANNED",
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "provider": "hailuo",
        "brief_snapshot": {
            "brief_id": f"brief_10f_{label}",
            "video_format_plan": {
                "clip_count": 5,
                "clip_duration_seconds": 6,
                "target_duration_seconds": 30,
                "provider_name": "hailuo",
                "format_type": "multi_clip_hailuo",
            },
            "decision_package": {"decision": "PROCEED", "production_ready": True},
        },
        "story_quality": {
            "composite_score": 86.0,
            "score": 86.0,
            "decision": "PROCEED",
            "warnings": [],
            "critical_failures": [],
        },
        "story_quality_score": 86.0,
        "provider_selection": {
            "primary_provider": "hailuo",
            "alternatives": [],
            "expected_retry_risk": "low",
        },
        "execution_confidence_score": 78.0,
        "execution_confidence": None,
        "approval_state": "pending",
        "approval_request": {
            "status": "pending",
            "estimated_credits": 5.0,
            "estimated_runtime_minutes": 0.5,
            "provider_selection": {"primary_provider": "hailuo"},
            "production_ready": True,
        },
        "approval_decision": None,
        "budget_state": "unknown",
        "budget_decision": {"estimated_credits": 5.0, "budget_allowed": None},
        "simulation_report": None,
        "simulation_report_id": None,
        "metadata": {"production_ready": True, "population_source": "governance_demo_seed"},
        "state_history": [{"at": TIMESTAMP, "state": "PLANNED", "reason": "governance demo seed"}],
    }


def _simulate_and_govern(
    session: dict[str, Any],
    policy: GovernancePolicy | None = None,
) -> dict[str, Any]:
    session = SimulationReportBuilder().enrich_session(session)
    return ApprovalBudgetGovernanceEngine().enrich_session(session, policy=policy)


def seed_demo_sessions(project_root: str | Path = ".") -> list[dict[str, Any]]:
    store = ExecutionSessionStore(project_root)
    sim = SimulationReportBuilder()
    gov = ApprovalBudgetGovernanceEngine()

    # 1 — APPROVED_FOR_EXECUTION
    approved = _base_session("exec_10f_approved_demo", "approved")
    approved["story_quality"]["composite_score"] = 86.0
    approved["story_quality"]["score"] = 86.0
    approved["execution_confidence_score"] = 78.0
    approved["provider_selection"]["expected_retry_risk"] = "low"
    approved = sim.enrich_session(approved)
    approved = gov.enrich_session(approved, policy=GovernancePolicy())

    # 2 — AWAITING_APPROVAL (medium confidence + medium retry)
    awaiting = _base_session("exec_10f_awaiting_demo", "awaiting")
    awaiting["story_quality"]["composite_score"] = 72.0
    awaiting["story_quality"]["score"] = 72.0
    awaiting["execution_confidence_score"] = 62.0
    awaiting["provider_selection"]["expected_retry_risk"] = "medium"
    awaiting = sim.enrich_session(awaiting)
    awaiting = gov.enrich_session(awaiting, policy=GovernancePolicy())

    # 3 — BUDGET_BLOCKED (high effective cost)
    blocked = _base_session("exec_10f_budget_blocked_demo", "blocked")
    blocked["brief_snapshot"]["video_format_plan"]["clip_count"] = 30
    blocked["story_quality"]["composite_score"] = 88.0
    blocked["story_quality"]["score"] = 88.0
    blocked["execution_confidence_score"] = 80.0
    blocked = sim.enrich_session(blocked)
    blocked = gov.enrich_session(blocked, policy=GovernancePolicy(per_run_credit_cap=25.0))

    results = []
    for session in (approved, awaiting, blocked):
        path = store.save_session(session, overwrite=True)
        results.append(
            {
                "path": str(path),
                "execution_session_id": session["execution_session_id"],
                "state": session["state"],
                "approval_status": session["approval_decision"]["status"],
                "budget_status": session["budget_decision"]["budget_status"],
            }
        )
    return results


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    rows = seed_demo_sessions(root)
    for row in rows:
        print(row)
