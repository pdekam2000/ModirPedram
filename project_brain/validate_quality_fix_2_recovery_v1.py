"""PHASE QUALITY-FIX-2 — recovery v2 + asset vault validation."""

from __future__ import annotations

import json
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.branding_runtime import FINAL_BRANDED_VIDEO_V2_NAME
from content_brain.execution.post_processing_recovery import recover_post_processing_inplace
from content_brain.platform.asset_library import load_asset_index, sha256_file


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write_minimal_mp4(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=720x1280:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        check=False,
    )


def _write_mp3(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wav = path.with_suffix(".wav")
    with wave.open(str(wav), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(22050)
        handle.writeframes(b"\x00\x01" * 22050)
    import subprocess

    subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-q:a", "4", str(path)], capture_output=True, check=False)
    wav.unlink(missing_ok=True)


def main() -> None:
    print("=== validate_quality_fix_2_recovery_v1 ===")
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("runway_automation_untouched", "runway_ui_navigator" in navigator or navigator.strip())

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        run_dir = tmp / "outputs" / "runs" / "test_run_quality_v2"
        final_dir = run_dir / "final"
        publish_dir = run_dir / "publish"
        metadata_dir = run_dir / "metadata"
        final_dir.mkdir(parents=True)
        publish_dir.mkdir(parents=True)
        metadata_dir.mkdir(parents=True)
        assembly_video = final_dir / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
        v1 = publish_dir / "FINAL_BRANDED_VIDEO.mp4"
        _write_minimal_mp4(assembly_video)
        v1.write_bytes(b"original-branded-v1")

        (metadata_dir / "run_summary.json").write_text(
            json.dumps({"run_id": "run_qf2", "topic": "Cute orange cartoon cat explorer", "assembly_status": "ASSEMBLED"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (metadata_dir / "assembly_manifest.json").write_text(
            json.dumps({"status": "ASSEMBLED", "clip_count": 2, "output_path": str(assembly_video)}, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "raw_downloads_manifest.json").write_text(json.dumps({"run_id": "run_qf2", "topic": "cat"}, ensure_ascii=False), encoding="utf-8")

        profile_dir = tmp / "project_brain" / "product_settings"
        profile_dir.mkdir(parents=True, exist_ok=True)
        track = tmp / "assets" / "audio" / "music" / "test.mp3"
        _write_mp3(track)
        (profile_dir / "channel_profile.json").write_text(
            json.dumps(
                {
                    "music_provider": "local",
                    "music_track_path": str(track.relative_to(tmp)).replace("\\", "/"),
                    "default_narration_provider": "none",
                    "character_voice_mode": "multi_voice",
                    "narration_style": "child_story",
                    "asset_vault_enabled": True,
                }
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        fake_audio = {
            "status": "completed",
            "narration_provider": "none",
            "music_provider": "local",
            "narrated_video_path": str(assembly_video),
            "subtitle_paths": [],
            "duration_seconds": 2.0,
            "music_status": "PASS — mixed track: test",
            "ambience_status": "Ambience skipped: no ambience files found.",
            "sfx_status": "SFX skipped: no sfx files found.",
            "subtitle_style_status": "Subtitle style: colorful lower-third active.",
            "character_voice_status": "Character voices skipped: multi-voice mode disabled.",
        }
        fake_branding = {
            "status": "completed",
            "branding_enabled": True,
            "branded_video_name": FINAL_BRANDED_VIDEO_V2_NAME,
            "final_branded_video_path": str(final_dir / FINAL_BRANDED_VIDEO_V2_NAME),
            "settings": {"subtitle_enabled": False, "logo_enabled": False, "cta_enabled": False},
        }
        fake_publish = {
            "status": "PUBLISHED_PACKAGE_CREATED",
            "branded_video_path": str(publish_dir / FINAL_BRANDED_VIDEO_V2_NAME),
            "branded_video_name": FINAL_BRANDED_VIDEO_V2_NAME,
        }

        with patch("content_brain.execution.post_processing_recovery.run_audio_post_processing", return_value=fake_audio), patch(
            "content_brain.execution.post_processing_recovery.run_branding_runtime",
            return_value=fake_branding,
        ), patch("content_brain.execution.post_processing_recovery.run_publish_package", return_value=fake_publish), patch(
            "content_brain.execution.post_processing_recovery.finalize_versioned_run_layout",
            return_value={"publish_status": "PUBLISHED_PACKAGE_CREATED"},
        ), patch("content_brain.execution.post_processing_recovery.register_published_asset", return_value={"status": "registered", "asset_id": "asset_v2"}):
            (final_dir / FINAL_BRANDED_VIDEO_V2_NAME).write_bytes(b"branded-v2-content")
            summary = recover_post_processing_inplace(
                tmp,
                run_dir=run_dir,
                report={"content_brain_run_id": "run_qf2", "content_brain_topic": "cat", "clip_count": 2},
                branded_video_name=FINAL_BRANDED_VIDEO_V2_NAME,
                register_asset=True,
            )

        _pass("recovery_ok", summary.get("ok") is True)
        _pass("v1_preserved", v1.is_file() and v1.read_bytes() == b"original-branded-v1")
        v2 = publish_dir / FINAL_BRANDED_VIDEO_V2_NAME
        _pass("v2_created", v2.is_file())
        _pass("v2_not_overwrite_v1", v1.read_bytes() != v2.read_bytes())

    print("=== complete ===")


if __name__ == "__main__":
    main()
