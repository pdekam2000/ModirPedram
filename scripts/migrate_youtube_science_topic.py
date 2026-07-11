"""One-off migration: YouTube channel topic -> Science That Feels Impossible."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from content_brain.automation.automation_queue import (
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_RUNNING,
    JOB_SKIPPED,
    AutomationQueue,
)
from content_brain.execution.youtube_science_channel import (
    CHANNEL_NAME,
    FORBIDDEN_TOPICS,
    PREFERRED_TOPICS,
    get_youtube_channel_topic_text,
)

TERMINAL = {JOB_COMPLETED, JOB_FAILED, JOB_CANCELLED, JOB_SKIPPED}
STALE_YOUTUBE_MARKERS = (
    "funny and unexpected animal",
    "hilarious fail",
    "dark fantasy",
    "cinematic miniature",
    "entertainment comedy",
    "main channel topic:",
    "cinematic storytelling built around dark fantasy",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    brief = get_youtube_channel_topic_text()

    profile_path = root / "project_brain" / "product_settings" / "channel_profile.json"
    with profile_path.open(encoding="utf-8") as handle:
        profile = json.load(handle)
    instagram_backup = profile.get("instagram_channel_topic")

    profile["channel_name"] = CHANNEL_NAME
    profile["main_niche"] = "Science Education"
    profile["sub_niche"] = "Impossible Science Facts"
    profile["channel_topic"] = brief
    profile["youtube_channel_topic"] = brief
    profile["niche"] = "science documentary"
    profile["genre"] = "science"
    profile["target_audience"] = (
        "Curious adults and teens (16-40) who love surprising science, mystery, "
        "and cinematic visual storytelling."
    )
    profile["tone_style"] = "cinematic intelligent mysterious"
    profile["visual_style"] = "premium cinematic science documentary"
    profile["youtube_video_style"] = "premium cinematic science documentary"
    profile["default_duration_seconds"] = 30
    profile["default_voice"] = "narrative_cinematic_female_presenter"
    profile["preferred_topics"] = PREFERRED_TOPICS
    profile["forbidden_topics"] = list(FORBIDDEN_TOPICS)
    profile["content_formats"] = [
        "Science fact Shorts with recurring presenter",
        "Cinematic visual science explanations",
        "Impossible-fact hook + payoff structure",
    ]
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()

    assert profile.get("instagram_channel_topic") == instagram_backup
    with profile_path.open("w", encoding="utf-8") as handle:
        json.dump(profile, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Updated channel_profile -> {CHANNEL_NAME}")

    queue = AutomationQueue(root)
    cancelled: list[str] = []
    for job in queue.list_jobs():
        if job.status in TERMINAL:
            continue
        platform = str((job.platform_targets[0] if job.platform_targets else "") or "").lower()
        if platform != "youtube_shorts":
            continue
        haystack = f"{job.topic} {job.title}".lower()
        if not any(marker in haystack for marker in STALE_YOUTUBE_MARKERS):
            continue
        if job.status == JOB_RUNNING:
            queue.update_job(job.job_id, status=JOB_FAILED, error="cancelled_stale_youtube_topic_migration")
        else:
            queue.update_job(job.job_id, status=JOB_CANCELLED, error="cancelled_stale_youtube_topic_migration")
        cancelled.append(job.job_id)
    print(f"Cancelled stale YouTube jobs: {len(cancelled)}", cancelled[:10])

    topic_dir = root / "project_brain" / "topic_universe_results"
    for name in ("latest.json", "latest.md", "latest.csv"):
        path = topic_dir / name
        if path.is_file():
            path.unlink()
            print(f"Removed stale topic cache: {path.name}")

    invalidation = {
        "invalidated_at": datetime.now(timezone.utc).isoformat(),
        "reason": "youtube_topic_migration_science_that_feels_impossible",
        "previous_niches": ["dark fantasy", "animal comedy", "cinematic miniature"],
        "new_niche": CHANNEL_NAME,
    }
    marker_path = topic_dir / "INVALIDATED_youtube_science_migration.json"
    marker_path.write_text(json.dumps(invalidation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote invalidation marker: {marker_path.name}")


if __name__ == "__main__":
    main()
