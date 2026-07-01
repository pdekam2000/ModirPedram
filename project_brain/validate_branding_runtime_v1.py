"""Validate branding runtime v1 — subtitles, logo, CTA, intro/outro, publish integration."""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult
from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_NAME, run_branding_runtime
from content_brain.branding.cta_engine import apply_cta_overlay, suggest_cta_texts
from content_brain.branding.intro_outro_engine import generate_intro_card, generate_outro_card, merge_intro_outro
from content_brain.branding.logo_overlay_engine import apply_logo_overlay
from content_brain.branding.subtitle_burn_engine import SUBTITLED_VIDEO_NAME, burn_subtitles
from content_brain.execution.assembly_ffmpeg_availability import FFmpegAvailabilityResult
from content_brain.execution.runway_live_post_processor import ASSEMBLY_ASSEMBLED, run_publish_package
from ui.api.product_studio_service import ProductStudioService


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _completed(path: Path) -> BrandingFfmpegResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-branded-video")
    return BrandingFfmpegResult(status="COMPLETED", output_path=str(path), input_path=str(path))


@dataclass
class FakeReport:
    content_brain_topic: str = "test topic"
    content_brain_run_id: str = "cb_branding_test"


def test_subtitle_burn_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "input.mp4"
        video.write_bytes(b"video")
        srt = tmp / "subs.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
        out = tmp / SUBTITLED_VIDEO_NAME
        with patch("content_brain.branding.subtitle_burn_engine.run_ffmpeg_filter", return_value=_completed(out)):
            result = burn_subtitles(input_video_path=video, subtitle_path=srt, output_path=out, subtitle_style="tiktok")
        _pass("subtitle_burn_completed", result.status == "COMPLETED")


def test_logo_overlay_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "input.mp4"
        video.write_bytes(b"video")
        logo = tmp / "project_brain/channel_assets/logo.png"
        logo.parent.mkdir(parents=True, exist_ok=True)
        logo.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        out = tmp / "logo.mp4"
        with patch("content_brain.branding.logo_overlay_engine.run_ffmpeg_complex", return_value=_completed(out)):
            result = apply_logo_overlay(project_root=tmp, input_video_path=video, output_path=out)
        _pass("logo_overlay_completed", result.status == "COMPLETED")


def test_cta_overlay_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "input.mp4"
        video.write_bytes(b"video")
        out = tmp / "cta.mp4"
        with patch("content_brain.branding.cta_engine.run_ffmpeg_filter", return_value=_completed(out)):
            result = apply_cta_overlay(
                input_video_path=video,
                output_path=out,
                cta_text="Follow for more",
                cta_frequency="end",
                duration_seconds=20,
            )
        _pass("cta_overlay_completed", result.status == "COMPLETED")
        suggestions, source = suggest_cta_texts(channel_name="LostSignal HD", platform="tiktok", use_openai=False)
        _pass("cta_suggestions", len(suggestions) >= 2, source)


def test_intro_generation_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        out = tmp / "INTRO.mp4"
        with patch("content_brain.branding.intro_outro_engine._generate_card", return_value=_completed(out)):
            result = generate_intro_card(output_dir=tmp, intro_text="LostSignal HD", intro_duration=2)
        _pass("intro_generation_completed", result.status == "COMPLETED")


def test_outro_generation_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        out = tmp / "OUTRO.mp4"
        with patch("content_brain.branding.intro_outro_engine._generate_card", return_value=_completed(out)):
            result = generate_outro_card(output_dir=tmp, outro_text="Follow for more", outro_duration=2)
        _pass("outro_generation_completed", result.status == "COMPLETED")


def test_branding_pipeline_creates_final_video() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        final_dir = tmp / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        assembled = final_dir / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        assembled.write_bytes(b"assembled")
        srt = tmp / "subs.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

        profile_path = tmp / "project_brain/product_settings/channel_profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(
                {
                    "channel_name": "Test Channel",
                    "branding_enabled": True,
                    "subtitle_enabled": True,
                    "logo_enabled": False,
                    "cta_enabled": True,
                    "cta_text": "Follow for more",
                    "intro_enabled": False,
                    "outro_enabled": False,
                }
            ),
            encoding="utf-8",
        )

        def fake_burn(**kwargs):
            out = Path(kwargs["output_path"])
            return _completed(out)

        def fake_cta(**kwargs):
            out = Path(kwargs["output_path"])
            return _completed(out)

        with patch("content_brain.branding.branding_runtime.burn_subtitles", side_effect=fake_burn):
            with patch("content_brain.branding.branding_runtime.apply_cta_overlay", side_effect=fake_cta):
                result = run_branding_runtime(
                    project_root=tmp,
                    report=FakeReport(),
                    assembly_manifest={"status": ASSEMBLY_ASSEMBLED, "output_path": str(assembled)},
                    audio_post_result={"subtitle_paths": [str(srt)], "duration_seconds": 20},
                    output_dir=final_dir,
                )
        branded = Path(result.get("final_branded_video_path") or "")
        _pass("branding_pipeline_completed", result.get("status") == "completed")
        _pass("branded_video_exists", branded.is_file())


def test_publish_package_includes_branded_video() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        final_video = tmp / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"assembled")
        branded = tmp / "outputs/final" / FINAL_BRANDED_VIDEO_NAME
        branded.write_bytes(b"branded")
        publish = run_publish_package(
            tmp,
            assembly_manifest={"status": ASSEMBLY_ASSEMBLED, "output_path": str(final_video)},
            run_id="cb_branded",
            topic="topic",
            clip_count=1,
            downloaded_file_paths=[str(tmp / "clip.mp4")],
            branding_post_result={
                "status": "completed",
                "branding_enabled": True,
                "final_branded_video_path": str(branded),
                "settings": {
                    "branding_enabled": True,
                    "subtitle_enabled": True,
                    "logo_enabled": True,
                    "cta_enabled": True,
                    "intro_enabled": False,
                    "outro_enabled": False,
                },
            },
        )
        metadata = json.loads((Path(str(publish.get("metadata_path"))).read_text(encoding="utf-8")))
        package_branded = tmp / "outputs/publish/runway_phase_i" / FINAL_BRANDED_VIDEO_NAME
        _pass("publish_created", publish.get("status") == "PUBLISHED_PACKAGE_CREATED")
        _pass("publish_branded_file", package_branded.is_file())
        _pass("publish_metadata_branding", metadata.get("branding_enabled") is True)


def test_results_page_shows_branding_status() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        runtime = tmp / "project_brain/runtime_state"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "runway_phase_i_branding_manifest.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "branding_enabled": True,
                    "final_branded_video_path": str(tmp / "outputs/final/FINAL_BRANDED_VIDEO.mp4"),
                    "steps": {
                        "subtitles": {"status": "PASS"},
                        "logo": {"status": "SKIP"},
                        "cta": {"status": "PASS"},
                        "intro": {"status": "SKIP"},
                        "outro": {"status": "SKIP"},
                    },
                }
            ),
            encoding="utf-8",
        )
        report_path = tmp / "project_brain/runway_live_smoke_last_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"ok": True, "simulate": False, "post_processing_status": "completed"}), encoding="utf-8")
        results = ProductStudioService(tmp).latest_results()
        branding = results.get("branding_status") or {}
        _pass("results_branding_status", branding.get("subtitles") == "PASS")
        _pass("results_branding_cta", branding.get("cta") == "PASS")


def test_existing_assembly_pipeline_still_works() -> None:
    from content_brain.execution.runway_live_post_processor import run_assembly

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        clip = tmp / "clip.mp4"
        clip.write_bytes(b"clip")
        unavailable = FFmpegAvailabilityResult(available=False, error="simulated missing")
        manifest = run_assembly(tmp, input_files=[str(clip)], clip_count=1, ffmpeg_probe=unavailable)
        _pass("assembly_plan_only", manifest.get("status") == "PLAN_ONLY")


def test_existing_audio_pipeline_still_works() -> None:
    from content_brain.audio.audio_post_processing import run_audio_post_processing

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        final_video = tmp / "outputs/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"assembled")
        profile_path = tmp / "project_brain/product_settings/channel_profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps({"default_narration_provider": "none"}), encoding="utf-8")
        result = run_audio_post_processing(
            project_root=tmp,
            report={"clip_count": 1},
            assembly_manifest={"status": ASSEMBLY_ASSEMBLED, "output_path": str(final_video)},
        )
        _pass("audio_skipped_provider", result.get("status") == "skipped_provider_disabled")


def test_runway_automation_unchanged() -> None:
    smoke_source = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    navigator_source = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("smoke_no_branding_engine", "subtitle_burn_engine" not in smoke_source)
    _pass("navigator_untouched", "branding_runtime" not in navigator_source)


def main() -> None:
    test_subtitle_burn_works()
    test_logo_overlay_works()
    test_cta_overlay_works()
    test_intro_generation_works()
    test_outro_generation_works()
    test_branding_pipeline_creates_final_video()
    test_publish_package_includes_branded_video()
    test_results_page_shows_branding_status()
    test_existing_assembly_pipeline_still_works()
    test_existing_audio_pipeline_still_works()
    test_runway_automation_unchanged()
    print("All branding runtime v1 validations passed.")


if __name__ == "__main__":
    main()
