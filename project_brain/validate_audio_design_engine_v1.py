"""PHASE QUALITY-FIX-2 — audio design engine validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_design_engine import build_audio_design_plan, reject_news_tone_for_cartoon


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== validate_audio_design_engine_v1 ===")
    plan = build_audio_design_plan(
        project_root=ROOT,
        topic="Cute orange cartoon cat explorer",
        run_id="cb_e2e_20260611_225308_dc20bc1f",
        duration_seconds=13.0,
    )
    _pass("cartoon_child_story_style", plan.narration_style == "child_story", plan.narration_style)
    _pass("cartoon_narrator_style", "playful" in plan.narrator_voice_style.lower())
    _pass("cartoon_music_mood", "whimsical" in plan.music_mood.lower())
    _pass("cartoon_ambience_present", len(plan.ambience_tracks) >= 1)
    _pass("cartoon_sfx_present", len(plan.sound_effects) >= 1)
    _pass("news_tone_rejected", bool(reject_news_tone_for_cartoon(topic=plan.topic, narration_style="documentary")))
    print("=== complete ===")


if __name__ == "__main__":
    main()
