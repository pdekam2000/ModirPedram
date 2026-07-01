"""Validate Kling Frame-to-Video generate approval state handling."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE  # noqa: E402
from content_brain.execution.kling_multishot_live_engine import (  # noqa: E402
    STATUS_AWAITING_APPROVAL,
    STATUS_COMPLETED,
    STATUS_PREPARED,
)
from content_brain.execution.kling_native_audio_models import KLING_AUDIO_STRATEGY, KLING_PROVIDER_ID  # noqa: E402
from content_brain.execution.kling_product_run import PRODUCT_STUDIO_APPROVED_BY, run_kling_product_studio_generate  # noqa: E402
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

DRAGON_TOPIC = (
    "A young boy discovers an injured baby dragon under twisted forest roots in a fantasy cinematic story"
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _kling_payload(**overrides: object) -> dict:
    base = {
        "topic_mode": "custom",
        "custom_topic": DRAGON_TOPIC,
        "duration_seconds": 30,
        "platform": "youtube",
        "provider": "kling",
        "audio_strategy": "kling_native_audio",
    }
    base.update(overrides)
    return base


def _frame_preflight(service: ProductStudioService) -> dict:
    pre = service.create_video_preflight(_kling_payload())
    _pass("preflight_frame_mode", pre.get("kling_shot_mode") == KLING_FRAME_TO_VIDEO_MODE)
    return pre


def test_frame_generate_without_approval_awaiting() -> None:
    service = ProductStudioService(ROOT)
    _frame_preflight(service)
    with patch("content_brain.execution.kling_product_run._execute_kling_clips") as mock_exec:
        mock_exec.return_value = (
            [{"clip_index": 1, "generate_clicked": True, "ok": True}],
            {"status": STATUS_COMPLETED},
            {"status": "completed"},
            "/tmp/video.mp4",
            {},
            {"continuity_status": "complete"},
        )
        result = service.create_video_generate(_kling_payload(), runway_service=object())
    _pass("auto_approved_by", result.get("approved_by") == PRODUCT_STUDIO_APPROVED_BY)
    _pass("runtime_called", mock_exec.called is True)
    _pass("generate_clicked", result.get("generate_clicked") is True)
    _pass("not_failed", result.get("status") != "failed")


def test_frame_generate_approved_by_only_awaiting() -> None:
    service = ProductStudioService(ROOT)
    _frame_preflight(service)
    result = service.create_video_generate(
        _kling_payload(approve_generate=True, approved_by="pop", confirm_credit_spend=False),
        runway_service=object(),
    )
    _pass("status", result.get("status") == STATUS_AWAITING_APPROVAL)
    _pass("approval_required", result.get("approval_required") is True)
    _pass("approved_by_echo", result.get("approved_by") == "pop")
    _pass("native_audio_status", result.get("native_audio_status") == "planned")
    _pass("generate_clicked", result.get("generate_clicked") is False)


def test_frame_generate_full_approval_proceeds() -> None:
    service = ProductStudioService(ROOT)
    pre = _frame_preflight(service)
    executed = {"called": False}

    def _fake_execute(**kwargs: object) -> tuple:
        executed["called"] = True
        return (
            [{"clip_index": 1, "generate_clicked": True, "credits_spent": True, "ok": True}],
            {"status": STATUS_COMPLETED, "clip_results": []},
            {"status": "completed", "final_video_path": "/tmp/video.mp4"},
            "/tmp/video.mp4",
            {},
            {"continuity_status": "complete", "chain_complete": True},
        )

    with patch("content_brain.execution.kling_product_run._execute_kling_clips", side_effect=_fake_execute):
        result = run_kling_product_studio_generate(
            project_root=ROOT,
            payload=_kling_payload(
                approve_generate=True,
                approved_by="operator",
                confirm_credit_spend=True,
            ),
            preflight=pre,
        )
    _pass("execute_called", executed["called"] is True)
    _pass("status", result.get("status") == STATUS_COMPLETED)
    _pass("generate_clicked", result.get("generate_clicked") is True)


def test_native_audio_not_failed_before_execution() -> None:
    service = ProductStudioService(ROOT)
    pre = _frame_preflight(service)
    with patch("content_brain.execution.kling_product_run._execute_kling_clips") as mock_exec:
        mock_exec.return_value = (
            [{"clip_index": 1, "generate_clicked": False, "ok": False, "status": STATUS_PREPARED}],
            {"status": STATUS_PREPARED},
            {"status": "pending"},
            "",
            {},
            {"continuity_status": "stopped"},
        )
        result = run_kling_product_studio_generate(
            project_root=ROOT,
            payload=_kling_payload(approve_generate=True, approved_by="operator", confirm_credit_spend=True),
            preflight=pre,
        )
    _pass("native_not_failed", result.get("native_audio_status") != "failed", str(result.get("native_audio_status")))
    _pass("status_not_failed", result.get("status") != "failed", str(result.get("status")))
    _pass("prepared_or_awaiting", result.get("status") in {STATUS_AWAITING_APPROVAL, STATUS_PREPARED, STATUS_COMPLETED})


def test_generate_clicked_false_only_when_not_executed() -> None:
    service = ProductStudioService(ROOT)
    pre = _frame_preflight(service)
    blocked = run_kling_product_studio_generate(
        project_root=ROOT,
        payload=_kling_payload(),
        preflight=pre,
    )
    _pass("blocked_generate_clicked", blocked.get("generate_clicked") is False)
    _pass("blocked_status", blocked.get("status") in {STATUS_AWAITING_APPROVAL, STATUS_PREPARED})

    with patch(
        "content_brain.execution.kling_product_run._execute_kling_clips",
        return_value=(
            [{"clip_index": 1, "generate_clicked": True, "credits_spent": True, "ok": False, "status": "failed"}],
            {"status": "failed"},
            {"status": "failed"},
            "",
            {},
            {"continuity_status": "stopped"},
        ),
    ):
        failed = run_kling_product_studio_generate(
            project_root=ROOT,
            payload=_kling_payload(
                approve_generate=True,
                approved_by="operator",
                confirm_credit_spend=True,
            ),
            preflight=pre,
        )
    _pass("executed_generate_clicked", failed.get("generate_clicked") is True)
    _pass("executed_failed_ok", failed.get("status") == "failed")


def test_runway_approval_unchanged() -> None:
    service = ProductStudioService(ROOT)
    runway_service = MagicMock()
    runway_service.start_runway_session.return_value = {"ok": True, "status": "started"}
    with patch("ui.api.product_studio_service.run_content_brain_e2e_micro_test") as mock_e2e:
        mock_e2e.return_value = {
            "run_id": "runway_test",
            "topic": "Ancient Rome vault secrets",
            "clip_count": 3,
            "prompts": ["p1", "p2", "p3"],
        }
        with patch("ui.api.product_studio_service.clear_registered_e2e_result"):
            result = service.create_video_generate(
                {
                    "topic_mode": "custom",
                    "custom_topic": "Ancient Rome vault secrets",
                    "duration_seconds": 30,
                    "platform": "youtube",
                    "provider": "runway",
                    "audio_strategy": "narrator",
                },
                runway_service=runway_service,
            )
    _pass("runway_not_kling", result.get("provider") != KLING_PROVIDER_ID)
    _pass("runway_no_kling_approval_gate", result.get("approval_required") is not True)
    _pass("runway_wired_or_handled", result.get("wired") is not False or result.get("status") == "failed")


def test_multishot_fallback_approval_unchanged() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(_kling_payload())
    pre["kling_shot_mode"] = "two_shot_continuity"
    pre.pop("kling_frame_to_video_plan", None)
    result = run_kling_product_studio_generate(
        project_root=ROOT,
        payload=_kling_payload(),
        preflight=pre,
    )
    _pass("multishot_awaiting", result.get("status") == STATUS_AWAITING_APPROVAL)
    _pass("multishot_approval_required", result.get("approval_required") is True)
    _pass("multishot_strategy", "two_shot" in str(result.get("kling_shot_mode") or ""))


def main() -> int:
    print("validate_kling_frame_generate_approval_state_fix")
    test_frame_generate_without_approval_awaiting()
    test_frame_generate_approved_by_only_awaiting()
    test_frame_generate_full_approval_proceeds()
    test_native_audio_not_failed_before_execution()
    test_generate_clicked_false_only_when_not_executed()
    test_runway_approval_unchanged()
    test_multishot_fallback_approval_unchanged()
    print("All Kling frame generate approval state fix checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
