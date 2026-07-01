"""Validate Video Quality Judge P1 — semantic story review."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.quality.video_learning_loop import LIVE_WEIGHTS_PATH, live_weights_snapshot
from content_brain.quality.video_quality_judge_p1 import (  # noqa: E402
    JUDGE_P1_VERSION,
    judge_and_persist_p1,
    judge_video_quality_p1,
    propose_p1_learning_updates,
    run_video_learning_loop_p1,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _semantic_context(**overrides: object) -> dict:
    base = {
        "run_id": "validate_vqj_p1",
        "run_dir": str(ROOT / "outputs" / "kling_frame_to_video" / "validate_vqj_p1"),
        "topic": "Young boy discovers a baby dragon in neon ruins",
        "clip_count": 4,
        "audio_strategy": "kling_native_audio",
        "preflight": {
            "kling_frame_to_video_plan": {
                "clip_count": 4,
                "story_progression": {
                    "validation_status": "PASS",
                    "chapters": [
                        {"clip_index": 1, "chapter_role": "hook", "conflict_level": 1},
                        {"clip_index": 2, "chapter_role": "escalation", "conflict_level": 2},
                        {"clip_index": 3, "chapter_role": "conflict", "conflict_level": 3},
                        {"clip_index": 4, "chapter_role": "resolution", "conflict_level": 1},
                    ],
                },
            },
            "kling_clip_prompts": [
                {
                    "clip_index": 1,
                    "prompt": "Chapter role: Hook. Character continuity: same boy and dragon. Dialogue: \"What is that glow?\"",
                },
                {
                    "clip_index": 2,
                    "prompt": "Continuing immediately from the previous bridge shot. Chapter role: Escalation. Do not repeat the previous clip's action.",
                },
            ],
        },
        "story_package": {
            "story_blueprint": {
                "hook": "A boy sees impossible light beneath the ruins.",
                "conflict": "The path collapses behind them.",
                "resolution": "They reach safety together.",
            }
        },
    }
    base.update(overrides)
    return base


def test_score_generation_works() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "deliverable.mp4"
        video.write_bytes(b"\x00" * 256)
        with patch(
            "content_brain.quality.video_quality_judge_p1.probe_has_audio_stream",
            return_value=True,
        ), patch(
            "content_brain.quality.video_quality_judge_p1.extract_semantic_review_frames",
            return_value=[],
        ):
            result = judge_video_quality_p1(
                video_path=video,
                run_id="validate_vqj_p1",
                context=_semantic_context(),
                prefer_openai=False,
            )
    _pass("overall_score", result.overall_score > 0, str(result.overall_score))
    _pass("version", result.version == JUDGE_P1_VERSION)


def test_categories_exist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "deliverable.mp4"
        video.write_bytes(b"\x00" * 128)
        with patch(
            "content_brain.quality.video_quality_judge_p1.probe_has_audio_stream",
            return_value=True,
        ), patch(
            "content_brain.quality.video_quality_judge_p1.extract_semantic_review_frames",
            return_value=[],
        ):
            result = judge_video_quality_p1(
                video_path=video,
                run_id="validate_vqj_p1",
                context=_semantic_context(),
                prefer_openai=False,
            )
    for field in (
        "story_score",
        "character_score",
        "dialogue_score",
        "visual_score",
        "audio_score",
        "continuity_score",
        "viral_score",
    ):
        value = getattr(result, field)
        _pass(f"category_{field}", isinstance(value, int) and 0 <= value <= 100, str(value))


def test_strengths_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "deliverable.mp4"
        video.write_bytes(b"\x00" * 128)
        with patch(
            "content_brain.quality.video_quality_judge_p1.probe_has_audio_stream",
            return_value=True,
        ), patch(
            "content_brain.quality.video_quality_judge_p1.extract_semantic_review_frames",
            return_value=[],
        ):
            result = judge_video_quality_p1(
                video_path=video,
                run_id="validate_vqj_p1",
                context=_semantic_context(),
                prefer_openai=False,
            )
    _pass("strengths_nonempty", len(result.strengths) > 0, str(len(result.strengths)))


def test_weaknesses_generated_when_weak() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "deliverable.mp4"
        video.write_bytes(b"\x00" * 128)
        with patch(
            "content_brain.quality.video_quality_judge_p1.probe_has_audio_stream",
            return_value=False,
        ), patch(
            "content_brain.quality.video_quality_judge_p1.extract_semantic_review_frames",
            return_value=[],
        ):
            result = judge_video_quality_p1(
                video_path=video,
                run_id="validate_vqj_p1_weak",
                context=_semantic_context(preflight={}),
                prefer_openai=False,
            )
    _pass("weaknesses_generated", len(result.weaknesses) > 0, str(result.weaknesses[:2]))


def test_improvement_actions_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "deliverable.mp4"
        video.write_bytes(b"\x00" * 128)
        with patch(
            "content_brain.quality.video_quality_judge_p1.probe_has_audio_stream",
            return_value=False,
        ), patch(
            "content_brain.quality.video_quality_judge_p1.extract_semantic_review_frames",
            return_value=[],
        ):
            result = judge_video_quality_p1(
                video_path=video,
                run_id="validate_vqj_p1_actions",
                context=_semantic_context(preflight={}),
                prefer_openai=False,
            )
    _pass("improvement_actions", len(result.improvement_actions) > 0)
    _pass("action_has_id", bool(result.improvement_actions[0].get("action_id")))


def test_learning_updates_proposed_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        judge = {
            "version": JUDGE_P1_VERSION,
            "run_id": "validate_vqj_p1_learning",
            "overall_score": 58,
            "improvement_actions": [
                {
                    "action_id": "increase_dialogue_emphasis",
                    "reason": "dialogue weak",
                    "target_score": "dialogue_score",
                    "current_score": 45,
                    "suggested_delta": {"dialogue_weight": 0.12},
                }
            ],
            "weaknesses": ["dialogue weak"],
            "strengths": [],
        }
        proposed = run_video_learning_loop_p1(judge, project_root=root, overall_threshold=70)
        out_path = Path(proposed["proposed_updates_path"])
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        _pass("proposed_file_written", out_path.is_file(), str(out_path))
        _pass("applied_false", payload.get("applied") is False)
        _pass("weights_mutated_false", payload.get("weights_mutated") is False)
        _pass("proposed_actions_present", len(payload.get("proposed_actions") or []) > 0)


def test_no_automatic_weight_mutation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        weights_path = root / LIVE_WEIGHTS_PATH
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        weights_path.write_text(json.dumps({"dialogue_weight": 0.5}), encoding="utf-8")
        before = live_weights_snapshot(root)
        judge = {
            "version": JUDGE_P1_VERSION,
            "run_id": "validate_vqj_p1_no_mutate",
            "overall_score": 50,
            "improvement_actions": [
                {
                    "action_id": "increase_emotional_arc",
                    "reason": "flat arc",
                    "target_score": "story_score",
                    "current_score": 40,
                    "suggested_delta": {"emotional_arc_weight": 0.12},
                }
            ],
            "weaknesses": ["flat arc"],
            "strengths": [],
        }
        run_video_learning_loop_p1(judge, project_root=root)
        after = live_weights_snapshot(root)
        _pass("weights_unchanged", before == after, json.dumps(after))


def test_persist_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        video = run_dir / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"\x00" * 64)
        with patch(
            "content_brain.quality.video_quality_judge_p1.probe_has_audio_stream",
            return_value=True,
        ), patch(
            "content_brain.quality.video_quality_judge_p1.extract_semantic_review_frames",
            return_value=[],
        ):
            payload = judge_and_persist_p1(
                video_path=video,
                run_id="persist_p1",
                context=_semantic_context(),
                project_root=root,
                run_dir=run_dir,
                prefer_openai=False,
            )
        out = run_dir / "quality" / "video_quality_judge_p1.json"
        _pass("persisted_file", out.is_file())
        _pass("persisted_overall", int(payload.get("overall_score") or 0) > 0)


def main() -> int:
    print("validate_video_judge_p1")
    test_score_generation_works()
    test_categories_exist()
    test_strengths_generated()
    test_weaknesses_generated_when_weak()
    test_improvement_actions_generated()
    test_learning_updates_proposed_only()
    test_no_automatic_weight_mutation()
    test_persist_roundtrip()
    print("All Video Judge P1 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
