"""
Content Brain — user topic authority / preservation audit.

Ensures downstream story generation does not replace the operator's topic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_locale import extract_topic_anchor_tokens

FORBIDDEN_TOPIC_DRIFT: tuple[str, ...] = (
    "astronaut",
    "cyberpunk",
    "neon megacity",
    "space station",
    "alien",
    "robot uprising",
    "medieval castle",
    "dragon",
)

SUBJECT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "man": ("man", "men", "male", "gentleman", "elder", "elderly", "old man", "fisherman", "walker"),
    "woman": ("woman", "women", "female", "lady", "girl"),
    "child": ("child", "kid", "boy", "girl"),
}

ENVIRONMENT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "beach": ("beach", "shore", "shoreline", "coast", "sand", "ocean", "sea", "tide", "waves"),
    "city": ("city", "street", "urban", "downtown", "metropolis", "alley"),
    "forest": ("forest", "woods", "trees", "trail"),
}

ACTION_VERBS: tuple[str, ...] = (
    "walking",
    "walks",
    "walk",
    "running",
    "runs",
    "run",
    "standing",
    "sitting",
    "looking",
    "holding",
    "gazing",
    "fishing",
    "catching",
    "casting",
    "method",
)

TOPIC_DOMAIN_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "fishing": {
        "keywords": (
            "fish",
            "fishing",
            "zander",
            "pike",
            "bass",
            "trout",
            "lure",
            "rod",
            "reel",
            "angler",
            "hook",
            "bait",
            "lake",
            "river",
            "ماهی",
            "صید",
            "قلاب",
        ),
        "subject": ("angler", "fisherman", "fisher", "ماهیگیر"),
        "environment": ("lakeside", "riverbank", "fishing spot", "misty lake", "calm river"),
        "action": ("fishing", "casting", "landing a fish"),
    },
    "cooking": {
        "keywords": ("cook", "recipe", "kitchen", "bake", "food", "dish", "آشپزی", "غذا"),
        "subject": ("home cook", "chef"),
        "environment": ("warm kitchen", "prep counter"),
        "action": ("cooking", "preparing"),
    },
    "fitness": {
        "keywords": ("workout", "gym", "exercise", "training", "fitness", "yoga"),
        "subject": ("athlete", "trainer"),
        "environment": ("gym floor", "training space"),
        "action": ("training", "exercising"),
    },
}


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


@dataclass
class TopicAuthorityResult:
    original_topic: str
    extracted_subject: str
    extracted_environment: str
    extracted_action: str
    preserved_subject: bool = False
    preserved_environment: bool = False
    preserved_action: bool = False
    topic_preservation_score: float = 0.0
    forbidden_drift_detected: list[str] = field(default_factory=list)
    allowed_synonyms_used: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_topic": self.original_topic,
            "extracted_subject": self.extracted_subject,
            "extracted_environment": self.extracted_environment,
            "extracted_action": self.extracted_action,
            "preserved_subject": self.preserved_subject,
            "preserved_environment": self.preserved_environment,
            "preserved_action": self.preserved_action,
            "topic_preservation_score": round(self.topic_preservation_score, 4),
            "forbidden_drift_detected": list(self.forbidden_drift_detected),
            "allowed_synonyms_used": list(self.allowed_synonyms_used),
            "notes": list(self.notes),
        }


def extract_topic_domain(topic: str) -> str:
    cleaned = _normalize(topic)
    for domain, hints in TOPIC_DOMAIN_HINTS.items():
        keywords = hints.get("keywords") or ()
        if any(_topic_keyword_matches(keyword, cleaned) for keyword in keywords):
            return domain
    return ""


def _topic_keyword_matches(keyword: str, text: str) -> bool:
    try:
        from content_brain.execution.content_brain_topic_strategy import topic_keyword_matches

        return topic_keyword_matches(keyword, text)
    except ImportError:  # pragma: no cover
        token = str(keyword or "").strip().lower()
        if len(token) <= 3:
            return bool(re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text))
        return token in text


def extract_topic_facets(topic: str) -> tuple[str, str, str]:
    cleaned = _normalize(topic)
    subject = ""
    environment = ""
    action = ""
    domain = extract_topic_domain(topic)
    domain_hints = TOPIC_DOMAIN_HINTS.get(domain, {})

    action_match = re.search(
        rf"\b({'|'.join(re.escape(v) for v in ACTION_VERBS)})\b",
        cleaned,
        re.I,
    )
    if action_match:
        action = _normalize(action_match.group(1))
    elif domain_hints.get("action"):
        action = str(domain_hints["action"][0])

    env_match = re.search(
        r"\b(on|in|at|along|across|near)\s+(?:a|an|the)\s+([a-z\u0600-\u06FF][\w\u0600-\u06FF\s-]{2,60})",
        cleaned,
        re.I,
    )
    if env_match:
        environment = _normalize(env_match.group(2))
    else:
        for key, synonyms in ENVIRONMENT_SYNONYMS.items():
            if any(word in cleaned for word in synonyms):
                environment = key
                break
        if not environment and domain_hints.get("environment"):
            environment = str(domain_hints["environment"][0])

    patterns = (
        r"\b(an?\s+old\s+[a-z\u0600-\u06FF]+)\b",
        r"\b(an?\s+elderly\s+[a-z\u0600-\u06FF]+)\b",
        r"\b(an?\s+[a-z\u0600-\u06FF]+)\s+(?:walking|standing|running|sitting)\b",
        r"\b(a|an|the)\s+([a-z\u0600-\u06FF][\w\u0600-\u06FF\s-]{2,40}?)\s+(?:walking|standing|running)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.I)
        if match:
            subject = _normalize(match.group(match.lastindex or 1))
            break

    if not subject:
        if "old man" in cleaned:
            subject = "old man"
        elif re.search(r"\b(man|woman|child|person|fisherman|angler)\b", cleaned, re.I):
            subject_match = re.search(r"\b(man|woman|child|person|fisherman|angler)\b", cleaned, re.I)
            if subject_match:
                subject = subject_match.group(1)
        elif domain_hints.get("subject"):
            subject = str(domain_hints["subject"][0])
        else:
            anchors = extract_topic_anchor_tokens(topic, limit=2)
            if anchors:
                subject = " ".join(anchors[:2])

    return subject, environment, action


def audit_topic_preservation(
    original_topic: str,
    *,
    generated_texts: list[str] | None = None,
) -> TopicAuthorityResult:
    topic = str(original_topic or "").strip()
    subject, environment, action = extract_topic_facets(topic)
    result = TopicAuthorityResult(
        original_topic=topic,
        extracted_subject=subject,
        extracted_environment=environment,
        extracted_action=action,
    )
    if not topic:
        result.notes.append("empty_topic")
        return result

    corpus = " ".join([topic] + list(generated_texts or []))
    lowered = _normalize(corpus)

    for forbidden in FORBIDDEN_TOPIC_DRIFT:
        if forbidden in lowered and forbidden not in _normalize(topic):
            result.forbidden_drift_detected.append(forbidden)

    result.preserved_subject = _facet_preserved(subject, lowered, SUBJECT_SYNONYMS)
    result.preserved_environment = _facet_preserved(environment, lowered, ENVIRONMENT_SYNONYMS)
    result.preserved_action = bool(not action or any(v in lowered for v in _action_variants(action)))

    weights = [0.4, 0.35, 0.25]
    flags = [result.preserved_subject, result.preserved_environment, result.preserved_action]
    if not subject:
        weights[0] = 0.0
    if not environment:
        weights[1] = 0.0
    if not action:
        weights[2] = 0.0
    total = sum(weights)
    if total > 0:
        score = sum(w for w, ok in zip(weights, flags) if ok) / total
    else:
        score = _token_preservation_score(topic, lowered)
    if result.forbidden_drift_detected:
        score = max(0.0, score - 0.35 * len(result.forbidden_drift_detected))
    result.topic_preservation_score = round(min(1.0, max(0.0, score)), 4)
    return result


def audit_story_brief_preservation(original_topic: str, story_payload: dict[str, Any]) -> TopicAuthorityResult:
    fields = [
        str(story_payload.get("title") or ""),
        str(story_payload.get("logline") or ""),
        str(story_payload.get("main_character") or ""),
        str(story_payload.get("setting") or ""),
        str(story_payload.get("conflict_tension") or ""),
        str(story_payload.get("visual_hook") or ""),
        str(story_payload.get("emotional_arc") or ""),
        str(story_payload.get("ending_beat") or ""),
    ]
    fields.extend(str(b) for b in story_payload.get("clip_beats") or [])
    result = audit_topic_preservation(original_topic, generated_texts=fields)
    return result


def _facet_preserved(
    facet: str,
    corpus: str,
    synonym_map: dict[str, tuple[str, ...]],
) -> bool:
    if not facet:
        return True
    facet_norm = _normalize(facet)
    if facet_norm in corpus:
        return True
    for key, synonyms in synonym_map.items():
        if key in facet_norm or facet_norm in synonyms:
            if any(word in corpus for word in synonyms):
                return True
    tokens = facet_norm.split()
    return any(token in corpus for token in tokens if len(token) > 2)


def _token_preservation_score(original_topic: str, corpus: str) -> float:
    anchors = extract_topic_anchor_tokens(original_topic, limit=6)
    if not anchors:
        return 0.0
    hits = sum(
        1
        for token in anchors
        if token.lower() in corpus or token in corpus
    )
    ratio = hits / len(anchors)
    if ratio >= 0.75:
        return 1.0
    if ratio >= 0.5:
        return 0.75
    if ratio >= 0.34:
        return 0.5
    return 0.2 if hits else 0.0


def _action_variants(action: str) -> tuple[str, ...]:
    base = _normalize(action)
    variants = {base}
    if base.endswith("ing"):
        variants.add(base[:-3])
        variants.add(base[:-3] + "s")
    if base.endswith("s"):
        variants.add(base[:-1])
    return tuple(variants)


__all__ = [
    "TopicAuthorityResult",
    "audit_story_brief_preservation",
    "audit_topic_preservation",
    "extract_topic_domain",
    "extract_topic_facets",
]
