"""Topic authority trace — log topic and clip_count at each pipeline boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_topic(value: str) -> str:
    return " ".join(str(value or "").split()).strip().lower()


@dataclass
class TopicAuthorityTrace:
    authoritative_topic: str = ""
    requested_clip_count: int = 0
    topic_mode: str = ""
    stages: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        stage: str,
        *,
        topic: str = "",
        clip_count: int | None = None,
        source: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "stage": stage,
            "topic": str(topic or ""),
            "topic_normalized": normalize_topic(topic),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if clip_count is not None:
            entry["clip_count"] = int(clip_count)
        if source:
            entry["source"] = source
        if extra:
            entry.update(extra)
        self.stages.append(entry)

    def validate_topic(self, stage: str, topic: str) -> bool:
        if not self.authoritative_topic:
            return True
        return normalize_topic(topic) == normalize_topic(self.authoritative_topic)

    def validate_clip_count(self, stage: str, clip_count: int) -> bool:
        if self.requested_clip_count <= 0:
            return True
        return int(clip_count) == int(self.requested_clip_count)

    def mismatch_report(self) -> list[str]:
        issues: list[str] = []
        auth = normalize_topic(self.authoritative_topic)
        for entry in self.stages:
            stage = str(entry.get("stage") or "")
            topic = normalize_topic(str(entry.get("topic") or ""))
            if auth and topic and topic != auth:
                issues.append(f"{stage}: topic mismatch ({entry.get('topic')!r} != {self.authoritative_topic!r})")
            if self.requested_clip_count > 0 and "clip_count" in entry:
                actual = int(entry["clip_count"])
                if actual != self.requested_clip_count:
                    issues.append(
                        f"{stage}: clip_count mismatch ({actual} != {self.requested_clip_count})"
                    )
        return issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "authoritative_topic": self.authoritative_topic,
            "requested_clip_count": self.requested_clip_count,
            "topic_mode": self.topic_mode,
            "stages": list(self.stages),
            "mismatches": self.mismatch_report(),
        }

    def write(self, project_root: str | Path) -> Path:
        root = Path(project_root).resolve()
        out_dir = root / "project_brain" / "runtime_state"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "topic_authority_trace.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path
