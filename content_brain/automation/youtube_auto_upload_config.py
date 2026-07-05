"""YouTube auto-upload configuration — project_brain/automation_center.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUTOMATION_CENTER_VERSION = "automation_center_youtube_v1"
AUTOMATION_CENTER_PATH = Path("project_brain") / "automation_center.json"

DEFAULT_YOUTUBE_CONFIG: dict[str, Any] = {
    "auto_upload_enabled": True,
    "default_visibility": "public",
    "publish_now": True,
    "allow_public_auto_upload": True,
    "require_manual_public_approval": False,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_automation_center(project_root: str | Path) -> dict[str, Any]:
    path = Path(project_root).resolve() / AUTOMATION_CENTER_PATH
    if not path.is_file():
        return {
            "version": AUTOMATION_CENTER_VERSION,
            "youtube": dict(DEFAULT_YOUTUBE_CONFIG),
            "updated_at": "",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    merged_youtube = dict(DEFAULT_YOUTUBE_CONFIG)
    merged_youtube.update(dict(payload.get("youtube") or {}))
    return {
        "version": str(payload.get("version") or AUTOMATION_CENTER_VERSION),
        "youtube": merged_youtube,
        "updated_at": str(payload.get("updated_at") or ""),
    }


def load_youtube_auto_upload_config(project_root: str | Path) -> dict[str, Any]:
    return dict(load_automation_center(project_root).get("youtube") or DEFAULT_YOUTUBE_CONFIG)


__all__ = [
    "AUTOMATION_CENTER_PATH",
    "DEFAULT_YOUTUBE_CONFIG",
    "load_automation_center",
    "load_youtube_auto_upload_config",
]
