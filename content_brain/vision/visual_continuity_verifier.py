"""Visual continuity verifier — score clip frames against visual subject lock."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.director.visual_subject_lock import VisualSubjectLock
from content_brain.vision.frame_extractor import ExtractedFrames
from content_brain.vision.openai_vision_reviewer import review_frames_with_openai

VERIFIER_VERSION = "visual_continuity_verifier_v1"

ISSUE_SUBJECT_MISSING = "subject_missing"
ISSUE_SUBJECT_MISMATCH = "subject_mismatch"
ISSUE_FORBIDDEN_CONFUSION = "forbidden_confusion"
ISSUE_CROSS_CLIP_DRIFT = "cross_clip_drift"
ISSUE_VISION_UNAVAILABLE = "vision_unavailable"


@dataclass
class ClipContinuityResult:
    clip_index: int
    video_path: str
    pass_: bool
    score: float
    expected_subject: str
    detected_subject: str
    similarity_score: float
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: str = ""
    frame_paths: dict[str, str] = field(default_factory=dict)
    vision_review: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "video_path": self.video_path,
            "pass": self.pass_,
            "score": round(self.score, 2),
            "expected_subject": self.expected_subject,
            "detected_subject": self.detected_subject,
            "similarity_score": round(self.similarity_score, 2),
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "notes": self.notes,
            "frame_paths": dict(self.frame_paths),
            "vision_review": dict(self.vision_review),
        }


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _norm(text)) if len(token) >= 4}


def _subject_overlap(expected: str, detected: str) -> float:
    expected_tokens = _tokens(expected)
    detected_tokens = _tokens(detected)
    if not expected_tokens or not detected_tokens:
        return 0.0
    overlap = expected_tokens & detected_tokens
    if overlap:
        return min(100.0, 60.0 + 15.0 * len(overlap))
    if _norm(expected) in _norm(detected) or _norm(detected) in _norm(expected):
        return 85.0
    return 0.0


def _forbidden_hit(detected: str, forbidden: tuple[str, ...]) -> str:
    lowered = _norm(detected)
    for item in forbidden:
        token = _norm(item)
        if token and token in lowered:
            return item
    return ""


def verify_clip_frames(
    *,
    clip_index: int,
    topic: str,
    video_path: str,
    frames: ExtractedFrames,
    visual_subject_lock: VisualSubjectLock | None,
    dry_run: bool = False,
    prior_detected_subjects: list[str] | None = None,
) -> ClipContinuityResult:
    lock = visual_subject_lock
    expected = lock.primary_visual_subject if lock else topic
    forbidden = tuple(lock.forbidden_confusions if lock else ())
    review, review_notes = review_frames_with_openai(
        topic=topic,
        expected_subject=expected,
        forbidden_confusions=list(forbidden),
        frame_paths=frames.frame_paths(),
        dry_run=dry_run,
    )

    detected = str(review.get("primary_subject") or "")
    issues: list[str] = []
    warnings: list[str] = list(review_notes)
    similarity = _subject_overlap(expected, detected)

    if review.get("source") in {"unavailable", "failed", "missing_frames"}:
        issues.append(ISSUE_VISION_UNAVAILABLE)
        warnings.append(str(review.get("notes") or "vision unavailable"))
    if not detected:
        issues.append(ISSUE_SUBJECT_MISSING)
    elif not review.get("matches_expected") and similarity < 70.0:
        issues.append(ISSUE_SUBJECT_MISMATCH)

    confusion = str(review.get("forbidden_confusion_label") or "") or _forbidden_hit(detected, forbidden)
    if review.get("forbidden_confusion_detected") or confusion:
        issues.append(ISSUE_FORBIDDEN_CONFUSION)
        if confusion:
            warnings.append(f"forbidden confusion detected: {confusion}")

    if prior_detected_subjects:
        prior = [_norm(item) for item in prior_detected_subjects if item]
        if prior and detected and _norm(detected) not in prior and similarity < 80.0:
            issues.append(ISSUE_CROSS_CLIP_DRIFT)
            warnings.append(
                f"clip {clip_index} detected '{detected}' differs from prior clip subject '{prior[-1]}'"
            )

    confidence = float(review.get("confidence_score") or 0.0)
    score = 0.0
    if detected:
        score += 25.0
    if review.get("matches_expected") or similarity >= 70.0:
        score += 35.0
    if not confusion and ISSUE_FORBIDDEN_CONFUSION not in issues:
        score += 20.0
    if review.get("same_species_or_object") or similarity >= 80.0:
        score += 10.0
    score += min(10.0, confidence / 10.0)

    passed = score >= 75.0 and ISSUE_FORBIDDEN_CONFUSION not in issues and ISSUE_SUBJECT_MISMATCH not in issues
    if ISSUE_VISION_UNAVAILABLE in issues:
        passed = False
        score = min(score, 40.0)

    return ClipContinuityResult(
        clip_index=clip_index,
        video_path=video_path,
        pass_=passed,
        score=score,
        expected_subject=expected,
        detected_subject=detected,
        similarity_score=similarity,
        issues=list(dict.fromkeys(issues)),
        warnings=warnings,
        notes=str(review.get("notes") or ""),
        frame_paths=frames.to_dict(),
        vision_review=review,
    )


__all__ = [
    "ClipContinuityResult",
    "ISSUE_FORBIDDEN_CONFUSION",
    "ISSUE_SUBJECT_MISMATCH",
    "ISSUE_VISION_UNAVAILABLE",
    "VERIFIER_VERSION",
    "verify_clip_frames",
]
