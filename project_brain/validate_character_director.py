"""PHASE STORY-AUDIO-1 — character director validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.story.character_director import CHARACTER_DIRECTOR_VERSION, build_character_profiles
from content_brain.story.story_architect import build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_character_director ===")
    topic = "Cute orange cartoon cat explorer"
    blueprint = build_story_blueprint(topic=topic, clip_count=3)
    profiles = build_character_profiles(blueprint=blueprint, topic=topic)
    _pass("version", CHARACTER_DIRECTOR_VERSION == "character_director_v1")
    _pass("multiple_characters", len(profiles) >= 3, str(len(profiles)))
    names = {p.name for p in profiles}
    _pass("named_protagonist", "Whiskers" in names)
    _pass("voice_style_fields", all(bool(p.voice_style) for p in profiles))
    print("=== complete ===")


if __name__ == "__main__":
    main()
