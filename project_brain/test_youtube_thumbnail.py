"""Test AI thumbnail generation for the latest YouTube run."""

from __future__ import annotations

import json
from pathlib import Path

from content_brain.branding.thumbnail_generator import generate_and_upload_youtube_thumbnail
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.media_video_resolver import find_latest_run_for_platform, resolve_run_platform


def _latest_youtube_video_id(project_root: Path) -> str:
    history_path = project_root / "project_brain" / "automation" / "upload_history.json"
    if not history_path.is_file():
        return ""
    data = json.loads(history_path.read_text(encoding="utf-8"))
    rows = list((data.get("platforms") or {}).get("youtube_shorts") or [])
    for row in rows:
        if row.get("success") and row.get("youtube_url"):
            url = str(row.get("youtube_url") or row.get("post_url") or "")
            if "watch?v=" in url:
                return url.split("watch?v=", 1)[1].split("&", 1)[0]
    return ""


def main() -> int:
    project_root = Path(".").resolve()
    profile = ProductChannelProfileStore(project_root).load()

    run_id, video_path = find_latest_run_for_platform(project_root, "youtube_shorts")
    if not run_id or video_path is None:
        print("No YouTube run with FINAL video found.")
        return 1

    platform = resolve_run_platform(project_root, run_id)
    video_id = _latest_youtube_video_id(project_root)
    title = str(profile.get("channel_name") or "Science That Feels Impossible")

    print("Run ID:", run_id)
    print("Platform:", platform)
    print("Video:", video_path)
    print("Video ID:", video_id or "(missing — will generate thumbnail only)")

    if not video_id:
        from content_brain.branding.thumbnail_generator import generate_youtube_thumbnail

        result = generate_youtube_thumbnail(
            project_root=project_root,
            video_path=video_path,
            title=title,
            channel_name=title,
        )
        print("Generate only result:", result)
        return 0 if result.get("ok") else 1

    result = generate_and_upload_youtube_thumbnail(
        project_root=project_root,
        profile=profile,
        video_path=video_path,
        video_id=video_id,
        title=title,
        channel_name=title,
    )
    print("ok:", result.get("ok"))
    print("thumbnail_path:", result.get("thumbnail_path"))
    print("upload_status:", (result.get("upload_result") or {}).get("status"))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
