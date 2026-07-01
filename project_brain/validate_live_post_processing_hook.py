"""Validate live post-processing hook after successful Runway runs."""

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
    PUBLISH_SKIPPED_PLAN_ONLY,
    evaluate_post_processing_eligibility,
    run_assembly,
    run_live_post_processing,
    run_publish_package,
)
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


def _fake_report(tmp: Path, clip_count: int, *, simulate: bool = False, missing: int | None = None) -> FakeReport:
    paths: list[str] = []
    for index in range(1, clip_count + 1):
        if missing is not None and index == missing:
            continue
        paths.append(_make_clip(tmp / "downloads" / f"clip_{index}.mp4", f"clip_{index}"))
    return FakeReport(
        ok=True,
        simulate=simulate,
        clip_count=clip_count,
        clips_completed=clip_count,
        total_downloads_completed=len(paths),
        downloaded_file_paths=paths,
        content_brain_run_id=f"cb_hook_{clip_count}",
        content_brain_topic=f"topic_{clip_count}",
    )


def test_assembly_hook_runs_for_clip_counts() -> None:
    for clip_count in (1, 2, 3):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            report = _fake_report(tmp, clip_count)
            unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
            with patch(
                "content_brain.execution.runway_live_post_processor.check_ffmpeg_availability",
                return_value=unavailable,
            ):
                result = run_live_post_processing(report, project_root=tmp)
            _pass(f"hook_runs_{clip_count}_clip", result.get("enabled") is True, str(result.get("status")))
            _pass(f"assembly_manifest_{clip_count}", (tmp / "project_brain/runtime_state/runway_phase_i_assembly_manifest.json").is_file())
            _pass(f"checkpoint_{clip_count}", (tmp / "project_brain/runtime_state/runway_phase_i_checkpoint.json").is_file())


def test_missing_file_blocked_safely() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 2)
        missing_path = Path(report.downloaded_file_paths[1])
        missing_path.unlink()
        result = run_live_post_processing(report, project_root=tmp)
        _pass("missing_file_skipped", result.get("enabled") is False)
        _pass("missing_file_reason", "missing" in str(result.get("reason")))


def test_simulate_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 1, simulate=True)
        result = run_live_post_processing(report, project_root=tmp)
        _pass("simulate_skipped", result.get("status") == "skipped")
        _pass("simulate_no_checkpoint", not (tmp / "project_brain/runtime_state/runway_phase_i_checkpoint.json").exists())


def test_ffmpeg_missing_plan_only() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        report = _fake_report(tmp, 2)
        unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
        with patch(
            "content_brain.execution.runway_live_post_processor.check_ffmpeg_availability",
            return_value=unavailable,
        ):
            result = run_live_post_processing(report, project_root=tmp)
        _pass("plan_only_status", result.get("assembly_status") == ASSEMBLY_PLAN_ONLY)
        manifest = json.loads((tmp / "project_brain/runtime_state/runway_phase_i_assembly_manifest.json").read_text(encoding="utf-8"))
        _pass("manifest_plan_only", manifest.get("status") == ASSEMBLY_PLAN_ONLY)


def test_publish_only_after_assembled() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        clip = _make_clip(tmp / "clip.mp4", "single")
        plan_only = run_publish_package(
            tmp,
            assembly_manifest={"status": ASSEMBLY_PLAN_ONLY, "output_path": str(tmp / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4")},
            run_id="cb_plan_only",
            topic="topic",
            clip_count=1,
            downloaded_file_paths=[clip],
        )
        _pass("publish_skipped_plan_only", plan_only.get("status") == PUBLISH_SKIPPED_PLAN_ONLY)

        final_video = tmp / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"assembled-video")
        assembled = run_publish_package(
            tmp,
            assembly_manifest={"status": ASSEMBLY_ASSEMBLED, "output_path": str(final_video)},
            run_id="cb_assembled",
            topic="topic",
            clip_count=1,
            downloaded_file_paths=[clip],
        )
        _pass("publish_created_after_assembled", assembled.get("status") == PUBLISH_CREATED)
        _pass("publish_folder_exists", (tmp / "outputs/publish/runway_phase_i").is_dir())


def test_checkpoint_run_id_and_stale_overwrite() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        stale_path = tmp / "project_brain/runtime_state/runway_phase_i_checkpoint.json"
        stale_path.parent.mkdir(parents=True, exist_ok=True)
        stale_path.write_text(
            json.dumps({"simulate": True, "run_id": "stale_sim", "checkpoint": "run_completed"}),
            encoding="utf-8",
        )

        report = _fake_report(tmp, 1)
        unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
        with patch(
            "content_brain.execution.runway_live_post_processor.check_ffmpeg_availability",
            return_value=unavailable,
        ):
            run_live_post_processing(report, project_root=tmp)

        checkpoint = json.loads(stale_path.read_text(encoding="utf-8"))
        _pass("stale_overwritten", checkpoint.get("simulate") is False)
        _pass("checkpoint_run_id", checkpoint.get("run_id") == "cb_hook_1")
        _pass("checkpoint_publish_stage", checkpoint.get("checkpoint") == "publish_completed")


def test_product_results_reads_manifests() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        runtime = tmp / "project_brain/runtime_state"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "runway_phase_i_assembly_manifest.json").write_text(
            json.dumps({"status": ASSEMBLY_PLAN_ONLY}),
            encoding="utf-8",
        )
        (runtime / "runway_phase_i_publish_manifest.json").write_text(
            json.dumps({"status": PUBLISH_SKIPPED_PLAN_ONLY}),
            encoding="utf-8",
        )
        report_path = tmp / "project_brain/runway_live_smoke_last_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "simulate": False,
                    "downloaded_file_paths": [str(tmp / "clip.mp4")],
                }
            ),
            encoding="utf-8",
        )
        service = ProductStudioService(tmp)
        results = service.latest_results()
        _pass("results_assembly_status", results.get("assembly_status") == ASSEMBLY_PLAN_ONLY)
        _pass("results_publish_status", results.get("publish_status") == PUBLISH_SKIPPED_PLAN_ONLY)
        _pass("results_has_downloads_only", results.get("has_downloads_only") is True)


def test_runway_automation_unchanged() -> None:
    smoke_source = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator_source = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("hook_only_addition", "run_live_post_processing" in smoke_source)
    _pass("navigator_untouched_by_hook", "run_live_post_processing" not in navigator_source)
    eligible, reason, _ = evaluate_post_processing_eligibility({"ok": True, "simulate": True, "clip_count": 1})
    _pass("eligibility_guard", eligible is False and reason == "simulate_skipped")


def test_dynamic_clip_count_not_hardcoded_three() -> None:
    source = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8")
    _pass("no_three_clips_gate", "three_clips" not in source)
    _pass("uses_downloaded_file_paths", "downloaded_file_paths" in source)


def main() -> None:
    print("=== Live Post-Processing Hook Validation ===")
    test_assembly_hook_runs_for_clip_counts()
    test_missing_file_blocked_safely()
    test_simulate_skipped()
    test_ffmpeg_missing_plan_only()
    test_publish_only_after_assembled()
    test_checkpoint_run_id_and_stale_overwrite()
    test_product_results_reads_manifests()
    test_runway_automation_unchanged()
    test_dynamic_clip_count_not_hardcoded_three()
    print("ALL PASS")


if __name__ == "__main__":
    main()
