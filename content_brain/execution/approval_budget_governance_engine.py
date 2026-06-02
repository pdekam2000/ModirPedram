"""
Phase 10F — approval and budget governance for execution sessions.

No provider execution, no queue, no browser automation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

ENGINE_NAME = "ApprovalBudgetGovernanceEngine"
ENGINE_VERSION = "10f_v1"
POLICY_VERSION = "10f_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

APPROVAL_APPROVED = "APPROVED_FOR_EXECUTION"
APPROVAL_AWAITING = "AWAITING_APPROVAL"
APPROVAL_REJECTED = "REJECTED"

BUDGET_WITHIN = "WITHIN_LIMIT"
BUDGET_WARNING = "WARNING"
BUDGET_BLOCKED = "BUDGET_BLOCKED"

RETRY_MULTIPLIERS = {"low": 1.0, "medium": 1.25, "high": 1.5}


@dataclass
class GovernancePolicy:
    policy_id: str = "default_local"
    policy_version: str = POLICY_VERSION
    story_quality_min: float = 70.0
    story_quality_auto_approve_min: float = 75.0
    execution_confidence_min: float = 60.0
    execution_confidence_auto_approve_min: float = 70.0
    per_run_credit_cap: float = 25.0
    monthly_credit_limit: float = 1000.0
    monthly_credits_spent: float = 0.0
    auto_approve_under_credits: float = 10.0
    require_human_over_credits: float = 15.0
    retry_risk_auto_approve: str = "low"
    budget_scope: str = "local"

    def approval_snapshot(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "story_quality_min": self.story_quality_min,
            "story_quality_auto_approve_min": self.story_quality_auto_approve_min,
            "execution_confidence_min": self.execution_confidence_min,
            "execution_confidence_auto_approve_min": self.execution_confidence_auto_approve_min,
            "retry_risk_auto_approve": self.retry_risk_auto_approve,
            "require_human_over_credits": self.require_human_over_credits,
        }

    def budget_snapshot(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "per_run_credit_cap": self.per_run_credit_cap,
            "monthly_credit_limit": self.monthly_credit_limit,
            "auto_approve_under_credits": self.auto_approve_under_credits,
            "retry_risk_budget_multiplier_high": RETRY_MULTIPLIERS["high"],
            "retry_risk_budget_multiplier_medium": RETRY_MULTIPLIERS["medium"],
            "budget_scope": self.budget_scope,
        }


@dataclass
class GovernanceResult:
    approval_decision: dict[str, Any]
    budget_decision: dict[str, Any]
    approval_state: str
    budget_state: str
    recommended_state: str
    warnings: list[str] = field(default_factory=list)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _first_number(*values: Any, default: float | None = None) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _retry_risk(session: dict[str, Any], simulation: dict[str, Any]) -> str:
    provider = _dict(session.get("provider_selection"))
    risk = str(
        simulation.get("estimated_retry_risk")
        or provider.get("expected_retry_risk")
        or "low"
    ).lower()
    if risk in RETRY_MULTIPLIERS:
        return risk
    if "high" in risk:
        return "high"
    if "medium" in risk:
        return "medium"
    return "low"


def _execution_confidence(session: dict[str, Any], simulation: dict[str, Any]) -> float | None:
    confidence_obj = _dict(session.get("execution_confidence"))
    return _first_number(
        confidence_obj.get("execution_confidence_score"),
        session.get("execution_confidence_score"),
        simulation.get("execution_confidence_estimate"),
    )


def _estimated_credits(session: dict[str, Any], simulation: dict[str, Any]) -> float:
    cost_estimate = _dict(simulation.get("cost_estimate"))
    budget = _dict(session.get("budget_decision"))
    approval = _dict(session.get("approval_request"))
    return (
        _first_number(
            simulation.get("estimated_credits"),
            cost_estimate.get("estimated_total_credits"),
            budget.get("estimated_credits"),
            approval.get("estimated_credits"),
            default=0.0,
        )
        or 0.0
    )


class ApprovalBudgetGovernanceEngine:
    """Evaluate session inputs and produce approval + budget decisions."""

    def evaluate(
        self,
        session: dict[str, Any],
        policy: GovernancePolicy | None = None,
    ) -> GovernanceResult:
        policy = policy or GovernancePolicy()
        simulation = _dict(session.get("simulation_report"))
        story_quality = _dict(session.get("story_quality"))
        provider_selection = _dict(session.get("provider_selection"))

        warnings: list[str] = []
        reasons: list[str] = []
        blockers: list[str] = []

        if not simulation:
            warnings.append("Simulation report missing — governance deferred.")
            approval = self._build_approval_decision(
                status=APPROVAL_AWAITING,
                policy=policy,
                reasons=["Simulation report required before governance."],
                blockers=["missing_simulation_report"],
                inputs={},
            )
            budget = self._build_budget_decision(
                status=BUDGET_WARNING,
                policy=policy,
                allowed=None,
                estimated_credits=0.0,
                effective_credits=0.0,
                warnings=["Simulation report missing."],
                block_reason=None,
            )
            return GovernanceResult(
                approval_decision=approval,
                budget_decision=budget,
                approval_state="pending",
                budget_state="unknown",
                recommended_state="SIMULATED",
                warnings=warnings,
            )

        story_score = _first_number(
            story_quality.get("composite_score"),
            story_quality.get("score"),
            session.get("story_quality_score"),
            default=0.0,
        ) or 0.0
        story_decision = str(story_quality.get("decision") or "").upper()
        confidence = _execution_confidence(session, simulation) or 0.0
        retry = _retry_risk(session, simulation)
        estimated = _estimated_credits(session, simulation)
        effective = round(estimated * RETRY_MULTIPLIERS.get(retry, 1.0), 2)
        production_ready = bool(_dict(session.get("metadata")).get("production_ready", True))

        inputs_summary = {
            "story_quality_score": story_score,
            "execution_confidence": confidence,
            "estimated_credits": estimated,
            "effective_credits": effective,
            "retry_risk": retry,
            "simulation_report_uuid": simulation.get("report_uuid"),
        }

        # --- Budget decision ---
        budget_status = BUDGET_WITHIN
        budget_allowed = True
        budget_warnings: list[str] = []
        budget_block_reason: str | None = None
        remaining = max(0.0, policy.monthly_credit_limit - policy.monthly_credits_spent - effective)

        if effective > policy.per_run_credit_cap:
            budget_status = BUDGET_BLOCKED
            budget_allowed = False
            budget_block_reason = (
                f"Effective cost {effective} exceeds per-run cap {policy.per_run_credit_cap}."
            )
            blockers.append(budget_block_reason)
        elif policy.monthly_credits_spent + effective > policy.monthly_credit_limit:
            budget_status = BUDGET_BLOCKED
            budget_allowed = False
            budget_block_reason = "Monthly credit limit would be exceeded."
            blockers.append(budget_block_reason)
        elif effective > policy.auto_approve_under_credits:
            budget_status = BUDGET_WARNING
            budget_warnings.append(
                f"Estimated effective cost {effective} exceeds auto-approve threshold "
                f"{policy.auto_approve_under_credits}."
            )

        budget_decision = self._build_budget_decision(
            status=budget_status,
            policy=policy,
            allowed=budget_allowed,
            estimated_credits=estimated,
            effective_credits=effective,
            warnings=budget_warnings,
            block_reason=budget_block_reason,
            remaining_credits=remaining,
        )

        # --- Approval decision ---
        approval_status = APPROVAL_APPROVED

        if not production_ready or story_decision in {"REJECT", "REGENERATE"}:
            approval_status = APPROVAL_REJECTED
            blockers.append(f"Content gate: {story_decision or 'not production ready'}")
        elif story_score < policy.story_quality_min:
            approval_status = APPROVAL_REJECTED
            blockers.append(
                f"Story quality {story_score} below minimum {policy.story_quality_min}."
            )
        elif confidence < policy.execution_confidence_min:
            approval_status = APPROVAL_REJECTED
            blockers.append(
                f"Execution confidence {confidence} below minimum {policy.execution_confidence_min}."
            )
        elif retry == "high":
            approval_status = APPROVAL_REJECTED
            blockers.append("Retry risk is high.")
        elif (
            story_score < policy.story_quality_auto_approve_min
            or confidence < policy.execution_confidence_auto_approve_min
            or retry != policy.retry_risk_auto_approve
            or estimated > policy.require_human_over_credits
            or budget_status == BUDGET_WARNING
        ):
            approval_status = APPROVAL_AWAITING
            if story_score < policy.story_quality_auto_approve_min:
                reasons.append("Story quality in human-review band.")
            if confidence < policy.execution_confidence_auto_approve_min:
                reasons.append("Execution confidence in human-review band.")
            if retry != policy.retry_risk_auto_approve:
                reasons.append(f"Retry risk '{retry}' requires review.")
            if estimated > policy.require_human_over_credits:
                reasons.append("Estimated cost requires human review.")
            if budget_status == BUDGET_WARNING:
                reasons.append("Budget warning active.")
        else:
            reasons.append("All auto-approval thresholds met.")

        approval_decision = self._build_approval_decision(
            status=approval_status,
            policy=policy,
            reasons=reasons,
            blockers=blockers,
            inputs=inputs_summary,
        )

        # --- Session state ---
        if budget_status == BUDGET_BLOCKED:
            recommended_state = "BUDGET_BLOCKED"
        elif approval_status == APPROVAL_REJECTED:
            recommended_state = "REJECTED"
        elif approval_status == APPROVAL_AWAITING:
            recommended_state = "AWAITING_APPROVAL"
        elif approval_status == APPROVAL_APPROVED and budget_allowed:
            recommended_state = "GOVERNED"
        else:
            recommended_state = "AWAITING_APPROVAL"

        approval_state = {
            APPROVAL_APPROVED: "approved",
            APPROVAL_AWAITING: "pending",
            APPROVAL_REJECTED: "rejected",
        }[approval_status]

        budget_state = {
            BUDGET_WITHIN: "allowed",
            BUDGET_WARNING: "warning",
            BUDGET_BLOCKED: "blocked",
        }[budget_status]

        return GovernanceResult(
            approval_decision=approval_decision,
            budget_decision=budget_decision,
            approval_state=approval_state,
            budget_state=budget_state,
            recommended_state=recommended_state,
            warnings=warnings,
        )

    def enrich_session(
        self,
        session: dict[str, Any],
        policy: GovernancePolicy | None = None,
    ) -> dict[str, Any]:
        result = self.evaluate(session, policy=policy)
        session = dict(session)
        timestamp = _now()

        session["approval_decision"] = result.approval_decision
        session["budget_decision"] = result.budget_decision
        session["approval_state"] = result.approval_state
        session["budget_state"] = result.budget_state
        session["state"] = result.recommended_state
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10f_v1"

        metadata = _dict(session.get("metadata"))
        metadata["governance_version"] = ENGINE_VERSION
        metadata["governance_evaluated_at"] = timestamp
        session["metadata"] = metadata

        history = list(session.get("state_history") or [])
        history.append(
            {
                "at": timestamp,
                "state": result.recommended_state,
                "reason": (
                    f"governance: approval={result.approval_decision.get('status')}, "
                    f"budget={result.budget_decision.get('budget_status')}"
                ),
            }
        )
        session["state_history"] = history
        return session

    def _build_approval_decision(
        self,
        *,
        status: str,
        policy: GovernancePolicy,
        reasons: list[str],
        blockers: list[str],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "decision_id": f"appr_{uuid.uuid4().hex[:12]}",
            "status": status,
            "action": status.lower(),
            "reasons": reasons,
            "blockers": blockers,
            "requires_human_approval": status == APPROVAL_AWAITING,
            "evaluated_at": _now(),
            "evaluated_by": {
                "engine": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
            },
            "policy_snapshot": policy.approval_snapshot(),
            "inputs_summary": inputs,
            "override": None,
        }

    def _build_budget_decision(
        self,
        *,
        status: str,
        policy: GovernancePolicy,
        allowed: bool | None,
        estimated_credits: float,
        effective_credits: float,
        warnings: list[str],
        block_reason: str | None,
        remaining_credits: float | None = None,
    ) -> dict[str, Any]:
        return {
            "decision_id": f"bdgt_{uuid.uuid4().hex[:12]}",
            "budget_status": status,
            "budget_allowed": allowed,
            "budget_state": status,
            "estimated_credits": estimated_credits,
            "effective_credits": effective_credits,
            "budget_warnings": warnings,
            "budget_block_reason": block_reason,
            "remaining_budget_after_run": (
                {"credits": remaining_credits, "scope": policy.budget_scope}
                if remaining_credits is not None
                else None
            ),
            "evaluated_at": _now(),
            "evaluated_by": {
                "engine": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
            },
            "policy_snapshot": policy.budget_snapshot(),
            "policy_source": policy.policy_id,
            "override": None,
        }


__all__ = [
    "ApprovalBudgetGovernanceEngine",
    "GovernancePolicy",
    "GovernanceResult",
    "APPROVAL_APPROVED",
    "APPROVAL_AWAITING",
    "APPROVAL_REJECTED",
    "BUDGET_WITHIN",
    "BUDGET_WARNING",
    "BUDGET_BLOCKED",
]
