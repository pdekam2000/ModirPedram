"""PHASE STORY-AUDIO-1 — story architect validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.story.story_architect import STORY_ARCHITECT_VERSION, build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_story_architect ===")
    blueprint = build_story_blueprint(topic="Cute orange cartoon cat explorer", clip_count=3)
    _pass("version", STORY_ARCHITECT_VERSION == "story_architect_v1")
    _pass("genre_cartoon", blueprint.genre == "cartoon")
    _pass("arc_hook", bool(blueprint.hook))
    _pass("arc_climax", bool(blueprint.climax))
    _pass("scene_progression", len(blueprint.scene_progression) >= 3, str(len(blueprint.scene_progression)))
    _pass("title_present", bool(blueprint.title))
    print("=== complete ===")


if __name__ == "__main__":
    main()
