"""
Phase 11C — provider failover policy validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.providers.provider_capability_registry import CAPABILITY_TEXT_TO_VIDEO
from content_brain.providers.provider_failover_policy import (
    FailoverConstraints,
    FailoverPolicy,
    MODE_PREFERENCE_API,
    MODE_PREFERENCE_BROWSER,
    ProviderFailoverPlanner,
    ProviderFailoverPolicyStore,
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
    planner = ProviderFailoverPlanner.load(root)
    results: list[dict] = []

    store = planner.policies
    results.append(_pass("policy_loads", store.to_dict().get("policy_version") == "11c_v1"))
    results.append(_pass("get_policy_text_to_video", planner.get_policy(CAPABILITY_TEXT_TO_VIDEO) is not None))

    plan = planner.plan_failover(CAPABILITY_TEXT_TO_VIDEO)
    chain_ids = [step.provider_id for step in plan.chain]
    results.append(
        _pass(
            "text_to_video_chain_created",
            plan.preferred_provider == "runway"
            and "runway_browser" in chain_ids
            and "hailuo_browser" in chain_ids,
            ",".join(chain_ids),
        )
    )
    results.append(_pass("plan_is_executable_later", plan.is_executable_later is True))
    results.append(_pass("plan_has_estimated_costs", len(plan.estimated_costs) >= 1))

    results.append(
        _pass(
            "unsupported_provider_not_in_chain",
            all(step.provider_id != "elevenlabs" for step in plan.chain),
        )
    )

    excluded = planner.plan_failover(
        CAPABILITY_TEXT_TO_VIDEO,
        constraints=FailoverConstraints(excluded_providers=("runway", "runway_browser")),
    )
    active = [step.provider_id for step in excluded.chain if not step.blocked]
    results.append(
        _pass(
            "excluded_provider_blocked",
            "runway" in excluded.blocked_providers and "runway" not in active,
        )
    )

    api_only = planner.plan_failover(
        CAPABILITY_TEXT_TO_VIDEO,
        constraints=FailoverConstraints(mode_preference=MODE_PREFERENCE_API),
    )
    api_active = [step for step in api_only.chain if not step.blocked]
    results.append(
        _pass(
            "mode_preference_api",
            all(step.supports_api_mode for step in api_active),
            ",".join(step.provider_id for step in api_active),
        )
    )
    browser_only = planner.plan_failover(
        CAPABILITY_TEXT_TO_VIDEO,
        constraints=FailoverConstraints(mode_preference=MODE_PREFERENCE_BROWSER),
    )
    browser_active = [step for step in browser_only.chain if not step.blocked]
    results.append(
        _pass(
            "mode_preference_browser",
            all(step.supports_browser_mode for step in browser_active),
        )
    )

    results.append(
        _pass(
            "unknown_cost_warning_default",
            any("hailuo_api" in w for w in plan.warnings) or any(
                step.provider_id == "hailuo_api" and step.warning for step in plan.chain
            ),
        )
    )

    base_policy = planner.get_policy(CAPABILITY_TEXT_TO_VIDEO)
    assert base_policy is not None
    strict_policy = FailoverPolicy(
        policy_id=base_policy.policy_id,
        capability=base_policy.capability,
        preferred_provider=base_policy.preferred_provider,
        fallback_providers=base_policy.fallback_providers,
        max_attempts=base_policy.max_attempts,
        allow_browser_fallback=base_policy.allow_browser_fallback,
        allow_api_fallback=base_policy.allow_api_fallback,
        allow_cross_vendor_fallback=base_policy.allow_cross_vendor_fallback,
        preserve_partial_artifacts=base_policy.preserve_partial_artifacts,
        stop_on_cost_unknown=True,
        stop_on_low_confidence_cost=base_policy.stop_on_low_confidence_cost,
        notes=base_policy.notes,
    )
    strict_planner = ProviderFailoverPlanner(
        policy_store=ProviderFailoverPolicyStore([strict_policy]),
        capability_registry=planner.capabilities,
        cost_estimator=planner.estimator,
    )
    strict_plan = strict_planner.plan_failover(
        CAPABILITY_TEXT_TO_VIDEO,
        constraints=FailoverConstraints(allow_unknown_cost=False),
    )
    hailuo_api_step = next((s for s in strict_plan.chain if s.provider_id == "hailuo_api"), None)
    results.append(
        _pass(
            "unknown_cost_block_when_policy_requires",
            hailuo_api_step is not None and hailuo_api_step.blocked is True,
            hailuo_api_step.block_reason if hailuo_api_step else "",
        )
    )

    results.append(
        _pass(
            "capability_support_enforced",
            plan.capability_support.get("runway") is True
            and len(planner.providers_for_failover(CAPABILITY_TEXT_TO_VIDEO)) >= 1,
        )
    )

    explanation = planner.explain_plan(plan)
    results.append(
        _pass(
            "explain_plan_produced",
            len(explanation) >= 4 and any("runway" in line for line in explanation),
        )
    )

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        planner.plan_failover(CAPABILITY_TEXT_TO_VIDEO)
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        planner.plan_failover("music_generation")
        results.append(_pass("no_router_dispatch", True))

    results.append(_pass("validate_11a_still_passes", _run_module("project_brain.validate_11a_capability_registry")))
    results.append(_pass("validate_11b_still_passes", _run_module("project_brain.validate_11b_cost_catalog")))
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
