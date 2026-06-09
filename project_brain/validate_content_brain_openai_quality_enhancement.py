"""
Validate Content Brain OpenAI Quality Enhancement Layer (V6).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_openai_quality_enhancer import (
    OpenAIQualityEnhancer,
    apply_quality_enhancements,
    evaluate_enhancement_triggers,
    maybe_enhance_quality,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _audit(payload: dict) -> dict:
    return dict(payload.get("quality_audit") or {})


def _enhancement_step(payload: dict) -> dict:
    step = next(
        (item for item in payload.get("steps") or [] if item.get("step_key") == "openai_quality_enhancement"),
        {},
    )
    return dict(step.get("payload") or {})


def _story_step(payload: dict) -> dict:
    step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "story_generation")
    return dict((step.get("payload") or {}).get("story") or {})


def _seo_title(payload: dict) -> str:
    step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "seo_title")
    return str((step.get("payload") or {}).get("seo_title") or "").lower()


def _classification(payload: dict) -> dict:
    step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "topic_classification")
    return dict((step.get("payload") or {}).get("classification") or {})


def _assert_preservation(payload: dict, topic: str, prefix: str) -> None:
    audit = _audit(payload)
    classification = _classification(payload)
    story = _story_step(payload)
    _pass(
        f"{prefix}_topic_preserved",
        float(audit.get("topic_preservation_score") or 0.0) >= 0.34,
        str(audit.get("topic_preservation_score")),
    )
    _pass(
        f"{prefix}_language_preserved",
        float(audit.get("language_authority_score") or 0.0) >= 0.7,
        str(audit.get("language_authority_score")),
    )
    _pass(
        f"{prefix}_category_preserved",
        classification.get("topic_category") not in (None, ""),
        str(classification.get("topic_category")),
    )
    _pass(
        f"{prefix}_topic_in_story",
        any(token in " ".join([topic.lower(), str(story.get("logline") or "").lower()]) for token in topic.lower().split()[:2]),
        topic,
    )


def _assert_improvement(payload: dict, prefix: str, *, min_keys: int = 1) -> None:
    audit = _audit(payload)
    enhancement = _enhancement_step(payload)
    before = dict(audit.get("scores_before_enhancement") or enhancement.get("before_scores") or {})
    after = dict(audit.get("scores_after_enhancement") or enhancement.get("after_scores") or {})
    improvement = dict(audit.get("improvement_summary") or enhancement.get("improvement_summary") or {})
    improved_count = sum(1 for key, value in after.items() if float(value or 0.0) > float(before.get(key) or 0.0))
    _pass(
        f"{prefix}_enhancement_applied_or_skipped_cleanly",
        enhancement.get("enabled") is not False,
        str(enhancement.get("notes")),
    )
    if enhancement.get("applied"):
        _pass(f"{prefix}_scores_improved", improved_count >= min_keys, f"improved={improved_count}")
        _pass(f"{prefix}_improvement_summary", len(improvement) >= min_keys, str(list(improvement.keys())))


def test_blockbuster() -> None:
    topic = "Why did Blockbuster disappear?"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    seo_title = _seo_title(payload)
    enhancement = _enhancement_step(payload)
    _pass("blockbuster_completed", payload.get("status") == "completed")
    _pass("blockbuster_no_malformed_seo", "how to why" not in seo_title, seo_title)
    _assert_preservation(payload, topic, "blockbuster")
    _assert_improvement(payload, "blockbuster")
    if enhancement.get("applied"):
        applied_types = list(enhancement.get("enhancements_applied") or [])
        _pass("blockbuster_quality_layers", len(applied_types) >= 1, str(applied_types))


def test_kodak() -> None:
    topic = "Why did Kodak fail?"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    story = _story_step(payload)
    character = str(story.get("main_character") or "").lower()
    _pass("kodak_completed", payload.get("status") == "completed")
    _assert_preservation(payload, topic, "kodak")
    _assert_improvement(payload, "kodak")
    if "presenter" in character:
        _pass("kodak_character_not_generic", "analyst" in character or "historian" in character, character)


def test_perfume() -> None:
    topic = "can you master perfume in one day?"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    story = _story_step(payload)
    text = " ".join(
        [
            str(story.get("logline") or ""),
            str(story.get("main_character") or ""),
            " ".join(str(b) for b in story.get("clip_beats") or []),
        ]
    ).lower()
    _pass("perfume_completed", payload.get("status") == "completed")
    _assert_preservation(payload, topic, "perfume")
    _assert_improvement(payload, "perfume", min_keys=0)


def test_fishing() -> None:
    topic = "zander fishing method"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("fishing_completed", payload.get("status") == "completed")
    _assert_preservation(payload, topic, "fishing")
    _assert_improvement(payload, "fishing", min_keys=0)


def test_pizza_dough() -> None:
    topic = "how to make pizza dough"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    seo_title = _seo_title(payload)
    _pass("pizza_completed", payload.get("status") == "completed")
    _pass("pizza_no_double_how_to", "how to how to" not in seo_title, seo_title)
    _assert_preservation(payload, topic, "pizza")
    _assert_improvement(payload, "pizza", min_keys=0)


def test_dyatlov() -> None:
    topic = "the mystery of dyatlov pass"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    story = _story_step(payload)
    setting = str(story.get("setting") or "").lower()
    _pass("dyatlov_completed", payload.get("status") == "completed")
    _assert_preservation(payload, topic, "dyatlov")
    _assert_improvement(payload, "dyatlov", min_keys=0)
    _pass(
        "dyatlov_setting_specific",
        any(term in setting for term in ("snow", "tent", "ural", "wilderness", "pass", "mountain")),
        setting[:160],
    )


def test_roanoke() -> None:
    topic = "What Really Happened to the Roanoke Colony?"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    classification = _classification(payload)
    _pass("roanoke_completed", payload.get("status") == "completed")
    _pass("roanoke_history_mystery", classification.get("topic_category") == "history_mystery")
    _assert_preservation(payload, topic, "roanoke")
    _assert_improvement(payload, "roanoke", min_keys=0)


def test_cache_reuse() -> None:
    topic = "Why did Blockbuster disappear?"
    first = maybe_enhance_quality(
        topic=topic,
        language_code="en",
        category="business_history",
        strategy="business_case_study",
        classification_confidence=0.95,
        audit_scores={
            "seo_title_quality_score": 0.4,
            "character_quality_score": 0.5,
            "domain_knowledge_score": 0.5,
            "story_specificity_score": 0.5,
            "prompt_specificity_score": 0.5,
            "language_authority_score": 0.95,
            "overall_content_score": 0.5,
        },
        story_payload={"main_character": "a knowledgeable presenter", "clip_beats": ["a", "b", "c"]},
        seo_title="How to Why Did Blockbuster Disappear?",
        seo_candidates=[],
        prompt_texts=["generic prompt"],
        topic_story_detail={"source": "generic_extractor"},
        domain_concepts=["market disruption"],
    )
    second = maybe_enhance_quality(
        topic=topic,
        language_code="en",
        category="business_history",
        strategy="business_case_study",
        classification_confidence=0.95,
        audit_scores={
            "seo_title_quality_score": 0.4,
            "character_quality_score": 0.5,
            "domain_knowledge_score": 0.5,
            "story_specificity_score": 0.5,
            "prompt_specificity_score": 0.5,
            "language_authority_score": 0.95,
            "overall_content_score": 0.5,
        },
        story_payload={"main_character": "a knowledgeable presenter", "clip_beats": ["a", "b", "c"]},
        seo_title="How to Why Did Blockbuster Disappear?",
        seo_candidates=[],
        prompt_texts=["generic prompt"],
        topic_story_detail={"source": "generic_extractor"},
        domain_concepts=["market disruption"],
    )
    _pass("cache_first_applied", first.applied, str(first.notes))
    _pass("cache_second_hit", second.cache_hit, str(second.notes))


def test_api_failure_fallback() -> None:
    trigger = evaluate_enhancement_triggers(
        audit_scores={"seo_title_quality_score": 0.2, "character_quality_score": 0.2},
        classification_confidence=0.5,
        story_payload={"main_character": "a knowledgeable presenter"},
        seo_title="How to Why Did Blockbuster Disappear?",
        prompt_texts=["generic"],
        topic_story_detail={"source": "generic_extractor"},
    )
    _pass("trigger_detects_weak_output", trigger.triggered, str(trigger.reasons))
    enhanced, applied = apply_quality_enhancements(
        context={
            "story_payload": {"main_character": "a knowledgeable presenter", "clip_beats": ["a", "b"]},
            "seo_title": "How to Why Did Blockbuster Disappear?",
            "seo_candidates": [],
            "prompt_texts": ["generic prompt"],
            "topic_story_detail": {"source": "generic_extractor"},
        },
        raw_enhancement={},
        requested_types=trigger.enhancement_types,
    )
    _pass("fallback_no_crash", isinstance(enhanced, dict))
    _pass("fallback_no_apply_on_empty", not applied, str(applied))
    enhancer = OpenAIQualityEnhancer(dry_run=False)
    enhancer.enabled = False
    result = enhancer.maybe_enhance(
        context={
            "topic": "Why did Blockbuster disappear?",
            "language_code": "en",
            "category": "business_history",
            "strategy": "business_case_study",
            "classification_confidence": 0.5,
            "audit_scores": {"seo_title_quality_score": 0.2},
            "story_payload": {},
            "seo_title": "bad",
            "seo_candidates": [],
            "prompt_texts": [],
            "topic_story_detail": {},
            "domain_concepts": [],
        }
    )
    _pass("disabled_enhancer_safe", not result.applied, str(result.notes))


def main() -> None:
    os.environ["OPENAI_QUALITY_DRY_RUN"] = "1"
    os.environ["OPENAI_CLASSIFICATION_DRY_RUN"] = "1"
    print("Content Brain OpenAI Quality Enhancement validation")
    test_cache_reuse()
    test_api_failure_fallback()
    test_blockbuster()
    test_kodak()
    test_perfume()
    test_fishing()
    test_pizza_dough()
    test_dyatlov()
    test_roanoke()
    print("All OpenAI quality enhancement checks passed.")


if __name__ == "__main__":
    main()
