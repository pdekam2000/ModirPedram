"""Find and test-upload the latest Instagram-specific pwmap run (not YouTube science)."""

from __future__ import annotations

import argparse
from pathlib import Path

from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.instagram_uploader import upload_reel_to_instagram
from content_brain.upload.media_video_resolver import find_latest_run_for_platform, resolve_run_platform


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload latest Instagram beauty run to Instagram Reels")
    parser.add_argument("--dry-run", action="store_true", help="Only print the resolved run/video")
    args = parser.parse_args()

    project_root = Path(".").resolve()
    profile = ProductChannelProfileStore(project_root).load()

    run_id, video_path = find_latest_run_for_platform(project_root, "instagram_reels")
    if not run_id or video_path is None:
        print("No Instagram run with FINAL video found.")
        return 1

    platform = resolve_run_platform(project_root, run_id)
    print("Instagram run found:", run_id)
    print("Platform:", platform)
    print("Video:", video_path)

    if args.dry_run:
        return 0

    result = upload_reel_to_instagram(
        project_root=project_root,
        profile=profile,
        video_path=str(video_path),
        run_id=run_id,
        caption="Honey & Turmeric Glow Mask - Follow for daily beauty recipes!",
        hashtags=["skincare", "diybeauty", "skincarerecipe", "naturalskincare"],
    )
    print("Result:", result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
