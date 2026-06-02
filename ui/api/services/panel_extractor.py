"""Map execution session JSON to expandable panel DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from content_brain.execution.category_runtime_compat import build_category_runtime_view


def _first(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _first_number(*values: Any, default: float | None = None) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _panel(
    *,
    status: str,
    completeness: float,
    warnings: list[str],
    metadata: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "completeness": round(max(0.0, min(1.0, completeness)), 2),
        "warnings": warnings,
        "metadata": metadata,
        "data": data,
    }


def _status_from_completeness(completeness: float) -> str:
    if completeness >= 0.85:
        return "available"
    if completeness >= 0.35:
        return "partial"
    if completeness <= 0.0:
        return "missing"
    return "partial"


class PanelExtractor:
    """Extract panel envelopes from raw session documents."""

    def extract_all(self, data: dict[str, Any]) -> dict[str, Any]:
        panels = {
            "story_quality_panel": self.extract_story_quality(data),
            "approval_panel": self.extract_approval(data),
            "budget_panel": self.extract_budget(data),
            "priority_panel": self.extract_priority(data),
            "provider_selection_panel": self.extract_provider_selection(data),
            "simulation_panel": self.extract_simulation(data, _dict(data.get("simulation_report"))),
            "readiness_panel": self.extract_readiness(data),
            "queue_panel": self.extract_queue(data),
            "provider_runtime_panel": self.extract_provider_runtime(data),
        }
        panels["data_completeness"] = {
            key.replace("_panel", ""): panel["completeness"]
            for key, panel in panels.items()
        }
        return panels

    def extract_story_quality(self, data: dict[str, Any]) -> dict[str, Any]:
        story_quality = _dict(data.get("story_quality"))
        score = _first_number(
            data.get("story_quality_score"),
            story_quality.get("composite_score"),
            story_quality.get("composite"),
            story_quality.get("score"),
        )
        decision = _first(
            story_quality.get("decision"),
            data.get("story_quality_decision"),
        )
        warnings = [
            str(item)
            for item in (story_quality.get("warnings") or [])
            if str(item).strip()
        ]
        critical = [
            str(item)
            for item in (story_quality.get("critical_failures") or [])
            if str(item).strip()
        ]
        cost_risk = _first_number(
            story_quality.get("production_cost_score"),
            _dict(data.get("simulation_report")).get("estimated_credits"),
        )

        present = sum(
            1
            for item in (score, decision, warnings, critical, cost_risk)
            if item not in (None, "", [], {})
        )
        completeness = present / 5.0

        panel_warnings: list[str] = []
        if score is None:
            panel_warnings.append("Story quality score not recorded.")
        if not decision:
            panel_warnings.append("Story quality decision not recorded (Phase 9D pending).")

        panel_data: dict[str, Any] = {
            "score": score,
            "decision": decision or None,
            "critical_failures": critical,
            "warnings": warnings,
            "cost_risk_score": cost_risk,
        }
        if story_quality:
            panel_data["raw"] = story_quality

        return _panel(
            status=_status_from_completeness(completeness),
            completeness=completeness,
            warnings=panel_warnings,
            metadata={
                "source_keys": ["story_quality_score", "story_quality"],
                "future_ready": True,
            },
            data=panel_data,
        )

    def extract_approval(self, data: dict[str, Any]) -> dict[str, Any]:
        approval_request = _dict(data.get("approval_request"))
        approval_decision = _dict(data.get("approval_decision"))
        simulation = _dict(data.get("simulation_report"))

        status = _first(
            data.get("approval_state"),
            approval_decision.get("status"),
            approval_decision.get("action"),
            approval_request.get("status"),
            default="",
        )
        estimated_credits = _first_number(
            approval_request.get("estimated_credits"),
            simulation.get("estimated_credits"),
            _dict(simulation.get("cost_estimate")).get("estimated_total_credits"),
        )
        estimated_runtime = _first_number(
            approval_request.get("estimated_runtime_minutes"),
            _dict(simulation.get("runtime_estimate")).get("estimated_total_minutes"),
        )
        provider_selection = _dict(approval_request.get("provider_selection"))
        provider = _first(
            provider_selection.get("primary_provider"),
            data.get("provider"),
        )

        present = sum(
            1
            for item in (status, estimated_credits, estimated_runtime, provider, approval_decision)
            if item not in (None, "", {}, [])
        )
        completeness = present / 5.0

        panel_warnings: list[str] = []
        if not approval_decision and approval_request:
            panel_warnings.append("Approval pending — no decision recorded yet.")
        if estimated_runtime is None:
            panel_warnings.append("Estimated runtime not available.")

        return _panel(
            status=_status_from_completeness(completeness),
            completeness=completeness,
            warnings=panel_warnings,
            metadata={"source_keys": ["approval_state", "approval_request", "approval_decision"]},
            data={
                "approval_state": status or None,
                "estimated_credits": estimated_credits,
                "estimated_runtime_minutes": estimated_runtime,
                "provider": provider or None,
                "decision": approval_decision or None,
                "request": approval_request or None,
            },
        )

    def extract_budget(self, data: dict[str, Any]) -> dict[str, Any]:
        budget_decision = _dict(data.get("budget_decision"))
        simulation = _dict(data.get("simulation_report"))
        cost_estimate = _dict(simulation.get("cost_estimate"))

        allowed = budget_decision.get("budget_allowed")
        budget_status = _first(
            budget_decision.get("budget_status"),
            budget_decision.get("budget_state"),
        )
        budget_state = _first(
            data.get("budget_state"),
            budget_status,
            "allowed" if allowed is True else "",
            "blocked" if allowed is False else "",
            "warning" if budget_status == "WARNING" else "",
        )
        estimated_cost = _first_number(
            budget_decision.get("estimated_credits"),
            simulation.get("estimated_credits"),
            cost_estimate.get("estimated_total_credits"),
        )
        remaining = _dict(budget_decision.get("remaining_budget_after_run"))
        budget_warnings = [
            str(item)
            for item in (budget_decision.get("budget_warnings") or [])
            if str(item).strip()
        ]
        block_reason = _first(budget_decision.get("budget_block_reason"))

        present = sum(
            1
            for item in (budget_state, estimated_cost, remaining, budget_warnings, block_reason)
            if item not in (None, "", {}, [])
        )
        completeness = present / 5.0

        panel_warnings = list(budget_warnings)
        if block_reason:
            panel_warnings.append(block_reason)
        if not budget_decision and budget_state:
            panel_warnings.append("Only summary budget_state available — decision object missing.")

        return _panel(
            status=_status_from_completeness(completeness),
            completeness=completeness,
            warnings=panel_warnings,
            metadata={"source_keys": ["budget_state", "budget_decision"]},
            data={
                "budget_state": budget_state or None,
                "budget_status": budget_status or None,
                "budget_allowed": allowed,
                "estimated_cost": estimated_cost,
                "remaining_budget_after_run": remaining or None,
                "budget_block_reason": block_reason or None,
            },
        )

    def extract_priority(self, data: dict[str, Any]) -> dict[str, Any]:
        priority_decision = _dict(data.get("priority_decision"))
        band = _first(
            data.get("priority_band"),
            priority_decision.get("priority_band"),
        )
        score = _first_number(
            priority_decision.get("priority_score"),
            data.get("priority_score"),
        )
        queue_position = priority_decision.get("queue_position", data.get("queue_position"))

        present = sum(
            1
            for item in (band, score, queue_position)
            if item not in (None, "", {})
        )
        completeness = present / 3.0

        panel_warnings: list[str] = []
        if queue_position is None:
            panel_warnings.append("Queue position not available.")

        return _panel(
            status=_status_from_completeness(completeness),
            completeness=completeness,
            warnings=panel_warnings,
            metadata={"source_keys": ["priority_band", "priority_decision", "queue_position"]},
            data={
                "priority_band": band or None,
                "priority_score": score,
                "queue_position": queue_position,
                "decision": priority_decision or None,
            },
        )

    def extract_provider_selection(self, data: dict[str, Any]) -> dict[str, Any]:
        provider_selection = _dict(data.get("provider_selection"))
        confidence = _dict(data.get("execution_confidence"))

        recommended = _first(
            provider_selection.get("primary_provider"),
            provider_selection.get("winner"),
            provider_selection.get("selected_provider"),
            data.get("provider"),
        )
        alternatives = provider_selection.get("alternatives") or provider_selection.get("runners_up") or []
        if not isinstance(alternatives, list):
            alternatives = []

        confidence_score = _first_number(
            data.get("execution_confidence_score"),
            confidence.get("execution_confidence_score"),
        )
        confidence_band = _first(confidence.get("confidence_band"))
        retry_risk = _first(provider_selection.get("expected_retry_risk"))

        present = sum(
            1
            for item in (recommended, alternatives, confidence_score, confidence_band, retry_risk)
            if item not in (None, "", [], {})
        )
        completeness = present / 5.0

        panel_warnings: list[str] = []
        if not provider_selection:
            panel_warnings.append("Provider selection object missing — showing flat provider only.")
        if not confidence_band:
            panel_warnings.append("Execution confidence band not recorded.")

        return _panel(
            status=_status_from_completeness(completeness),
            completeness=completeness,
            warnings=panel_warnings,
            metadata={"source_keys": ["provider_selection", "execution_confidence", "provider"]},
            data={
                "recommended_provider": recommended or None,
                "alternative_providers": alternatives,
                "execution_confidence_score": confidence_score,
                "confidence_band": confidence_band or None,
                "expected_retry_risk": retry_risk or None,
                "selection": provider_selection or None,
                "confidence": confidence or None,
            },
        )

    def extract_simulation(self, data: dict[str, Any], simulation_report: dict[str, Any] | None) -> dict[str, Any]:
        report = simulation_report if isinstance(simulation_report, dict) else _dict(data.get("simulation_report"))
        report_id = _first(report.get("report_id"), data.get("simulation_report_id"))

        present = sum(1 for item in (report, report_id) if item not in (None, "", {}))
        completeness = 1.0 if report else (0.5 if report_id else 0.0)

        panel_warnings: list[str] = []
        if not report:
            panel_warnings.append("Simulation report not available.")

        return _panel(
            status=_status_from_completeness(completeness),
            completeness=completeness,
            warnings=panel_warnings,
            metadata={"source_keys": ["simulation_report", "simulation_report_id"]},
            data={
                "report_id": report_id or None,
                "report": report or None,
            },
        )


    def extract_readiness(self, data: dict[str, Any]) -> dict[str, Any]:
        readiness = _dict(data.get("execution_readiness"))
        decision = _first(readiness.get("decision"))
        score = readiness.get("readiness_score")
        failures = [
            str(item)
            for item in (readiness.get("readiness_failures") or [])
            if str(item).strip()
        ]
        warnings = [
            str(item)
            for item in (readiness.get("readiness_warnings") or [])
            if str(item).strip()
        ]

        present = sum(
            1
            for item in (decision, score, failures or warnings or readiness)
            if item not in (None, "", {}, [])
        )
        completeness = present / 4.0 if readiness else 0.0

        panel_warnings = list(warnings)
        if failures:
            panel_warnings.extend(failures)
        if not readiness:
            panel_warnings.append("Execution readiness has not been evaluated.")

        return _panel(
            status=_status_from_completeness(completeness if readiness else 0.0),
            completeness=completeness if readiness else 0.0,
            warnings=panel_warnings,
            metadata={"source_keys": ["execution_readiness"]},
            data={
                "decision": decision or None,
                "readiness_score": score,
                "readiness_failures": failures,
                "readiness_warnings": warnings,
                "readiness": readiness or None,
            },
        )

    def extract_queue(self, data: dict[str, Any]) -> dict[str, Any]:
        queue_item = _dict(data.get("queue_item"))
        queue_state = _first(queue_item.get("queue_state"))
        priority = _dict(queue_item.get("priority"))
        lifecycle = _dict(queue_item.get("lifecycle"))
        enqueue_ctx = _dict(queue_item.get("enqueue_context"))
        metadata = _dict(queue_item.get("metadata"))
        queue_fingerprint = metadata.get("queue_fingerprint")

        present = sum(
            1
            for item in (queue_state, priority.get("queue_position"), enqueue_ctx.get("enqueued_at"), queue_item)
            if item not in (None, "", {}, [])
        )
        completeness = present / 4.0 if queue_item else 0.0

        panel_warnings: list[str] = []
        if not queue_item:
            panel_warnings.append("Session has not been enqueued.")

        return _panel(
            status=_status_from_completeness(completeness if queue_item else 0.0),
            completeness=completeness if queue_item else 0.0,
            warnings=panel_warnings,
            metadata={"source_keys": ["queue_item", "queue_audit_log"]},
            data={
                "queue_state": queue_state or None,
                "queue_item_id": queue_item.get("queue_item_id"),
                "queue_position": priority.get("queue_position"),
                "priority_band": priority.get("priority_band"),
                "effective_priority": priority.get("effective_priority"),
                "enqueued_at": enqueue_ctx.get("enqueued_at"),
                "expires_at": lifecycle.get("expires_at"),
                "queue_fingerprint": queue_fingerprint,
                "queue_item": queue_item or None,
            },
        )

    def extract_provider_runtime(self, data: dict[str, Any]) -> dict[str, Any]:
        runtime = _dict(data.get("execution_runtime"))
        runtime_state = _first(runtime.get("state"))
        category_runtime = _dict(runtime.get("category_runtime"))
        video_slot = _dict(category_runtime.get("video_generation"))
        voice_slot = _dict(category_runtime.get("voice_generation"))
        category_runtime_slots = build_category_runtime_view(runtime) if runtime else []
        artifacts = _dict(runtime.get("artifacts_by_category"))
        video_artifacts = artifacts.get("video_generation") or []
        if not isinstance(video_artifacts, list):
            video_artifacts = []
        failure = _dict(runtime.get("failure"))

        present = sum(
            1
            for item in (
                runtime_state,
                runtime.get("provider_resolved"),
                runtime.get("dispatch_id"),
                runtime.get("dispatched_at"),
            )
            if item not in (None, "", {}, [])
        )
        completeness = present / 4.0 if runtime else 0.0

        panel_warnings: list[str] = []
        if not runtime:
            panel_warnings.append("Provider runtime has not been dispatched.")
        if failure:
            panel_warnings.append(_first(failure.get("message"), failure.get("code"), default="Runtime failure recorded."))

        return _panel(
            status=_status_from_completeness(completeness if runtime else 0.0),
            completeness=completeness if runtime else 0.0,
            warnings=panel_warnings,
            metadata={"source_keys": ["execution_runtime", "provider_audit_log"]},
            data={
                "runtime_state": runtime_state or None,
                "provider_category": runtime.get("provider_category"),
                "provider_resolved": runtime.get("provider_resolved"),
                "provider_mode": runtime.get("provider_mode"),
                "dispatch_id": runtime.get("dispatch_id"),
                "dispatched_at": runtime.get("dispatched_at"),
                "running_at": runtime.get("running_at"),
                "completed_at": runtime.get("completed_at"),
                "clip_artifact_count": len(video_artifacts),
                "video_generation_state": video_slot.get("state"),
                "voice_generation_status": voice_slot.get("status"),
                "voice_generation_executed": voice_slot.get("executed"),
                "voice_preflight_dry_run": _dict(_dict(runtime.get("operations")).get("voice_preflight_dry_run")) or None,
                "voice_approval_gate": _dict(_dict(runtime.get("operations")).get("voice_approval_gate")) or None,
                "category_runtime_slots": category_runtime_slots,
                "failure": failure or None,
                "execution_runtime": runtime or None,
            },
        )


def overview_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
