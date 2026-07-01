"""
Content Brain End-to-End Micro Test Studio.

Permanent intelligence pipeline test — no Runway, no Hailuo, no media generation.
Uses real trend providers when configured (DataForSEO, SerpAPI, OpenAI enricher).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_DIR = ROOT / "project_brain" / "content_brain_test_results"

from content_brain.execution.content_brain_character_builder import build_character
from content_brain.execution.content_brain_cross_domain_fusion import (
    audit_fused_strategy_alignment,
    resolve_cross_domain_fusion,
    score_cross_domain_fusion,
    validate_cross_domain_fusion_gates,
)
from content_brain.execution.content_brain_concept_distribution import (
    resolve_concept_distribution,
    score_prompt_diversity,
    validate_concept_distribution_gates,
)
from content_brain.execution.content_brain_prompt_cleanup import (
    resolve_prompt_cleanup,
    validate_prompt_cleanup_gates,
)
from content_brain.execution.content_brain_topic_label_generator import generate_topic_label
from content_brain.execution.content_brain_intent_intelligence import resolve_topic_intent
from content_brain.execution.content_brain_dynamic_domain_expert import (
    dynamic_expert_to_openai_enrichment,
    resolve_dynamic_domain_expert,
)
from content_brain.execution.content_brain_openai_classification_enricher import maybe_enrich_classification
from content_brain.execution.content_brain_openai_quality_enhancer import (
    _build_improvement_summary,
    _extract_score_snapshot,
    maybe_enhance_quality,
    validate_enhancement_quality_gates,
)
from content_brain.execution.content_brain_openai_story_enricher import maybe_enrich_story_brief
from content_brain.execution.content_brain_quality_audit_v2 import run_quality_audit_v2
from content_brain.execution.content_brain_seo_director import build_seo_director_package
from content_brain.execution.content_brain_studio_preflight import run_content_brain_studio_preflight
from content_brain.execution.content_brain_trend_intelligence import (
    analyze_trend_opportunities,
    classify_trend_mode_v2,
)
from content_brain.execution.domain_knowledge_layer import get_domain_profile
from content_brain.execution.story_strategy_library import resolve_story_strategy
from content_brain.execution.topic_knowledge_graph import get_knowledge_graph
from content_brain.execution.content_brain_topic_authority import (
    audit_story_brief_preservation,
    audit_topic_preservation,
    extract_topic_facets,
)
from content_brain.execution.content_brain_topic_locale import (
    detect_language_code,
    profile_with_output_language,
)
from content_brain.execution.content_brain_topic_strategy import (
    ContentStrategyPlan,
    TopicClassification,
    audit_post_prompt_strategy_alignment,
    build_content_strategy_plan,
    classify_topic,
)
from content_brain.execution.runway_prompt_builder import (
    RUNWAY_PROMPT_MAX_CHARS,
    build_continuity_prompts_from_brief,
    validate_prompt_bundle,
    validate_prompt_entity_gates,
)
from content_brain.execution.runway_story_brief_builder import (
    RunwayStoryBriefBuilder,
    StoryBriefInput,
)
from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
from content_brain.engines.video_format_planner import VideoFormatPlanner
from content_brain.profiles.profile_loader import ProfileLoader
from content_brain.schemas.content_brief import Platform


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 2)


@dataclass
class ContentBrainE2ETestInput:
    topic: str
    duration_seconds: int = 30
    platform: str = "youtube_shorts"
    niche: str = "general"
    mood: str = "emotional"
    clip_length_preference: int | None = None
    requested_clip_count: int | None = None


@dataclass
class StudioStepResult:
    step: int
    step_key: str
    title: str
    duration_ms: float = 0.0
    api_sources: list[str] = field(default_factory=list)
    provider_costs: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "step_key": self.step_key,
            "title": self.title,
            "duration_ms": self.duration_ms,
            "api_sources": list(self.api_sources),
            "provider_costs": dict(self.provider_costs),
            "payload": dict(self.payload),
            "error": self.error,
        }


@dataclass
class ContentBrainE2ETestResult:
    run_id: str
    started_at: str
    completed_at: str = ""
    status: str = "completed"
    input: dict[str, Any] = field(default_factory=dict)
    steps: list[StudioStepResult] = field(default_factory=list)
    quality_audit: dict[str, Any] = field(default_factory=dict)
    overall_content_score: float = 0.0
    export_paths: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "input": dict(self.input),
            "steps": [step.to_dict() for step in self.steps],
            "quality_audit": dict(self.quality_audit),
            "overall_content_score": round(self.overall_content_score, 4),
            "export_paths": dict(self.export_paths),
            "errors": list(self.errors),
            "total_duration_ms": self.total_duration_ms,
        }


class ContentBrainE2EMicroTestStudio:
    """Orchestrates Content Brain intelligence steps without media providers."""

    STUDIO_VERSION = "content_brain_e2e_micro_test_studio_v8_5"

    def __init__(self, project_root: str | Path = ROOT) -> None:
        self.project_root = Path(project_root).resolve()
        self.profile_loader = ProfileLoader(self.project_root)
        self.trend_engine = TrendDiscoveryEngine(self.project_root, use_provider_layer=True)
        self.format_planner = VideoFormatPlanner()
        self.story_brief_builder = RunwayStoryBriefBuilder()
        self.export_dir = DEFAULT_EXPORT_DIR

    def run(self, spec: ContentBrainE2ETestInput | dict[str, Any]) -> ContentBrainE2ETestResult:
        payload = self._coerce_input(spec)
        run_id = f"cb_e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        result = ContentBrainE2ETestResult(
            run_id=run_id,
            started_at=_now_stamp(),
            input=payload.to_dict() if hasattr(payload, "to_dict") else self._coerce_input(payload).__dict__,
        )
        result.input = {
            "topic": payload.topic,
            "duration_seconds": payload.duration_seconds,
            "platform": payload.platform,
            "niche": payload.niche,
            "mood": payload.mood,
            "clip_length_preference": payload.clip_length_preference,
            "requested_clip_count": payload.requested_clip_count,
            "studio_version": self.STUDIO_VERSION,
        }

        profile = self.profile_loader.resolve(niche=payload.niche)
        platform = self._resolve_platform(payload.platform)
        language_code = detect_language_code(payload.topic)
        localized_profile = profile_with_output_language(profile, language_code)
        preflight = run_content_brain_studio_preflight()
        result.input["language_code"] = language_code
        result.input["preflight"] = preflight

        authority_clip_count = int(payload.requested_clip_count or 0)
        strategy_clip_count = (
            authority_clip_count
            if authority_clip_count > 0
            else max(1, payload.duration_seconds // 10)
        )

        try:
            step1 = self._step_topic_authority(payload, language_code)
            result.steps.append(step1)

            step2 = self._step_trend_discovery(payload, localized_profile, platform)
            result.steps.append(step2)

            classification, strategy_plan, openai_classification, step_strategy = self._step_topic_strategy(
                payload,
                language_code,
                mood=payload.mood,
                clip_count=strategy_clip_count,
            )
            result.steps.append(step_strategy)

            fusion_result, step_fusion = self._step_cross_domain_fusion(
                payload,
                classification,
                strategy_plan,
                language_code=language_code,
                intent_payload=dict(step_strategy.payload.get("intent_intelligence") or {}),
                clip_count=strategy_clip_count,
            )
            result.steps.append(step_fusion)

            duration_plan, step4 = self._step_duration_plan(payload, profile, platform)
            result.steps.append(step4)

            if authority_clip_count > 0:
                from content_brain.platform.clip_count_authority import (
                    apply_authoritative_clip_count,
                    assert_clip_count_authority,
                    build_clip_count_authority,
                )

                authority = build_clip_count_authority(
                    requested_clip_count=authority_clip_count,
                    duration_seconds=payload.duration_seconds,
                    provider="runway",
                )
                duration_plan = apply_authoritative_clip_count(duration_plan, authority)
                step4.payload.update(
                    {
                        key: duration_plan[key]
                        for key in (
                            "clip_count",
                            "requested_clip_count",
                            "duration_seconds",
                            "target_duration_seconds",
                            "clip_count_authority_source",
                            "clip_count_authority_version",
                        )
                        if key in duration_plan
                    }
                )
                assert_clip_count_authority(
                    requested=authority_clip_count,
                    actual=int(duration_plan.get("clip_count") or 0),
                    stage="duration_planner",
                )

            seo_package, step_seo_title = self._step_seo_title(
                payload,
                step2.payload,
                language_code,
                strategy_plan,
                profile=localized_profile,
            )
            result.steps.append(step_seo_title)

            dynamic_expert_payload = dict(step_strategy.payload.get("dynamic_domain_expert") or {})
            story_openai_enrichment = self._resolve_story_openai_enrichment(
                openai_classification,
                step_strategy.payload.get("intent_intelligence"),
                dynamic_expert_payload,
            )
            story_brief, step3 = self._step_story_generation(
                payload,
                duration_plan,
                seo_title=seo_package.seo_title,
                related_trends=[str(item.get("trend") or "") for item in (step2.payload.get("trends") or [])[:5]],
                language_code=language_code,
                strategy_plan=strategy_plan,
                classification=classification,
                openai_enrichment=story_openai_enrichment,
                cross_domain_fusion=fusion_result.to_dict(),
            )
            result.steps.append(step3)

            if authority_clip_count > 0:
                from content_brain.platform.clip_count_authority import assert_clip_count_authority

                assert_clip_count_authority(
                    requested=authority_clip_count,
                    actual=int(getattr(story_brief, "clip_count", 0) or 0),
                    stage="story_package",
                )

            preservation = audit_story_brief_preservation(payload.topic, step3.payload.get("story") or {})
            step1.payload["story_preservation"] = preservation.to_dict()
            step1.payload["preserved_subject"] = preservation.preserved_subject
            step1.payload["preserved_environment"] = preservation.preserved_environment
            step1.payload["preserved_action"] = preservation.preserved_action
            step1.payload["topic_preservation_score"] = preservation.topic_preservation_score

            step5 = self._step_clip_planner(story_brief, duration_plan)
            result.steps.append(step5)

            story_brief, step_distribution = self._step_concept_distribution(
                payload,
                story_brief,
                duration_plan,
                fusion_result=fusion_result,
                strategy_plan=strategy_plan,
                language_code=language_code,
            )
            result.steps.append(step_distribution)
            step3.payload["story"] = story_brief.to_dict()

            step6 = self._step_prompt_generation(
                story_brief,
                payload,
                strategy_plan=strategy_plan,
                classification=classification,
                language_code=language_code,
                seo_title=str(seo_package.seo_title or ""),
                preservation_score=float(
                    getattr(preservation, "topic_preservation_score", step1.payload.get("topic_preservation_score") or 0.0)
                ),
            )
            result.steps.append(step6)

            if authority_clip_count > 0:
                from content_brain.platform.clip_count_authority import assert_clip_count_authority

                assert_clip_count_authority(
                    requested=authority_clip_count,
                    actual=len(step6.payload.get("clip_prompts") or []),
                    stage="prompt_builder",
                )

            step6b = self._step_prompt_cleanup(step6, payload, expected_clip_count=authority_clip_count or None)
            result.steps.append(step6b)

            if authority_clip_count > 0:
                from content_brain.platform.clip_count_authority import assert_clip_count_authority

                assert_clip_count_authority(
                    requested=authority_clip_count,
                    actual=int(step6b.payload.get("clip_count") or len(step6b.payload.get("clip_prompts") or [])),
                    stage="prompt_cleanup",
                )

            step7 = self._step_seo_generation(
                payload,
                profile,
                story_brief,
                step2.payload,
                seo_package,
            )
            result.steps.append(step7)

            step8 = self._step_quality_audit(
                step1,
                step2,
                step3,
                step4,
                step5,
                step6,
                step7,
                preservation,
                strategy_plan,
                language_code=language_code,
                classification=classification,
                seo_title=str(step_seo_title.payload.get("seo_title") or seo_package.seo_title),
                seo_title_quality_score=float(
                    step_seo_title.payload.get("seo_score") or getattr(seo_package, "seo_score", 0.0) or 0.0
                ),
                step_num=10,
                prompt_cleanup_step=step6b,
            )
            step8.payload["audit_phase"] = "before_enhancement"
            result.steps.append(step8)

            enhancement, step9_enhance = self._step_openai_quality_enhancement(
                payload,
                step1,
                step2,
                step3,
                step4,
                step5,
                step6,
                step7,
                step8,
                preservation,
                strategy_plan,
                classification=classification,
                language_code=language_code,
                seo_package=seo_package,
                intent_intelligence=dict(step_strategy.payload.get("intent_intelligence") or {}),
            )
            result.steps.append(step9_enhance)
            if enhancement.applied:
                step3 = self._apply_enhancement_to_story_step(step3, enhancement)
                step5 = self._apply_enhancement_to_clip_step(step5, enhancement)
                step6 = self._apply_enhancement_to_prompt_step(step6, enhancement)
                step6b = self._step_prompt_cleanup(step6, payload)
                step7 = self._apply_enhancement_to_seo_step(step7, enhancement, seo_package)
                step_seo_title = self._apply_enhancement_to_seo_title_step(step_seo_title, enhancement)
                for index, step in enumerate(result.steps):
                    if step.step_key == "story_generation":
                        result.steps[index] = step3
                    elif step.step_key == "clip_planner":
                        result.steps[index] = step5
                    elif step.step_key == "prompt_generation":
                        result.steps[index] = step6
                    elif step.step_key == "prompt_cleanup":
                        result.steps[index] = step6b
                    elif step.step_key == "seo_generation":
                        result.steps[index] = step7
                    elif step.step_key == "seo_title":
                        result.steps[index] = step_seo_title

            step10 = self._step_quality_audit(
                step1,
                step2,
                step3,
                step4,
                step5,
                step6,
                step7,
                preservation,
                strategy_plan,
                language_code=language_code,
                classification=classification,
                seo_title=str(
                    step_seo_title.payload.get("seo_title")
                    or step7.payload.get("seo_title")
                    or seo_package.seo_title
                ),
                seo_title_quality_score=float(
                    step_seo_title.payload.get("seo_score")
                    or step7.payload.get("seo_score")
                    or getattr(seo_package, "seo_score", 0.0)
                    or 0.0
                ),
                prompt_cleanup_step=step6b,
                step_num=12,
            )
            after_scores = _extract_score_snapshot(step10.payload)
            step10.payload["audit_phase"] = "after_enhancement"
            step10.payload["quality_enhancement"] = enhancement.to_dict()
            step10.payload["raw_enhancement"] = dict(getattr(enhancement, "raw_enhancement", {}) or {})
            step10.payload["scores_before_enhancement"] = enhancement.before_scores
            step10.payload["scores_after_enhancement"] = after_scores
            step10.payload["improvement_summary"] = _build_improvement_summary(
                enhancement.before_scores,
                after_scores,
            )
            gates_passed, gate_failures = validate_enhancement_quality_gates(
                enhancement_applied=bool(enhancement.applied),
                audit_scores=step10.payload,
            )
            step10.payload["enhancement_quality_gates_passed"] = gates_passed
            step10.payload["enhancement_quality_gate_failures"] = gate_failures
            if enhancement.applied and not gates_passed:
                step10.payload["passed"] = False
                warnings = list(step10.payload.get("warnings") or [])
                warnings.extend(gate_failures)
                step10.payload["warnings"] = warnings
            enhancement.after_scores = after_scores
            enhancement.improvement_summary = step10.payload["improvement_summary"]
            result.steps.append(step10)
            result.quality_audit = step10.payload
            result.overall_content_score = float(step10.payload.get("overall_content_score") or 0.0)

            step11 = self._step_export(result)
            result.steps.append(step11)
            result.export_paths = dict(step11.payload.get("paths") or {})
        except Exception as exc:
            result.status = "failed"
            result.errors.append(str(exc))
            result.steps.append(
                StudioStepResult(
                    step=99,
                    step_key="fatal",
                    title="Fatal Error",
                    error=str(exc),
                )
            )

        result.completed_at = _now_stamp()
        result.total_duration_ms = _ms(started)
        result.steps.sort(key=lambda item: item.step)
        return result

    def _coerce_input(self, spec: ContentBrainE2ETestInput | dict[str, Any]) -> ContentBrainE2ETestInput:
        if isinstance(spec, ContentBrainE2ETestInput):
            return spec
        return ContentBrainE2ETestInput(
            topic=str(spec.get("topic") or "").strip(),
            duration_seconds=int(spec.get("duration_seconds") or spec.get("duration") or 30),
            platform=str(spec.get("platform") or "youtube_shorts"),
            niche=str(spec.get("niche") or "general"),
            mood=str(spec.get("mood") or "emotional"),
            clip_length_preference=(
                int(spec["clip_length_preference"])
                if spec.get("clip_length_preference") not in (None, "")
                else None
            ),
        )

    @staticmethod
    def _resolve_platform(value: str) -> Platform:
        cleaned = str(value or "youtube_shorts").strip().lower().replace("-", "_")
        aliases = {
            "youtube_shorts": Platform.YOUTUBE_SHORTS,
            "shorts": Platform.YOUTUBE_SHORTS,
            "tiktok": Platform.TIKTOK,
            "instagram_reels": Platform.INSTAGRAM_REELS,
            "reels": Platform.INSTAGRAM_REELS,
        }
        return aliases.get(cleaned, Platform.YOUTUBE_SHORTS)

    def _step_topic_authority(
        self,
        payload: ContentBrainE2ETestInput,
        language_code: str,
    ) -> StudioStepResult:
        start = time.perf_counter()
        subject, environment, action = extract_topic_facets(payload.topic)
        audit = audit_topic_preservation(payload.topic)
        step = StudioStepResult(
            step=1,
            step_key="topic_authority",
            title="User Topic Authority Test",
            duration_ms=_ms(start),
            api_sources=["content_brain_topic_authority", "content_brain_topic_locale"],
            payload={
                "original_topic": payload.topic,
                "detected_language_code": language_code,
                "extracted_subject": subject,
                "extracted_environment": environment,
                "extracted_action": action,
                "preserved_subject": audit.preserved_subject,
                "preserved_environment": audit.preserved_environment,
                "preserved_action": audit.preserved_action,
                "topic_preservation_score": audit.topic_preservation_score,
                "forbidden_drift_detected": audit.forbidden_drift_detected,
            },
        )
        return step

    def _step_trend_discovery(
        self,
        payload: ContentBrainE2ETestInput,
        profile: dict[str, Any],
        platform: Platform,
    ) -> StudioStepResult:
        start = time.perf_counter()
        discovery = self.trend_engine.discover(
            profile=profile,
            niche=payload.niche,
            topic=payload.topic,
            platforms=[platform],
            max_results=10,
            use_provider_layer=True,
        )
        trends = []
        raw_outputs: list[dict[str, Any]] = []
        for opp in discovery.opportunities:
            meta = dict(getattr(opp, "metadata", {}) or {})
            item = {
                "trend": opp.topic,
                "source": opp.source,
                "score": round(float(opp.scores.overall_trend_score), 4),
                "confidence": round(float(meta.get("provider_confidence") or 0.0), 4),
                "provider_id": str(meta.get("provider_id") or ""),
                "metadata": meta,
            }
            trends.append(item)
            if meta:
                raw_outputs.append(
                    {
                        "provider_id": item["provider_id"] or opp.source,
                        "raw": meta,
                    }
                )
        best = discovery.best_signal.to_dict() if discovery.best_signal else {}
        trend_mode = classify_trend_mode_v2(list(discovery.sources_used), use_live_trends=True)
        trend_intel = analyze_trend_opportunities(trends, topic=payload.topic, trend_mode=trend_mode)
        return StudioStepResult(
            step=2,
            step_key="trend_discovery",
            title="Live Trend Discovery",
            duration_ms=_ms(start),
            api_sources=list(discovery.sources_used) or ["trend_discovery_engine"],
            payload={
                "trends": trends,
                "best_signal": best,
                "sources_used": list(discovery.sources_used),
                "trend_mode": trend_mode,
                "trend_intelligence": trend_intel,
                "raw_provider_outputs": raw_outputs,
                "niche": discovery.niche,
            },
        )

    def _step_topic_strategy(
        self,
        payload: ContentBrainE2ETestInput,
        language_code: str,
        *,
        mood: str = "emotional",
        clip_count: int = 3,
    ) -> tuple[TopicClassification, ContentStrategyPlan, Any, StudioStepResult]:
        start = time.perf_counter()
        classification = classify_topic(payload.topic, language_code=language_code)
        openai_classification = maybe_enrich_classification(
            topic=payload.topic,
            classification=classification,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
        )
        if openai_classification.applied and openai_classification.classification is not None:
            classification = openai_classification.classification
        dynamic_expert = resolve_dynamic_domain_expert(
            topic=payload.topic,
            classification=classification,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
        )
        if dynamic_expert.used and dynamic_expert.classification is not None:
            classification = dynamic_expert.classification
        intent_resolution = resolve_topic_intent(
            payload.topic,
            classification,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
        )
        classification = intent_resolution.classification
        strategy_plan = intent_resolution.strategy_plan or build_content_strategy_plan(
            payload.topic,
            classification,
            language_code=language_code,
            mood=mood,
            clip_count=clip_count,
        )
        if dynamic_expert.used and dynamic_expert.strategy_plan is not None:
            strategy_plan = dynamic_expert.strategy_plan
        openai_enrichment = self._merge_openai_enrichment(
            openai_classification,
            intent_resolution.intent.to_dict(),
        )
        if dynamic_expert.used and dynamic_expert.payload is not None:
            openai_enrichment = dynamic_expert_to_openai_enrichment(dynamic_expert.payload)
        domain_profile = dynamic_expert.domain_profile or get_domain_profile(
            payload.topic,
            topic_category=classification.topic_category,
            openai_enrichment=openai_enrichment,
        )
        knowledge_graph = get_knowledge_graph(payload.topic, topic_category=classification.topic_category)
        character = build_character(
            payload.topic,
            explicit_character=openai_classification.enrichment.domain_role if openai_classification.enrichment else "",
            topic_category=classification.topic_category,
            language_code=language_code,
        )
        story_strategy = resolve_story_strategy(classification.content_strategy)
        api_sources = [
            "content_brain_topic_strategy",
            "content_brain_intent_intelligence",
            "domain_knowledge_layer",
            "topic_knowledge_graph",
            "content_brain_character_builder",
            "story_strategy_library",
        ]
        if openai_classification.applied:
            api_sources.append("openai_classification_enricher")
        elif openai_classification.notes:
            api_sources.append("openai_classification_enricher_skipped")
        if dynamic_expert.used:
            api_sources.append("openai_dynamic_domain_expert")
        elif dynamic_expert.notes:
            api_sources.append("openai_dynamic_domain_expert_skipped")
        if intent_resolution.intent.openai_applied:
            api_sources.append("openai_intent_enricher")
        return classification, strategy_plan, openai_classification, StudioStepResult(
            step=3,
            step_key="topic_classification",
            title="Topic Classification, Intent & Strategy",
            duration_ms=_ms(start),
            api_sources=api_sources,
            payload={
                "classification": classification.to_dict(),
                "intent_intelligence": intent_resolution.intent.to_dict(),
                "content_strategy": strategy_plan.to_dict(),
                "domain_knowledge": domain_profile.to_dict(),
                "knowledge_graph": knowledge_graph,
                "character_builder": character.to_dict(),
                "story_strategy": story_strategy.to_dict(),
                "detected_language_code": language_code,
                "openai_classification": openai_classification.to_dict(),
                "dynamic_domain_expert": dynamic_expert.to_dict(),
            },
        )

    @staticmethod
    def _merge_openai_enrichment(openai_classification: Any, intent_payload: dict[str, Any] | None) -> dict[str, Any] | None:
        enrichment: dict[str, Any] = {}
        if openai_classification.enrichment:
            enrichment.update(openai_classification.enrichment.to_dict())
        intent = dict(intent_payload or {})
        if intent.get("domain_concepts"):
            merged = list(dict.fromkeys(list(enrichment.get("domain_concepts") or []) + list(intent.get("domain_concepts") or [])))
            enrichment["domain_concepts"] = merged
        if intent.get("story_angles"):
            enrichment["story_angles"] = list(intent.get("story_angles") or [])
        if intent.get("seo_title_candidates"):
            enrichment["seo_title_candidates"] = list(intent.get("seo_title_candidates") or [])
        return enrichment or None

    @staticmethod
    def _resolve_story_openai_enrichment(
        openai_classification: Any,
        intent_payload: dict[str, Any] | None,
        dynamic_expert_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if dynamic_expert_payload.get("used") and dynamic_expert_payload.get("payload"):
            expert_payload = dict(dynamic_expert_payload.get("payload") or {})
            profile = dict(expert_payload.get("domain_profile") or {})
            clip_structure = dict(profile.get("clip_structure") or {})
            story_angles = [
                str(clip_structure.get("clip_1") or "").strip(),
                str(clip_structure.get("clip_2") or "").strip(),
                str(clip_structure.get("clip_3") or "").strip(),
            ]
            story_angles = [angle for angle in story_angles if angle]
            if not story_angles:
                story_angles = list(profile.get("timeline_beats") or [])
            return {
                "category": expert_payload.get("category"),
                "strategy": expert_payload.get("strategy"),
                "domain_role": profile.get("expert_role"),
                "domain_concepts": list(profile.get("core_concepts") or []),
                "setting": profile.get("setting"),
                "story_angles": story_angles,
                "visual_objects": list(profile.get("visual_objects") or []),
                "timeline_beats": list(profile.get("timeline_beats") or []),
                "clip_structure": clip_structure,
                "confidence": expert_payload.get("confidence"),
            }
        return ContentBrainE2EMicroTestStudio._merge_openai_enrichment(
            openai_classification,
            intent_payload,
        )

    def _step_cross_domain_fusion(
        self,
        payload: ContentBrainE2ETestInput,
        classification: TopicClassification,
        strategy_plan: ContentStrategyPlan | None,
        *,
        language_code: str = "en",
        intent_payload: dict[str, Any] | None = None,
        clip_count: int = 3,
    ) -> tuple[Any, StudioStepResult]:
        del strategy_plan
        start = time.perf_counter()
        fusion = resolve_cross_domain_fusion(
            payload.topic,
            classification,
            intent_payload=intent_payload,
            language_code=language_code,
            clip_count=clip_count,
        )
        api_sources = ["content_brain_cross_domain_fusion"]
        if fusion.openai_fusion_used:
            api_sources.append("openai_cross_domain_fusion")
        if fusion.cache_hit:
            api_sources.append("cross_domain_fusion_cache")
        return fusion, StudioStepResult(
            step=4,
            step_key="cross_domain_fusion",
            title="Cross-Domain Fusion",
            duration_ms=_ms(start),
            api_sources=api_sources,
            payload=fusion.to_dict(),
        )

    def _step_seo_title(
        self,
        payload: ContentBrainE2ETestInput,
        trend_payload: dict[str, Any],
        language_code: str,
        strategy_plan: ContentStrategyPlan | None = None,
        *,
        profile: dict[str, Any] | None = None,
    ) -> tuple[Any, StudioStepResult]:
        start = time.perf_counter()
        package = build_seo_director_package(
            topic=payload.topic,
            trends=list(trend_payload.get("trends") or []),
            platform=payload.platform,
            language_code=language_code,
            mood=strategy_plan.effective_mood if strategy_plan else payload.mood,
            strategy_plan=strategy_plan,
            audience_level="general",
            profile=dict(profile or {}),
            niche=payload.niche,
        )
        api_sources = [
            "content_brain_seo_director",
            "content_brain_seo_provider_bridge",
            "content_brain_openai_seo_polisher",
        ]
        if getattr(package, "dataforseo_used", False):
            api_sources.append("dataforseo")
        if getattr(package, "serpapi_used", False):
            api_sources.append("serpapi")
        if getattr(package, "dataforseo_youtube_used", False):
            api_sources.append("dataforseo_youtube")
        if getattr(package, "seo_data_source", "") == "fallback_templates":
            api_sources.append("seo_template_fallback")
        return package, StudioStepResult(
            step=5,
            step_key="seo_title",
            title="SEO Title Generation",
            duration_ms=_ms(start),
            api_sources=api_sources,
            payload={
                **package.to_dict(),
                "content_strategy": strategy_plan.strategy_id if strategy_plan else "",
                "selected_seo_title": package.seo_title,
            },
        )

    def _step_story_generation(
        self,
        payload: ContentBrainE2ETestInput,
        duration_plan: dict[str, Any],
        *,
        seo_title: str = "",
        related_trends: list[str] | None = None,
        language_code: str = "en",
        strategy_plan: ContentStrategyPlan | None = None,
        classification: TopicClassification | None = None,
        openai_enrichment: dict[str, Any] | None = None,
        cross_domain_fusion: dict[str, Any] | None = None,
    ) -> tuple[Any, StudioStepResult]:
        start = time.perf_counter()
        clip_count = int(duration_plan.get("clip_count") or 3)
        clip_duration = int(duration_plan.get("clip_duration_seconds") or 10)
        effective_mood = strategy_plan.effective_mood if strategy_plan else payload.mood
        niche_style = strategy_plan.niche_style if strategy_plan else (
            payload.niche if payload.niche != "general" else "cinematic"
        )
        brief = self.story_brief_builder.build(
            StoryBriefInput(
                topic=payload.topic,
                target_platform=payload.platform,
                niche_style=niche_style,
                mood=effective_mood,
                clip_count=clip_count,
                duration_seconds=clip_duration,
                seo_title=seo_title,
                related_trends=tuple(related_trends or ()),
                language_code=language_code,
                content_strategy=strategy_plan.strategy_id if strategy_plan else "",
                strategy_clip_beats=tuple(strategy_plan.clip_beats if strategy_plan else ()),
                strategy_conflict=strategy_plan.conflict if strategy_plan else "",
                strategy_visual_hook=strategy_plan.visual_hook if strategy_plan else "",
                strategy_niche_style=strategy_plan.niche_style if strategy_plan else "",
                strategy_effective_mood=effective_mood,
                topic_category=classification.topic_category if classification else "",
                openai_enrichment=openai_enrichment,
                cross_domain_fusion=cross_domain_fusion,
            )
        )
        brief, enrichment = maybe_enrich_story_brief(
            brief,
            topic=payload.topic,
            seo_title=seo_title,
            language_code=language_code,
            mood=effective_mood,
            platform=payload.platform,
            related_trends=related_trends,
            content_strategy=strategy_plan.strategy_id if strategy_plan else "",
            strategy_purpose=strategy_plan.purpose if strategy_plan else "",
            forbidden_filler=list(strategy_plan.forbidden_filler if strategy_plan else ()),
        )
        story = brief.to_dict()
        story["goal"] = brief.conflict_tension
        story["conflict"] = brief.conflict_tension
        story["tension"] = brief.conflict_tension
        story["seo_title"] = seo_title
        story["language_code"] = language_code
        if strategy_plan:
            story["content_strategy"] = strategy_plan.strategy_id
            story["content_strategy_label"] = strategy_plan.label
        if classification:
            story["topic_category"] = classification.topic_category
        if openai_enrichment:
            story["openai_classification"] = openai_enrichment
        if cross_domain_fusion:
            story["cross_domain_fusion"] = cross_domain_fusion
        character_result = build_character(
            payload.topic,
            topic_category=classification.topic_category if classification else "",
            language_code=language_code,
        )
        story["character_builder"] = character_result.to_dict()
        api_sources = ["runway_story_brief_builder", "content_brain_topic_strategy", "content_brain_character_builder"]
        if enrichment.applied:
            api_sources.append("openai_story_enricher")
        return brief, StudioStepResult(
            step=6,
            step_key="story_generation",
            title="Story Generation",
            duration_ms=_ms(start),
            api_sources=api_sources,
            payload={
                "story": story,
                "seo_title": seo_title,
                "language_code": language_code,
                "content_strategy": strategy_plan.to_dict() if strategy_plan else {},
                "openai_enrichment": enrichment.to_dict(),
            },
        )

    def _step_duration_plan(
        self,
        payload: ContentBrainE2ETestInput,
        profile: dict[str, Any],
        platform: Platform,
    ) -> tuple[dict[str, Any], StudioStepResult]:
        start = time.perf_counter()
        plan = self.format_planner.plan(
            profile=profile,
            platform=platform,
            user_duration_seconds=payload.duration_seconds,
            provider_name="runway",
            provider_clip_duration_seconds=payload.clip_length_preference,
        )
        reasoning = [plan.selection_reason] if plan.selection_reason else []
        if plan.metadata:
            reasoning.extend(str(v) for v in plan.metadata.values() if isinstance(v, str))
        payload_out = {
            "duration_seconds": payload.duration_seconds,
            "clip_count": plan.clip_count,
            "clip_duration_seconds": plan.clip_duration_seconds,
            "target_duration_seconds": plan.target_duration_seconds,
            "format_type": str(getattr(plan.format_type, "value", plan.format_type)),
            "reasoning": reasoning,
            "examples": {
                "10s": "1 clip @ 10s",
                "30s": "3 clips @ 10s",
                "50s": "5 clips @ 10s",
            },
        }
        return payload_out, StudioStepResult(
            step=4,
            step_key="duration_planner",
            title="Duration Planner",
            duration_ms=_ms(start),
            api_sources=["video_format_planner"],
            payload=payload_out,
        )

    def _step_clip_planner(
        self,
        story_brief: Any,
        duration_plan: dict[str, Any],
    ) -> StudioStepResult:
        start = time.perf_counter()
        clip_count = int(duration_plan.get("clip_count") or len(story_brief.clip_beats))
        roles = ["hook", "escalation", "payoff"]
        clips: list[dict[str, Any]] = []
        beats = list(story_brief.clip_beats or [])
        for index in range(clip_count):
            beat = beats[index] if index < len(beats) else ""
            if index == 0:
                purpose = "hook"
            elif index >= clip_count - 1:
                purpose = "payoff"
            else:
                purpose = "escalation"
            clips.append(
                {
                    "clip_index": index + 1,
                    "purpose": purpose,
                    "scene": beat or f"Clip {index + 1} story beat",
                    "role_label": roles[min(index, len(roles) - 1)] if index < len(roles) else purpose,
                    "story_beat": beat,
                }
            )
        return StudioStepResult(
            step=7,
            step_key="clip_planner",
            title="Clip Planner",
            duration_ms=_ms(start),
            api_sources=["runway_story_brief_builder"],
            payload={"clip_count": clip_count, "clips": clips},
        )

    def _step_concept_distribution(
        self,
        payload: ContentBrainE2ETestInput,
        story_brief: Any,
        duration_plan: dict[str, Any],
        *,
        fusion_result: Any,
        strategy_plan: ContentStrategyPlan | None = None,
        language_code: str = "en",
    ) -> tuple[Any, StudioStepResult]:
        start = time.perf_counter()
        clip_count = int(duration_plan.get("clip_count") or getattr(story_brief, "clip_count", 3) or 3)
        fusion_payload = dict(getattr(story_brief, "cross_domain_fusion", {}) or fusion_result.to_dict())
        topic_detail = dict(getattr(story_brief, "topic_story_detail", {}) or {})
        flat_concepts = list(getattr(story_brief, "domain_concepts", []) or topic_detail.get("domain_concepts") or [])

        label_result = generate_topic_label(payload.topic, language_code=language_code)
        story_brief.topic_label = label_result.label
        story_brief.topic_label_quality_score = float(label_result.quality_score)
        topic_detail["subject"] = label_result.label
        topic_detail["topic_label"] = label_result.label
        story_brief.topic_story_detail = topic_detail

        distribution = resolve_concept_distribution(
            payload.topic,
            clip_count=clip_count,
            domain_concepts_by_domain=dict(fusion_payload.get("domain_concepts_by_domain") or {}),
            flat_concepts=flat_concepts,
            clip_beats=list(getattr(story_brief, "clip_beats", []) or []),
            content_strategy=strategy_plan.strategy_id if strategy_plan else getattr(story_brief, "content_strategy", ""),
            strategic_angle=str(fusion_payload.get("strategic_angle") or ""),
            cross_domain_fusion=fusion_payload,
            fusion_score=float(fusion_payload.get("cross_domain_fusion_score") or 0.0),
            language_code=language_code,
        )
        clip_assigned = {
            index: distribution.concepts_for_clip(index)
            for index in range(1, clip_count + 1)
        }
        story_brief.concept_distribution = distribution.to_dict()
        story_brief.clip_assigned_concepts = clip_assigned

        api_sources = ["content_brain_concept_distribution", "content_brain_topic_label_generator"]
        if distribution.openai_distribution_used:
            api_sources.append("openai_concept_distribution")
        if distribution.cache_hit:
            api_sources.append("concept_distribution_cache")

        return story_brief, StudioStepResult(
            step=7,
            step_key="concept_distribution",
            title="Concept Distribution",
            duration_ms=_ms(start),
            api_sources=api_sources,
            payload={
                "concept_distribution": distribution.to_dict(),
                "clip_assigned_concepts": {
                    str(index): list(values) for index, values in clip_assigned.items()
                },
                "topic_label": label_result.to_dict(),
            },
        )

    def _step_prompt_generation(
        self,
        story_brief: Any,
        payload: ContentBrainE2ETestInput,
        *,
        strategy_plan: ContentStrategyPlan | None = None,
        classification: TopicClassification | None = None,
        language_code: str = "en",
        seo_title: str = "",
        preservation_score: float = 0.0,
    ) -> StudioStepResult:
        start = time.perf_counter()
        bundle = build_continuity_prompts_from_brief(
            story_brief,
            project_id=f"cb_test_{uuid.uuid4().hex[:8]}",
        )
        bundle_dict = bundle.to_dict() if hasattr(bundle, "to_dict") else {}
        warnings = validate_prompt_bundle(bundle)
        char_stats = dict(getattr(bundle, "char_stats", {}) or {})
        prompt_texts = [str(item) for item in getattr(bundle, "clip_prompts", []) or []]
        story = dict(getattr(story_brief, "to_dict", lambda: {})() or {})
        topic_detail = dict(story.get("topic_story_detail") or {})
        domain_concepts = list(story.get("domain_concepts") or topic_detail.get("domain_concepts") or [])
        concept_distribution = dict(story.get("concept_distribution") or {})
        topic_label_quality_score = float(story.get("topic_label_quality_score") or 0.0)
        post_prompt_audit = run_quality_audit_v2(
            topic=payload.topic,
            language_code=language_code,
            topic_preservation_score=preservation_score,
            story_payload=story,
            seo_title=str(seo_title or story.get("seo_title") or ""),
            seo_title_quality_score=0.0,
            strategy_plan=strategy_plan,
            clip_payloads=[
                {"story_beat": beat, "scene": beat}
                for beat in list(story.get("clip_beats") or [])
            ],
            prompt_texts=prompt_texts,
            topic_category=str(classification.topic_category if classification else ""),
            domain_concepts=domain_concepts,
            concept_distribution=concept_distribution,
            topic_label_quality_score=topic_label_quality_score,
        )
        post_prompt_strategy = audit_fused_strategy_alignment(
            payload.topic,
            strategy_plan or build_content_strategy_plan(payload.topic, classification or classify_topic(payload.topic)),
            seo_title=str(seo_title or story.get("seo_title") or ""),
            story_payload=story,
            clip_payloads=[
                {"story_beat": beat, "scene": beat}
                for beat in list(story.get("clip_beats") or [])
            ],
            prompt_texts=prompt_texts,
            fusion=dict(story.get("cross_domain_fusion") or {}),
        )
        strategy_id = str(strategy_plan.strategy_id if strategy_plan else "")
        validation_failures = validate_prompt_entity_gates(
            bundle,
            content_strategy=strategy_id,
            prompt_specificity_score=post_prompt_audit.prompt_specificity_score,
        )
        clip_prompts = []
        for index, prompt in enumerate(getattr(bundle, "clip_prompts", []) or [], start=1):
            clip_prompts.append(
                {
                    "clip_index": index,
                    "video_prompt": str(prompt),
                    "video_prompt_chars": len(str(prompt)),
                    "video_prompt_max_chars": RUNWAY_PROMPT_MAX_CHARS,
                    "image_prompt": str(getattr(bundle, "starter_image_prompt", "") or "") if index == 1 else "",
                    "image_prompt_chars": len(str(getattr(bundle, "starter_image_prompt", "") or "")) if index == 1 else 0,
                    "continuity_notes": self._extract_continuity_notes(str(prompt)),
                }
            )
        anchors = getattr(bundle, "continuity_anchors", None)
        anchors_payload: dict[str, Any] | str = {}
        if anchors is not None:
            if hasattr(anchors, "to_dict"):
                anchors_payload = anchors.to_dict()
            else:
                anchors_payload = str(anchors)
        return StudioStepResult(
            step=8,
            step_key="prompt_generation",
            title="Prompt Generation",
            duration_ms=_ms(start),
            api_sources=["runway_prompt_builder"],
            payload={
                "starter_image_prompt": str(getattr(bundle, "starter_image_prompt", "") or ""),
                "starter_image_prompt_chars": len(str(getattr(bundle, "starter_image_prompt", "") or "")),
                "runway_prompt_max_chars": RUNWAY_PROMPT_MAX_CHARS,
                "clip_prompts": clip_prompts,
                "continuity_anchors": anchors_payload,
                "builder_version": getattr(bundle, "builder_version", ""),
                "validation_warnings": warnings,
                "validation_failures": validation_failures,
                "prompt_entity_gates_passed": not validation_failures,
                "char_stats": char_stats,
                "raw_bundle": bundle_dict,
                "runway_calls": False,
                "media_generation": False,
                "prompt_specificity_score": post_prompt_audit.prompt_specificity_score,
                "prompt_diversity_score": post_prompt_audit.prompt_diversity_score,
                "strategy_alignment_score": post_prompt_strategy.topic_strategy_alignment_score,
                "post_prompt_audit": post_prompt_audit.to_dict(),
                "post_prompt_strategy_alignment": post_prompt_strategy.to_dict(),
                "domain_concepts_used": domain_concepts,
            },
        )

    def _step_prompt_cleanup(
        self,
        prompt_step: StudioStepResult,
        payload: ContentBrainE2ETestInput,
        *,
        expected_clip_count: int | None = None,
    ) -> StudioStepResult:
        start = time.perf_counter()
        cleanup = resolve_prompt_cleanup(
            topic=payload.topic,
            starter_image_prompt=str(prompt_step.payload.get("starter_image_prompt") or ""),
            clip_prompts=list(prompt_step.payload.get("clip_prompts") or []),
        )
        authoritative_clip_count = int(
            expected_clip_count
            or payload.requested_clip_count
            or len(cleanup.clip_prompts)
        )
        if expected_clip_count and len(cleanup.clip_prompts) != int(expected_clip_count):
            from content_brain.platform.clip_count_authority import assert_clip_count_authority

            assert_clip_count_authority(
                requested=int(expected_clip_count),
                actual=len(cleanup.clip_prompts),
                stage="prompt_cleanup",
            )
        prompt_texts = [str(item.get("video_prompt") or "") for item in cleanup.clip_prompts]
        gates_passed, gate_failures = validate_prompt_cleanup_gates(
            prompt_texts=prompt_texts,
            prompt_noise_score=cleanup.prompt_noise_score,
            prompt_efficiency_score=cleanup.prompt_efficiency_score,
        )
        api_sources = ["content_brain_prompt_cleanup"]
        if cleanup.openai_cleanup_used:
            api_sources.append("openai_prompt_cleanup")
        if cleanup.cache_hit:
            api_sources.append("prompt_cleanup_cache")
        return StudioStepResult(
            step=9,
            step_key="prompt_cleanup",
            title="Prompt Cleanup Pass",
            duration_ms=_ms(start),
            api_sources=api_sources,
            payload={
                **cleanup.to_dict(),
                "runway_prompt_max_chars": prompt_step.payload.get("runway_prompt_max_chars") or RUNWAY_PROMPT_MAX_CHARS,
                "continuity_anchors": prompt_step.payload.get("continuity_anchors") or {},
                "prompt_cleanup_gates_passed": gates_passed,
                "prompt_cleanup_gate_failures": gate_failures,
                "raw_prompt_generation": {
                    "original_total_chars": cleanup.original_total_chars,
                    "clip_count": authoritative_clip_count,
                    "prompt_list_length": len(cleanup.clip_prompts),
                },
                "clip_count": authoritative_clip_count,
                "requested_clip_count": int(payload.requested_clip_count or expected_clip_count or 0),
            },
        )

    def _step_seo_generation(
        self,
        payload: ContentBrainE2ETestInput,
        profile: dict[str, Any],
        story_brief: Any,
        trend_payload: dict[str, Any],
        seo_package: Any,
    ) -> StudioStepResult:
        start = time.perf_counter()
        seo_rules = dict(profile.get("seo_rules") or {})
        profile_keywords = [str(k) for k in (seo_rules.get("keywords") or profile.get("seo_keywords") or [])]
        profile_hashtags = [str(h) for h in (seo_rules.get("hashtags") or [])]
        trend_terms = [str(t.get("trend") or "") for t in (trend_payload.get("trends") or [])[:5]]
        keywords = list(dict.fromkeys((seo_package.keywords if seo_package else []) + profile_keywords + trend_terms))[:12]
        hashtags = list(dict.fromkeys(profile_hashtags + [f"#{payload.niche}", "#shorts"]))[:10]
        title = str(getattr(seo_package, "seo_title", "") or getattr(story_brief, "title", "") or payload.topic)
        description = (
            f"{getattr(story_brief, 'logline', '')} "
            f"{getattr(story_brief, 'visual_hook', '')}"
        ).strip()
        seo_score = float(getattr(seo_package, "seo_score", 0.0) or 0.0)
        if seo_score <= 0:
            seo_score = min(
                1.0,
                sum(
                    [
                        0.25 if title else 0.0,
                        0.25 if description else 0.0,
                        0.25 if keywords else 0.0,
                        0.25 if hashtags else 0.0,
                    ]
                ),
            )
        return StudioStepResult(
            step=9,
            step_key="seo_generation",
            title="SEO Generation",
            duration_ms=_ms(start),
            api_sources=["content_brain_seo_title_builder", "profile_seo_rules", "story_brief"],
            payload={
                "seo_title": title,
                "seo_description": description[:500],
                "keywords": keywords,
                "hashtags": hashtags,
                "seo_score": round(seo_score, 4),
                "title_candidates": list(getattr(seo_package, "title_candidates", []) or []),
                "trend_angle": str(getattr(seo_package, "trend_angle", "") or ""),
                "language_code": str(getattr(seo_package, "language_code", "") or ""),
            },
        )

    def _step_quality_audit(
        self,
        step1: StudioStepResult,
        step2: StudioStepResult,
        step3: StudioStepResult,
        step4: StudioStepResult,
        step5: StudioStepResult,
        step6: StudioStepResult,
        step7: StudioStepResult,
        preservation: Any,
        strategy_plan: ContentStrategyPlan | None = None,
        *,
        language_code: str = "en",
        classification: TopicClassification | None = None,
        seo_title: str = "",
        seo_title_quality_score: float = 0.0,
        step_num: int = 10,
        prompt_cleanup_step: StudioStepResult | None = None,
    ) -> StudioStepResult:
        start = time.perf_counter()
        story = step3.payload.get("story") or {}
        topic_detail = dict(story.get("topic_story_detail") or {})
        domain_concepts = list(
            dict.fromkeys(list(story.get("domain_concepts") or []) + list(topic_detail.get("entities") or []))
        )
        prompt_source = prompt_cleanup_step or step6
        prompt_texts = [
            str(item.get("video_prompt") or "")
            for item in (prompt_source.payload.get("clip_prompts") or [])
        ]
        cleanup_payload = dict((prompt_cleanup_step.payload if prompt_cleanup_step else {}) or {})
        preservation_score = float(getattr(preservation, "topic_preservation_score", step1.payload.get("topic_preservation_score") or 0.0))
        audit = run_quality_audit_v2(
            topic=str(step1.payload.get("original_topic") or ""),
            language_code=language_code,
            topic_preservation_score=preservation_score,
            story_payload=story,
            seo_title=seo_title,
            seo_title_quality_score=seo_title_quality_score,
            strategy_plan=strategy_plan,
            clip_payloads=list(step5.payload.get("clips") or []),
            prompt_texts=prompt_texts,
            hashtags=list(step7.payload.get("hashtags") or []),
            trends=[str(item.get("trend") or "") for item in (step2.payload.get("trends") or [])[:5]],
            topic_category=str((classification.topic_category if classification else "") or ""),
            planned_clip_count=int(step4.payload.get("clip_count") or 0),
            actual_clip_count=int(step5.payload.get("clip_count") or 0),
            domain_concepts=domain_concepts,
            cross_domain_fusion=dict(story.get("cross_domain_fusion") or {}),
            concept_distribution=dict(story.get("concept_distribution") or {}),
            topic_label_quality_score=float(story.get("topic_label_quality_score") or 0.0),
            prompt_cleanup=cleanup_payload,
        )
        payload = audit.to_dict()
        payload["audit_version"] = "quality_audit_v2"
        payload["strategy_alignment_passed"] = audit.strategy_alignment_score >= 0.55
        payload["topic_strategy_alignment_score"] = audit.strategy_alignment_score
        payload["story_quality_score"] = audit.story_specificity_score
        payload["seo_score"] = audit.seo_title_quality_score
        payload["prompt_completeness_score"] = audit.prompt_specificity_score
        payload["prompt_noise_score"] = audit.prompt_noise_score
        payload["prompt_efficiency_score"] = audit.prompt_efficiency_score
        payload["prompt_cleanup_applied"] = bool(cleanup_payload.get("cleanup_applied"))
        payload["openai_cleanup_used"] = bool(cleanup_payload.get("openai_cleanup_used"))
        payload["forbidden_drift"] = list(getattr(preservation, "forbidden_drift_detected", []) or [])
        return StudioStepResult(
            step=step_num,
            step_key="quality_audit",
            title="Quality Audit V2",
            duration_ms=_ms(start),
            api_sources=["content_brain_quality_audit_v2", "content_brain_language_authority"],
            payload=payload,
        )

    def _step_openai_quality_enhancement(
        self,
        payload: ContentBrainE2ETestInput,
        step1: StudioStepResult,
        step2: StudioStepResult,
        step3: StudioStepResult,
        step4: StudioStepResult,
        step5: StudioStepResult,
        step6: StudioStepResult,
        step7: StudioStepResult,
        step8: StudioStepResult,
        preservation: Any,
        strategy_plan: ContentStrategyPlan | None,
        *,
        classification: TopicClassification | None = None,
        language_code: str = "en",
        seo_package: Any = None,
        intent_intelligence: dict[str, Any] | None = None,
    ) -> tuple[Any, StudioStepResult]:
        start = time.perf_counter()
        story = dict(step3.payload.get("story") or {})
        audit_payload = dict(step8.payload or {})
        topic_detail = dict((audit_payload.get("details") or {}).get("topic_story_detail") or story.get("topic_story_detail") or {})
        domain_profile = dict((audit_payload.get("details") or {}).get("domain_profile") or {})
        intent_payload = dict(intent_intelligence or {})
        prompt_texts = [
            str(item.get("video_prompt") or "")
            for item in (step6.payload.get("clip_prompts") or [])
        ]
        clip_payloads = list(step5.payload.get("clips") or [])
        preservation_score = float(
            getattr(preservation, "topic_preservation_score", step1.payload.get("topic_preservation_score") or 0.0)
        )
        enhancement = maybe_enhance_quality(
            topic=str(step1.payload.get("original_topic") or payload.topic),
            language_code=language_code,
            category=str((classification.topic_category if classification else "") or story.get("topic_category") or ""),
            strategy=str((strategy_plan.strategy_id if strategy_plan else "") or story.get("content_strategy") or ""),
            classification_confidence=float((classification.confidence if classification else 0.0) or 0.0),
            audit_scores=audit_payload,
            story_payload=story,
            seo_title=str(
                getattr(seo_package, "seo_title", "")
                or step7.payload.get("seo_title")
                or ""
            ),
            seo_candidates=list(
                getattr(seo_package, "title_candidates", [])
                or step7.payload.get("title_candidates")
                or []
            ),
            prompt_texts=prompt_texts,
            topic_story_detail=topic_detail,
            domain_concepts=list(domain_profile.get("concepts") or []),
            intent_domain_concepts=list(intent_payload.get("domain_concepts") or []),
            intent_story_angles=list(intent_payload.get("story_angles") or []),
            intent_seo_candidates=list(intent_payload.get("seo_title_candidates") or []),
            strategy_plan=strategy_plan,
            clip_payloads=clip_payloads,
            topic_preservation_score=preservation_score,
            cross_domain_fusion=dict(story.get("cross_domain_fusion") or {}),
        )
        api_sources = ["content_brain_openai_quality_enhancer"]
        if not enhancement.applied:
            api_sources.append("openai_quality_skipped")
        return enhancement, StudioStepResult(
            step=11,
            step_key="openai_quality_enhancement",
            title="OpenAI Quality Enhancement",
            duration_ms=_ms(start),
            api_sources=api_sources,
            provider_costs={
                "estimated_cost_usd": enhancement.estimated_cost_usd,
                "usage": enhancement.usage,
            },
            payload=enhancement.to_dict(),
        )

    @staticmethod
    def _apply_enhancement_to_story_step(step3: StudioStepResult, enhancement: Any) -> StudioStepResult:
        story = dict(step3.payload.get("story") or {})
        enhanced_story = dict(enhancement.enhanced.get("story_payload") or {})
        story.update(enhanced_story)
        topic_detail = dict(enhancement.enhanced.get("topic_story_detail") or {})
        if topic_detail:
            story["topic_story_detail"] = topic_detail
        domain_concepts = list(enhancement.enhanced.get("domain_concepts") or enhanced_story.get("domain_concepts") or [])
        if domain_concepts:
            story["domain_concepts"] = domain_concepts
        fusion = dict(story.get("cross_domain_fusion") or {})
        if fusion.get("multi_domain") and fusion.get("fused_clip_structure"):
            story["clip_beats"] = list(fusion.get("fused_clip_structure") or story.get("clip_beats") or [])
        story["openai_quality_enhanced"] = True
        payload = dict(step3.payload)
        payload["story"] = story
        sources = list(step3.api_sources or [])
        if "openai_quality_enhancer" not in sources:
            sources.append("openai_quality_enhancer")
        return StudioStepResult(
            step=step3.step,
            step_key=step3.step_key,
            title=step3.title,
            duration_ms=step3.duration_ms,
            api_sources=sources,
            payload=payload,
        )

    @staticmethod
    def _apply_enhancement_to_clip_step(step5: StudioStepResult, enhancement: Any) -> StudioStepResult:
        beats = list((enhancement.enhanced.get("story_payload") or {}).get("clip_beats") or [])
        if not beats:
            return step5
        clips = []
        for item in list(step5.payload.get("clips") or []):
            clip = dict(item)
            index = int(clip.get("clip_index") or 0) - 1
            if 0 <= index < len(beats):
                clip["story_beat"] = beats[index]
                clip["scene"] = beats[index]
            clips.append(clip)
        payload = dict(step5.payload)
        payload["clips"] = clips
        return StudioStepResult(
            step=step5.step,
            step_key=step5.step_key,
            title=step5.title,
            duration_ms=step5.duration_ms,
            api_sources=list(step5.api_sources or []),
            payload=payload,
        )

    @staticmethod
    def _apply_enhancement_to_prompt_step(step6: StudioStepResult, enhancement: Any) -> StudioStepResult:
        prompts = list(enhancement.enhanced.get("prompt_texts") or [])
        if not prompts:
            return step6
        clip_prompts = []
        for index, item in enumerate(list(step6.payload.get("clip_prompts") or []), start=0):
            clip = dict(item)
            if index < len(prompts):
                clip["video_prompt"] = prompts[index]
                clip["video_prompt_chars"] = len(str(prompts[index]))
            clip_prompts.append(clip)
        payload = dict(step6.payload)
        payload["clip_prompts"] = clip_prompts
        sources = list(step6.api_sources or [])
        if "openai_quality_enhancer" not in sources:
            sources.append("openai_quality_enhancer")
        return StudioStepResult(
            step=step6.step,
            step_key=step6.step_key,
            title=step6.title,
            duration_ms=step6.duration_ms,
            api_sources=sources,
            payload=payload,
        )

    @staticmethod
    def _apply_enhancement_to_seo_title_step(step: StudioStepResult, enhancement: Any) -> StudioStepResult:
        seo_title = str(enhancement.enhanced.get("seo_title") or step.payload.get("seo_title") or "")
        candidates = list(enhancement.enhanced.get("seo_candidates") or step.payload.get("title_candidates") or [])
        if not seo_title and not candidates:
            return step
        payload = dict(step.payload)
        payload["seo_title"] = seo_title or payload.get("seo_title")
        payload["selected_seo_title"] = seo_title or payload.get("selected_seo_title")
        if candidates:
            payload["title_candidates"] = candidates
        if seo_title and "how to why" not in seo_title.lower():
            payload["seo_score"] = max(float(payload.get("seo_score") or 0.0), 0.9)
        sources = list(step.api_sources or [])
        if "openai_quality_enhancer" not in sources:
            sources.append("openai_quality_enhancer")
        return StudioStepResult(
            step=step.step,
            step_key=step.step_key,
            title=step.title,
            duration_ms=step.duration_ms,
            api_sources=sources,
            payload=payload,
        )

    @staticmethod
    def _apply_enhancement_to_seo_step(step7: StudioStepResult, enhancement: Any, seo_package: Any) -> StudioStepResult:
        seo_title = str(enhancement.enhanced.get("seo_title") or step7.payload.get("seo_title") or "")
        candidates = list(enhancement.enhanced.get("seo_candidates") or step7.payload.get("title_candidates") or [])
        payload = dict(step7.payload)
        payload["seo_title"] = seo_title
        payload["title_candidates"] = candidates
        if seo_title and "how to why" not in seo_title.lower():
            payload["seo_score"] = max(float(payload.get("seo_score") or 0.0), 0.9)
        sources = list(step7.api_sources or [])
        if "openai_quality_enhancer" not in sources:
            sources.append("openai_quality_enhancer")
        return StudioStepResult(
            step=step7.step,
            step_key=step7.step_key,
            title=step7.title,
            duration_ms=step7.duration_ms,
            api_sources=sources,
            payload=payload,
        )

    def _step_export(self, result: ContentBrainE2ETestResult) -> StudioStepResult:
        start = time.perf_counter()
        self.export_dir.mkdir(parents=True, exist_ok=True)
        base = self.export_dir / result.run_id
        json_path = base.with_suffix(".json")
        md_path = base.with_suffix(".md")
        runway_txt_path = base.with_suffix(".runway_prompts.txt")
        payload = result.to_dict()
        json_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        md_path.write_text(self._render_markdown(result), encoding="utf-8")
        runway_txt_path.write_text(self._render_runway_prompts(result), encoding="utf-8")
        latest_json = self.export_dir / "latest.json"
        latest_md = self.export_dir / "latest.md"
        latest_runway = self.export_dir / "latest.runway_prompts.txt"
        latest_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        latest_runway.write_text(runway_txt_path.read_text(encoding="utf-8"), encoding="utf-8")
        return StudioStepResult(
            step=13,
            step_key="export",
            title="Export",
            duration_ms=_ms(start),
            api_sources=["filesystem"],
            payload={
                "paths": {
                    "json": str(json_path.resolve()),
                    "markdown": str(md_path.resolve()),
                    "runway_prompts": str(runway_txt_path.resolve()),
                    "latest_json": str(latest_json.resolve()),
                    "latest_markdown": str(latest_md.resolve()),
                    "latest_runway_prompts": str(latest_runway.resolve()),
                }
            },
        )

    @staticmethod
    def _extract_continuity_notes(prompt: str) -> str:
        match = None
        import re

        m = re.search(r"(?i)continuity lock[:.\s-]+(.+?)(?:\.|$)", prompt)
        if m:
            return m.group(1).strip()[:400]
        return ""

    @staticmethod
    def _render_markdown(result: ContentBrainE2ETestResult) -> str:
        lines = [
            "# Content Brain E2E Micro Test",
            "",
            f"- Run ID: `{result.run_id}`",
            f"- Started: {result.started_at}",
            f"- Completed: {result.completed_at}",
            f"- Overall score: **{result.overall_content_score}**",
            "",
        ]
        audit = dict(result.quality_audit or {})
        enhancement = dict(audit.get("quality_enhancement") or {})
        if enhancement:
            lines.extend(
                [
                    "## OpenAI Quality Enhancement",
                    "",
                    f"- Enabled: {enhancement.get('enabled')}",
                    f"- Applied: {enhancement.get('applied')}",
                    f"- Types: {', '.join(enhancement.get('enhancements_applied') or []) or 'none'}",
                    f"- Cache hit: {enhancement.get('cache_hit')}",
                    f"- Cost: ${enhancement.get('estimated_cost_usd')}",
                    "",
                ]
            )
            improvement = dict(audit.get("improvement_summary") or enhancement.get("improvement_summary") or {})
            if improvement:
                lines.append("### Score Improvements")
                lines.append("")
                for key, item in improvement.items():
                    if isinstance(item, dict):
                        lines.append(
                            f"- {key}: {item.get('before')} → {item.get('after')} (+{item.get('percent')}%)"
                        )
                lines.append("")
        story_step = next((step for step in result.steps if step.step_key == "story_generation"), None)
        seo_step = next((step for step in result.steps if step.step_key == "seo_generation"), None)
        prompt_step = next((step for step in result.steps if step.step_key == "prompt_generation"), None)
        if story_step:
            story = dict(story_step.payload.get("story") or {})
            lines.extend(
                [
                    "## Story",
                    "",
                    f"**SEO Title:** {story.get('title') or story.get('seo_title') or ''}",
                    "",
                    f"**Logline:** {story.get('logline') or ''}",
                    "",
                    f"**Character:** {story.get('main_character') or ''}",
                    "",
                    f"**Setting:** {story.get('setting') or ''}",
                    "",
                    "### Clip Beats",
                    "",
                ]
            )
            for index, beat in enumerate(story.get("clip_beats") or [], start=1):
                lines.append(f"{index}. {beat}")
            lines.append("")
        if seo_step:
            lines.extend(
                [
                    "## SEO",
                    "",
                    f"**Title:** {seo_step.payload.get('seo_title') or ''}",
                    "",
                ]
            )
        if prompt_step:
            lines.extend(
                [
                    "## Runway Prompts",
                    "",
                    f"Max chars per prompt: {prompt_step.payload.get('runway_prompt_max_chars') or RUNWAY_PROMPT_MAX_CHARS}",
                    "",
                    "### Starter Image Prompt",
                    "",
                    str(prompt_step.payload.get("starter_image_prompt") or ""),
                    "",
                    f"({prompt_step.payload.get('starter_image_prompt_chars')} chars)",
                    "",
                ]
            )
            for clip in prompt_step.payload.get("clip_prompts") or []:
                if not isinstance(clip, dict):
                    continue
                lines.extend(
                    [
                        f"### Clip {clip.get('clip_index')} Video Prompt",
                        "",
                        str(clip.get("video_prompt") or ""),
                        "",
                        f"({clip.get('video_prompt_chars')} chars)",
                        "",
                    ]
                )
        for step in result.steps:
            lines.append(f"## Step {step.step} — {step.title}")
            lines.append(f"- Duration: {step.duration_ms} ms")
            if step.api_sources:
                lines.append(f"- API sources: {', '.join(step.api_sources)}")
            if step.error:
                lines.append(f"- Error: {step.error}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_runway_prompts(result: ContentBrainE2ETestResult) -> str:
        prompt_step = next((step for step in result.steps if step.step_key == "prompt_cleanup"), None)
        if prompt_step is None:
            prompt_step = next((step for step in result.steps if step.step_key == "prompt_generation"), None)
        if not prompt_step:
            return "No Runway prompts generated.\n"
        lines = [
            "Content Brain — Runway Image/Video Prompts",
            f"Run ID: {result.run_id}",
            f"Max chars: {prompt_step.payload.get('runway_prompt_max_chars') or RUNWAY_PROMPT_MAX_CHARS}",
            "",
            "=== STARTER IMAGE PROMPT ===",
            str(prompt_step.payload.get("starter_image_prompt") or ""),
            "",
            f"[{prompt_step.payload.get('starter_image_prompt_chars')} chars]",
            "",
        ]
        for clip in prompt_step.payload.get("clip_prompts") or []:
            if not isinstance(clip, dict):
                continue
            lines.extend(
                [
                    f"=== CLIP {clip.get('clip_index')} VIDEO PROMPT ===",
                    str(clip.get("video_prompt") or ""),
                    "",
                    f"[{clip.get('video_prompt_chars')} chars]",
                    "",
                ]
            )
        return "\n".join(lines)


def run_content_brain_e2e_micro_test(
    *,
    topic: str,
    duration_seconds: int = 30,
    platform: str = "youtube_shorts",
    niche: str = "general",
    mood: str = "emotional",
    clip_length_preference: int | None = None,
    requested_clip_count: int | None = None,
    project_root: str | Path = ROOT,
) -> dict[str, Any]:
    studio = ContentBrainE2EMicroTestStudio(project_root=project_root)
    result = studio.run(
        ContentBrainE2ETestInput(
            topic=topic,
            duration_seconds=duration_seconds,
            platform=platform,
            niche=niche,
            mood=mood,
            clip_length_preference=clip_length_preference,
            requested_clip_count=requested_clip_count,
        )
    )
    return result.to_dict()


__all__ = [
    "ContentBrainE2EMicroTestStudio",
    "ContentBrainE2ETestInput",
    "ContentBrainE2ETestResult",
    "DEFAULT_EXPORT_DIR",
    "run_content_brain_e2e_micro_test",
]
