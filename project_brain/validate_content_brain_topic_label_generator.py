"""
Validate Content Brain V8.2 — Topic Label Generator.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_topic_label_generator import (
    FORBIDDEN_LABEL_FRAGMENTS,
    generate_topic_label,
    is_malformed_topic_label,
    score_topic_label_quality,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_chemistry_label() -> None:
    topic = "Can chemistry predict which perfume will become a bestseller?"
    result = generate_topic_label(topic)
    _pass("chemistry_label_present", bool(result.label), result.label)
    _pass("chemistry_label_quality", result.quality_score >= 0.75, str(result.quality_score))
    _pass("chemistry_not_malformed", not is_malformed_topic_label(result.label, topic=topic), result.label)
    _pass("chemistry_not_chemistry_predict", "chemistry predict" not in result.label.lower(), result.label)


def test_ai_perfume_label() -> None:
    topic = "Could AI design a billion-dollar perfume brand by 2030?"
    result = generate_topic_label(topic)
    _pass("ai_perfume_label_quality", result.quality_score >= 0.75, result.label)
    _pass("ai_perfume_no_could", not result.label.lower().startswith("could "), result.label)


def test_roanoke_label() -> None:
    topic = "What really happened to the Roanoke Colony?"
    result = generate_topic_label(topic)
    _pass("roanoke_label_quality", result.quality_score >= 0.75, result.label)
    _pass("roanoke_no_what_really", "what really" not in result.label.lower(), result.label)


def test_bad_labels_rejected() -> None:
    for bad in ("Chemistry Predict", "AI Replace", "Why Did", "What Really"):
        score, warnings = score_topic_label_quality(bad)
        _pass(f"reject_{bad.replace(' ', '_').lower()}", score < 0.75 or bool(warnings), f"{score}:{warnings}")


def test_forbidden_fragments_registered() -> None:
    _pass("forbidden_fragments_present", len(FORBIDDEN_LABEL_FRAGMENTS) >= 5, str(len(FORBIDDEN_LABEL_FRAGMENTS)))


def main() -> None:
    print("[validate_content_brain_topic_label_generator] Content Brain V8.2")
    test_chemistry_label()
    test_ai_perfume_label()
    test_roanoke_label()
    test_bad_labels_rejected()
    test_forbidden_fragments_registered()
    print("[validate_content_brain_topic_label_generator] All checks PASS")


if __name__ == "__main__":
    main()
