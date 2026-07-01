"""Validate Video Quality Judge P0 wiring into post-processing and Results page."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_product_run import kling_run_dir
from content_brain.platform.results_run_loader import load_run_results
from content_brain.quality.video_learning_loop import LIVE_WEIGHTS_PATH, live_weights_snapshot
from content_brain.quality.video_quality_judge import (
    JUDGE_VERSION,
    run_post_processing_quality_pipeline,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_probes(**kwargs: object):
    defaults = {
        "duration": 30.0,
        "has_audio": True,
        "has_video": True,
        "resolution": (1080, 1920),
        "mean_db": -28.0,
    }
    defaults.update(kwargs)
    return patch.multiple(
        "content_brain.quality.video_quality_judge",
        probe_duration_seconds=lambda _path: defaults["duration"],
        probe_has_audio_stream=lambda _path: defaults["has_audio"],
        probe_has_video_stream=lambda _path: defaults["has_video"],
        probe_video_resolution=lambda _path: defaults["resolution"] if defaults["has_video"] else None,
        probe_mean_volume_db=lambda _path: defaults["mean_db"] if defaults["has_audio"] else None,
    )


def _write_runway_run(root: Path, run_id: str) -> tuple[Path, Path]:
    run_dir = root / "outputs" / "runs" / run_id
    (run_dir / "metadata").mkdir(parents=True)
    (run_dir / "publish").mkdir(parents=True)
    (run_dir / "quality").mkdir(parents=True, exist_ok=True)
    video = run_dir / "publish" / "FINAL_BRANDED.mp4"
    video.write_bytes(b"\x00" * 128)
    (run_dir / "metadata" / "run_summary.json").write_text(
        json.dumps({"run_id": run_id, "topic": "Runway wiring test"}),
        encoding="utf-8",
    )
    (run_dir / "metadata" / "assembly_manifest.json").write_text(
        json.dumps({"run_id": run_id, "duration_seconds": 30.0, "clip_count": 2, "status": "ASSEMBLED"}),
        encoding="utf-8",
    )
    (run_dir / "metadata" / "visual_continuity_report.json").write_text(
        json.dumps({"run_id": run_id, "overall_score": 88, "overall_pass": True}),
        encoding="utf-8",
    )
    (run_dir / "metadata" / "delivery_quality_gate.json").write_text(
        json.dumps({"run_id": run_id, "delivery_status": "PASS", "canonical_video_path": str(video)}),
        encoding="utf-8",
    )
    (root / "project_brain" / "runtime_state").mkdir(parents=True, exist_ok=True)
    (root / "project_brain" / "runtime_state" / "runs_index.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "run_id": run_id,
                        "run_dir": str(run_dir),
                        "topic": "Runway wiring test",
                        "created_at": "2026-06-16T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return run_dir, video


def _write_kling_run(root: Path, run_id: str) -> tuple[Path, Path]:
    run_dir = kling_run_dir(root, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    video = run_dir / "video.mp4"
    video.write_bytes(b"\x00" * 128)
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "topic": "Kling wiring test",
                "clip_count": 2,
                "audio_strategy": "kling_native_audio",
                "provider": "kling_3_0_pro_native_audio",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "preflight.json").write_text(
        json.dumps({"authoritative_topic": "Kling wiring test", "kling_clip_count": 2}),
        encoding="utf-8",
    )
    return run_dir, video


def test_kling_output_triggers_judge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "kling_ms_wiring_test"
        run_dir, video = _write_kling_run(root, run_id)
        with _mock_probes():
            pipeline = run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
                topic="Kling wiring test",
                clip_count=2,
                audio_strategy="kling_native_audio",
            )
        _pass("kling_pipeline_not_skipped", not pipeline.get("skipped"))
        _pass("kling_judge_version", pipeline.get("judge", {}).get("version") == JUDGE_VERSION)


def test_runway_output_triggers_judge() -> None:
    source = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8")
    _pass("runway_wires_quality_pipeline", "run_post_processing_quality_pipeline" in source)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "runway_wiring_test"
        run_dir, video = _write_runway_run(root, run_id)
        with _mock_probes():
            pipeline = run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
                topic="Runway wiring test",
                clip_count=2,
            )
        _pass("runway_pipeline_not_skipped", not pipeline.get("skipped"))
        _pass("runway_judge_has_overall", isinstance(pipeline.get("judge", {}).get("overall_score"), int))


def test_judge_result_saved_in_run_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "save_run_dir_test"
        run_dir, video = _write_kling_run(root, run_id)
        with _mock_probes():
            run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
            )
        out_path = run_dir / "quality" / "video_quality_judge.json"
        _pass("run_dir_quality_json", out_path.is_file(), str(out_path))


def test_latest_judge_result_updated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "latest_judge_test"
        run_dir, video = _write_kling_run(root, run_id)
        with _mock_probes():
            run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
            )
        latest = root / "project_brain" / "quality_judge" / "latest_video_quality_judge.json"
        payload = json.loads(latest.read_text(encoding="utf-8"))
        _pass("latest_judge_exists", latest.is_file())
        _pass("latest_judge_run_id", payload.get("run_id") == run_id)


def test_learning_proposed_file_created() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "learning_proposed_test"
        run_dir, video = _write_kling_run(root, run_id)
        with _mock_probes(has_audio=False, duration=10.0):
            pipeline = run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
                context_overrides={"story_package": {}, "clip_count": 2, "visual_continuity_report": {}},
            )
        proposed_path = Path(pipeline.get("proposed_updates_path") or "")
        _pass("learning_proposed_file", proposed_path.is_file(), str(proposed_path))


def test_learning_not_applied_automatically() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        live_path = root / LIVE_WEIGHTS_PATH
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(json.dumps({"dialogue_weight": 0.4}), encoding="utf-8")
        before = live_weights_snapshot(root)
        run_id = "learning_not_applied_test"
        run_dir, video = _write_kling_run(root, run_id)
        with _mock_probes(has_audio=False):
            pipeline = run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
            )
        after = live_weights_snapshot(root)
        learning = pipeline.get("learning") or {}
        _pass("learning_applied_false", learning.get("applied") is False)
        _pass("live_weights_not_mutated", before == after)


def test_results_page_displays_scores() -> None:
    page = (ROOT / "ui/web/src/pages/ResultsPage.tsx").read_text(encoding="utf-8")
    _pass("results_section_title", "Video Quality Judge" in page)
    _pass("results_overall_score", "overall_score" in page)
    _pass("results_story_score", "story_score" in page)
    _pass("results_learning_proposed", "Learning proposed" in page)


def test_results_page_missing_judge_graceful() -> None:
    page = (ROOT / "ui/web/src/pages/ResultsPage.tsx").read_text(encoding="utf-8")
    _pass("results_missing_message", "Quality Judge not run yet" in page)
    loader = (ROOT / "content_brain/platform/results_run_loader.py").read_text(encoding="utf-8")
    _pass("loader_exposes_video_quality_judge", "video_quality_judge" in loader)


def test_results_loader_includes_judge_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "loader_judge_test"
        run_dir, video = _write_runway_run(root, run_id)
        with _mock_probes():
            run_post_processing_quality_pipeline(
                project_root=root,
                run_dir=run_dir,
                run_id=run_id,
                video_path=video,
            )
        results = load_run_results(root, run_id=run_id, run_dir=str(run_dir))
        judge = dict(results.get("video_quality_judge") or {})
        _pass("loader_judge_version", judge.get("version") == JUDGE_VERSION)
        _pass("loader_learning_flag", isinstance(results.get("video_quality_learning_proposed"), bool))


def test_does_not_call_llm() -> None:
    files = [
        ROOT / "content_brain/execution/runway_live_post_processor.py",
        ROOT / "content_brain/execution/kling_product_run.py",
        ROOT / "content_brain/platform/results_run_loader.py",
        ROOT / "ui/api/product_studio_service.py",
    ]
    banned = ("openai", "anthropic", "chat.completions", "generate_content")
    for path in files:
        source = path.read_text(encoding="utf-8").lower()
        for token in banned:
            _pass(f"no_llm_{path.name}_{token}", token not in source)


def test_does_not_call_provider() -> None:
    judge_source = (ROOT / "content_brain/quality/video_quality_judge.py").read_text(encoding="utf-8").lower()
    runway_source = (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8").lower()
    kling_source = (ROOT / "content_brain/execution/kling_product_run.py").read_text(encoding="utf-8").lower()
    banned = ("requests.post", "product_studio_service", "provider.generate", "credits")
    for token in banned:
        _pass(f"judge_wiring_no_provider_{token}", token not in judge_source)
    _pass(
        "runway_quality_block_present",
        "run_post_processing_quality_pipeline" in runway_source and "evaluate_delivery_quality" in runway_source,
    )
    _pass(
        "kling_quality_block_present",
        "run_post_processing_quality_pipeline" in kling_source and "_execute_kling_clips" in kling_source,
    )


def test_kling_product_run_wires_pipeline() -> None:
    source = (ROOT / "content_brain/execution/kling_product_run.py").read_text(encoding="utf-8")
    _pass("kling_wires_quality_pipeline", "run_post_processing_quality_pipeline" in source)


def main() -> None:
    test_kling_output_triggers_judge()
    test_runway_output_triggers_judge()
    test_judge_result_saved_in_run_dir()
    test_latest_judge_result_updated()
    test_learning_proposed_file_created()
    test_learning_not_applied_automatically()
    test_results_page_displays_scores()
    test_results_page_missing_judge_graceful()
    test_results_loader_includes_judge_payload()
    test_does_not_call_llm()
    test_does_not_call_provider()
    test_kling_product_run_wires_pipeline()
    print("validate_video_quality_judge_p0_wiring: all checks passed")


if __name__ == "__main__":
    main()
