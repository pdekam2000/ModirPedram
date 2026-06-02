"""
Phase 11I-4 — subtitle cue data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

BATCH_VERSION = "11i4_v1"


class SubtitleSourceType(str, Enum):
    NARRATION_TEXT_ONLY = "narration_text_only"
    NARRATION_WITH_TIMING = "narration_with_timing"
    UNAVAILABLE = "unavailable"


class SubtitleTimingStrategy(str, Enum):
    EQUAL_CHUNK = "equal_chunk"
    AUDIO_DURATION = "audio_duration"
    WORD_LEVEL = "word_level"
    KARAOKE = "karaoke"


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class SubtitleCue:
    index: int
    start_time: float
    end_time: float
    text: str
    source_segment_id: str | None = None
    confidence: float = 0.6
    highlight_terms: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=lambda: ["default"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start_time": round(self.start_time, 3),
            "end_time": round(self.end_time, 3),
            "text": self.text,
            "source_segment_id": self.source_segment_id,
            "confidence": round(self.confidence, 3),
            "highlight_terms": list(self.highlight_terms),
            "style_tags": list(self.style_tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SubtitleCue:
        data = _dict(payload)
        return cls(
            index=int(data.get("index") or 0),
            start_time=float(data.get("start_time") or 0),
            end_time=float(data.get("end_time") or 0),
            text=str(data.get("text") or ""),
            source_segment_id=data.get("source_segment_id"),
            confidence=float(data.get("confidence") or 0.6),
            highlight_terms=[str(item) for item in _list(data.get("highlight_terms"))],
            style_tags=[str(item) for item in _list(data.get("style_tags"))] or ["default"],
        )


@dataclass
class SubtitleCueBatch:
    cues: list[SubtitleCue]
    language: str
    source_type: str
    timing_strategy: str
    total_duration: float
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    batch_version: str = BATCH_VERSION

    @property
    def cue_count(self) -> int:
        return len(self.cues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_version": self.batch_version,
            "language": self.language,
            "source_type": self.source_type,
            "timing_strategy": self.timing_strategy,
            "total_duration": round(self.total_duration, 3),
            "cue_count": self.cue_count,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "cues": [cue.to_dict() for cue in self.cues],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SubtitleCueBatch:
        data = _dict(payload)
        return cls(
            cues=[SubtitleCue.from_dict(item) for item in _list(data.get("cues"))],
            language=str(data.get("language") or "en"),
            source_type=str(data.get("source_type") or SubtitleSourceType.UNAVAILABLE.value),
            timing_strategy=str(data.get("timing_strategy") or SubtitleTimingStrategy.EQUAL_CHUNK.value),
            total_duration=float(data.get("total_duration") or 0),
            warnings=[str(item) for item in _list(data.get("warnings"))],
            metadata=dict(_dict(data.get("metadata"))),
            batch_version=str(data.get("batch_version") or BATCH_VERSION),
        )


__all__ = [
    "BATCH_VERSION",
    "SubtitleSourceType",
    "SubtitleTimingStrategy",
    "SubtitleCue",
    "SubtitleCueBatch",
]
