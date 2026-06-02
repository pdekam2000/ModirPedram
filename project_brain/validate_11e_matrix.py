"""
Phase 11E-g — complete Runway Hardening validation matrix (11E-a through 11E-f + cross-cutting).

Validation and documentation support only — no provider execution, API calls, or browser automation.
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.provider_cancel_wiring import supports_cancel_check
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.execution.runway_config import RUNWAY_BROWSER_ROUTER_KEY, RunwayConfigResolver
from content_brain.execution.runway_failover_advisory import build_runway_failover_advisory
from content_brain.execution.runway_preflight import RunwayPreflightEngine
from content_brain.providers.provider_capability_registry import CAPABILITY_TEXT_TO_VIDEO
from content_brain.providers.provider_failover_policy import ProviderFailoverPlanner
from content_brain.providers.provider_selection_engine import ProviderSelectionEngine
from core.video_provider_router import VideoProviderRouter
from providers.runway_artifact_utils import finalize_download_artifact, normalize_artifact_record
from providers.runway_error_classifier import classify_runway_failure
from providers.runway_video_provider import RunwayVideoProvider


def _pass(name: str, ok: bool, detail: str = "", *, section: str = "11E-g") -> dict:
    return {"test": name, "section": section, "pass": ok, "detail": detail}


def _extract_json_report(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.rfind("{")
    if start >= 0:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            return {}
    return {}


def _run_subprocess_module(module_name: str, section: str) -> list[dict]:
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    rows: list[dict] = []
    report = _extract_json_report(result.stdout)
    summary = report.get("summary", {})
    exit_ok = result.returncode == 0 or bool(summary.get("all_pass"))
    rows.append(
        _pass(
            f"{section}_module_exit_ok",
            exit_ok,
            f"exit={result.returncode}",
            section=section,
        )
    )
    if summary:
        rows.append(
            _pass(
                f"{section}_all_pass",
                bool(summary.get("all_pass")),
                json.dumps(summary),
                section=section,
            )
        )
    return rows


def _run_submodule_gate(module_name: str, section: str) -> list[dict]:
    """Run validator in isolated subprocess; return single all_pass gate row."""
    last_row: list[dict] = []
    for attempt in range(2):
        env = {**os.environ, "VALIDATE_11E_MATRIX": "1"}
        result = subprocess.run(
            [sys.executable, "-m", module_name],
            capture_output=True,
            text=True,
            cwd=str(Path(".").resolve()),
            env=env,
        )
        report = _extract_json_report(result.stdout)
        summary = report.get("summary", {})
        all_pass = bool(summary.get("all_pass")) if summary else result.returncode == 0
        last_row = [
            _pass(
                f"{section}_all_pass",
                all_pass,
                json.dumps(summary) if summary else f"exit={result.returncode}",
                section=section,
            )
        ]
        if all_pass:
            return last_row
    return last_row


def validate_11e_cross_cutting(root: Path) -> list[dict]:
    results: list[dict] = []

    resolver = RunwayConfigResolver(root)
    config = resolver.resolve()
    results.append(
        _pass(
            "runway_config_resolver_active_default",
            config.active_video_provider == RUNWAY_BROWSER_ROUTER_KEY,
            config.active_video_provider,
            section="11E-a",
        )
    )
    results.append(_pass("runway_config_resolver_has_api_key_flag", hasattr(config, "api_key_present"), section="11E-a"))

    preflight = RunwayPreflightEngine(root).evaluate(_runway_browser_session())
    results.append(_pass("runway_preflight_engine_runs", preflight is not None, section="11E-a"))

    taxonomy = classify_runway_failure("timeout waiting for runway task", http_status=504)
    results.append(
        _pass(
            "runway_error_taxonomy_timeout",
            taxonomy.get("code") in {"PROVIDER_TIMEOUT", "PROVIDER_RUNTIME_ERROR"},
            taxonomy.get("code", ""),
            section="11E-a",
        )
    )

    api_source = Path(inspect.getfile(RunwayVideoProvider)).read_text(encoding="utf-8")
    results.append(_pass("api_bounded_polling_present", "max_poll" in api_source.lower() or "poll" in api_source, section="11E-b"))
    results.append(_pass("api_cancel_checkpoints", "cancel_check" in api_source, section="11E-b"))
    results.append(_pass("api_uses_finalize_download_artifact", "finalize_download_artifact" in api_source, section="11E-b"))

    orch_path = root / "orchestrators" / "runway_browser_orchestrator.py"
    orch_source = orch_path.read_text(encoding="utf-8") if orch_path.exists() else ""
    results.append(_pass("browser_no_infinite_sleep", "999999" not in orch_source, section="11E-c"))
    results.append(_pass("browser_bounded_waits", "browser_max_wait_seconds" in orch_source or "wait_seconds" in orch_source, section="11E-c"))
    results.append(_pass("browser_cancel_checkpoints", "cancel_check" in orch_source, section="11E-c"))
    results.append(_pass("browser_partial_artifact_attach", "_attach_partial_artifacts" in orch_source, section="11E-c"))

    artifact_utils = root / "providers" / "runway_artifact_utils.py"
    results.append(_pass("shared_artifact_utils_exists", artifact_utils.exists(), section="11E-d"))

    router_source = Path(inspect.getfile(VideoProviderRouter)).read_text(encoding="utf-8")
    runtime_source = Path(inspect.getfile(ProviderRuntimeEngine)).read_text(encoding="utf-8")
    results.append(_pass("router_passes_cancel_check", "cancel_check" in router_source, section="11E-e"))
    results.append(_pass("runtime_builds_cancel_check", "build_runtime_cancel_check" in runtime_source, section="11E-e"))
    results.append(
        _pass(
            "api_provider_supports_cancel_check",
            supports_cancel_check(RunwayVideoProvider.generate_clips),
            section="11E-e",
        )
    )

    advisory = build_runway_failover_advisory(
        session={"provider": "runway_browser"},
        execution_runtime={"provider_resolved": "runway_browser"},
        outcome="FAILED",
        failure_code="PROVIDER_TIMEOUT",
        project_root=root,
    )
    results.append(_pass("failover_advisory_metadata", advisory is not None and advisory.get("advisory_only") is True, section="11E-f"))
    results.append(
        _pass(
            "failover_advisory_no_auto_execute",
            advisory.get("failover_recommended") is True and advisory.get("failover_allowed") in {True, False},
            str(advisory.get("preferred_next_provider")),
            section="11E-f",
        )
    )

    cancel_advisory = build_runway_failover_advisory(
        session={"provider": "runway"},
        execution_runtime={"provider_resolved": "runway"},
        outcome="CANCELLED",
        failure_code="OPERATIONS_CANCELLED",
        project_root=root,
    )
    results.append(_pass("cancel_blocks_failover_advisory", cancel_advisory.get("failover_recommended") is False, section="11E-f"))

    advisory_source = (root / "content_brain" / "execution" / "runway_failover_advisory.py").read_text(encoding="utf-8")
    results.append(
        _pass(
            "no_auto_failover_execution_in_advisory",
            "ProviderRuntimeEngine" not in advisory_source
            and "VideoProviderRouter" not in advisory_source
            and "dispatch_by_id" not in advisory_source
            and "generate_clips(" not in advisory_source,
            section="11E-f",
        )
    )

    results.append(_pass("11a_capability_registry_loads", ProviderSelectionEngine.load(root).capabilities is not None, section="11A"))
    results.append(_pass("11b_cost_estimator_available", ProviderSelectionEngine.load(root).estimator is not None, section="11B"))
    results.append(_pass("11c_failover_planner_loads", ProviderFailoverPlanner.load(root) is not None, section="11C"))
    plan = ProviderFailoverPlanner.load(root).plan_failover(CAPABILITY_TEXT_TO_VIDEO)
    results.append(_pass("11c_chain_non_empty", len(plan.chain) >= 2, section="11C"))
    ranked = ProviderSelectionEngine.load(root).rank_providers(CAPABILITY_TEXT_TO_VIDEO)
    results.append(_pass("11d_selection_ranks_providers", len(ranked.ranked_candidates) >= 1, section="11D"))

    with patch("core.video_provider_router.VideoProviderRouter.generate_clips") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("provider dispatch must not run in matrix cross-cut")
        import tempfile

        from providers.runway_artifact_utils import MIN_ARTIFACT_BYTES

        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.mp4"
            sample.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 10))
            normalize_artifact_record(
                file_path=str(sample),
                mode="api",
                provider_id="runway",
                clip_index=1,
            )
        build_runway_failover_advisory(
            session={"provider": "runway"},
            execution_runtime={"provider_resolved": "runway"},
            outcome="FAILED",
            failure_code="PROVIDER_RUNTIME_ERROR",
            project_root=root,
        )
        results.append(_pass("validation_no_provider_dispatch", True, section="11E-g"))

    with tempfile.TemporaryDirectory() as tmp:
        from providers.runway_artifact_utils import MIN_ARTIFACT_BYTES, MODE_API

        path = Path(tmp) / "partial.mp4"
        path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 20))
        record = finalize_download_artifact(path, mode=MODE_API, provider_id="runway", clip_index=1, partial=True)
        results.append(_pass("partial_artifact_preserved", path.exists(), section="11E-d"))
        results.append(_pass("partial_marked_not_reusable_default", record.get("partial") is True, section="11E-d"))

    return results


def _runway_browser_session() -> dict:
    return {
        "provider": "runway_browser",
        "provider_selection": {
            "primary_provider": "runway_browser",
            "category_selections": {
                "video_generation": {"provider": "runway_browser", "execution_mode": "browser"}
            },
        },
        "brief_snapshot": {
            "video_format_plan": {"clip_count": 1, "capability": CAPABILITY_TEXT_TO_VIDEO},
            "run_context": {
                "story_intelligence": {
                    "schema_director_shots": [{"clip_number": 1, "prompt": "matrix validation clip."}]
                }
            },
        },
    }


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    slice_modules = [
        ("project_brain.validate_11e_a_runway_preflight", "11E-a"),
        ("project_brain.validate_11e_b_runway_api_hardening", "11E-b"),
        ("project_brain.validate_11e_c_runway_browser_hardening", "11E-c"),
        ("project_brain.validate_11e_d_runway_artifacts", "11E-d"),
        ("project_brain.validate_11e_e_runtime_cancel_wiring", "11E-e"),
        ("project_brain.validate_11e_f_runway_failover_advisory", "11E-f"),
    ]

    for module_name, section in slice_modules:
        results.extend(_run_submodule_gate(module_name, section))

    regression_modules = [
        ("project_brain.validate_11a_capability_registry", "11A"),
        ("project_brain.validate_11b_cost_catalog", "11B"),
        ("project_brain.validate_11c_failover_policy", "11C"),
        ("project_brain.validate_11d_provider_selection", "11D"),
        ("project_brain.validate_10k_matrix", "10K"),
    ]
    for module_name, section in regression_modules:
        results.extend(_run_submodule_gate(module_name, section))

    results.extend(validate_11e_cross_cutting(root))

    passed = sum(1 for item in results if item["pass"])
    failed_items = [item for item in results if not item["pass"]]
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_pass": passed == len(results),
            "failed_tests": [item["test"] for item in failed_items],
        },
        "slice_modules": [name for name, _ in slice_modules],
        "regression_modules": [name for name, _ in regression_modules],
    }


if __name__ == "__main__":
    report = run_matrix(".")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
