"""
Phase 11I-4 — subtitle cue generation engine (in-memory cues only).

No file writes, FFmpeg, or legacy subtitle_engine imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import CATEGORY_VOICE
from content_brain.execution.session_narration_adapter import SessionNarrationAdapter
from content_brain.execution.subtitle_cue_validator import SubtitleCueValidator
from content_brain.execution.subtitle_highlight_terms import (
    cue_highlight_terms,
    resolve_session_highlight_terms,
)
from content_brain.execution.subtitle_models import (
    BATCH_VERSION,
    SubtitleCue,
    SubtitleCueBatch,
    SubtitleTimingStrategy,
)
from content_brain.execution.subtitle_preflight_runtime_slot import (
    SOURCE_UNAVAILABLE,
    _load_voice_manifest,
    resolve_subtitle_source_type,
)
from content_brain.execution.subtitle_text_normalizer import (
    resolve_max_line_length,
    split_into_cue_lines,
)

ENGINE_VERSION = "11i4_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_TOTAL_DURATION = 30.0
MIN_TOTAL_DURATION = 15.0
WORDS_PER_SECOND = 2.8
MIN_CUE_DURATION = 0.8
MAX_CUE_DURATION = 6.0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _segment_id(segment_index: int, beat_id: str | None) -> str:
    if beat_id:
        return f"beat_{beat_id}"
    return f"segment_{segment_index}"


def _resolve_language(session: dict[str, Any], profile: dict[str, Any] | None) -> str:
    profile = _dict(profile)
    language_rules = _dict(profile.get("language_rules"))
    caption = str(language_rules.get("caption_language") or profile.get("language") or "").strip()
    if caption:
        return caption[:2].lower() if len(caption) >= 2 else caption.lower()

    brief = _dict(session.get("brief_snapshot"))
    brief_language = str(brief.get("language") or "").strip()
    if brief_language:
        return brief_language[:2].lower()

    return "en"


def _resolve_total_duration(session: dict[str, Any], manifest: dict[str, Any] | None) -> float:
    if manifest and manifest.get("duration_seconds") is not None:
        try:
            return max(float(manifest["duration_seconds"]), MIN_TOTAL_DURATION)
        except (TypeError, ValueError):
            pass

    brief = _dict(session.get("brief_snapshot"))
    content_format = _dict(brief.get("content_format"))
    if content_format.get("default_duration_seconds") is not None:
        try:
            return max(float(content_format["default_duration_seconds"]), MIN_TOTAL_DURATION)
        except (TypeError, ValueError):
            pass

    runtime = _dict(session.get("execution_runtime"))
    voice_slot = _dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VOICE))
    if voice_slot.get("duration_seconds") is not None:
        try:
            return max(float(voice_slot["duration_seconds"]), MIN_TOTAL_DURATION)
        except (TypeError, ValueError):
            pass

    return DEFAULT_TOTAL_DURATION


def _estimate_total_duration_from_text(total_chars: int) -> float:
    words = max(total_chars / 5, 1)
    return max(MIN_TOTAL_DURATION, words / WORDS_PER_SECOND)


def _voice_segment_durations(manifest: dict[str, Any], segment_count: int) -> list[float] | None:
    files = _list(manifest.get("files"))
    if not files:
        return None

    durations: list[float] = []
    has_explicit = False
    for index in range(segment_count):
        record = next(
            (item for item in files if int(_dict(item).get("segment_index", -1)) == index),
            None,
        )
        if record is None and index < len(files):
            record = files[index]
        record = _dict(record)
        duration = record.get("duration_seconds")
        if duration is None:
            durations.append(0.0)
            continue
        try:
            durations.append(max(float(duration), MIN_CUE_DURATION))
            has_explicit = True
        except (TypeError, ValueError):
            durations.append(0.0)

    if not has_explicit:
        total = manifest.get("duration_seconds")
        if total is None:
            return None
        try:
            total_seconds = float(total)
        except (TypeError, ValueError):
            return None
        if segment_count <= 0:
            return None
        per_segment = total_seconds / segment_count
        return [max(per_segment, MIN_CUE_DURATION) for _ in range(segment_count)]

    if len(durations) < segment_count:
        pad = durations[-1] if durations else MIN_CUE_DURATION
        durations.extend([pad] * (segment_count - len(durations)))
    return durations[:segment_count]


def _allocate_segment_windows(
    segments: list[Any],
    total_duration: float,
) -> list[tuple[float, float]]:
    if not segments:
        return []

    timed: list[tuple[float, float] | None] = []
    for segment in segments:
        start = getattr(segment, "start_second", None)
        end = getattr(segment, "end_second", None)
        if start is not None and end is not None and float(end) > float(start):
            timed.append((float(start), float(end)))
        else:
            timed.append(None)

    if all(item is not None for item in timed):
        return [item for item in timed if item is not None]

    weights = [max(len(getattr(segment, "text", "")), 1) for segment in segments]
    weight_sum = sum(weights)
    cursor = 0.0
    windows: list[tuple[float, float]] = []
    for weight in weights:
        span = total_duration * (weight / weight_sum)
        end = min(total_duration, cursor + span)
        windows.append((cursor, max(end, cursor + MIN_CUE_DURATION)))
        cursor = end
    if windows:
        last_start, _last_end = windows[-1]
        windows[-1] = (last_start, total_duration)
    return windows


def _distribute_cue_times(
    cue_texts: list[str],
    window_start: float,
    window_end: float,
    *,
    confidence: float,
) -> list[tuple[str, float, float, float]]:
    if not cue_texts:
        return []

    span = max(window_end - window_start, MIN_CUE_DURATION * len(cue_texts))
    weights = [max(len(text.split()), 1) for text in cue_texts]
    weight_sum = sum(weights)
    cursor = window_start
    timed: list[tuple[str, float, float, float]] = []

    for index, text in enumerate(cue_texts):
        portion = span * (weights[index] / weight_sum)
        duration = max(MIN_CUE_DURATION, min(portion, MAX_CUE_DURATION))
        if index == len(cue_texts) - 1:
            end = window_end
        else:
            end = min(window_end, cursor + duration)
        if end <= cursor:
            end = cursor + MIN_CUE_DURATION
        timed.append((text, cursor, end, confidence))
        cursor = end

    if timed:
        text, start, _end, conf = timed[-1]
        timed[-1] = (text, start, window_end, conf)

    if len(timed) >= 2:
        last_text, last_start, last_end, last_conf = timed[-1]
        if last_end - last_start < MIN_CUE_DURATION:
            prev_text, prev_start, prev_end, prev_conf = timed[-2]
            timed[-2] = (f"{prev_text} {last_text}".strip(), prev_start, window_end, prev_conf)
            timed.pop()

    return timed


@dataclass
class SubtitleCueGenerationRequest:
    session: dict[str, Any]
    profile: dict[str, Any] | None = None
    channel_identity: dict[str, Any] | None = None
    timing_strategy: str | None = None
    max_line_length: int | None = None
    min_cue_duration: float = MIN_CUE_DURATION
    max_cue_duration: float = MAX_CUE_DURATION


@dataclass
class SubtitleCueGenerationResult:
    passed: bool
    batch: SubtitleCueBatch | None = None
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    generated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "generated_at": self.generated_at,
            "passed": self.passed,
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
            "warnings": list(self.warnings),
            "batch": self.batch.to_dict() if self.batch else None,
        }


class SubtitleCueGenerationEngine:
    """Generate validated subtitle cues from session narration and optional voice timing."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or ".").resolve()
        self.narration_adapter = SessionNarrationAdapter()
        self.cue_validator = SubtitleCueValidator()

    def generate(self, request: SubtitleCueGenerationRequest) -> SubtitleCueGenerationResult:
        session = dict(_dict(request.session))
        profile = _dict(request.profile)
        runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
        voice_slot = dict(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VOICE)))

        bundle = self.narration_adapter.build(session)
        if bundle.skipped or not bundle.segments:
            return SubtitleCueGenerationResult(
                passed=False,
                reject_code="NARRATION_UNAVAILABLE",
                reject_reasons=["No narration segments available for subtitle cue generation."],
            )

        source_type = resolve_subtitle_source_type(session, voice_slot)
        if source_type == SOURCE_UNAVAILABLE:
            return SubtitleCueGenerationResult(
                passed=False,
                reject_code="SOURCE_UNAVAILABLE",
                reject_reasons=["Subtitle source unavailable."],
            )

        manifest = _load_voice_manifest(voice_slot)
        segment_durations = None
        if manifest and source_type == "narration_with_timing":
            segment_durations = _voice_segment_durations(manifest, len(bundle.segments))

        requested = str(request.timing_strategy or "auto").lower()
        if requested == SubtitleTimingStrategy.AUDIO_DURATION.value:
            timing_strategy = SubtitleTimingStrategy.AUDIO_DURATION.value
        elif requested == SubtitleTimingStrategy.EQUAL_CHUNK.value:
            timing_strategy = SubtitleTimingStrategy.EQUAL_CHUNK.value
        elif segment_durations:
            timing_strategy = SubtitleTimingStrategy.AUDIO_DURATION.value
        else:
            timing_strategy = SubtitleTimingStrategy.EQUAL_CHUNK.value

        if timing_strategy == SubtitleTimingStrategy.AUDIO_DURATION.value and not segment_durations:
            timing_strategy = SubtitleTimingStrategy.EQUAL_CHUNK.value

        max_line_length = request.max_line_length or resolve_max_line_length(profile)
        narration_texts = [segment.text for segment in bundle.segments]
        highlight_terms, highlight_sources = resolve_session_highlight_terms(
            session,
            profile=profile,
            channel_identity=request.channel_identity,
            narration_texts=narration_texts,
        )

        warnings = list(bundle.warnings)
        if timing_strategy == SubtitleTimingStrategy.EQUAL_CHUNK.value:
            warnings.append("TIMING_ESTIMATED_EQUAL_CHUNK")

        confidence = 0.85 if timing_strategy == SubtitleTimingStrategy.AUDIO_DURATION.value else 0.6

        if manifest and manifest.get("duration_seconds") is not None:
            total_duration = _resolve_total_duration(session, manifest)
        elif narration_texts:
            total_duration = _estimate_total_duration_from_text(sum(len(text) for text in narration_texts))
        else:
            total_duration = _resolve_total_duration(session, None)

        segment_windows = _allocate_segment_windows(bundle.segments, total_duration)
        audio_windows: list[tuple[float, float]] = []
        if timing_strategy == SubtitleTimingStrategy.AUDIO_DURATION.value and segment_durations:
            cursor = 0.0
            for duration in segment_durations:
                audio_windows.append((cursor, cursor + duration))
                cursor += duration

        cues: list[SubtitleCue] = []
        cue_index = 1

        for seg_idx, segment in enumerate(bundle.segments):
            cue_lines = split_into_cue_lines(segment.text, max_line_length=max_line_length)
            if not cue_lines:
                continue

            if audio_windows and seg_idx < len(audio_windows):
                seg_start, seg_end = audio_windows[seg_idx]
            elif seg_idx < len(segment_windows):
                seg_start, seg_end = segment_windows[seg_idx]
            else:
                seg_start, seg_end = (0.0, total_duration)

            timed_lines = _distribute_cue_times(
                cue_lines,
                seg_start,
                seg_end,
                confidence=confidence,
            )
            segment_key = _segment_id(segment.segment_index, segment.beat_id)
            for text, start, end, cue_confidence in timed_lines:
                cues.append(
                    SubtitleCue(
                        index=cue_index,
                        start_time=round(start, 3),
                        end_time=round(end, 3),
                        text=text,
                        source_segment_id=segment_key,
                        confidence=cue_confidence,
                        highlight_terms=cue_highlight_terms(text, highlight_terms),
                        style_tags=["default"],
                    )
                )
                cue_index += 1

        if not cues:
            return SubtitleCueGenerationResult(
                passed=False,
                reject_code="CUE_BATCH_EMPTY",
                reject_reasons=["No subtitle cues generated from narration."],
                warnings=warnings,
            )

        batch = SubtitleCueBatch(
            cues=cues,
            language=_resolve_language(session, profile),
            source_type=source_type,
            timing_strategy=timing_strategy,
            total_duration=cues[-1].end_time,
            warnings=warnings,
            metadata={
                "engine_version": ENGINE_VERSION,
                "batch_version": BATCH_VERSION,
                "segment_count": bundle.segment_count,
                "highlight_term_sources": highlight_sources,
                "voice_manifest_path": voice_slot.get("voice_manifest_path"),
                "quality_level": 2 if timing_strategy == SubtitleTimingStrategy.AUDIO_DURATION.value else 1,
            },
        )

        validation = self.cue_validator.validate(
            batch,
            min_cue_duration=request.min_cue_duration,
            max_cue_duration=request.max_cue_duration,
        )
        warnings.extend(validation.warnings)
        if not validation.passed:
            return SubtitleCueGenerationResult(
                passed=False,
                batch=batch,
                reject_code=validation.reject_code,
                reject_reasons=list(validation.reject_reasons),
                warnings=warnings,
            )

        return SubtitleCueGenerationResult(
            passed=True,
            batch=batch,
            warnings=warnings,
        )

    def generate_to_dict(self, request: SubtitleCueGenerationRequest) -> dict[str, Any]:
        return self.generate(request).to_dict()


__all__ = [
    "ENGINE_VERSION",
    "SubtitleCueGenerationRequest",
    "SubtitleCueGenerationResult",
    "SubtitleCueGenerationEngine",
]
