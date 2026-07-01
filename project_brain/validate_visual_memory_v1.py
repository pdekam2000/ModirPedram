"""Validate visual memory runtime v1 — store, inject, recall, continuity, scoring."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.director.consistency_score_engine import score_visual_consistency
from content_brain.director.scene_recall_engine import SceneRecallStore, generate_scene_recall_packages
from content_brain.director.subject_memory_extractor import extract_subject_memory
from content_brain.director.visual_memory_injector import MEMORY_LOCK_MARKER, apply_visual_memory_injection
from content_brain.director.visual_memory_pipeline import apply_visual_memory_pipeline
from content_brain.director.visual_memory_store import VisualMemoryStore
from content_brain.execution.runway_prompt_builder import RunwayPromptBuilder
from content_brain.execution.runway_story_brief_builder import RunwayStoryBriefBuilder, StoryBriefInput
from content_brain.execution.seamless_continuity_engine import CONTINUE_MARKER, ENGINE_VERSION, EXACT_FRAME_MARKER
from content_brain.platform.results_run_loader import _resolve_visual_memory_report


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_memory_profile_created() -> None:
    memory = extract_subject_memory(run_id="run_lion", topic="A male lion hunts at dawn on the savanna")
    _pass("memory_subject", "lion" in memory.subject_name.lower(), memory.subject_name)
    _pass("memory_markings", bool(memory.markings or memory.fur_color))


def test_memory_stored_to_disk() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        memory = extract_subject_memory(run_id="run_scorpion", topic="Black scorpion crawling at night")
        store = VisualMemoryStore(tmp)
        path = store.save(memory)
        _pass("memory_file_written", path.is_file())


def test_memory_loaded_correctly() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        memory = extract_subject_memory(run_id="run_gpu", topic="RTX graphics card thermal performance test")
        store = VisualMemoryStore(tmp)
        store.save(memory)
        loaded = store.load("run_gpu")
        _pass("memory_loaded", loaded is not None)
        _pass("memory_gpu_subject", loaded is not None and ("rtx" in loaded.subject_name.lower() or "gpu" in loaded.subject_name.lower()), loaded.subject_name if loaded else "")


def test_clip_two_receives_memory_injection() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result = apply_visual_memory_pipeline(
            clip_prompts=["clip one base", "clip two base"],
            topic="Orange tabby cat exploring a kitchen",
            run_id="run_cat",
            project_root=tmp,
        )
        _pass("clip2_memory_lock", MEMORY_LOCK_MARKER in result.clip_prompts[1])


def test_clip_three_receives_memory_injection() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result = apply_visual_memory_pipeline(
            clip_prompts=["clip one", "clip two", "clip three"],
            topic="Lion pride leader with scar above eye",
            run_id="run_lion_3",
            project_root=tmp,
        )
        _pass("clip3_memory_lock", MEMORY_LOCK_MARKER in result.clip_prompts[2])
        _pass("clip3_continue", CONTINUE_MARKER in result.clip_prompts[2])


def test_scene_recall_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        packages = generate_scene_recall_packages(run_id="run_recall", clip_count=3, environment="savanna")
        manifest = SceneRecallStore(tmp).save_packages(packages)
        _pass("recall_manifest", manifest.is_file())
        loaded = SceneRecallStore(tmp).load_packages("run_recall")
        _pass("recall_packages", len(loaded) == 3)


def test_continuity_upgrade_active() -> None:
    _pass("continuity_engine_v2", ENGINE_VERSION == "seamless_continuity_engine_v2")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result = apply_visual_memory_pipeline(
            clip_prompts=["a", "b"],
            topic="Scorpion in desert sand",
            run_id="run_cont",
            project_root=tmp,
        )
        _pass("exact_frame_marker", EXACT_FRAME_MARKER in result.clip_prompts[1])


def test_consistency_score_generated() -> None:
    memory = extract_subject_memory(run_id="run_score", topic="Lion with dark mane on savanna")
    injection = apply_visual_memory_injection(
        clip_prompts=["prompt one", "prompt two"],
        memory=memory,
    )
    score = score_visual_consistency(memory=memory, clip_prompts=injection.clip_prompts)
    _pass("consistency_score_range", 0 <= score.visual_consistency_score <= 100, str(score.visual_consistency_score))
    _pass("consistency_metrics", score.subject_consistency > 0)


def test_results_panel_receives_score() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result = apply_visual_memory_pipeline(
            clip_prompts=["one", "two", "three"],
            topic="RTX GPU stress test benchmark",
            run_id="run_panel",
            project_root=tmp,
        )
        panel = result.results_panel
        _pass("panel_subject", bool(panel.get("subject")))
        _pass("panel_score", isinstance(panel.get("consistency_score"), int))
        _pass("panel_memory_status", panel.get("visual_memory_status") == "PASS")


def test_prompt_builder_integration() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        bundle = RunwayPromptBuilder().build(
            {
                "story_idea": "Documentary about a lion with scar above eye hunting at dawn",
                "clip_count": 3,
                "auto_story_brief": True,
                "auto_prompt_critic": False,
                "run_id": "run_builder",
                "project_root": str(tmp),
            }
        )
        _pass("builder_memory_report", bool(bundle.visual_memory_report))
        _pass("builder_memory_subject", "lion" in str((bundle.visual_memory_report or {}).get("subject", "")).lower())


def test_results_loader_exposes_visual_memory() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        apply_visual_memory_pipeline(
            clip_prompts=["one", "two"],
            topic="Scorpion hunting at night",
            run_id="run_loader",
            project_root=tmp,
        )
        report_path = tmp / "project_brain" / "runtime_state" / "visual_memory_report_run_loader.json"
        _pass("runtime_report_exists", report_path.is_file())
        from content_brain.platform.results_run_loader import _resolve_visual_memory_report

        memory = _resolve_visual_memory_report(tmp, tmp / "outputs" / "runs" / "missing", "run_loader")
        _pass("results_loader_memory", memory.get("visual_memory_status") == "PASS", str(memory.get("subject")))


def test_runway_automation_untouched() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("smoke_no_visual_memory", "visual_memory_store" not in smoke)
    _pass("navigator_no_visual_memory", "visual_memory_injector" not in navigator)


def test_upload_pipeline_untouched() -> None:
    upload_manager = (ROOT / "content_brain/upload/upload_manager.py").read_text(encoding="utf-8")
    package_builder = (ROOT / "content_brain/upload/upload_package_builder.py").read_text(encoding="utf-8")
    _pass("upload_manager_clean", "visual_memory" not in upload_manager)
    _pass("upload_package_clean", "visual_memory" not in package_builder)


def test_branding_pipeline_untouched() -> None:
    branding = (ROOT / "content_brain/branding/branding_runtime.py").read_text(encoding="utf-8")
    music = (ROOT / "content_brain/audio/music_runtime.py").read_text(encoding="utf-8")
    _pass("branding_runtime_clean", "visual_memory" not in branding)
    _pass("music_runtime_clean", "visual_memory" not in music)


def main() -> None:
    test_memory_profile_created()
    test_memory_stored_to_disk()
    test_memory_loaded_correctly()
    test_clip_two_receives_memory_injection()
    test_clip_three_receives_memory_injection()
    test_scene_recall_generated()
    test_continuity_upgrade_active()
    test_consistency_score_generated()
    test_results_panel_receives_score()
    test_prompt_builder_integration()
    test_results_loader_exposes_visual_memory()
    test_runway_automation_untouched()
    test_upload_pipeline_untouched()
    test_branding_pipeline_untouched()
    print("All visual memory v1 validations passed.")


if __name__ == "__main__":
    main()
