"""Validate Kling Native Audio Audio Strategy Router P2."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.audio.audio_strategy_router import route_audio_strategy  # noqa: E402
from content_brain.execution.kling_native_audio_models import (  # noqa: E402
    KLING_AUDIO_STRATEGY,
    KLING_PROVIDER_ID,
    KLING_SHOT_PROMPT_MAX_CHARS,
)
from ui.api.product_studio_service import ProductStudioService  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_dragon_boy_fantasy_kling() -> None:
    route = route_audio_strategy(topic="A young boy discovers a baby dragon in a fantasy forest cinematic story")
    _pass("dragon_boy_strategy", route.audio_strategy == KLING_AUDIO_STRATEGY)
    _pass("dragon_boy_provider", route.provider_recommendation == KLING_PROVIDER_ID)


def test_animal_story_kling() -> None:
    route = route_audio_strategy(topic="Talking animals adventure in the wild with emotional trust")
    _pass("animal_story_strategy", route.audio_strategy == KLING_AUDIO_STRATEGY)


def test_two_character_emotional_kling() -> None:
    route = route_audio_strategy(
        topic="Two characters share an emotional dialogue-heavy scene with whispers",
        character_count=2,
        dialogue_count=2,
    )
    _pass("two_character_strategy", route.audio_strategy == KLING_AUDIO_STRATEGY)


def test_horror_creature_kling() -> None:
    route = route_audio_strategy(topic="Horror creature growling in a dark corridor with breathing and footsteps")
    _pass("horror_creature_strategy", route.audio_strategy == KLING_AUDIO_STRATEGY)


def test_educational_explainer_narrator() -> None:
    route = route_audio_strategy(topic="Educational explainer about science facts and how to learn")
    _pass("educational_strategy", route.audio_strategy == "narrator")


def test_documentary_mystery_narrator() -> None:
    route = route_audio_strategy(topic="Documentary mystery investigation with historical explanation")
    _pass("documentary_mystery_strategy", route.audio_strategy == "narrator")


def test_luxury_aesthetic_music_only() -> None:
    route = route_audio_strategy(topic="Luxury aesthetic travel reel fashion montage with no dialogue")
    _pass("luxury_aesthetic_strategy", route.audio_strategy == "music_only")


def test_low_confidence_narrator_fallback() -> None:
    route = route_audio_strategy(topic="generic video content sample")
    _pass("low_confidence_strategy", route.audio_strategy == "narrator")
    _pass(
        "low_confidence_override",
        any("low_confidence" in item for item in route.hard_overrides),
    )


def test_kling_provider_metadata() -> None:
    route = route_audio_strategy(topic="Dragon fantasy mini movie with dialogue")
    _pass("kling_provider_id", route.provider_recommendation == KLING_PROVIDER_ID)
    _pass(
        "kling_native_block_provider",
        (route.kling_native_audio or {}).get("provider") == KLING_PROVIDER_ID,
    )


def test_kling_duration_plan_attached() -> None:
    route = route_audio_strategy(topic="Fantasy dragon cinematic story", duration_seconds=30)
    kling = route.kling_native_audio or {}
    _pass("kling_duration_plan_present", bool(kling))
    _pass("kling_clip_count", kling.get("clip_count") == 2)
    _pass("kling_shot_mode", kling.get("shot_mode") == "two_shot_continuity")


def test_kling_disables_elevenlabs() -> None:
    route = route_audio_strategy(topic="Monster creature emotional dialogue scene")
    _pass("route_use_elevenlabs_false", route.use_elevenlabs is False)
    _pass("route_use_external_music_false", route.use_external_music is False)
    _pass("route_native_audio_required", route.native_audio_required is True)
    _pass("route_shot_prompt_max", route.shot_prompt_max_chars == KLING_SHOT_PROMPT_MAX_CHARS)


def test_explicit_narrator_music_unchanged() -> None:
    narrator = route_audio_strategy(topic="Dragon fantasy story", audio_strategy="narrator")
    music = route_audio_strategy(topic="Educational documentary mystery", audio_strategy="music_only")
    _pass("explicit_narrator", narrator.audio_strategy == "narrator")
    _pass("explicit_narrator_provider", narrator.provider_recommendation == "runway")
    _pass("explicit_narrator_elevenlabs", narrator.use_elevenlabs is True)
    _pass("explicit_music", music.audio_strategy == "music_only")
    _pass("explicit_music_no_kling_meta", music.kling_native_audio is None)


def test_preflight_auto_routes_kling() -> None:
    service = ProductStudioService(ROOT)
    pre = service.create_video_preflight(
        {
            "topic_mode": "custom",
            "custom_topic": "Fantasy dragon boy mini movie with dialogue and emotional trust",
            "duration_seconds": 30,
            "audio_strategy": "auto",
            "provider": "auto",
        }
    )
    route = pre.get("audio_strategy_route") or {}
    _pass("preflight_auto_kling_strategy", pre.get("audio_strategy") == KLING_AUDIO_STRATEGY)
    _pass("preflight_auto_kling_provider", pre.get("provider") == KLING_PROVIDER_ID)
    _pass("preflight_route_block", bool(route))
    _pass("preflight_kling_duration_plan", bool(pre.get("kling_duration_plan")))


def main() -> int:
    print("validate_kling_native_audio_router_p2")
    test_dragon_boy_fantasy_kling()
    test_animal_story_kling()
    test_two_character_emotional_kling()
    test_horror_creature_kling()
    test_educational_explainer_narrator()
    test_documentary_mystery_narrator()
    test_luxury_aesthetic_music_only()
    test_low_confidence_narrator_fallback()
    test_kling_provider_metadata()
    test_kling_duration_plan_attached()
    test_kling_disables_elevenlabs()
    test_explicit_narrator_music_unchanged()
    test_preflight_auto_routes_kling()
    print("All Kling Native Audio router P2 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
