"""PHASE STORY-AUDIO-1 — voice casting director validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.voice_casting_director import VOICE_CASTING_DIRECTOR_VERSION, build_voice_cast_plan
from content_brain.story.character_director import build_character_profiles
from content_brain.story.dialogue_engine import build_dialogue_plan
from content_brain.story.story_architect import build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_voice_casting_director ===")
    topic = "Cute orange cartoon cat explorer"
    blueprint = build_story_blueprint(topic=topic, clip_count=3)
    characters = build_character_profiles(blueprint=blueprint, topic=topic)
    dialogue = build_dialogue_plan(blueprint=blueprint, characters=characters, clip_count=3)
    plan = build_voice_cast_plan(project_root=ROOT, characters=characters, dialogue_plan=dialogue)
    _pass("version", VOICE_CASTING_DIRECTOR_VERSION == "voice_casting_director_v1")
    _pass("narrator_assigned", bool(plan.narrator.get("voice_style")))
    _pass("character_rows", len(plan.characters) >= 2)
    _pass("voice_count", plan.voice_count >= 2, str(plan.voice_count))
    _pass("provider_ready", "elevenlabs" in plan.to_dict().get("provider_ready", []))
    print("=== complete ===")


if __name__ == "__main__":
    main()
