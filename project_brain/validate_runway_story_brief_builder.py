"""
Phase RUNWAY-CONTENT-BRIEF — story brief builder validation.

Content layer only — no browser, Runway, credits, or provider execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_prompt_builder import (
    build_continuity_prompts,
    build_continuity_prompts_from_brief,
)
from content_brain.execution.runway_story_brief_builder import (
    BUILDER_VERSION,
    RunwayStoryBriefBuilder,
    StoryBriefInput,
    build_runway_story_brief,
    validate_story_brief,
)

SHORT_TOPIC = "astronaut alone on neon platform in rain"
RICH_STORY = (
    "A lone astronaut in a weathered EVA suit stands on a giant abandoned futuristic "
    "platform above a glowing cyberpunk city at night. Heavy rain, cinematic atmosphere. "
    "Clip 1: rain intensifies as she turns toward the skyline. "
    "Clip 2: she walks along the platform edge with city lights pulsing below. "
    "Clip 3: she reaches a dormant launch cradle and places her gloved hand on its surface."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    brief_path = ROOT / "content_brain/execution/runway_story_brief_builder.py"
    prompt_path = ROOT / "content_brain/execution/runway_prompt_builder.py"
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    brief_text = brief_path.read_text(encoding="utf-8")
    prompt_text = prompt_path.read_text(encoding="utf-8")

    _pass("brief_builder_exists", brief_path.is_file())
    _pass("report_exists", (ROOT / "project_brain/PHASE_RUNWAY_CONTENT_BRIEF_BUILDER_REPORT.md").is_file())
    _pass("no_browser_in_brief", "BrowserManager" not in brief_text)
    _pass("no_runway_automation", "MappedRunwayUINavigator" not in brief_text)
    _pass("prompt_builder_uses_brief", "build_runway_story_brief" in prompt_text)
    _pass("prompt_builder_from_brief", "build_continuity_prompts_from_brief" in prompt_text)
    _pass("no_provider_mutation", "runway_story_brief_builder" not in provider)


def _unit_story_brief_fields() -> None:
    brief = build_runway_story_brief(
        SHORT_TOPIC,
        target_platform="youtube_shorts",
        niche_style="cyberpunk",
        mood="tense hopeful",
        clip_count=3,
    )
    _pass("brief_not_empty", bool(brief.logline), brief.logline[:80])
    _pass("has_title", bool(brief.title))
    _pass("has_character", bool(brief.main_character))
    _pass("has_setting", bool(brief.setting))
    _pass("has_conflict", bool(brief.conflict_tension))
    _pass("has_visual_hook", bool(brief.visual_hook))
    _pass("has_emotional_arc", bool(brief.emotional_arc))
    _pass("has_ending_beat", bool(brief.ending_beat))
    _pass("has_style_direction", bool(brief.style_direction))
    _pass("has_continuity_anchors", bool(brief.continuity_anchors.character))
    _pass("three_clip_beats", len(brief.clip_beats) == 3, str(len(brief.clip_beats)))
    _pass("brief_validation_clean", not validate_story_brief(brief), str(validate_story_brief(brief)))


def _unit_short_topic_expansion() -> None:
    brief = build_runway_story_brief(SHORT_TOPIC, clip_count=3, niche_style="cyberpunk")
    _pass("short_topic_logline_richer", len(brief.logline) > len(SHORT_TOPIC), f"{len(brief.logline)} chars")
    _pass("short_topic_has_astronaut", "astronaut" in brief.main_character.lower())
    _pass("short_topic_neon_setting", "neon" in brief.setting.lower() or "platform" in brief.setting.lower())


def _unit_prompt_builder_receives_brief() -> None:
    brief = build_runway_story_brief(SHORT_TOPIC, clip_count=3, niche_style="cyberpunk")
    bundle = build_continuity_prompts_from_brief(brief, project_id="brief_bridge")
    _pass("bundle_has_story_brief", bundle.story_brief is not None)
    _pass("bundle_brief_title", bool(getattr(bundle.story_brief, "title", "")))
    _pass("bundle_three_clips", len(bundle.clip_prompts) == 3)


def _unit_starter_prompt_improves_from_brief() -> None:
    raw_bundle = build_continuity_prompts(
        SHORT_TOPIC,
        clip_count=3,
        auto_story_brief=False,
        project_id="raw_short",
    )
    rich_bundle = build_continuity_prompts(
        SHORT_TOPIC,
        clip_count=3,
        auto_story_brief=True,
        niche_style="cyberpunk",
        mood="tense hopeful",
        project_id="brief_enriched",
    )
    _pass(
        "starter_longer_with_brief",
        len(rich_bundle.starter_image_prompt) > len(raw_bundle.starter_image_prompt),
        f"{len(raw_bundle.starter_image_prompt)} -> {len(rich_bundle.starter_image_prompt)}",
    )
    _pass("starter_has_visual_hook_language", "hook" in rich_bundle.starter_image_prompt.lower())
    _pass("starter_has_tension_language", "tension" in rich_bundle.starter_image_prompt.lower())


def _unit_clip_continuity_from_brief() -> None:
    brief = RunwayStoryBriefBuilder().build(
        StoryBriefInput(topic=RICH_STORY, clip_count=3, niche_style="cyberpunk")
    )
    bundle = build_continuity_prompts_from_brief(brief, project_id="continuity_chain")
    character = bundle.continuity_anchors.character.lower()
    for index, prompt in enumerate(bundle.clip_prompts, start=1):
        lowered = prompt.lower()
        _pass(f"clip_{index}_continuity_lock", "continuity lock" in lowered)
        _pass(f"clip_{index}_same_character", character.split()[0] in lowered or "same character" in lowered)
    _pass("clip_1_use_to_video_seed", "starter reference" in bundle.clip_prompts[0].lower())
    _pass("clip_2_use_frame_seed", "use frame" in bundle.clip_prompts[1].lower())
    _pass("clip_3_final_no_epilogue", "no epilogue" in bundle.clip_prompts[2].lower() or "final clip" in bundle.clip_prompts[2].lower())


def _unit_auto_brief_preserves_rich_story() -> None:
    bundle = build_continuity_prompts(RICH_STORY, clip_count=3, auto_story_brief=True)
    _pass("rich_story_bundle_ok", bool(bundle.starter_image_prompt))
    _pass("rich_story_has_brief", bundle.story_brief is not None)
    beats = getattr(bundle.story_brief, "clip_beats", []) or []
    _pass("rich_story_beats_preserved", len(beats) == 3)
    _pass("rich_story_clip1_turn", "turn" in beats[0].lower() or "rain" in beats[0].lower())


def main() -> int:
    print(f"[validate_runway_story_brief_builder] {BUILDER_VERSION}")
    print("[validate_runway_story_brief_builder] Static")
    _static_checks()
    print("\n[validate_runway_story_brief_builder] Unit")
    _unit_story_brief_fields()
    _unit_short_topic_expansion()
    _unit_prompt_builder_receives_brief()
    _unit_starter_prompt_improves_from_brief()
    _unit_clip_continuity_from_brief()
    _unit_auto_brief_preserves_rich_story()
    print("\n[validate_runway_story_brief_builder] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
