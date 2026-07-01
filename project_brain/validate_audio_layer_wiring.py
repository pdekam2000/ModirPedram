"""Validate audio layer wiring — voices, ambience, music, mix levels."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_character_voice_detection() -> None:
    from content_brain.audio.voice_casting_engine import build_voice_cast_plan

    plan = build_voice_cast_plan(
        project_root=ROOT,
        topic="A boy finds a dragon egg in the forest",
        segments=["Scene one.", "Scene two.", "Scene three."],
        story_brief={"main_character": "Boy"},
    )
    non_narrator = [item for item in plan.character_assignments if item.get("character") != "narrator"]
    _pass("character_assignments_present", len(non_narrator) >= 1, str(len(non_narrator)))


def test_audio_post_character_status_logic() -> None:
    source = (ROOT / "content_brain/audio/audio_post_processing.py").read_text(encoding="utf-8")
    _pass("non_narrator_count", "non_narrator" in source)
    _pass("run_dir_passed_from_post_processor", "run_dir=run_layout.run_dir" in (ROOT / "content_brain/execution/runway_live_post_processor.py").read_text(encoding="utf-8"))


def test_ambience_volume_wired() -> None:
    source = (ROOT / "content_brain/audio/audio_post_processing.py").read_text(encoding="utf-8")
    _pass("ambience_volume_boost", "ambience_volume=0.22" in source)


def test_music_local_fallback() -> None:
    source = (ROOT / "content_brain/audio/music_runtime.py").read_text(encoding="utf-8")
    _pass("local_fallback_when_provider_none", "local_fallback" in source)
    _pass("music_no_shortest", "-shortest" not in source.split("run_music_runtime")[1] if "run_music_runtime" in source else False)


def test_env_mix_no_shortest() -> None:
    source = (ROOT / "content_brain/audio/audio_mix_engine.py").read_text(encoding="utf-8")
    _pass("env_mix_no_shortest", "-shortest" not in source)


def main() -> None:
    test_character_voice_detection()
    test_audio_post_character_status_logic()
    test_ambience_volume_wired()
    test_music_local_fallback()
    test_env_mix_no_shortest()
    print("validate_audio_layer_wiring: all checks passed")


if __name__ == "__main__":
    main()
