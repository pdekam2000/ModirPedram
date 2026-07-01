"""Phase DIRECTOR-1 — Director Layer validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.director.director_pipeline import build_director_layer
from content_brain.director.storyboard_generator import generate_storyboard_plan
from content_brain.execution.runway_prompt_builder import build_continuity_prompts

ANTS = "ants"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    print("=== Director Layer v1 Validation ===")
    plan, _ = generate_storyboard_plan(topic=ANTS, clip_count=3, dry_run=True)
    _pass("storyboard_generated", bool(plan.title and plan.clips))
    _pass("three_clips", len(plan.clips) == 3)
    out = build_director_layer(topic=ANTS, clip_count=3, dry_run=True)
    _pass("director_pipeline", bool(out.scene_breakdown.clips))
    _pass("topic_authority", out.topic_authority_pass, str(out.topic_authority_score))
    bundle = build_continuity_prompts(ANTS, clip_count=3, auto_story_brief=True, auto_director=True, director_dry_run=True)
    _pass("prompt_builder_director", bundle.director_layer is not None)
    print("Director Layer v1 validation complete — PASS")


if __name__ == "__main__":
    main()
