"""PHASE STORY-AUDIO-2 — dialogue timeline validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.dialogue_timeline_builder import (
    DIALOGUE_TIMELINE_RUNTIME_VERSION,
    build_runtime_dialogue_timeline,
    save_runtime_dialogue_timeline,
)
from content_brain.audio.dialogue_to_speech_engine import generate_dialogue_speech_files
from content_brain.audio.emotion_voice_engine import build_voice_performance_plan
from content_brain.audio.multi_voice_casting_engine import build_multi_voice_cast_runtime
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_dialogue_timeline ===")
    package = build_story_package(project_root=ROOT, topic="Cute orange cartoon cat explorer", clip_count=3)
    performance = build_voice_performance_plan(
        dialogue_plan=package.dialogue_plan.to_dict(),
        emotion_plan=package.emotion_plan.to_dict(),
    )
    cast = build_multi_voice_cast_runtime(voice_cast_plan=package.voice_cast_plan.to_dict())
    with tempfile.TemporaryDirectory() as tmp:
        speech = generate_dialogue_speech_files(
            project_root=ROOT,
            performance_plan=performance.to_dict(),
            voice_cast_runtime=cast.to_dict(),
            output_dir=Path(tmp) / "dialogue",
            allow_local_fallback=True,
        )
        timeline = build_runtime_dialogue_timeline(
            performance_plan=performance.to_dict(),
            speech_result=speech.to_dict(),
            duration_seconds=12.0,
        )
        path = save_runtime_dialogue_timeline(Path(tmp) / "timeline", timeline)
        first = timeline.lines[0] if timeline.lines else None
        _pass("version", DIALOGUE_TIMELINE_RUNTIME_VERSION == "dialogue_timeline_builder_v2")
        _pass("timeline_file", path.is_file())
        _pass("line_count", len(timeline.lines) >= 3, str(len(timeline.lines)))
        _pass("audio_paths", all(line.audio_path for line in timeline.lines))
        _pass("timing", bool(first and first.end_seconds > first.start_seconds))
    print("=== complete ===")


if __name__ == "__main__":
    main()
