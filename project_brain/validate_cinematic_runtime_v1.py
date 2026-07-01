"""Validate cinematic runtime v1 — story, prompts, continuity, subtitles, music, branding."""

from __future__ import annotations

import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.music_runtime import resolve_music_track_path, run_music_runtime
from content_brain.audio.subtitle_format_engine import (
    MAX_WORDS_PER_LINE,
    PLATFORM_SAFE_MARGINS,
    break_cue_into_short_lines,
    validate_shorts_subtitle_cue,
)
from content_brain.branding.cta_engine import CTA_PRESETS, apply_cta_overlay, resolve_cta_text
from content_brain.execution.cinematic_prompt_expander import EXPANDER_VERSION, average_prompt_length, expand_clip_prompt
from content_brain.execution.runway_prompt_builder import RunwayPromptBuilder
from content_brain.execution.runway_story_brief_builder import RunwayStoryBriefBuilder, StoryBriefInput
from content_brain.execution.seamless_continuity_engine import CONTINUE_MARKER, EXACT_FRAME_MARKER, apply_seamless_continuity


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write_minimal_mp3(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ID3" + b"\x00" * 128)


def _write_minimal_wav(path: Path, *, duration_seconds: float = 0.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 8000
    frames = int(rate * duration_seconds)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_story_brief_conflict_stakes_payoff() -> None:
    builder = RunwayStoryBriefBuilder()
    brief = builder.build(
        StoryBriefInput(
            topic="A wildlife biologist tracks lions across the savanna at dawn",
            clip_count=3,
            niche_style="cinematic",
        )
    )
    _pass("story_conflict", bool(brief.conflict))
    _pass("story_stakes", bool(brief.stakes))
    _pass("story_payoff", bool(brief.payoff))
    _pass("story_opening_hook", bool(brief.opening_hook))
    _pass("story_escalation", bool(brief.escalation))
    _pass("scene_progression", len(brief.scene_progression) >= 3)


def test_expanded_prompts_generated() -> None:
    builder = RunwayStoryBriefBuilder()
    brief = builder.build(StoryBriefInput(topic="GPU performance under load", clip_count=3))
    prompt = expand_clip_prompt(
        base_prompt="Base cinematic clip about GPU thermals.",
        clip_index=1,
        clip_count=3,
        beat=brief.clip_beats[0],
        story_brief=brief,
        anchors=brief.continuity_anchors,
    )
    _pass("expanded_prompt_created", bool(prompt))
    _pass("expander_version", EXPANDER_VERSION in prompt or len(prompt) > 500)


def test_prompt_length_target() -> None:
    builder = RunwayStoryBriefBuilder()
    brief = builder.build(StoryBriefInput(topic="Skincare routine for dry skin in winter", clip_count=3))
    prompts = [
        expand_clip_prompt(
            base_prompt=f"Clip base {index}",
            clip_index=index,
            clip_count=3,
            beat=brief.clip_beats[index - 1],
            story_brief=brief,
            anchors=brief.continuity_anchors,
        )
        for index in range(1, 4)
    ]
    avg = average_prompt_length(prompts)
    _pass("prompt_length_gt_2000", avg >= 2000, str(avg))


def test_continuity_state_generated() -> None:
    builder = RunwayStoryBriefBuilder()
    brief = builder.build(StoryBriefInput(topic="Ocean storm rescue at night", clip_count=3))
    plan = apply_seamless_continuity(
        clip_prompts=["clip one", "clip two", "clip three"],
        story_brief=brief,
        anchors=brief.continuity_anchors,
        clip_beats=brief.clip_beats,
    )
    _pass("continuity_states", len(plan.states) == 3)
    _pass("state_fields", all(state.subject_state and state.camera_state for state in plan.states))


def test_continuity_passed_to_next_clip() -> None:
    plan = apply_seamless_continuity(
        clip_prompts=["first clip prompt", "second clip prompt"],
        clip_beats=["beat one", "beat two"],
    )
    _pass("continue_marker", CONTINUE_MARKER in plan.clip_prompts[1])
    _pass("exact_frame_marker", EXACT_FRAME_MARKER in plan.clip_prompts[1])


def test_subtitle_line_limits() -> None:
    lines = break_cue_into_short_lines("This is a much longer subtitle sentence that must break cleanly", platform="tiktok")
    _pass("subtitle_lines_created", bool(lines))
    _pass("subtitle_max_words", all(len(line.split()) <= MAX_WORDS_PER_LINE for line in lines))
    warnings = validate_shorts_subtitle_cue("Follow for more skincare tips today", platform="youtube_shorts")
    _pass("subtitle_validation_ok", not any("line_too_long" in item for item in warnings))


def test_subtitle_safe_zone() -> None:
    margins = PLATFORM_SAFE_MARGINS["tiktok"]
    _pass("safe_margin_v", margins["margin_v"] >= 140)


def test_music_runtime_loads_local_mp3() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        track = tmp / "project_brain" / "music" / "default_background.mp3"
        _write_minimal_mp3(track)
        profile = {"music_track_path": str(track), "music_provider": "local"}
        resolved = resolve_music_track_path(tmp, profile)
        _pass("music_track_resolved", resolved is not None and resolved.is_file())


def test_music_fade_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        track = tmp / "music.mp3"
        _write_minimal_mp3(track)
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            '{"music_provider":"local","music_track_path":"music.mp3","music_fade_in_seconds":1.5,"music_fade_out_seconds":2.0}',
            encoding="utf-8",
        )
        video = tmp / "input.mp4"
        video.write_bytes(b"\x00" * 64)
        result = run_music_runtime(project_root=tmp, input_video_path=video, fade_in_seconds=1.5, fade_out_seconds=2.0)
        _pass("music_fade_configured", result.get("fade_in_seconds") == 1.5 and result.get("fade_out_seconds") == 2.0)


def test_branding_cta_still_works() -> None:
    text, suggestions, source = resolve_cta_text(profile={"cta_preset": "subscribe"}, channel_name="Tech Lab")
    _pass("cta_preset", text == CTA_PRESETS["subscribe"], text)
    _pass("cta_suggestions", bool(suggestions))
    result = apply_cta_overlay(
        input_video_path=Path(tempfile.gettempdir()) / "missing_cta_video.mp4",
        output_path=Path(tempfile.gettempdir()) / "missing_cta_out.mp4",
        cta_text=text,
    )
    _pass("cta_overlay_callable", result.status in {"SKIPPED", "FAILED", "PLAN_ONLY", "COMPLETED"})


def test_prompt_builder_integration() -> None:
    bundle = RunwayPromptBuilder().build(
        {
            "story_idea": "Documentary about coral reef recovery",
            "clip_count": 3,
            "auto_story_brief": True,
            "auto_prompt_critic": False,
        }
    )
    avg = average_prompt_length(bundle.clip_prompts)
    _pass("builder_clip_count", len(bundle.clip_prompts) == 3)
    _pass("builder_avg_length", avg >= 2000, str(avg))
    _pass("builder_continue_in_later_clip", any(CONTINUE_MARKER in prompt for prompt in bundle.clip_prompts[1:]))
    _pass("builder_exact_frame_marker", any(EXACT_FRAME_MARKER in prompt for prompt in bundle.clip_prompts[1:]))


def test_runway_automation_unchanged() -> None:
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("smoke_no_cinematic_import", "cinematic_prompt_expander" not in smoke)
    _pass("navigator_no_cinematic_import", "seamless_continuity_engine" not in navigator)


def test_provider_router_unchanged() -> None:
    router = (ROOT / "core/video_provider_router.py").read_text(encoding="utf-8")
    _pass("router_exists", "class VideoProviderRouter" in router)
    _pass("router_no_music_runtime", "music_runtime" not in router)


def main() -> None:
    test_story_brief_conflict_stakes_payoff()
    test_expanded_prompts_generated()
    test_prompt_length_target()
    test_continuity_state_generated()
    test_continuity_passed_to_next_clip()
    test_subtitle_line_limits()
    test_subtitle_safe_zone()
    test_music_runtime_loads_local_mp3()
    test_music_fade_metadata()
    test_branding_cta_still_works()
    test_prompt_builder_integration()
    test_runway_automation_unchanged()
    test_provider_router_unchanged()
    print("All cinematic runtime v1 validations passed.")


if __name__ == "__main__":
    main()
