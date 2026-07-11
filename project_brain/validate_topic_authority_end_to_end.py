"""End-to-end topic authority validation for Product Create Video generate flow."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_live_smoke_handoff import (
    clear_registered_e2e_result,
    resolve_live_smoke_prompts,
)
from content_brain.product.topic_authority_trace import normalize_topic
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _run(rel: str) -> None:
    script = ROOT / rel
    if not script.is_file():
        _pass(f"skip_{script.name}", True, "missing")
        return
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), capture_output=True, text=True)
    _pass(rel, proc.returncode == 0, (proc.stdout or proc.stderr)[-220:])


def _make_e2e_result(topic: str, clip_count: int) -> dict:
    clip_prompts = [
        {"clip_index": index, "video_prompt": f"Clip {index} about {topic}."}
        for index in range(1, clip_count + 1)
    ]
    return {
        "run_id": "trace_test_run",
        "input": {"topic": topic},
        "steps": [
            {
                "step_key": "prompt_cleanup",
                "payload": {
                    "starter_image_prompt": f"Starter image for {topic}.",
                    "clip_prompts": clip_prompts,
                    "cleanup_applied": True,
                },
            }
        ],
    }


def test_custom_topic_not_replaced_by_stale_cache() -> None:
    clear_registered_e2e_result()
    user_topic = "urban rooftop garden automation"
    stale_topic = "zander fishing method"
    stale = _make_e2e_result(stale_topic, 3)

    bundle, meta = resolve_live_smoke_prompts(
        story_idea=user_topic,
        project_id="topic_authority_test",
        clip_count=2,
        e2e_result=stale,
        strict_topic_authority=True,
        export_dir=ROOT / "project_brain" / "content_brain_test_results",
    )
    _pass(
        "custom_topic_not_stale",
        normalize_topic(user_topic) in normalize_topic(bundle.story_idea)
        or normalize_topic(user_topic) in normalize_topic(bundle.starter_image_prompt),
        bundle.story_idea[:120],
    )
    _pass("stale_cache_not_used", "fishing" not in normalize_topic(bundle.story_idea))
    _pass("clip_count_two", bundle.clip_count == 2, str(bundle.clip_count))
    _pass("two_clip_prompts", len(bundle.clip_prompts) == 2, str(len(bundle.clip_prompts)))


def test_channel_topic_only_when_selected() -> None:
    service = ProductStudioService(ROOT)
    service.save_channel_profile(
        {
            "channel_name": "Trace Channel",
            "main_niche": "home automation",
            "sub_niche": "smart lighting",
            "channel_topic": "smart lighting routines",
            "target_audience": "homeowners",
            "language": "English",
            "tone_style": "cinematic",
            "default_platform": "youtube_shorts",
            "default_duration_seconds": 20,
            "default_provider": "runway",
            "upload_platforms": ["youtube_shorts"],
        }
    )
    channel = service.create_video_preflight({"topic_mode": "channel", "custom_topic": "ignored custom"})
    custom = service.create_video_preflight(
        {"topic_mode": "custom", "custom_topic": "portable espresso hacks", "duration_seconds": 20}
    )
    _pass("channel_mode_uses_saved_topic", channel.get("authoritative_topic") == "smart lighting routines")
    _pass("custom_mode_uses_custom_topic", custom.get("authoritative_topic") == "portable espresso hacks")


def test_no_stale_topic_reuse_from_latest_json() -> None:
    clear_registered_e2e_result()
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp)
        stale = _make_e2e_result("zander fishing method", 3)
        (export_dir / "latest.json").write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
        user_topic = "micro SaaS pricing psychology"
        bundle, _meta = resolve_live_smoke_prompts(
            story_idea=user_topic,
            project_id="topic_authority_test",
            clip_count=2,
            export_dir=export_dir,
            strict_topic_authority=True,
        )
        _pass("latest_json_stale_rejected", "fishing" not in normalize_topic(bundle.story_idea), bundle.story_idea[:120])
        _pass("fallback_topic_authoritative", normalize_topic(user_topic) in normalize_topic(bundle.story_idea))


def test_requested_clip_count_survives_handoff() -> None:
    topic = "cold brew chemistry explained"
    e2e = _make_e2e_result(topic, 3)
    bundle, _meta = resolve_live_smoke_prompts(
        story_idea=topic,
        project_id="clip_count_test",
        clip_count=2,
        e2e_result=e2e,
        strict_topic_authority=True,
    )
    _pass("requested_clip_count_preserved", bundle.clip_count == 2)
    _pass("two_clips_remain_two", len(bundle.clip_prompts) == 2)


def test_topic_mismatch_fails_in_generate_service() -> None:
    service = ProductStudioService(ROOT)
    bad_e2e = _make_e2e_result("zander fishing method", 2)
    runway_mock = MagicMock()
    runway_mock.start_run.return_value = {"ok": True, "project_id": "phase_i_live", "snapshot": {}}

    with patch(
        "ui.api.product_studio_service.run_content_brain_e2e_micro_test",
        return_value=bad_e2e,
    ):
        result = service.create_video_generate(
            {
                "topic_mode": "custom",
                "custom_topic": "indoor herb garden tips",
                "clip_count": 2,
                "provider": "runway",
                "duration_seconds": 20,
            },
            runway_service=runway_mock,
        )

    _pass("topic_mismatch_fails", result.get("ok") is False)
    _pass("topic_mismatch_message", "Topic authority mismatch" in str(result.get("message")))
    _pass("runway_not_started_on_mismatch", runway_mock.start_run.call_count == 0)


def test_matching_topic_passes_generate_preflight_stages() -> None:
    service = ProductStudioService(ROOT)
    topic = "indoor herb garden tips"
    good_e2e = _make_e2e_result(topic, 2)
    runway_mock = MagicMock()
    runway_mock.start_run.return_value = {
        "ok": True,
        "project_id": "phase_i_live",
        "snapshot": {"project_id": "phase_i_live"},
        "handoff_preview": {"content_brain_run_id": "trace_test_run"},
    }

    with patch(
        "ui.api.product_studio_service.run_content_brain_e2e_micro_test",
        return_value=good_e2e,
    ):
        result = service.create_video_generate(
            {
                "topic_mode": "custom",
                "custom_topic": topic,
                "clip_count": 2,
                "provider": "runway",
                "duration_seconds": 20,
            },
            runway_service=runway_mock,
        )

    _pass("matching_topic_generate_ok", result.get("ok") is True)
    _pass("generate_requested_clip_count", result.get("requested_clip_count") == 2)
    _pass("generate_actual_clip_count", result.get("actual_clip_count") == 2)
    trace = result.get("topic_authority_trace") or {}
    _pass("trace_has_no_mismatches", trace.get("mismatches") == [])


def main() -> None:
    print("=== Topic Authority End-to-End Validation ===")
    test_custom_topic_not_replaced_by_stale_cache()
    test_channel_topic_only_when_selected()
    test_no_stale_topic_reuse_from_latest_json()
    test_requested_clip_count_survives_handoff()
    test_topic_mismatch_fails_in_generate_service()
    test_matching_topic_passes_generate_preflight_stages()

    print("\n=== Regression ===")
    _run("project_brain/validate_director_layer_v1.py")
    _run("project_brain/validate_director_layer_v2_prompt_critic.py")
    _run("project_brain/validate_content_brain_live_smoke_handoff.py")

    print("\nTopic authority end-to-end validation complete — PASS")


if __name__ == "__main__":
    main()
