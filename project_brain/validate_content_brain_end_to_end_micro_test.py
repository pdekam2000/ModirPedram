"""
Validate Content Brain End-to-End Micro Test Studio wiring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_e2e_micro_test_studio import (
    ContentBrainE2EMicroTestStudio,
    DEFAULT_EXPORT_DIR,
    run_content_brain_e2e_micro_test,
)
from content_brain.execution.content_brain_topic_authority import (
    audit_story_brief_preservation,
    audit_topic_preservation,
    extract_topic_facets,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _unit_topic_preservation() -> None:
    subject, env, action = extract_topic_facets("old man walking on a beach")
    _pass("extract_subject", "man" in subject or "old" in subject, subject)
    _pass("extract_environment", "beach" in env, env)
    _pass("extract_action", action in {"walking", "walk"}, action)
    audit = audit_topic_preservation("old man walking on a beach")
    _pass("preservation_score", audit.topic_preservation_score >= 0.8, str(audit.topic_preservation_score))
    drift = audit_story_brief_preservation(
        "old man walking on a beach",
        {
            "title": "The Old Fisherman",
            "logline": "An elderly man walks along a quiet shoreline at dusk.",
            "main_character": "elderly man",
            "setting": "beach shoreline",
            "clip_beats": ["He steps into frame on the sand."],
        },
    )
    _pass("no_astronaut_drift", "astronaut" not in drift.forbidden_drift_detected)


def _unit_zander_fishing_topic() -> None:
    payload = run_content_brain_e2e_micro_test(
        topic="zander fishing method",
        duration_seconds=30,
        platform="youtube_shorts",
        niche="general",
        mood="emotional",
    )
    _pass("zander_pipeline_completed", payload.get("status") == "completed")
    strategy_step = next(
        step for step in payload.get("steps") or [] if step.get("step_key") == "topic_classification"
    )
    classification = (strategy_step.get("payload") or {}).get("classification") or {}
    _pass("zander_category_fishing", classification.get("topic_category") == "fishing", str(classification))
    _pass(
        "zander_strategy_instructional",
        (strategy_step.get("payload") or {}).get("content_strategy", {}).get("strategy_id") == "instructional_fishing",
        str((strategy_step.get("payload") or {}).get("content_strategy")),
    )
    story_step = next(
        step for step in payload.get("steps") or [] if step.get("step_key") == "story_generation"
    )
    story = (story_step.get("payload") or {}).get("story") or {}
    beats = " ".join(str(b) for b in story.get("clip_beats") or []).lower()
    combined = " ".join(
        [
            str(story.get("title") or ""),
            str(story.get("logline") or ""),
            str(story.get("main_character") or ""),
            str(story.get("setting") or ""),
            beats,
        ]
    ).lower()
    _pass("zander_topic_in_story", "zander" in combined or "fish" in combined, combined[:120])
    technique_terms = ("lure", "cast", "hook", "depth", "strike", "technique", "retrieve", "tackle", "setup")
    technique_hits = sum(1 for term in technique_terms if term in beats)
    _pass("zander_technique_beats", technique_hits >= 2, beats[:180])
    filler_terms = ("emotional journey", "staring at the horizon", "walking on the shore", "contemplation")
    _pass("zander_no_generic_filler", not any(term in combined for term in filler_terms), combined[:120])
    seo_step = next(
        step for step in payload.get("steps") or [] if step.get("step_key") == "seo_generation"
    )
    seo_title = str((seo_step.get("payload") or {}).get("seo_title") or "").lower()
    _pass("zander_seo_not_concrete", "concrete" not in seo_title, seo_title)
    _pass("zander_seo_instructional", "how to" in seo_title or "method" in seo_title or "step" in seo_title, seo_title)
    preservation = float(payload.get("quality_audit", {}).get("topic_preservation_score") or 0.0)
    _pass("zander_preservation", preservation >= 0.5, str(preservation))
    alignment = float(payload.get("quality_audit", {}).get("topic_strategy_alignment_score") or 0.0)
    _pass("zander_strategy_alignment", alignment >= 0.6, str(alignment))
    _pass(
        "zander_strategy_passed",
        bool(payload.get("quality_audit", {}).get("strategy_alignment_passed")),
        str(payload.get("quality_audit", {}).get("topic_strategy_alignment")),
    )


def _unit_pipeline_offline() -> None:
    payload = run_content_brain_e2e_micro_test(
        topic="old man walking on a beach",
        duration_seconds=30,
        platform="youtube_shorts",
        niche="general",
        mood="emotional",
    )
    _pass("pipeline_completed", payload.get("status") == "completed", payload.get("status"))
    keys = {step.get("step_key") for step in payload.get("steps") or []}
    for required in (
        "topic_authority",
        "trend_discovery",
        "topic_classification",
        "seo_title",
        "story_generation",
        "duration_planner",
        "clip_planner",
        "prompt_generation",
        "seo_generation",
        "quality_audit",
        "export",
    ):
        _pass(f"step_{required}", required in keys)
    _pass("clip_count_30s", any(
        step.get("step_key") == "duration_planner"
        and (step.get("payload") or {}).get("clip_count") == 3
        for step in payload.get("steps") or []
    ))
    prompts = next(
        step for step in payload.get("steps") or [] if step.get("step_key") == "prompt_generation"
    )
    _pass("prompts_generated", len((prompts.get("payload") or {}).get("clip_prompts") or []) >= 1)
    _pass("no_runway_calls", (prompts.get("payload") or {}).get("runway_calls") is False)
    export = next(step for step in payload.get("steps") or [] if step.get("step_key") == "export")
    paths = (export.get("payload") or {}).get("paths") or {}
    _pass("export_json", bool(paths.get("json")))
    _pass("export_md", bool(paths.get("markdown")))
    _pass("export_runway_prompts", bool(paths.get("runway_prompts") or paths.get("latest_runway_prompts")))
    if paths.get("json"):
        path = Path(paths["json"])
        _pass("export_file_exists", path.is_file())
        saved = json.loads(path.read_text(encoding="utf-8"))
        _pass("export_has_run_id", bool(saved.get("run_id")))


def _unit_implementation() -> None:
    studio_src = (ROOT / "content_brain/execution/content_brain_e2e_micro_test_studio.py").read_text(
        encoding="utf-8"
    )
    api_src = (ROOT / "ui/api/main.py").read_text(encoding="utf-8")
    page_src = (ROOT / "ui/web/src/pages/ContentBrainTestStudioPage.tsx").read_text(encoding="utf-8")
    exec_src = (ROOT / "ui/web/src/pages/ExecutionCenterPage.tsx").read_text(encoding="utf-8")
    report = ROOT / "project_brain/CONTENT_BRAIN_END_TO_END_MICRO_TEST_STUDIO_REPORT.md"
    _pass("studio_module", "class ContentBrainE2EMicroTestStudio" in studio_src)
    _pass("topic_authority_step", "topic_authority" in studio_src)
    _pass("trend_step", "trend_discovery" in studio_src)
    _pass("topic_strategy_step", "topic_classification" in studio_src)
    _pass("topic_strategy_module", "content_brain_topic_strategy" in studio_src)
    _pass("story_step", "story_generation" in studio_src)
    _pass("duration_step", "duration_planner" in studio_src)
    _pass("clip_step", "clip_planner" in studio_src)
    _pass("prompt_step", "prompt_generation" in studio_src)
    _pass("seo_step", "seo_generation" in studio_src)
    _pass("quality_step", "quality_audit" in studio_src)
    _pass("export_step", "content_brain_test_results" in studio_src)
    _pass("no_runway_in_studio", "runway_live_smoke" not in studio_src)
    _pass("api_route", "/content-brain-test-studio/run" in api_src)
    _pass("preflight_route", "/content-brain-test-studio/preflight" in api_src)
    _pass("open_export_route", "/content-brain-test-studio/open-export" in api_src)
    _pass("preflight_module", "run_content_brain_studio_preflight" in studio_src)
    _pass("openai_story_module", "content_brain_openai_story_enricher" in studio_src)
    _pass("ui_page", "ContentBrainTestStudioPage" in page_src)
    _pass("execution_center_tab", "content_brain_test" in exec_src)
    _pass("report_exists", report.is_file())


def main() -> int:
    print("[validate_content_brain_end_to_end_micro_test] Content Brain Test Studio")
    _unit_implementation()
    _unit_topic_preservation()
    _unit_zander_fishing_topic()
    _unit_pipeline_offline()
    print("\n[validate_content_brain_end_to_end_micro_test] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
