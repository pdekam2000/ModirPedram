"""PHASE STORY-AUDIO-1 — music director validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.music_director import MUSIC_DIRECTOR_VERSION, build_music_plan
from content_brain.story.character_director import build_character_profiles
from content_brain.story.dialogue_engine import build_dialogue_plan
from content_brain.story.emotion_engine import build_emotion_plan
from content_brain.story.story_architect import build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_music_director ===")
    topic = "Cute orange cartoon cat explorer"
    blueprint = build_story_blueprint(topic=topic, clip_count=3)
    characters = build_character_profiles(blueprint=blueprint, topic=topic)
    dialogue = build_dialogue_plan(blueprint=blueprint, characters=characters, clip_count=3)
    emotion = build_emotion_plan(dialogue_plan=dialogue)
    plan = build_music_plan(blueprint=blueprint, emotion_plan=emotion, duration_seconds=12.0)
    _pass("version", MUSIC_DIRECTOR_VERSION == "music_director_v1")
    _pass("mood_selected", bool(plan.mood))
    _pass("intensity_curve", len(plan.intensity_curve) >= 3)
    _pass("ending_fade", plan.ending_fade_seconds >= 1.0)
    print("=== complete ===")


if __name__ == "__main__":
    main()
