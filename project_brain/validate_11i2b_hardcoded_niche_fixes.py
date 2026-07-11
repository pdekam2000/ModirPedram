"""
Phase 11I-2B — validation for minimal hardcoded niche term fixes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from engines.seo_package_engine import (
    GENERIC_HASHTAGS,
    SKINCARE_HASHTAGS,
    SKINCARE_TERM_MARKERS,
    SEOPackageEngine,
)
from engines.subtitle_engine import DEFAULT_HIGHLIGHT_KEYWORDS, SubtitleEngine


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    return result.returncode == 0


SKINCARE_HIGHLIGHT_TERMS = frozenset(
    {"skin", "glow", "mask", "radiant", "hydrated", "beauty", "skincare", "soft", "healthy", "beautiful"}
)


def run_matrix(project_root: str | Path = ".") -> dict:
    _ = Path(project_root).resolve()
    results: list[dict] = []

    # 1. Default subtitle fallback has no skincare terms
    overlap = SKINCARE_HIGHLIGHT_TERMS.intersection(set(DEFAULT_HIGHLIGHT_KEYWORDS))
    results.append(
        _pass(
            "subtitle_default_no_skincare_terms",
            len(overlap) == 0,
            ",".join(sorted(overlap)) or "none",
        )
    )

    # 2. Custom highlight_keywords accepted
    custom_engine = SubtitleEngine(highlight_keywords=["goal", "referee", "VAR"])
    styled = custom_engine.style_word("GOAL")
    results.append(
        _pass(
            "subtitle_custom_highlight_keywords",
            r"{\c&H00FFFF&" in styled and "GOAL" in styled,
        )
    )
    neutral = custom_engine.style_word("skin")
    results.append(
        _pass(
            "subtitle_custom_keywords_not_skincare_default",
            neutral == "skin",
        )
    )

    # 3. Old caller signature still works
    try:
        legacy_engine = SubtitleEngine()
        legacy_result = legacy_engine.create_subtitles(
            narration_text="Stop and watch this secret detail.",
            duration=6,
            base_name="validate_11i2b_legacy",
        )
        legacy_ok = (
            isinstance(legacy_result, dict)
            and bool(legacy_result.get("srt"))
            and bool(legacy_result.get("ass"))
        )
    except Exception as exc:
        legacy_ok = False
        legacy_result = str(exc)
    results.append(
        _pass(
            "subtitle_legacy_caller_signature",
            legacy_ok,
            str(legacy_result) if not legacy_ok else "",
        )
    )

    seo = SEOPackageEngine()
    generic_topic = "football VAR decisions in the 89th minute"

    # 4. Generic hashtags — no skincare tags
    generic_tags = seo.generate_hashtags(count=8, profile=None, topic=generic_topic)
    skincare_in_tags = [tag for tag in generic_tags if any(m in tag.lower() for m in ("skincare", "selfcare", "glowup", "beauty", "glassskin"))]
    results.append(
        _pass(
            "seo_generic_no_skincare_hashtags",
            len(skincare_in_tags) == 0,
            ",".join(skincare_in_tags) or ",".join(generic_tags),
        )
    )
    results.append(
        _pass(
            "seo_generic_hashtags_from_neutral_pool",
            all(tag in GENERIC_HASHTAGS for tag in generic_tags),
            ",".join(generic_tags),
        )
    )

    # 5. Generic titles — no skin/glow/mask/radiant
    banned_in_titles = []
    for _ in range(20):
        title = seo.generate_title(generic_topic, profile=None)
        lowered = title.lower()
        if any(term in lowered for term in SKINCARE_TERM_MARKERS):
            banned_in_titles.append(title)
    results.append(
        _pass(
            "seo_generic_title_no_skincare_terms",
            len(banned_in_titles) == 0,
            banned_in_titles[0] if banned_in_titles else "clean",
        )
    )

    # 6. Explicit skincare profile may still produce skincare terms
    skincare_profile = {
        "niche": "selfcare",
        "niche_label": "Skincare Selfcare",
        "seo_keywords": ["#skincare", "#glowup", "#selfcare"],
    }
    skincare_tags = seo.generate_hashtags(count=5, profile=skincare_profile, topic="night routine")
    skincare_title = seo.generate_title("night routine", profile=skincare_profile)
    skincare_keywords = seo.generate_keywords("night routine", profile=skincare_profile)
    skincare_hit = any(
        any(marker in str(item).lower() for marker in ("skincare", "selfcare", "glow", "skin"))
        for item in (skincare_tags + [skincare_title] + skincare_keywords)
    )
    results.append(
        _pass(
            "seo_skincare_profile_allows_skincare_terms",
            skincare_hit,
            f"tags={skincare_tags} title={skincare_title}",
        )
    )
    results.append(
        _pass(
            "seo_skincare_profile_hashtag_pool",
            any(tag in SKINCARE_HASHTAGS or "skincare" in tag.lower() for tag in skincare_tags),
            ",".join(skincare_tags),
        )
    )

    # 7–9. Regression validators
    results.append(
        _pass(
            "validate_11g_regression",
            _run_module("project_brain.validate_11g_multi_category_runtime_shell"),
        )
    )
    results.append(
        _pass(
            "validate_11i2_subtitle_foundation_regression",
            _run_module("project_brain.validate_11i2_subtitle_runtime_foundation"),
        )
    )
    results.append(
        _pass(
            "validate_11h2d_voice_regression",
            _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"),
        )
    )

    passed = sum(1 for item in results if item["pass"])
    failed = [item for item in results if not item["pass"]]
    return {
        "phase": "11I-2B",
        "title": "Hardcoded Niche Term Fixes",
        "passed": passed,
        "failed": len(failed),
        "total": len(results),
        "all_pass": len(failed) == 0,
        "results": results,
        "failures": failed,
    }


def main() -> int:
    report = run_matrix(".")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for item in report["results"]:
        status = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{status}] {item['test']}{detail}")
    print(f"\nSummary: {report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
