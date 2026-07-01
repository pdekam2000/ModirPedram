"""Validate platform → aspect ratio defaults."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_planner import (
    plan_kling_frame_to_video_content,
    validate_kling_frame_content_plan,
)
from content_brain.platform.platform_aspect_defaults import (
    default_aspect_ratio_for_platform,
    resolve_aspect_ratio,
)
from content_brain.story.story_first_prompt_engine import (
    STORY_FIRST_PROMPT_MIN_CHARS,
    STORY_FIRST_TARGET_STORY_RATIO,
    audit_story_first_prompt,
    find_forbidden_story_metadata,
    validate_cinematic_story_body,
)
from ui.api.product_studio_service import ProductStudioService

ROBOT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "Cinematic emotional sci-fi. Native audio."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_platform_aspect_defaults() -> None:
    _pass("tiktok_9_16", default_aspect_ratio_for_platform("tiktok") == "9:16")
    _pass("reels_9_16", default_aspect_ratio_for_platform("instagram_reels") == "9:16")
    _pass("shorts_9_16", default_aspect_ratio_for_platform("youtube_shorts") == "9:16")
    _pass("long_16_9", default_aspect_ratio_for_platform("youtube_long") == "16:9")
    _pass("multi_9_16", default_aspect_ratio_for_platform("multi") == "9:16")


def test_resolve_aspect_ratio() -> None:
    _pass(
        "stale_16_9_on_shorts_coerced",
        resolve_aspect_ratio(platform="youtube_shorts", aspect_ratio="16:9", aspect_ratio_manual=False) == "9:16",
    )
    _pass(
        "manual_16_9_on_shorts_honored",
        resolve_aspect_ratio(platform="youtube_shorts", aspect_ratio="16:9", aspect_ratio_manual=True) == "16:9",
    )
    _pass("fallback_shorts", resolve_aspect_ratio(platform="youtube_shorts", aspect_ratio="") == "9:16")
    _pass("fallback_long", resolve_aspect_ratio(platform="youtube_long", aspect_ratio=None) == "16:9")


def test_preflight_wires_aspect_ratio() -> None:
    service = ProductStudioService(project_root=ROOT)
    shorts = service.create_video_preflight(
        {
            "platform": "youtube_shorts",
            "duration_seconds": 30,
            "provider": "kling_3_0_pro_native_audio",
            "audio_strategy": "kling_native_audio",
            "custom_topic": ROBOT_TOPIC,
            "topic_mode": "custom",
        }
    )
    _pass("shorts_preflight_aspect", shorts.get("aspect_ratio") == "9:16", str(shorts.get("aspect_ratio")))

    long_form = service.create_video_preflight(
        {
            "platform": "youtube_long",
            "duration_seconds": 30,
            "provider": "kling_3_0_pro_native_audio",
            "audio_strategy": "kling_native_audio",
            "custom_topic": ROBOT_TOPIC,
            "topic_mode": "custom",
        }
    )
    _pass("long_preflight_aspect", long_form.get("aspect_ratio") == "16:9", str(long_form.get("aspect_ratio")))


def test_ui_constants_module() -> None:
    constants = (ROOT / "ui/web/src/product/constants.ts").read_text(encoding="utf-8")
    _pass("constants_tiktok", 'tiktok: "9:16"' in constants)
    _pass("constants_shorts", 'youtube_shorts: "9:16"' in constants)
    _pass("constants_long", 'youtube_long: "16:9"' in constants)
    _pass("constants_youtube_long_option", "YouTube Long" in constants)
    _pass("create_page_auto_aspect", "defaultAspectRatioForPlatform" in (ROOT / "ui/web/src/pages/CreateVideoPage.tsx").read_text(encoding="utf-8"))


def main() -> int:
    print("validate_platform_aspect_ratio_defaults")
    test_platform_aspect_defaults()
    test_resolve_aspect_ratio()
    test_preflight_wires_aspect_ratio()
    test_ui_constants_module()
    print("All platform aspect ratio default checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
