"""Shared simulation fingerprint helper for execution sessions."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def compute_simulation_fingerprint(session: dict[str, Any]) -> str:
    payload = {
        "brief_snapshot": session.get("brief_snapshot"),
        "story_quality": session.get("story_quality"),
        "provider_selection": session.get("provider_selection"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


QUEUE_FINGERPRINT_VERSION = "10h_v1"
QUEUE_FINGERPRINT_SOURCES = [
    "execution_readiness",
    "approval_decision",
    "budget_decision",
    "simulation_fingerprint",
]


def compute_queue_fingerprint(session: dict[str, Any]) -> str:
    """Composite hash of governing inputs at enqueue time (store-only in 10H)."""
    readiness = _dict(session.get("execution_readiness"))
    approval = _dict(session.get("approval_decision"))
    budget = _dict(session.get("budget_decision"))
    simulation_meta = _dict(_dict(session.get("simulation_report")).get("metadata"))

    payload = {
        "execution_readiness": {
            "decision": readiness.get("decision"),
            "readiness_score": readiness.get("readiness_score"),
            "readiness_failures": sorted(readiness.get("readiness_failures") or []),
            "readiness_warnings": sorted(readiness.get("readiness_warnings") or []),
            "governance_decision_ids": _dict(
                _dict(readiness.get("metadata")).get("governance_decision_ids")
            ),
        },
        "approval_decision": {
            "decision_id": approval.get("decision_id"),
            "status": approval.get("status"),
            "policy_version": _dict(approval.get("policy_snapshot")).get("policy_version"),
        },
        "budget_decision": {
            "decision_id": budget.get("decision_id"),
            "budget_status": budget.get("budget_status"),
            "budget_allowed": budget.get("budget_allowed"),
            "policy_version": _dict(budget.get("policy_snapshot")).get("policy_version"),
        },
        "simulation_fingerprint": simulation_meta.get("simulation_fingerprint"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


__all__ = [
    "compute_simulation_fingerprint",
    "compute_queue_fingerprint",
    "QUEUE_FINGERPRINT_VERSION",
    "QUEUE_FINGERPRINT_SOURCES",
]
