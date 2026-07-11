#!/usr/bin/env python3
"""Launch 45s / 3-clip / private YouTube live retest after root-cause repair."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.automation.automation_queue import AutomationQueue, JOB_PLANNED  # noqa: E402

API_BASE = "http://127.0.0.1:8765"
CENTER_PATH = ROOT / "project_brain" / "automation_center.json"
CHANNEL_PATH = ROOT / "project_brain" / "product_settings" / "channel_profile.json"


def _post(path: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _backup_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _restore_json(path: Path, payload: dict | None) -> None:
    if payload is None:
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    center_backup = _backup_json(CENTER_PATH)
    channel_backup = _backup_json(CHANNEL_PATH)

    try:
        if center_backup is not None:
            center = dict(center_backup)
            youtube = dict(center.get("youtube") or {})
            youtube["default_visibility"] = "private"
            center["youtube"] = youtube
            center["updated_at"] = datetime.now(timezone.utc).isoformat()
            CENTER_PATH.write_text(json.dumps(center, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        if channel_backup is not None:
            channel = dict(channel_backup)
            channel["youtube_privacy"] = "private"
            CHANNEL_PATH.write_text(json.dumps(channel, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        queue = AutomationQueue(ROOT)
        job = queue.create_job(
            {
                "topic": "Science That Feels Impossible — YouTube Shorts",
                "title": "PHASE 45S-3CLIP ROOT CAUSE REPAIR LIVE RETEST",
                "duration": 45,
                "clip_count": 3,
                "platform_targets": ["youtube_shorts"],
                "status": JOB_PLANNED,
                "scheduled_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
            }
        )
        print(f"[OK] Created job: {job.job_id} (45s / 3 clips / youtube_shorts / private)")

        try:
            health = urllib.request.urlopen(f"{API_BASE}/automation/status", timeout=10)
            health.read()
        except urllib.error.URLError as exc:
            raise SystemExit(f"API not reachable at {API_BASE}: {exc}") from exc

        result = _post("/automation/start")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise SystemExit(1)
    finally:
        _restore_json(CENTER_PATH, center_backup)
        _restore_json(CHANNEL_PATH, channel_backup)
        print("[i] Restored automation_center.json and channel_profile.json privacy settings")


if __name__ == "__main__":
    main()
