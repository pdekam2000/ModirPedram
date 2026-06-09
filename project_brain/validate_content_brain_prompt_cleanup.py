"""
Validate Content Brain V8.3 — Prompt Cleanup Pass.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.content_brain_e2e_micro_test_studio import run_content_brain_e2e_micro_test
from content_brain.execution.content_brain_prompt_cleanup import (
    PROMPT_EFFICIENCY_TARGET,
    PROMPT_NOISE_TARGET,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_chemistry_perfume_prompt_cleanup() -> None:
    topic = "Can chemistry predict which perfume will become a bestseller?"
    result = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    _pass("chemistry_completed", result.get("status") == "completed")

    cleanup_step = next(item for item in result.get("steps") or [] if item.get("step_key") == "prompt_cleanup")
    payload = dict(cleanup_step.get("payload") or {})
    audit = dict(result.get("quality_audit") or {})

    original_length = int(payload.get("original_total_chars") or payload.get("original_length") or 0)
    cleaned_length = int(payload.get("cleaned_total_chars") or payload.get("cleaned_length") or 0)
    characters_saved = int(payload.get("characters_saved") or 0)
    noise = float(payload.get("prompt_noise_score") or audit.get("prompt_noise_score") or 0.0)
    efficiency = float(payload.get("prompt_efficiency_score") or audit.get("prompt_efficiency_score") or 0.0)

    _pass("cleanup_applied", bool(payload.get("cleanup_applied")), str(payload.get("cleanup_applied")))
    _pass("prompt_size_reduced", cleaned_length <= original_length and characters_saved >= 0, f"{original_length}->{cleaned_length}")
    _pass("prompt_noise_score", noise < PROMPT_NOISE_TARGET, str(noise))
    _pass("prompt_efficiency_score", efficiency > PROMPT_EFFICIENCY_TARGET, str(efficiency))
    _pass("prompt_cleanup_gates_passed", bool(payload.get("prompt_cleanup_gates_passed")), str(payload.get("prompt_cleanup_gate_failures")))

    clip_prompts = list(payload.get("clip_prompts") or [])
    for clip in clip_prompts:
        prompt = str(clip.get("video_prompt") or "")
        historical = re.findall(r"Historical detail:\s*([^.]+)\.", prompt, flags=re.I)
        unique_historical = {_normalize(item) for item in historical}
        _pass(
            f"clip_{clip.get('clip_index')}_no_repeated_historical_details",
            len(historical) == len(unique_historical),
            f"{len(historical)} items",
        )
        entities = _section_items(prompt, "Key entities")
        unique_entities = {_normalize(item) for item in entities}
        _pass(
            f"clip_{clip.get('clip_index')}_no_repeated_entities",
            len(entities) == len(unique_entities),
            f"{len(entities)} items",
        )

    diversity = float(audit.get("prompt_diversity_score") or 0.0)
    _pass("prompt_diversity_preserved", diversity >= 0.70, str(diversity))
    fusion = float(audit.get("cross_domain_fusion_score") or 0.0)
    _pass("cross_domain_fusion_preserved", fusion >= 0.75, str(fusion))
    strategy = float(audit.get("strategy_alignment_score") or 0.0)
    _pass("strategy_alignment_preserved", strategy >= 0.80, str(strategy))


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _section_items(prompt: str, label: str) -> list[str]:
    match = re.search(rf"{label}:\s*([^.]+)\.", prompt, flags=re.I)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(";") if item.strip()]


def main() -> None:
    os.environ.setdefault("OPENAI_INTENT_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_CROSS_DOMAIN_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_CONCEPT_DISTRIBUTION_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_PROMPT_CLEANUP_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_QUALITY_DRY_RUN", "1")
    os.environ.setdefault("SEO_PROVIDER_DRY_RUN", "1")
    os.environ.setdefault("OPENAI_SEO_DRY_RUN", "1")
    print("[validate_content_brain_prompt_cleanup] Content Brain V8.3")
    test_chemistry_perfume_prompt_cleanup()
    print("[validate_content_brain_prompt_cleanup] All checks PASS")


if __name__ == "__main__":
    main()
