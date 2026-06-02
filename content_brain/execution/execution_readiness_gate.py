"""
Phase 10G — execution readiness gate between governance and future queue runtime.

No queue execution, no provider execution, no browser automation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

from content_brain.execution.session_fingerprint import compute_simulation_fingerprint

ENGINE_NAME = "ExecutionReadinessGate"
ENGINE_VERSION = "10g_v1"
POLICY_VERSION = "10g_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

READINESS_READY = "READY"
READINESS_WARNINGS = "READY_WITH_WARNINGS"
READINESS_NOT_READY = "NOT_READY"

KNOWN_PROVIDERS = {"hailuo", "hailuo_browser", "runway", "runway_browser", "generic"}

REQUIRED_ROOT_FIELDS = [
    "session_uuid",
    "execution_session_id",
    "brief_id",
    "brief_snapshot",
    "simulation_report",
    "approval_decision",
    "budget_decision",
    "story_quality",
    "provider_selection",
    "provider",
]

CHECK_WEIGHTS = {
    "simulation_exists": 0.15,
    "governance_exists": 0.25,
    "provider_selection_exists": 0.10,
    "story_quality_exists": 0.15,
    "required_fields_completeness": 0.10,
    "fingerprint_consistency": 0.15,
    "valid_session_state": 0.10,
}

GOVERNED_STATES = {"GOVERNED", "APPROVED_FOR_EXECUTION"}


@dataclass
class ReadinessPolicy:
    policy_version: str = POLICY_VERSION
    min_readiness_score_for_ready: float = 75.0


@dataclass
class CheckResult:
    name: str
    passed: bool
    score: float
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if isinstance(value, dict) and not value:
        return False
    return True


class ExecutionReadinessGate:
    """Evaluate whether a governed session may enter the future execution queue."""

    def evaluate(
        self,
        session: dict[str, Any],
        policy: ReadinessPolicy | None = None,
    ) -> dict[str, Any]:
        policy = policy or ReadinessPolicy()
        checks = [
            self._check_simulation_exists(session),
            self._check_governance_exists(session),
            self._check_provider_selection_exists(session),
            self._check_story_quality_exists(session),
            self._check_required_fields(session),
            self._check_fingerprint_consistency(session),
            self._check_valid_session_state(session),
        ]

        failures: list[str] = []
        warnings: list[str] = []
        for check in checks:
            failures.extend(check.failures)
            warnings.extend(check.warnings)

        readiness_score = round(
            sum(check.score * CHECK_WEIGHTS[check.name] for check in checks),
            1,
        )

        if failures:
            decision = READINESS_NOT_READY
            readiness_score = min(readiness_score, 49.0)
        elif warnings:
            decision = READINESS_WARNINGS
        else:
            decision = READINESS_READY

        if not failures and readiness_score < policy.min_readiness_score_for_ready:
            decision = READINESS_WARNINGS
            warnings.append(
                f"Readiness score {readiness_score} below preferred minimum "
                f"{policy.min_readiness_score_for_ready}."
            )

        evaluated_at = _now()
        simulation = _dict(session.get("simulation_report"))
        approval = _dict(session.get("approval_decision"))
        budget = _dict(session.get("budget_decision"))

        return {
            "decision": decision,
            "readiness_score": readiness_score,
            "readiness_failures": failures,
            "readiness_warnings": warnings,
            "checks": {
                check.name: {
                    "passed": check.passed,
                    "score": check.score,
                    "failures": check.failures,
                    "warnings": check.warnings,
                }
                for check in checks
            },
            "metadata": {
                "readiness_provenance": {
                    "engine": ENGINE_NAME,
                    "engine_version": ENGINE_VERSION,
                    "policy_version": policy.policy_version,
                    "evaluated_at": evaluated_at,
                },
                "simulation_report_uuid": simulation.get("report_uuid"),
                "governance_decision_ids": {
                    "approval": approval.get("decision_id"),
                    "budget": budget.get("decision_id"),
                },
            },
        }

    def enrich_session(
        self,
        session: dict[str, Any],
        policy: ReadinessPolicy | None = None,
    ) -> dict[str, Any]:
        session = dict(session)
        readiness = self.evaluate(session, policy=policy)
        timestamp = _now()

        session["execution_readiness"] = readiness
        session["state"] = readiness["decision"]
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10g_v1"

        metadata = _dict(session.get("metadata"))
        metadata["readiness_version"] = ENGINE_VERSION
        metadata["readiness_evaluated_at"] = timestamp
        session["metadata"] = metadata

        history = list(session.get("state_history") or [])
        history.append(
            {
                "at": timestamp,
                "state": readiness["decision"],
                "reason": (
                    f"readiness gate: {readiness['decision']} "
                    f"(score={readiness['readiness_score']})"
                ),
            }
        )
        session["state_history"] = history
        return session

    def _check_simulation_exists(self, session: dict[str, Any]) -> CheckResult:
        simulation = _dict(session.get("simulation_report"))
        failures: list[str] = []
        warnings: list[str] = []

        if not simulation:
            failures.append("Simulation report is missing.")
            return CheckResult("simulation_exists", False, 0.0, failures, warnings)

        if not simulation.get("report_id"):
            warnings.append("Simulation report_id missing.")
        if not simulation.get("report_uuid"):
            warnings.append("Simulation report_uuid missing (legacy report).")
        if simulation.get("stitch_complexity") == "high":
            warnings.append("Simulation stitch_complexity is high.")

        score = 100.0 - (10.0 * len(warnings))
        return CheckResult("simulation_exists", True, max(score, 70.0), failures, warnings)

    def _check_governance_exists(self, session: dict[str, Any]) -> CheckResult:
        approval = _dict(session.get("approval_decision"))
        budget = _dict(session.get("budget_decision"))
        failures: list[str] = []
        warnings: list[str] = []

        if not approval or not approval.get("evaluated_by"):
            failures.append("Approval governance decision is missing.")
        if not budget or not budget.get("evaluated_by"):
            failures.append("Budget governance decision is missing.")

        if failures:
            return CheckResult("governance_exists", False, 0.0, failures, warnings)

        approval_status = str(approval.get("status", ""))
        budget_status = str(budget.get("budget_status", ""))

        if approval_status != "APPROVED_FOR_EXECUTION":
            failures.append(f"Approval status is {approval_status or 'unknown'}, not APPROVED_FOR_EXECUTION.")
        if budget.get("budget_allowed") is not True:
            failures.append("Budget is not allowed for execution.")
        if budget_status == "BUDGET_BLOCKED":
            failures.append("Budget status is BUDGET_BLOCKED.")
        elif budget_status == "WARNING":
            warnings.append("Budget status is WARNING.")

        if failures:
            return CheckResult("governance_exists", False, 0.0, failures, warnings)

        score = 90.0 if warnings else 100.0
        return CheckResult("governance_exists", True, score, failures, warnings)

    def _check_provider_selection_exists(self, session: dict[str, Any]) -> CheckResult:
        provider_selection = _dict(session.get("provider_selection"))
        provider = str(provider_selection.get("primary_provider") or session.get("provider") or "").strip()
        failures: list[str] = []
        warnings: list[str] = []

        if not provider:
            failures.append("Provider selection is missing.")
            return CheckResult("provider_selection_exists", False, 0.0, failures, warnings)

        provider_key = provider.lower()
        if not any(known in provider_key for known in KNOWN_PROVIDERS):
            warnings.append(f"Provider '{provider}' is not in the known provider registry.")

        retry = str(
            provider_selection.get("expected_retry_risk")
            or _dict(session.get("simulation_report")).get("estimated_retry_risk")
            or ""
        ).lower()
        if retry == "high":
            warnings.append("Provider retry risk is high.")
        elif retry == "medium":
            warnings.append("Provider retry risk is medium.")
        if "_browser" in provider_key:
            warnings.append("Browser provider selected — runtime variability expected.")

        score = 100.0 - (8.0 * len(warnings))
        return CheckResult(
            "provider_selection_exists",
            True,
            max(score, 60.0),
            failures,
            warnings,
        )

    def _check_story_quality_exists(self, session: dict[str, Any]) -> CheckResult:
        story_quality = _dict(session.get("story_quality"))
        failures: list[str] = []
        warnings: list[str] = []

        score_value = story_quality.get("composite_score") or story_quality.get("score") or session.get("story_quality_score")
        if not story_quality or score_value is None:
            failures.append("Story quality score is missing.")
            return CheckResult("story_quality_exists", False, 0.0, failures, warnings)

        decision = str(story_quality.get("decision", "")).upper()
        if decision in {"REJECT", "REGENERATE"}:
            failures.append(f"Story quality decision is {decision}.")
        elif decision == "REVISE":
            warnings.append("Story quality decision is REVISE.")

        critical = story_quality.get("critical_failures") or []
        if critical:
            failures.append("Story quality has critical failures.")

        for warning in story_quality.get("warnings") or []:
            text = str(warning).strip()
            if text:
                warnings.append(text)

        if failures:
            return CheckResult("story_quality_exists", False, 0.0, failures, warnings)

        score = 100.0 - min(30.0, 5.0 * len(warnings))
        return CheckResult("story_quality_exists", True, max(score, 70.0), failures, warnings)

    def _check_required_fields(self, session: dict[str, Any]) -> CheckResult:
        missing = [field for field in REQUIRED_ROOT_FIELDS if not _present(session.get(field))]
        failures = [f"Required field missing: {field}" for field in missing]
        warnings: list[str] = []

        simulation = _dict(session.get("simulation_report"))
        if session.get("simulation_report_id") and simulation.get("report_id"):
            if session.get("simulation_report_id") != simulation.get("report_id"):
                warnings.append("simulation_report_id does not match simulation_report.report_id.")

        brief = _dict(session.get("brief_snapshot"))
        if not _dict(brief.get("video_format_plan")).get("clip_count"):
            warnings.append("brief_snapshot.video_format_plan.clip_count missing.")

        if failures:
            score = max(0.0, 100.0 * (1 - len(missing) / len(REQUIRED_ROOT_FIELDS)))
            return CheckResult("required_fields_completeness", False, score, failures, warnings)

        score = 100.0 - (5.0 * len(warnings))
        return CheckResult("required_fields_completeness", True, max(score, 80.0), failures, warnings)

    def _check_fingerprint_consistency(self, session: dict[str, Any]) -> CheckResult:
        simulation = _dict(session.get("simulation_report"))
        metadata = _dict(simulation.get("metadata"))
        stored = metadata.get("simulation_fingerprint")
        failures: list[str] = []
        warnings: list[str] = []

        if not stored:
            warnings.append("Simulation fingerprint absent — stale simulation cannot be ruled out.")
            return CheckResult("fingerprint_consistency", True, 70.0, failures, warnings)

        current = compute_simulation_fingerprint(session)
        if current != stored:
            failures.append("Simulation fingerprint mismatch — session changed since simulation.")
            return CheckResult("fingerprint_consistency", False, 0.0, failures, warnings)

        return CheckResult("fingerprint_consistency", True, 100.0, failures, warnings)

    def _check_valid_session_state(self, session: dict[str, Any]) -> CheckResult:
        state = str(session.get("state", "")).upper()
        failures: list[str] = []
        warnings: list[str] = []

        if state in GOVERNED_STATES:
            return CheckResult("valid_session_state", True, 100.0, failures, warnings)

        if state in {"AWAITING_APPROVAL", "BUDGET_BLOCKED", "REJECTED", "SIMULATED", "PLANNED"}:
            failures.append(f"Session state {state} is not governed for queue entry.")
            return CheckResult("valid_session_state", False, 0.0, failures, warnings)

        if state in {READINESS_READY, READINESS_WARNINGS, READINESS_NOT_READY}:
            warnings.append(f"Session state already set to {state} before readiness re-run.")

        failures.append(f"Session state {state or 'UNKNOWN'} is invalid for readiness gate.")
        return CheckResult("valid_session_state", False, 0.0, failures, warnings)


__all__ = [
    "ExecutionReadinessGate",
    "ReadinessPolicy",
    "READINESS_READY",
    "READINESS_WARNINGS",
    "READINESS_NOT_READY",
]
