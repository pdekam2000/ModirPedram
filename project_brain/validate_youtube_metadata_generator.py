"""Validation — PHASE YT-1 YouTube metadata generator foundation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_live_post_processor import (  # noqa: E402
    ASSEMBLY_ASSEMBLED,
    PUBLISH_CREATED,
    run_publish_package,
)
from content_brain.publish.youtube_metadata_generator import (  # noqa: E402
    YOUTUBE_METADATA_FILENAME,
    ensure_product_studio_publish_metadata,
    generate_youtube_metadata,
    generate_and_save_youtube_metadata,
    load_youtube_metadata,
)

PASS = 0
FAIL = 1
results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _profile() -> dict:
    return {
        "channel_name": "Modir Demo Channel",
        "main_niche": "animation",
        "language": "English",
        "upload_platforms": ["youtube_shorts"],
        "youtube_default_hashtags": ["shorts", "ai"],
        "ai_creation_disclosure_enabled": True,
        "youtube_made_for_kids": False,
        "cta_text": "Subscribe for more cinematic stories.",
    }


def main() -> int:
    print("validate_youtube_metadata_generator")
    print("=" * 60)

    profile = _profile()
    topic = "Honor demogogon animation reveal"

    meta_short = generate_youtube_metadata(
        topic=topic,
        channel_profile=profile,
        duration_seconds=30,
        clip_count=2,
        platform_targets=["youtube_shorts"],
        story_hook="A mythic figure steps out of shadow.",
    )
    _record("title_generated", bool(meta_short.get("title")), meta_short.get("title", ""))
    _record("description_generated", bool(meta_short.get("description")), str(len(meta_short.get("description", ""))))
    _record("tags_generated", len(meta_short.get("tags") or []) >= 5, str(len(meta_short.get("tags") or [])))
    hashtags = list(meta_short.get("hashtags") or [])
    _record(
        "hashtags_generated",
        3 <= len(hashtags) <= 10,
        str(len(hashtags)),
    )
    lowered = [item.lower() for item in hashtags]
    _record("hashtags_no_duplicates", len(lowered) == len(set(lowered)), str(hashtags))
    _record("thumbnail_prompt_generated", bool(meta_short.get("thumbnail_prompt")), meta_short.get("thumbnail_prompt", "")[:80])
    _record("shorts_format", meta_short.get("video_format") == "shorts", str(meta_short.get("video_format")))
    _record(
        "shorts_title_present",
        "short" in str(meta_short.get("title") or "").lower() or len(meta_short.get("short_title") or "") > 0,
        meta_short.get("short_title", ""),
    )

    meta_long = generate_youtube_metadata(
        topic=topic,
        channel_profile={**profile, "upload_platforms": ["youtube"]},
        duration_seconds=120,
        clip_count=4,
        platform_targets=["youtube"],
    )
    _record("long_video_format", meta_long.get("video_format") == "long", str(meta_long.get("video_format")))
    _record("long_form_description", "long-form" in str(meta_long.get("description") or "").lower(), "long-form mention")

    with tempfile.TemporaryDirectory() as tmp:
        publish_dir = Path(tmp) / "publish"
        saved = generate_and_save_youtube_metadata(
            publish_dir=publish_dir,
            topic=topic,
            channel_profile=profile,
            duration_seconds=45,
            clip_count=2,
        )
        target = publish_dir / YOUTUBE_METADATA_FILENAME
        _record("metadata_saved_in_publish_package", target.is_file(), str(target))
        loaded = load_youtube_metadata(publish_dir)
        _record(
            "metadata_roundtrip",
            loaded is not None and loaded.get("title") == saved.get("title"),
            str(loaded.get("title") if loaded else ""),
        )

        video = Path(tmp) / "video.mp4"
        video.write_bytes(b"\x00" * 2_000_000)
        product_info = ensure_product_studio_publish_metadata(
            project_root=ROOT,
            run_dir=Path(tmp) / "pwmap_test_run",
            topic=topic,
            video_path=str(video),
            channel_profile=profile,
            duration_seconds=30,
            clip_count=2,
        )
        publish_path = Path(str(product_info.get("publish_package_path") or ""))
        _record(
            "product_studio_publish_package_created",
            publish_path.is_dir() and (publish_path / YOUTUBE_METADATA_FILENAME).is_file(),
            str(publish_path),
        )

    assembly_manifest = {
        "status": ASSEMBLY_ASSEMBLED,
        "output_path": str(ROOT / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"),
    }
    final_video = ROOT / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
    if not final_video.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            final_video = tmp_root / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
            final_video.parent.mkdir(parents=True, exist_ok=True)
            final_video.write_bytes(b"\x00" * 2_000_000)
            assembly_manifest["output_path"] = str(final_video)
            manifest = run_publish_package(
                tmp_root,
                assembly_manifest=assembly_manifest,
                run_id="yt1_publish_test",
                topic=topic,
                clip_count=2,
                downloaded_file_paths=[str(final_video)],
            )
            package_dir = Path(str(manifest.get("package_folder") or ""))
            _record(
                "runway_publish_package_youtube_metadata",
                manifest.get("status") == PUBLISH_CREATED
                and (package_dir / YOUTUBE_METADATA_FILENAME).is_file(),
                str(manifest.get("youtube_metadata_path") or ""),
            )
    else:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            staged = tmp_root / "outputs" / "final" / "FINAL_RUNWAY_PHASE_I_VIDEO.mp4"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(final_video.read_bytes())
            manifest = run_publish_package(
                tmp_root,
                assembly_manifest={**assembly_manifest, "output_path": str(staged)},
                run_id="yt1_publish_test",
                topic=topic,
                clip_count=2,
                downloaded_file_paths=[str(staged)],
            )
            package_dir = Path(str(manifest.get("package_folder") or ""))
            _record(
                "runway_publish_package_youtube_metadata",
                manifest.get("status") == PUBLISH_CREATED
                and (package_dir / YOUTUBE_METADATA_FILENAME).is_file(),
                str(manifest.get("youtube_metadata_path") or ""),
            )

    generator_src = (ROOT / "content_brain" / "publish" / "youtube_metadata_generator.py").read_text(encoding="utf-8")
    _record(
        "no_youtube_api_imports",
        "googleapiclient" not in generator_src
        and "youtube.googleapis.com" not in generator_src
        and "google.oauth2" not in generator_src,
        "static scan",
    )

    def _blocked_urlopen(*args, **kwargs):
        url = str(args[0] if args else kwargs.get("url") or "")
        if "youtube" in url.lower() or "googleapis" in url.lower():
            raise AssertionError(f"YouTube API call attempted: {url}")
        raise OSError("network disabled in validation")

    with patch("urllib.request.urlopen", side_effect=_blocked_urlopen):
        blocked_meta = generate_youtube_metadata(
            topic=topic,
            channel_profile=profile,
            duration_seconds=30,
        )
    _record(
        "no_youtube_api_calls_at_runtime",
        bool(blocked_meta.get("title")),
        blocked_meta.get("title", ""),
    )

    required_fields = (
        "title",
        "short_title",
        "description",
        "tags",
        "hashtags",
        "category",
        "language",
        "made_for_kids",
        "thumbnail_prompt",
        "cta_text",
        "seo_keywords",
        "publish_summary",
    )
    _record(
        "schema_fields_present",
        all(field in meta_short for field in required_fields),
        ", ".join(field for field in required_fields if field not in meta_short),
    )

    failed = [name for name, ok, _ in results if not ok]
    print("=" * 60)
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return FAIL
    print("ALL PASS")
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
