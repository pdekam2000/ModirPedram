"""Validate AI Director V2 — shot library, planner, graph, rhythm, prompt integration."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.director.ai_director_v2_pipeline import apply_ai_director_v2
from content_brain.director.camera_language_engine import DIRECTOR_CAMERA_PLAN_MARKER, generate_camera_language_for_plan
from content_brain.director.shot_graph_engine import ShotGraphStore, build_shot_graph
from content_brain.director.shot_library import ALL_SHOT_TYPES, SHOT_LIBRARY, list_shots
from content_brain.director.shot_planner import has_duplicate_adjacent_shots, plan_shot_sequence
from content_brain.director.visual_rhythm_engine import score_visual_rhythm
from content_brain.director.visual_memory_injector import MEMORY_LOCK_MARKER
from content_brain.execution.runway_prompt_builder import RunwayPromptBuilder
from content_brain.execution.seamless_continuity_engine import CONTINUE_MARKER, EXACT_FRAME_MARKER
from content_brain.platform.results_run_loader import _resolve_ai_director_v2_report


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_shot_library_loads() -> None:
    shots = list_shots()
    _pass("shot_library_count", len(shots) >= 17, str(len(shots)))
    _pass("required_shot_types", all(key in SHOT_LIBRARY for key in ALL_SHOT_TYPES))
    sample = SHOT_LIBRARY["establishing_shot"]
    _pass("shot_has_purpose", bool(sample.purpose and sample.camera_behavior and sample.emotional_effect))


def test_shot_planner_generates_sequence() -> None:
    plan = plan_shot_sequence(clip_count=3, topic="Lion hunting on the savanna at dawn")
    _pass("planner_clip_count", len(plan.shots) == 3)
    _pass("clip1_establish", plan.shots[0].shot_type == "establishing_shot", plan.shots[0].shot_type)
    _pass("clip3_hero", plan.shots[2].shot_type in {"hero_shot", "reveal_shot"}, plan.shots[2].shot_type)


def test_no_duplicate_shot_spam() -> None:
    for count in (3, 4, 5, 6):
        plan = plan_shot_sequence(clip_count=count, topic="Wildlife documentary about scorpions")
        _pass(f"no_adjacent_dupes_{count}", not has_duplicate_adjacent_shots(plan))


def test_camera_language_generated() -> None:
    plan = plan_shot_sequence(clip_count=3, topic="RTX GPU benchmark thermal test")
    cameras = generate_camera_language_for_plan(shot_plan=plan, topic_category=plan.topic_category)
    _pass("camera_plan_count", len(cameras) == 3)
    _pass("camera_has_lens", all(bool(cam.lens) for cam in cameras))
    _pass("camera_block_marker", DIRECTOR_CAMERA_PLAN_MARKER in cameras[0].prompt_block())


def test_shot_graph_created() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        plan = plan_shot_sequence(clip_count=3, topic="Ancient empire documentary")
        cameras = generate_camera_language_for_plan(shot_plan=plan, topic_category=plan.topic_category)
        graph = build_shot_graph(run_id="run_graph", topic="history topic", shot_plan=plan, camera_plans=cameras)
        path = ShotGraphStore(tmp).save(graph)
        _pass("shot_graph_file", path.name == "shot_graph.json" and path.is_file())
        _pass("shot_graph_nodes", len(graph.nodes) == 3)


def test_rhythm_score_generated() -> None:
    plan = plan_shot_sequence(clip_count=3, topic="Orange cat exploring kitchen counters")
    cameras = generate_camera_language_for_plan(shot_plan=plan, topic_category=plan.topic_category)
    graph = build_shot_graph(run_id="run_rhythm", topic="cat", shot_plan=plan, camera_plans=cameras)
    rhythm = score_visual_rhythm(shot_plan=plan, camera_plans=cameras, pacing_curve=graph.pacing_curve)
    _pass("rhythm_score_range", 0 <= rhythm.rhythm_score <= 100, str(rhythm.rhythm_score))


def test_prompt_builder_receives_camera_plan() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        bundle = RunwayPromptBuilder().build(
            {
                "story_idea": "Wildlife documentary about a lion with scar above eye",
                "clip_count": 3,
                "auto_story_brief": True,
                "auto_prompt_critic": False,
                "run_id": "run_director_v2",
                "project_root": str(tmp),
            }
        )
        _pass("builder_director_report", bool(bundle.ai_director_v2_report))
        _pass("builder_camera_plan", all(DIRECTOR_CAMERA_PLAN_MARKER in prompt for prompt in bundle.clip_prompts))
        plan = (bundle.ai_director_v2_report or {}).get("shot_plan") or []
        _pass("builder_shot_plan", len(plan) == 3)


def test_results_receives_director_data() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        apply_ai_director_v2(
            clip_prompts=["clip one", "clip two", "clip three"],
            topic="Scorpion in desert night",
            clip_count=3,
            run_id="run_results",
            project_root=tmp,
        )
        report = _resolve_ai_director_v2_report(tmp, tmp / "missing", "run_results")
        _pass("results_shot_plan", bool(report.get("shot_plan")))
        _pass("results_rhythm", isinstance(report.get("rhythm_score"), int))


def test_visual_memory_unaffected() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        bundle = RunwayPromptBuilder().build(
            {
                "story_idea": "Black scorpion hunting at night",
                "clip_count": 3,
                "auto_story_brief": True,
                "auto_prompt_critic": False,
                "run_id": "run_memory_check",
                "project_root": str(tmp),
            }
        )
        _pass("memory_report_present", bool(bundle.visual_memory_report))
        _pass("memory_lock_preserved", all(MEMORY_LOCK_MARKER in prompt for prompt in bundle.clip_prompts))


def test_continuity_unaffected() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        bundle = RunwayPromptBuilder().build(
            {
                "story_idea": "Lion pride leader documentary",
                "clip_count": 3,
                "auto_story_brief": True,
                "auto_prompt_critic": False,
                "run_id": "run_continuity_check",
                "project_root": str(tmp),
            }
        )
        later = bundle.clip_prompts[1:]
        _pass("continue_marker", all(CONTINUE_MARKER in prompt for prompt in later))
        _pass("exact_frame_marker", all(EXACT_FRAME_MARKER in prompt for prompt in later))


def test_runway_automation_untouched() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("smoke_clean", "ai_director_v2" not in smoke and "shot_planner" not in smoke)
    _pass("navigator_clean", "shot_graph_engine" not in navigator)


def test_upload_untouched() -> None:
    upload_manager = (ROOT / "content_brain/upload/upload_manager.py").read_text(encoding="utf-8")
    _pass("upload_clean", "ai_director_v2" not in upload_manager and "shot_library" not in upload_manager)


def main() -> None:
    test_shot_library_loads()
    test_shot_planner_generates_sequence()
    test_no_duplicate_shot_spam()
    test_camera_language_generated()
    test_shot_graph_created()
    test_rhythm_score_generated()
    test_prompt_builder_receives_camera_plan()
    test_results_receives_director_data()
    test_visual_memory_unaffected()
    test_continuity_unaffected()
    test_runway_automation_untouched()
    test_upload_untouched()
    print("All AI Director V2 validations passed.")


if __name__ == "__main__":
    main()
