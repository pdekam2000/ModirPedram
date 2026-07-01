"""PHASE STORY-AUDIO-2 — dialogue to speech validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.dialogue_to_speech_engine import DIALOGUE_TO_SPEECH_VERSION, generate_dialogue_speech_files
from content_brain.audio.emotion_voice_engine import build_voice_performance_plan
from content_brain.audio.multi_voice_casting_engine import build_multi_voice_cast_runtime
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_dialogue_to_speech ===")
    package = build_story_package(
        project_root=ROOT,
        topic="Cute orange cartoon cat explorer",
        run_id="validate_dialogue_speech",
        clip_count=3,
    )
    performance = build_voice_performance_plan(
        dialogue_plan=package.dialogue_plan.to_dict(),
        emotion_plan=package.emotion_plan.to_dict(),
    )
    cast = build_multi_voice_cast_runtime(
        voice_cast_plan=package.voice_cast_plan.to_dict(),
        performance_plan=performance.to_dict(),
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = generate_dialogue_speech_files(
            project_root=ROOT,
            performance_plan=performance.to_dict(),
            voice_cast_runtime=cast.to_dict(),
            output_dir=Path(tmp) / "dialogue",
            allow_local_fallback=True,
        )
        _pass("version", DIALOGUE_TO_SPEECH_VERSION == "dialogue_to_speech_engine_v1")
        _pass("status_completed", result.status == "completed", result.status)
        _pass("multiple_speakers", len(result.speaker_files) >= 2, str(list(result.speaker_files)))
        _pass("whiskers_files", "whiskers" in result.speaker_files)
        _pass("sage_files", "sage" in result.speaker_files)
    print("=== complete ===")


if __name__ == "__main__":
    main()
