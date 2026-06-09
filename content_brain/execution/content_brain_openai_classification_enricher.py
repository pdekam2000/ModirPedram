"""
OpenAI-assisted classification and enrichment fallback for Content Brain.

Used when local classification confidence is weak, category is general, or
domain knowledge is missing. Results are cached by normalized topic + language.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]

from content_brain.execution.content_brain_topic_locale import detect_language_code, extract_topic_anchor_tokens
from content_brain.execution.content_brain_topic_strategy import (
    ContentStrategyPlan,
    TopicClassification,
    build_content_strategy_plan,
)
from content_brain.execution.domain_knowledge_layer import DomainKnowledgeProfile, get_domain_profile

ENRICHMENT_ID = "openai_classification_enricher"
DEFAULT_MODEL = "gpt-4.1-mini"
LOCAL_CONFIDENCE_THRESHOLD = 0.75
MAX_OUTPUT_TOKENS = 1200
REQUEST_TIMEOUT_SECONDS = 45.0

REQUIRED_KEYS = (
    "category",
    "strategy",
    "domain_role",
    "domain_concepts",
    "setting",
    "story_angles",
    "seo_title_candidates",
    "confidence",
)

OPENAI_STRATEGY_ALIASES: dict[str, str] = {
    "business_case_study": "business_case_study",
    "business_history": "business_case_study",
    "documentary_mystery": "historical_investigation",
    "historical_investigation": "historical_investigation",
    "case_study": "business_case_study",
    "documentary": "documentary",
    "comparison": "business_case_study",
    "technology_explainer": "educational_tech",
}


@dataclass
class OpenAIClassificationPayload:
    category: str
    strategy: str
    domain_role: str
    domain_concepts: tuple[str, ...]
    setting: str
    story_angles: tuple[str, ...]
    seo_title_candidates: tuple[str, ...]
    confidence: float = 0.0
    language_code: str = "en"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "strategy": self.strategy,
            "domain_role": self.domain_role,
            "domain_concepts": list(self.domain_concepts),
            "setting": self.setting,
            "story_angles": list(self.story_angles),
            "seo_title_candidates": list(self.seo_title_candidates),
            "confidence": round(self.confidence, 4),
            "language_code": self.language_code,
        }


@dataclass
class ClassificationEnrichmentResult:
    applied: bool = False
    provider: str = ENRICHMENT_ID
    model: str = ""
    trigger_reason: str = ""
    cache_hit: bool = False
    classification: TopicClassification | None = None
    strategy_plan: ContentStrategyPlan | None = None
    enrichment: OpenAIClassificationPayload | None = None
    domain_profile: DomainKnowledgeProfile | None = None
    notes: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "provider": self.provider,
            "model": self.model,
            "trigger_reason": self.trigger_reason,
            "cache_hit": self.cache_hit,
            "classification": self.classification.to_dict() if self.classification else {},
            "strategy_plan": self.strategy_plan.to_dict() if self.strategy_plan else {},
            "enrichment": self.enrichment.to_dict() if self.enrichment else {},
            "domain_profile": self.domain_profile.to_dict() if self.domain_profile else {},
            "notes": list(self.notes),
            "usage": dict(self.usage),
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


class OpenAIClassificationEnricher:
    """Optional LLM classification layer when local rules are weak."""

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        model: str | None = None,
        dry_run: bool | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.model = (model or os.getenv("OPENAI_CLASSIFICATION_MODEL") or DEFAULT_MODEL).strip()
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_CLASSIFICATION_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        root = Path(__file__).resolve().parents[2]
        self.cache_dir = Path(cache_dir or root / "project_brain" / "content_brain_classification_cache")
        self._api_key = ""
        self.enabled = self._resolve_enabled_state() or self.dry_run
        self._client: Any | None = None

    def maybe_enrich(
        self,
        *,
        topic: str,
        classification: TopicClassification,
        language_code: str,
        mood: str = "emotional",
        clip_count: int = 3,
        force: bool = False,
    ) -> ClassificationEnrichmentResult:
        domain_profile = get_domain_profile(topic, topic_category=classification.topic_category)
        should_use, reason = should_use_openai_classification(
            classification,
            domain_profile,
            topic=topic,
        )
        if not force and not should_use:
            return ClassificationEnrichmentResult(
                notes=["openai_classification_not_needed"],
                classification=classification,
            )
        if not self.enabled:
            return ClassificationEnrichmentResult(
                trigger_reason=reason,
                notes=["openai_classification_enricher_disabled"],
                classification=classification,
            )

        normalized = normalize_topic_cache_key(topic, language_code)
        cached = self._read_cache(normalized)
        if cached is not None:
            payload = _parse_openai_payload(cached.get("payload") or {}, language_code)
            if payload is not None:
                return self._build_result(
                    topic=topic,
                    language_code=language_code,
                    mood=mood,
                    clip_count=clip_count,
                    local_classification=classification,
                    payload=payload,
                    trigger_reason=reason,
                    cache_hit=True,
                    usage=dict(cached.get("usage") or {}),
                    estimated_cost_usd=float(cached.get("estimated_cost_usd") or 0.0),
                    notes=["openai_classification_cache_hit"],
                )

        if self.dry_run:
            payload = _build_dry_run_payload(topic, language_code)
            notes = ["openai_classification_dry_run"]
            usage: dict[str, Any] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            cost = 0.0
        else:
            if not self._api_key or OpenAI is None:
                return ClassificationEnrichmentResult(
                    trigger_reason=reason,
                    notes=["openai_client_unavailable"],
                    classification=classification,
                )
            raw, usage, cost = self._call_openai(topic, language_code, classification)
            if not raw:
                return ClassificationEnrichmentResult(
                    trigger_reason=reason,
                    notes=["openai_classification_failed"],
                    classification=classification,
                )
            payload = _parse_openai_payload(raw, language_code)
            if payload is None:
                return ClassificationEnrichmentResult(
                    trigger_reason=reason,
                    notes=["openai_classification_invalid"],
                    classification=classification,
                )
            notes = ["openai_classification_applied"]
            self._write_cache(
                normalized,
                {
                    "topic": topic,
                    "language_code": language_code,
                    "payload": payload.to_dict(),
                    "usage": usage,
                    "estimated_cost_usd": cost,
                },
            )

        return self._build_result(
            topic=topic,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
            local_classification=classification,
            payload=payload,
            trigger_reason=reason,
            cache_hit=False,
            usage=usage,
            estimated_cost_usd=cost,
            notes=notes,
        )

    def _build_result(
        self,
        *,
        topic: str,
        language_code: str,
        mood: str,
        clip_count: int,
        local_classification: TopicClassification,
        payload: OpenAIClassificationPayload,
        trigger_reason: str,
        cache_hit: bool,
        usage: dict[str, Any],
        estimated_cost_usd: float,
        notes: list[str],
    ) -> ClassificationEnrichmentResult:
        merged_classification = apply_openai_classification(local_classification, payload, topic)
        domain_profile = build_domain_profile_from_enrichment(topic, payload)
        strategy_plan = build_content_strategy_plan(
            topic,
            merged_classification,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
        )
        strategy_plan = apply_openai_strategy_overlay(strategy_plan, payload, topic, clip_count)
        if not _topic_preserved(topic, payload, strategy_plan):
            return ClassificationEnrichmentResult(
                trigger_reason=trigger_reason,
                notes=["openai_classification_rejected_topic_drift"],
                classification=local_classification,
            )
        return ClassificationEnrichmentResult(
            applied=True,
            model=self.model,
            trigger_reason=trigger_reason,
            cache_hit=cache_hit,
            classification=merged_classification,
            strategy_plan=strategy_plan,
            enrichment=payload,
            domain_profile=domain_profile,
            notes=notes,
            usage=usage,
            estimated_cost_usd=estimated_cost_usd,
        )

    def _call_openai(
        self,
        topic: str,
        language_code: str,
        classification: TopicClassification,
    ) -> tuple[dict[str, Any], dict[str, Any], float]:
        client = self._client
        if client is None:
            client = OpenAI(api_key=self._api_key, timeout=REQUEST_TIMEOUT_SECONDS)
            self._client = client

        system_prompt = (
            "You classify short-form video topics for a content pipeline. "
            "Return JSON only with keys: category, strategy, domain_role, domain_concepts, "
            "setting, story_angles, seo_title_candidates, confidence. "
            "Write ALL string values in the same language as the user's topic. "
            "Never rename or replace the user's topic. "
            "Use concrete domain concepts, settings, and story angles tied to the topic. "
            "category examples: business_history, technology, history_mystery, fitness, cooking. "
            "strategy examples: business_case_study, historical_investigation, educational_tech, documentary. "
            "domain_role examples: business analyst, historian, technology analyst, investigator. "
            "confidence must be 0.0-1.0."
        )
        user_payload = {
            "topic": topic,
            "language_code": language_code,
            "local_classification": classification.to_dict(),
        }
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=0.35,
                max_tokens=MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception:
            return {}, {}, 0.0

        content = response.choices[0].message.content if response.choices else ""
        usage_obj = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
        }
        cost = _estimate_cost_usd(self.model, usage)
        if not content:
            return {}, usage, cost
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}, usage, cost
        return parsed if isinstance(parsed, dict) else {}, usage, cost

    def _resolve_enabled_state(self) -> bool:
        try:
            engine = self._get_registry_engine()
        except Exception:
            return bool(str(os.getenv("OPENAI_API_KEY") or "").strip())

        for category, provider in (("llm", "openai"), (ProviderRegistryEngine.TREND_ENRICHMENT_CATEGORY, "openai_trend_enricher")):
            if engine.credentials_ready(category, provider):
                creds = engine.get_provider_credentials(category, provider)
                api_key = creds.get("OPENAI_API_KEY", "").strip()
                if api_key:
                    self._api_key = api_key
                    return True

        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if api_key:
            self._api_key = api_key
            return True
        return False

    def _get_registry_engine(self) -> Any:
        if self.registry_engine is not None:
            return self.registry_engine
        if ProviderRegistryEngine is None:
            raise RuntimeError("ProviderRegistryEngine is unavailable.")
        return ProviderRegistryEngine()

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        path = self.cache_dir / f"{cache_key}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{cache_key}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def maybe_enrich_classification(
    *,
    topic: str,
    classification: TopicClassification,
    language_code: str | None = None,
    mood: str = "emotional",
    clip_count: int = 3,
    force: bool = False,
) -> ClassificationEnrichmentResult:
    lang = language_code or detect_language_code(topic)
    enricher = OpenAIClassificationEnricher()
    return enricher.maybe_enrich(
        topic=topic,
        classification=classification,
        language_code=lang,
        mood=mood,
        clip_count=clip_count,
        force=force,
    )


def should_use_openai_classification(
    classification: TopicClassification,
    domain_profile: DomainKnowledgeProfile,
    *,
    topic: str = "",
) -> tuple[bool, str]:
    if classification.topic_category in {"general", ""}:
        return True, "category_general"
    if classification.confidence < LOCAL_CONFIDENCE_THRESHOLD:
        return True, "low_confidence"
    if domain_profile.domain_id == "general":
        return True, "domain_knowledge_missing"
    if topic and classification.topic_category in {"general", "cinematic"} and classification.confidence < 0.8:
        from content_brain.execution.domain_knowledge_layer import score_domain_concept_usage

        if score_domain_concept_usage(topic, domain_profile) < 0.2:
            return True, "domain_knowledge_missing"
    return False, ""


def apply_openai_classification(
    local: TopicClassification,
    payload: OpenAIClassificationPayload,
    topic: str,
) -> TopicClassification:
    category = _sanitize_token(payload.category) or local.topic_category
    strategy = _map_openai_strategy(payload.strategy) or local.content_strategy
    confidence = max(float(local.confidence), float(payload.confidence or 0.0))
    return TopicClassification(
        topic=topic,
        topic_category=category,
        content_strategy=strategy,
        instructional_intent=local.instructional_intent,
        confidence=min(1.0, confidence),
        reasoning=f"OpenAI classification overlay ({payload.category}/{payload.strategy}).",
    )


def apply_openai_strategy_overlay(
    plan: ContentStrategyPlan,
    payload: OpenAIClassificationPayload,
    topic: str,
    clip_count: int,
) -> ContentStrategyPlan:
    beats = list(plan.clip_beats)
    if payload.story_angles:
        beats = [_normalize_beat(angle, topic) for angle in payload.story_angles[:clip_count]]
        while len(beats) < clip_count:
            beats.append(_normalize_beat(payload.story_angles[-1], topic))
    seo_candidates = list(dict.fromkeys(list(payload.seo_title_candidates) + list(plan.seo_title_candidates)))[:6]
    required_terms = tuple(dict.fromkeys(list(payload.domain_concepts) + list(plan.required_terms)))[:12]
    conflict = plan.conflict
    if payload.story_angles:
        conflict = _normalize_beat(payload.story_angles[0], topic)
    visual_hook = plan.visual_hook
    if payload.setting:
        visual_hook = f"Visual anchor in {payload.setting} tied directly to {topic}."
    return ContentStrategyPlan(
        strategy_id=plan.strategy_id,
        label=plan.label,
        purpose=plan.purpose,
        niche_style=plan.niche_style,
        effective_mood=plan.effective_mood,
        clip_beats=beats[:clip_count],
        conflict=conflict,
        visual_hook=visual_hook,
        seo_title_candidates=seo_candidates,
        required_terms=required_terms,
        forbidden_filler=plan.forbidden_filler,
    )


def build_domain_profile_from_enrichment(
    topic: str,
    payload: OpenAIClassificationPayload,
) -> DomainKnowledgeProfile:
    beats = tuple(_normalize_beat(angle, topic) for angle in payload.story_angles[:3]) or (
        f"Context and stakes for {topic}.",
        f"Evidence and comparison around {topic}.",
        f"Takeaway tied to {topic}.",
    )
    return DomainKnowledgeProfile(
        domain_id=_sanitize_token(payload.category) or "general",
        label=f"OpenAI domain: {payload.category or 'general'}",
        concepts=tuple(str(item) for item in payload.domain_concepts if str(item).strip()),
        default_role_en=_normalize_role(payload.domain_role),
        setting_en=str(payload.setting or "").strip(),
        instructional_beats_en=beats,
    )


def build_topic_detail_from_enrichment(
    topic: str,
    payload: OpenAIClassificationPayload,
) -> dict[str, Any]:
    subject = pick_subject_from_topic(topic, payload.domain_concepts)
    return {
        "topic": topic,
        "subject": subject,
        "facts": tuple(payload.story_angles[:2]) if payload.story_angles else (f"The story explores {topic}.",),
        "entities": tuple(payload.domain_concepts[:6]),
        "settings": (payload.setting,) if payload.setting else (),
        "objects": tuple(payload.domain_concepts[:4]),
        "narrative_beats": tuple(_normalize_beat(angle, topic) for angle in payload.story_angles[:3]),
        "source": "openai_classification",
        "match_key": _sanitize_token(payload.category),
    }


def normalize_topic_cache_key(topic: str, language_code: str) -> str:
    normalized = re.sub(r"\s+", " ", str(topic or "").strip().lower())
    digest = hashlib.sha256(f"{language_code}:{normalized}".encode("utf-8")).hexdigest()
    return digest[:20]


def pick_subject_from_topic(topic: str, concepts: tuple[str, ...]) -> str:
    anchors = extract_topic_anchor_tokens(topic, limit=3)
    if anchors:
        return " ".join(anchors[:2]).title()
    if concepts:
        return str(concepts[0])
    cleaned = re.sub(r"^(why did|why|how did|how|what happened to|what really happened to)\s+", "", topic, flags=re.I)
    return cleaned.strip(" ?").title() or topic[:48]


def _parse_openai_payload(raw: dict[str, Any], language_code: str) -> OpenAIClassificationPayload | None:
    if not isinstance(raw, dict):
        return None
    for key in REQUIRED_KEYS:
        if key not in raw:
            return None
    concepts = raw.get("domain_concepts")
    angles = raw.get("story_angles")
    seo = raw.get("seo_title_candidates")
    if not isinstance(concepts, list) or not isinstance(angles, list) or not isinstance(seo, list):
        return None
    if not all(str(item).strip() for item in concepts[:2]) or not all(str(item).strip() for item in angles[:1]):
        return None
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))
    return OpenAIClassificationPayload(
        category=_sanitize_token(str(raw.get("category") or "")),
        strategy=_sanitize_token(str(raw.get("strategy") or "")),
        domain_role=_normalize_role(str(raw.get("domain_role") or "")),
        domain_concepts=tuple(str(item).strip() for item in concepts if str(item).strip()),
        setting=re.sub(r"\s+", " ", str(raw.get("setting") or "").strip()),
        story_angles=tuple(str(item).strip() for item in angles if str(item).strip()),
        seo_title_candidates=tuple(str(item).strip() for item in seo if str(item).strip()),
        confidence=confidence,
        language_code=language_code,
    )


def _build_dry_run_payload(topic: str, language_code: str) -> OpenAIClassificationPayload:
    lowered = topic.lower()
    if "blockbuster" in lowered or "netflix" in lowered:
        return OpenAIClassificationPayload(
            category="business_history",
            strategy="business_case_study",
            domain_role="a business analyst",
            domain_concepts=("Blockbuster", "Netflix", "DVD rental", "late fees", "streaming", "subscription model"),
            setting="abandoned video rental store with DVD shelves and old Blockbuster branding",
            story_angles=(
                "Missed streaming opportunity while Netflix scaled subscriptions.",
                "Late fees versus subscription model changed customer behavior.",
                "Failure to adapt to digital behavior destroyed the business model.",
            ),
            seo_title_candidates=(
                "Why Blockbuster Disappeared",
                "How Netflix Beat Blockbuster",
                "The Business Mistake That Destroyed Blockbuster",
            ),
            confidence=0.86,
            language_code=language_code,
        )
    if "kodak" in lowered:
        return OpenAIClassificationPayload(
            category="business_history",
            strategy="business_case_study",
            domain_role="a business analyst",
            domain_concepts=("Kodak", "film photography", "digital camera", "innovation", "market disruption"),
            setting="legacy film manufacturing floor with archived product displays",
            story_angles=(
                "Kodak invented digital imaging but protected film revenue too long.",
                "Market shifted to digital photography faster than the company adapted.",
                "Strategic hesitation let competitors own the digital transition.",
            ),
            seo_title_candidates=("Why Kodak Failed", "The Kodak Mistake That Changed Photography", "How Kodak Lost the Digital Shift"),
            confidence=0.84,
            language_code=language_code,
        )
    if "graphic designer" in lowered or ("ai" in lowered and "replace" in lowered):
        return OpenAIClassificationPayload(
            category="technology",
            strategy="educational_tech",
            domain_role="a technology analyst",
            domain_concepts=("AI tools", "graphic design", "automation", "creative workflow", "2026"),
            setting="modern design studio with screens showing AI-assisted layout tools",
            story_angles=(
                "Which design tasks AI already automates in 2026.",
                "Where human designers still add irreplaceable value.",
                "How workflows are changing for graphic designers.",
            ),
            seo_title_candidates=(
                "Can AI Replace Graphic Designers in 2026?",
                "What AI Still Cannot Do for Designers",
                "How Designers Should Adapt to AI in 2026",
            ),
            confidence=0.82,
            language_code=language_code,
        )
    return OpenAIClassificationPayload(
        category="general",
        strategy="documentary",
        domain_role="a knowledgeable presenter",
        domain_concepts=tuple(extract_topic_anchor_tokens(topic, limit=4)),
        setting=f"context-rich environment tied to {topic}",
        story_angles=(f"Central question behind {topic}.", f"Evidence around {topic}.", f"What {topic} means now."),
        seo_title_candidates=(topic[:72], f"Why {topic} matters"),
        confidence=0.7,
        language_code=language_code,
    )


def _topic_preserved(topic: str, payload: OpenAIClassificationPayload, plan: ContentStrategyPlan) -> bool:
    from content_brain.execution.content_brain_topic_authority import audit_story_brief_preservation

    story_probe = {
        "logline": " ".join(payload.story_angles[:2]),
        "main_character": payload.domain_role,
        "setting": payload.setting,
        "clip_beats": list(plan.clip_beats),
    }
    audit = audit_story_brief_preservation(topic, story_probe)
    return float(audit.topic_preservation_score) >= 0.34


def _map_openai_strategy(strategy: str) -> str:
    cleaned = _sanitize_token(strategy)
    return OPENAI_STRATEGY_ALIASES.get(cleaned, cleaned or "documentary")


def _sanitize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")


def _normalize_role(role: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(role or "").strip())
    if not cleaned:
        return "a knowledgeable presenter"
    if cleaned.lower().startswith(("a ", "an ", "the ")):
        return cleaned
    article = "an" if cleaned[0].lower() in "aeiou" else "a"
    return f"{article} {cleaned}"


def _normalize_beat(text: str, topic: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if "{topic}" in cleaned:
        return cleaned.format(topic=topic)
    return cleaned


def _estimate_cost_usd(model: str, usage: dict[str, Any]) -> float:
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if "mini" in model.lower():
        return (prompt_tokens * 0.0000004) + (completion_tokens * 0.0000016)
    return (prompt_tokens * 0.0000025) + (completion_tokens * 0.00001)


__all__ = [
    "ClassificationEnrichmentResult",
    "OpenAIClassificationEnricher",
    "OpenAIClassificationPayload",
    "apply_openai_classification",
    "apply_openai_strategy_overlay",
    "build_domain_profile_from_enrichment",
    "build_topic_detail_from_enrichment",
    "maybe_enrich_classification",
    "should_use_openai_classification",
]
