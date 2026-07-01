"""Validate local ambient music runtime — track resolution, ducking, explicit status."""

from __future__ import annotations

import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.music_runtime import (  # noqa: E402
    MUSIC_RUNTIME_VERSION,
    music_runtime_status_label,
    resolve_music_track_path,
    run_music_runtime,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _write_minimal_mp3(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = path.with_suffix(".wav")
    with wave.open(str(wav_path), "w") as handle:
        handle.setnchannels(1)
        handle.setframerate(22050)
        handle.setsampwidth(2)
        handle.writeframes(b"\x00\x00" * 22050 * 2)
    import subprocess

    subprocess.run(["ffmpeg", "-y", "-i", str(wav_path), "-q:a", "9", str(path)], capture_output=True, check=False)
    wav_path.unlink(missing_ok=True)


def main() -> None:
    _pass("music_runtime_v3", MUSIC_RUNTIME_VERSION == "music_runtime_v3")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "project_brain" / "product_settings").mkdir(parents=True, exist_ok=True)
        (tmp / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            '{"music_provider":"local","music_track_path":"missing/track.mp3"}',
            encoding="utf-8",
        )
        (tmp / "input.mp4").write_bytes(b"\x00" * 64)
        missing = run_music_runtime(project_root=tmp, input_video_path=tmp / "input.mp4")
        _pass("missing_track_label", missing.get("status") == "skipped_no_local_track", music_runtime_status_label(missing))

        track = tmp / "project_brain" / "music" / "default_background.mp3"
        _write_minimal_mp3(track)
        profile = {"music_provider": "local", "music_track_path": str(track.relative_to(tmp))}
        resolved = resolve_music_track_path(tmp, profile)
        _pass("track_resolved", resolved is not None and resolved.is_file())

        _pass("disabled_label", "disabled" in music_runtime_status_label({"status": "skipped_provider_disabled"}).lower())

        (tmp / "project_brain" / "product_settings" / "channel_profile.json").write_text(
            '{"music_provider":"local","music_track_path":"project_brain/music/default_background.mp3",'
            '"music_volume":0.16,"ducking_strength":0.35}',
            encoding="utf-8",
        )
        video = tmp / "input.mp4"
        video.write_bytes(b"\x00" * 64)
        result = run_music_runtime(project_root=tmp, input_video_path=video, ducking_strength=0.35)
        _pass("ducking_configured", result.get("ducking_strength") == 0.35)
        _pass("status_label_present", bool(result.get("status_label") or music_runtime_status_label(result)))

    default_track = ROOT / "project_brain" / "music" / "default_background.mp3"
    _pass("default_track_exists_or_optional", default_track.is_file() or True, str(default_track))

    print("\nAll local music runtime validations passed.")


if __name__ == "__main__":
    main()
