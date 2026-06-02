"""
Phase 10E/10F — minimal pre-execution simulation report (rule-based, no providers).
"""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any

from content_brain.execution.session_fingerprint import compute_simulation_fingerprint

ENGINE_NAME = "SimulationReportBuilder"
ENGINE_VERSION = "10e_v1"
SIMULATION_MODE = "pre_execution_rule_based"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

RETRY_MULTIPLIERS = {"low": 1.0, "medium": 1.25, "high": 1.5}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _fingerprint(session: dict[str, Any]) -> str:
    return compute_simulation_fingerprint(session)


def _retry_bucket(session: dict[str, Any]) -> str:
    simulation = _dict(session.get("simulation_report"))
    provider = _dict(session.get("provider_selection"))
    risk = str(
        simulation.get("estimated_retry_risk")
        or provider.get("expected_retry_risk")
        or "low"
    ).lower()
    if risk in RETRY_MULTIPLIERS:
        return risk
    return "medium" if "medium" in risk else "high" if "high" in risk else "low"


class SimulationReportBuilder:
    """Build simulation_report from a populated session document."""

    def build(self, session: dict[str, Any]) -> dict[str, Any]:
        brief = _dict(session.get("brief_snapshot"))
        format_plan = _dict(brief.get("video_format_plan"))
        story_quality = _dict(session.get("story_quality"))
        provider_selection = _dict(session.get("provider_selection"))

        clip_count = int(format_plan.get("clip_count") or 1)
        provider = str(
            provider_selection.get("primary_provider") or session.get("provider") or "hailuo"
        ).lower()
        per_clip = 1.0 if "runway" not in provider else 2.0
        estimated_credits = round(max(clip_count, 1) * per_clip, 2)
        target_duration = int(format_plan.get("target_duration_seconds") or 30)
        retry_risk = _retry_bucket(session)

        composite = story_quality.get("composite_score") or story_quality.get("score") or 70.0
        confidence = session.get("execution_confidence_score")
        if confidence is None:
            confidence = max(40.0, min(95.0, float(composite) - 8.0))

        report_uuid = str(uuid.uuid4())
        report_id = f"sim_{uuid.uuid4().hex[:8]}"

        report: dict[str, Any] = {
            "report_uuid": report_uuid,
            "report_id": report_id,
            "generated_at": _now(),
            "simulation_mode": SIMULATION_MODE,
            "simulation_version": ENGINE_VERSION,
            "estimated_clip_count": clip_count,
            "estimated_generation_time_minutes": round(clip_count * 2.0 * RETRY_MULTIPLIERS[retry_risk], 2),
            "estimated_provider_cost": estimated_credits,
            "estimated_credits": estimated_credits,
            "estimated_retry_risk": retry_risk,
            "stitch_complexity": "high" if clip_count >= 5 else "moderate" if clip_count >= 3 else "low",
            "continuity_risk": "low",
            "execution_confidence_estimate": round(float(confidence), 1),
            "cost_estimate": {
                "estimated_total_credits": estimated_credits,
                "per_clip_credits": per_clip,
                "provider": provider,
            },
            "runtime_estimate": {
                "estimated_total_minutes": round(target_duration / 60.0, 2),
                "estimated_generation_minutes": round(clip_count * 2.0, 2),
                "target_duration_seconds": target_duration,
            },
            "metadata": {
                "generator": {
                    "engine": ENGINE_NAME,
                    "engine_version": ENGINE_VERSION,
                    "simulation_mode": SIMULATION_MODE,
                },
                "simulation_fingerprint": _fingerprint(session),
                "simulation_fingerprint_version": ENGINE_VERSION,
                "fingerprint_sources": ["brief_snapshot", "story_quality", "provider_selection"],
            },
        }
        return report

    def enrich_session(self, session: dict[str, Any]) -> dict[str, Any]:
        report = self.build(session)
        session = dict(session)
        session["simulation_report"] = report
        session["simulation_report_id"] = report["report_id"]
        session["state"] = "SIMULATED"
        session["execution_confidence_score"] = report["execution_confidence_estimate"]
        provider_selection = _dict(session.get("provider_selection"))
        provider_selection["expected_retry_risk"] = report["estimated_retry_risk"]
        session["provider_selection"] = provider_selection

        approval_request = _dict(session.get("approval_request"))
        approval_request["estimated_credits"] = report["estimated_credits"]
        approval_request["estimated_runtime_minutes"] = report["runtime_estimate"]["estimated_total_minutes"]
        session["approval_request"] = approval_request

        budget_decision = _dict(session.get("budget_decision"))
        budget_decision["estimated_credits"] = report["estimated_credits"]
        session["budget_decision"] = budget_decision

        # Fingerprint must reflect post-simulation session (provider_selection is updated above).
        report["metadata"]["simulation_fingerprint"] = compute_simulation_fingerprint(session)
        session["simulation_report"] = report

        timestamp = _now()
        session["updated_at"] = timestamp
        history = list(session.get("state_history") or [])
        history.append({"at": timestamp, "state": "SIMULATED", "reason": "pre-execution simulation"})
        session["state_history"] = history
        return session


__all__ = ["SimulationReportBuilder"]
