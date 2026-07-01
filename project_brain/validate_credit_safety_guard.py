"""Validation — global free-credit-first credit safety guard."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.credit_safety_guard import (  # noqa: E402
    CREDIT_MODE_DRY_RUN,
    CREDIT_MODE_FREE,
    CREDIT_MODE_UNKNOWN,
    PAID_BLOCKED_MESSAGE,
    assert_credit_safe_for_live_run,
    evaluate_credit_safety,
)
from content_brain.execution.pwmap_runway_agent_adapter import run_pwmap_product_studio_generate  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def main() -> int:
    print("validate_credit_safety_guard")
    print("=" * 60)

    paid_blocked = evaluate_credit_safety(
        payload={"duration_seconds": 30, "clip_count": 2},
        preflight={"duration_plan": {"duration_seconds": 30, "clip_count": 2}},
        provider="runway",
        model="Kling 3.0 Pro",
    )
    _record(
        "paid_run_blocked_without_approval",
        paid_blocked.blocked and not paid_blocked.allowed,
        paid_blocked.block_reason[:60],
    )
    _record(
        "paid_block_message",
        PAID_BLOCKED_MESSAGE in (paid_blocked.block_reason or ""),
    )
    _record(
        "unknown_credit_mode_is_paid_risk",
        paid_blocked.credit_mode == CREDIT_MODE_UNKNOWN and paid_blocked.paid_credit_risk is True,
    )
    _record(
        "report_includes_credit_mode_and_paid_risk",
        "credit_mode" in paid_blocked.to_report() and "paid_credit_risk" in paid_blocked.to_report(),
    )

    free_allowed = evaluate_credit_safety(
        payload={"free_credit_mode": True, "duration_seconds": 30, "clip_count": 2},
        preflight={"duration_plan": {"clip_count": 2, "duration_seconds": 30}},
        provider="runway",
    )
    _record(
        "free_credit_mode_allowed",
        free_allowed.allowed and free_allowed.credit_mode == CREDIT_MODE_FREE,
        free_allowed.credit_mode,
    )

    dry = evaluate_credit_safety(payload={"dry_run": True}, dry_run=True)
    _record(
        "dry_run_allowed",
        dry.allowed and dry.credit_mode == CREDIT_MODE_DRY_RUN,
        dry.credit_mode,
    )

    retest_blocked = evaluate_credit_safety(
        payload={"duration_seconds": 30, "clip_count": 2},
        preflight={"duration_plan": {"duration_seconds": 30, "clip_count": 2}},
        live_retest=True,
        duration_seconds=30,
        clip_count=2,
    )
    _record(
        "30s_live_retest_refuses_paid_without_approval",
        retest_blocked.blocked,
        retest_blocked.block_reason[:80],
    )

    approved = evaluate_credit_safety(
        payload={
            "duration_seconds": 30,
            "operator_paid_approval": True,
            "credit_mode": "paid",
            "confirm_credit_spend": True,
            "approved_by": "operator",
        },
        operator_paid_approval=True,
        credit_mode="paid",
    )
    _record(
        "paid_allowed_with_operator_approval",
        approved.allowed and approved.operator_paid_approval is True,
        str(approved.may_spend_paid_credits),
    )

    preflight = {
        "authoritative_topic": "credit safety validation",
        "duration_plan": {"duration_seconds": 30, "clip_count": 2, "requested_duration_seconds": 30},
        "multiclip_execution_plan": {"clip_count": 2, "duration_seconds": 30},
        "kling_clip_count": 2,
        "pipeline_steps": [],
    }
    try:
        from content_brain.execution.pwmap_runway_agent_adapter import build_pwmap_job_from_preflight

        build_pwmap_job_from_preflight(preflight, native_audio=True)
        pwmap_blocked = run_pwmap_product_studio_generate(
            project_root=ROOT,
            payload={"duration_seconds": 30, "clip_count": 2},
            preflight=preflight,
        )
        _record(
            "pwmap_product_studio_blocks_paid_by_default",
            pwmap_blocked.get("status") == "paid_credit_blocked",
            str(pwmap_blocked.get("status")),
        )
        _record(
            "pwmap_blocked_report_has_credit_fields",
            pwmap_blocked.get("credit_mode") and pwmap_blocked.get("paid_credit_risk") is True,
            str(pwmap_blocked.get("credit_mode")),
        )
    except Exception as exc:
        _record("pwmap_product_studio_blocks_paid_by_default", False, str(exc))
        _record("pwmap_blocked_report_has_credit_fields", False, str(exc))

    import project_brain.validate_results_run_truth_consistency as truth_validator  # noqa: E402

    truth_exit = truth_validator.main()
    _record("results_truth_validator_still_passes", truth_exit == PASS, str(truth_exit))

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"Passed: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return FAIL
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
