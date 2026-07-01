"""PHASE STORY-AUDIO-1 — emotion engine validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.story.character_director import build_character_profiles
from content_brain.story.dialogue_engine import build_dialogue_plan
from content_brain.story.emotion_engine import EMOTION_ENGINE_VERSION, SUPPORTED_EMOTIONS, build_emotion_plan
from content_brain.story.story_architect import build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_emotion_engine ===")
    topic = "Cute orange cartoon cat explorer"
    blueprint = build_story_blueprint(topic=topic, clip_count=3)
    characters = build_character_profiles(blueprint=blueprint, topic=topic)
    dialogue = build_dialogue_plan(blueprint=blueprint, characters=characters, clip_count=3)
    emotion = build_emotion_plan(dialogue_plan=dialogue)
    _pass("version", EMOTION_ENGINE_VERSION == "emotion_engine_v1")
    _pass("supported_emotions", len(SUPPORTED_EMOTIONS) >= 8)
    _pass("scene_profiles", len(emotion.scenes) >= 3)
    _pass("progression_arc", len(emotion.arc_summary.split()) >= 2, emotion.arc_summary.replace("\u2192", "->"))
    _pass("curiosity_scene1", emotion.scenes[0].scores.get("curiosity", 0) >= 50)
    print("=== complete ===")


if __name__ == "__main__":
    main()
