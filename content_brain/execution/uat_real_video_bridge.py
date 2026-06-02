"""
Phase 12I-B — UAT-only bridge to dequeue + provider dispatch for supervised real Runway video.

Does not modify queue engine defaults, provider runtime, or Runway browser automation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from automation.browser_launcher import get_browser_operator_status
from content_brain.execution.approval_budget_governance_engine import APPROVAL_APPROVED
from content_brain.execution.execution_queue_engine import ExecutionQueueEngine
from content_brain.execution.execution_readiness_gate import ExecutionReadinessGate
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.uat_runtime_profile import (
    UAT_TRIGGER,
    UatRuntimeConfig,
    normalize_video_provider,
)

BRIDGE_VERSION = "12i_b_v1"
UAT_SUPERVISED_VIDEO_REASON = "12I-B supervised real-video UAT"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def uat_log(channel: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={fields[key]}" for key in fields)
    print(f"[{channel}] {payload}".strip())


def uat_supervised_real_runway_requested(config: UatRuntimeConfig, *, mock_paid_providers: bool) -> bool:
    if mock_paid_providers or normalize_video_provider(config.video_provider) == "mock":
        return False
    return normalize_video_provider(config.video_provider) == "runway_browser" and bool(config.confirm_real_video)


def validate_runway_browser_operator_ready(project_root: Path) -> dict[str, Any]:
    """Fail loud if controlled Chrome / CDP / Runway login preconditions are not met."""
    status = get_browser_operator_status(project_root, probe_login=True)
    if not status.get("browser_running"):
        raise RuntimeError(
            "Browser not running: launch controlled Chrome from Execution Center or "
            "POST /operations/browser/launch before supervised real-video UAT."
        )
    if not status.get("cdp_connected"):
        raise RuntimeError(
            "CDP not connected: Chrome must listen on the configured debug port "
            "(default http://127.0.0.1:9222)."
        )
    if not status.get("runway_login_detected"):
        raise RuntimeError(
            "Runway login missing: open https://app.runwayml.com in the controlled Chrome "
            "profile and sign in before starting real-video UAT."
        )
    return status


def apply_uat_supervised_video_dispatch_readiness(session: dict[str, Any]) -> dict[str, Any]:
    """
    UAT-only session patch: supervised execution approval without re-running Content Brain
    or ApprovalBudgetGovernanceEngine (avoids resetting approval from brief REVISE).
    """
    session = dict(session)
    approval = dict(_dict(session.get("approval_decision")))
    approval["status"] = APPROVAL_APPROVED
    approval["action"] = "approved"
    approval["override"] = {
        "source": "uat_supervised_real_video",
        "bridge_version": BRIDGE_VERSION,
        "reason": UAT_SUPERVISED_VIDEO_REASON,
        "evaluated_at": _now(),
        "by": UAT_TRIGGER,
    }
    session["approval_decision"] = approval
    session["approval_state"] = "approved"
    session["state"] = "GOVERNED"
    return ExecutionReadinessGate().enrich_session(session)


def uat_runway_queue_and_dispatch_prepare(
    store: ExecutionSessionStore,
    session_id: str,
) -> dict[str, Any]:
    """
    Enqueue + dequeue this UAT session only so ProviderRuntimeEngine integrity passes.
    """
    session = store.load_session(session_id)
    session = apply_uat_supervised_video_dispatch_readiness(session)
    store.save_session(session, overwrite=True)

    readiness = _dict(session.get("execution_readiness"))
    decision = str(readiness.get("decision") or "")
    if decision not in {"READY", "READY_WITH_WARNINGS"}:
        failures = readiness.get("readiness_failures") or []
        raise RuntimeError(
            "Session not ready for UAT video dispatch after supervised approval override: "
            f"readiness={decision or 'unknown'}; "
            + ("; ".join(str(f) for f in failures) if failures else "no failure detail")
        )

    queue = ExecutionQueueEngine(store)
    enqueue = queue.enqueue_by_id(session_id, actor=UAT_TRIGGER)
    uat_log(
        "UAT_QUEUE",
        session_id=session_id,
        enqueued=enqueue.success,
        reject_code=enqueue.reject_code or "",
    )
    if not enqueue.success:
        reasons = "; ".join(enqueue.reject_reasons or [])
        raise RuntimeError(f"UAT queue enqueue failed ({enqueue.reject_code}): {reasons or 'unknown'}")

    dequeue = queue.dequeue_by_id(session_id, actor=UAT_TRIGGER)
    uat_log(
        "UAT_QUEUE",
        session_id=session_id,
        dequeued=dequeue.success,
        reject_code=dequeue.reject_code or "",
    )
    if not dequeue.success:
        reasons = "; ".join(dequeue.reject_reasons or [])
        raise RuntimeError(f"UAT queue dequeue failed ({dequeue.reject_code}): {reasons or 'unknown'}")

    refreshed = store.load_session(session_id)
    state = str(refreshed.get("state") or "")
    queue_item = _dict(refreshed.get("queue_item"))
    if state != "DEQUEUED" or queue_item.get("queue_state") != "DEQUEUED":
        raise RuntimeError(
            f"Queue state invalid after UAT bridge: session.state={state or 'missing'}, "
            f"queue_item.queue_state={queue_item.get('queue_state') or 'missing'}"
        )

    uat_log("UAT_QUEUE", session_id=session_id, dispatch_started=True, session_state=state)
    return refreshed


__all__ = [
    "BRIDGE_VERSION",
    "UAT_SUPERVISED_VIDEO_REASON",
    "uat_log",
    "uat_supervised_real_runway_requested",
    "validate_runway_browser_operator_ready",
    "apply_uat_supervised_video_dispatch_readiness",
    "uat_runway_queue_and_dispatch_prepare",
]
