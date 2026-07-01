"""OpenAI vision review for visual continuity verification."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

VISION_REVIEWER_VERSION = "visual_continuity_openai_vision_v1"
VISION_MODEL_PREFERENCE = ("gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1")

VISION_SYSTEM_PROMPT = """You are a visual continuity reviewer for short-form video clips.
Analyze the provided frames and return ONLY valid JSON with:
primary_subject, matches_expected (bool), forbidden_confusion_detected (bool),
forbidden_confusion_label (string or empty), same_species_or_object (bool),
confidence_score (0-100 number), notes (string).
Focus on the main on-screen subject, not background humans unless they dominate frame."""


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _normalize_review(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_subject": str(payload.get("primary_subject") or "").strip(),
        "matches_expected": bool(payload.get("matches_expected")),
        "forbidden_confusion_detected": bool(payload.get("forbidden_confusion_detected")),
        "forbidden_confusion_label": str(payload.get("forbidden_confusion_label") or "").strip(),
        "same_species_or_object": bool(payload.get("same_species_or_object")),
        "confidence_score": float(payload.get("confidence_score") or 0.0),
        "notes": str(payload.get("notes") or "").strip(),
        "source": str(payload.get("source") or "openai"),
        "model": str(payload.get("model") or ""),
    }


def review_frames_with_openai(
    *,
    topic: str,
    expected_subject: str,
    forbidden_confusions: list[str],
    frame_paths: list[str],
    dry_run: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    if dry_run:
        notes.append("openai_vision_dry_run")
        return _normalize_review(
            {
                "primary_subject": expected_subject,
                "matches_expected": True,
                "forbidden_confusion_detected": False,
                "forbidden_confusion_label": "",
                "same_species_or_object": True,
                "confidence_score": 92.0,
                "notes": "Dry-run vision review.",
                "source": "dry_run",
            }
        ), notes

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        notes.append("openai_vision_unavailable")
        return _normalize_review(
            {
                "primary_subject": "",
                "matches_expected": False,
                "forbidden_confusion_detected": False,
                "forbidden_confusion_label": "",
                "same_species_or_object": False,
                "confidence_score": 0.0,
                "notes": "OpenAI vision unavailable.",
                "source": "unavailable",
            }
        ), notes

    usable_frames = [Path(item) for item in frame_paths if Path(item).is_file()]
    if not usable_frames:
        notes.append("openai_vision_no_frames")
        return _normalize_review(
            {
                "primary_subject": "",
                "matches_expected": False,
                "forbidden_confusion_detected": False,
                "forbidden_confusion_label": "",
                "same_species_or_object": False,
                "confidence_score": 0.0,
                "notes": "No analysis frames available.",
                "source": "missing_frames",
            }
        ), notes

    user_payload = {
        "topic": topic,
        "expected_visual_subject": expected_subject,
        "forbidden_confusions": list(forbidden_confusions),
        "questions": [
            "What is the primary subject?",
            "Does it match the expected visual subject?",
            "Any forbidden confusion present?",
            "Same species/object as expected?",
            "Confidence score 0-100?",
        ],
    }
    content: list[dict[str, Any]] = [
        {"type": "text", "text": json.dumps(user_payload, ensure_ascii=False)},
    ]
    for frame in usable_frames[:3]:
        mime = "image/jpeg" if frame.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{_encode_image(frame)}"},
            }
        )

    client = OpenAI(api_key=api_key, timeout=90.0)
    last_error = ""
    for model in VISION_MODEL_PREFERENCE:
        try:
            response = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                temperature=0.2,
                max_tokens=700,
            )
            raw = (response.choices[0].message.content or "").strip()
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                last_error = f"invalid_json:{model}"
                continue
            review = _normalize_review({**payload, "source": "openai", "model": model})
            notes.append(f"openai_vision_applied:{model}")
            return review, notes
        except Exception as exc:  # pragma: no cover
            last_error = f"{model}:{exc}"
            continue

    notes.append(f"openai_vision_failed:{last_error or 'unknown'}")
    return _normalize_review(
        {
            "primary_subject": "",
            "matches_expected": False,
            "forbidden_confusion_detected": False,
            "forbidden_confusion_label": "",
            "same_species_or_object": False,
            "confidence_score": 0.0,
            "notes": last_error or "OpenAI vision failed.",
            "source": "failed",
        }
    ), notes


__all__ = ["VISION_REVIEWER_VERSION", "review_frames_with_openai"]
