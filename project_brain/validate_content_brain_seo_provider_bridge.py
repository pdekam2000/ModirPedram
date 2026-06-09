"""
Validate SEO Provider Bridge + SEO Director live-provider integration.
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
from content_brain.execution.content_brain_seo_director import build_seo_director_package, is_malformed_seo_title
from content_brain.execution.content_brain_seo_provider_bridge import fetch_seo_provider_intelligence


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _seo_step(result: dict) -> dict:
    step = next(item for item in result.get("steps") or [] if item.get("step_key") == "seo_title")
    return dict(step.get("payload") or {})


def test_bridge_marketing_dry_run() -> None:
    intel = fetch_seo_provider_intelligence(
        topic="Can AI destroy traditional marketing agencies by 2026?",
        language_code="en",
        platform="youtube_shorts",
    )
    _pass("bridge_dataforseo_used", intel.dataforseo_used is True)
    _pass("bridge_serpapi_used", intel.serpapi_used is True)
    _pass("bridge_keywords", len(intel.seo_keywords) >= 4, str(len(intel.seo_keywords)))
    _pass("bridge_related_queries", len(intel.related_queries) >= 2, str(len(intel.related_queries)))
    _pass("bridge_provider_titles", len(intel.title_candidates_from_providers) >= 3)
    _pass("bridge_live_source", intel.seo_data_source.startswith("live_providers"))


def test_director_marketing_dry_run() -> None:
    package = build_seo_director_package(
        topic="Can AI destroy traditional marketing agencies by 2026?",
        platform="youtube_shorts",
        language_code="en",
        use_provider_bridge=True,
    )
    _pass("director_dataforseo_used", package.dataforseo_used is True)
    _pass("director_serpapi_used", package.serpapi_used is True)
    _pass("director_live_source", package.seo_data_source.startswith("live_providers"))
    _pass("director_keywords_used", len(package.seo_keywords_used) >= 3)
    _pass("director_related_queries_used", len(package.related_queries_used) >= 2)
    _pass("director_title_not_raw_topic", not _is_raw_duplicate(package.seo_title, "Can AI destroy traditional marketing agencies by 2026?"), package.seo_title)
    _pass("director_title_not_malformed", not is_malformed_seo_title(package.seo_title, "Can AI destroy traditional marketing agencies by 2026?"), package.seo_title)
    _pass("director_openai_polish", bool((package.openai_seo_polish or {}).get("applied")), str(package.openai_seo_polish))


def test_e2e_marketing_seo() -> None:
    topic = "Can AI destroy traditional marketing agencies by 2026?"
    payload = run_content_brain_e2e_micro_test(topic=topic, duration_seconds=30)
    seo = _seo_step(payload)
    _pass("e2e_completed", payload.get("status") == "completed")
    _pass("e2e_seo_data_source", str(seo.get("seo_data_source", "")).startswith("live_providers"), str(seo.get("seo_data_source")))
    _pass("e2e_dataforseo_used", bool(seo.get("dataforseo_used")))
    _pass("e2e_serpapi_used", bool(seo.get("serpapi_used")))
    _pass("e2e_seo_keywords_used", len(seo.get("seo_keywords_used") or []) >= 3)
    _pass("e2e_related_queries_used", len(seo.get("related_queries_used") or []) >= 2)
    title = str(seo.get("seo_title") or "")
    _pass("e2e_title_not_raw_topic", not _is_raw_duplicate(title, topic), title)


def test_fallback_when_bridge_disabled() -> None:
    package = build_seo_director_package(
        topic="How to make pizza dough?",
        platform="youtube_shorts",
        language_code="en",
        use_provider_bridge=False,
    )
    _pass("fallback_source", package.seo_data_source == "fallback_templates", package.seo_data_source)
    _pass("fallback_title_present", bool(package.seo_title))


def _is_raw_duplicate(title: str, topic: str) -> bool:
    def tokens(text: str) -> list[str]:
        cleaned = re.sub(r"[^\w\s']", " ", str(text or "").lower())
        stop = {"by", "the", "a", "an", "in", "on", "of", "to", "for"}
        return [token for token in cleaned.split() if token and token not in stop]

    title_tokens = tokens(title)
    topic_tokens = tokens(topic)
    if title_tokens == topic_tokens:
        return True
    if len(title_tokens) >= len(topic_tokens) - 1:
        matches = sum(
            1
            for index, token in enumerate(topic_tokens)
            if index < len(title_tokens) and title_tokens[index] == token
        )
        if matches >= max(len(topic_tokens) - 2, int(len(topic_tokens) * 0.85)):
            return True
    return False


def main() -> None:
    os.environ["SEO_PROVIDER_DRY_RUN"] = "1"
    os.environ["OPENAI_SEO_DRY_RUN"] = "1"
    os.environ["OPENAI_INTENT_DRY_RUN"] = "1"
    os.environ["OPENAI_CLASSIFICATION_DRY_RUN"] = "1"
    os.environ["OPENAI_QUALITY_DRY_RUN"] = "1"
    os.environ["DATAFORSEO_DRY_RUN"] = "1"
    os.environ["SERPAPI_DRY_RUN"] = "1"
    print("[validate_content_brain_seo_provider_bridge] SEO Provider Bridge")
    test_bridge_marketing_dry_run()
    test_director_marketing_dry_run()
    test_e2e_marketing_seo()
    test_fallback_when_bridge_disabled()
    print("[validate_content_brain_seo_provider_bridge] All checks PASS")


if __name__ == "__main__":
    main()
