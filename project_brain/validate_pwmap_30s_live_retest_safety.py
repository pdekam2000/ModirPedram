"""Validation — PWMAP 30s two-clip live retest safety gates."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.credit_safety_guard import (  # noqa: E402
    CREDIT_MODE_FREE,
    evaluate_credit_safety,
)
from content_brain.execution.product_multiclip_execution_plan import (  # noqa: E402
    EXECUTION_MODE_USE_FRAME,
    calculate_product_clip_count,
    execution_mode_for_clip_count,
)
from content_brain.execution.pwmap_clip_duplicate_guard import (  # noqa: E402
    DUPLICATE_ERROR,
    GUARD_VERSION,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []
CHANNEL_TOPIC = "dark fantasy analog horror stories"


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def main() -> int:
    print("validate_pwmap_30s_live_retest_safety")
    print("=" * 60)

    _record("30s_maps_to_two_clips", calculate_product_clip_count(30) == 2)
    _record(
        "30s_use_frame_execution_mode",
        execution_mode_for_clip_count(2) == EXECUTION_MODE_USE_FRAME,
    )
    _record("clip_3_not_applicable_for_30s", calculate_product_clip_count(30) < 3)

    free_decision = evaluate_credit_safety(
        payload={
            "duration_seconds": 30,
            "clip_count": 2,
            "free_credit_mode": True,
            "live_retest": True,
            "specific_story_override": "",
        },
        provider="runway",
        model="Kling 3.0 Pro",
        duration_seconds=30,
        clip_count=2,
        live_retest=True,
    )
    _record(
        "free_credit_mode_allowed_for_retest",
        free_decision.allowed and free_decision.credit_mode == CREDIT_MODE_FREE,
        free_decision.credit_mode,
    )
    _record(
        "free_credit_mode_zero_paid_risk",
        free_decision.paid_credit_risk is False,
        str(free_decision.paid_credit_risk),
    )

    paid_decision = evaluate_credit_safety(
        payload={"duration_seconds": 30, "clip_count": 2, "live_retest": True},
        provider="runway",
        duration_seconds=30,
        clip_count=2,
        live_retest=True,
    )
    _record(
        "paid_path_blocked_without_approval",
        paid_decision.blocked and not paid_decision.allowed,
        paid_decision.block_reason[:60],
    )

    service = ProductStudioService(ROOT)
    preflight = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": CHANNEL_TOPIC,
            "specific_story_override": "",
            "duration_seconds": 30,
            "provider": "kling_3_0_pro_native_audio",
            "audio_strategy": "kling_native_audio",
            "story_diversity_mode": "safe_variety",
        }
    )
    _record(
        "preflight_auto_ideation_active",
        not preflight.get("story_override_active") and bool(preflight.get("channel_story_idea")),
    )
    _record(
        "preflight_two_clip_plan",
        int((preflight.get("multiclip_execution_plan") or {}).get("clip_count") or preflight.get("kling_clip_count") or 0) == 2,
        str(preflight.get("kling_clip_count")),
    )

    blocked = service.create_video_generate(
        {
            "topic_mode": "custom",
            "custom_topic": CHANNEL_TOPIC,
            "duration_seconds": 30,
            "provider": "kling_3_0_pro_native_audio",
            "audio_strategy": "kling_native_audio",
            "live_retest": True,
            "dry_run": True,
            "free_credit_mode": True,
        },
        runway_service=None,
    )
    _record("dry_run_generate_allowed", blocked.get("status") == "dry_run", str(blocked.get("status")))

    unpaid = service.create_video_generate(
        {
            "topic_mode": "custom",
            "custom_topic": CHANNEL_TOPIC,
            "duration_seconds": 30,
            "provider": "kling_3_0_pro_native_audio",
            "audio_strategy": "kling_native_audio",
            "live_retest": True,
        },
        runway_service=None,
    )
    _record(
        "unapproved_live_generate_blocked",
        unpaid.get("status") == "paid_credit_blocked",
        str(unpaid.get("status")),
    )

    _record("duplicate_guard_module_present", GUARD_VERSION.startswith("pwmap_clip_duplicate_guard"))
    _record("duplicate_error_message_defined", "byte-identical" in DUPLICATE_ERROR.lower())

    import project_brain.validate_channel_story_ideation_diversity as ideation  # noqa: E402
    import project_brain.validate_pwmap_30s_two_clip_duplicate_guard as duplicate  # noqa: E402
    import project_brain.validate_results_run_truth_consistency as truth  # noqa: E402

    _record("ideation_validator_passes", ideation.main() == PASS)
    _record("duplicate_guard_validator_passes", duplicate.main() == PASS)
    _record("results_truth_validator_passes", truth.main() == PASS)

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"Passed: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return FAIL
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
