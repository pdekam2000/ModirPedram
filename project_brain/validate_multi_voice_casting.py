"""PHASE STORY-AUDIO-2 — multi voice casting validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.multi_voice_casting_engine import MULTI_VOICE_CASTING_VERSION, build_multi_voice_cast_runtime, save_voice_cast_runtime
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_multi_voice_casting ===")
    package = build_story_package(project_root=ROOT, topic="Cute orange cartoon cat explorer", clip_count=3)
    runtime = build_multi_voice_cast_runtime(voice_cast_plan=package.voice_cast_plan.to_dict())
    with tempfile.TemporaryDirectory() as tmp:
        path = save_voice_cast_runtime(tmp, runtime)
        _pass("version", MULTI_VOICE_CASTING_VERSION == "multi_voice_casting_engine_v1")
        _pass("runtime_file", path.is_file())
        _pass("voice_count", runtime.voice_count >= 3, str(runtime.voice_count))
        _pass("whiskers_mapped", "whiskers" in runtime.speaker_map)
        _pass("sage_mapped", "sage" in runtime.speaker_map)
    print("=== complete ===")


if __name__ == "__main__":
    main()
