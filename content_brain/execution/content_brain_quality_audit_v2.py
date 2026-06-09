"""
Quality Audit V2 — realistic multi-dimensional content scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_character_builder import score_character_quality
from content_brain.execution.content_brain_language_authority import audit_language_authority
from content_brain.execution.content_brain_cross_domain_fusion import (
    audit_fused_strategy_alignment,
    score_cross_domain_fusion,
    validate_cross_domain_fusion_gates,
)
from content_brain.execution.content_brain_concept_distribution import (
    score_prompt_diversity,
    validate_concept_distribution_gates,
)
from content_brain.execution.content_brain_prompt_cleanup import (
    PROMPT_EFFICIENCY_TARGET,
    PROMPT_NOISE_TARGET,
    validate_prompt_cleanup_gates,
)
from content_brain.execution.content_brain_topic_strategy import (
    ContentStrategyPlan,
    audit_post_prompt_strategy_alignment,
    audit_topic_strategy_alignment,
)
from content_brain.execution.domain_knowledge_layer import (
    build_domain_profile_from_concepts,
    filter_expert_domain_concepts,
    get_domain_profile,
    score_domain_concept_usage,
)
from content_brain.execution.content_brain_topic_story_detail import (
    TopicStoryDetail,
    build_topic_story_detail,
    score_narrative_detail,
)
from content_brain.execution.story_strategy_library import resolve_story_strategy

GENERIC_STORY_MARKERS: tuple[str, ...] = (
    "setup and preparation",
    "core technique demonstration",
    "result and takeaway",
    "emotional journey",
    "walking on the shore",
    "staring at the horizon",
    "compelling lead subject",
    "focused subject centered on",
)


@dataclass
class QualityAuditV2Result:
    topic_preservation_score: float = 0.0
    language_authority_score: float = 0.0
    domain_knowledge_score: float = 0.0
    character_quality_score: float = 0.0
    story_specificity_score: float = 0.0
    strategy_alignment_score: float = 0.0
    seo_title_quality_score: float = 0.0
    clip_specificity_score: float = 0.0
    prompt_specificity_score: float = 0.0
    narrative_detail_score: float = 0.0
    continuity_score: float = 0.0
    cross_domain_fusion_score: float = 0.0
    domain_balance_score: float = 0.0
    prompt_diversity_score: float = 0.0
    topic_label_quality_score: float = 0.0
    prompt_noise_score: float = 0.0
    prompt_efficiency_score: float = 0.0
    overall_content_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    passed: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_preservation_score": round(self.topic_preservation_score, 4),
            "language_authority_score": round(self.language_authority_score, 4),
            "domain_knowledge_score": round(self.domain_knowledge_score, 4),
            "character_quality_score": round(self.character_quality_score, 4),
            "story_specificity_score": round(self.story_specificity_score, 4),
            "strategy_alignment_score": round(self.strategy_alignment_score, 4),
            "seo_title_quality_score": round(self.seo_title_quality_score, 4),
            "clip_specificity_score": round(self.clip_specificity_score, 4),
            "prompt_specificity_score": round(self.prompt_specificity_score, 4),
            "narrative_detail_score": round(self.narrative_detail_score, 4),
            "continuity_score": round(self.continuity_score, 4),
            "cross_domain_fusion_score": round(self.cross_domain_fusion_score, 4),
            "domain_balance_score": round(self.domain_balance_score, 4),
            "prompt_diversity_score": round(self.prompt_diversity_score, 4),
            "topic_label_quality_score": round(self.topic_label_quality_score, 4),
            "prompt_noise_score": round(self.prompt_noise_score, 4),
            "prompt_efficiency_score": round(self.prompt_efficiency_score, 4),
            "overall_content_score": round(self.overall_content_score, 4),
            "warnings": list(self.warnings),
            "passed": self.passed,
            "details": dict(self.details),
        }


def run_quality_audit_v2(
    *,
    topic: str,
    language_code: str,
    topic_preservation_score: float,
    story_payload: dict[str, Any],
    seo_title: str,
    seo_title_quality_score: float,
    strategy_plan: ContentStrategyPlan | None,
    clip_payloads: list[dict[str, Any]],
    prompt_texts: list[str],
    hashtags: list[str] | None = None,
    trends: list[str] | None = None,
    topic_category: str = "",
    planned_clip_count: int = 0,
    actual_clip_count: int = 0,
    domain_concepts: list[str] | None = None,
    cross_domain_fusion: dict[str, Any] | None = None,
    concept_distribution: dict[str, Any] | None = None,
    topic_label_quality_score: float = 0.0,
    prompt_cleanup: dict[str, Any] | None = None,
) -> QualityAuditV2Result:
    story = dict(story_payload or {})
    warnings: list[str] = []
    fusion_payload = dict(cross_domain_fusion or story.get("cross_domain_fusion") or {})
    clip_text = " ".join(str(c.get("story_beat") or c.get("scene") or "") for c in clip_payloads)
    prompt_text = " ".join(prompt_texts)
    domain_profile = _resolve_audit_domain_profile(
        topic,
        topic_category=topic_category,
        story=story,
        domain_concepts=domain_concepts,
    )
    story_text = " ".join(
        [
            str(story.get("logline") or ""),
            str(story.get("main_character") or ""),
            str(story.get("setting") or ""),
            " ".join(str(b) for b in story.get("clip_beats") or []),
        ]
    )

    language = audit_language_authority(
        topic=topic,
        expected_language_code=language_code,
        seo_title=seo_title,
        story_payload=story,
        prompt_texts=prompt_texts,
        hashtags=hashtags,
        trends=trends,
    )
    if not language.passed:
        warnings.append("language drift detected")

    character = str(story.get("main_character") or "")
    character_score = score_character_quality(character, topic, domain_profile.domain_id)
    if character_score < 0.7:
        warnings.append("character extraction weak")

    domain_score = score_domain_concept_usage(story_text, domain_profile)
    if fusion_payload.get("multi_domain"):
        from content_brain.execution.content_brain_cross_domain_fusion import balance_fusion_domain_concepts

        fusion_concepts = balance_fusion_domain_concepts(
            dict(fusion_payload.get("domain_concepts_by_domain") or {}),
            max_total=12,
        )
        if fusion_concepts:
            fusion_profile = build_domain_profile_from_concepts(
                topic,
                fusion_concepts,
                topic_category=topic_category,
                base_profile=domain_profile,
            )
            domain_score = max(
                domain_score,
                score_domain_concept_usage(" ".join([story_text, clip_text, prompt_text]), fusion_profile),
            )
    if domain_score < 0.35:
        warnings.append("domain knowledge missing")

    story_specificity = _score_story_specificity(story_text, topic, domain_profile.domain_id)
    if story_specificity < 0.55:
        warnings.append("story too generic")

    strategy_alignment = audit_topic_strategy_alignment(
        topic,
        strategy_plan or _fallback_strategy(),
        seo_title=seo_title,
        story_payload=story,
        clip_payloads=clip_payloads,
        prompt_texts=prompt_texts,
    )
    if fusion_payload.get("multi_domain") and prompt_texts:
        strategy_alignment = audit_fused_strategy_alignment(
            topic,
            strategy_plan or _fallback_strategy(),
            seo_title=seo_title,
            story_payload=story,
            clip_payloads=clip_payloads,
            prompt_texts=prompt_texts,
            fusion=fusion_payload,
        )
    strategy_score = float(strategy_alignment.topic_strategy_alignment_score)
    if not strategy_alignment.passed:
        warnings.append("topic intent not preserved")

    clip_specificity = max(domain_score, score_domain_concept_usage(clip_text, domain_profile))
    if clip_specificity < 0.35:
        warnings.append("clip beats too generic")

    prompt_specificity = score_domain_concept_usage(prompt_text, domain_profile)
    if "focused subject centered on" in prompt_text.lower():
        prompt_specificity = min(prompt_specificity, 0.35)
        warnings.append("prompt character drift")

    distribution_payload = dict(concept_distribution or story.get("concept_distribution") or {})
    assignments_raw = dict(distribution_payload.get("clip_assignments") or {})
    clip_assignments: dict[int, dict[str, list[str]]] = {}
    for key, value in assignments_raw.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        clip_assignments[index] = {
            "primary": list((value or {}).get("primary") or []),
            "secondary": list((value or {}).get("secondary") or []),
        }
    prompt_diversity, diversity_warnings = score_prompt_diversity(
        prompt_texts,
        clip_assignments=clip_assignments or None,
        concept_states=dict(distribution_payload.get("concept_states") or {}),
    )
    warnings.extend(diversity_warnings[:4])
    if prompt_diversity < 0.70:
        warnings.append("prompt diversity weak")

    label_quality = float(
        topic_label_quality_score
        or story.get("topic_label_quality_score")
        or (story.get("topic_story_detail") or {}).get("topic_label_quality_score")
        or 0.0
    )
    if label_quality <= 0.0 and story.get("topic_label"):
        from content_brain.execution.content_brain_topic_label_generator import score_topic_label_quality

        label_quality, label_warnings = score_topic_label_quality(
            str(story.get("topic_label") or ""),
            topic=topic,
        )
        warnings.extend(label_warnings[:3])
    if label_quality < 0.75:
        warnings.append("topic label quality weak")

    cleanup_payload = dict(prompt_cleanup or {})
    prompt_noise = float(cleanup_payload.get("prompt_noise_score") or 0.0)
    prompt_efficiency = float(cleanup_payload.get("prompt_efficiency_score") or 0.0)
    if cleanup_payload:
        if prompt_noise > PROMPT_NOISE_TARGET:
            warnings.append("prompt noise above target")
        if prompt_efficiency < PROMPT_EFFICIENCY_TARGET:
            warnings.append("prompt efficiency below target")

    topic_detail = build_topic_story_detail(
        topic,
        topic_category=topic_category,
        content_strategy=strategy_plan.strategy_id if strategy_plan else "",
        language_code=language_code,
    )
    enriched_detail = dict(story.get("topic_story_detail") or {})
    if enriched_detail.get("entities"):
        topic_detail = TopicStoryDetail(
            topic=str(enriched_detail.get("topic") or topic_detail.topic),
            subject=str(enriched_detail.get("subject") or topic_detail.subject),
            facts=tuple(enriched_detail.get("facts") or topic_detail.facts),
            entities=tuple(enriched_detail.get("entities") or topic_detail.entities),
            settings=tuple(enriched_detail.get("settings") or topic_detail.settings),
            objects=tuple(enriched_detail.get("objects") or topic_detail.objects),
            narrative_beats=tuple(enriched_detail.get("narrative_beats") or topic_detail.narrative_beats),
            source=str(enriched_detail.get("source") or topic_detail.source),
            match_key=str(enriched_detail.get("match_key") or topic_detail.match_key),
        )
    combined_narrative_text = " ".join([story_text, clip_text, prompt_text, seo_title])
    narrative_detail = score_narrative_detail(combined_narrative_text, topic_detail)
    if narrative_detail < 0.35:
        warnings.append("topic narrative detail weak")

    continuity = 1.0 if planned_clip_count == actual_clip_count and actual_clip_count > 0 else 0.5

    fusion_score = 1.0
    domain_balance = float(fusion_payload.get("domain_balance_score") or 0.0)
    missing_domain_warnings: list[str] = list(fusion_payload.get("missing_domain_warnings") or [])
    if fusion_payload.get("multi_domain"):
        fusion_score, fusion_warnings = score_cross_domain_fusion(
            fusion_payload,
            story_text=story_text,
            prompt_text=prompt_text,
            strategy_id=strategy_plan.strategy_id if strategy_plan else "",
        )
        missing_domain_warnings = list(dict.fromkeys(missing_domain_warnings + fusion_warnings))
        if domain_balance <= 0.0:
            from content_brain.execution.content_brain_cross_domain_fusion import score_domain_balance

            domain_balance = score_domain_balance(dict(fusion_payload.get("domain_weights") or {}))
        if fusion_score < 0.75:
            warnings.append("cross-domain fusion weak")
        if domain_balance < 0.75:
            warnings.append("domain balance weak")
        warnings.extend(missing_domain_warnings[:4])

    overall = (
        float(topic_preservation_score) * 0.11
        + language.language_authority_score * 0.11
        + domain_score * 0.09
        + character_score * 0.09
        + story_specificity * 0.11
        + strategy_score * 0.11
        + float(seo_title_quality_score) * 0.07
        + clip_specificity * 0.09
        + prompt_specificity * 0.07
        + narrative_detail * 0.1
        + continuity * 0.05
    )
    if fusion_payload.get("multi_domain"):
        overall = overall * 0.92 + fusion_score * 0.08
    overall = round(min(1.0, max(0.0, overall)), 4)
    passed = overall >= 0.62 and language.passed and character_score >= 0.55
    if fusion_payload.get("multi_domain"):
        gates_passed, gate_failures = validate_cross_domain_fusion_gates(
            fusion=fusion_payload,
            cross_domain_fusion_score=fusion_score,
            strategy_alignment_score=strategy_score,
        )
        if not gates_passed:
            passed = False
            warnings.extend(gate_failures)

    if distribution_payload:
        distribution_passed, distribution_failures = validate_concept_distribution_gates(
            distribution=distribution_payload,
            prompt_texts=prompt_texts,
            prompt_diversity_score=prompt_diversity,
        )
        if not distribution_passed:
            passed = False
            warnings.extend(distribution_failures)

    if cleanup_payload:
        cleanup_passed, cleanup_failures = validate_prompt_cleanup_gates(
            prompt_texts=prompt_texts,
            prompt_noise_score=prompt_noise,
            prompt_efficiency_score=prompt_efficiency,
        )
        if not cleanup_passed:
            passed = False
            warnings.extend(cleanup_failures)

    return QualityAuditV2Result(
        topic_preservation_score=float(topic_preservation_score),
        language_authority_score=language.language_authority_score,
        domain_knowledge_score=domain_score,
        character_quality_score=character_score,
        story_specificity_score=story_specificity,
        strategy_alignment_score=strategy_score,
        seo_title_quality_score=float(seo_title_quality_score),
        clip_specificity_score=clip_specificity,
        prompt_specificity_score=prompt_specificity,
        narrative_detail_score=narrative_detail,
        continuity_score=continuity,
        cross_domain_fusion_score=fusion_score,
        domain_balance_score=domain_balance,
        prompt_diversity_score=prompt_diversity,
        topic_label_quality_score=label_quality,
        prompt_noise_score=prompt_noise,
        prompt_efficiency_score=prompt_efficiency,
        overall_content_score=overall,
        warnings=warnings,
        passed=passed,
        details={
            "language_authority": language.to_dict(),
            "strategy_alignment": strategy_alignment.to_dict(),
            "story_strategy": resolve_story_strategy(
                strategy_plan.strategy_id if strategy_plan else "cinematic_narrative"
            ).to_dict(),
            "domain_profile": domain_profile.to_dict(),
            "topic_story_detail": topic_detail.to_dict(),
            "narrative_detail_hits": narrative_detail,
            "cross_domain_fusion": fusion_payload,
            "missing_domain_warnings": missing_domain_warnings,
            "concept_distribution": distribution_payload,
            "topic_label": str(story.get("topic_label") or topic_detail.subject or ""),
        },
    )


def _score_story_specificity(text: str, topic: str, domain: str) -> float:
    lowered = str(text or "").lower()
    if not lowered:
        return 0.0
    generic_hits = sum(1 for marker in GENERIC_STORY_MARKERS if marker in lowered)
    score = 0.75 - 0.12 * generic_hits
    score = max(score, score_domain_concept_usage(text, get_domain_profile(topic, topic_category=domain)))
    topic_tokens = [token for token in topic.lower().split() if len(token) > 3]
    if topic_tokens and any(token in lowered for token in topic_tokens):
        score += 0.08
    return min(1.0, max(0.0, score))


def _resolve_audit_domain_profile(
    topic: str,
    *,
    topic_category: str,
    story: dict[str, Any],
    domain_concepts: list[str] | None = None,
):
    base_profile = get_domain_profile(topic, topic_category=topic_category)
    story_concepts = filter_expert_domain_concepts(list(story.get("domain_concepts") or []))
    detail = dict(story.get("topic_story_detail") or {})
    detail_entities = filter_expert_domain_concepts(list(detail.get("entities") or []))
    merged = list(dict.fromkeys(list(domain_concepts or []) + story_concepts + detail_entities))
    if merged:
        return build_domain_profile_from_concepts(
            topic,
            merged,
            topic_category=topic_category,
            base_profile=base_profile,
        )
    return base_profile


def _fallback_strategy() -> ContentStrategyPlan:
    return ContentStrategyPlan(
        strategy_id="cinematic_narrative",
        label="Cinematic narrative strategy",
        purpose="character-driven visual story",
        niche_style="cinematic",
        effective_mood="emotional",
        clip_beats=[],
        conflict="",
        visual_hook="",
        seo_title_candidates=[],
        required_terms=(),
    )


__all__ = ["QualityAuditV2Result", "run_quality_audit_v2"]
