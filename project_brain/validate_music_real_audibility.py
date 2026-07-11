"""PHASE QUALITY-FIX-3 — real music audibility validation."""

from __future__ import annotations

import json
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.local_audio_assets import ensure_local_audio_assets
from content_brain.audio.music_runtime import (
    LEGACY_MUSIC_RELATIVE,
    MIN_IDEAL_SOURCE_MEAN_DB,
    MIN_MIX_OUTPUT_MEAN_DB,
    MIN_SOURCE_MEAN_DB,
    MUSIC_RUNTIME_VERSION,
    music_runtime_status_label,
    probe_mean_volume_db,
    resolve_music_track_path,
    run_music_runtime,
)

TARGET_RUN_DIR = ROOT / "outputs" / "runs" / "20260611_235927_308_dc20bc1f"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write_tone_mp3(path: Path, *, amplitude: int = 12000, seconds: int = 6) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = path.with_suffix(".wav")
    import math
    import subprocess

    sample_rate = 22050
    with wave.open(str(wav_path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for i in range(sample_rate * seconds):
            sample = int(amplitude * math.sin(2 * math.pi * 440 * (i / sample_rate)))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        handle.writeframes(bytes(frames))
    subprocess.run(["ffmpeg", "-y", "-i", str(wav_path), "-q:a", "4", str(path)], capture_output=True, check=False)
    wav_path.unlink(missing_ok=True)


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
            "color=c=black:s=720x1280:d=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4:sample_rate=44100,volume=0.6",
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


def _validate_cartoon_run() -> None:
    debug_path = TARGET_RUN_DIR / "publish" / "audio" / "music_debug_manifest.json"
    music_path = ROOT / "assets" / "audio" / "music" / "whimsical_adventure.mp3"
    legacy = ROOT / LEGACY_MUSIC_RELATIVE

    if music_path.is_file():
        source_mean = probe_mean_volume_db(music_path)
        _pass("usable_music_source_exists", source_mean is not None and source_mean > MIN_SOURCE_MEAN_DB, f"mean={source_mean}")
    else:
        _pass("usable_music_source_exists", False, str(music_path))

    if legacy.is_file():
        legacy_mean = probe_mean_volume_db(legacy)
        _pass("silent_legacy_not_used_as_pass", legacy_mean is None or legacy_mean <= MIN_SOURCE_MEAN_DB or not debug_path.is_file(), f"legacy_mean={legacy_mean}")

    if debug_path.is_file():
        payload = json.loads(debug_path.read_text(encoding="utf-8"))
        source_mean = payload.get("source_mean_volume_db")
        output_mean = payload.get("mean_volume_db")
        status = str(payload.get("status") or "")
        audibility = bool(payload.get("audibility_pass"))
        if status == "completed":
            _pass("debug_manifest_source_loud_enough", source_mean is not None and source_mean > MIN_SOURCE_MEAN_DB, f"source={source_mean}")
            _pass("debug_manifest_output_loud_enough", output_mean is not None and output_mean >= MIN_MIX_OUTPUT_MEAN_DB, f"output={output_mean}")
            _pass("debug_manifest_audibility_pass", audibility, str(payload.get("status_label")))
        elif status in {"skipped_no_local_track", "skipped_silent_source"}:
            label = music_runtime_status_label(payload)
            _pass("honest_skip_not_fake_pass", "PASS" not in label or "SKIPPED" in label, label)


def main() -> None:
    print("=== validate_music_real_audibility ===")
    _pass("music_runtime_v4", MUSIC_RUNTIME_VERSION == "music_runtime_v4")

    ensure_local_audio_assets(ROOT)
    whimsical = ROOT / "assets" / "audio" / "music" / "whimsical_adventure.mp3"
    if whimsical.is_file():
        mean = probe_mean_volume_db(whimsical)
        _pass("procedural_music_audible", mean is not None and mean > MIN_IDEAL_SOURCE_MEAN_DB, f"mean={mean}")
        _pass("procedural_music_not_tiny", whimsical.stat().st_size > 4000, f"size={whimsical.stat().st_size}")

    silent = ROOT / "project_brain" / "music" / "default_background.mp3"
    if silent.is_file():
        silent_mean = probe_mean_volume_db(silent)
        _pass("silent_placeholder_rejected", silent_mean is None or silent_mean <= MIN_SOURCE_MEAN_DB, f"mean={silent_mean}")

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        input_mp4 = tmp / "input.mp4"
        _write_minimal_mp4(input_mp4)

        silent_track = tmp / "assets" / "audio" / "music" / "silent.mp3"
        _write_tone_mp3(silent_track, amplitude=1, seconds=2)
        (tmp / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            json.dumps({"music_provider": "local", "music_track_path": str(silent_track.relative_to(tmp)).replace("\\", "/")}, ensure_ascii=False),
            encoding="utf-8",
        )
        silent_result = run_music_runtime(project_root=tmp, input_video_path=input_mp4)
        _pass("silent_source_skipped", silent_result.get("status") == "skipped_silent_source", str(silent_result.get("status")))

        track = tmp / "assets" / "audio" / "music" / "test_track.mp3"
        _write_tone_mp3(track)
        (tmp / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            json.dumps({"music_provider": "local", "music_track_path": str(track.relative_to(tmp)).replace("\\", "/")}, ensure_ascii=False),
            encoding="utf-8",
        )
        resolved = resolve_music_track_path(tmp, {"music_track_path": str(track.relative_to(tmp)).replace("\\", "/")})
        resolved_mean = probe_mean_volume_db(resolved) if resolved else None
        _pass("resolved_track_loud_enough", resolved is not None and resolved_mean is not None and resolved_mean > MIN_SOURCE_MEAN_DB, f"mean={resolved_mean}")

        mixed = run_music_runtime(project_root=tmp, input_video_path=input_mp4)
        _pass("mixed_output_has_audio", mixed.get("output_audio_stream_detected") is True)
        _pass("mixed_audibility_pass", mixed.get("audibility_pass") is True, music_runtime_status_label(mixed))
        _pass("mixed_status_completed", mixed.get("status") == "completed")

        (tmp / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            json.dumps({"music_provider": "local", "music_track_path": "assets/audio/music/missing.mp3"}, ensure_ascii=False),
            encoding="utf-8",
        )
        for leftover in (tmp / "assets" / "audio" / "music").glob("*"):
            leftover.unlink(missing_ok=True)
        missing = run_music_runtime(project_root=tmp, input_video_path=input_mp4)
        label = music_runtime_status_label(missing)
        _pass("missing_music_honest_skip", "SKIPPED" in label, label)

    if TARGET_RUN_DIR.is_dir():
        _validate_cartoon_run()

    print("=== complete ===")


if __name__ == "__main__":
    main()
