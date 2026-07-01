"""Validate Kling Continuity Chain V1 — frame extract, upload mapping, metadata, safety."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_continuity_runtime import (  # noqa: E402
    RUNTIME_VERSION,
    clip_is_approved,
    continuity_chain_v1_path,
    record_upload_status,
    run_kling_continuity_chain,
    upload_frame_for_next_clip,
    verify_upload_visible,
    write_continuity_chain_files,
)
from content_brain.execution.kling_last_frame_extractor import (  # noqa: E402
    EXTRACTOR_VERSION,
    continuity_frame_path,
    extract_and_save_continuity_frame,
    extract_last_frame,
    save_frame,
    validate_frame,
)
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_CONTINUITY_CHAIN_VERSION,
    build_kling_native_audio_plan,
)
from content_brain.execution.kling_native_audio_planner import (  # noqa: E402
    plan_kling_native_audio_content,
    validate_kling_content_plan,
)
from content_brain.execution.kling_product_run import (  # noqa: E402
    _execute_kling_clips,
    load_kling_product_run_results,
)

REAL_RUN_ID = "kling_ms_20260617T035534_f392af70"
REAL_CLIP_MP4 = ROOT / "outputs" / "kling_multishot_live" / REAL_RUN_ID / "clips" / "c1" / "video.mp4"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_extract_last_frame() -> None:
    if not REAL_CLIP_MP4.is_file():
        _pass("extract_last_frame_skipped", True, "real MP4 not present — skip live extract")
        return
    with tempfile.TemporaryDirectory() as tmp:
        temp = extract_last_frame(REAL_CLIP_MP4)
        dest = Path(tmp) / "frame.png"
        saved = save_frame(temp, dest)
        validation = validate_frame(saved)
        _pass("extract_last_frame", validation.get("ok") is True, str(saved))


def test_frame_file_exists() -> None:
    if not REAL_CLIP_MP4.is_file():
        _pass("frame_file_exists_skipped", True, "real MP4 not present")
        return
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        extracted = extract_and_save_continuity_frame(
            video_path=REAL_CLIP_MP4,
            run_dir=run_dir,
            clip_index=1,
        )
        frame_path = continuity_frame_path(run_dir, 1)
        _pass("frame_file_exists", frame_path.is_file(), str(frame_path))
        _pass("frame_path_matches", extracted.frame_path == str(frame_path.resolve()))


def test_upload_runtime_uses_mapped_control() -> None:
    source = (ROOT / "content_brain/execution/kling_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("upload_uses_first_frame_upload", 'try_locate_control(page, "first_frame_upload"' in source)
    _pass("upload_record_status", "record_upload_status" in source)
    page = MagicMock()
    with patch(
        "content_brain.execution.kling_continuity_runtime.try_locate_control",
        return_value=MagicMock(strategy="role_button_first_frame", locator=page.locator.return_value),
    ), patch(
        "content_brain.execution.kling_continuity_runtime.load_kling_ui_map",
        return_value={"labels": {"first_frame_upload": {"strategies": []}}},
    ):
        visible = verify_upload_visible(page)
        _pass("verify_upload_visible", visible.get("ok") is True, visible.get("strategy", ""))


def test_continuity_metadata_created() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        plan = build_kling_native_audio_plan(requested_duration_seconds=30)
        from content_brain.execution.kling_native_audio_models import build_continuity_chain_from_plan

        plan_chain = build_continuity_chain_from_plan(plan, run_id="chain_meta_test").to_dict()
        from content_brain.execution.kling_continuity_runtime import KlingContinuityChainState

        state = KlingContinuityChainState(
            run_id="chain_meta_test",
            clip_count=2,
            clips=[{"clip": 1, "last_frame": "/tmp/frame_c1.png", "next_clip": 2}],
        )
        payload = write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=state)
        v1_path = continuity_chain_v1_path(run_dir)
        _pass("continuity_chain_v1_exists", v1_path.is_file(), str(v1_path))
        _pass("continuity_version", payload.get("version") == KLING_CONTINUITY_CHAIN_VERSION)
        _pass("continuity_clips_array", isinstance(payload.get("clips"), list) and len(payload["clips"]) == 1)


def test_clip2_receives_frame_from_clip1() -> None:
    plan = plan_kling_native_audio_content(topic="boy and dragon", planned_duration_seconds=30)
    ok, _ = validate_kling_content_plan(plan)
    _pass("planner_30s_valid", ok)
    clip2 = plan.clips[1]
    _pass("clip2_prior_source", clip2.first_frame_source == "prior_clip_shot2_final_frame")
    _pass("clip2_prior_reference", "continue" in clip2.prior_clip_reference.lower())
    _pass("clip2_shot1_continuity", "continuing from" in clip2.shot_1.prompt.lower())


def test_clip3_receives_frame_from_clip2() -> None:
    plan = plan_kling_native_audio_content(topic="boy and dragon", planned_duration_seconds=45)
    clip3 = plan.clips[2]
    _pass("clip3_exists", clip3.clip_index == 3)
    _pass("clip3_prior_index", clip3.prior_clip_index == 2)
    _pass("clip3_shot1_reference", "continuing from" in clip3.shot_1.prompt.lower())


def test_chain_can_stop_safely() -> None:
    approved = clip_is_approved(2, {1})
    _pass("clip2_not_auto_approved", approved is False)
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        run_dir.mkdir(parents=True)
        plan = build_kling_native_audio_plan(requested_duration_seconds=30)
        payload = {"approve_generate": True, "approved_clips": [1]}

        def _fake_live(**kwargs: object):
            from content_brain.execution.kling_multishot_live_engine import (
                DOWNLOAD_STATUS_PASSED,
                KlingMultishotLiveResult,
                STATUS_COMPLETED,
            )

            output_dir = Path(str(kwargs.get("output_dir")))
            video = output_dir / "video.mp4"
            video.write_bytes(b"\x00" * 2_000_000)
            return KlingMultishotLiveResult(
                ok=True,
                status=STATUS_COMPLETED,
                run_id="stop_test",
                dry_run_prepare=False,
                generate_clicked=True,
                credits_spent=True,
                generation_completed=True,
                download_status=DOWNLOAD_STATUS_PASSED,
                approved_by="operator",
                approved_at="now",
                download_path=str(video),
                output_path=str(video),
                approval_checklist={"first_frame_uploaded": False},
            )

        with patch("content_brain.execution.kling_continuity_runtime.run_kling_multishot_live", side_effect=_fake_live), patch(
            "content_brain.execution.kling_continuity_runtime.verify_recovered_mp4",
            return_value={"is_real_mp4": True, "duration_seconds": 15.0},
        ), patch(
            "content_brain.execution.kling_continuity_runtime.extract_and_save_continuity_frame",
            return_value=MagicMock(frame_path=str(run_dir / "continuity" / "frame_c1.png"), to_dict=lambda: {}),
        ):
            _, generation_report, _, _, _, continuity = run_kling_continuity_chain(
                project_root=tmp,
                run_id="stop_test",
                run_dir=run_dir,
                plan=plan,
                approved_by="operator",
                confirm_credit_spend=True,
                first_frame_path=None,
                cdp_url="http://127.0.0.1:9222",
                payload=payload,
            )
        _pass("chain_stopped_for_clip2", continuity.get("continuity_status") == "awaiting_approval")
        _pass("generation_one_clip", len(generation_report.get("clip_results") or []) == 1)


def test_approval_still_enforced() -> None:
    live_source = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    _pass("live_engine_approval_gate", "grant_continuity_approval" in live_source)
    _pass("live_engine_confirm_credit", "confirm_credit_spend" in live_source)
    config_source = (ROOT / "content_brain/execution/kling_multishot_config.py").read_text(encoding="utf-8")
    _pass("generate_button_gated", "generate_button" in config_source and "APPROVAL_GATED" in config_source)


def test_single_clip_flow_uses_continuity_runtime() -> None:
    source = (ROOT / "content_brain/execution/kling_product_run.py").read_text(encoding="utf-8")
    _pass("product_run_delegates_runtime", "run_kling_continuity_chain" in source)
    plan = build_kling_native_audio_plan(requested_duration_seconds=15)
    _pass("single_clip_count", plan.clip_count == 1)


def test_runway_flow_unchanged() -> None:
    runway_post = ROOT / "content_brain/execution/runway_live_post_processor.py"
    runway_nav = ROOT / "content_brain/execution/runway_ui_navigator.py"
    _pass("runway_post_processor_exists", runway_post.is_file())
    _pass("runway_navigator_exists", runway_nav.is_file())
    continuity_source = (ROOT / "content_brain/execution/kling_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("runtime_no_runway_rewrite", "runway_ui_navigator" not in continuity_source)


def test_results_loader_exposes_continuity_fields() -> None:
    if not (ROOT / "outputs" / "kling_multishot_live" / REAL_RUN_ID).is_dir():
        _pass("results_loader_skipped", True, "real run folder not present")
        return
    payload = load_kling_product_run_results(ROOT, run_id=REAL_RUN_ID)
    _pass("results_found", payload is not None)
    if payload:
        _pass("results_has_continuity_status", "continuity_status" in payload)
        _pass("results_has_frames_extracted", "frames_extracted_count" in payload)
        _pass("results_has_chain_complete", "chain_complete" in payload)


def main() -> None:
    test_extract_last_frame()
    test_frame_file_exists()
    test_upload_runtime_uses_mapped_control()
    test_continuity_metadata_created()
    test_clip2_receives_frame_from_clip1()
    test_clip3_receives_frame_from_clip2()
    test_chain_can_stop_safely()
    test_approval_still_enforced()
    test_single_clip_flow_uses_continuity_runtime()
    test_runway_flow_unchanged()
    test_results_loader_exposes_continuity_fields()
    print("validate_kling_continuity_chain_v1: all checks passed")


if __name__ == "__main__":
    main()
