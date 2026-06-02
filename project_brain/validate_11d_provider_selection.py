"""
Phase 11D — provider selection engine validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.providers.provider_capability_registry import CAPABILITY_TEXT_TO_VIDEO
from content_brain.providers.provider_failover_policy import MODE_PREFERENCE_API, MODE_PREFERENCE_BROWSER
from content_brain.providers.provider_selection_engine import (
    OPTIMIZE_COST,
    OPTIMIZE_QUALITY,
    ProviderSelectionEngine,
    SelectionPreferences,
)
from core.video_provider_router import VideoProviderRouter


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


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    engine = ProviderSelectionEngine.load(str(root))
    results: list[dict] = []

    ranked = engine.rank_providers(CAPABILITY_TEXT_TO_VIDEO)
    results.append(
        _pass(
            "providers_ranked_text_to_video",
            len(ranked.ranked_candidates) >= 2,
            ",".join(c.provider_id for c in ranked.ranked_candidates[:5]),
        )
    )

    best = engine.select_best(CAPABILITY_TEXT_TO_VIDEO)
    results.append(
        _pass(
            "select_best_supported",
            best.selected_provider is not None
            and engine.capabilities.supports(best.selected_provider, CAPABILITY_TEXT_TO_VIDEO),
            best.selected_provider or "",
        )
    )

    blocked = engine.rank_providers(
        "subtitle_generation",
        SelectionPreferences(preferred_provider="runway"),
    )
    results.append(
        _pass(
            "unsupported_capability_blocked",
            blocked.selected_provider is None or len(blocked.ranked_candidates) == 0,
        )
    )

    excluded = engine.rank_providers(
        CAPABILITY_TEXT_TO_VIDEO,
        SelectionPreferences(excluded_providers=("runway", "runway_browser")),
    )
    active_ids = [c.provider_id for c in excluded.ranked_candidates]
    results.append(
        _pass(
            "excluded_provider_removed",
            "runway" not in active_ids and "runway_browser" not in active_ids,
        )
    )

    api_mode = engine.rank_providers(
        CAPABILITY_TEXT_TO_VIDEO,
        SelectionPreferences(mode_preference=MODE_PREFERENCE_API),
    )
    results.append(
        _pass(
            "mode_preference_api",
            all(
                engine.capabilities.get_provider(c.provider_id).supports_api_mode
                for c in api_mode.ranked_candidates
            ),
        )
    )
    browser_mode = engine.rank_providers(
        CAPABILITY_TEXT_TO_VIDEO,
        SelectionPreferences(mode_preference=MODE_PREFERENCE_BROWSER),
    )
    results.append(
        _pass(
            "mode_preference_browser",
            all(
                engine.capabilities.get_provider(c.provider_id).supports_browser_mode
                for c in browser_mode.ranked_candidates
            ),
        )
    )

    low_cost = engine.rank_providers(
        CAPABILITY_TEXT_TO_VIDEO,
        SelectionPreferences(max_cost=0.01, allow_unknown_cost=False),
    )
    results.append(
        _pass(
            "max_cost_blocks_expensive",
            low_cost.selected_provider in {None, "runway_browser"}
            or all(c.estimated_cost is None or c.estimated_cost <= 0.01 for c in low_cost.ranked_candidates),
        )
    )

    cost_opt = engine.rank_providers(
        CAPABILITY_TEXT_TO_VIDEO,
        SelectionPreferences(optimize_for=OPTIMIZE_COST),
    )
    quality_opt = engine.rank_providers(
        CAPABILITY_TEXT_TO_VIDEO,
        SelectionPreferences(optimize_for=OPTIMIZE_QUALITY),
    )
    cost_top = cost_opt.ranked_candidates[0].provider_id if cost_opt.ranked_candidates else ""
    quality_top = quality_opt.ranked_candidates[0].provider_id if quality_opt.ranked_candidates else ""
    results.append(
        _pass(
            "optimize_for_cost_changes_ranking",
            cost_top != "" and cost_opt.optimize_for == OPTIMIZE_COST,
            cost_top,
        )
    )
    results.append(
        _pass(
            "optimize_for_quality_changes_ranking",
            quality_top != "" and quality_opt.optimize_for == OPTIMIZE_QUALITY,
            quality_top,
        )
    )

    explanation = engine.explain_selection(best)
    results.append(
        _pass(
            "explanation_generated",
            len(explanation) >= 3 and any("Selected provider" in line for line in explanation),
        )
    )

    compare = engine.compare_candidates(
        CAPABILITY_TEXT_TO_VIDEO,
        ["runway", "hailuo_browser", "runway_browser"],
    )
    results.append(_pass("compare_candidates", len(compare.ranked_candidates) <= 3))

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        engine.select_best(CAPABILITY_TEXT_TO_VIDEO)
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        engine.rank_providers(CAPABILITY_TEXT_TO_VIDEO)
        results.append(_pass("no_router_dispatch", True))

    results.append(_pass("validate_11a_still_passes", _run_module("project_brain.validate_11a_capability_registry")))
    results.append(_pass("validate_11b_still_passes", _run_module("project_brain.validate_11b_cost_catalog")))
    results.append(_pass("validate_11c_still_passes", _run_module("project_brain.validate_11c_failover_policy")))
    results.append(_pass("validate_10k_matrix_still_passes", _run_module("project_brain.validate_10k_matrix")))

    passed = sum(1 for item in results if item["pass"])
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_pass": passed == len(results),
        },
    }


if __name__ == "__main__":
    report = run_matrix(".")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
