"""Global free-credit-first safety guard for provider live tests and generation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

GUARD_VERSION = "credit_safety_guard_v1"
PAID_BLOCKED_MESSAGE = (
    "Paid credit execution blocked. Free-credit-first rule requires explicit approval."
)

CREDIT_MODE_FREE = "free"
CREDIT_MODE_TRIAL = "trial"
CREDIT_MODE_PAID = "paid"
CREDIT_MODE_DRY_RUN = "dry_run"
CREDIT_MODE_UNKNOWN = "unknown"

TEST_ORDER = (
    "A_dry_run_validation",
    "B_ui_runtime_simulation",
    "C_free_credit_live",
    "D_cheapest_short_live",
    "E_full_paid_provider",
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_model(payload: dict[str, Any], preflight: dict[str, Any] | None) -> str:
    preflight = preflight or {}
    job = dict(payload.get("job") or {})
    return str(
        payload.get("model")
        or job.get("model")
        or (preflight.get("duration_plan") or {}).get("model")
        or "Kling 3.0 Pro"
    ).strip()


def _resolve_provider(payload: dict[str, Any], preflight: dict[str, Any] | None) -> str:
    preflight = preflight or {}
    return str(
        payload.get("provider")
        or (preflight.get("duration_plan") or {}).get("provider")
        or "runway"
    ).strip().lower()


def _resolve_duration_seconds(payload: dict[str, Any], preflight: dict[str, Any] | None) -> int:
    preflight = preflight or {}
    plan = dict(preflight.get("duration_plan") or {})
    for key in ("requested_duration_seconds", "duration_seconds", "planned_duration_seconds"):
        value = payload.get(key) or plan.get(key)
        if value not in (None, ""):
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                pass
    try:
        return max(0, int(payload.get("duration_seconds") or payload.get("duration_preset") or 0))
    except (TypeError, ValueError):
        return 0


def _estimate_credit_cost(*, clip_count: int, duration_seconds: int, model: str) -> float | None:
    clips = max(1, int(clip_count or 1))
    if "kling" in model.lower() or "runway" in model.lower():
        return float(clips * 1.0)
    if duration_seconds >= 30:
        return float(clips * 1.0)
    return None


@dataclass
class CreditSafetyDecision:
    allowed: bool
    blocked: bool
    block_reason: str = ""
    provider: str = ""
    model: str = ""
    credit_mode: str = CREDIT_MODE_UNKNOWN
    paid_credit_risk: bool = True
    free_credit_checked: bool = False
    operator_paid_approval: bool = False
    free_credit_first: bool = True
    may_spend_paid_credits: bool = False
    available_free_credits: str = ""
    estimated_credit_cost: float | None = None
    test_phase_allowed: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_report(self) -> dict[str, Any]:
        return {
            "version": GUARD_VERSION,
            "provider": self.provider,
            "model": self.model,
            "credit_mode": self.credit_mode,
            "paid_credit_risk": self.paid_credit_risk,
            "free_credit_checked": self.free_credit_checked,
            "operator_paid_approval": self.operator_paid_approval,
            "free_credit_first": self.free_credit_first,
            "may_spend_paid_credits": self.may_spend_paid_credits,
            "available_free_credits": self.available_free_credits,
            "estimated_credit_cost": self.estimated_credit_cost,
            "test_phase_allowed": self.test_phase_allowed,
            "allowed": self.allowed,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            **self.metadata,
        }


def detect_available_free_credits(*, provider: str) -> tuple[str, bool]:
    """Best-effort free quota signal from env; unknown if not configured."""
    env_key = f"MODIR_{provider.upper()}_FREE_CREDITS_AVAILABLE"
    raw = os.environ.get(env_key) or os.environ.get("MODIR_FREE_CREDITS_AVAILABLE")
    if raw is None:
        return "unknown", False
    text = str(raw).strip().lower()
    if text in {"0", "false", "no", "none", "unavailable"}:
        return "unavailable", True
    return str(raw).strip(), True


CREDIT_MODE_BROWSER = "browser_automation"


def is_browser_automation_payload(payload: dict[str, Any] | None) -> bool:
    """Browser Playwright runs use the logged-in session — no API credits."""
    data = dict(payload or {})
    if data.get("browser_automation") or data.get("skip_credit_guard"):
        return True
    if str(data.get("provider_runtime") or "").strip().lower() == "pwmap_agent":
        return True
    if "pwmap/runway_agent" in str(data.get("execution_engine") or ""):
        return True
    return False


def evaluate_credit_safety(
    *,
    payload: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    provider: str = "",
    model: str = "",
    dry_run: bool = False,
    free_credit_first: bool | None = None,
    operator_paid_approval: bool | None = None,
    credit_mode: str = "",
    clip_count: int = 0,
    duration_seconds: int = 0,
    live_retest: bool = False,
) -> CreditSafetyDecision:
    """Evaluate whether a live provider run may proceed under free-credit-first rules."""
    payload = dict(payload or {})
    preflight = dict(preflight or {})

    # Browser automation uses logged-in Runway session — never block on API credits.
    provider_name = provider or _resolve_provider(payload, preflight)
    model_name = model or _resolve_model(payload, preflight)
    return CreditSafetyDecision(
        allowed=True,
        blocked=False,
        provider=provider_name,
        model=model_name,
        credit_mode=CREDIT_MODE_BROWSER,
        paid_credit_risk=False,
        free_credit_checked=False,
        operator_paid_approval=False,
        free_credit_first=False,
        may_spend_paid_credits=False,
        available_free_credits="browser_session",
        estimated_credit_cost=0.0,
        test_phase_allowed="browser_automation",
        metadata={"browser_automation": True, "reason": "browser_automation"},
    )

    provider_name = provider or _resolve_provider(payload, preflight)
    model_name = model or _resolve_model(payload, preflight)
    duration = duration_seconds or _resolve_duration_seconds(payload, preflight)
    clips = int(
        clip_count
        or payload.get("clip_count")
        or (preflight.get("multiclip_execution_plan") or {}).get("clip_count")
        or (preflight.get("duration_plan") or {}).get("clip_count")
        or 1
    )

    free_first = _env_bool("MODIR_FREE_CREDIT_FIRST", True) if free_credit_first is None else bool(free_credit_first)
    operator_approved = (
        _env_bool("MODIR_OPERATOR_PAID_APPROVAL", False)
        if operator_paid_approval is None
        else bool(operator_paid_approval)
    )
    if payload.get("operator_paid_approval") is True:
        operator_approved = True
    if payload.get("confirm_credit_spend") and str(payload.get("approved_by") or "").strip():
        operator_approved = True

    free_quota_text, free_checked = detect_available_free_credits(provider=provider_name)
    explicit_mode = str(credit_mode or payload.get("credit_mode") or "").strip().lower()
    free_credit_mode = bool(payload.get("free_credit_mode") or payload.get("use_free_credits"))

    if dry_run or bool(payload.get("dry_run")):
        return CreditSafetyDecision(
            allowed=True,
            blocked=False,
            provider=provider_name,
            model=model_name,
            credit_mode=CREDIT_MODE_DRY_RUN,
            paid_credit_risk=False,
            free_credit_checked=True,
            operator_paid_approval=operator_approved,
            free_credit_first=free_first,
            may_spend_paid_credits=False,
            available_free_credits=free_quota_text,
            estimated_credit_cost=0.0,
            test_phase_allowed=TEST_ORDER[0],
        )

    if free_credit_mode or explicit_mode in {CREDIT_MODE_FREE, CREDIT_MODE_TRIAL}:
        mode = CREDIT_MODE_TRIAL if explicit_mode == CREDIT_MODE_TRIAL else CREDIT_MODE_FREE
        return CreditSafetyDecision(
            allowed=True,
            blocked=False,
            provider=provider_name,
            model=model_name,
            credit_mode=mode,
            paid_credit_risk=False,
            free_credit_checked=True,
            operator_paid_approval=operator_approved,
            free_credit_first=free_first,
            may_spend_paid_credits=False,
            available_free_credits=free_quota_text or mode,
            estimated_credit_cost=_estimate_credit_cost(
                clip_count=clips, duration_seconds=duration, model=model_name
            ),
            test_phase_allowed=TEST_ORDER[2],
        )

    if explicit_mode == CREDIT_MODE_PAID and operator_approved:
        return CreditSafetyDecision(
            allowed=True,
            blocked=False,
            provider=provider_name,
            model=model_name,
            credit_mode=CREDIT_MODE_PAID,
            paid_credit_risk=True,
            free_credit_checked=free_checked,
            operator_paid_approval=True,
            free_credit_first=free_first,
            may_spend_paid_credits=True,
            available_free_credits=free_quota_text,
            estimated_credit_cost=_estimate_credit_cost(
                clip_count=clips, duration_seconds=duration, model=model_name
            ),
            test_phase_allowed=TEST_ORDER[4],
        )

    paid_risk = True
    may_spend = operator_approved and not free_first
    if free_first and not operator_approved:
        blocked = True
        reason = PAID_BLOCKED_MESSAGE
        if live_retest and duration == 30:
            reason = (
                f"{PAID_BLOCKED_MESSAGE} "
                "30s live retest requires free-credit mode first; "
                "set free_credit_mode=true or operator_paid_approval=true."
            )
        elif free_quota_text == "unavailable":
            reason = (
                f"{PAID_BLOCKED_MESSAGE} Free credits unavailable — "
                "stop and report before spending paid credits."
            )
        return CreditSafetyDecision(
            allowed=False,
            blocked=True,
            block_reason=reason,
            provider=provider_name,
            model=model_name,
            credit_mode=CREDIT_MODE_UNKNOWN,
            paid_credit_risk=paid_risk,
            free_credit_checked=free_checked,
            operator_paid_approval=operator_approved,
            free_credit_first=free_first,
            may_spend_paid_credits=False,
            available_free_credits=free_quota_text,
            estimated_credit_cost=_estimate_credit_cost(
                clip_count=clips, duration_seconds=duration, model=model_name
            ),
            test_phase_allowed=TEST_ORDER[2] if live_retest else "",
            metadata={"live_retest": live_retest, "duration_seconds": duration, "clip_count": clips},
        )

    return CreditSafetyDecision(
        allowed=operator_approved,
        blocked=not operator_approved,
        block_reason="" if operator_approved else PAID_BLOCKED_MESSAGE,
        provider=provider_name,
        model=model_name,
        credit_mode=CREDIT_MODE_PAID if operator_approved else CREDIT_MODE_UNKNOWN,
        paid_credit_risk=paid_risk,
        free_credit_checked=free_checked,
        operator_paid_approval=operator_approved,
        free_credit_first=free_first,
        may_spend_paid_credits=may_spend,
        available_free_credits=free_quota_text,
        estimated_credit_cost=_estimate_credit_cost(
            clip_count=clips, duration_seconds=duration, model=model_name
        ),
        test_phase_allowed=TEST_ORDER[4] if operator_approved else TEST_ORDER[2],
    )


def assert_credit_safe_for_live_run(**kwargs: Any) -> CreditSafetyDecision:
    """Return decision; caller blocks when decision.blocked."""
    return evaluate_credit_safety(**kwargs)


def attach_credit_safety_to_report(report: dict[str, Any], decision: CreditSafetyDecision) -> dict[str, Any]:
    merged = dict(report)
    merged["credit_safety"] = decision.to_report()
    merged["credit_mode"] = decision.credit_mode
    merged["paid_credit_risk"] = decision.paid_credit_risk
    merged["free_credit_checked"] = decision.free_credit_checked
    merged["operator_paid_approval"] = decision.operator_paid_approval
    if decision.estimated_credit_cost is not None:
        merged["estimated_credit_cost"] = decision.estimated_credit_cost
    return merged


def blocked_live_response(*, decision: CreditSafetyDecision, run_id: str = "", **extra: Any) -> dict[str, Any]:
    payload = {
        "ok": False,
        "wired": True,
        "status": "paid_credit_blocked",
        "message": decision.block_reason or PAID_BLOCKED_MESSAGE,
        "run_id": run_id,
        "credits_spent": False,
        "approval_required": True,
    }
    payload.update(extra)
    return attach_credit_safety_to_report(payload, decision)


__all__ = [
    "GUARD_VERSION",
    "PAID_BLOCKED_MESSAGE",
    "TEST_ORDER",
    "CREDIT_MODE_BROWSER",
    "CreditSafetyDecision",
    "assert_credit_safe_for_live_run",
    "attach_credit_safety_to_report",
    "blocked_live_response",
    "detect_available_free_credits",
    "evaluate_credit_safety",
    "is_browser_automation_payload",
]
