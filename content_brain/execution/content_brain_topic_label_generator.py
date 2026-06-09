"""
Content Brain V8.2 — Topic Label Generator.

Converts raw question topics into clean documentary subject labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

FORBIDDEN_LABEL_FRAGMENTS: tuple[str, ...] = (
    "can ",
    "could ",
    "why ",
    "what ",
    "how ",
    "will ",
    "did ",
    "does ",
    "do ",
    "is ",
    "are ",
    " chemistry predict",
    " ai replace",
    " ai design",
    "what really",
    "why did",
)

MALFORMED_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"^(can|could|why|what|how|will|did|does|do)\b",
        r"\b(can|could|why|what|how|will)\b$",
        r"\bchemistry predict\b",
        r"\bai replace\b",
        r"\bai design\b",
        r"\bwhat really\b",
        r"\bwhy did\b",
        r"\bpredict$",
        r"\breplace$",
        r"\bdesign$",
    )
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _title_case(text: str) -> str:
    words = []
    for word in _normalize(text).split():
        if word.lower() in {"ai", "vr", "ar", "ios", "android", "seo", "usb"}:
            words.append(word.upper())
        elif word.lower() in {"of", "the", "and", "in", "to", "a", "an", "by", "for", "vs"} and words:
            words.append(word.lower())
        else:
            words.append(word[:1].upper() + word[1:])
    if words:
        words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


@dataclass
class TopicLabelResult:
    topic: str
    label: str = ""
    quality_score: float = 0.0
    source: str = "local_rules"
    candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "label": self.label,
            "topic_label": self.label,
            "quality_score": round(self.quality_score, 4),
            "topic_label_quality_score": round(self.quality_score, 4),
            "source": self.source,
            "candidates": list(self.candidates),
            "warnings": list(self.warnings),
        }


def score_topic_label_quality(label: str, *, topic: str = "") -> tuple[float, list[str]]:
    warnings: list[str] = []
    cleaned = _normalize(label)
    lowered = cleaned.lower()
    if not cleaned:
        return 0.0, ["empty_label"]
    for fragment in FORBIDDEN_LABEL_FRAGMENTS:
        if fragment in lowered:
            warnings.append(f"forbidden_fragment:{fragment.strip()}")
    for pattern in MALFORMED_LABEL_PATTERNS:
        if pattern.search(cleaned):
            warnings.append(f"malformed_label:{pattern.pattern}")
    if len(cleaned.split()) < 2:
        warnings.append("label_too_short")
    if len(cleaned) > 72:
        warnings.append("label_too_long")
    if topic and cleaned.lower() == _normalize(topic).lower():
        warnings.append("label_equals_raw_topic")
    penalty = min(0.85, len(warnings) * 0.22)
    score = 1.0 - penalty
    return round(max(0.0, min(1.0, score)), 4), warnings


def generate_topic_label(topic: str, *, language_code: str = "en") -> TopicLabelResult:
    del language_code
    cleaned = _normalize(topic).rstrip("?")
    lowered = cleaned.lower()
    candidates: list[str] = []

    if "roanoke" in lowered:
        candidates = ["The Roanoke Colony Mystery", "The Lost Roanoke Colony", "Roanoke Colony Investigation"]
    elif "dyatlov" in lowered:
        candidates = ["The Dyatlov Pass Mystery", "Dyatlov Pass Investigation", "The Dyatlov Incident"]
    elif "chemistry" in lowered and "perfume" in lowered and "bestseller" in lowered:
        candidates = ["Perfume Bestseller Prediction", "Predicting Fragrance Success", "Chemistry and Fragrance Hits"]
    elif "ai" in lowered and "perfume" in lowered and ("billion" in lowered or "brand" in lowered):
        candidates = [
            "AI-Created Luxury Fragrance Brands",
            "The Future of AI Perfume Companies",
            "Billion-Dollar AI Fragrance Brands",
        ]
    elif "ai" in lowered and "marketing agenc" in lowered:
        candidates = ["AI Disruption of Marketing Agencies", "The Future of Marketing Agencies", "AI vs Traditional Agencies"]
    elif "ai" in lowered and "creative profession" in lowered:
        candidates = ["AI and Creative Professions", "Creative Jobs in the AI Era", "AI Disruption of Creative Work"]
    elif "ai" in lowered and "surgeon" in lowered:
        candidates = ["AI Surgeons vs Human Surgeons", "The Future of Surgical AI", "AI in the Operating Room"]
    elif "nokia" in lowered and "android" in lowered:
        candidates = ["Nokia's Android Counterfactual", "Could Nokia Have Survived", "Nokia and the Platform Shift"]
    elif lowered.startswith("what really happened"):
        subject = re.sub(r"^what really happened (?:to|at|in)\s+", "", lowered, flags=re.I).strip(" ?.")
        candidates = [f"The {_title_case(subject)} Mystery", f"What Happened to {_title_case(subject)}", _title_case(subject)]
    elif lowered.startswith("why "):
        remainder = re.sub(r"^why\s+", "", lowered, flags=re.I).strip(" ?.")
        candidates = [f"Why {_title_case(remainder)}", f"The Science Behind {_title_case(remainder)}"]
    elif "how to" in lowered or lowered.startswith("how "):
        remainder = re.sub(r"^(?:how to|how)\s+", "", lowered, flags=re.I).strip(" ?.")
        candidates = [f"How {_title_case(remainder)} Works", _title_case(remainder)]
    else:
        remainder = re.sub(
            r"^(?:can|could|will|what|why|how)\s+",
            "",
            lowered,
            flags=re.I,
        ).strip(" ?.")
        remainder = re.sub(r"\s+by\s+20\d\d\b.*$", "", remainder, flags=re.I)
        remainder = re.sub(r"\s+within the next .*$", "", remainder, flags=re.I)
        if remainder:
            candidates.append(_title_case(remainder[:72]))

    chosen = ""
    for candidate in candidates:
        score, warnings = score_topic_label_quality(candidate, topic=topic)
        if score >= 0.75 and not warnings:
            chosen = candidate
            break
        if not chosen or score > score_topic_label_quality(chosen, topic=topic)[0]:
            chosen = candidate

    if not chosen:
        chosen = _title_case(re.sub(r"^(?:can|could|will|what|why|how)\s+", "", cleaned, flags=re.I))[:72]

    quality, warnings = score_topic_label_quality(chosen, topic=topic)
    return TopicLabelResult(
        topic=topic,
        label=chosen,
        quality_score=quality,
        source="local_rules",
        candidates=candidates,
        warnings=warnings,
    )


def is_malformed_topic_label(label: str, *, topic: str = "") -> bool:
    score, _ = score_topic_label_quality(label, topic=topic)
    return score < 0.75


__all__ = [
    "TopicLabelResult",
    "FORBIDDEN_LABEL_FRAGMENTS",
    "generate_topic_label",
    "is_malformed_topic_label",
    "score_topic_label_quality",
]
