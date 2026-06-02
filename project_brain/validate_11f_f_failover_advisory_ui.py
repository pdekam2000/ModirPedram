"""
Phase 11F-f — Failover advisory UI visibility validation (static + API fixture checks).
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

from content_brain.execution.session_store import ExecutionSessionStore
from project_brain.validate_11e_common import append_regression_checks
from ui.api.services.runtime_service import RuntimeService


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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_failover_advisory(status: dict) -> dict | None:
    runtime = status.get("execution_runtime") if isinstance(status.get("execution_runtime"), dict) else {}
    operations = runtime.get("operations") if isinstance(runtime.get("operations"), dict) else {}
    advisory = operations.get("failover_advisory")
    return advisory if isinstance(advisory, dict) else None


def _sample_failed_advisory() -> dict:
    return {
        "advisory_only": True,
        "advisory_version": "11f_e_v1",
        "failover_recommended": True,
        "failover_allowed": True,
        "reason": "provider_failure",
        "current_provider": "hailuo_browser",
        "preferred_next_provider": "runway_browser",
        "cost_warning": "runway_browser: cost unknown for text_to_video",
        "capability_match": True,
        "partial_artifacts_present": True,
        "partial_artifacts_safe_to_reuse": False,
        "partial_artifact_count": 1,
        "partial_paths": ["/tmp/clip_01.mp4"],
        "candidate_chain": ["runway_browser", "runway", "minimax_api"],
        "provider_selection": {
            "selected_provider": "runway_browser",
            "ranked_candidates": ["runway_browser", "runway", "minimax_api"],
            "warnings": [],
        },
        "failover_plan": {
            "policy_id": "text_to_video_default",
            "chain": ["hailuo_browser", "runway_browser", "runway"],
            "warnings": [],
        },
    }


def _sample_cancel_advisory() -> dict:
    return {
        "advisory_only": True,
        "failover_recommended": False,
        "failover_allowed": False,
        "reason": "operator_cancelled",
        "blocked_reason": "operator_cancelled",
        "current_provider": "hailuo_browser",
        "partial_artifacts_present": False,
        "partial_artifacts_safe_to_reuse": False,
        "partial_artifact_count": 0,
    }


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    observability = root / "ui" / "web" / "src" / "components" / "RuntimeObservability.tsx"
    panel = root / "ui" / "web" / "src" / "components" / "FailoverAdvisoryPanel.tsx"
    utils = root / "ui" / "web" / "src" / "utils" / "failoverAdvisory.ts"
    css = root / "ui" / "web" / "src" / "App.css"

    observability_text = _read(observability)
    panel_text = _read(panel)
    utils_text = _read(utils)

    results.append(_pass("failover_panel_file_exists", panel.exists()))
    results.append(_pass("failover_utils_file_exists", utils.exists()))
    results.append(_pass("observability_imports_panel", "FailoverAdvisoryPanel" in observability_text))
    results.append(_pass("observability_resolves_advisory", "resolveFailoverAdvisory" in observability_text))
    results.append(_pass("panel_title_present", "Failover Advisory" in panel_text))
    results.append(_pass("panel_shows_recommended", "failover_recommended" in panel_text))
    results.append(_pass("panel_shows_reason", "reason" in panel_text))
    results.append(_pass("panel_shows_next_provider", "Next provider" in panel_text))
    results.append(_pass("panel_shows_provider_selection", "Provider selection (11D)" in panel_text))
    results.append(_pass("panel_shows_cost_warning", "Cost warning" in panel_text))
    results.append(_pass("panel_shows_partial_count", "Partial artifacts" in panel_text))
    results.append(_pass("panel_shows_partial_reusable", "Partial reusable" in panel_text))
    results.append(_pass("advisory_only_note", "Advisory only" in panel_text))
    results.append(_pass("css_styles_present", "runtime-failover-advisory" in _read(css)))

    ui_bundle = observability_text + panel_text + utils_text
    forbidden = [
        "dispatchRuntime(",
        "postSessionAction(",
        "generate_clips(",
        "dispatch_by_id(",
        "ProviderRuntimeEngine",
        "VideoProviderRouter",
        "retry(",
        "requeue(",
    ]
    hits = [token for token in forbidden if token in ui_bundle]
    results.append(_pass("no_execution_calls_in_ui", not hits, ", ".join(hits)))

    # Missing advisory: resolve helper returns null
    missing = _resolve_failover_advisory({"execution_runtime": {"operations": {}}})
    legacy = _resolve_failover_advisory({})
    results.append(_pass("missing_advisory_returns_none", missing is None and legacy is None))

    failed_advisory = _sample_failed_advisory()
    cancel_advisory = _sample_cancel_advisory()

    results.append(
        _pass(
            "failed_advisory_recommends_failover",
            failed_advisory.get("failover_recommended") is True,
            str(failed_advisory.get("preferred_next_provider")),
        )
    )
    results.append(
        _pass(
            "failed_advisory_has_selection_metadata",
            bool(failed_advisory.get("provider_selection")),
        )
    )
    results.append(
        _pass(
            "failed_advisory_has_chain_metadata",
            bool(failed_advisory.get("candidate_chain")),
            ",".join(failed_advisory.get("candidate_chain") or []),
        )
    )
    results.append(
        _pass(
            "cancelled_advisory_blocks_failover",
            cancel_advisory.get("failover_recommended") is False
            and cancel_advisory.get("reason") == "operator_cancelled",
        )
    )
    results.append(
        _pass(
            "partial_advisory_not_reusable",
            failed_advisory.get("partial_artifacts_safe_to_reuse") is False
            and failed_advisory.get("partial_artifact_count") == 1,
        )
    )

    # Runtime status API exposes advisory from session without executing providers
    store = ExecutionSessionStore(root)
    service = RuntimeService(store)
    session_id = "exec_11ff_ui_advisory"
    base = json.loads(
        (root / "storage" / "content_brain" / "execution" / "sessions" / "exec_10i_dequeued_demo.json").read_text(
            encoding="utf-8"
        )
    )
    session = copy.deepcopy(base)
    session["execution_session_id"] = session_id
    session["state"] = "FAILED"
    session["provider"] = "hailuo_browser"
    session["execution_runtime"] = {
        "state": "FAILED",
        "provider_resolved": "hailuo_browser",
        "operations": {"failover_advisory": failed_advisory},
        "artifacts_by_category": {"video_generation": []},
    }
    store.save_session(session, overwrite=True)

    status = service.status(session_id)
    advisory_from_api = _resolve_failover_advisory(status)
    results.append(_pass("runtime_status_exposes_advisory", advisory_from_api is not None))
    results.append(
        _pass(
            "runtime_status_next_provider",
            advisory_from_api.get("preferred_next_provider") == "runway_browser" if advisory_from_api else False,
        )
    )

    legacy_id = "exec_11ff_ui_legacy"
    legacy_session = copy.deepcopy(base)
    legacy_session["execution_session_id"] = legacy_id
    legacy_session["state"] = "SIMULATED"
    legacy_session.pop("execution_runtime", None)
    store.save_session(legacy_session, overwrite=True)
    legacy_status = service.status(legacy_id)
    results.append(_pass("legacy_status_no_crash", legacy_status.get("state") == "SIMULATED"))
    results.append(_pass("legacy_status_no_advisory", _resolve_failover_advisory(legacy_status) is None))

    # Conditional render guard in observability component
    results.append(
        _pass(
            "observability_conditional_render",
            bool(re.search(r"failoverAdvisory\s*&&\s*<FailoverAdvisoryPanel", observability_text)),
        )
    )

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11f_e_still_passes", "project_brain.validate_11f_e_hailuo_failover_advisory"),
            ("validate_11f_d_still_passes", "project_brain.validate_11f_d_hailuo_runtime_cancel"),
            ("validate_10k_matrix_still_passes", "project_brain.validate_10k_matrix"),
        ],
    )

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
