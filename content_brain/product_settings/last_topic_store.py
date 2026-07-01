"""Persist last Product Studio custom topic across sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRODUCT_SETTINGS_SUBDIR = Path("project_brain") / "product_settings"
LAST_TOPIC_FILENAME = "last_topic.json"

DEFAULT_LAST_TOPIC: dict[str, Any] = {
    "topic": "",
    "topic_mode": "custom",
    "updated_at": "",
}


class ProductLastTopicStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.topic_path = self.project_root / PRODUCT_SETTINGS_SUBDIR / LAST_TOPIC_FILENAME

    def load(self) -> dict[str, Any]:
        if not self.topic_path.is_file():
            return dict(DEFAULT_LAST_TOPIC)
        try:
            payload = json.loads(self.topic_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_LAST_TOPIC)
        if not isinstance(payload, dict):
            return dict(DEFAULT_LAST_TOPIC)
        merged = dict(DEFAULT_LAST_TOPIC)
        merged.update(payload)
        return merged

    def save(self, *, topic: str, topic_mode: str = "custom") -> dict[str, Any]:
        cleaned = str(topic or "").strip()
        payload = {
            "topic": cleaned,
            "topic_mode": str(topic_mode or "custom"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.topic_path.parent.mkdir(parents=True, exist_ok=True)
        self.topic_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload


__all__ = ["ProductLastTopicStore", "LAST_TOPIC_FILENAME", "DEFAULT_LAST_TOPIC"]
