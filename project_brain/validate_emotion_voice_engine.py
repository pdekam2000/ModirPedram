"""PHASE STORY-AUDIO-2 — emotion voice engine validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.emotion_voice_engine import EMOTION_VOICE_ENGINE_VERSION, build_voice_performance_plan
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_emotion_voice_engine ===")
    package = build_story_package(project_root=ROOT, topic="Cute orange cartoon cat explorer", clip_count=3)
    plan = build_voice_performance_plan(
        dialogue_plan=package.dialogue_plan.to_dict(),
        emotion_plan=package.emotion_plan.to_dict(),
    )
    _pass("version", EMOTION_VOICE_ENGINE_VERSION == "emotion_voice_engine_v1")
    _pass("lines_exist", len(plan.lines) >= 3, str(len(plan.lines)))
    _pass("delivery_styles", all(line.delivery_style for line in plan.lines))
    _pass("emotion_states", len(plan.emotion_states) >= 2)
    _pass("curiosity_delivery", any(line.delivery_style == "excited_wondering" for line in plan.lines))
    print("=== complete ===")


if __name__ == "__main__":
    main()
