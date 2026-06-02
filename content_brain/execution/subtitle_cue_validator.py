"""
Phase 11I-4 — in-memory subtitle cue batch validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_brain.execution.subtitle_models import SubtitleCueBatch

VALIDATION_VERSION = "11i4_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_MIN_CUE_DURATION = 0.5
DEFAULT_MAX_CUE_DURATION = 8.0
DEFAULT_OVERLAP_EPSILON = 0.001


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


@dataclass
class SubtitleCueValidationResult:
    passed: bool
    validated_at: str
    cue_count: int = 0
    checks: list[dict[str, Any]] = field(default_factory=list)
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_version": VALIDATION_VERSION,
            "passed": self.passed,
            "validated_at": self.validated_at,
            "cue_count": self.cue_count,
            "checks": list(self.checks),
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
            "warnings": list(self.warnings),
        }


class SubtitleCueValidator:
    """Validate a SubtitleCueBatch before format writers run."""

    def validate(
        self,
        batch: SubtitleCueBatch,
        *,
        min_cue_duration: float = DEFAULT_MIN_CUE_DURATION,
        max_cue_duration: float = DEFAULT_MAX_CUE_DURATION,
        overlap_epsilon: float = DEFAULT_OVERLAP_EPSILON,
    ) -> SubtitleCueValidationResult:
        validated_at = _now()
        checks: list[dict[str, Any]] = []
        reject_reasons: list[str] = []
        warnings: list[str] = []

        cues = list(batch.cues or [])
        if not cues:
            return SubtitleCueValidationResult(
                passed=False,
                validated_at=validated_at,
                cue_count=0,
                checks=[{"id": "CUE_COUNT_POSITIVE", "passed": False}],
                reject_code="CUE_BATCH_EMPTY",
                reject_reasons=["Cue batch is empty."],
            )

        for index, cue in enumerate(cues):
            text_ok = bool(str(cue.text or "").strip())
            checks.append({"id": "TEXT_NON_EMPTY", "passed": text_ok, "cue_index": cue.index})
            if not text_ok:
                reject_reasons.append(f"Cue {cue.index}: empty text")

            start_ok = cue.start_time >= 0
            checks.append({"id": "START_NON_NEGATIVE", "passed": start_ok, "cue_index": cue.index})
            if not start_ok:
                reject_reasons.append(f"Cue {cue.index}: negative start time")

            end_ok = cue.end_time > cue.start_time
            checks.append({"id": "END_AFTER_START", "passed": end_ok, "cue_index": cue.index})
            if not end_ok:
                reject_reasons.append(f"Cue {cue.index}: end must be after start")

            duration = cue.end_time - cue.start_time
            min_ok = duration >= min_cue_duration
            checks.append(
                {
                    "id": "MIN_DURATION",
                    "passed": min_ok,
                    "cue_index": cue.index,
                    "duration": round(duration, 3),
                }
            )
            if not min_ok:
                reject_reasons.append(f"Cue {cue.index}: duration below minimum")

            max_ok = duration <= max_cue_duration
            checks.append(
                {
                    "id": "MAX_DURATION",
                    "passed": max_ok,
                    "cue_index": cue.index,
                    "duration": round(duration, 3),
                }
            )
            if not max_ok:
                warnings.append(f"Cue {cue.index}: duration exceeds recommended maximum")

            if index > 0:
                ordered_ok = cue.start_time >= cues[index - 1].start_time
                checks.append({"id": "ORDERED", "passed": ordered_ok, "cue_index": cue.index})
                if not ordered_ok:
                    reject_reasons.append(f"Cue {cue.index}: timestamps out of order")

                overlap_ok = cue.start_time >= cues[index - 1].end_time - overlap_epsilon
                checks.append({"id": "NO_OVERLAP", "passed": overlap_ok, "cue_index": cue.index})
                if not overlap_ok:
                    reject_reasons.append(f"Cue {cue.index}: overlaps previous cue")

            expected_index = index + 1
            index_ok = cue.index == expected_index
            checks.append({"id": "INDEX_SEQUENTIAL", "passed": index_ok, "cue_index": cue.index})
            if not index_ok:
                reject_reasons.append(f"Cue at position {index + 1}: expected index {expected_index}")

            lowered = str(cue.text or "").lower()
            invalid_highlights = [
                term for term in cue.highlight_terms if term and term not in lowered
            ]
            highlight_ok = not invalid_highlights
            checks.append({"id": "HIGHLIGHT_IN_TEXT", "passed": highlight_ok, "cue_index": cue.index})
            if invalid_highlights:
                warnings.append(
                    f"Cue {cue.index}: highlight terms not in text: {', '.join(invalid_highlights)}"
                )

        language_ok = bool(str(batch.language or "").strip())
        checks.append({"id": "LANGUAGE_PRESENT", "passed": language_ok})
        if not language_ok:
            reject_reasons.append("Batch language is missing.")

        passed = len(reject_reasons) == 0
        return SubtitleCueValidationResult(
            passed=passed,
            validated_at=validated_at,
            cue_count=len(cues),
            checks=checks,
            reject_code=None if passed else "CUE_VALIDATION_FAILED",
            reject_reasons=reject_reasons,
            warnings=warnings,
        )


__all__ = [
    "VALIDATION_VERSION",
    "DEFAULT_MIN_CUE_DURATION",
    "DEFAULT_MAX_CUE_DURATION",
    "SubtitleCueValidationResult",
    "SubtitleCueValidator",
]
