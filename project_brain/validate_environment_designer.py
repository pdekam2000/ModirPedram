"""PHASE STORY-AUDIO-1 — environment designer validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.environment_designer import ENVIRONMENT_DESIGNER_VERSION, build_environment_plan
from content_brain.story.story_architect import build_story_blueprint


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_environment_designer ===")
    topic = "Cute orange cartoon cat explorer"
    blueprint = build_story_blueprint(topic=topic, clip_count=3)
    plan = build_environment_plan(project_root=ROOT, blueprint=blueprint, topic=topic)
    _pass("version", ENVIRONMENT_DESIGNER_VERSION == "environment_designer_v1")
    _pass("environment_detected", plan.environment in {"forest", "jungle"})
    _pass("ambience_layers", len(plan.ambience) >= 2)
    _pass("movement_or_animals", len(plan.movement_sounds) + len(plan.animal_sounds) >= 1)
    print("=== complete ===")


if __name__ == "__main__":
    main()
