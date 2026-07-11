#!/usr/bin/env python3
"""PHASE 45S-3CLIP-ROOT-CAUSE-REPAIR — use-frame seek + fail-closed upload/assembly validator."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PWMAP_ROOT = ROOT / "external" / "pwmap"
if str(PWMAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PWMAP_ROOT))

from content_brain.automation.fail_closed_upload_gate import evaluate_automation_upload_gate  # noqa: E402
from content_brain.execution.kling_native_audio_planner import plan_kling_frame_from_audio_route  # noqa: E402
from content_brain.execution.product_multiclip_execution_plan import (  # noqa: E402
    build_multiclip_execution_plan,
    plan_product_duration,
)
from content_brain.execution.product_multiclip_orchestrator import finalize_multiclip_output  # noqa: E402
from content_brain.execution.product_subtitle_branding_publish import FINAL_BRANDED_PUBLISH_READY_NAME  # noqa: E402
from content_brain.execution.pwmap_clip_assembly_guard import verify_clips_unique_for_assembly  # noqa: E402
from content_brain.execution.pwmap_finalization import recover_partial_clips_to_run_dir  # noqa: E402
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME  # noqa: E402
from runway_agent import (  # noqa: E402
    USE_FRAME_END_OFFSET_SEC,
    UseFrameSeekFailedError,
    seek_video_for_use_frame,
)

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {name}{suffix}")
    if not ok:
        raise SystemExit(1)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _seed_publish_chain(tmp: Path, *, clip_count: int = 3, unique_clips: bool = True) -> tuple[Path, dict]:
    run_dir = tmp / "outputs" / "pwmap_agent_runs" / "pwmap_validate_45s"
    run_dir.mkdir(parents=True, exist_ok=True)
    publish = run_dir / "publish"
    publish.mkdir(parents=True, exist_ok=True)
    for index in range(1, clip_count + 1):
        payload = bytes([index]) * 4096 if unique_clips else b"same_clip_bytes" * 256
        _write_bytes(run_dir / f"clip_{index}.mp4", payload)
    branded = publish / FINAL_BRANDED_PUBLISH_READY_NAME
    _write_bytes(branded, b"\x00" * 4096)
    (publish / YOUTUBE_METADATA_FILENAME).write_text(
        json.dumps({"title": "Test", "description": "Test", "tags": [], "hashtags": []}),
        encoding="utf-8",
    )
    report = {
        "ok": True,
        "status": "completed",
        "run_id": "pwmap_validate_45s",
        "run_dir": str(run_dir).replace("\\", "/"),
        "clip_count": clip_count,
        "expected_clip_count": clip_count,
        "clips_completed": clip_count,
        "assembly_status": "completed",
        "assembly_complete": True,
        "merge_info": {"merged": True, "assembly_status": "completed"},
        "branding_status": "completed",
        "publish_ready": True,
        "publish_package_ready": True,
        "publish_package_path": str(publish).replace("\\", "/"),
        "final_branded_publish_video_path": str(branded).replace("\\", "/"),
        "youtube_metadata_path": str((publish / YOUTUBE_METADATA_FILENAME)).replace("\\", "/"),
        "youtube_upload_allowed": True,
    }
    return run_dir, report


def test_seek_rejects_012s() -> None:
    page = MagicMock()
    video = MagicMock()
    video.count.return_value = 1
    video.first = video
    page.locator.return_value = video

    durations = [15.0] * 6
    currents = [0.12] * 6

    def evaluate_side_effect(script, *args):
        script_text = str(script)
        if "currentTime" in script_text and "duration" in script_text:
            idx = evaluate_side_effect.probe_calls
            evaluate_side_effect.probe_calls += 1
            return {"currentTime": currents[idx], "duration": durations[idx]}
        return None

    evaluate_side_effect.probe_calls = 0

    video.evaluate.side_effect = evaluate_side_effect

    with patch("runway_agent._feed_top_video", return_value=video), patch(
        "runway_agent._wait_for_video_metadata_loaded", return_value=15.0
    ):
        try:
            seek_video_for_use_frame(page, 15, clip_index=2)
            record("seek_never_accepts_0_12s", False, "expected UseFrameSeekFailedError")
        except UseFrameSeekFailedError as exc:
            record(
                "seek_never_accepts_0_12s",
                "0.12" in str(exc) or exc.failed_clip_index == 2,
                str(exc),
            )


def test_seek_accepts_duration_minus_offset() -> None:
    page = MagicMock()
    video = MagicMock()
    video.count.return_value = 1
    video.first = video
    page.locator.return_value = video

    target = 15.0 - USE_FRAME_END_OFFSET_SEC

    def evaluate_side_effect(script, arg=None):
        script_text = str(script)
        if "currentTime" in script_text and "duration" in script_text:
            return {"currentTime": target, "duration": 15.0}
        return None

    video.evaluate.side_effect = evaluate_side_effect

    with patch("runway_agent._feed_top_video", return_value=video), patch(
        "runway_agent._wait_for_video_metadata_loaded", return_value=15.0
    ):
        landed = seek_video_for_use_frame(page, 15, clip_index=2)
        record(
            "seek_accepts_duration_minus_0_3",
            abs(landed - target) <= 0.75,
            f"landed={landed:.2f}s target={target:.2f}s",
        )


def test_duplicate_clips_block_assembly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        run_dir.mkdir(parents=True)
        payload = b"duplicate_clip_payload" * 128
        _write_bytes(run_dir / "clip_1.mp4", payload)
        _write_bytes(run_dir / "clip_2.mp4", payload)
        guard = verify_clips_unique_for_assembly(run_dir=run_dir, clip_count=2)
        merge = finalize_multiclip_output(
            run_dir=run_dir,
            clip_count=2,
            execution_mode="use_frame_chain",
        )
        record(
            "duplicate_clips_block_assembly",
            not guard.get("assembly_allowed")
            and merge.get("assembly_status") == "blocked_duplicate_or_missing_clips",
            str(merge.get("merge_note") or guard.get("error")),
        )


def test_duplicate_clips_block_upload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir, report = _seed_publish_chain(tmp_path, clip_count=2, unique_clips=False)
        allowed, reason = evaluate_automation_upload_gate(
            project_root=tmp_path,
            generation_report=report,
            run_id="pwmap_validate_45s",
            planned_clip_count=2,
            publish_package_path=str(run_dir / "publish"),
        )
        record("duplicate_clips_block_upload", not allowed and reason == "blocked_duplicate_clips", reason)


def test_partial_failed_blocks_upload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir, report = _seed_publish_chain(tmp_path, clip_count=3, unique_clips=True)
        report["status"] = "partial_failed"
        report["ok"] = False
        report["youtube_upload_allowed"] = False
        allowed, reason = evaluate_automation_upload_gate(
            project_root=tmp_path,
            generation_report=report,
            run_id="pwmap_validate_45s",
            planned_clip_count=3,
            publish_package_path=str(run_dir / "publish"),
        )
        record("partial_failed_blocks_upload", not allowed and reason == "blocked_partial_failed", reason)


def test_branding_missing_blocks_upload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir, report = _seed_publish_chain(tmp_path, clip_count=3, unique_clips=True)
        branded = Path(report["final_branded_publish_video_path"])
        branded.unlink(missing_ok=True)
        report["final_branded_publish_video_path"] = ""
        allowed, reason = evaluate_automation_upload_gate(
            project_root=tmp_path,
            generation_report=report,
            run_id="pwmap_validate_45s",
            planned_clip_count=3,
            publish_package_path=str(run_dir / "publish"),
        )
        record("branding_missing_blocks_upload", not allowed and reason == "blocked_missing_branding", reason)


def test_assembly_missing_blocks_upload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir, report = _seed_publish_chain(tmp_path, clip_count=3, unique_clips=True)
        report["assembly_status"] = ""
        report["assembly_complete"] = False
        report["merge_info"] = {"merged": False}
        allowed, reason = evaluate_automation_upload_gate(
            project_root=tmp_path,
            generation_report=report,
            run_id="pwmap_validate_45s",
            planned_clip_count=3,
            publish_package_path=str(run_dir / "publish"),
        )
        record("assembly_missing_blocks_upload", not allowed and reason == "blocked_missing_assembly", reason)


def test_final_branded_publish_ready_required() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir, report = _seed_publish_chain(tmp_path, clip_count=1, unique_clips=True)
        branded = Path(report["final_branded_publish_video_path"])
        branded.unlink(missing_ok=True)
        report["final_branded_publish_video_path"] = ""
        allowed, reason = evaluate_automation_upload_gate(
            project_root=tmp_path,
            generation_report=report,
            run_id="pwmap_validate_45s",
            planned_clip_count=1,
            publish_package_path=str(run_dir / "publish"),
        )
        record(
            "final_branded_publish_ready_required",
            not allowed and reason == "blocked_missing_branding",
            reason,
        )


def test_30s_two_clips_still_works() -> None:
    plan = plan_product_duration(30)
    record("30s_two_clips_duration", plan["duration_seconds"] == 30, str(plan))
    record("30s_two_clips_count", plan["clip_count"] == 2, str(plan["clip_count"]))
    preflight = {
        "authoritative_topic": "Science test topic",
        "kling_frame_to_video_plan": {
            "clips": [
                {"clip": 1, "prompt": "Clip one prompt"},
                {"clip": 2, "prompt": "Clip two prompt"},
            ]
        },
        "duration_plan": {"duration_seconds": 30},
    }
    multiclip = build_multiclip_execution_plan(preflight, duration_seconds=30)
    record("30s_two_clips_execution_plan", multiclip.clip_count == 2, str(multiclip.clip_count))


def test_45s_three_clips_generates_three_prompts() -> None:
    plan = plan_product_duration(45)
    record("45s_three_clips_duration", plan["duration_seconds"] == 45, str(plan))
    record("45s_three_clips_count", plan["clip_count"] == 3, str(plan["clip_count"]))

    frame_plan = plan_kling_frame_from_audio_route(
        topic="Quantum entanglement explained simply",
        audio_route={"kling_native_audio": {"planned_duration_seconds": 45, "clip_count": 3}},
        story_summary="A three-part science short.",
        planned_duration_seconds=45,
        clip_count=3,
    )
    prompt_count = len(getattr(frame_plan, "clips", []) or [])
    record("45s_three_clips_frame_plan_prompts", prompt_count == 3, f"prompts={prompt_count}")

    preflight = {
        "authoritative_topic": "Quantum entanglement explained simply",
        "kling_frame_to_video_plan": frame_plan.to_dict(),
        "duration_plan": {"duration_seconds": 45, "clip_count": 3},
    }
    multiclip = build_multiclip_execution_plan(preflight, duration_seconds=45)
    record(
        "45s_three_clips_execution_plan",
        multiclip.clip_count == 3 and len(multiclip.prompts) == 3,
        f"clips={multiclip.clip_count} prompts={len(multiclip.prompts)}",
    )


def test_recovery_never_duplicates_prior_clip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        downloads = Path(tmp) / "downloads"
        downloads.mkdir(parents=True)
        from datetime import datetime, timedelta, timezone
        import os

        now = datetime.now(timezone.utc)
        run_started = now - timedelta(seconds=1)
        same = b"clip_one_bytes" * 80000
        src1 = downloads / "clip_1.mp4"
        src2 = downloads / "clip_2.mp4"
        _write_bytes(src1, same)
        _write_bytes(src2, same)
        started_ts = now.timestamp()
        os.utime(src1, (started_ts, started_ts))
        os.utime(src2, (started_ts, started_ts))
        recovered = recover_partial_clips_to_run_dir(
            run_dir=run_dir,
            downloads_dir=downloads,
            run_started=run_started,
            run_ended=now,
        )
        record(
            "recovery_never_duplicates_prior_clip",
            len(recovered) == 1,
            f"recovered={len(recovered)}",
        )


def main() -> None:
    print("validate_45s_use_frame_and_fail_closed")
    test_seek_rejects_012s()
    test_seek_accepts_duration_minus_offset()
    test_duplicate_clips_block_assembly()
    test_duplicate_clips_block_upload()
    test_partial_failed_blocks_upload()
    test_branding_missing_blocks_upload()
    test_assembly_missing_blocks_upload()
    test_final_branded_publish_ready_required()
    test_30s_two_clips_still_works()
    test_45s_three_clips_generates_three_prompts()
    test_recovery_never_duplicates_prior_clip()
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nSUMMARY: {passed}/{len(results)} checks passed")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
