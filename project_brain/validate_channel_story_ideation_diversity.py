"""Validation — channel topic story ideation and anti-repetition."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.channel_story_ideation import (  # noqa: E402
    LOGLINE_SIMILARITY_REJECT,
    PROMPT_SIMILARITY_REJECT,
    ChannelStoryIdea,
    append_story_memory,
    apply_channel_story_ideation,
    check_story_similarity,
    generate_channel_story_idea,
    ideate_and_persist_channel_story,
    load_story_memory,
    story_memory_path,
    token_jaccard_similarity,
)
from content_brain.execution.product_multiclip_execution_plan import calculate_product_clip_count  # noqa: E402
from ui.api.product_studio_service import ProductStudioService  # noqa: E402

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []
CHANNEL_TOPIC = "dark fantasy analog horror stories"


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def main() -> int:
    print("validate_channel_story_ideation_diversity")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        titles: set[str] = set()
        settings: set[str] = set()
        characters: set[str] = set()
        for index in range(5):
            idea = generate_channel_story_idea(
                channel_topic=CHANNEL_TOPIC,
                niche="dark fantasy",
                clip_count=2,
                duration_seconds=30,
                previous_story_memory=load_story_memory(root),
                attempt_offset=index * 3,
            )
            titles.add(idea.title.lower())
            settings.add(idea.setting.lower())
            characters.add(idea.main_character.lower())
            append_story_memory(root, idea.to_dict())
        _record("same_channel_topic_different_titles", len(titles) >= 4, str(len(titles)))
        _record("same_channel_topic_different_settings", len(settings) >= 4, str(len(settings)))
        _record("same_channel_topic_different_characters", len(characters) >= 4, str(len(characters)))

        dragon = ChannelStoryIdea(
            unique_story_id="dragon1",
            title="Boy and the Dragon Egg",
            logline="A boy finds a dragon egg in a forest clearing and vows to protect it.",
            main_character="a frightened boy",
            setting="twisted fantasy forest with mossy roots",
            conflict="the egg begins to hatch unexpectedly",
            visual_hook="pale glow beneath wet leaves",
            emotional_hook="fear and wonder",
            twist_or_reveal="the egg recognizes the boy",
            ending_beat="the forest falls silent as wings unfurl",
            clip_beat_outline=["boy discovers egg", "forest reacts"],
            channel_topic=CHANNEL_TOPIC,
        )
        append_story_memory(root, dragon.to_dict())
        repeat_dragon = ChannelStoryIdea(
            unique_story_id="dragon2",
            title="Another Dragon Egg",
            logline="A boy discovers a dragon egg hidden in the forest and tries to hide it.",
            main_character="a young boy",
            setting="twisted fantasy forest with mossy roots",
            conflict="footsteps approach the nest",
            visual_hook="warm light through branches",
            emotional_hook="panic",
            twist_or_reveal="the egg cracks",
            ending_beat="the boy shields the hatchling",
            clip_beat_outline=["boy finds egg", "forest closes in"],
            channel_topic=CHANNEL_TOPIC,
        )
        ok_dragon, reason_dragon, _ = check_story_similarity(repeat_dragon, load_story_memory(root))
        _record("repeated_dragon_pattern_rejected", not ok_dragon, reason_dragon)

        base = generate_channel_story_idea(channel_topic=CHANNEL_TOPIC, clip_count=2)
        near = ChannelStoryIdea(
            unique_story_id="near",
            title=base.title + " copy",
            logline=base.logline,
            main_character=base.main_character,
            setting=base.setting,
            conflict=base.conflict,
            visual_hook=base.visual_hook,
            emotional_hook=base.emotional_hook,
            twist_or_reveal=base.twist_or_reveal,
            ending_beat=base.ending_beat,
            clip_beat_outline=list(base.clip_beat_outline),
            channel_topic=CHANNEL_TOPIC,
        )
        ok_logline, reason_logline, _ = check_story_similarity(near, [base.to_dict()])
        _record("logline_similarity_rejected", not ok_logline, reason_logline)
        _record(
            "logline_threshold_configured",
            LOGLINE_SIMILARITY_REJECT == 0.72 and token_jaccard_similarity(near.logline, base.logline) > LOGLINE_SIMILARITY_REJECT,
        )

        prompt_like = ChannelStoryIdea(
            unique_story_id="prompt_like",
            title="Different title entirely",
            logline=base.logline,
            main_character=base.main_character,
            setting=base.setting,
            conflict=base.conflict,
            visual_hook=base.visual_hook,
            emotional_hook=base.emotional_hook,
            twist_or_reveal=base.twist_or_reveal,
            ending_beat=base.ending_beat,
            clip_beat_outline=list(base.clip_beat_outline),
            channel_topic=CHANNEL_TOPIC,
        )
        ok_prompt, reason_prompt, _ = check_story_similarity(prompt_like, [base.to_dict()])
        _record("prompt_similarity_rejected", not ok_prompt, reason_prompt)
        _record("prompt_threshold_configured", PROMPT_SIMILARITY_REJECT == 0.78)

        before = story_memory_path(root)
        ideate_and_persist_channel_story(
            project_root=root,
            channel_topic=CHANNEL_TOPIC,
            clip_count=2,
            duration_seconds=30,
        )
        after = story_memory_path(root)
        _record("story_memory_append_only", after.is_file() and after.stat().st_size >= before.stat().st_size if before.is_file() else after.is_file())
        lines = after.read_text(encoding="utf-8").strip().splitlines()
        _record("story_memory_jsonl_format", all(line.strip().startswith("{") for line in lines if line.strip()))

        service = ProductStudioService(root)
        preflight = service.create_video_preflight(
            {
                "topic_mode": "custom",
                "custom_topic": CHANNEL_TOPIC,
                "duration_seconds": 30,
                "provider": "kling_3_0_pro_native_audio",
                "audio_strategy": "kling_native_audio",
                "skip_story_memory_persist": True,
            }
        )
        _record(
            "prompt_builder_receives_story_brief",
            bool(preflight.get("runway_story_brief")) and bool(preflight.get("channel_story_idea")),
            str(preflight.get("story_ideation_version")),
        )
        _record(
            "authoritative_topic_not_raw_channel_only",
            CHANNEL_TOPIC not in str(preflight.get("authoritative_topic") or "") or len(str(preflight.get("authoritative_topic") or "")) > len(CHANNEL_TOPIC) + 20,
            str(len(str(preflight.get("authoritative_topic") or ""))),
        )

        override_text = "A subway archivist finds a tape that plays tomorrow's platform announcement today."
        override = apply_channel_story_ideation(
            project_root=root,
            payload={"specific_story_override": override_text},
            channel_topic=CHANNEL_TOPIC,
            niche="dark fantasy",
            target_platform="youtube_shorts",
            style="cinematic",
            mood="uneasy",
            duration_seconds=30,
            clip_count=2,
        )
        _record("specific_story_override_works", override.get("story_override_active") is True, override_text[:40])

    ui_src = (ROOT / "ui" / "web" / "src" / "pages" / "CreateVideoPage.tsx").read_text(encoding="utf-8")
    _record("product_studio_channel_topic_label", "Channel Topic / Niche" in ui_src)
    _record("product_studio_story_override_label", "Specific Story Override" in ui_src)

    _record("no_provider_calls_in_ideation_module", "subprocess" not in (ROOT / "content_brain" / "execution" / "channel_story_ideation.py").read_text(encoding="utf-8"))
    _record("duration_planner_still_two_clips_for_30s", calculate_product_clip_count(30) == 2)

    import project_brain.validate_pwmap_30s_two_clip_duplicate_guard as duplicate_guard  # noqa: E402
    import project_brain.validate_results_run_truth_consistency as truth_validator  # noqa: E402

    _record("duplicate_guard_still_passes", duplicate_guard.main() == PASS, "duplicate_guard")
    _record("results_truth_still_passes", truth_validator.main() == PASS, "results_truth")

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"Passed: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("Failed:", ", ".join(failed))
        return FAIL
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
