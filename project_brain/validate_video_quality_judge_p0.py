"""Validate Video Quality Judge P0 — rules-only, no LLM/provider/weight mutation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.quality.video_learning_loop import (
    LIVE_WEIGHTS_PATH,
    live_weights_snapshot,
    run_video_learning_loop,
)
from content_brain.quality.video_quality_judge import (
    JUDGE_VERSION,
    judge_and_persist,
    judge_video_quality,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _base_context(**overrides: object) -> dict:
    base = {
        "run_id": "validate_vqj_p0",
        "topic": "Ancient Rome secrets",
        "clip_count": 1,
        "story_package": {
            "story_blueprint": {
                "hook": "Nobody talks about this Roman vault.",
                "setup": "A historian opens a sealed archive.",
                "conflict": "The evidence contradicts the textbook.",
                "resolution": "The vault changes the timeline.",
            },
            "metadata": {
                "story_audio_audit": {"story_score": 82},
            },
        },
        "assembly_manifest": {"duration_seconds": 30.0, "clip_count": 1},
        "runtime_metadata": {"topic": "Ancient Rome secrets"},
        "publish_metadata": {"title": "Ancient Rome secrets"},
        "visual_continuity_report": {"overall_score": 88, "overall_pass": True},
        "audio_report": {"music_status_code": "completed"},
        "channel_profile": {"music_provider": "none", "audio_strategy": "kling_native_audio"},
        "audio_strategy": "kling_native_audio",
    }
    base.update(overrides)
    return base


def _mock_probes(
    *,
    duration: float = 30.0,
    has_audio: bool = True,
    has_video: bool = True,
    resolution: tuple[int, int] = (1080, 1920),
    mean_db: float = -28.0,
):
    return patch.multiple(
        "content_brain.quality.video_quality_judge",
        probe_duration_seconds=lambda _path: duration,
        probe_has_audio_stream=lambda _path: has_audio,
        probe_has_video_stream=lambda _path: has_video,
        probe_video_resolution=lambda _path: resolution if has_video else None,
        probe_mean_volume_db=lambda _path: mean_db if has_audio else None,
    )


def test_valid_mp4_with_metadata_gets_score() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "deliverable.mp4"
        video.write_bytes(b"\x00" * 128)
        with _mock_probes():
            result = judge_video_quality(video_path=video, run_id="validate_vqj_p0", context=_base_context())
    _pass("valid_mp4_overall_score", result.overall_score > 0, str(result.overall_score))
    _pass("valid_mp4_version", result.version == JUDGE_VERSION)


def test_missing_audio_lowers_audio_score() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "silent.mp4"
        video.write_bytes(b"\x00" * 64)
        with _mock_probes(has_audio=True, mean_db=-28.0):
            good = judge_video_quality(video_path=video, run_id="audio_good", context=_base_context())
        with _mock_probes(has_audio=False, mean_db=-80.0):
            bad = judge_video_quality(video_path=video, run_id="audio_bad", context=_base_context())
    _pass("missing_audio_lowers_score", bad.audio_score < good.audio_score, f"{bad.audio_score} < {good.audio_score}")


def test_truncated_duration_lowers_visual_story_score() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "truncated.mp4"
        video.write_bytes(b"\x00" * 64)
        context = _base_context(assembly_manifest={"duration_seconds": 30.0, "clip_count": 1})
        with _mock_probes(duration=30.0):
            full = judge_video_quality(video_path=video, run_id="full", context=context)
        with _mock_probes(duration=10.0):
            truncated = judge_video_quality(video_path=video, run_id="truncated", context=context)
    _pass(
        "truncated_lowers_visual",
        truncated.visual_score < full.visual_score,
        f"{truncated.visual_score} < {full.visual_score}",
    )
    _pass(
        "truncated_lowers_story",
        truncated.story_score < full.story_score,
        f"{truncated.story_score} < {full.story_score}",
    )


def test_missing_story_package_lowers_story_score() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "nostory.mp4"
        video.write_bytes(b"\x00" * 64)
        with _mock_probes():
            with_story = judge_video_quality(video_path=video, run_id="with_story", context=_base_context())
            without_story = judge_video_quality(
                video_path=video,
                run_id="without_story",
                context=_base_context(story_package={}),
            )
    _pass(
        "missing_story_lowers_score",
        without_story.story_score < with_story.story_score,
        f"{without_story.story_score} < {with_story.story_score}",
    )


def test_continuity_report_improves_continuity_score() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "continuity.mp4"
        video.write_bytes(b"\x00" * 64)
        with _mock_probes():
            with_report = judge_video_quality(
                video_path=video,
                run_id="with_continuity",
                context=_base_context(clip_count=2, visual_continuity_report={"overall_score": 90, "overall_pass": True}),
            )
            without_report = judge_video_quality(
                video_path=video,
                run_id="without_continuity",
                context=_base_context(clip_count=2, visual_continuity_report={}),
            )
    _pass(
        "continuity_report_improves_score",
        with_report.continuity_score > without_report.continuity_score,
        f"{with_report.continuity_score} > {without_report.continuity_score}",
    )


def test_improvement_actions_generated_for_weak_areas() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "weak.mp4"
        video.write_bytes(b"\x00" * 64)
        context = _base_context(
            clip_count=2,
            visual_continuity_report={},
            story_package={},
            assembly_manifest={"duration_seconds": 30.0, "clip_count": 2},
        )
        with _mock_probes(has_audio=False, duration=10.0):
            result = judge_video_quality(video_path=video, run_id="weak_run", context=context)
    _pass("improvement_actions_present", bool(result.improvement_actions))
    _pass("weaknesses_present", bool(result.weaknesses))


def test_learning_loop_produces_proposed_update_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        video = root / "deliverable.mp4"
        video.write_bytes(b"\x00" * 64)
        with _mock_probes(has_audio=False, duration=10.0):
            judge = judge_video_quality(
                video_path=video,
                run_id="learning_run",
                context=_base_context(story_package={}, clip_count=2, visual_continuity_report={}),
            )
        proposed = run_video_learning_loop(judge.to_dict(), project_root=root, overall_threshold=90)
        out_path = Path(proposed["proposed_updates_path"])
        _pass("learning_loop_file_created", out_path.is_file(), str(out_path))
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        _pass("learning_loop_not_applied", payload.get("applied") is False)
        _pass("learning_loop_has_deltas", isinstance(payload.get("aggregated_deltas"), dict))


def test_does_not_call_llm() -> None:
    source = (ROOT / "content_brain/quality/video_quality_judge.py").read_text(encoding="utf-8")
    learning_source = (ROOT / "content_brain/quality/video_learning_loop.py").read_text(encoding="utf-8")
    banned = ("openai", "anthropic", "llm", "chat.completions", "generate_content")
    for token in banned:
        _pass(f"judge_no_{token}", token not in source.lower())
        _pass(f"learning_no_{token}", token not in learning_source.lower())


def test_does_not_call_provider() -> None:
    source = (ROOT / "content_brain/quality/video_quality_judge.py").read_text(encoding="utf-8")
    learning_source = (ROOT / "content_brain/quality/video_learning_loop.py").read_text(encoding="utf-8")
    banned = ("runway_live", "product_studio_service", "provider.generate", "requests.post", "credits")
    for token in banned:
        _pass(f"judge_no_provider_{token}", token not in source.lower())
        _pass(f"learning_no_provider_{token}", token not in learning_source.lower())


def test_does_not_mutate_live_weights() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        live_path = root / LIVE_WEIGHTS_PATH
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(json.dumps({"dialogue_weight": 0.5}), encoding="utf-8")
        before = live_weights_snapshot(root)
        judge = {
            "version": JUDGE_VERSION,
            "run_id": "no_mutation_run",
            "overall_score": 40,
            "improvement_actions": [
                {
                    "action_id": "boost_dialogue_emphasis",
                    "reason": "weak audio",
                    "target_score": "audio_score",
                    "current_score": 30,
                    "suggested_delta": {"dialogue_weight": 0.15},
                }
            ],
            "strengths": [],
            "weaknesses": ["missing audio stream"],
        }
        run_video_learning_loop(judge, project_root=root)
        after = live_weights_snapshot(root)
    _pass("live_weights_unchanged", before == after)


def test_persistence_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "outputs" / "kling_multishot_live" / "persist_run"
        run_dir.mkdir(parents=True)
        video = run_dir / "final.mp4"
        video.write_bytes(b"\x00" * 64)
        with _mock_probes():
            payload = judge_and_persist(
                video_path=video,
                run_id="persist_run",
                context=_base_context(),
                project_root=root,
                run_dir=run_dir,
            )
        run_output = run_dir / "quality" / "video_quality_judge.json"
        latest_output = root / "project_brain" / "quality_judge" / "latest_video_quality_judge.json"
        _pass("run_quality_json_written", run_output.is_file())
        _pass("latest_quality_json_written", latest_output.is_file())
        _pass("persisted_run_id", json.loads(run_output.read_text(encoding="utf-8")).get("run_id") == "persist_run")
        _pass("persisted_overall_score", payload.get("overall_score", 0) > 0)


def main() -> None:
    test_valid_mp4_with_metadata_gets_score()
    test_missing_audio_lowers_audio_score()
    test_truncated_duration_lowers_visual_story_score()
    test_missing_story_package_lowers_story_score()
    test_continuity_report_improves_continuity_score()
    test_improvement_actions_generated_for_weak_areas()
    test_learning_loop_produces_proposed_update_file()
    test_does_not_call_llm()
    test_does_not_call_provider()
    test_does_not_mutate_live_weights()
    test_persistence_paths()
    print("validate_video_quality_judge_p0: all checks passed")


if __name__ == "__main__":
    main()
