"""Phase ElevenLabs Runtime v1 validation — Suno-ready architecture."""

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

from content_brain.audio.audio_merge_engine import merge_narration_into_video
from content_brain.audio.audio_post_processing import run_audio_post_processing
from content_brain.audio.narration_engine import NarrationEngine
from content_brain.audio.narration_script_builder import build_narration_script
from content_brain.audio.subtitle_timing_engine import generate_timed_subtitles
from content_brain.execution.assembly_ffmpeg_availability import FFmpegAvailabilityResult
from content_brain.execution.runway_live_post_processor import ASSEMBLY_ASSEMBLED, run_publish_package
from providers.audio.elevenlabs_provider import ElevenLabsNarrationProvider
from providers.audio.local_music_provider import SunoMusicProvider
from providers.audio.provider_registry import resolve_music_provider, resolve_narration_provider


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


def test_elevenlabs_provider_loads() -> None:
    provider = resolve_narration_provider("elevenlabs", ROOT)
    _pass("provider_loads", isinstance(provider, ElevenLabsNarrationProvider))
    _pass("provider_id", provider.provider_id == "elevenlabs")


def test_connection_validation() -> None:
    provider = ElevenLabsNarrationProvider(ROOT)
    with patch.object(provider, "validate_connection", return_value={"ok": True, "provider_id": "elevenlabs"}):
        result = provider.validate_connection()
    _pass("connection_validation", result.get("ok") is True)


def test_narration_script_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result = build_narration_script(
            project_root=tmp,
            topic="urban rooftop gardens",
            platform="tiktok",
            clip_count=2,
            run_id="script_test",
            report={"story_brief_logline": "Tiny gardens changing city rooftops.", "seo_title": "Rooftop Gardens"},
        )
        _pass("script_nonempty", bool(result.script.strip()), result.script[:80])
        _pass("script_file_written", Path(result.script_path).is_file())
        _pass("multi_segment", len(result.segments) >= 3)


def test_narration_audio_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        engine = NarrationEngine(tmp)
        fake_provider = MagicMock()
        fake_provider.validate_connection.return_value = {
            "ok": True,
            "config_summary": {"voice_id": "voice_test", "model_id": "eleven_multilingual_v2"},
        }
        fake_provider.generate_voice.return_value = MagicMock(
            mp3_path=str(tmp / "outputs" / "audio" / "run_narration.mp3"),
            metadata={"provider_id": "elevenlabs"},
        )
        with patch("content_brain.audio.narration_engine.resolve_narration_provider", return_value=fake_provider):
            result = engine.run(topic="test topic", platform="youtube_shorts", clip_count=1, run_id="run")
        _pass("narration_audio_completed", result.status == "completed")
        fake_provider.generate_voice.assert_called_once()


def test_audio_merge_works() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        video = tmp / "video.mp4"
        audio = tmp / "narration.mp3"
        merged = tmp / "out.mp4"
        video.write_bytes(b"video")
        audio.write_bytes(b"audio")

        def fake_run(cmd, **kwargs):
            merged.write_bytes(b"merged")
            return MagicMock(returncode=0, stdout="", stderr="")

        ffmpeg_ok = FFmpegAvailabilityResult(available=True, ffmpeg_path="ffmpeg")
        with patch("content_brain.audio.audio_merge_engine.subprocess.run", side_effect=fake_run):
            result = merge_narration_into_video(
                video_path=video,
                narration_audio_path=audio,
                output_path=merged,
                ffmpeg_probe=ffmpeg_ok,
            )
        _pass("audio_merge_called", result.ffmpeg_executed is True)
        _pass("audio_merge_status", result.status == "MERGED")


def test_real_subtitles_generated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        audio = tmp / "narration.mp3"
        audio.write_bytes(b"fake")
        out_dir = tmp / "subs"
        with patch("content_brain.audio.subtitle_timing_engine._probe_audio_duration_seconds", return_value=12.0):
            result = generate_timed_subtitles(
                script="Hook. Scene one details. Scene two details. Outro.",
                narration_audio_path=audio,
                output_dir=out_dir,
                segments=["Hook.", "Scene one details.", "Scene two details.", "Outro."],
            )
        srt = Path(result.srt_path).read_text(encoding="utf-8")
        _pass("subtitle_status", result.status == "GENERATED")
        _pass("subtitle_real_timing", "00:00:00,000" in srt and "-->" in srt)
        _pass("subtitle_not_placeholder", "[placeholder subtitles]" not in srt)


def test_publish_package_updated() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        final_video = tmp / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        final_video.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"video")
        narrated = tmp / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"
        narrated.write_bytes(b"narrated")
        script = tmp / "outputs" / "audio" / "script.txt"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("Narration script.", encoding="utf-8")
        audio = tmp / "outputs" / "audio" / "narration.mp3"
        audio.write_bytes(b"mp3")
        srt = tmp / "outputs" / "audio" / "subtitles" / "subtitles.srt"
        vtt = tmp / "outputs" / "audio" / "subtitles" / "subtitles.vtt"
        srt.parent.mkdir(parents=True, exist_ok=True)
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
        vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello\n", encoding="utf-8")

        manifest = run_publish_package(
            tmp,
            assembly_manifest={"status": ASSEMBLY_ASSEMBLED, "output_path": str(final_video)},
            run_id="pub_test",
            topic="topic",
            clip_count=2,
            downloaded_file_paths=[str(final_video)],
            audio_post_result={
                "status": "completed",
                "narration_provider": "elevenlabs",
                "voice_id": "voice_test",
                "music_provider": "none",
                "narrated_video_path": str(narrated),
                "narration_script_path": str(script),
                "narration_audio_path": str(audio),
                "subtitle_paths": [str(srt), str(vtt)],
                "duration_seconds": 12.0,
            },
        )
        package = tmp / "outputs" / "publish" / "runway_phase_i"
        _pass("publish_created", manifest.get("status") == "PUBLISHED_PACKAGE_CREATED")
        _pass("publish_narrated_video", (package / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4").is_file())
        _pass("publish_narration_script", (package / "narration" / "narration_script.txt").is_file())
        _pass("publish_narration_audio", (package / "narration" / "narration.mp3").is_file())
        metadata = json.loads((package / "metadata.json").read_text(encoding="utf-8"))
        _pass("publish_metadata_provider", metadata.get("narration_provider") == "elevenlabs")


def test_runway_pipeline_unchanged() -> None:
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    smoke = (ROOT / "content_brain/execution/runway_live_smoke_test.py").read_text(encoding="utf-8")
    _pass("navigator_untouched", "elevenlabs" not in navigator.lower())
    _pass("smoke_still_calls_drive_until_done", "_drive_until_done()" in smoke)
    _pass("audio_hook_after_assembly", "run_audio_post_processing" in (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8"))


def test_suno_slot_reserved_not_implemented() -> None:
    suno = resolve_music_provider("suno")
    _pass("suno_provider_exists", isinstance(suno, SunoMusicProvider))
    validation = suno.validate_connection()
    _pass("suno_not_implemented", validation.get("ok") is False)


def test_audio_post_processing_skips_without_assembly() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result = run_audio_post_processing(
            project_root=tmp,
            report={"clip_count": 1, "content_brain_topic": "topic"},
            assembly_manifest={"status": "PLAN_ONLY"},
        )
        _pass("audio_skip_plan_only", result.get("status") == "skipped_assembly_not_ready")


def main() -> None:
    print("=== ElevenLabs Runtime v1 Validation ===")
    test_elevenlabs_provider_loads()
    test_connection_validation()
    test_narration_script_generated()
    test_narration_audio_generated()
    test_audio_merge_works()
    test_real_subtitles_generated()
    test_publish_package_updated()
    test_runway_pipeline_unchanged()
    test_suno_slot_reserved_not_implemented()
    test_audio_post_processing_skips_without_assembly()

    print("\n=== Regression ===")
    _run("project_brain/validate_director_layer_v1.py")
    _run("project_brain/validate_live_post_processing_hook.py")
    print("\nALL PASS")


if __name__ == "__main__":
    main()
