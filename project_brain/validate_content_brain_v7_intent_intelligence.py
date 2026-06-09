"""
Validate Content Brain V7 — Intent & Strategy Intelligence Layer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_intent_intelligence import (
    detect_local_intent,
    resolve_topic_intent,
)
from content_brain.execution.content_brain_topic_strategy import (
    STRATEGY_BUSINESS_CASE_STUDY,
    STRATEGY_BUSINESS_DEBATE,
    STRATEGY_EDUCATIONAL_TECH,
    STRATEGY_FUTURE_ANALYSIS,
    STRATEGY_HISTORICAL_INVESTIGATION,
    STRATEGY_NARRATIVE_MYSTERY,
    STRATEGY_RECIPE_TUTORIAL,
    STRATEGY_SCIENTIFIC_EXPLANATION,
    STRATEGY_TECHNOLOGY_FORECAST,
    TUTORIAL_STRATEGIES,
    classify_topic,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _intent_payload(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "topic_classification")
    return dict((step.get("payload") or {}).get("intent_intelligence") or {})


def _classification(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "topic_classification")
    return dict((step.get("payload") or {}).get("classification") or {})


def _strategy(result: dict) -> str:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "topic_classification")
    strategy = dict((step.get("payload") or {}).get("content_strategy") or {})
    return str(strategy.get("strategy_id") or "")


def _audit(result: dict) -> dict:
    return dict(result.get("quality_audit") or {})


def _step_payload(result: dict, step_key: str) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == step_key)
    return dict(step.get("payload") or {})


def _prompt_texts(result: dict) -> list[str]:
    prompt_step = _step_payload(result, "prompt_generation")
    return [str(item.get("video_prompt") or "") for item in prompt_step.get("clip_prompts") or []]


def test_ai_marketing_agencies() -> None:
    topic = "Can AI destroy traditional marketing agencies by 2026?"
    local = classify_topic(topic)
    intent = detect_local_intent(topic, local)
    _pass("ai_marketing_local_intent", intent.recommended_strategy in {STRATEGY_BUSINESS_DEBATE, STRATEGY_FUTURE_ANALYSIS}, intent.recommended_strategy)
    _pass("ai_marketing_not_tutorial", intent.recommended_strategy not in TUTORIAL_STRATEGIES, intent.recommended_strategy)

    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    strategy = _strategy(payload)
    intent_data = _intent_payload(payload)
    audit = _audit(payload)
    _pass("ai_marketing_completed", payload.get("status") == "completed")
    _pass(
        "ai_marketing_strategy",
        strategy in {STRATEGY_BUSINESS_DEBATE, STRATEGY_FUTURE_ANALYSIS},
        strategy,
    )
    _pass("ai_marketing_intent_confidence", float(intent_data.get("confidence") or 0.0) >= 0.85, str(intent_data.get("confidence")))
    _pass("ai_marketing_not_educational_tech", strategy != STRATEGY_EDUCATIONAL_TECH, strategy)

    domain_profile = dict((audit.get("details") or {}).get("domain_profile") or {})
    concepts = [str(item).lower() for item in domain_profile.get("concepts") or []]
    _pass(
        "ai_marketing_expert_concepts",
        any(
            marker in concepts
            for marker in (
                "marketing agency",
                "client acquisition",
                "media buying",
                "campaign management",
                "performance marketing",
                "agency economics",
            )
        ),
        ", ".join(concepts[:8]),
    )
    _pass(
        "ai_marketing_domain_knowledge_score",
        float(audit.get("domain_knowledge_score") or 0.0) >= 0.50,
        str(audit.get("domain_knowledge_score")),
    )
    _pass(
        "ai_marketing_clip_specificity_score",
        float(audit.get("clip_specificity_score") or 0.0) >= 0.50,
        str(audit.get("clip_specificity_score")),
    )
    _pass(
        "ai_marketing_strategy_alignment_score",
        float(audit.get("strategy_alignment_score") or 0.0) >= 0.60,
        str(audit.get("strategy_alignment_score")),
    )
    _pass(
        "ai_marketing_enhancement_quality_gates",
        bool(audit.get("enhancement_quality_gates_passed", True)),
        ", ".join(audit.get("enhancement_quality_gate_failures") or []),
    )
    raw_enhancement = dict(audit.get("raw_enhancement") or {})
    _pass(
        "ai_marketing_raw_enhancement_logged",
        bool(raw_enhancement.get("domain_concepts") or raw_enhancement.get("story")),
        f"keys={sorted(raw_enhancement.keys())}",
    )


def test_ai_graphic_designers() -> None:
    topic = "Will AI replace graphic designers?"
    resolved = resolve_topic_intent(topic, classify_topic(topic))
    _pass(
        "designers_strategy",
        resolved.classification.content_strategy in {STRATEGY_TECHNOLOGY_FORECAST, STRATEGY_FUTURE_ANALYSIS},
        resolved.classification.content_strategy,
    )
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("designers_completed", payload.get("status") == "completed")
    _pass(
        "designers_e2e_strategy",
        _strategy(payload) in {STRATEGY_TECHNOLOGY_FORECAST, STRATEGY_FUTURE_ANALYSIS},
        _strategy(payload),
    )


def test_blockbuster() -> None:
    topic = "Why did Blockbuster disappear?"
    resolved = resolve_topic_intent(topic, classify_topic(topic))
    _pass("blockbuster_strategy", resolved.classification.content_strategy == STRATEGY_BUSINESS_CASE_STUDY, resolved.classification.content_strategy)
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("blockbuster_completed", payload.get("status") == "completed")
    _pass("blockbuster_e2e_strategy", _strategy(payload) == STRATEGY_BUSINESS_CASE_STUDY, _strategy(payload))


def test_roanoke() -> None:
    topic = "What really happened to the Roanoke Colony?"
    resolved = resolve_topic_intent(topic, classify_topic(topic))
    _pass("roanoke_strategy", resolved.classification.content_strategy == STRATEGY_HISTORICAL_INVESTIGATION, resolved.classification.content_strategy)
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("roanoke_completed", payload.get("status") == "completed")
    _pass("roanoke_e2e_strategy", _strategy(payload) == STRATEGY_HISTORICAL_INVESTIGATION, _strategy(payload))


def test_pizza_dough() -> None:
    topic = "How to make pizza dough?"
    resolved = resolve_topic_intent(topic, classify_topic(topic))
    _pass("pizza_intent_tutorial", resolved.intent.primary_intent == "tutorial", resolved.intent.primary_intent)
    _pass("pizza_strategy", resolved.classification.content_strategy == STRATEGY_RECIPE_TUTORIAL, resolved.classification.content_strategy)
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("pizza_completed", payload.get("status") == "completed")
    _pass("pizza_e2e_strategy", _strategy(payload) == STRATEGY_RECIPE_TUTORIAL, _strategy(payload))


def test_perfume_longevity() -> None:
    topic = "Why do some perfumes last all day?"
    resolved = resolve_topic_intent(topic, classify_topic(topic))
    _pass("perfume_intent", resolved.intent.primary_intent == "scientific_explanation", resolved.intent.primary_intent)
    _pass("perfume_strategy", resolved.classification.content_strategy == STRATEGY_SCIENTIFIC_EXPLANATION, resolved.classification.content_strategy)
    intent_concepts = [str(item).lower() for item in resolved.intent.domain_concepts or []]
    _pass(
        "perfume_intent_domain_concepts",
        any(marker in " ".join(intent_concepts) for marker in ("top notes", "base notes", "fixatives", "longevity")),
        ", ".join(intent_concepts[:8]),
    )
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("perfume_completed", payload.get("status") == "completed")
    _pass("perfume_e2e_strategy", _strategy(payload) == STRATEGY_SCIENTIFIC_EXPLANATION, _strategy(payload))
    prompt_step = _step_payload(payload, "prompt_generation")
    prompt_specificity = float(prompt_step.get("prompt_specificity_score") or 0.0)
    strategy_alignment = float(prompt_step.get("strategy_alignment_score") or 0.0)
    _pass(
        "perfume_prompt_specificity_score",
        prompt_specificity >= 0.70,
        str(prompt_specificity),
    )
    _pass(
        "perfume_post_prompt_strategy_alignment",
        strategy_alignment >= 0.80,
        str(strategy_alignment),
    )
    _pass(
        "perfume_prompt_entity_gates",
        bool(prompt_step.get("prompt_entity_gates_passed", True)),
        ", ".join(prompt_step.get("validation_failures") or []),
    )
    prompt_blob = " ".join(_prompt_texts(payload)).lower()
    required_markers = (
        "top notes",
        "heart notes",
        "base notes",
        "fixatives",
        "projection",
        "longevity",
        "volatility",
        "maceration",
        "evaporation",
    )
    _pass(
        "perfume_prompt_domain_markers",
        sum(1 for marker in required_markers if marker in prompt_blob) >= 5,
        ", ".join(marker for marker in required_markers if marker in prompt_blob),
    )
    forbidden = ("some", "many", "all", "thing", "stuff", "method", "technique")
    _pass(
        "perfume_prompt_no_generic_entities",
        not any(f"key entities: {token}" in prompt_blob or f"; {token}." in prompt_blob for token in forbidden),
        prompt_blob[prompt_blob.find("key entities:") : prompt_blob.find("key entities:") + 120] if "key entities:" in prompt_blob else "",
    )


def test_dyatlov() -> None:
    topic = "The mystery of Dyatlov Pass"
    resolved = resolve_topic_intent(topic, classify_topic(topic))
    classification = resolved.classification
    _pass(
        "dyatlov_category_or_strategy",
        classification.topic_category in {"history_mystery", "mystery"}
        and classification.content_strategy in {STRATEGY_HISTORICAL_INVESTIGATION, STRATEGY_NARRATIVE_MYSTERY},
        f"{classification.topic_category}/{classification.content_strategy}",
    )
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("dyatlov_completed", payload.get("status") == "completed")
    class_payload = _classification(payload)
    _pass(
        "dyatlov_e2e_history_mystery",
        class_payload.get("topic_category") in {"history_mystery", "mystery"},
        str(class_payload.get("topic_category")),
    )


def test_intent_module_file() -> None:
    path = ROOT / "content_brain" / "execution" / "content_brain_intent_intelligence.py"
    _pass("intent_module_exists", path.is_file(), str(path))


def main() -> None:
    os.environ["OPENAI_INTENT_DRY_RUN"] = "1"
    os.environ["OPENAI_CLASSIFICATION_DRY_RUN"] = "1"
    os.environ["OPENAI_QUALITY_DRY_RUN"] = "1"
    print("[validate_content_brain_v7_intent_intelligence] Content Brain V7")
    test_intent_module_file()
    test_ai_marketing_agencies()
    test_ai_graphic_designers()
    test_blockbuster()
    test_roanoke()
    test_pizza_dough()
    test_perfume_longevity()
    test_dyatlov()
    print("[validate_content_brain_v7_intent_intelligence] All checks PASS")


if __name__ == "__main__":
    main()
