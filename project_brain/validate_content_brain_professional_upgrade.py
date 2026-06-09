"""
Validate Content Brain Professional Upgrade V4 (Phases A–J).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_character_builder import build_character, score_character_quality
from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_language_authority import audit_language_authority
from content_brain.execution.content_brain_seo_director import build_seo_director_package, is_malformed_seo_title
from content_brain.execution.content_brain_topic_strategy import TopicClassification, classify_topic, topic_keyword_matches
from content_brain.execution.domain_knowledge_layer import score_domain_concept_usage
from content_brain.execution.topic_universe_studio import run_topic_universe_studio


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _story_text(payload: dict) -> str:
    step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "story_generation")
    story = (step.get("payload") or {}).get("story") or {}
    return " ".join(
        [
            str(story.get("logline") or ""),
            str(story.get("main_character") or ""),
            str(story.get("setting") or ""),
            " ".join(str(b) for b in story.get("clip_beats") or []),
        ]
    ).lower()


def _audit(payload: dict) -> dict:
    return dict(payload.get("quality_audit") or {})


def test_perfume_english() -> None:
    payload = run_content_brain_e2e_micro_test(topic="can you master perfume in one day?", duration_seconds=30)
    text = _story_text(payload)
    audit = _audit(payload)
    _pass("perfume_pipeline_completed", payload.get("status") == "completed")
    _pass("perfume_english_only", " el " not in f" {text} " and " para " not in f" {text} ", text[:120])
    _pass("perfume_character_role", "perfumer" in text or "aspiring perfumer" in text, text[:120])
    _pass("perfume_domain_concepts", any(term in text for term in ("perfume", "fragrance", "notes", "blending", "accord")), text[:120])
    _pass("perfume_language_authority", float(audit.get("language_authority_score") or 0.0) >= 0.8, str(audit.get("language_authority_score")))
    _pass("perfume_character_quality", float(audit.get("character_quality_score") or 0.0) >= 0.7, str(audit.get("character_quality_score")))


def test_pizza_dough() -> None:
    payload = run_content_brain_e2e_micro_test(topic="how to make pizza dough", duration_seconds=30)
    text = _story_text(payload)
    audit = _audit(payload)
    seo_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "seo_title")
    seo_title = str((seo_step.get("payload") or {}).get("seo_title") or "").lower()
    _pass("pizza_pipeline_completed", payload.get("status") == "completed")
    _pass("pizza_no_double_how_to", "how to how to" not in seo_title, seo_title)
    _pass("pizza_no_broken_character", "centered on to make" not in text and "centered on can you" not in text, text[:120])
    _pass("pizza_baker_role", "baker" in text or "home baker" in text, text[:120])
    _pass("pizza_domain_terms", sum(1 for term in ("flour", "yeast", "hydration", "knead", "proof", "dough", "gluten") if term in text) >= 2, text[:160])
    _pass("pizza_realistic_scores", float(audit.get("overall_content_score") or 1.0) < 1.0)


def test_zander_fishing_method() -> None:
    payload = run_content_brain_e2e_micro_test(topic="zander fishing method", duration_seconds=30)
    text = _story_text(payload)
    audit = _audit(payload)
    _pass("zander_completed", payload.get("status") == "completed")
    _pass("zander_angler_or_fishing", "angler" in text or "fish" in text, text[:120])
    _pass("zander_technique_terms", sum(1 for term in ("lure", "cast", "hook", "depth", "retrieve", "strike") if term in text) >= 2, text[:160])
    _pass("zander_strategy_alignment", float(audit.get("strategy_alignment_score") or 0.0) >= 0.55, str(audit.get("strategy_alignment_score")))


def test_fishing_title_bank() -> None:
    payload = run_topic_universe_studio(topic="fishing", title_target=100, use_live_trends=False)
    bank = payload.get("title_bank") or {}
    titles = list(bank.get("titles") or [])
    _pass("fishing_bank_mode", bank.get("mode") == "title_bank")
    _pass("fishing_many_titles", len(titles) >= 80, str(len(titles)))
    _pass("fishing_subtopics", len({item.get("subtopic") for item in titles}) >= 10)


def test_dyatlov_mystery() -> None:
    payload = run_content_brain_e2e_micro_test(topic="the mystery of dyatlov pass", duration_seconds=30)
    strategy_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "topic_classification")
    story_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "story_generation")
    seo_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "seo_title")
    story_strategy = (strategy_step.get("payload") or {}).get("story_strategy") or {}
    story = (story_step.get("payload") or {}).get("story") or {}
    seo_title = str((seo_step.get("payload") or {}).get("seo_title") or "").lower()
    text = _story_text(payload)
    audit = _audit(payload)
    setting = str(story.get("setting") or "").lower()
    _pass("dyatlov_completed", payload.get("status") == "completed")
    _pass("dyatlov_mystery_strategy", story_strategy.get("strategy_id") == "mystery" or "mystery" in str(story_strategy.get("label", "")).lower())
    _pass("dyatlov_seo_natural", "how to how to" not in seo_title and not seo_title.endswith(" that"), seo_title)
    _pass("dyatlov_seo_no_malformed", not is_malformed_seo_title(seo_title, "the mystery of dyatlov pass"), seo_title)
    _pass(
        "dyatlov_setting_specific",
        any(term in setting for term in ("snow", "tent", "ural", "wilderness", "pass", "mountain")),
        setting[:160],
    )
    _pass(
        "dyatlov_story_terms",
        sum(
            1
            for term in ("dyatlov", "tent", "snow", "hiker", "ural", "investig", "expedition", "wilderness", "1959")
            if term in text
        )
        >= 3,
        text[:200],
    )
    _pass("dyatlov_investigator_role", "investigator" in text or "investig" in text, text[:120])
    _pass("dyatlov_narrative_detail_score", float(audit.get("narrative_detail_score") or 0.0) >= 0.35, str(audit.get("narrative_detail_score")))
    _pass("dyatlov_no_generic_setting", "single continuous environment" not in setting, setting[:120])


def test_roanoke_colony() -> None:
    topic = "What Really Happened to the Roanoke Colony?"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    class_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "topic_classification")
    story_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "story_generation")
    prompt_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "prompt_generation")
    seo_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "seo_title")
    classification = (class_step.get("payload") or {}).get("classification") or {}
    story = (story_step.get("payload") or {}).get("story") or {}
    seo_title = str((seo_step.get("payload") or {}).get("seo_title") or "").lower()
    text = _story_text(payload)
    setting = str(story.get("setting") or "").lower()
    character = str(story.get("main_character") or "").lower()
    prompts = " ".join(
        str(item.get("video_prompt") or "")
        for item in (prompt_step.get("payload") or {}).get("clip_prompts") or []
    ).lower()
    audit = _audit(payload)
    _pass("roanoke_completed", payload.get("status") == "completed")
    _pass(
        "roanoke_history_mystery_category",
        classification.get("topic_category") == "history_mystery",
        str(classification.get("topic_category")),
    )
    _pass(
        "roanoke_historical_investigation_strategy",
        classification.get("content_strategy") == "historical_investigation",
        str(classification.get("content_strategy")),
    )
    _pass("roanoke_not_technology", classification.get("topic_category") != "technology", str(classification))
    _pass(
        "roanoke_character_role",
        any(role in character for role in ("historian", "researcher", "investigator", "narrator")),
        character[:120],
    )
    _pass(
        "roanoke_setting_specific",
        any(term in setting for term in ("roanoke", "colonial", "coastal", "settlement", "wilderness")),
        setting[:160],
    )
    _pass(
        "roanoke_story_concepts",
        sum(
            1
            for term in ("roanoke", "colony", "croatoan", "settler", "archaeological", "colonial", "disappearance")
            if term in text
        )
        >= 3,
        text[:200],
    )
    _pass(
        "roanoke_prompt_concepts",
        sum(
            1
            for term in ("roanoke", "colony", "croatoan", "settler", "archaeological", "colonial", "historical")
            if term in prompts
        )
        >= 3,
        prompts[:200],
    )
    _pass("roanoke_no_generic_setting", "single continuous environment" not in setting, setting[:120])
    _pass("roanoke_narrative_detail_score", float(audit.get("narrative_detail_score") or 0.0) >= 0.35, str(audit.get("narrative_detail_score")))
    _pass("roanoke_seo_not_tech", "how to" not in seo_title and "software" not in seo_title, seo_title)


def test_openai_classification_fallback_blockbuster() -> None:
    os.environ["OPENAI_CLASSIFICATION_DRY_RUN"] = "1"
    try:
        from content_brain.execution.content_brain_openai_classification_enricher import maybe_enrich_classification

        local = classify_topic("Why did Blockbuster disappear?")
        _pass("blockbuster_local_category", local.topic_category == "business_history", local.topic_category)
        result = maybe_enrich_classification(
            topic="Why did Blockbuster disappear?",
            classification=TopicClassification(
                topic="Why did Blockbuster disappear?",
                topic_category="general",
                content_strategy="cinematic_narrative",
                confidence=0.55,
            ),
            language_code="en",
            force=True,
        )
        _pass("blockbuster_openai_applied", result.applied)
        _pass(
            "blockbuster_openai_category",
            (result.enrichment.category if result.enrichment else "") == "business_history",
            str(result.enrichment.category if result.enrichment else ""),
        )
        _pass(
            "blockbuster_openai_role",
            "business analyst" in str(result.enrichment.domain_role if result.enrichment else "").lower(),
        )
        _pass(
            "blockbuster_openai_concepts",
            any(term in " ".join(result.enrichment.domain_concepts if result.enrichment else ()).lower() for term in ("blockbuster", "netflix", "streaming")),
        )
    finally:
        os.environ.pop("OPENAI_CLASSIFICATION_DRY_RUN", None)


def test_blockbuster_local_or_openai_pipeline() -> None:
    os.environ["OPENAI_CLASSIFICATION_DRY_RUN"] = "1"
    try:
        payload = run_content_brain_e2e_micro_test(topic="Why did Blockbuster disappear?", duration_seconds=30)
        class_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "topic_classification")
        story_step = next(item for item in payload.get("steps") or [] if item.get("step_key") == "story_generation")
        classification = (class_step.get("payload") or {}).get("classification") or {}
        story = (story_step.get("payload") or {}).get("story") or {}
        text = _story_text(payload)
        _pass("blockbuster_pipeline_completed", payload.get("status") == "completed")
        _pass(
            "blockbuster_category",
            classification.get("topic_category") in {"business_history", "general"},
            str(classification.get("topic_category")),
        )
        _pass(
            "blockbuster_not_technology",
            classification.get("topic_category") != "technology",
            str(classification),
        )
        _pass(
            "blockbuster_story_concepts",
            sum(1 for term in ("blockbuster", "netflix", "streaming", "dvd", "late fees", "subscription") if term in text) >= 2,
            text[:200],
        )
        _pass(
            "blockbuster_character",
            any(role in str(story.get("main_character") or "").lower() for role in ("analyst", "business", "presenter")),
            str(story.get("main_character")),
        )
    finally:
        os.environ.pop("OPENAI_CLASSIFICATION_DRY_RUN", None)


def test_best_perfume_winter() -> None:
    payload = run_content_brain_e2e_micro_test(topic="best perfume for winter", duration_seconds=30)
    text = _story_text(payload)
    _pass("winter_perfume_completed", payload.get("status") == "completed")
    _pass("winter_perfume_terms", any(term in text for term in ("perfume", "fragrance", "longevity", "projection", "winter", "notes")), text[:160])


def test_unit_modules() -> None:
    character = build_character("can you master perfume in one day?")
    _pass("character_builder_v2", "perfumer" in character.character.lower())
    _pass("character_not_can_you", "can you" not in character.character.lower())
    seo = build_seo_director_package(topic="how to make pizza dough", trends=[], language_code="en")
    _pass("seo_director_no_duplicate", "how to how to" not in seo.seo_title.lower(), seo.seo_title)
    dyatlov_seo = build_seo_director_package(topic="the mystery of dyatlov pass", trends=[], language_code="en")
    _pass("dyatlov_seo_director", "how to" not in dyatlov_seo.seo_title.lower(), dyatlov_seo.seo_title)
    _pass("dyatlov_seo_not_malformed", not is_malformed_seo_title(dyatlov_seo.seo_title, "the mystery of dyatlov pass"), dyatlov_seo.seo_title)
    bad_examples = (
        "Why the mystery of dyatlov pass matters",
        "Why the mystery of Dyatlov Pass Matters",
        "How to the mystery of dyatlov pass",
        "Stop making this mystery mistake",
    )
    for sample in bad_examples:
        _pass(
            f"dyatlov_rejects_{sample[:28].replace(' ', '_')}",
            is_malformed_seo_title(sample, "the mystery of dyatlov pass"),
            sample,
        )
    lang = audit_language_authority(
        topic="can you master perfume in one day?",
        expected_language_code="en",
        story_payload={"logline": "An aspiring perfumer tests a one-day blending challenge.", "main_character": "an aspiring perfumer", "clip_beats": ["Blending accords on evaluation strips."]},
        seo_title="Can You Master Perfume in One Day?",
    )
    _pass("language_authority_module", lang.passed)
    roanoke = classify_topic("What Really Happened to the Roanoke Colony?")
    _pass("roanoke_classify_history_mystery", roanoke.topic_category == "history_mystery", roanoke.topic_category)
    _pass("roanoke_classify_not_technology", roanoke.content_strategy != "educational_tech", roanoke.content_strategy)
    _pass("keyword_match_blocks_app_in_happened", not topic_keyword_matches("app", "what really happened to the roanoke colony"))
    bad_score = score_character_quality("a focused subject centered on Can You", "can you master perfume in one day?")
    _pass("broken_character_low_score", bad_score < 0.4, str(bad_score))
    good_text = "flour hydration yeast kneading proofing dough gluten oven spring"
    _pass("domain_score_module", score_domain_concept_usage(good_text, __import__("content_brain.execution.domain_knowledge_layer", fromlist=["get_domain_profile"]).get_domain_profile("pizza dough")) >= 0.5)


def test_implementation_files() -> None:
    files = [
        "content_brain/execution/content_brain_language_authority.py",
        "content_brain/execution/domain_knowledge_layer.py",
        "content_brain/execution/content_brain_character_builder.py",
        "content_brain/execution/story_strategy_library.py",
        "content_brain/execution/topic_knowledge_graph.py",
        "content_brain/execution/content_brain_trend_intelligence.py",
        "content_brain/execution/content_brain_seo_director.py",
        "content_brain/execution/content_brain_quality_audit_v2.py",
        "content_brain/execution/content_brain_topic_story_detail.py",
        "content_brain/execution/content_brain_setting_builder.py",
        "content_brain/execution/content_brain_openai_classification_enricher.py",
    ]
    for rel in files:
        _pass(f"file_{Path(rel).name}", (ROOT / rel).is_file(), rel)


def main() -> int:
    print("[validate_content_brain_professional_upgrade] Content Brain V5")
    test_implementation_files()
    test_unit_modules()
    test_perfume_english()
    test_pizza_dough()
    test_zander_fishing_method()
    test_fishing_title_bank()
    test_dyatlov_mystery()
    test_roanoke_colony()
    test_openai_classification_fallback_blockbuster()
    test_blockbuster_local_or_openai_pipeline()
    test_best_perfume_winter()
    print("\n[validate_content_brain_professional_upgrade] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
