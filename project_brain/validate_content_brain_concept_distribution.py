"""
Validate Content Brain V8.1 — Concept Distribution Engine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_concept_distribution import (
    PROMPT_DIVERSITY_TARGET,
    score_prompt_diversity,
)
from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_chemistry_perfume_bestseller_distribution() -> None:
    topic = "Can chemistry predict which perfume will become a bestseller?"
    result = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("chemistry_completed", result.get("status") == "completed")

    distribution_step = next(item for item in result.get("steps") or [] if item.get("step_key") == "concept_distribution")
    distribution = dict(distribution_step.get("payload") or {})
    assignments = dict((distribution.get("concept_distribution") or {}).get("clip_assignments") or {})
    clip1 = " ".join(
        list((assignments.get("1") or {}).get("primary") or [])
        + list((assignments.get("1") or {}).get("secondary") or [])
    ).lower()
    clip2 = " ".join(
        list((assignments.get("2") or {}).get("primary") or [])
        + list((assignments.get("2") or {}).get("secondary") or [])
    ).lower()
    clip3 = " ".join(
        list((assignments.get("3") or {}).get("primary") or [])
        + list((assignments.get("3") or {}).get("secondary") or [])
    ).lower()

    _pass("clip1_science_heavy", any(token in clip1 for token in ("molecular", "formulation", "raw material")), clip1)
    _pass("clip2_perfume_heavy", any(token in clip2 for token in ("accord", "longevity", "consumer testing")), clip2)
    _pass("clip3_business_heavy", any(token in clip3 for token in ("market share", "consumer adoption", "brand positioning")), clip3)

    prompts = next(item for item in result.get("steps") or [] if item.get("step_key") == "prompt_generation")
    prompt_texts = [str(item.get("video_prompt") or "") for item in (prompts.get("payload") or {}).get("clip_prompts") or []]
    diversity = float((result.get("quality_audit") or {}).get("prompt_diversity_score") or 0.0)
    _pass("prompt_diversity_score", diversity >= PROMPT_DIVERSITY_TARGET, str(diversity))

    clip_assignments = {
        int(key): {
            "primary": list((value or {}).get("primary") or []),
            "secondary": list((value or {}).get("secondary") or []),
        }
        for key, value in assignments.items()
    }
    measured, _ = score_prompt_diversity(prompt_texts, clip_assignments=clip_assignments)
    _pass("measured_prompt_diversity", measured >= 0.70, str(measured))

    primary_sets = [
        {item.lower() for item in (clip_assignments.get(index) or {}).get("primary") or []}
        for index in sorted(clip_assignments)
    ]
    if len(primary_sets) >= 2 and primary_sets[0]:
        overlap_all = set.intersection(*primary_sets)
        _pass("no_universal_primary_concepts", not overlap_all, str(sorted(overlap_all)))


def main() -> None:
    os.environ.setdefault("OPENAI_INTENT_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_CROSS_DOMAIN_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_CONCEPT_DISTRIBUTION_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_QUALITY_DRY_RUN", "1")
    os.environ.setdefault("SEO_PROVIDER_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_SEO_DRY_RUN", "1")
    print("[validate_content_brain_concept_distribution] Content Brain V8.1")
    test_chemistry_perfume_bestseller_distribution()
    print("[validate_content_brain_concept_distribution] All checks PASS")


if __name__ == "__main__":
    main()
