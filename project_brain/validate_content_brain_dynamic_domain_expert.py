"""
Content Brain V8.5 — Dynamic Domain Expert validation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["OPENAI_DYNAMIC_DOMAIN_DRY_RUN"] = "1"

from content_brain.execution.content_brain_dynamic_domain_expert import (
    EXPERT_LAYER_VERSION,
    resolve_dynamic_domain_expert,
)
from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_topic_strategy import classify_topic
from content_brain.execution.content_brain_concept_distribution import score_prompt_diversity


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _unit_module() -> None:
    src = (ROOT / "content_brain/execution/content_brain_dynamic_domain_expert.py").read_text(encoding="utf-8")
    studio = (ROOT / "content_brain/execution/content_brain_e2e_micro_test_studio.py").read_text(encoding="utf-8")
    page = (ROOT / "ui/web/src/pages/ContentBrainTestStudioPage.tsx").read_text(encoding="utf-8")
    _pass("module_version", EXPERT_LAYER_VERSION in src)
    _pass("cache_dir", "content_brain_dynamic_domain_cache" in src)
    _pass("resolve_entry", "def resolve_dynamic_domain_expert" in src)
    _pass("studio_wired", "resolve_dynamic_domain_expert" in studio)
    _pass("ui_panel", "DynamicDomainExpertPanel" in page)


def _assert_topic_pack(topic: str, *, category_tokens: tuple[str, ...], concept_tokens: tuple[str, ...]) -> None:
    local = classify_topic(topic)
    result = resolve_dynamic_domain_expert(
        topic=topic,
        classification=local,
        language_code="en",
        clip_count=3,
        force=True,
    )
    _pass(f"{topic[:32]} used", result.used is True)
    category = str(result.classification.topic_category if result.classification else "")
    _pass(
        f"{topic[:32]} category",
        any(token in category for token in category_tokens),
        category,
    )
    strategy = str(result.classification.content_strategy if result.classification else "")
    _pass(f"{topic[:32]} strategy", strategy not in {"general", "cinematic_narrative", ""}, strategy)
    concepts = " ".join(result.payload.domain_profile.core_concepts if result.payload else []).lower()
    hits = sum(1 for token in concept_tokens if token in concepts)
    _pass(f"{topic[:32]} concepts", hits >= 2, concepts[:120])


def _unit_topic_packs() -> None:
    _assert_topic_pack(
        "The history and evolution of snakes through the ages",
        category_tokens=("natural_history", "evolutionary"),
        concept_tokens=("snake", "fossil", "reptile", "venom"),
    )
    _assert_topic_pack(
        "How volcanoes shaped human civilization",
        category_tokens=("geology", "history"),
        concept_tokens=("volcano", "civilization", "human"),
    )
    _assert_topic_pack(
        "Why octopuses are considered alien intelligence",
        category_tokens=("marine_biology", "animal_intelligence"),
        concept_tokens=("octopus", "intelligence", "marine"),
    )
    _assert_topic_pack(
        "The rise and fall of the Ottoman Empire",
        category_tokens=("history", "empire"),
        concept_tokens=("ottoman", "empire", "decline"),
    )
    _assert_topic_pack(
        "Can mushrooms communicate through underground networks?",
        category_tokens=("biology", "ecology"),
        concept_tokens=("mushroom", "mycelium", "network"),
    )


def _unit_pipeline_snakes() -> None:
    payload = run_content_brain_e2e_micro_test(
        topic="The history and evolution of snakes through the ages",
        duration_seconds=30,
    )
    strategy_step = next(item for item in payload["steps"] if item["step_key"] == "topic_classification")
    expert = strategy_step["payload"].get("dynamic_domain_expert") or {}
    classification = strategy_step["payload"].get("classification") or {}
    _pass("pipeline_expert_used", bool(expert.get("used")))
    _pass(
        "pipeline_not_general",
        str(classification.get("topic_category") or "") not in {"general", ""},
        str(classification.get("topic_category")),
    )
    audit = payload.get("quality_audit") or {}
    diversity_score = float(audit.get("prompt_diversity_score") or 0.0)
    _pass("pipeline_prompt_diversity", float(diversity_score) >= 0.75, f"{diversity_score:.4f}")
    _pass("pipeline_domain_knowledge", float(audit.get("domain_knowledge_score") or 0.0) >= 0.70)


def main() -> int:
    print("[validate_content_brain_dynamic_domain_expert] V8.5 dynamic domain expert")
    _unit_module()
    _unit_topic_packs()
    _unit_pipeline_snakes()
    print("\n[validate_content_brain_dynamic_domain_expert] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
