"""
Content Brain V8.5 — OpenAI Dynamic Domain Expert fallback.

When local classification/domain knowledge is weak or generic, call OpenAI to build
a temporary topic-specific knowledge pack (cached by normalized topic).
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

from content_brain.execution.content_brain_openai_classification_enricher import (
    OpenAIClassificationPayload,
    apply_openai_classification,
    apply_openai_strategy_overlay,
    normalize_topic_cache_key,
)
from content_brain.execution.content_brain_topic_locale import detect_language_code
from content_brain.execution.content_brain_topic_strategy import (
    STRATEGY_CINEMATIC_NARRATIVE,
    ContentStrategyPlan,
    TopicClassification,
    build_content_strategy_plan,
)
from content_brain.execution.domain_knowledge_layer import (
    DomainKnowledgeProfile,
    get_domain_profile,
    score_domain_concept_usage,
)

EXPERT_LAYER_VERSION = "dynamic_domain_expert_v85"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_OUTPUT_TOKENS = 2200
REQUEST_TIMEOUT_SECONDS = 45.0
DOMAIN_KNOWLEDGE_TRIGGER_MAX = 0.70
PROMPT_DIVERSITY_TRIGGER_MAX = 0.70
TOPIC_LABEL_TRIGGER_MAX = 0.80

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "project_brain" / "content_brain_dynamic_domain_cache"

EDUCATIONAL_TOPIC_MARKERS: tuple[str, ...] = (
    "history",
    "evolution",
    "origin",
    "rise and fall",
    "science",
    "ancient",
    "biology",
    "mystery",
    "future",
    " why ",
    " how ",
    "through the ages",
    "civilization",
    "empire",
    "communicate",
    "intelligence",
)

STRATEGY_ALIASES: dict[str, str] = {
    "evolutionary_timeline": "documentary",
    "evolutionary_history": "documentary",
    "documentary_explainer": "documentary",
    "scientific_explanation": "scientific_explanation",
    "empire_documentary": "historical_investigation",
    "historical_documentary": "historical_investigation",
    "natural_history": "documentary",
    "geology_history": "documentary",
    "marine_biology": "scientific_explanation",
    "ecology_explainer": "scientific_explanation",
}


@dataclass
class DynamicDomainClipStructure:
    clip_1: str = ""
    clip_2: str = ""
    clip_3: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "clip_1": self.clip_1,
            "clip_2": self.clip_2,
            "clip_3": self.clip_3,
        }

    def clip_beats(self, clip_count: int = 3) -> tuple[str, ...]:
        ordered = (self.clip_1, self.clip_2, self.clip_3)
        beats = [beat for beat in ordered if beat.strip()]
        while len(beats) < clip_count and beats:
            beats.append(beats[-1])
        return tuple(beats[:clip_count])


@dataclass
class DynamicDomainProfile:
    domain_name: str
    expert_role: str
    setting: str
    core_concepts: tuple[str, ...] = ()
    timeline_beats: tuple[str, ...] = ()
    visual_objects: tuple[str, ...] = ()
    clip_structure: DynamicDomainClipStructure = field(default_factory=DynamicDomainClipStructure)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_name": self.domain_name,
            "expert_role": self.expert_role,
            "setting": self.setting,
            "core_concepts": list(self.core_concepts),
            "timeline_beats": list(self.timeline_beats),
            "visual_objects": list(self.visual_objects),
            "clip_structure": self.clip_structure.to_dict(),
        }


@dataclass
class DynamicDomainExpertPayload:
    category: str
    strategy: str
    domain_profile: DynamicDomainProfile
    confidence: float = 0.0
    language_code: str = "en"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "strategy": self.strategy,
            "domain_profile": self.domain_profile.to_dict(),
            "confidence": round(self.confidence, 4),
            "language_code": self.language_code,
        }


@dataclass
class DynamicDomainExpertResult:
    used: bool = False
    provider: str = EXPERT_LAYER_VERSION
    model: str = ""
    trigger_reason: str = ""
    cache_hit: bool = False
    classification: TopicClassification | None = None
    strategy_plan: ContentStrategyPlan | None = None
    payload: DynamicDomainExpertPayload | None = None
    domain_profile: DomainKnowledgeProfile | None = None
    notes: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "used": self.used,
            "provider": self.provider,
            "model": self.model,
            "trigger_reason": self.trigger_reason,
            "cache_hit": self.cache_hit,
            "classification": self.classification.to_dict() if self.classification else {},
            "strategy_plan": self.strategy_plan.to_dict() if self.strategy_plan else {},
            "payload": self.payload.to_dict() if self.payload else {},
            "domain_profile": self.domain_profile.to_dict() if self.domain_profile else {},
            "notes": list(self.notes),
            "usage": dict(self.usage),
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


class OpenAIDynamicDomainExpert:
    """Build temporary topic-specific knowledge packs via OpenAI."""

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        model: str | None = None,
        dry_run: bool | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.model = (model or os.getenv("OPENAI_DYNAMIC_DOMAIN_MODEL") or DEFAULT_MODEL).strip()
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_DYNAMIC_DOMAIN_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self._api_key = ""
        self.enabled = self._resolve_enabled_state() or self.dry_run
        self._client: Any | None = None

    def maybe_resolve(
        self,
        *,
        topic: str,
        classification: TopicClassification,
        language_code: str,
        mood: str = "emotional",
        clip_count: int = 3,
        domain_knowledge_score: float | None = None,
        prompt_diversity_score: float | None = None,
        topic_label_quality_score: float | None = None,
        force: bool = False,
    ) -> DynamicDomainExpertResult:
        local_profile = get_domain_profile(topic, topic_category=classification.topic_category)
        should_use, reason = should_trigger_dynamic_domain_expert(
            topic=topic,
            classification=classification,
            domain_profile=local_profile,
            domain_knowledge_score=domain_knowledge_score,
            prompt_diversity_score=prompt_diversity_score,
            topic_label_quality_score=topic_label_quality_score,
        )
        if not force and not should_use:
            return DynamicDomainExpertResult(
                notes=["dynamic_domain_expert_not_needed"],
                classification=classification,
            )
        if not self.enabled:
            return DynamicDomainExpertResult(
                trigger_reason=reason,
                notes=["dynamic_domain_expert_disabled"],
                classification=classification,
            )

        cache_key = normalize_topic_cache_key(topic, language_code)
        cached = self._read_cache(cache_key)
        if cached is not None:
            payload = _parse_payload(cached.get("payload") or {}, language_code)
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
                    notes=["dynamic_domain_expert_cache_hit"],
                )

        if self.dry_run:
            payload = _build_dry_run_payload(topic, language_code)
            notes = ["dynamic_domain_expert_dry_run"]
            usage: dict[str, Any] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            cost = 0.0
        else:
            if not self._api_key or OpenAI is None:
                return DynamicDomainExpertResult(
                    trigger_reason=reason,
                    notes=["dynamic_domain_expert_client_unavailable"],
                    classification=classification,
                )
            raw, usage, cost = self._call_openai(topic, language_code, classification)
            if not raw:
                return DynamicDomainExpertResult(
                    trigger_reason=reason,
                    notes=["dynamic_domain_expert_failed"],
                    classification=classification,
                )
            payload = _parse_payload(raw, language_code)
            if payload is None:
                return DynamicDomainExpertResult(
                    trigger_reason=reason,
                    notes=["dynamic_domain_expert_invalid"],
                    classification=classification,
                )
            notes = ["dynamic_domain_expert_applied"]
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
        payload: DynamicDomainExpertPayload,
        trigger_reason: str,
        cache_hit: bool,
        usage: dict[str, Any],
        estimated_cost_usd: float,
        notes: list[str],
    ) -> DynamicDomainExpertResult:
        openai_payload = _to_openai_classification_payload(payload)
        merged_classification = apply_openai_classification(local_classification, openai_payload, topic)
        strategy_plan = build_content_strategy_plan(
            topic,
            merged_classification,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
        )
        strategy_plan = apply_openai_strategy_overlay(strategy_plan, openai_payload, topic, clip_count)
        strategy_plan = apply_dynamic_clip_structure(strategy_plan, payload, topic, clip_count)
        domain_profile = build_domain_profile_from_dynamic_payload(topic, payload)
        if not _topic_preserved(topic, payload):
            return DynamicDomainExpertResult(
                trigger_reason=trigger_reason,
                notes=["dynamic_domain_expert_rejected_topic_drift"],
                classification=local_classification,
            )
        return DynamicDomainExpertResult(
            used=True,
            model=self.model,
            trigger_reason=trigger_reason,
            cache_hit=cache_hit,
            classification=merged_classification,
            strategy_plan=strategy_plan,
            payload=payload,
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
            "You are a dynamic domain expert for short-form educational video topics. "
            "Return JSON only with keys: category, strategy, domain_profile, confidence. "
            "domain_profile must include: domain_name, expert_role, setting, core_concepts, "
            "timeline_beats, visual_objects, clip_structure (clip_1, clip_2, clip_3). "
            "Write ALL string values in the same language as the user's topic. "
            "Never rename or replace the user's topic. "
            "Use concrete domain-specific concepts, settings, timeline beats, and clip beats. "
            "category examples: natural_history, evolutionary_history, geology, marine_biology, "
            "history, ecology, animal_intelligence. "
            "strategy examples: evolutionary_timeline, documentary_explainer, scientific_explanation, "
            "historical_investigation, empire_documentary. "
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


def resolve_dynamic_domain_expert(
    *,
    topic: str,
    classification: TopicClassification,
    language_code: str | None = None,
    mood: str = "emotional",
    clip_count: int = 3,
    domain_knowledge_score: float | None = None,
    prompt_diversity_score: float | None = None,
    topic_label_quality_score: float | None = None,
    force: bool = False,
) -> DynamicDomainExpertResult:
    lang = language_code or detect_language_code(topic)
    expert = OpenAIDynamicDomainExpert()
    return expert.maybe_resolve(
        topic=topic,
        classification=classification,
        language_code=lang,
        mood=mood,
        clip_count=clip_count,
        domain_knowledge_score=domain_knowledge_score,
        prompt_diversity_score=prompt_diversity_score,
        topic_label_quality_score=topic_label_quality_score,
        force=force,
    )


def should_trigger_dynamic_domain_expert(
    *,
    topic: str,
    classification: TopicClassification,
    domain_profile: DomainKnowledgeProfile,
    domain_knowledge_score: float | None = None,
    prompt_diversity_score: float | None = None,
    topic_label_quality_score: float | None = None,
) -> tuple[bool, str]:
    lowered = f" {str(topic or '').lower()} "
    if classification.topic_category in {"general", ""}:
        return True, "category_general"
    if domain_profile.domain_id == "general":
        return True, "domain_knowledge_missing"
    if score_domain_concept_usage(topic, domain_profile) < 0.25:
        return True, "domain_knowledge_missing"
    if (
        classification.content_strategy == STRATEGY_CINEMATIC_NARRATIVE
        and _looks_educational_topic(lowered)
    ):
        return True, "generic_cinematic_for_educational_topic"
    if domain_knowledge_score is not None and float(domain_knowledge_score) < DOMAIN_KNOWLEDGE_TRIGGER_MAX:
        return True, "domain_knowledge_score_low"
    if prompt_diversity_score is not None and float(prompt_diversity_score) < PROMPT_DIVERSITY_TRIGGER_MAX:
        return True, "prompt_diversity_score_low"
    if topic_label_quality_score is not None and float(topic_label_quality_score) < TOPIC_LABEL_TRIGGER_MAX:
        return True, "topic_label_quality_low"
    if any(marker in lowered for marker in EDUCATIONAL_TOPIC_MARKERS):
        if classification.topic_category in {"general", "cinematic", "lifestyle"}:
            return True, "educational_topic_keyword"
        if classification.content_strategy == STRATEGY_CINEMATIC_NARRATIVE:
            return True, "educational_topic_keyword"
    return False, ""


def apply_dynamic_clip_structure(
    plan: ContentStrategyPlan,
    payload: DynamicDomainExpertPayload,
    topic: str,
    clip_count: int,
) -> ContentStrategyPlan:
    beats = list(payload.domain_profile.clip_structure.clip_beats(clip_count))
    if not beats:
        beats = list(payload.domain_profile.timeline_beats[:clip_count])
    if not beats:
        return plan
    normalized = [_normalize_beat(beat, topic) for beat in beats]
    required_terms = tuple(
        dict.fromkeys(
            list(payload.domain_profile.core_concepts)
            + list(payload.domain_profile.visual_objects)
            + list(plan.required_terms)
        )
    )[:14]
    visual_hook = plan.visual_hook
    if payload.domain_profile.setting:
        visual_hook = f"Visual anchor in {payload.domain_profile.setting} tied directly to {topic}."
    return ContentStrategyPlan(
        strategy_id=plan.strategy_id,
        label=plan.label,
        purpose=plan.purpose,
        niche_style=plan.niche_style,
        effective_mood=plan.effective_mood,
        clip_beats=normalized[:clip_count],
        conflict=normalized[0] if normalized else plan.conflict,
        visual_hook=visual_hook,
        seo_title_candidates=plan.seo_title_candidates,
        required_terms=required_terms,
        forbidden_filler=plan.forbidden_filler,
    )


def build_domain_profile_from_dynamic_payload(
    topic: str,
    payload: DynamicDomainExpertPayload,
) -> DomainKnowledgeProfile:
    profile = payload.domain_profile
    beats = profile.clip_structure.clip_beats(3) or profile.timeline_beats or (
        f"Context and stakes for {topic}.",
        f"Evidence and comparison around {topic}.",
        f"Takeaway tied to {topic}.",
    )
    return DomainKnowledgeProfile(
        domain_id=_sanitize_token(payload.category) or _sanitize_token(profile.domain_name) or "dynamic",
        label=f"Dynamic domain: {profile.domain_name or payload.category}",
        concepts=tuple(str(item) for item in profile.core_concepts if str(item).strip()),
        default_role_en=_normalize_role(profile.expert_role),
        setting_en=str(profile.setting or "").strip(),
        instructional_beats_en=tuple(_normalize_beat(beat, topic) for beat in beats[:3]),
        review_beats_en=tuple(_normalize_beat(beat, topic) for beat in profile.timeline_beats[:3]),
    )


def dynamic_expert_to_openai_enrichment(payload: DynamicDomainExpertPayload) -> dict[str, Any]:
    profile = payload.domain_profile
    beats = profile.clip_structure.clip_beats(3) or profile.timeline_beats
    return {
        "category": payload.category,
        "strategy": payload.strategy,
        "domain_role": profile.expert_role,
        "domain_concepts": list(profile.core_concepts),
        "setting": profile.setting,
        "story_angles": list(beats),
        "seo_title_candidates": [],
        "confidence": payload.confidence,
        "visual_objects": list(profile.visual_objects),
        "timeline_beats": list(profile.timeline_beats),
        "clip_structure": profile.clip_structure.to_dict(),
    }


def _to_openai_classification_payload(payload: DynamicDomainExpertPayload) -> OpenAIClassificationPayload:
    profile = payload.domain_profile
    beats = profile.clip_structure.clip_beats(3) or profile.timeline_beats
    return OpenAIClassificationPayload(
        category=_sanitize_token(payload.category),
        strategy=_map_strategy(payload.strategy),
        domain_role=_normalize_role(profile.expert_role),
        domain_concepts=tuple(str(item) for item in profile.core_concepts if str(item).strip()),
        setting=str(profile.setting or "").strip(),
        story_angles=tuple(_normalize_beat(beat, "") for beat in beats if str(beat).strip()),
        seo_title_candidates=(),
        confidence=float(payload.confidence or 0.0),
        language_code=payload.language_code,
    )


def _parse_payload(raw: dict[str, Any], language_code: str) -> DynamicDomainExpertPayload | None:
    if not isinstance(raw, dict):
        return None
    profile_raw = raw.get("domain_profile")
    if not isinstance(profile_raw, dict):
        return None
    clip_raw = profile_raw.get("clip_structure") or {}
    if not isinstance(clip_raw, dict):
        clip_raw = {}
    concepts = profile_raw.get("core_concepts")
    timeline = profile_raw.get("timeline_beats")
    visuals = profile_raw.get("visual_objects")
    if not isinstance(concepts, list) or not concepts:
        return None
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))
    clip_structure = DynamicDomainClipStructure(
        clip_1=str(clip_raw.get("clip_1") or "").strip(),
        clip_2=str(clip_raw.get("clip_2") or "").strip(),
        clip_3=str(clip_raw.get("clip_3") or "").strip(),
    )
    domain_profile = DynamicDomainProfile(
        domain_name=str(profile_raw.get("domain_name") or raw.get("category") or "").strip(),
        expert_role=str(profile_raw.get("expert_role") or "").strip(),
        setting=re.sub(r"\s+", " ", str(profile_raw.get("setting") or "").strip()),
        core_concepts=tuple(str(item).strip() for item in concepts if str(item).strip()),
        timeline_beats=tuple(str(item).strip() for item in timeline if str(item).strip()) if isinstance(timeline, list) else (),
        visual_objects=tuple(str(item).strip() for item in visuals if str(item).strip()) if isinstance(visuals, list) else (),
        clip_structure=clip_structure,
    )
    category = _sanitize_token(str(raw.get("category") or domain_profile.domain_name or ""))
    strategy = _map_strategy(str(raw.get("strategy") or ""))
    if not category or not domain_profile.expert_role or not domain_profile.setting:
        return None
    return DynamicDomainExpertPayload(
        category=category,
        strategy=strategy,
        domain_profile=domain_profile,
        confidence=confidence,
        language_code=language_code,
    )


def _build_dry_run_payload(topic: str, language_code: str) -> DynamicDomainExpertPayload:
    lowered = topic.lower()
    if "snake" in lowered:
        return _payload_from_template(
            category="natural_history",
            strategy="evolutionary_timeline",
            domain_name="natural_history",
            expert_role="natural history narrator",
            setting="prehistoric landscapes, fossil beds, modern rainforest habitats",
            core_concepts=(
                "snake evolution",
                "ancient reptiles",
                "loss of limbs",
                "venom evolution",
                "fossil evidence",
                "modern snake species",
            ),
            timeline_beats=(
                "ancient reptile ancestors",
                "evolutionary adaptations",
                "modern ecological roles",
            ),
            visual_objects=("fossils", "prehistoric reptiles", "desert habitat", "rainforest floor", "snake skeleton"),
            clip_structure=DynamicDomainClipStructure(
                clip_1="ancient origins",
                clip_2="major evolutionary adaptations",
                clip_3="modern snakes and survival advantage",
            ),
            confidence=0.91,
            language_code=language_code,
        )
    if "volcano" in lowered:
        return _payload_from_template(
            category="geology",
            strategy="documentary_explainer",
            domain_name="geology_history",
            expert_role="geology and civilization historian",
            setting="active volcanic landscapes, ancient settlements, ash-covered ruins",
            core_concepts=(
                "volcanic eruptions",
                "fertile soil",
                "ancient civilizations",
                "trade routes",
                "climate impact",
                "human adaptation",
            ),
            timeline_beats=(
                "volcanic formation shaping land",
                "civilizations built near volcanoes",
                "long-term human consequences",
            ),
            visual_objects=("lava flows", "ash layers", "terraced farmland", "ancient ruins", "volcano crater"),
            clip_structure=DynamicDomainClipStructure(
                clip_1="how volcanoes reshape land",
                clip_2="civilizations that rose near volcanoes",
                clip_3="legacy of volcanic landscapes on human history",
            ),
            confidence=0.89,
            language_code=language_code,
        )
    if "octopus" in lowered or "octopuses" in lowered:
        return _payload_from_template(
            category="marine_biology",
            strategy="scientific_explanation",
            domain_name="animal_intelligence",
            expert_role="marine biologist",
            setting="underwater reef labs, aquarium tanks, neural-behavior research stations",
            core_concepts=(
                "octopus intelligence",
                "problem solving",
                "camouflage",
                "distributed nervous system",
                "tool use",
                "alien-like cognition",
            ),
            timeline_beats=(
                "unique octopus biology",
                "evidence of advanced cognition",
                "why scientists compare octopuses to alien intelligence",
            ),
            visual_objects=("octopus camouflage", "coral reef", "research tank", "neuron diagram", "underwater lab"),
            clip_structure=DynamicDomainClipStructure(
                clip_1="biology that makes octopuses unusual",
                clip_2="behaviors that look like alien intelligence",
                clip_3="what science still cannot fully explain",
            ),
            confidence=0.9,
            language_code=language_code,
        )
    if "ottoman" in lowered or "empire" in lowered:
        return _payload_from_template(
            category="history",
            strategy="empire_documentary",
            domain_name="empire_history",
            expert_role="historian",
            setting="Ottoman palaces, battlefields, trade hubs, and archival maps",
            core_concepts=(
                "Ottoman Empire",
                "military expansion",
                "trade networks",
                "administrative decline",
                "territorial loss",
                "legacy",
            ),
            timeline_beats=(
                "rise of imperial power",
                "peak influence and control",
                "forces that led to decline",
            ),
            visual_objects=("palace architecture", "battle maps", "trade caravans", "imperial banners", "archival documents"),
            clip_structure=DynamicDomainClipStructure(
                clip_1="origins and rapid rise",
                clip_2="peak power and global influence",
                clip_3="decline and lasting legacy",
            ),
            confidence=0.92,
            language_code=language_code,
        )
    if "mushroom" in lowered:
        return _payload_from_template(
            category="biology",
            strategy="scientific_explanation",
            domain_name="ecology",
            expert_role="ecologist",
            setting="forest floor mycelium networks, soil cross-sections, fungal microscopy labs",
            core_concepts=(
                "mycelium networks",
                "fungal communication",
                "nutrient exchange",
                "forest ecology",
                "underground signaling",
                "symbiosis",
            ),
            timeline_beats=(
                "hidden fungal networks beneath forests",
                "evidence of communication between organisms",
                "why this changes how we see ecosystems",
            ),
            visual_objects=("mycelium", "mushroom caps", "root systems", "soil cross-section", "microscopy slides"),
            clip_structure=DynamicDomainClipStructure(
                clip_1="what underground fungal networks look like",
                clip_2="evidence that mushrooms may communicate",
                clip_3="ecological impact of fungal signaling",
            ),
            confidence=0.88,
            language_code=language_code,
        )
    return _payload_from_template(
        category="general",
        strategy="documentary",
        domain_name="general",
        expert_role="knowledgeable presenter",
        setting=f"context-rich environment tied to {topic}",
        core_concepts=tuple(_topic_tokens(topic, limit=4)),
        timeline_beats=(f"Central question behind {topic}.", f"Evidence around {topic}.", f"What {topic} means now."),
        visual_objects=tuple(_topic_tokens(topic, limit=3)),
        clip_structure=DynamicDomainClipStructure(
            clip_1=f"opening context for {topic}",
            clip_2=f"core evidence about {topic}",
            clip_3=f"takeaway from {topic}",
        ),
        confidence=0.72,
        language_code=language_code,
    )


def _payload_from_template(
    *,
    category: str,
    strategy: str,
    domain_name: str,
    expert_role: str,
    setting: str,
    core_concepts: tuple[str, ...],
    timeline_beats: tuple[str, ...],
    visual_objects: tuple[str, ...],
    clip_structure: DynamicDomainClipStructure,
    confidence: float,
    language_code: str,
) -> DynamicDomainExpertPayload:
    return DynamicDomainExpertPayload(
        category=_sanitize_token(category),
        strategy=_map_strategy(strategy),
        domain_profile=DynamicDomainProfile(
            domain_name=_sanitize_token(domain_name),
            expert_role=expert_role,
            setting=setting,
            core_concepts=core_concepts,
            timeline_beats=timeline_beats,
            visual_objects=visual_objects,
            clip_structure=clip_structure,
        ),
        confidence=confidence,
        language_code=language_code,
    )


def _looks_educational_topic(lowered_topic: str) -> bool:
    return any(marker in lowered_topic for marker in EDUCATIONAL_TOPIC_MARKERS)


def _topic_preserved(topic: str, payload: DynamicDomainExpertPayload) -> bool:
    from content_brain.execution.content_brain_topic_authority import audit_story_brief_preservation

    beats = payload.domain_profile.clip_structure.clip_beats(3) or payload.domain_profile.timeline_beats
    story_probe = {
        "logline": " ".join(beats[:2]),
        "main_character": payload.domain_profile.expert_role,
        "setting": payload.domain_profile.setting,
        "clip_beats": list(beats[:3]),
    }
    audit = audit_story_brief_preservation(topic, story_probe)
    return float(audit.topic_preservation_score) >= 0.34


def _map_strategy(strategy: str) -> str:
    cleaned = _sanitize_token(strategy)
    return STRATEGY_ALIASES.get(cleaned, cleaned or "documentary")


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


def _topic_tokens(topic: str, *, limit: int = 4) -> tuple[str, ...]:
    tokens = re.findall(r"[a-zA-Z]{4,}", topic.lower())
    return tuple(dict.fromkeys(tokens))[:limit]


def _estimate_cost_usd(model: str, usage: dict[str, Any]) -> float:
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if "mini" in model.lower():
        return (prompt_tokens * 0.0000004) + (completion_tokens * 0.0000016)
    return (prompt_tokens * 0.0000025) + (completion_tokens * 0.00001)


__all__ = [
    "DEFAULT_CACHE_DIR",
    "DynamicDomainExpertPayload",
    "DynamicDomainExpertResult",
    "DynamicDomainProfile",
    "EXPERT_LAYER_VERSION",
    "OpenAIDynamicDomainExpert",
    "apply_dynamic_clip_structure",
    "build_domain_profile_from_dynamic_payload",
    "dynamic_expert_to_openai_enrichment",
    "resolve_dynamic_domain_expert",
    "should_trigger_dynamic_domain_expert",
]
