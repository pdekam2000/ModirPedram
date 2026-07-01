"""PHASE STORY-AUDIO-2 — music timeline validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.music_timeline_builder import MUSIC_TIMELINE_VERSION, build_music_timeline, save_music_timeline
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_music_timeline ===")
    package = build_story_package(project_root=ROOT, topic="Cute orange cartoon cat explorer", clip_count=3)
    timeline = build_music_timeline(
        project_root=ROOT,
        music_plan=package.music_plan.to_dict(),
        duration_seconds=12.0,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = save_music_timeline(tmp, timeline)
        _pass("version", MUSIC_TIMELINE_VERSION == "music_timeline_builder_v1")
        _pass("timeline_file", path.is_file())
        _pass("segments", len(timeline.segments) >= 2, str(len(timeline.segments)))
        _pass("track_path", bool(timeline.track_path))
    print("=== complete ===")


if __name__ == "__main__":
    main()
