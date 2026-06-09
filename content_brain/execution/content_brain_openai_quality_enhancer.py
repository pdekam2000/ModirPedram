"""
OpenAI Quality Enhancement Layer — selective repair of weak local Content Brain outputs.

Runs only when quality audit detects low scores or generic content.
Does not replace category, strategy, topic, or language.
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

from content_brain.execution.content_brain_quality_audit_v2 import GENERIC_STORY_MARKERS
from content_brain.execution.content_brain_seo_director import is_malformed_seo_title
from content_brain.execution.content_brain_topic_locale import detect_language_code
from content_brain.execution.content_brain_topic_story_detail import _extract_subject_phrase
from content_brain.execution.domain_knowledge_layer import (
    MARKETING_AGENCY_CONCEPTS,
    build_domain_profile_from_concepts,
    filter_expert_domain_concepts,
    get_domain_profile,
    score_domain_concept_usage,
)

ENHANCER_ID = "openai_quality_enhancer"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_OUTPUT_TOKENS = 2200
REQUEST_TIMEOUT_SECONDS = 60.0

THRESHOLD_LANGUAGE = 0.90
THRESHOLD_CHARACTER = 0.80
THRESHOLD_DOMAIN = 0.80
THRESHOLD_STORY = 0.80
THRESHOLD_SEO = 0.85
THRESHOLD_PROMPT = 0.80
THRESHOLD_CLASSIFICATION = 0.85

ENHANCEMENT_SEO = "seo"
ENHANCEMENT_DOMAIN = "domain_knowledge"
ENHANCEMENT_CHARACTER = "character"
ENHANCEMENT_STORY = "story"
ENHANCEMENT_PROMPT = "prompt"

GENERIC_CHARACTER_MARKERS: tuple[str, ...] = (
    "knowledgeable presenter",
    "focused digital creator",
    "primary subject in focus",
    "compelling lead subject",
)

MALFORMED_SEO_PATTERNS: tuple[str, ...] = (
    r"how to why",
    r"why how to",
    r"how to how to",
    r"\?\?",
    r"why the mystery",
    r"why the mystery of",
    r"why your mystery",
    r"how to mystery",
    r"how to the mystery",
    r"stop making this .+ mystery mistake",
    r"mystery .+ never works",
)

QUALITY_CACHE_VERSION = "domain_depth_v6"

ENHANCEMENT_DOMAIN_KNOWLEDGE_MIN = 0.50
ENHANCEMENT_CLIP_SPECIFICITY_MIN = 0.50
ENHANCEMENT_STRATEGY_ALIGNMENT_MIN = 0.60


@dataclass
class EnhancementTriggerReport:
    triggered: bool = False
    reasons: list[str] = field(default_factory=list)
    enhancement_types: list[str] = field(default_factory=list)
    generic_content_detected: bool = False
    domain_pack_missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "reasons": list(self.reasons),
            "enhancement_types": list(self.enhancement_types),
            "generic_content_detected": self.generic_content_detected,
            "domain_pack_missing": self.domain_pack_missing,
        }


@dataclass
class QualityEnhancementResult:
    applied: bool = False
    enabled: bool = False
    provider: str = ENHANCER_ID
    model: str = ""
    trigger_report: EnhancementTriggerReport = field(default_factory=EnhancementTriggerReport)
    enhancements_applied: list[str] = field(default_factory=list)
    before_scores: dict[str, float] = field(default_factory=dict)
    after_scores: dict[str, float] = field(default_factory=dict)
    improvement_summary: dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False
    usage: dict[str, Any] = field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)
    enhanced: dict[str, Any] = field(default_factory=dict)
    raw_enhancement: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "trigger_report": self.trigger_report.to_dict(),
            "enhancements_applied": list(self.enhancements_applied),
            "before_scores": {k: round(v, 4) for k, v in self.before_scores.items()},
            "after_scores": {k: round(v, 4) for k, v in self.after_scores.items()},
            "improvement_summary": dict(self.improvement_summary),
            "cache_hit": self.cache_hit,
            "usage": dict(self.usage),
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "notes": list(self.notes),
            "enhanced": dict(self.enhanced),
            "raw_enhancement": dict(self.raw_enhancement),
        }


class OpenAIQualityEnhancer:
    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        model: str | None = None,
        dry_run: bool | None = None,
        cache_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.model = (model or os.getenv("OPENAI_QUALITY_MODEL") or DEFAULT_MODEL).strip()
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_QUALITY_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.cache_dir = os.path.join(root, "project_brain", "content_brain_quality_cache")
        if cache_dir:
            self.cache_dir = str(cache_dir)
        self._api_key = ""
        self.enabled = self._resolve_enabled_state() or self.dry_run
        self._client: Any | None = None

    def maybe_enhance(self, *, context: dict[str, Any]) -> QualityEnhancementResult:
        audit_scores = dict(context.get("audit_scores") or {})
        trigger = evaluate_enhancement_triggers(
            audit_scores=audit_scores,
            classification_confidence=float(context.get("classification_confidence") or 0.0),
            story_payload=dict(context.get("story_payload") or {}),
            seo_title=str(context.get("seo_title") or ""),
            prompt_texts=list(context.get("prompt_texts") or []),
            topic_story_detail=dict(context.get("topic_story_detail") or {}),
            cross_domain_fusion=dict(context.get("cross_domain_fusion") or {}),
        )
        before_scores = _extract_score_snapshot(audit_scores)
        if not trigger.triggered:
            return QualityEnhancementResult(
                enabled=self.enabled,
                trigger_report=trigger,
                before_scores=before_scores,
                after_scores=before_scores,
                notes=["openai_quality_enhancement_not_needed"],
            )
        if not self.enabled:
            return QualityEnhancementResult(
                enabled=False,
                trigger_report=trigger,
                before_scores=before_scores,
                after_scores=before_scores,
                notes=["openai_quality_enhancer_disabled"],
            )

        topic = str(context.get("topic") or "")
        category = str(context.get("category") or "general")
        strategy = str(context.get("strategy") or "cinematic_narrative")
        language_code = str(context.get("language_code") or detect_language_code(topic))
        cache_key = _cache_key(topic, category, strategy, trigger.enhancement_types)
        cached = self._read_cache(cache_key)
        if cached is not None:
            raw = dict(cached.get("payload") or {})
            usage = dict(cached.get("usage") or {})
            cost = float(cached.get("estimated_cost_usd") or 0.0)
            notes = ["openai_quality_cache_hit"]
            cache_hit = True
        elif self.dry_run:
            raw = _build_dry_run_enhancement(context, trigger.enhancement_types)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            cost = 0.0
            notes = ["openai_quality_dry_run"]
            cache_hit = False
            self._write_cache(
                cache_key,
                {
                    "topic": topic,
                    "category": category,
                    "strategy": strategy,
                    "enhancement_types": trigger.enhancement_types,
                    "payload": raw,
                    "usage": usage,
                    "estimated_cost_usd": cost,
                },
            )
        else:
            if not self._api_key or OpenAI is None:
                return QualityEnhancementResult(
                    enabled=True,
                    trigger_report=trigger,
                    before_scores=before_scores,
                    after_scores=before_scores,
                    notes=["openai_client_unavailable"],
                )
            raw, usage, cost = self._call_openai(context, trigger.enhancement_types)
            if not raw:
                return QualityEnhancementResult(
                    enabled=True,
                    trigger_report=trigger,
                    before_scores=before_scores,
                    after_scores=before_scores,
                    notes=["openai_quality_enhancement_failed"],
                )
            notes = ["openai_quality_enhancement_applied"]
            cache_hit = False
            self._write_cache(
                cache_key,
                {
                    "topic": topic,
                    "category": category,
                    "strategy": strategy,
                    "enhancement_types": trigger.enhancement_types,
                    "payload": raw,
                    "usage": usage,
                    "estimated_cost_usd": cost,
                },
            )

        enhanced_payload, applied_types = apply_quality_enhancements(
            context=context,
            raw_enhancement=raw,
            requested_types=trigger.enhancement_types,
        )
        if not _topic_preserved(topic, enhanced_payload):
            return QualityEnhancementResult(
                enabled=True,
                trigger_report=trigger,
                before_scores=before_scores,
                after_scores=before_scores,
                notes=["openai_quality_rejected_topic_drift"],
                raw_enhancement=raw,
            )

        after_audit = dict(context)
        after_audit.update(enhanced_payload)
        after_scores = _estimate_after_scores(after_audit, before_scores)
        improvement = _build_improvement_summary(before_scores, after_scores)
        return QualityEnhancementResult(
            applied=bool(applied_types),
            enabled=True,
            model=self.model,
            trigger_report=trigger,
            enhancements_applied=applied_types,
            before_scores=before_scores,
            after_scores=after_scores,
            improvement_summary=improvement,
            cache_hit=cache_hit,
            usage=usage,
            estimated_cost_usd=cost,
            notes=notes,
            enhanced=enhanced_payload,
            raw_enhancement=raw,
        )

    def _call_openai(
        self,
        context: dict[str, Any],
        enhancement_types: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any], float]:
        client = self._client
        if client is None:
            client = OpenAI(api_key=self._api_key, timeout=REQUEST_TIMEOUT_SECONDS)
            self._client = client
        system_prompt = (
            "You improve weak short-form video content outputs. Return JSON only. "
            "Never change the topic, language, category, or strategy. "
            "Only enrich/refine/improve the requested sections. "
            "Write all strings in the same language as language_code. "
            "Include only requested enhancement sections. "
            "For domain_knowledge, replace generic placeholders with expert-level domain concepts "
            "specific to the topic (e.g. marketing agency, media buying, campaign automation). "
            "Weave domain concepts into story beats, prompt additions, and SEO titles — do not append generic filler."
        )
        user_payload = {
            "topic": context.get("topic"),
            "language_code": context.get("language_code"),
            "category": context.get("category"),
            "strategy": context.get("strategy"),
            "enhancement_types": enhancement_types,
            "current_seo_title": context.get("seo_title"),
            "current_seo_candidates": context.get("seo_candidates"),
            "current_character": (context.get("story_payload") or {}).get("main_character"),
            "current_domain_concepts": context.get("domain_concepts"),
            "intent_domain_concepts": context.get("intent_domain_concepts"),
            "intent_story_angles": context.get("intent_story_angles"),
            "current_story": {
                "logline": (context.get("story_payload") or {}).get("logline"),
                "clip_beats": (context.get("story_payload") or {}).get("clip_beats"),
                "setting": (context.get("story_payload") or {}).get("setting"),
            },
            "current_prompts": context.get("prompt_texts"),
            "required_output": {
                "seo_titles": "array of 5 improved titles if seo requested",
                "domain_concepts": "array of additional concepts if domain_knowledge requested",
                "character_role": "string if character requested",
                "story": "object with logline string and clip_beats array (same length) if story requested",
                "prompt_additions": "array of topic-specific detail lines if prompt requested",
            },
        }
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=0.45,
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


def maybe_enhance_quality(**context: Any) -> QualityEnhancementResult:
    enhancer = OpenAIQualityEnhancer()
    return enhancer.maybe_enhance(context=context)


def evaluate_enhancement_triggers(
    *,
    audit_scores: dict[str, Any],
    classification_confidence: float,
    story_payload: dict[str, Any],
    seo_title: str,
    prompt_texts: list[str],
    topic_story_detail: dict[str, Any],
    cross_domain_fusion: dict[str, Any] | None = None,
) -> EnhancementTriggerReport:
    reasons: list[str] = []
    types: list[str] = []
    story_text = _story_corpus(story_payload)
    character = str(story_payload.get("main_character") or "").lower()
    generic_content = any(marker in story_text for marker in GENERIC_STORY_MARKERS) or any(
        marker in character for marker in GENERIC_CHARACTER_MARKERS
    )
    domain_pack_missing = str(topic_story_detail.get("source") or "") in {"generic_extractor", ""}

    lang = float(audit_scores.get("language_authority_score") or 0.0)
    if lang < THRESHOLD_LANGUAGE:
        reasons.append(f"language_authority_score<{THRESHOLD_LANGUAGE}")

    char = float(audit_scores.get("character_quality_score") or 0.0)
    if char < THRESHOLD_CHARACTER or any(marker in character for marker in GENERIC_CHARACTER_MARKERS):
        reasons.append(f"character_quality_score<{THRESHOLD_CHARACTER}")
        if ENHANCEMENT_CHARACTER not in types:
            types.append(ENHANCEMENT_CHARACTER)

    domain = float(audit_scores.get("domain_knowledge_score") or 0.0)
    if domain < THRESHOLD_DOMAIN or domain_pack_missing:
        reasons.append(f"domain_knowledge_score<{THRESHOLD_DOMAIN}")
        if ENHANCEMENT_DOMAIN not in types:
            types.append(ENHANCEMENT_DOMAIN)

    story = float(audit_scores.get("story_specificity_score") or 0.0)
    if story < THRESHOLD_STORY or generic_content:
        reasons.append(f"story_specificity_score<{THRESHOLD_STORY}")
        if ENHANCEMENT_STORY not in types:
            types.append(ENHANCEMENT_STORY)

    seo = float(audit_scores.get("seo_title_quality_score") or 0.0)
    if seo < THRESHOLD_SEO or _seo_title_malformed(seo_title, str(story_payload.get("source_topic") or "")):
        reasons.append(f"seo_title_quality_score<{THRESHOLD_SEO}")
        if ENHANCEMENT_SEO not in types:
            types.append(ENHANCEMENT_SEO)

    prompt = float(audit_scores.get("prompt_specificity_score") or 0.0)
    narrative = float(audit_scores.get("narrative_detail_score") or 0.0)
    if prompt < THRESHOLD_PROMPT or narrative < 0.75:
        reasons.append(f"prompt_specificity_score<{THRESHOLD_PROMPT}")
        if ENHANCEMENT_PROMPT not in types:
            types.append(ENHANCEMENT_PROMPT)

    if generic_content:
        reasons.append("generic_content_detected")
    if domain_pack_missing:
        reasons.append("domain_pack_missing")
    if classification_confidence < THRESHOLD_CLASSIFICATION:
        reasons.append(f"classification_confidence<{THRESHOLD_CLASSIFICATION}")
        if ENHANCEMENT_DOMAIN not in types:
            types.append(ENHANCEMENT_DOMAIN)

    fusion = dict(cross_domain_fusion or story_payload.get("cross_domain_fusion") or {})
    if fusion.get("multi_domain") and ENHANCEMENT_SEO not in types:
        reasons.append("cross_domain_fusion_seo_refresh")
        types.append(ENHANCEMENT_SEO)

    return EnhancementTriggerReport(
        triggered=bool(types),
        reasons=reasons,
        enhancement_types=types,
        generic_content_detected=generic_content,
        domain_pack_missing=domain_pack_missing,
    )


def validate_enhancement_quality_gates(
    *,
    enhancement_applied: bool,
    audit_scores: dict[str, Any],
) -> tuple[bool, list[str]]:
    if not enhancement_applied:
        return True, []
    failures: list[str] = []
    domain = float(audit_scores.get("domain_knowledge_score") or 0.0)
    clip = float(audit_scores.get("clip_specificity_score") or 0.0)
    strategy = float(audit_scores.get("strategy_alignment_score") or 0.0)
    if domain < ENHANCEMENT_DOMAIN_KNOWLEDGE_MIN:
        failures.append(f"domain_knowledge_score<{ENHANCEMENT_DOMAIN_KNOWLEDGE_MIN}: {domain:.4f}")
    if clip < ENHANCEMENT_CLIP_SPECIFICITY_MIN:
        failures.append(f"clip_specificity_score<{ENHANCEMENT_CLIP_SPECIFICITY_MIN}: {clip:.4f}")
    if strategy < ENHANCEMENT_STRATEGY_ALIGNMENT_MIN:
        failures.append(f"strategy_alignment_score<{ENHANCEMENT_STRATEGY_ALIGNMENT_MIN}: {strategy:.4f}")
    return not failures, failures


def _fusion_payload(context: dict[str, Any]) -> dict[str, Any]:
    return dict(context.get("cross_domain_fusion") or {})


def _fusion_expert_concepts(context: dict[str, Any]) -> list[str]:
    fusion = _fusion_payload(context)
    if not fusion.get("multi_domain"):
        return []
    from content_brain.execution.content_brain_cross_domain_fusion import balance_fusion_domain_concepts

    balanced = balance_fusion_domain_concepts(
        fusion.get("domain_concepts_by_domain") or {},
        max_total=12,
    )
    return filter_expert_domain_concepts(balanced)


def _collect_expert_concepts(raw_enhancement: dict[str, Any], context: dict[str, Any]) -> list[str]:
    fusion_expert = _fusion_expert_concepts(context)
    if fusion_expert:
        return fusion_expert
    raw_concepts = list(
        raw_enhancement.get("domain_concepts")
        or raw_enhancement.get("additional_domain_concepts")
        or []
    )
    intent_concepts = list(context.get("intent_domain_concepts") or [])
    context_concepts = list(context.get("domain_concepts") or [])
    topic = str(context.get("topic") or "").lower()
    category = str(context.get("category") or "").lower()
    strategy = str(context.get("strategy") or "").lower()
    expert = filter_expert_domain_concepts(raw_concepts + intent_concepts + context_concepts)
    if expert:
        return list(dict.fromkeys(expert))
    if any(marker in topic for marker in ("marketing agency", "marketing agencies")) or (
        "marketing" in topic and "agenc" in topic
    ):
        return list(MARKETING_AGENCY_CONCEPTS[:12])
    if category in {"business", "marketing"} or strategy in {"business_debate", "future_analysis"}:
        if "marketing" in topic or "agenc" in topic:
            return list(MARKETING_AGENCY_CONCEPTS[:12])
    base_profile = get_domain_profile(str(context.get("topic") or ""), topic_category=category)
    if base_profile.domain_id != "general":
        return list(base_profile.concepts[:12])
    return []


def _inject_concepts_into_beats(
    beats: list[str],
    concepts: list[str],
    *,
    strategy: str,
    topic: str,
    story_angles: list[str] | None = None,
) -> list[str]:
    if not concepts:
        return beats
    angles = [str(item).strip() for item in (story_angles or []) if str(item).strip()]
    if angles and len(angles) >= len(beats or [""]):
        woven = []
        for index, angle in enumerate(angles[: max(len(beats or []), 3)]):
            concept = concepts[index % len(concepts)]
            if concept.lower() not in angle.lower():
                woven.append(f"{angle.rstrip('.')}, focusing on {concept}.")
            else:
                woven.append(angle)
        return woven[: max(len(beats or []), len(woven)) or 3]
    if not beats:
        if strategy == "business_debate":
            return [
                f"Open with a bold claim that AI could reshape {concepts[0]} and {concepts[1]} by 2026.",
                f"Compare evidence from {concepts[2]}, {concepts[3]}, and {concepts[4]} in agency workflows.",
                f"Deliver a verdict on {concepts[5]} and {concepts[6]} for traditional agencies.",
            ]
        return [
            f"Open with a topic-specific hook about {concepts[0]} and {topic.rstrip('?')}.",
            f"Demonstrate {concepts[1]} and {concepts[2]} with concrete evidence.",
            f"Close with the sharpest takeaway on {concepts[3]} and {concepts[4]}.",
        ]
    injected: list[str] = []
    for index, beat in enumerate(beats):
        concept = concepts[index % len(concepts)]
        cleaned = str(beat or "").strip()
        if not cleaned:
            continue
        if concept.lower() in cleaned.lower():
            injected.append(cleaned)
        else:
            injected.append(f"{cleaned.rstrip('.')}, highlighting {concept}.")
    return injected


def _weave_domain_logline(logline: str, concepts: list[str], topic: str, *, strategy: str) -> str:
    if not concepts:
        return logline
    profile = build_domain_profile_from_concepts(topic, concepts)
    corpus = logline or topic
    if score_domain_concept_usage(corpus, profile) >= 0.5:
        return logline or corpus
    core = ", ".join(concepts[:4])
    topic_clean = topic.rstrip("?")
    if strategy == "business_debate":
        return (
            logline
            or f"A marketing strategist debates whether AI will disrupt {topic_clean} through {core}."
        )
    if logline:
        return f"{logline.rstrip('.')}, weaving in {core}."
    return f"An expert breaks down {topic_clean} through {core} with concrete agency evidence."


def _build_domain_facts(topic: str, concepts: list[str], strategy: str) -> list[str]:
    topic_clean = topic.rstrip("?")
    facts = [
        f"{concept} is a core lever when evaluating {topic_clean}."
        for concept in concepts[:4]
    ]
    if strategy == "business_debate":
        facts.append(f"Agency economics hinge on retainers, {concepts[0]}, and {concepts[1]}.")
    return facts


def apply_quality_enhancements(
    *,
    context: dict[str, Any],
    raw_enhancement: dict[str, Any],
    requested_types: list[str],
) -> tuple[dict[str, Any], list[str]]:
    applied: list[str] = []
    story_payload = dict(context.get("story_payload") or {})
    topic_detail = dict(context.get("topic_story_detail") or {})
    prompt_texts = [str(item) for item in context.get("prompt_texts") or []]
    seo_title = str(context.get("seo_title") or "")
    seo_candidates = list(context.get("seo_candidates") or [])
    topic = str(context.get("topic") or "")
    strategy = str(context.get("strategy") or "")
    expert_concepts = _collect_expert_concepts(raw_enhancement, context)
    fusion = _fusion_payload(context)
    fusion_beats = [
        str(item).strip()
        for item in fusion.get("fused_clip_structure") or []
        if str(item).strip()
    ]

    if ENHANCEMENT_SEO in requested_types:
        subject = str(context.get("subject") or _extract_subject_phrase(topic))
        titles = raw_enhancement.get("seo_titles") or raw_enhancement.get("seo_title_candidates") or []
        intent_titles = list(context.get("intent_seo_candidates") or [])
        cleaned_titles = []
        for item in list(titles) + intent_titles:
            cleaned = _clean_seo_title(str(item))
            if cleaned and not is_malformed_seo_title(cleaned, topic, subject=subject):
                cleaned_titles.append(cleaned)
        if cleaned_titles:
            seo_title = cleaned_titles[0]
            seo_candidates = list(dict.fromkeys(cleaned_titles + seo_candidates))[:8]
            applied.append(ENHANCEMENT_SEO)

    if ENHANCEMENT_DOMAIN in requested_types and expert_concepts:
        topic_detail["entities"] = expert_concepts
        topic_detail["objects"] = expert_concepts[:4]
        topic_detail["facts"] = _build_domain_facts(topic, expert_concepts, strategy)
        topic_detail["source"] = "openai_quality_enhancement"
        story_payload["domain_concepts"] = expert_concepts
        if fusion.get("multi_domain") and fusion_beats:
            story_payload["clip_beats"] = fusion_beats[: len(story_payload.get("clip_beats") or fusion_beats)]
        else:
            story_payload["clip_beats"] = _inject_concepts_into_beats(
                list(story_payload.get("clip_beats") or []),
                expert_concepts,
                strategy=strategy,
                topic=topic,
                story_angles=list(context.get("intent_story_angles") or raw_enhancement.get("story_angles") or []),
            )
        if not fusion.get("multi_domain"):
            story_payload["logline"] = _weave_domain_logline(
                str(story_payload.get("logline") or ""),
                expert_concepts,
                topic,
                strategy=strategy,
            )
        if strategy in {"business_debate", "future_analysis", "technology_forecast"} and not fusion.get("multi_domain"):
            story_payload["main_character"] = story_payload.get("main_character") or _normalize_role("marketing strategist")
            story_payload["setting"] = story_payload.get("setting") or (
                "modern agency war room with campaign dashboards, media plans, and client pitch decks"
            )
        applied.append(ENHANCEMENT_DOMAIN)

    if ENHANCEMENT_CHARACTER in requested_types:
        role = str(raw_enhancement.get("character_role") or raw_enhancement.get("domain_role") or "").strip()
        if role and "presenter" not in role.lower():
            story_payload["main_character"] = _normalize_role(role)
            applied.append(ENHANCEMENT_CHARACTER)

    if ENHANCEMENT_STORY in requested_types:
        story_block = raw_enhancement.get("story") if isinstance(raw_enhancement.get("story"), dict) else raw_enhancement
        logline = str(story_block.get("logline") or raw_enhancement.get("logline") or "").strip()
        beats = story_block.get("clip_beats") if isinstance(story_block, dict) else raw_enhancement.get("clip_beats")
        current_beats = list(story_payload.get("clip_beats") or [])
        angles = list(
            raw_enhancement.get("story_angles")
            or context.get("intent_story_angles")
            or raw_enhancement.get("topic_facts")
            or []
        )
        if fusion.get("multi_domain") and fusion_beats:
            story_payload["clip_beats"] = fusion_beats[: len(story_payload.get("clip_beats") or fusion_beats)]
        elif logline:
            story_payload["logline"] = _weave_domain_logline(
                str(story_payload.get("logline") or logline),
                expert_concepts,
                topic,
                strategy=strategy,
            )
        if isinstance(beats, list) and beats and not (fusion.get("multi_domain") and fusion_beats):
            merged_beats = [str(b).strip() for b in beats if str(b).strip()]
            if expert_concepts:
                merged_beats = _inject_concepts_into_beats(
                    merged_beats,
                    expert_concepts,
                    strategy=strategy,
                    topic=topic,
                    story_angles=angles,
                )
            if not current_beats or len(merged_beats) == len(current_beats):
                story_payload["clip_beats"] = merged_beats[: len(current_beats) or len(merged_beats)]
        elif angles and expert_concepts and not (fusion.get("multi_domain") and fusion_beats):
            story_payload["clip_beats"] = _inject_concepts_into_beats(
                current_beats,
                expert_concepts,
                strategy=strategy,
                topic=topic,
                story_angles=angles,
            )
        if angles and not story_payload.get("logline"):
            story_payload["logline"] = _weave_domain_logline(
                _normalize(" ".join(str(a) for a in angles[:2])),
                expert_concepts,
                topic,
                strategy=strategy,
            )
        if logline or beats or angles:
            applied.append(ENHANCEMENT_STORY)

    if ENHANCEMENT_PROMPT in requested_types:
        additions = filter_expert_domain_concepts(
            list(raw_enhancement.get("prompt_additions") or raw_enhancement.get("topic_details") or [])
        )
        prompt_concepts = additions or expert_concepts[:8]
        if prompt_concepts:
            block = "Topic-specific detail: " + "; ".join(str(item).strip() for item in prompt_concepts[:8] if str(item).strip())
            prompt_texts = [_inject_prompt_detail(prompt, block) for prompt in prompt_texts]
            applied.append(ENHANCEMENT_PROMPT)
        elif topic_detail:
            block = _topic_detail_block(topic_detail)
            if block:
                prompt_texts = [_inject_prompt_detail(prompt, block) for prompt in prompt_texts]
                applied.append(ENHANCEMENT_PROMPT)

    return (
        {
            "story_payload": story_payload,
            "topic_story_detail": topic_detail,
            "seo_title": seo_title,
            "seo_candidates": seo_candidates,
            "prompt_texts": prompt_texts,
            "domain_concepts": expert_concepts,
            "_applied_types": applied,
        },
        applied,
    )


def _estimate_after_scores(after_context: dict[str, Any], before: dict[str, float]) -> dict[str, float]:
    from content_brain.execution.content_brain_quality_audit_v2 import run_quality_audit_v2

    topic = str(after_context.get("topic") or "")
    story = dict(after_context.get("story_payload") or {})
    expert_concepts = list(after_context.get("domain_concepts") or story.get("domain_concepts") or [])
    category = str(after_context.get("category") or "")
    strategy_plan = after_context.get("strategy_plan")
    prompt_texts = list(after_context.get("prompt_texts") or [])
    clip_payloads = list(after_context.get("clip_payloads") or [])
    if not clip_payloads:
        beats = list(story.get("clip_beats") or [])
        clip_payloads = [{"story_beat": beat, "scene": beat} for beat in beats]
    audit = run_quality_audit_v2(
        topic=topic,
        language_code=str(after_context.get("language_code") or detect_language_code(topic)),
        topic_preservation_score=float(
            after_context.get("topic_preservation_score") or before.get("topic_preservation_score") or 0.0
        ),
        story_payload=story,
        seo_title=str(after_context.get("seo_title") or ""),
        seo_title_quality_score=float(before.get("seo_title_quality_score") or 0.0),
        strategy_plan=strategy_plan,
        clip_payloads=clip_payloads,
        prompt_texts=prompt_texts,
        topic_category=category,
        domain_concepts=expert_concepts,
    )
    scores = dict(before)
    scores.update(
        {
            "language_authority_score": audit.language_authority_score,
            "domain_knowledge_score": audit.domain_knowledge_score,
            "character_quality_score": audit.character_quality_score,
            "story_specificity_score": audit.story_specificity_score,
            "seo_title_quality_score": audit.seo_title_quality_score,
            "prompt_specificity_score": audit.prompt_specificity_score,
            "narrative_detail_score": audit.narrative_detail_score,
            "clip_specificity_score": audit.clip_specificity_score,
            "strategy_alignment_score": audit.strategy_alignment_score,
            "overall_content_score": audit.overall_content_score,
        }
    )
    return scores


def _build_improvement_summary(before: dict[str, float], after: dict[str, float]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        b = float(before.get(key) or 0.0)
        a = float(after.get(key) or 0.0)
        if a <= b:
            continue
        delta = a - b
        summary[key] = {
            "before": round(b, 4),
            "after": round(a, 4),
            "delta": round(delta, 4),
            "percent": round((delta / max(b, 0.01)) * 100, 1),
        }
    return summary


def _extract_score_snapshot(audit_scores: dict[str, Any]) -> dict[str, float]:
    keys = (
        "language_authority_score",
        "domain_knowledge_score",
        "character_quality_score",
        "story_specificity_score",
        "strategy_alignment_score",
        "seo_title_quality_score",
        "clip_specificity_score",
        "prompt_specificity_score",
        "narrative_detail_score",
        "overall_content_score",
    )
    return {key: float(audit_scores.get(key) or 0.0) for key in keys}


def _topic_preserved(topic: str, enhanced: dict[str, Any]) -> bool:
    from content_brain.execution.content_brain_topic_authority import audit_story_brief_preservation

    story = dict(enhanced.get("story_payload") or {})
    audit = audit_story_brief_preservation(
        topic,
        {
            "logline": story.get("logline"),
            "main_character": story.get("main_character"),
            "setting": story.get("setting"),
            "clip_beats": story.get("clip_beats"),
        },
    )
    return float(audit.topic_preservation_score) >= 0.34


def _cache_key(topic: str, category: str, strategy: str, enhancement_types: list[str]) -> str:
    normalized = re.sub(r"\s+", " ", str(topic or "").strip().lower())
    types = ",".join(sorted(enhancement_types))
    digest = hashlib.sha256(
        f"{QUALITY_CACHE_VERSION}|{category}|{strategy}|{types}|{normalized}".encode("utf-8")
    ).hexdigest()
    return digest[:24]


def _build_dry_run_enhancement(context: dict[str, Any], enhancement_types: list[str]) -> dict[str, Any]:
    topic = str(context.get("topic") or "")
    lowered = topic.lower()
    subject = str(context.get("subject") or _extract_subject_phrase(topic))
    fusion = _fusion_payload(context)
    fusion_multi = bool(fusion.get("multi_domain"))
    payload: dict[str, Any] = {}
    if ENHANCEMENT_SEO in enhancement_types:
        if fusion_multi:
            payload["seo_titles"] = [
                topic[:72],
                f"Can Chemistry Predict a Perfume Bestseller?" if "bestseller" in lowered else f"The Truth About {subject.rstrip('?')}",
                f"What {subject.rstrip('?')} Means for the Market" if "market" in lowered or "bestseller" in lowered else f"Why {subject.rstrip('?')} Matters",
                f"The Science and Business of {subject.rstrip('?')}" if "chemistry" in lowered else f"What Everyone Gets Wrong About {subject.rstrip('?')}",
                subject[:72],
            ]
            payload["domain_concepts"] = _fusion_expert_concepts(context)
            payload["story_angles"] = list(fusion.get("fused_clip_structure") or [])
        elif "blockbuster" in lowered:
            payload["seo_titles"] = [
                "The Fatal Mistake That Killed Blockbuster",
                "How Netflix Beat a $5 Billion Giant",
                "Why Blockbuster Ignored the Future",
                "The Business Decision That Changed Entertainment Forever",
                "What Blockbuster Got Wrong About Streaming",
            ]
        elif "kodak" in lowered:
            payload["seo_titles"] = [
                "Why Kodak Failed After Inventing Digital Photography",
                "The Kodak Mistake That Changed an Industry",
                "How Kodak Lost the Digital Shift",
                "What Kodak Got Wrong About Innovation",
                "The Rise and Fall of Kodak",
            ]
        elif any(marker in lowered for marker in ("dyatlov", "mystery", "roanoke", "unsolved", "disappearance")):
            payload["seo_titles"] = [
                f"The Untold Story of {subject}",
                f"What Really Happened at {subject}?",
                f"The Most Disturbing Clue From {subject}",
                f"Why {subject} Still Has No Simple Answer",
                f"Why {subject} Remains Unsolved",
            ]
        elif "perfume" in lowered:
            if "last" in lowered or "longevity" in lowered or "all day" in lowered:
                payload["seo_titles"] = [
                    "The Science Behind Perfume Longevity",
                    "Why Some Perfumes Last All Day",
                    "What Makes Fragrance Longevity Work",
                    "How Concentration and Base Notes Affect Longevity",
                    "Why Your Perfume Fades Fast — The Mechanism Explained",
                ]
            else:
                payload["seo_titles"] = [
                    "Can You Master Perfume in One Day?",
                    "The One-Day Perfume Challenge Explained",
                    "Why Most Beginners Fail at Perfume Blending",
                    "What Perfume Notes Actually Do",
                    "The Fastest Way to Learn Perfume Basics",
                ]
        elif "fish" in lowered or "zander" in lowered:
            payload["seo_titles"] = [
                "The Zander Fishing Method That Actually Works",
                "Why This Zander Retrieve Gets More Bites",
                "The Simple Zander Fishing Setup Beginners Miss",
                "How to Hook Zander With Better Depth Control",
                "Stop Making This Zander Fishing Mistake",
            ]
        elif "pizza" in lowered or "dough" in lowered:
            payload["seo_titles"] = [
                "The Easiest Pizza Dough for Beginners",
                "Why Your Pizza Dough Never Works",
                "The Simple Pizza Dough Trick Most Beginners Miss",
                "How to Make Pizza Dough Step by Step",
                "Stop Making This Pizza Dough Mistake",
            ]
        else:
            payload["seo_titles"] = [
                f"Why {subject.rstrip('?')} Matters",
                f"The Truth About {subject.rstrip('?')}",
                f"What Everyone Gets Wrong About {subject.rstrip('?')}",
                f"The Real Story Behind {subject.rstrip('?')}",
                subject[:72],
            ]
    if ENHANCEMENT_DOMAIN in enhancement_types:
        fusion = _fusion_payload(context)
        if fusion.get("multi_domain"):
            payload["domain_concepts"] = _fusion_expert_concepts(context)
            payload["story_angles"] = list(fusion.get("fused_clip_structure") or [])
        elif "blockbuster" in lowered:
            payload["domain_concepts"] = [
                "Netflix",
                "DVD by mail",
                "Reed Hastings",
                "late fees",
                "subscription model",
                "digital transformation",
                "customer retention",
            ]
        elif "kodak" in lowered:
            payload["domain_concepts"] = ["film photography", "digital camera", "innovation", "market disruption", "Kodak moment"]
        elif "perfume" in lowered or ("fragrance" in lowered and ("last" in lowered or "longevity" in lowered)):
            payload["domain_concepts"] = [
                "top notes",
                "heart notes",
                "base notes",
                "fixatives",
                "projection",
                "longevity",
                "volatility",
                "maceration",
                "evaporation",
            ]
            payload["story_angles"] = [
                "Explain why some perfumes fade quickly while others linger all day with visible evidence and science.",
                "Compare molecules, concentration, base notes, fixatives, projection, and skin chemistry because volatility drives longevity.",
                "Deliver practical takeaways grounded in concentration, evidence, and lasting mechanism.",
            ]
        elif "fish" in lowered or "zander" in lowered:
            payload["domain_concepts"] = ["lure", "retrieve", "hook set", "depth", "strike", "tackle"]
        elif "pizza" in lowered or "dough" in lowered:
            payload["domain_concepts"] = ["hydration", "kneading", "proofing", "gluten", "oven spring"]
        elif "dyatlov" in lowered:
            payload["domain_concepts"] = ["Ural Mountains", "expedition tent", "1959", "hikers", "snow", "investigation"]
        elif "roanoke" in lowered:
            payload["domain_concepts"] = ["Croatoan", "settlers", "Roanoke Island", "archaeological evidence", "colonial settlement"]
        elif "marketing" in lowered and "agenc" in lowered:
            payload["domain_concepts"] = list(MARKETING_AGENCY_CONCEPTS[:12])
            payload["story_angles"] = list(context.get("intent_story_angles") or []) or [
                "Open with the claim that AI could reshape agency economics by 2026.",
                "Compare evidence from automation, media buying, and creative production trends.",
                "Deliver a verdict on which agency roles survive and which shrink.",
            ]
            payload["seo_titles"] = list(context.get("intent_seo_candidates") or []) or [
                "Will AI Replace Marketing Agencies by 2026?",
                "The AI Threat Most Agencies Ignore",
                "Can Agencies Survive the AI Revolution?",
                "Why AI Could Disrupt the Marketing Industry",
                "What AI Automation Means for Agencies in 2026",
            ]
            payload["character_role"] = "a marketing strategist"
        else:
            profile = get_domain_profile(topic, topic_category=str(context.get("category") or ""))
            if profile.domain_id != "general":
                payload["domain_concepts"] = list(profile.concepts[:8])
            else:
                payload["domain_concepts"] = filter_expert_domain_concepts(
                    [token for token in topic.split() if len(token) > 3][:6]
                )
    if ENHANCEMENT_CHARACTER in enhancement_types and not fusion_multi:
        if "blockbuster" in lowered or "kodak" in lowered or "netflix" in lowered:
            payload["character_role"] = "a business analyst"
        elif "dyatlov" in lowered or "roanoke" in lowered or "mystery" in lowered:
            payload["character_role"] = "a historian"
        elif "fish" in lowered or "zander" in lowered:
            payload["character_role"] = "an experienced angler"
        elif "perfume" in lowered:
            payload["character_role"] = "an aspiring perfumer"
        elif "pizza" in lowered or "dough" in lowered:
            payload["character_role"] = "a home baker"
        else:
            payload["character_role"] = "a focused analyst"
    if ENHANCEMENT_STORY in enhancement_types and not fusion_multi:
        story = dict(context.get("story_payload") or {})
        beats = list(story.get("clip_beats") or [])
        concepts = list(payload.get("domain_concepts") or _collect_expert_concepts(payload, context))
        angles = list(payload.get("story_angles") or context.get("intent_story_angles") or [])
        woven_beats = _inject_concepts_into_beats(
            beats,
            concepts,
            strategy=str(context.get("strategy") or ""),
            topic=topic,
            story_angles=angles,
        )
        payload["story"] = {
            "logline": _weave_domain_logline(
                f"A focused expert breaks down {topic.rstrip('?')} with concrete evidence, objects, and topic-specific stakes.",
                concepts,
                topic,
                strategy=str(context.get("strategy") or ""),
            ),
            "clip_beats": woven_beats
            or [
                f"Open with a topic-specific hook about {topic.rstrip('?')}.",
                f"Compare the key evidence and details behind {topic.rstrip('?')}.",
                f"Deliver the sharpest takeaway about {topic.rstrip('?')}.",
            ],
        }
    if ENHANCEMENT_PROMPT in enhancement_types:
        payload["prompt_additions"] = list(payload.get("domain_concepts") or [])[:6] or [topic]
    return payload


def _seo_title_malformed(title: str, topic: str = "", *, subject: str = "") -> bool:
    if is_malformed_seo_title(title, topic, subject=subject):
        return True
    lowered = str(title or "").lower()
    if not lowered:
        return True
    for pattern in MALFORMED_SEO_PATTERNS:
        if re.search(pattern, lowered):
            return True
    if lowered.startswith("how to why") or lowered.startswith("why how to"):
        return True
    return False


def _clean_seo_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    cleaned = re.sub(r"(?i)^how to why ", "", cleaned)
    cleaned = re.sub(r"(?i)^why how to ", "Why ", cleaned)
    return cleaned.strip(" .")


def _story_corpus(story_payload: dict[str, Any]) -> str:
    return " ".join(
        [
            str(story_payload.get("logline") or ""),
            str(story_payload.get("main_character") or ""),
            str(story_payload.get("setting") or ""),
            " ".join(str(b) for b in story_payload.get("clip_beats") or []),
        ]
    ).lower()


def _inject_prompt_detail(prompt: str, block: str) -> str:
    if block.lower() in prompt.lower():
        return prompt
    marker = "Strict negatives:"
    if marker in prompt:
        return prompt.replace(marker, f"{block}. {marker}")
    return f"{prompt} {block}"


def _topic_detail_block(topic_detail: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("facts", "entities", "objects", "settings"):
        for item in list(topic_detail.get(key) or [])[:3]:
            cleaned = str(item).strip()
            if cleaned:
                parts.append(cleaned)
    if not parts:
        return ""
    return "Topic-specific detail: " + "; ".join(parts[:6])


def _normalize_role(role: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(role or "").strip())
    if not cleaned:
        return cleaned
    if cleaned.lower().startswith(("a ", "an ", "the ")):
        return cleaned
    article = "an" if cleaned[0].lower() in "aeiou" else "a"
    return f"{article} {cleaned}"


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _estimate_cost_usd(model: str, usage: dict[str, Any]) -> float:
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if "mini" in model.lower():
        return (prompt_tokens * 0.0000004) + (completion_tokens * 0.0000016)
    return (prompt_tokens * 0.0000025) + (completion_tokens * 0.00001)


__all__ = [
    "OpenAIQualityEnhancer",
    "QualityEnhancementResult",
    "maybe_enhance_quality",
    "evaluate_enhancement_triggers",
    "apply_quality_enhancements",
    "validate_enhancement_quality_gates",
    "ENHANCEMENT_DOMAIN_KNOWLEDGE_MIN",
    "ENHANCEMENT_CLIP_SPECIFICITY_MIN",
    "ENHANCEMENT_STRATEGY_ALIGNMENT_MIN",
    "_extract_score_snapshot",
    "_build_improvement_summary",
]
