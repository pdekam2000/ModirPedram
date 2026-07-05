"""Per-platform upload history for Upload Center."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UPLOAD_HISTORY_VERSION = "upload_history_v1"
HISTORY_PATH = Path("project_brain") / "automation" / "upload_history.json"
MAX_ENTRIES_PER_PLATFORM = 50


class UploadHistoryStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / HISTORY_PATH

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": UPLOAD_HISTORY_VERSION, "platforms": {}, "updated_at": ""}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": UPLOAD_HISTORY_VERSION, "platforms": {}, "updated_at": ""}
        if not isinstance(payload, dict):
            return {"version": UPLOAD_HISTORY_VERSION, "platforms": {}, "updated_at": ""}
        payload.setdefault("platforms", {})
        return payload

    def record(
        self,
        *,
        platform: str,
        title: str,
        success: bool,
        run_id: str = "",
        youtube_url: str = "",
        post_url: str = "",
        error: str = "",
        uploaded_at: str = "",
    ) -> dict[str, Any]:
        current = self.load()
        platforms = dict(current.get("platforms") or {})
        history = list(platforms.get(platform) or [])
        resolved_url = str(post_url or youtube_url or "")
        entry = {
            "title": str(title or "Untitled"),
            "uploaded_at": uploaded_at or self._now(),
            "success": bool(success),
            "run_id": str(run_id or ""),
            "youtube_url": resolved_url,
            "post_url": resolved_url,
            "error": str(error or ""),
        }
        history.insert(0, entry)
        platforms[platform] = history[:MAX_ENTRIES_PER_PLATFORM]
        current["platforms"] = platforms
        current["updated_at"] = self._now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        return entry

    def list_for_platform(self, platform: str) -> list[dict[str, Any]]:
        payload = self.load()
        return list((payload.get("platforms") or {}).get(platform) or [])

    def list_all(self) -> dict[str, list[dict[str, Any]]]:
        payload = self.load()
        platforms = dict(payload.get("platforms") or {})
        return {key: list(value or []) for key, value in platforms.items()}


__all__ = ["UploadHistoryStore", "UPLOAD_HISTORY_VERSION"]
