"""PHASE STORY-AUDIO-2 — environment timeline validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.environment_timeline_builder import ENVIRONMENT_TIMELINE_VERSION, build_environment_timeline, save_environment_timeline
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_environment_timeline ===")
    package = build_story_package(project_root=ROOT, topic="Cute orange cartoon cat explorer", clip_count=3)
    timeline = build_environment_timeline(
        environment_plan=package.environment_plan.to_dict(),
        duration_seconds=12.0,
        scene_count=3,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = save_environment_timeline(tmp, timeline)
        _pass("version", ENVIRONMENT_TIMELINE_VERSION == "environment_timeline_builder_v1")
        _pass("timeline_file", path.is_file())
        _pass("layers", len(timeline.layers) >= 2, str(len(timeline.layers)))
        _pass("environment", timeline.environment in {"forest", "jungle"})
    print("=== complete ===")


if __name__ == "__main__":
    main()
