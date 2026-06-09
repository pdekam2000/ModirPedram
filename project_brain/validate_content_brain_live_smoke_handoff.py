"""
Validate Content Brain V8.3 → Runway Live Smoke handoff layer.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_e2e_micro_test_studio import DEFAULT_EXPORT_DIR
from content_brain.execution.content_brain_live_smoke_handoff import (
    PROMPT_SOURCE_CONTENT_BRAIN,
    PROMPT_SOURCE_FALLBACK,
    clear_registered_e2e_result,
    preview_live_smoke_handoff,
    resolve_live_smoke_prompts,
)
from content_brain.execution.runway_live_smoke_test import RunwayLiveSmokeRunner


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _cleanup_step_payload(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "prompt_cleanup")
    return dict(step.get("payload") or {})


def test_e2e_export_exists() -> dict:
    latest_json = DEFAULT_EXPORT_DIR / "latest.json"
    latest_txt = DEFAULT_EXPORT_DIR / "latest.runway_prompts.txt"
    _pass("e2e_export_latest_json_exists", latest_json.is_file(), str(latest_json))
    _pass("e2e_export_latest_runway_prompts_exists", latest_txt.is_file(), str(latest_txt))
    result = json.loads(latest_json.read_text(encoding="utf-8"))
    _pass("e2e_export_latest_json_parseable", isinstance(result, dict))
    return result


def test_handoff_loads_cleaned_prompts(result: dict) -> None:
    cleanup = _cleanup_step_payload(result)
    bundle, meta = resolve_live_smoke_prompts(
        story_idea=str((result.get("input") or {}).get("topic") or ""),
        project_id="handoff_validation",
        clip_count=3,
    )

    starter = str(cleanup.get("starter_image_prompt") or "").strip()
    clip_prompts = [
        str(item.get("video_prompt") or "").strip()
        for item in cleanup.get("clip_prompts") or []
        if isinstance(item, dict)
    ]

    _pass("starter_image_loaded", bool(bundle.starter_image_prompt), f"{len(bundle.starter_image_prompt)} chars")
    _pass("starter_matches_cleanup", bundle.starter_image_prompt.strip() == starter)
    _pass("clip_1_loaded", len(bundle.clip_prompts) >= 1 and bool(bundle.clip_prompts[0]))
    _pass("clip_2_loaded", len(bundle.clip_prompts) >= 2 and bool(bundle.clip_prompts[1]))
    _pass("clip_3_loaded", len(bundle.clip_prompts) >= 3 and bool(bundle.clip_prompts[2]))
    if len(clip_prompts) >= 3:
        _pass("clip_1_matches_cleanup", bundle.clip_prompts[0].strip() == clip_prompts[0])
        _pass("clip_2_matches_cleanup", bundle.clip_prompts[1].strip() == clip_prompts[1])
        _pass("clip_3_matches_cleanup", bundle.clip_prompts[2].strip() == clip_prompts[2])


def test_cleanup_metrics_preserved(result: dict) -> None:
    cleanup = _cleanup_step_payload(result)
    audit = dict(result.get("quality_audit") or {})
    _, meta = resolve_live_smoke_prompts(
        story_idea=str((result.get("input") or {}).get("topic") or ""),
        project_id="handoff_validation",
        clip_count=3,
    )
    expected_noise = float(cleanup.get("prompt_noise_score") or audit.get("prompt_noise_score") or 0.0)
    expected_efficiency = float(cleanup.get("prompt_efficiency_score") or audit.get("prompt_efficiency_score") or 0.0)
    _pass("prompt_source_content_brain", meta.prompt_source == PROMPT_SOURCE_CONTENT_BRAIN, meta.prompt_source)
    _pass("prompt_cleanup_used", meta.prompt_cleanup_used is True, str(meta.prompt_cleanup_used))
    _pass(
        "prompt_noise_score_preserved",
        abs(meta.prompt_noise_score - expected_noise) < 0.0001,
        f"{meta.prompt_noise_score} vs {expected_noise}",
    )
    _pass(
        "prompt_efficiency_score_preserved",
        abs(meta.prompt_efficiency_score - expected_efficiency) < 0.0001,
        f"{meta.prompt_efficiency_score} vs {expected_efficiency}",
    )
    _pass("content_brain_run_id_present", bool(meta.content_brain_run_id), meta.content_brain_run_id)


def test_handoff_reaches_live_smoke_runner(result: dict) -> None:
    topic = str((result.get("input") or {}).get("topic") or "")
    cleanup = _cleanup_step_payload(result)
    runner = RunwayLiveSmokeRunner(
        story_idea=topic,
        project_id="handoff_validation",
        simulate=True,
        clip_count=3,
    )
    bundle, handoff = resolve_live_smoke_prompts(
        story_idea=topic,
        project_id=runner.project_id,
        clip_count=runner.clip_count,
    )
    runner._apply_handoff_meta(handoff)
    runner._capture_prompt_bundle_diagnostics(bundle)

    _pass("runner_prompt_source", runner.report.prompt_source == PROMPT_SOURCE_CONTENT_BRAIN, runner.report.prompt_source)
    _pass(
        "runner_starter_matches_cleanup",
        runner.report.starter_prompt_chars == len(str(cleanup.get("starter_image_prompt") or "")),
        str(runner.report.starter_prompt_chars),
    )
    _pass("runner_handoff_loaded_from", bool(runner.report.handoff_loaded_from), runner.report.handoff_loaded_from)


def test_handoff_preview_metadata(result: dict) -> None:
    preview = preview_live_smoke_handoff(clip_count=3)
    _pass("preview_prompt_source_content_brain", preview.prompt_source == PROMPT_SOURCE_CONTENT_BRAIN, preview.prompt_source)
    _pass("preview_content_brain_topic", bool(preview.content_brain_topic), preview.content_brain_topic[:80])
    _pass("preview_topic_label", bool(preview.topic_label), preview.topic_label)
    _pass("preview_seo_title", bool(preview.seo_title), preview.seo_title[:80])
    _pass("preview_story_summary", bool(preview.story_summary), preview.story_summary[:80])
    _pass("preview_starter_prompt_preview", bool(preview.starter_prompt_preview), preview.starter_prompt_preview[:80])
    expected_topic = str((result.get("input") or {}).get("topic") or "")
    _pass(
        "preview_topic_matches_export",
        preview.content_brain_topic == expected_topic,
        preview.content_brain_topic,
    )


def test_fallback_ui_story_path_still_available() -> None:
    clear_registered_e2e_result()
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp)
        bundle, meta = resolve_live_smoke_prompts(
            story_idea="A fallback-only smoke story about rain and neon.",
            project_id="fallback_validation",
            clip_count=1,
            export_dir=export_dir,
        )
        _pass("fallback_prompt_source", meta.prompt_source == PROMPT_SOURCE_FALLBACK, meta.prompt_source)
        _pass("fallback_bundle_starter_present", bool(bundle.starter_image_prompt))
        _pass("fallback_bundle_clip_present", bool(bundle.clip_prompts))


def main() -> None:
    print("Content Brain V8.3 -> Live Smoke handoff validation")
    print("=" * 60)
    result = test_e2e_export_exists()
    test_handoff_loads_cleaned_prompts(result)
    test_cleanup_metrics_preserved(result)
    test_handoff_reaches_live_smoke_runner(result)
    test_handoff_preview_metadata(result)
    test_fallback_ui_story_path_still_available()
    print("=" * 60)
    print("All handoff validation checks passed.")


if __name__ == "__main__":
    main()
