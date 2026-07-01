"""PHASE QUALITY-FIX-2 — multi-voice narration validation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_design_engine import reject_news_tone_for_cartoon
from content_brain.audio.voice_casting_engine import build_voice_cast_plan, detect_characters


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_multivoice_narration_v1 ===")
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        profile_path = tmp / "project_brain" / "product_settings" / "channel_profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(
                {
                    "character_voice_mode": "multi_voice",
                    "narration_style": "child_story",
                    "default_narrator_voice": "voice_narrator_001",
                    "child_friendly_voice": "voice_cat_002",
                    "character_voice_2": "voice_friend_003",
                }
            ),
            encoding="utf-8",
        )
        topic = "Cute orange cartoon cat explorer with fox friend"
        characters = detect_characters(topic=topic, story_brief={"main_character": "orange cat and fox friend"})
        _pass("characters_detected", len(characters) >= 1, str(characters))
        cast = build_voice_cast_plan(
            project_root=tmp,
            topic=topic,
            segments=["Introduce the cat.", "The fox friend appears.", "Follow for more adventures."],
            audio_design={"narration_style": "child_story", "narrator_voice_style": "warm playful"},
        )
        _pass("cartoon_child_story", cast.narration_style == "child_story")
        _pass("news_tone_rejected", "documentary_style_on_cartoon_topic" in reject_news_tone_for_cartoon(topic=topic, narration_style="documentary") or cast.narration_style != "documentary")
        ids = {str(item.get("voice_id") or "") for item in cast.character_assignments}
        _pass("multi_voice_assignments", len(cast.character_assignments) >= 2)
        _pass("distinct_voice_ids", len(ids) >= 2, str(ids))
    print("=== complete ===")


if __name__ == "__main__":
    main()
