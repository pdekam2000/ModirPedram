"""
Intent Intelligence Layer — detects what the user is really asking before strategy selection.

Pipeline position:
  Topic → Classification → Intent Detection → Strategy Selection → Story
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]

from content_brain.execution.content_brain_topic_strategy import (
    STRATEGY_BUSINESS_CASE_STUDY,
    STRATEGY_BUSINESS_DEBATE,
    STRATEGY_CINEMATIC_NARRATIVE,
    STRATEGY_EDUCATIONAL_TECH,
    STRATEGY_FUTURE_ANALYSIS,
    STRATEGY_HISTORICAL_INVESTIGATION,
    STRATEGY_INSTRUCTIONAL_FISHING,
    STRATEGY_INSTRUCTIONAL_GENERAL,
    STRATEGY_NARRATIVE_MYSTERY,
    STRATEGY_RECIPE_TUTORIAL,
    STRATEGY_SCIENTIFIC_EXPLANATION,
    STRATEGY_TECHNOLOGY_FORECAST,
    ContentStrategyPlan,
    TopicClassification,
    TUTORIAL_STRATEGIES,
    build_content_strategy_plan,
    topic_keyword_matches,
)

INTENT_LAYER_VERSION = "intent_intelligence_v2"
INTENT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_OUTPUT_TOKENS = 1400
REQUEST_TIMEOUT_SECONDS = 45.0

INTENT_TUTORIAL = "tutorial"
INTENT_INSTRUCTIONAL = "instructional"
INTENT_FUTURE_PREDICTION = "future_prediction"
INTENT_BUSINESS_CASE_STUDY = "business_case_study"
INTENT_BUSINESS_DEBATE = "business_debate"
INTENT_INDUSTRY_DISRUPTION = "industry_disruption"
INTENT_HISTORICAL_INVESTIGATION = "historical_investigation"
INTENT_DOCUMENTARY = "documentary"
INTENT_MYSTERY = "mystery"
INTENT_SCIENTIFIC_EXPLANATION = "scientific_explanation"
INTENT_TECHNOLOGY_FORECAST = "technology_forecast"
INTENT_MARKET_FORECAST = "market_forecast"

TUTORIAL_MARKERS: tuple[str, ...] = (
    "how to",
    "how-to",
    "step by step",
    "step-by-step",
    "tutorial",
    "guide",
    "recipe",
    "method",
    "technique",
)

FUTURE_MARKERS: tuple[str, ...] = (
    "by 2026",
    "by 2027",
    "by 2028",
    "by 2029",
    "by 2030",
    "in 2026",
    "in 2027",
    "in 2030",
    "will ai",
    "can ai",
    "going to replace",
    "take over",
    "destroy",
    "future of",
    "next decade",
)

DISRUPTION_MARKERS: tuple[str, ...] = (
    "disrupt",
    "disruption",
    "replace",
    "obsolete",
    "agencies",
    "agency",
    "industry",
    "traditional",
    "survive",
)

SCIENTIFIC_MARKERS: tuple[str, ...] = (
    "why do",
    "why does",
    "why is",
    "how does",
    "how do",
    "what makes",
    "last all day",
    "last longer",
    "science",
    "molecule",
    "chemistry",
)

BUSINESS_CASE_MARKERS: tuple[str, ...] = (
    "why did",
    "why was",
    "why has",
    "what went wrong",
    "rise and fall",
    "failed",
    "disappear",
    "bankruptcy",
)

INTENT_TO_STRATEGY: dict[str, str] = {
    INTENT_TUTORIAL: STRATEGY_RECIPE_TUTORIAL,
    INTENT_INSTRUCTIONAL: STRATEGY_INSTRUCTIONAL_GENERAL,
    INTENT_FUTURE_PREDICTION: STRATEGY_FUTURE_ANALYSIS,
    INTENT_INDUSTRY_DISRUPTION: STRATEGY_BUSINESS_DEBATE,
    INTENT_BUSINESS_DEBATE: STRATEGY_BUSINESS_DEBATE,
    INTENT_BUSINESS_CASE_STUDY: STRATEGY_BUSINESS_CASE_STUDY,
    INTENT_HISTORICAL_INVESTIGATION: STRATEGY_HISTORICAL_INVESTIGATION,
    INTENT_MYSTERY: STRATEGY_NARRATIVE_MYSTERY,
    INTENT_TECHNOLOGY_FORECAST: STRATEGY_TECHNOLOGY_FORECAST,
    INTENT_MARKET_FORECAST: STRATEGY_FUTURE_ANALYSIS,
    INTENT_SCIENTIFIC_EXPLANATION: STRATEGY_SCIENTIFIC_EXPLANATION,
    INTENT_DOCUMENTARY: STRATEGY_CINEMATIC_NARRATIVE,
}


@dataclass
class IntentDetectionResult:
    topic: str
    primary_intent: str
    secondary_intents: list[str] = field(default_factory=list)
    recommended_strategy: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    source: str = "local_rules"
    alternative_intents: list[str] = field(default_factory=list)
    domain_concepts: list[str] = field(default_factory=list)
    story_angles: list[str] = field(default_factory=list)
    seo_title_candidates: list[str] = field(default_factory=list)
    openai_applied: bool = False
    cache_hit: bool = False
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "primary_intent": self.primary_intent,
            "secondary_intents": list(self.secondary_intents),
            "recommended_strategy": self.recommended_strategy,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "source": self.source,
            "alternative_intents": list(self.alternative_intents),
            "domain_concepts": list(self.domain_concepts),
            "story_angles": list(self.story_angles),
            "seo_title_candidates": list(self.seo_title_candidates),
            "openai_applied": self.openai_applied,
            "cache_hit": self.cache_hit,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


@dataclass
class IntentResolutionResult:
    intent: IntentDetectionResult
    classification: TopicClassification
    strategy_plan: ContentStrategyPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "classification": self.classification.to_dict(),
            "strategy_plan": self.strategy_plan.to_dict() if self.strategy_plan else {},
        }


class OpenAIIntentEnricher:
    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        model: str | None = None,
        dry_run: bool | None = None,
        cache_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.model = (model or os.getenv("OPENAI_INTENT_MODEL") or DEFAULT_MODEL).strip()
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_INTENT_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.cache_dir = os.path.join(root, "project_brain", "content_brain_intent_cache")
        if cache_dir:
            self.cache_dir = str(cache_dir)
        self._api_key = ""
        self.enabled = self._resolve_enabled_state() or self.dry_run
        self._client: Any | None = None

    def maybe_enrich(
        self,
        *,
        topic: str,
        classification: TopicClassification,
        local_intent: IntentDetectionResult,
        language_code: str = "en",
    ) -> IntentDetectionResult:
        should_use, reason = should_use_openai_intent(local_intent, classification)
        if not should_use:
            local_intent.reasoning = f"{local_intent.reasoning} | openai_skipped: {reason}"
            return local_intent
        if not self.enabled:
            local_intent.reasoning = f"{local_intent.reasoning} | openai_intent_disabled"
            return local_intent

        cache_key = _cache_key(topic, language_code, classification.topic_category)
        cached = self._read_cache(cache_key)
        if cached is not None:
            parsed = _parse_openai_intent_payload(cached.get("payload") or {}, topic)
            if parsed is not None:
                parsed.cache_hit = True
                parsed.openai_applied = True
                parsed.source = "openai_cache"
                parsed.estimated_cost_usd = float(cached.get("estimated_cost_usd") or 0.0)
                return parsed

        if self.dry_run:
            payload = _build_dry_run_intent(topic, classification)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            cost = 0.0
            notes_source = "openai_intent_dry_run"
        else:
            if not self._api_key or OpenAI is None:
                return local_intent
            payload, usage, cost = self._call_openai(topic, classification, local_intent, language_code)
            if payload is None:
                return local_intent
            notes_source = "openai_intent_applied"

        payload.openai_applied = True
        payload.source = notes_source
        payload.estimated_cost_usd = cost
        self._write_cache(
            cache_key,
            {
                "topic": topic,
                "language_code": language_code,
                "payload": payload.to_dict(),
                "usage": usage,
                "estimated_cost_usd": cost,
            },
        )
        return payload

    def _call_openai(
        self,
        topic: str,
        classification: TopicClassification,
        local_intent: IntentDetectionResult,
        language_code: str,
    ) -> tuple[IntentDetectionResult | None, dict[str, Any], float]:
        client = self._client
        if client is None:
            client = OpenAI(api_key=self._api_key, timeout=REQUEST_TIMEOUT_SECONDS)
            self._client = client
        system_prompt = (
            "You detect content intent for short-form video topics. Return JSON only. "
            "Never change the topic language. Choose the best storytelling intent and strategy. "
            "Do not classify prediction/disruption questions as tutorials."
        )
        user_payload = {
            "topic": topic,
            "language_code": language_code,
            "local_category": classification.topic_category,
            "local_strategy": classification.content_strategy,
            "local_intent": local_intent.primary_intent,
            "local_confidence": local_intent.confidence,
            "allowed_intents": list(INTENT_TO_STRATEGY.keys()),
            "allowed_strategies": sorted(set(INTENT_TO_STRATEGY.values())),
            "required_output": {
                "intent": "primary intent id",
                "strategy": "recommended strategy id",
                "reasoning": "short explanation",
                "confidence": "0.0-1.0",
                "alternative_intents": ["..."],
                "domain_concepts": ["topic-specific concepts"],
                "story_angles": ["3 short angles"],
                "seo_title_candidates": ["5 natural titles"],
            },
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
            return None, {}, 0.0
        content = response.choices[0].message.content if response.choices else ""
        usage_obj = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
        }
        cost = _estimate_cost_usd(self.model, usage)
        if not content:
            return None, usage, cost
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            return None, usage, cost
        parsed = _parse_openai_intent_payload(raw, topic)
        return parsed, usage, cost

    def _resolve_enabled_state(self) -> bool:
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if api_key:
            self._api_key = api_key
            return True
        try:
            if ProviderRegistryEngine is None:
                return False
            engine = ProviderRegistryEngine()
            for category, provider in (("llm", "openai"), (ProviderRegistryEngine.TREND_ENRICHMENT_CATEGORY, "openai_trend_enricher")):
                if engine.credentials_ready(category, provider):
                    creds = engine.get_provider_credentials(category, provider)
                    key = creds.get("OPENAI_API_KEY", "").strip()
                    if key:
                        self._api_key = key
                        return True
        except Exception:
            return False
        return False

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)


def resolve_topic_intent(
    topic: str,
    classification: TopicClassification,
    *,
    language_code: str = "en",
    mood: str = "emotional",
    clip_count: int = 3,
    use_openai: bool = True,
) -> IntentResolutionResult:
    local = detect_local_intent(topic, classification)
    intent = local
    if use_openai:
        enricher = OpenAIIntentEnricher()
        enriched = enricher.maybe_enrich(
            topic=topic,
            classification=classification,
            local_intent=local,
            language_code=language_code,
        )
        if enriched.openai_applied and _should_prefer_openai_intent(local, enriched):
            intent = enriched

    updated = apply_intent_to_classification(classification, intent)
    strategy_plan = build_content_strategy_plan(
        topic,
        updated,
        language_code=language_code,
        mood=mood,
        clip_count=clip_count,
    )
    if intent.seo_title_candidates:
        merged = list(dict.fromkeys(intent.seo_title_candidates + strategy_plan.seo_title_candidates))[:8]
        strategy_plan.seo_title_candidates = merged
    if intent.story_angles and len(intent.story_angles) >= clip_count:
        strategy_plan.clip_beats = list(intent.story_angles[:clip_count])
    return IntentResolutionResult(intent=intent, classification=updated, strategy_plan=strategy_plan)


def detect_local_intent(topic: str, classification: TopicClassification) -> IntentDetectionResult:
    cleaned = _normalize(topic)
    secondary: list[str] = []
    alternatives: list[str] = []

    if classification.instructional_intent or _is_tutorial_intent(cleaned, classification):
        strategy = _tutorial_strategy_for_category(classification)
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_TUTORIAL,
            recommended_strategy=strategy,
            confidence=max(0.9, float(classification.confidence or 0.0)),
            reasoning="Instructional or tutorial intent detected.",
            source="local_rules",
        )

    if classification.content_strategy == STRATEGY_HISTORICAL_INVESTIGATION:
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_HISTORICAL_INVESTIGATION,
            recommended_strategy=STRATEGY_HISTORICAL_INVESTIGATION,
            confidence=0.96,
            reasoning="Historical investigation pattern detected.",
            source="local_rules",
        )

    if _is_business_case_intent(cleaned):
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_BUSINESS_CASE_STUDY,
            recommended_strategy=STRATEGY_BUSINESS_CASE_STUDY,
            confidence=0.93,
            reasoning="Business rise/fall or failure question detected.",
            source="local_rules",
        )

    if _is_scientific_explanation_intent(cleaned):
        from content_brain.execution.domain_knowledge_layer import get_domain_profile, resolve_domain

        domain_id = resolve_domain(cleaned, topic_category=classification.topic_category)
        profile = get_domain_profile(cleaned, topic_category=classification.topic_category)
        concepts = list(profile.concepts[:10])
        story_angles = (
            "Explain the core mechanism behind the question with visible evidence and science.",
            "Compare the key factors because concentration, molecules, and skin chemistry change the outcome.",
            "Deliver a practical takeaway grounded in domain-specific evidence and longevity detail.",
        )
        if domain_id == "perfume":
            story_angles = (
                "Explain why some perfumes fade quickly while others linger all day with visible evidence and science.",
                "Compare molecules, concentration, base notes, fixatives, projection, and skin chemistry because volatility drives longevity.",
                "Deliver practical takeaways grounded in concentration, evidence, and lasting mechanism.",
            )
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_SCIENTIFIC_EXPLANATION,
            recommended_strategy=STRATEGY_SCIENTIFIC_EXPLANATION,
            confidence=0.9,
            reasoning="Scientific why/how explanation question detected.",
            source="local_rules",
            domain_concepts=concepts,
            story_angles=story_angles,
        )

    if _is_mystery_intent(cleaned):
        strategy = (
            STRATEGY_HISTORICAL_INVESTIGATION
            if classification.topic_category in {"history_mystery", "history"}
            else STRATEGY_NARRATIVE_MYSTERY
        )
        intent = INTENT_HISTORICAL_INVESTIGATION if strategy == STRATEGY_HISTORICAL_INVESTIGATION else INTENT_MYSTERY
        return IntentDetectionResult(
            topic=topic,
            primary_intent=intent,
            recommended_strategy=strategy,
            confidence=0.91,
            reasoning="Mystery or unsolved-case intent detected.",
            source="local_rules",
        )

    if _is_future_disruption_intent(cleaned):
        secondary = []
        if _has_markers(cleaned, DISRUPTION_MARKERS):
            secondary.append(INTENT_INDUSTRY_DISRUPTION)
        if _has_markers(cleaned, FUTURE_MARKERS) or "replace" in cleaned or "will ai" in cleaned:
            secondary.append(INTENT_FUTURE_PREDICTION)
        if "designer" in cleaned or "graphic" in cleaned or "developer" in cleaned:
            primary = INTENT_TECHNOLOGY_FORECAST
            strategy = STRATEGY_TECHNOLOGY_FORECAST
            alternatives = [INTENT_FUTURE_PREDICTION]
        elif "marketing" in cleaned or "agency" in cleaned or "agencies" in cleaned:
            primary = INTENT_INDUSTRY_DISRUPTION
            strategy = STRATEGY_BUSINESS_DEBATE
            secondary = [INTENT_FUTURE_PREDICTION, INTENT_BUSINESS_DEBATE]
            alternatives = [INTENT_MARKET_FORECAST]
        else:
            primary = INTENT_FUTURE_PREDICTION
            strategy = STRATEGY_FUTURE_ANALYSIS
            alternatives = [INTENT_TECHNOLOGY_FORECAST, INTENT_INDUSTRY_DISRUPTION]
        return IntentDetectionResult(
            topic=topic,
            primary_intent=primary,
            secondary_intents=secondary,
            recommended_strategy=strategy,
            confidence=0.92,
            reasoning="Future prediction or industry disruption question detected.",
            source="local_rules",
            alternative_intents=alternatives,
        )

    if classification.content_strategy in TUTORIAL_STRATEGIES and not classification.instructional_intent:
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_DOCUMENTARY,
            recommended_strategy=STRATEGY_CINEMATIC_NARRATIVE,
            confidence=0.62,
            reasoning="Category mapped to tutorial strategy but question is not instructional.",
            source="local_rules",
            alternative_intents=[INTENT_FUTURE_PREDICTION, INTENT_BUSINESS_DEBATE],
        )

    strategy = classification.content_strategy or STRATEGY_CINEMATIC_NARRATIVE
    return IntentDetectionResult(
        topic=topic,
        primary_intent=_strategy_to_intent(strategy),
        recommended_strategy=strategy,
        confidence=float(classification.confidence or 0.55),
        reasoning=classification.reasoning or "Classification strategy retained.",
        source="local_rules",
    )


def apply_intent_to_classification(
    classification: TopicClassification,
    intent: IntentDetectionResult,
) -> TopicClassification:
    strategy = intent.recommended_strategy or classification.content_strategy
    instructional = intent.primary_intent in {INTENT_TUTORIAL, INTENT_INSTRUCTIONAL}
    category = classification.topic_category
    if intent.primary_intent in {INTENT_INDUSTRY_DISRUPTION, INTENT_BUSINESS_DEBATE} and "marketing" in intent.topic.lower():
        category = "business"
    if intent.primary_intent == INTENT_TECHNOLOGY_FORECAST:
        category = "technology"
    if intent.primary_intent == INTENT_SCIENTIFIC_EXPLANATION and classification.topic_category in {"general", "self_care"}:
        category = classification.topic_category or "perfume"
    if intent.primary_intent == INTENT_MYSTERY and "dyatlov" in intent.topic.lower():
        category = "history_mystery"
    return TopicClassification(
        topic=classification.topic,
        topic_category=category,
        content_strategy=strategy,
        instructional_intent=instructional,
        confidence=max(float(classification.confidence or 0.0), float(intent.confidence or 0.0)),
        reasoning=f"{classification.reasoning} | intent={intent.primary_intent}: {intent.reasoning}",
    )


def should_use_openai_intent(
    intent: IntentDetectionResult,
    classification: TopicClassification,
) -> tuple[bool, str]:
    if intent.confidence < INTENT_CONFIDENCE_THRESHOLD:
        return True, f"intent_confidence<{INTENT_CONFIDENCE_THRESHOLD}"
    if classification.content_strategy in TUTORIAL_STRATEGIES and intent.primary_intent not in {
        INTENT_TUTORIAL,
        INTENT_INSTRUCTIONAL,
    }:
        return True, "strategy_intent_mismatch"
    if intent.primary_intent in {INTENT_DOCUMENTARY} and intent.confidence < 0.75:
        return True, "ambiguous_intent"
    if classification.topic_category == "technology" and _is_question_form(intent.topic) and not classification.instructional_intent:
        if classification.content_strategy == STRATEGY_EDUCATIONAL_TECH:
            return True, "technology_question_not_tutorial"
    return False, "local_intent_sufficient"


def maybe_enrich_intent(**kwargs: Any) -> IntentDetectionResult:
    enricher = OpenAIIntentEnricher()
    return enricher.maybe_enrich(**kwargs)


def _parse_openai_intent_payload(raw: dict[str, Any], topic: str) -> IntentDetectionResult | None:
    if not isinstance(raw, dict):
        return None
    intent = _sanitize_intent(str(raw.get("intent") or raw.get("primary_intent") or ""))
    strategy = _sanitize_strategy(str(raw.get("strategy") or raw.get("recommended_strategy") or ""))
    if not intent:
        intent = _strategy_to_intent(strategy)
    if not strategy:
        strategy = INTENT_TO_STRATEGY.get(intent, STRATEGY_CINEMATIC_NARRATIVE)
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    alternatives = [str(item).strip() for item in raw.get("alternative_intents") or [] if str(item).strip()]
    concepts = [str(item).strip() for item in raw.get("domain_concepts") or [] if str(item).strip()]
    angles = [str(item).strip() for item in raw.get("story_angles") or [] if str(item).strip()]
    seo = [str(item).strip() for item in raw.get("seo_title_candidates") or [] if str(item).strip()]
    return IntentDetectionResult(
        topic=topic,
        primary_intent=intent,
        secondary_intents=[item for item in alternatives if item != intent][:3],
        recommended_strategy=strategy,
        confidence=min(1.0, max(0.0, confidence)),
        reasoning=str(raw.get("reasoning") or "OpenAI intent enrichment."),
        source="openai",
        alternative_intents=alternatives[:5],
        domain_concepts=concepts[:12],
        story_angles=angles[:5],
        seo_title_candidates=seo[:8],
    )


def _build_dry_run_intent(topic: str, classification: TopicClassification) -> IntentDetectionResult:
    lowered = topic.lower()
    if "marketing agencies" in lowered or ("ai" in lowered and "agency" in lowered and "2026" in lowered):
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_INDUSTRY_DISRUPTION,
            secondary_intents=[INTENT_FUTURE_PREDICTION, INTENT_BUSINESS_DEBATE],
            recommended_strategy=STRATEGY_BUSINESS_DEBATE,
            confidence=0.91,
            reasoning="AI disruption forecast for marketing agencies.",
            alternative_intents=[INTENT_MARKET_FORECAST, INTENT_FUTURE_PREDICTION],
            domain_concepts=[
                "client acquisition",
                "media buying",
                "copywriting",
                "performance marketing",
                "marketing operations",
                "AI agents",
                "campaign automation",
                "agency economics",
                "creative production",
                "customer targeting",
            ],
            story_angles=[
                "Open with the claim that AI could reshape agency economics by 2026.",
                "Compare evidence from automation, media buying, and creative production trends.",
                "Deliver a verdict on which agency roles survive and which shrink.",
            ],
            seo_title_candidates=[
                "Will AI Replace Marketing Agencies by 2026?",
                "The AI Threat Most Agencies Ignore",
                "Can Agencies Survive the AI Revolution?",
                "Why AI Could Disrupt the Marketing Industry",
                "What AI Automation Means for Agencies in 2026",
            ],
        )
    if "graphic designer" in lowered or ("ai" in lowered and "replace" in lowered and "designer" in lowered):
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_TECHNOLOGY_FORECAST,
            secondary_intents=[INTENT_FUTURE_PREDICTION],
            recommended_strategy=STRATEGY_TECHNOLOGY_FORECAST,
            confidence=0.9,
            reasoning="Technology workforce forecast about AI replacing designers.",
            domain_concepts=("AI design tools", "creative workflow", "brand systems", "layout automation", "human taste", "client revision"),
            story_angles=[
                "Show what AI already automates in graphic design workflows today.",
                "Compare tasks machines handle versus human judgment and brand taste.",
                "Forecast which designer roles adapt and which shrink.",
            ],
            seo_title_candidates=(
                "Will AI Replace Graphic Designers?",
                "What AI Still Cannot Do for Designers",
                "The Future of Graphic Design in an AI World",
                "Which Design Jobs AI Will Change First",
            ),
        )
    if "blockbuster" in lowered:
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_BUSINESS_CASE_STUDY,
            recommended_strategy=STRATEGY_BUSINESS_CASE_STUDY,
            confidence=0.93,
            reasoning="Business failure case study.",
        )
    if "roanoke" in lowered or "what really happened" in lowered:
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_HISTORICAL_INVESTIGATION,
            recommended_strategy=STRATEGY_HISTORICAL_INVESTIGATION,
            confidence=0.95,
            reasoning="Historical mystery investigation.",
        )
    if "pizza dough" in lowered or lowered.startswith("how to make"):
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_TUTORIAL,
            recommended_strategy=STRATEGY_RECIPE_TUTORIAL,
            confidence=0.94,
            reasoning="Cooking tutorial intent.",
        )
    if "perfume" in lowered and ("last" in lowered or "why" in lowered):
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_SCIENTIFIC_EXPLANATION,
            recommended_strategy=STRATEGY_SCIENTIFIC_EXPLANATION,
            confidence=0.9,
            reasoning="Scientific explanation of perfume longevity.",
            domain_concepts=("top notes", "heart notes", "base notes", "concentration", "skin chemistry", "projection", "longevity"),
            story_angles=(
                "Explain why some perfumes fade quickly while others linger.",
                "Compare concentration, notes, and skin chemistry with visible examples.",
                "Give practical takeaways for choosing longer-lasting fragrances.",
            ),
            seo_title_candidates=(
                "Why Some Perfumes Last All Day",
                "The Science Behind Perfume Longevity",
                "What Makes a Fragrance Last Longer?",
            ),
        )
    if "dyatlov" in lowered:
        return IntentDetectionResult(
            topic=topic,
            primary_intent=INTENT_MYSTERY,
            recommended_strategy=STRATEGY_NARRATIVE_MYSTERY,
            confidence=0.92,
            reasoning="Historical mystery case.",
        )
    return IntentDetectionResult(
        topic=topic,
        primary_intent=_strategy_to_intent(classification.content_strategy),
        recommended_strategy=classification.content_strategy,
        confidence=max(0.7, float(classification.confidence or 0.0)),
        reasoning="Dry-run fallback retained local mapping.",
    )


def _should_prefer_openai_intent(local: IntentDetectionResult, enriched: IntentDetectionResult) -> bool:
    if enriched.recommended_strategy in TUTORIAL_STRATEGIES and local.recommended_strategy not in TUTORIAL_STRATEGIES:
        return False
    if local.recommended_strategy in TUTORIAL_STRATEGIES and enriched.recommended_strategy not in TUTORIAL_STRATEGIES:
        return False
    if local.recommended_strategy in {
        STRATEGY_BUSINESS_CASE_STUDY,
        STRATEGY_HISTORICAL_INVESTIGATION,
        STRATEGY_FUTURE_ANALYSIS,
        STRATEGY_BUSINESS_DEBATE,
        STRATEGY_TECHNOLOGY_FORECAST,
        STRATEGY_SCIENTIFIC_EXPLANATION,
    } and enriched.recommended_strategy in TUTORIAL_STRATEGIES:
        return False
    if enriched.confidence < local.confidence and local.recommended_strategy == enriched.recommended_strategy:
        return False
    return enriched.confidence >= local.confidence or enriched.recommended_strategy != local.recommended_strategy


def _is_tutorial_intent(text: str, classification: TopicClassification | None = None) -> bool:
    if classification is not None and classification.instructional_intent:
        return True
    if text.startswith("how to ") or text.startswith("how-to "):
        return True
    if "method" in text and classification is not None and classification.topic_category in {"fishing", "cooking", "fitness"}:
        return True
    return any(marker in text for marker in TUTORIAL_MARKERS if marker not in {"method", "technique", "guide"})


def _is_business_case_intent(text: str) -> bool:
    if any(marker in text for marker in ("if it had", "could have survived", "would have survived", "adopted earlier")):
        if any(token in text for token in ("nokia", "android", "company", "brand", "strategy", "market", "platform", "survived")):
            return True
    if any(marker in text for marker in BUSINESS_CASE_MARKERS):
        if any(token in text for token in ("blockbuster", "kodak", "netflix", "business", "company", "brand", "startup", "market")):
            return True
    return False


def _is_scientific_explanation_intent(text: str) -> bool:
    if not any(marker in text for marker in SCIENTIFIC_MARKERS):
        return False
    return any(token in text for token in ("perfume", "fragrance", "scent", "last", "longer", "skin", "molecule", "notes"))


def _is_mystery_intent(text: str) -> bool:
    return any(token in text for token in ("mystery", "unsolved", "dyatlov", "disappearance", "what happened"))


def _is_future_disruption_intent(text: str) -> bool:
    if not _is_question_form(text):
        return False
    has_future = _has_markers(text, FUTURE_MARKERS) or "will ai" in text or "can ai" in text
    has_disruption = _has_markers(text, DISRUPTION_MARKERS) or "replace" in text or "destroy" in text
    has_ai = topic_keyword_matches("ai", text) or "artificial intelligence" in text
    return has_ai and (has_future or has_disruption)


def _is_question_form(text: str) -> bool:
    if text.endswith("?"):
        return True
    return bool(re.match(r"^(can|will|why|what|how|should|is|are|do|does)\b", text))


def _has_markers(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _tutorial_strategy_for_category(classification: TopicClassification) -> str:
    if classification.topic_category == "fishing":
        return STRATEGY_INSTRUCTIONAL_FISHING
    if classification.topic_category == "cooking":
        return STRATEGY_RECIPE_TUTORIAL
    if classification.topic_category == "technology":
        return STRATEGY_EDUCATIONAL_TECH
    return STRATEGY_RECIPE_TUTORIAL


def _strategy_to_intent(strategy: str) -> str:
    if strategy in TUTORIAL_STRATEGIES:
        return INTENT_TUTORIAL
    for intent, mapped in INTENT_TO_STRATEGY.items():
        if mapped == strategy:
            return intent
    return INTENT_DOCUMENTARY


def _sanitize_intent(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    aliases = {
        "future_analysis": INTENT_FUTURE_PREDICTION,
        "industry_disruption": INTENT_INDUSTRY_DISRUPTION,
        "history_mystery": INTENT_HISTORICAL_INVESTIGATION,
        "business_history": INTENT_BUSINESS_CASE_STUDY,
        "scientific_explanation": INTENT_SCIENTIFIC_EXPLANATION,
        "technology_forecast": INTENT_TECHNOLOGY_FORECAST,
        "business_debate": INTENT_BUSINESS_DEBATE,
    }
    return aliases.get(cleaned, cleaned)


def _sanitize_strategy(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    aliases = {
        "business_history": STRATEGY_BUSINESS_CASE_STUDY,
        "history_mystery": STRATEGY_HISTORICAL_INVESTIGATION,
        "future_analysis": STRATEGY_FUTURE_ANALYSIS,
        "technology_forecast": STRATEGY_TECHNOLOGY_FORECAST,
        "scientific_explanation": STRATEGY_SCIENTIFIC_EXPLANATION,
        "business_debate": STRATEGY_BUSINESS_DEBATE,
        "instructional_cooking": STRATEGY_RECIPE_TUTORIAL,
        "tutorial": STRATEGY_RECIPE_TUTORIAL,
    }
    allowed = set(INTENT_TO_STRATEGY.values())
    mapped = aliases.get(cleaned, cleaned)
    return mapped if mapped in allowed else ""


def _cache_key(topic: str, language_code: str, category: str) -> str:
    normalized = re.sub(r"\s+", " ", str(topic or "").strip().lower())
    digest = hashlib.sha256(f"{INTENT_LAYER_VERSION}|{language_code}|{category}|{normalized}".encode("utf-8")).hexdigest()
    return digest[:24]


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _estimate_cost_usd(model: str, usage: dict[str, Any]) -> float:
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if "mini" in model.lower():
        return (prompt_tokens * 0.0000004) + (completion_tokens * 0.0000016)
    return (prompt_tokens * 0.0000025) + (completion_tokens * 0.00001)


__all__ = [
    "INTENT_LAYER_VERSION",
    "IntentDetectionResult",
    "IntentResolutionResult",
    "OpenAIIntentEnricher",
    "apply_intent_to_classification",
    "detect_local_intent",
    "maybe_enrich_intent",
    "resolve_topic_intent",
    "should_use_openai_intent",
]
