"""PHASE STORY-AUDIO-1 — story audio auditor validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.quality.story_audio_auditor import STORY_AUDIO_AUDITOR_VERSION, audit_story_package
from content_brain.story.story_package import build_story_package


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_story_audio_auditor ===")
    package = build_story_package(
        project_root=ROOT,
        topic="Cute orange cartoon cat explorer",
        run_id="story_audio_test",
        clip_count=3,
        duration_seconds=12.0,
    )
    audit = audit_story_package(package)
    _pass("version", STORY_AUDIO_AUDITOR_VERSION == "story_audio_auditor_v1")
    _pass("audit_pass", audit.status == "PASS", str(audit.failures))
    _pass("dialogue_score", audit.dialogue_score >= 40, str(audit.dialogue_score))
    _pass("character_count", audit.character_count >= 2, str(audit.character_count))
    _pass("voice_count", audit.voice_count >= 2, str(audit.voice_count))
    empty = audit_story_package({})
    _pass("empty_fails", empty.status == "FAIL")
    print("=== complete ===")


if __name__ == "__main__":
    main()
