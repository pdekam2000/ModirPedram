"""
Phase 11H-1a — session → narration segments adapter (Content Brain brief only).

Does not use TimelineEngine, full_video_pipeline, or schema_director_shots visual prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VOICE

ENGINE_NAME = "SessionNarrationAdapter"
ENGINE_VERSION = "11h1a_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

SOURCE_BEAT_PLANS = "run_context.story_intelligence.story_architecture.beat_plans"
SOURCE_STORY_BLUEPRINT = "story_blueprint.beats"
SOURCE_NONE = "none"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _text_hash(text: str) -> str:
    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def _parse_narration_from_description(description: str) -> str:
    text = str(description or "").strip()
    if not text:
        return ""
    marker = "NARRATION:"
    upper = text.upper()
    if marker in upper:
        index = upper.index(marker)
        return text[index + len(marker) :].split("|")[0].strip()
    return ""


@dataclass
class NarrationSegment:
    segment_index: int
    clip_number: int | None
    beat_id: str | None
    text: str
    start_second: float | None = None
    end_second: float | None = None
    text_hash: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "clip_number": self.clip_number,
            "beat_id": self.beat_id,
            "text": self.text,
            "start_second": self.start_second,
            "end_second": self.end_second,
            "text_hash": self.text_hash or _text_hash(self.text),
            "source": self.source,
        }


@dataclass
class NarrationBundle:
    adapter_version: str
    adapter_source: str
    provider_category: str
    source_path: str
    segment_count: int
    segments: list[NarrationSegment]
    total_text_length: int
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_version": self.adapter_version,
            "adapter_source": self.adapter_source,
            "provider_category": self.provider_category,
            "source_path": self.source_path,
            "segment_count": self.segment_count,
            "segments": [segment.to_dict() for segment in self.segments],
            "total_text_length": self.total_text_length,
            "warnings": list(self.warnings),
            "skipped": self.skipped,
            "metadata": dict(self.metadata),
        }


class SessionNarrationAdapter:
    """Extract narration text from Content Brain brief_snapshot on execution sessions."""

    def build(self, session: dict[str, Any]) -> NarrationBundle:
        brief = _dict(session.get("brief_snapshot"))
        warnings: list[str] = []

        if _has_visual_only_sources(brief):
            warnings.append(
                "schema_director_shots present but ignored — visual prompts are not narration sources."
            )

        segments, source_path = self._resolve_segments(brief, warnings)
        if not segments:
            warnings.append("No narration segments found in brief_snapshot.")
            return NarrationBundle(
                adapter_version=ENGINE_VERSION,
                adapter_source=ENGINE_NAME,
                provider_category=CATEGORY_VOICE,
                source_path=SOURCE_NONE,
                segment_count=0,
                segments=[],
                total_text_length=0,
                warnings=warnings,
                skipped=True,
                metadata={
                    "adapter_provenance": {
                        "engine": ENGINE_NAME,
                        "engine_version": ENGINE_VERSION,
                        "evaluated_at": _now(),
                    },
                    "status": "skipped",
                },
            )

        total_length = sum(len(segment.text) for segment in segments)
        return NarrationBundle(
            adapter_version=ENGINE_VERSION,
            adapter_source=ENGINE_NAME,
            provider_category=CATEGORY_VOICE,
            source_path=source_path,
            segment_count=len(segments),
            segments=segments,
            total_text_length=total_length,
            warnings=warnings,
            skipped=False,
            metadata={
                "adapter_provenance": {
                    "engine": ENGINE_NAME,
                    "engine_version": ENGINE_VERSION,
                    "evaluated_at": _now(),
                },
                "sources_used": [source_path, "brief_snapshot"],
            },
        )

    def _resolve_segments(
        self,
        brief: dict[str, Any],
        warnings: list[str],
    ) -> tuple[list[NarrationSegment], str]:
        run_context = _dict(brief.get("run_context"))
        story_intelligence = _dict(run_context.get("story_intelligence"))
        story_architecture = _dict(story_intelligence.get("story_architecture"))
        beat_plans = story_architecture.get("beat_plans")
        if isinstance(beat_plans, list) and beat_plans:
            segments = self._segments_from_beat_plans(beat_plans, SOURCE_BEAT_PLANS)
            if segments:
                return segments, SOURCE_BEAT_PLANS

        blueprint = _dict(brief.get("story_blueprint"))
        beats = blueprint.get("beats")
        if isinstance(beats, list) and beats:
            segments = self._segments_from_story_beats(beats, warnings)
            if segments:
                return segments, SOURCE_STORY_BLUEPRINT

        return [], SOURCE_NONE

    def _segments_from_beat_plans(
        self,
        beat_plans: list[Any],
        source: str,
    ) -> list[NarrationSegment]:
        segments: list[NarrationSegment] = []
        for index, raw in enumerate(beat_plans, start=1):
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("narration") or "").strip()
            if not text:
                continue
            segments.append(
                NarrationSegment(
                    segment_index=len(segments) + 1,
                    clip_number=index if raw.get("clip_number") is None else int(raw.get("clip_number") or index),
                    beat_id=str(raw.get("beat_id") or "") or None,
                    text=text,
                    start_second=_float_or_none(raw.get("start_second")),
                    end_second=_float_or_none(raw.get("end_second")),
                    text_hash=_text_hash(text),
                    source=source,
                )
            )
        return segments

    def _segments_from_story_beats(
        self,
        beats: list[Any],
        warnings: list[str],
    ) -> list[NarrationSegment]:
        segments: list[NarrationSegment] = []
        for index, raw in enumerate(beats, start=1):
            if not isinstance(raw, dict):
                continue
            narration = _parse_narration_from_description(str(raw.get("description") or ""))
            if not narration:
                continue
            segments.append(
                NarrationSegment(
                    segment_index=len(segments) + 1,
                    clip_number=index,
                    beat_id=str(raw.get("beat_id") or "") or None,
                    text=narration,
                    start_second=_float_or_none(raw.get("start_second")),
                    end_second=_float_or_none(raw.get("end_second")),
                    text_hash=_text_hash(narration),
                    source=SOURCE_STORY_BLUEPRINT,
                )
            )
        if not segments:
            warnings.append("story_blueprint beats present but no NARRATION: text extracted.")
        return segments


def _has_visual_only_sources(brief: dict[str, Any]) -> bool:
    run_context = _dict(brief.get("run_context"))
    story_intelligence = _dict(run_context.get("story_intelligence"))
    schema_shots = story_intelligence.get("schema_director_shots")
    return isinstance(schema_shots, list) and len(schema_shots) > 0


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "SessionNarrationAdapter",
    "NarrationBundle",
    "NarrationSegment",
    "SOURCE_BEAT_PLANS",
    "SOURCE_STORY_BLUEPRINT",
]
