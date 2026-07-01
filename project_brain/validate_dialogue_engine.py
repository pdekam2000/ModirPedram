"""PHASE STORY-AUDIO-1 — dialogue engine validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.story.character_director import build_character_profiles
from content_brain.story.dialogue_engine import DIALOGUE_ENGINE_VERSION, build_dialogue_plan
from content_brain.story.story_architect import build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_dialogue_engine ===")
    topic = "Cute orange cartoon cat explorer"
    blueprint = build_story_blueprint(topic=topic, clip_count=3)
    characters = build_character_profiles(blueprint=blueprint, topic=topic)
    plan = build_dialogue_plan(blueprint=blueprint, characters=characters, clip_count=3)
    lines = plan.all_spoken_lines()
    _pass("version", DIALOGUE_ENGINE_VERSION == "dialogue_engine_v1")
    _pass("scene_count", len(plan.scenes) >= 3)
    _pass("actual_dialogue", any("Wow!" in line or "?" in line for line in lines), str(lines[:2]))
    _pass("not_stage_direction", not any("Introduce the cute" in line for line in lines))
    print("=== complete ===")


if __name__ == "__main__":
    main()
