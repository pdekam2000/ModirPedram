"""
Domain Knowledge Layer V1 — domain concepts, roles, and beat guidance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_authority import extract_topic_domain


@dataclass
class DomainKnowledgeProfile:
    domain_id: str
    label: str
    concepts: tuple[str, ...]
    default_role_en: str
    default_role_fa: str = ""
    setting_en: str = ""
    instructional_beats_en: tuple[str, ...] = ()
    review_beats_en: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "label": self.label,
            "concepts": list(self.concepts),
            "default_role_en": self.default_role_en,
            "default_role_fa": self.default_role_fa,
            "setting_en": self.setting_en,
            "instructional_beats_en": list(self.instructional_beats_en),
            "review_beats_en": list(self.review_beats_en),
        }


DOMAIN_PROFILES: dict[str, DomainKnowledgeProfile] = {
    "perfume": DomainKnowledgeProfile(
        domain_id="perfume",
        label="Perfume & fragrance",
        concepts=(
            "perfumer",
            "fragrance oils",
            "raw materials",
            "top notes",
            "heart notes",
            "base notes",
            "fixatives",
            "accord",
            "blending",
            "evaluation strip",
            "maceration",
            "longevity",
            "projection",
            "volatility",
            "evaporation",
            "layering",
            "niche perfume",
        ),
        default_role_en="an aspiring perfumer",
        default_role_fa="عطرساز تازه‌کار",
        setting_en="a compact fragrance lab with evaluation strips and raw material bottles",
        instructional_beats_en=(
            "Raw materials and top/heart/base note selection for the topic.",
            "Blending, accord balance, and maceration technique demonstration.",
            "Evaluation strip test, longevity/projection takeaway.",
        ),
        review_beats_en=(
            "Fragrance reveal and first impression on evaluation strip.",
            "Wear test for projection, longevity, and season fit.",
            "Verdict and who this scent is best for.",
        ),
    ),
    "fishing": DomainKnowledgeProfile(
        domain_id="fishing",
        label="Fishing",
        concepts=(
            "angler",
            "lure",
            "bait",
            "hook",
            "cast",
            "retrieve",
            "depth",
            "strike",
            "hook set",
            "water clarity",
            "current",
            "night fishing",
            "shallow water",
            "tackle",
            "rod",
            "reel",
        ),
        default_role_en="an experienced angler",
        setting_en="a readable lakeside or riverbank fishing spot",
        instructional_beats_en=(
            "Lure/bait selection, rig setup, and spot choice.",
            "Casting, retrieve rhythm, and depth strategy.",
            "Strike, hook set, landing, and takeaway lesson.",
        ),
    ),
    "cooking": DomainKnowledgeProfile(
        domain_id="cooking",
        label="Cooking & baking",
        concepts=(
            "baker",
            "flour",
            "hydration",
            "yeast",
            "salt",
            "kneading",
            "gluten",
            "proofing",
            "dough ball",
            "oven spring",
            "crust texture",
            "fermentation",
            "sauce",
            "toppings",
        ),
        default_role_en="a home baker",
        setting_en="a clean kitchen prep counter with flour, yeast, and mixing tools",
        instructional_beats_en=(
            "Ingredients, hydration ratio, and prep setup.",
            "Kneading, gluten development, and shaping.",
            "Proofing, bake, and final texture takeaway.",
        ),
    ),
    "fitness": DomainKnowledgeProfile(
        domain_id="fitness",
        label="Fitness & training",
        concepts=(
            "trainer",
            "workout",
            "form",
            "reps",
            "sets",
            "warm up",
            "recovery",
            "consistency",
            "progression",
        ),
        default_role_en="a focused fitness trainer",
        instructional_beats_en=(
            "Setup, form baseline, and common mistake.",
            "Technique demonstration with clear cues.",
            "Result, progression tip, and takeaway.",
        ),
    ),
    "technology": DomainKnowledgeProfile(
        domain_id="technology",
        label="Technology & AI",
        concepts=(
            "creator",
            "workflow",
            "automation",
            "prompt",
            "tool",
            "productivity",
            "comparison",
            "setup",
            "use case",
            "integration",
        ),
        default_role_en="a focused digital creator",
        setting_en="a modern desk setup with laptop, tools, and readable screen glow",
        instructional_beats_en=(
            "Problem setup and tool/workflow overview.",
            "Step-by-step setup or demonstration.",
            "Result, comparison, and practical takeaway.",
        ),
        review_beats_en=(
            "Claim and product/tool reveal.",
            "Hands-on test and comparison.",
            "Verdict and best use case.",
        ),
    ),
    "history_mystery": DomainKnowledgeProfile(
        domain_id="history_mystery",
        label="Historical mystery & investigation",
        concepts=(
            "historian",
            "researcher",
            "archival records",
            "archaeological evidence",
            "colonial settlement",
            "Roanoke Island",
            "Croatoan",
            "settlers",
            "disappearance theories",
            "expedition",
            "excavation",
            "colony",
            "investigation",
            "historical records",
        ),
        default_role_en="a historical researcher",
        setting_en="Roanoke Island, abandoned colonial settlement, and coastal wilderness research camp",
        instructional_beats_en=(
            "Historical question and settlement context for the case.",
            "Archival records, artifacts, or carved clues compared against official accounts.",
            "Strongest disappearance theory or unresolved historical detail.",
        ),
    ),
    "business_history": DomainKnowledgeProfile(
        domain_id="business_history",
        label="Business history & case study",
        concepts=(
            "business analyst",
            "market disruption",
            "strategy",
            "competition",
            "subscription model",
            "late fees",
            "streaming",
            "digital transformation",
            "bankruptcy",
            "innovation",
            "customer behavior",
            "market share",
        ),
        default_role_en="a business analyst",
        setting_en="boardroom with market charts, product artifacts, and archival business footage",
        instructional_beats_en=(
            "Business context and the central strategic question.",
            "Evidence of the market shift, mistake, or competitive pressure.",
            "Takeaway about adaptation, disruption, or failure to change.",
        ),
    ),
    "mystery": DomainKnowledgeProfile(
        domain_id="mystery",
        label="Mystery & investigation",
        concepts=(
            "clue",
            "investigation",
            "evidence",
            "timeline",
            "contradiction",
            "witness",
            "theory",
            "reveal",
            "expedition tent",
            "footprints",
            "snow",
            "wilderness",
            "case file",
            "archival",
            "Ural Mountains",
        ),
        default_role_en="a careful investigator",
        setting_en="documentary investigation space with evidence boards, maps, and archival photographs",
        instructional_beats_en=(
            "Strange clue or unsettling detail tied to the case.",
            "Investigation escalation with evidence comparison and conflicting reports.",
            "Reveal or open-loop payoff that keeps the central question alive.",
        ),
    ),
    "general": DomainKnowledgeProfile(
        domain_id="general",
        label="General",
        concepts=("method", "technique", "setup", "result", "takeaway", "demonstration"),
        default_role_en="a knowledgeable presenter",
        instructional_beats_en=(
            "Setup and context for the topic.",
            "Core method demonstration.",
            "Result and takeaway.",
        ),
    ),
    "marketing": DomainKnowledgeProfile(
        domain_id="marketing",
        label="Marketing & agencies",
        concepts=(
            "marketing agency",
            "client acquisition",
            "campaign management",
            "media buying",
            "copywriting",
            "creative strategy",
            "performance marketing",
            "marketing operations",
            "AI agents",
            "campaign automation",
            "customer targeting",
            "analytics",
            "retainers",
            "agency economics",
            "brand strategy",
            "client pitch",
        ),
        default_role_en="a marketing strategist",
        setting_en="modern agency war room with campaign dashboards, media plans, and client pitch decks",
        instructional_beats_en=(
            "Claim — frame the boldest business question about agency disruption.",
            "Evidence — compare automation, media buying, and client economics trends.",
            "Counterargument — deliver a nuanced verdict on what survives by 2026.",
        ),
    ),
}

GENERIC_PLACEHOLDER_CONCEPTS: frozenset[str] = frozenset(
    {
        "method",
        "technique",
        "setup",
        "result",
        "takeaway",
        "demonstration",
        "workflow",
        "creator",
        "tool",
        "productivity",
        "use case",
        "integration",
        "comparison",
        "automation",
        "prompt",
    }
)

PROMPT_ENTITY_STOPWORDS: frozenset[str] = frozenset(
    {
        "some",
        "many",
        "why",
        "how",
        "last",
        "all",
        "others",
        "other",
        "thing",
        "stuff",
        "method",
        "technique",
        "perfumes",
        "perfume",
        "day",
        "days",
    }
)

MARKETING_AGENCY_CONCEPTS: tuple[str, ...] = DOMAIN_PROFILES["marketing"].concepts

DOMAIN_ALIASES: dict[str, str] = {
    "fishing": "fishing",
    "cooking": "cooking",
    "fitness": "fitness",
    "technology": "technology",
    "perfume": "perfume",
    "mystery": "mystery",
    "history_mystery": "history_mystery",
    "history": "history_mystery",
    "business_history": "business_history",
    "business": "marketing",
    "news": "general",
    "self_care": "general",
}


def resolve_domain(topic: str, *, topic_category: str = "") -> str:
    domain = extract_topic_domain(topic) or ""
    lowered = str(topic or "").lower()
    if "perfume" in lowered or "fragrance" in lowered or "scent" in lowered or "oud" in lowered:
        return "perfume"
    if "pizza" in lowered or "dough" in lowered or "bread" in lowered or "bake" in lowered:
        return "cooking"
    if "dog" in lowered or "puppy" in lowered or "leash" in lowered or "training" in lowered:
        return "fitness"
    if any(word in lowered for word in ("mystery", "unsolved", "dyatlov", "cold case", "disappearance", "roanoke", "colony", "croatoan")):
        return "mystery"
    if any(word in lowered for word in ("historical", "archaeological", "colonial", "ancient", "empire", "archival")):
        return "history_mystery"
    if any(word in lowered for word in ("blockbuster", "netflix", "kodak", "bankruptcy", "startup failure")):
        return "business_history"
    if any(
        word in lowered
        for word in (
            "marketing agency",
            "marketing agencies",
            "media buying",
            "performance marketing",
            "agency economics",
            "campaign automation",
            "client acquisition",
        )
    ) or ("marketing" in lowered and "agenc" in lowered):
        return "marketing"
    if "graphic designer" in lowered or ("ai" in lowered and any(word in lowered for word in ("replace", "destroy", "disrupt", "forecast"))):
        if "marketing" in lowered or "agenc" in lowered:
            return "marketing"
        return "technology"
    if topic_category and topic_category in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[topic_category]
    return DOMAIN_ALIASES.get(domain, domain or "general")


def get_domain_profile(
    topic: str,
    *,
    topic_category: str = "",
    openai_enrichment: dict[str, Any] | None = None,
) -> DomainKnowledgeProfile:
    if openai_enrichment and openai_enrichment.get("domain_concepts"):
        try:
            from content_brain.execution.content_brain_openai_classification_enricher import (
                OpenAIClassificationPayload,
                build_domain_profile_from_enrichment,
            )

            payload = OpenAIClassificationPayload(
                category=str(openai_enrichment.get("category") or topic_category or "general"),
                strategy=str(openai_enrichment.get("strategy") or "documentary"),
                domain_role=str(openai_enrichment.get("domain_role") or ""),
                domain_concepts=tuple(str(item) for item in openai_enrichment.get("domain_concepts") or ()),
                setting=str(openai_enrichment.get("setting") or ""),
                story_angles=tuple(str(item) for item in openai_enrichment.get("story_angles") or ()),
                seo_title_candidates=tuple(str(item) for item in openai_enrichment.get("seo_title_candidates") or ()),
                confidence=float(openai_enrichment.get("confidence") or 0.0),
            )
            return build_domain_profile_from_enrichment(topic, payload)
        except ImportError:  # pragma: no cover
            pass
    domain_id = resolve_domain(topic, topic_category=topic_category)
    if domain_id == "marketing" and openai_enrichment and openai_enrichment.get("domain_concepts"):
        return build_domain_profile_from_concepts(
            topic,
            list(openai_enrichment.get("domain_concepts") or []),
            topic_category=topic_category,
            base_profile=DOMAIN_PROFILES["marketing"],
        )
    if domain_id == "fitness" and ("dog" in topic.lower() or "puppy" in topic.lower()):
        return DomainKnowledgeProfile(
            domain_id="dog_training",
            label="Dog training",
            concepts=(
                "trainer",
                "puppy",
                "leash",
                "reward",
                "timing",
                "command",
                "recall",
                "crate training",
                "correction",
                "consistency",
            ),
            default_role_en="a patient dog trainer",
            setting_en="a calm training space with leash, treats, and clear sightlines",
            instructional_beats_en=(
                "Setup, command context, and common mistake.",
                "Timing, reward, and technique demonstration.",
                "Result and consistency takeaway.",
            ),
        )
    return DOMAIN_PROFILES.get(domain_id, DOMAIN_PROFILES["general"])


def filter_expert_domain_concepts(concepts: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for item in concepts:
        concept = str(item or "").strip()
        if not concept:
            continue
        lowered = concept.lower()
        if lowered in GENERIC_PLACEHOLDER_CONCEPTS:
            continue
        if lowered in PROMPT_ENTITY_STOPWORDS and len(concept.split()) == 1:
            continue
        if len(concept.split()) == 1 and len(concept) < 4:
            continue
        cleaned.append(concept)
    return list(dict.fromkeys(cleaned))


def filter_prompt_entity_concepts(
    concepts: list[str] | tuple[str, ...],
    *,
    topic: str = "",
) -> list[str]:
    expert = filter_expert_domain_concepts(concepts)
    if not expert and topic:
        profile = get_domain_profile(topic)
        if profile.domain_id != "general":
            expert = list(profile.concepts[:8])
    return expert


def build_domain_profile_from_concepts(
    topic: str,
    concepts: list[str] | tuple[str, ...],
    *,
    topic_category: str = "",
    base_profile: DomainKnowledgeProfile | None = None,
) -> DomainKnowledgeProfile:
    base = base_profile or get_domain_profile(topic, topic_category=topic_category)
    expert = filter_expert_domain_concepts(concepts)
    if not expert:
        return base
    return DomainKnowledgeProfile(
        domain_id=base.domain_id,
        label=base.label,
        concepts=tuple(expert),
        default_role_en=base.default_role_en,
        default_role_fa=base.default_role_fa,
        setting_en=base.setting_en,
        instructional_beats_en=base.instructional_beats_en,
        review_beats_en=base.review_beats_en,
    )


def score_domain_concept_usage(text: str, profile: DomainKnowledgeProfile) -> float:
    lowered = str(text or "").lower()
    if not lowered:
        return 0.0
    hits = 0
    for concept in profile.concepts:
        token = str(concept or "").strip().lower()
        if not token:
            continue
        if " " in token:
            if token in lowered:
                hits += 1
        elif token in lowered:
            hits += 1
    target = max(3, min(len(profile.concepts), 8))
    return min(1.0, hits / target)


__all__ = [
    "DOMAIN_PROFILES",
    "DomainKnowledgeProfile",
    "GENERIC_PLACEHOLDER_CONCEPTS",
    "MARKETING_AGENCY_CONCEPTS",
    "build_domain_profile_from_concepts",
    "filter_expert_domain_concepts",
    "filter_prompt_entity_concepts",
    "PROMPT_ENTITY_STOPWORDS",
    "get_domain_profile",
    "resolve_domain",
    "score_domain_concept_usage",
]
