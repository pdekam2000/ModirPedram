"""
Validate Content Brain V8 — Cross-Domain Fusion Engine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_cross_domain_fusion import (
    OpenAICrossDomainFusionEnricher,
    build_local_cross_domain_fusion,
    resolve_cross_domain_fusion,
)
from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_intent_intelligence import resolve_topic_intent
from content_brain.execution.content_brain_topic_strategy import classify_topic


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _fusion_step(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "cross_domain_fusion")
    return dict(step.get("payload") or {})


def _prompt_step(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "prompt_generation")
    return dict(step.get("payload") or {})


def _story_step(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "story_generation")
    return dict((step.get("payload") or {}).get("story") or {})


def _audit(result: dict) -> dict:
    return dict(result.get("quality_audit") or {})


def _assert_multi_domain_case(
    name: str,
    topic: str,
    *,
    required_domains: set[str],
    required_concepts: tuple[str, ...],
    strategy_options: set[str] | None = None,
) -> None:
    classification = classify_topic(topic)
    resolved = resolve_topic_intent(topic, classification)
    local = build_local_cross_domain_fusion(
        topic,
        classification=resolved.classification,
        intent_payload=resolved.intent.to_dict(),
    )
    _pass(f"{name}_local_multi_domain", local.multi_domain, str(local.domain_weights))
    for domain in required_domains:
        _pass(f"{name}_domain_{domain}", domain in local.domain_weights, str(local.domain_weights))

    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass(f"{name}_completed", payload.get("status") == "completed")
    fusion = _fusion_step(payload)
    story = _story_step(payload)
    prompts = _prompt_step(payload)
    audit = _audit(payload)
    story_blob = " ".join(
        [
            str(story.get("logline") or ""),
            " ".join(str(item) for item in story.get("clip_beats") or []),
            str(story.get("main_character") or ""),
            str(story.get("setting") or ""),
        ]
    ).lower()
    prompt_blob = " ".join(
        str(item.get("video_prompt") or "") for item in prompts.get("clip_prompts") or []
    ).lower()
    _pass(
        f"{name}_cross_domain_fusion_score",
        float(audit.get("cross_domain_fusion_score") or 0.0) >= 0.75,
        str(audit.get("cross_domain_fusion_score")),
    )
    _pass(
        f"{name}_strategy_alignment_score",
        float(audit.get("strategy_alignment_score") or prompts.get("strategy_alignment_score") or 0.0) >= 0.75,
        str(audit.get("strategy_alignment_score")),
    )
    if strategy_options:
        strategy = str(story.get("content_strategy") or fusion.get("classification_strategy") or "")
        _pass(f"{name}_strategy", strategy in strategy_options, strategy)
    max_weight = max((fusion.get("domain_weights") or {"x": 0.0}).values())
    if len(required_domains) >= 3:
        _pass(f"{name}_domain_cap", max_weight <= 0.75, str(max_weight))
    for concept in required_concepts:
        token = concept.lower()
        stem = token.rstrip("s")
        found = (
            token in story_blob
            or token in prompt_blob
            or stem in story_blob
            or stem in prompt_blob
        )
        _pass(
            f"{name}_concept_{concept.replace(' ', '_')}",
            found,
            concept,
        )
    _pass(f"{name}_openai_fusion_used", bool(fusion.get("openai_fusion_used")), str(fusion.get("source")))


def test_ai_billion_dollar_perfume_brand() -> None:
    topic = "Could AI design a billion-dollar perfume brand by 2030?"
    _assert_multi_domain_case(
        "ai_perfume_brand",
        topic,
        required_domains={"business", "perfume", "ai"},
        required_concepts=(
            "brand positioning",
            "luxury market",
            "consumer adoption",
            "accord design",
            "raw materials",
            "algorithmic formulation",
            "prediction models",
        ),
        strategy_options={"future_analysis", "business_debate", "technology_forecast"},
    )


def test_ai_creative_professions() -> None:
    topic = "Will AI eliminate most creative professions by 2040?"
    _assert_multi_domain_case(
        "ai_creative_professions",
        topic,
        required_domains={"ai", "economics", "creative"},
        required_concepts=(
            "generative design",
            "workflow automation",
            "workforce economics",
            "automation",
        ),
        strategy_options={"future_analysis", "business_debate", "technology_forecast"},
    )


def test_chemistry_perfume_bestseller() -> None:
    topic = "Can chemistry predict which perfume will become a bestseller?"
    _assert_multi_domain_case(
        "chemistry_perfume_bestseller",
        topic,
        required_domains={"science", "perfume", "business"},
        required_concepts=(
            "chemical prediction",
            "accord design",
            "market share",
            "formulation science",
        ),
        strategy_options={"scientific_explanation", "future_analysis", "business_debate"},
    )


def test_ai_surgeons() -> None:
    topic = "Will AI surgeons outperform human surgeons within the next 20 years?"
    _assert_multi_domain_case(
        "ai_surgeons",
        topic,
        required_domains={"ai", "medicine"},
        required_concepts=(
            "surgical precision",
            "generative design",
            "ethical oversight",
            "clinical outcomes",
        ),
        strategy_options={"future_analysis", "technology_forecast", "scientific_explanation"},
    )


def test_nokia_android_counterfactual() -> None:
    topic = "Could Nokia have survived if it had adopted Android earlier?"
    _assert_multi_domain_case(
        "nokia_android",
        topic,
        required_domains={"business_history", "technology"},
        required_concepts=(
            "strategic mistake",
            "platform strategy",
            "market timing",
            "smartphone market",
        ),
        strategy_options={"business_case_study", "future_analysis", "business_debate"},
    )


def test_openai_cache_and_fallback() -> None:
    topic = "Could AI design a billion-dollar perfume brand by 2030?"
    classification = classify_topic(topic)
    local = build_local_cross_domain_fusion(topic, classification=classification)
    enricher = OpenAICrossDomainFusionEnricher(dry_run=True)
    first = enricher.maybe_enrich(
        topic=topic,
        classification=classification,
        local_fusion=local,
        language_code="en",
    )
    second = enricher.maybe_enrich(
        topic=topic,
        classification=classification,
        local_fusion=local,
        language_code="en",
    )
    _pass("openai_fusion_dry_run", first.openai_fusion_used, first.source)
    _pass("openai_fusion_cache_hit", second.cache_hit, str(second.source))
    broken = OpenAICrossDomainFusionEnricher(
        dry_run=False,
        cache_dir=str(ROOT / "project_brain" / "content_brain_cross_domain_cache_fallback_test"),
    )
    broken.enabled = False
    broken._api_key = ""
    fallback_topic = "Could quantum AI replace human perfumers by 2042?"
    fallback_classification = classify_topic(fallback_topic)
    fallback_local = build_local_cross_domain_fusion(fallback_topic, classification=fallback_classification)
    fallback = broken.maybe_enrich(
        topic=fallback_topic,
        classification=fallback_classification,
        local_fusion=fallback_local,
        language_code="en",
    )
    _pass("openai_fusion_safe_fallback", not fallback.openai_fusion_used, fallback.source)


def main() -> None:
    os.environ["OPENAI_INTENT_DRY_RUN"] = "1"
    os.environ["OPENAI_CLASSIFICATION_DRY_RUN"] = "1"
    os.environ["OPENAI_QUALITY_DRY_RUN"] = "1"
    os.environ["OPENAI_CROSS_DOMAIN_DRY_RUN"] = "1"
    os.environ["SEO_PROVIDER_DRY_RUN"] = "1"
    os.environ["OPENAI_SEO_DRY_RUN"] = "1"
    print("[validate_content_brain_cross_domain_fusion] Content Brain V8")
    test_openai_cache_and_fallback()
    test_ai_billion_dollar_perfume_brand()
    test_ai_creative_professions()
    test_chemistry_perfume_bestseller()
    test_ai_surgeons()
    test_nokia_android_counterfactual()
    print("[validate_content_brain_cross_domain_fusion] All checks PASS")


if __name__ == "__main__":
    main()
