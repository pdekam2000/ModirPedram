"""Validate platform_daily_scheduler uses per-platform topics (not global channel topic)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.automation.platform_daily_scheduler import build_platform_daily_jobs  # noqa: E402
from content_brain.automation.platform_daily_scheduler_store import PlatformDailySchedulerStore  # noqa: E402
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore  # noqa: E402

PASS = 0
FAIL = 1


def _write_profile(root: Path, *, channel_topic: str, instagram_topic: str, tiktok_topic: str) -> None:
    profile_path = root / "project_brain" / "product_settings" / "channel_profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(
            {
                "channel_name": "Test",
                "main_niche": "beauty tips",
                "channel_topic": channel_topic,
                "tiktok_channel_topic": tiktok_topic,
                "instagram_channel_topic": instagram_topic,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_jobs_use_platform_specific_topics_not_global() -> None:
    """YouTube science + Instagram beauty even when global channel_topic is beauty."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_profile(
            root,
            channel_topic="beauty tips",
            instagram_topic="beauty tips",
            tiktok_topic="men's fashion",
        )
        store = PlatformDailySchedulerStore(root)
        store.save_platform(
            "youtube_shorts",
            {"enabled": True, "topic": "science facts", "videos_per_day": 1, "interval_hours": 4},
        )
        store.save_platform(
            "instagram_reels",
            {"enabled": True, "topic": "beauty tips", "videos_per_day": 1, "interval_hours": 4},
        )
        store.save_platform(
            "tiktok",
            {"enabled": True, "topic": "men's fashion", "videos_per_day": 1, "interval_hours": 4},
        )

        jobs = build_platform_daily_jobs(root)
        by_platform: dict[str, list[str]] = {}
        for job in jobs:
            platform = str((job.get("platform_targets") or [""])[0])
            by_platform.setdefault(platform, []).append(str(job.get("topic") or ""))

        assert "youtube_shorts" in by_platform, by_platform
        assert "instagram_reels" in by_platform, by_platform
        assert by_platform["youtube_shorts"] == ["science facts"], by_platform
        assert by_platform["instagram_reels"] == ["beauty tips"], by_platform
        assert by_platform["tiktok"] == ["men's fashion"], by_platform

        # YouTube must not inherit global/beauty topic from channel profile.
        for topic in by_platform["youtube_shorts"]:
            assert topic != "beauty tips", "YouTube job used global channel topic instead of platform topic"
            assert "science" in topic.lower()


def test_empty_platform_topic_falls_back_to_profile_field_for_that_platform_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_profile(
            root,
            channel_topic="global default topic",
            instagram_topic="instagram from profile",
            tiktok_topic="",
        )
        store = PlatformDailySchedulerStore(root)
        store.save_platform("youtube_shorts", {"enabled": True, "topic": "", "videos_per_day": 1})
        store.save_platform("instagram_reels", {"enabled": True, "topic": "", "videos_per_day": 1})

        jobs = build_platform_daily_jobs(root)
        topics = {str((j.get("platform_targets") or [""])[0]): str(j.get("topic") or "") for j in jobs}

        assert topics["youtube_shorts"] == "global default topic"
        assert topics["instagram_reels"] == "instagram from profile"
        assert topics["youtube_shorts"] != topics["instagram_reels"]


def main() -> int:
    print("validate_platform_daily_scheduler_topics")
    print("=" * 60)
    tests = [
        ("platform_specific_topics_not_global", test_jobs_use_platform_specific_topics_not_global),
        ("profile_fallback_is_platform_scoped", test_empty_platform_topic_falls_back_to_profile_field_for_that_platform_only),
    ]
    failed: list[str] = []
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
        except AssertionError as exc:
            failed.append(name)
            print(f"[FAIL] {name} — {exc}")
        except Exception as exc:
            failed.append(name)
            print(f"[FAIL] {name} — {type(exc).__name__}: {exc}")

    print("=" * 60)
    print(f"TOTAL: {len(tests)}  PASS: {len(tests) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
