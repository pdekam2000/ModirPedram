"""Validate N-clip post-processing recovery and stale Results guards."""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.assembly_ffmpeg_availability import FFmpegAvailabilityResult
from content_brain.execution.runway_live_post_processor import (
    ASSEMBLY_ASSEMBLED,
    ASSEMBLY_PLAN_ONLY,
    PUBLISH_CREATED,
    collect_valid_download_paths,
    evaluate_post_processing_eligibility,
    run_assembly,
    run_live_post_processing,
    run_publish_package,
)
from project_brain.recover_latest_run_post_processing import recover_latest_run_post_processing
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


@dataclass
class FakeReport:
    ok: bool = True
    simulate: bool = False
    clip_count: int = 1
    clips_completed: int = 1
    total_downloads_completed: int = 1
    downloaded_file_paths: list[str] = field(default_factory=list)
    content_brain_run_id: str = "cb_test_run"
    content_brain_topic: str = "test topic"
    post_processing_enabled: bool = False
    post_processing_status: str = ""
    assembly_status: str = ""
    final_video_path: str = ""
    publish_package_status: str = ""
    publish_package_folder: str = ""
    post_processing_warnings: list[str] = field(default_factory=list)


def _make_clip(path: Path, label: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"fake-mp4-{label}".encode("utf-8"))
    return str(path)


def _fake_report(tmp: Path, clip_count: int, *, stale_counter: int | None = None) -> FakeReport:
    paths = [_make_clip(tmp / "downloads" / f"clip_{index}.mp4", f"clip_{index}") for index in range(1, clip_count + 1)]
    counter = len(paths) if stale_counter is None else stale_counter
    return FakeReport(
        ok=True,
        simulate=False,
        clip_count=clip_count,
        clips_completed=clip_count,
        total_downloads_completed=counter,
        downloaded_file_paths=paths,
        content_brain_run_id=f"cb_recovery_{clip_count}",
        content_brain_topic=f"topic_{clip_count}",
    )


def test_six_downloads_with_stale_counter_still_eligible() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 6, stale_counter=3)
        eligible, reason, context = evaluate_post_processing_eligibility(report)
        _pass("six_clip_eligible", eligible is True, reason)
        _pass("six_clip_context_count", len(context.get("downloaded_file_paths") or []) == 6)
        _pass("counter_synced", report.total_downloads_completed == 6)


def test_missing_file_blocks_post_processing() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 6, stale_counter=3)
        Path(report.downloaded_file_paths[-1]).unlink()
        eligible, reason, _ = evaluate_post_processing_eligibility(report)
        _pass("missing_file_not_eligible", eligible is False)
        _pass("missing_file_reason", "missing" in reason or "downloads_mismatch" in reason, reason)
        result = run_live_post_processing(report, project_root=tmp)
        _pass("missing_file_skipped_hook", result.get("enabled") is False)


def test_recovery_runs_post_processing_without_runway() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 2)
        report_path = tmp / "project_brain/runway_phase_i_3clip_last_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")

        unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
        with patch(
            "content_brain.execution.runway_live_post_processor.check_ffmpeg_availability",
            return_value=unavailable,
        ):
            summary = recover_latest_run_post_processing(tmp)

        _pass("recovery_ok", summary.get("ok") is True, str(summary))
        import inspect

        recovery_source = inspect.getsource(recover_latest_run_post_processing)
        _pass("recovery_no_smoke_call", "runway_live_smoke" not in recovery_source)
        _pass("recovery_no_browser_call", "browser" not in recovery_source.lower())
        updated = json.loads(report_path.read_text(encoding="utf-8"))
        _pass("recovery_persisted_status", updated.get("post_processing_status") == "completed")


def test_assembly_handles_six_clips() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 6)
        unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
        with patch(
            "content_brain.execution.runway_live_post_processor.check_ffmpeg_availability",
            return_value=unavailable,
        ):
            manifest = run_assembly(
                tmp,
                input_files=report.downloaded_file_paths,
                clip_count=6,
            )
        _pass("assembly_six_clip_count", manifest.get("clip_count") == 6)
        _pass("assembly_six_inputs", len(manifest.get("input_files") or []) == 6)


def test_publish_package_created_for_six_clips() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 6)
        final_video = tmp / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"assembled-six-clip-video")
        publish = run_publish_package(
            tmp,
            assembly_manifest={"status": ASSEMBLY_ASSEMBLED, "output_path": str(final_video)},
            run_id=report.content_brain_run_id,
            topic=report.content_brain_topic,
            clip_count=6,
            downloaded_file_paths=report.downloaded_file_paths,
        )
        _pass("publish_six_created", publish.get("status") == PUBLISH_CREATED)
        metadata_path = Path(str(publish.get("metadata_path") or ""))
        _pass("publish_six_metadata", metadata_path.is_file())
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            _pass("publish_six_metadata_clip_count", metadata.get("clip_count") == 6)


def test_results_ignores_stale_manifest_for_different_run_id() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        runtime = tmp / "project_brain/runtime_state"
        runtime.mkdir(parents=True, exist_ok=True)
        publish_dir = tmp / "outputs/publish/runway_phase_i"
        publish_dir.mkdir(parents=True, exist_ok=True)
        (publish_dir / "metadata.json").write_text(
            json.dumps({"run_id": "cb_cat_run", "clip_count": 2}, ensure_ascii=False),
            encoding="utf-8",
        )
        (runtime / "runway_phase_i_checkpoint.json").write_text(
            json.dumps({"run_id": "cb_cat_run", "clip_count": 2}, ensure_ascii=False),
            encoding="utf-8",
        )
        (runtime / "runway_phase_i_assembly_manifest.json").write_text(
            json.dumps({"status": ASSEMBLY_ASSEMBLED, "clip_count": 2}, ensure_ascii=False),
            encoding="utf-8",
        )
        (runtime / "runway_phase_i_publish_manifest.json").write_text(
            json.dumps({"status": PUBLISH_CREATED}, ensure_ascii=False),
            encoding="utf-8",
        )
        final_video = tmp / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"cat-video")

        report_path = tmp / "project_brain/runway_phase_i_3clip_last_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        grafig_clip = _make_clip(tmp / "downloads/grafig_clip_1.mp4", "grafig")
        report_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "simulate": False,
                    "clip_count": 6,
                    "content_brain_run_id": "cb_grafig_run",
                    "downloaded_file_paths": [grafig_clip],
                    "post_processing_status": "skipped",
                }
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        results = ProductStudioService(tmp).latest_results()
        _pass("stale_manifest_flag", results.get("stale_manifest_ignored") is True)
        _pass("stale_assembly_cleared", results.get("assembly_status") == "")
        _pass("stale_publish_cleared", results.get("publish_status") == "")
        _pass("stale_video_cleared", results.get("video_path") == "")
        _pass("post_processing_missing_flag", results.get("post_processing_missing") is True)


def test_results_ignores_stale_visual_continuity_for_different_run_id() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        runtime = tmp / "project_brain/runtime_state"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "visual_continuity_report.json").write_text(
            json.dumps(
                {
                    "run_id": "cb_cat_run",
                    "overall_pass": False,
                    "clips": [{"clip_index": 1, "pass": False, "score": 0}],
                }
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        clip_paths = [_make_clip(tmp / "downloads/clip_1.mp4", "one")]
        report_path = tmp / "project_brain/runway_phase_i_3clip_last_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "simulate": False,
                    "clip_count": 6,
                    "content_brain_run_id": "cb_latest_run",
                    "downloaded_file_paths": clip_paths,
                    "post_processing_status": "skipped",
                }
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        results = ProductStudioService(tmp).latest_results()

        continuity = results.get("visual_continuity_report") or {}
        _pass("visual_not_available_status", continuity.get("status") == "not_available_for_latest_run")
        _pass("visual_not_available_message", "not available" in str(continuity.get("message") or "").lower())
        _pass("visual_stale_clips_hidden", not continuity.get("clips"))


def test_existing_two_clip_post_processing_still_passes() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 2)
        unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
        with patch(
            "content_brain.execution.runway_live_post_processor.check_ffmpeg_availability",
            return_value=unavailable,
        ):
            result = run_live_post_processing(report, project_root=tmp)
        _pass("two_clip_enabled", result.get("enabled") is True)
        _pass("two_clip_plan_only", result.get("assembly_status") == ASSEMBLY_PLAN_ONLY)


def test_runway_automation_unchanged() -> None:
    smoke_source = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator_source = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("navigator_untouched", "collect_valid_download_paths" not in navigator_source)
    _pass("smoke_no_eligibility_rewrite", "collect_valid_download_paths" not in smoke_source)


def main() -> None:
    test_six_downloads_with_stale_counter_still_eligible()
    test_missing_file_blocks_post_processing()
    test_recovery_runs_post_processing_without_runway()
    test_assembly_handles_six_clips()
    test_publish_package_created_for_six_clips()
    test_results_ignores_stale_manifest_for_different_run_id()
    test_results_ignores_stale_visual_continuity_for_different_run_id()
    test_existing_two_clip_post_processing_still_passes()
    test_runway_automation_unchanged()
    print("All N-clip post-processing recovery validations passed.")


if __name__ == "__main__":
    main()
