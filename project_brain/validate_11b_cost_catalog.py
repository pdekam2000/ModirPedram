"""
Phase 11B — provider cost catalog and estimator validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.providers.provider_capability_registry import CAPABILITY_TEXT_TO_VIDEO
from content_brain.providers.provider_cost_catalog import (
    COST_MODEL_FREE,
    COST_MODEL_UNKNOWN,
    DEFAULT_11A_PROVIDER_IDS,
    PLACEHOLDER_NOTE,
    ProviderCostCatalog,
    ProviderCostEstimator,
)
from core.video_provider_router import VideoProviderRouter


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    catalog = ProviderCostCatalog.load(root)
    estimator = ProviderCostEstimator.load(root)
    results: list[dict] = []

    results.append(_pass("catalog_loads", catalog.to_dict().get("catalog_version") == "11b_v1"))
    results.append(_pass("estimator_loads", estimator.catalog is not None))

    coverage = catalog.coverage_for_default_providers()
    results.append(
        _pass(
            "all_11a_providers_have_entries",
            all(coverage.get(pid) for pid in DEFAULT_11A_PROVIDER_IDS),
            json.dumps({k: v for k, v in coverage.items() if not v}),
        )
    )

    runway_est = estimator.estimate_video("runway", clips=2, seconds=10)
    results.append(
        _pass(
            "estimate_supported_video_capability",
            runway_est.blocked is False and runway_est.estimated_cost is not None,
            json.dumps(runway_est.to_dict()),
        )
    )
    results.append(
        _pass(
            "estimate_is_marked_estimate",
            runway_est.is_estimate is True and PLACEHOLDER_NOTE in runway_est.notes,
        )
    )

    hailuo_free = estimator.estimate_video("runway_browser", clips=3)
    results.append(
        _pass(
            "estimate_free_model",
            hailuo_free.cost_model == COST_MODEL_FREE and hailuo_free.estimated_cost == 0.0,
        )
    )

    blocked = estimator.estimate("elevenlabs", CAPABILITY_TEXT_TO_VIDEO, 1)
    results.append(
        _pass(
            "block_unsupported_capability",
            blocked.blocked is True and blocked.block_reason == "CAPABILITY_UNSUPPORTED",
        )
    )

    unknown = estimator.estimate("hailuo_api", CAPABILITY_TEXT_TO_VIDEO, 2)
    results.append(
        _pass(
            "unknown_pricing_handled",
            unknown.blocked is False
            and unknown.cost_model == COST_MODEL_UNKNOWN
            and unknown.estimated_cost is None,
        )
    )

    voice = estimator.estimate_voice("elevenlabs", characters=1000)
    results.append(
        _pass(
            "estimate_voice",
            voice.blocked is False and voice.estimated_cost is not None,
            str(voice.estimated_cost),
        )
    )

    music = estimator.estimate_music("suno", tracks=1)
    results.append(
        _pass(
            "estimate_music_unknown_safe",
            music.blocked is False and music.estimated_cost is None,
        )
    )

    comparison = estimator.compare(
        ["hailuo_browser", "runway", "runway_browser"],
        CAPABILITY_TEXT_TO_VIDEO,
        2,
    )
    results.append(_pass("compare_multiple_providers", len(comparison) == 3))
    results.append(
        _pass(
            "compare_sorts_cheapest_first",
            comparison[0].provider_id == "runway_browser" and comparison[0].estimated_cost == 0.0,
        )
    )

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        estimator.estimate_video("runway", clips=1)
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        estimator.compare(["runway", "hailuo_browser"], CAPABILITY_TEXT_TO_VIDEO, 1)
        results.append(_pass("no_router_dispatch", True))

    results.append(_pass("runtime_engine_importable", ProviderRuntimeEngine is not None))

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
