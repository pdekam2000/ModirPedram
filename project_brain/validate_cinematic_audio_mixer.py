"""PHASE STORY-AUDIO-2 — cinematic audio mixer validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.cinematic_audio_mixer import CINEMATIC_MIXER_VERSION, mix_cinematic_audio
from content_brain.audio.dialogue_timeline_builder import build_runtime_dialogue_timeline
from content_brain.audio.dialogue_to_speech_engine import generate_dialogue_speech_files
from content_brain.audio.emotion_voice_engine import build_voice_performance_plan
from content_brain.audio.environment_timeline_builder import build_environment_timeline
from content_brain.audio.multi_voice_casting_engine import build_multi_voice_cast_runtime
from content_brain.audio.music_timeline_builder import build_music_timeline
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_cinematic_audio_mixer ===")
    package = build_story_package(project_root=ROOT, topic="Cute orange cartoon cat explorer", clip_count=3)
    performance = build_voice_performance_plan(
        dialogue_plan=package.dialogue_plan.to_dict(),
        emotion_plan=package.emotion_plan.to_dict(),
    )
    cast = build_multi_voice_cast_runtime(voice_cast_plan=package.voice_cast_plan.to_dict())
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        speech = generate_dialogue_speech_files(
            project_root=ROOT,
            performance_plan=performance.to_dict(),
            voice_cast_runtime=cast.to_dict(),
            output_dir=tmp_path / "dialogue",
            allow_local_fallback=True,
        )
        dialogue_timeline = build_runtime_dialogue_timeline(
            performance_plan=performance.to_dict(),
            speech_result=speech.to_dict(),
            duration_seconds=12.0,
        )
        env_timeline = build_environment_timeline(
            environment_plan=package.environment_plan.to_dict(),
            duration_seconds=12.0,
            scene_count=3,
        )
        music_timeline = build_music_timeline(
            project_root=ROOT,
            music_plan=package.music_plan.to_dict(),
            duration_seconds=12.0,
        )
        output = tmp_path / "FINAL_CINEMATIC_AUDIO.mp3"
        mix = mix_cinematic_audio(
            project_root=ROOT,
            dialogue_timeline=dialogue_timeline.to_dict(),
            environment_timeline=env_timeline.to_dict(),
            music_timeline=music_timeline.to_dict(),
            output_path=output,
            duration_seconds=12.0,
        )
        _pass("version", CINEMATIC_MIXER_VERSION == "cinematic_audio_mixer_v1")
        _pass("mix_completed", mix.status == "completed", mix.status)
        _pass("output_exists", output.is_file())
        _pass("audible", mix.mean_volume_db is not None and mix.mean_volume_db > -45.0, str(mix.mean_volume_db))
    print("=== complete ===")


if __name__ == "__main__":
    main()
