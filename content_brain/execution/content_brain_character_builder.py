"""
Character Builder V3 — domain-aware roles without auxiliary-word drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from content_brain.execution.content_brain_topic_locale import detect_language_code, extract_topic_anchor_tokens, filter_auxiliary_topic_tokens
from content_brain.execution.content_brain_topic_strategy import _detect_historical_investigation
from content_brain.execution.domain_knowledge_layer import get_domain_profile, resolve_domain

BUILDER_VERSION = "character_builder_v3"

BROKEN_CHARACTER_PATTERNS: tuple[str, ...] = (
    "focused subject centered on can you",
    "focused subject centered on to make",
    "focused subject centered on how to",
    "focused subject centered on the best",
    "compelling lead subject with clear silhouette",
    "knowledgeable presenter",
)

EXPLICIT_CHARACTER_PATTERNS: tuple[str, ...] = (
    r"\b(astronaut|detective|survivor|mercenary|artist|hacker|soldier|doctor|pilot|child|woman|man|girl|boy|robot|android|perfumer|angler|baker|trainer|chef|historian|researcher|investigator|narrator)\b",
    r"\b(a|an|the)\s+([a-zA-Z][\w\s-]{2,48}?)\s+(?:standing|walking|sitting|looking|running|holding)\b",
)

HISTORY_MYSTERY_ROLES: tuple[str, ...] = (
    "a historian",
    "a historical researcher",
    "a careful investigator",
    "a historical narrator",
)


@dataclass
class CharacterBuildResult:
    character: str
    domain: str
    source: str
    quality_score: float = 1.0
    warnings: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "character": self.character,
            "domain": self.domain,
            "source": self.source,
            "quality_score": round(self.quality_score, 4),
            "warnings": list(self.warnings or []),
            "builder_version": BUILDER_VERSION,
        }


def build_character(
    topic: str,
    *,
    explicit_character: str = "",
    topic_category: str = "",
    language_code: str | None = None,
) -> CharacterBuildResult:
    lang = language_code or detect_language_code(topic)
    domain = resolve_domain(topic, topic_category=topic_category or "")
    if topic_category == "history_mystery" or _detect_historical_investigation(topic):
        domain = "history_mystery"
    if topic_category == "business_history":
        domain = "business_history"
    profile = get_domain_profile(topic, topic_category=topic_category or domain)
    warnings: list[str] = []

    explicit = _normalize(str(explicit_character or "").strip())
    if explicit:
        score = score_character_quality(explicit, topic, domain)
        return CharacterBuildResult(
            character=explicit,
            domain=domain,
            source="user_explicit",
            quality_score=score,
            warnings=warnings if score >= 0.7 else ["character_quality_low"],
        )

    for pattern in EXPLICIT_CHARACTER_PATTERNS[:1]:
        match = re.search(pattern, topic, re.I)
        if match:
            keyword = match.group(1 if match.lastindex == 1 else 0).lower()
            article = "an" if keyword[0] in "aeiou" else "a"
            return CharacterBuildResult(
                character=f"{article} {keyword}",
                domain=domain,
                source="topic_keyword",
                quality_score=0.9,
            )

    if lang == "fa" and profile.default_role_fa:
        return CharacterBuildResult(
            character=profile.default_role_fa,
            domain=domain,
            source="domain_role",
            quality_score=0.92,
        )

    character = profile.default_role_en
    lowered = topic.lower()
    if domain == "history_mystery" or topic_category == "history_mystery" or _detect_historical_investigation(topic):
        character = _pick_history_mystery_role(topic)
    elif "dog" in lowered or "puppy" in lowered:
        character = "a patient dog trainer"
    elif "pizza" in lowered or "dough" in lowered:
        character = "a home baker"
    elif "perfume" in lowered or "fragrance" in lowered:
        character = "an aspiring perfumer"
    elif any(
        word in lowered
        for word in ("boxing", "boxer", "heavyweight", "knockout", "sparring", "championship", "punch")
    ):
        character = "a dedicated young boxer"
    elif domain == "sports":
        character = "a dedicated young boxer"
    elif domain == "fishing":
        character = "an experienced angler"
    elif domain == "mystery" or any(word in lowered for word in ("mystery", "unsolved", "dyatlov", "case")):
        character = "a careful investigator"
    elif domain == "business_history" or topic_category == "business_history":
        character = "a business analyst"
    elif domain == "technology" or re.search(r"\bai\b", lowered):
        character = "a focused digital creator"

    score = score_character_quality(character, topic, domain)
    if score < 0.7:
        warnings.append("character_quality_low")
    return CharacterBuildResult(
        character=character,
        domain=domain,
        source="domain_role",
        quality_score=score,
        warnings=warnings,
    )


def _pick_history_mystery_role(topic: str) -> str:
    lowered = topic.lower()
    if "archaeolog" in lowered or "excavat" in lowered or "artifact" in lowered:
        return "a historical researcher"
    if "what really happened" in lowered or "what happened" in lowered:
        return "a historian"
    if "mystery" in lowered or "disappearance" in lowered or "vanished" in lowered:
        return "a careful investigator"
    return HISTORY_MYSTERY_ROLES[0]


def score_character_quality(character: str, topic: str, domain: str = "") -> float:
    lowered = _normalize(character).lower()
    if not lowered:
        return 0.0
    if any(broken in lowered for broken in BROKEN_CHARACTER_PATTERNS):
        return 0.15
    anchors = filter_auxiliary_topic_tokens(extract_topic_anchor_tokens(topic, limit=4))
    if anchors and lowered.endswith(f"centered on {' '.join(anchors[:2]).lower()}"):
        if any(aux in lowered for aux in ("can you", "to make", "how to", "the best")):
            return 0.2
    if lowered.startswith("a focused subject centered on"):
        return 0.25
    profile = get_domain_profile(topic, topic_category=domain)
    if any(
        role_word in lowered
        for role_word in (
            "perfumer",
            "angler",
            "baker",
            "trainer",
            "creator",
            "investigator",
            "chef",
            "historian",
            "researcher",
            "narrator",
        )
    ):
        return 0.92
    if profile.default_role_en.lower() in lowered:
        return 0.9
    return 0.75


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


__all__ = [
    "BUILDER_VERSION",
    "BROKEN_CHARACTER_PATTERNS",
    "CharacterBuildResult",
    "build_character",
    "score_character_quality",
]
