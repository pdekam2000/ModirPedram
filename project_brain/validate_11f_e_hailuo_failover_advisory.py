"""
Phase 11F-e — Hailuo failover readiness advisory validation (mocks only).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.hailuo_config import HAILUO_BROWSER_ROUTER_KEY
from content_brain.execution.hailuo_failover_advisory import (
    REASON_OPERATOR_CANCELLED,
    build_hailuo_failover_advisory,
    is_hailuo_provider,
)
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine, RuntimePolicy
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.providers.provider_capability_registry import CAPABILITY_TEXT_TO_VIDEO
from content_brain.providers.provider_failover_policy import ProviderFailoverPlanner
from content_brain.providers.provider_selection_engine import ProviderSelectionEngine
from core.video_provider_router import VideoProviderRouter
from providers.hailuo_api_errors import HailuoCancelledError
from providers.hailuo_artifact_utils import MIN_ARTIFACT_BYTES, MODE_BROWSER, finalize_download_artifact
from project_brain.validate_11e_common import append_regression_checks


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


def _hailuo_session(root: Path, session_id: str) -> dict:
    base = json.loads(
        (root / "storage" / "content_brain" / "execution" / "sessions" / "exec_10i_dequeued_demo.json").read_text(
            encoding="utf-8"
        )
    )
    session = copy.deepcopy(base)
    session["execution_session_id"] = session_id
    session["state"] = "DEQUEUED"
    session["provider"] = "hailuo_browser"
    session.setdefault("provider_selection", {})
    session["provider_selection"]["primary_provider"] = "hailuo_browser"
    session["provider_selection"].setdefault("category_selections", {})
    session["provider_selection"]["category_selections"]["video_generation"] = {
        "provider": "hailuo",
        "execution_mode": "browser",
    }
    session["brief_snapshot"]["video_format_plan"]["provider_name"] = "hailuo_browser"
    session["brief_snapshot"]["video_format_plan"]["capability"] = "text_to_video"
    session.pop("execution_runtime", None)
    session.pop("operations_control", None)
    return session


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    engine = ProviderRuntimeEngine(store)
    planner = ProviderFailoverPlanner.load(root)
    selector = ProviderSelectionEngine.load(root)
    results: list[dict] = []

    runtime_failed = {
        "provider_resolved": HAILUO_BROWSER_ROUTER_KEY,
        "prompt_bundle": {"capability": CAPABILITY_TEXT_TO_VIDEO, "clip_count": 1},
        "artifacts_by_category": {},
    }
    advisory_failed = build_hailuo_failover_advisory(
        session={"provider": HAILUO_BROWSER_ROUTER_KEY},
        execution_runtime=runtime_failed,
        outcome="FAILED",
        failure_code="PROVIDER_TIMEOUT",
        failure_message="hailuo generation timed out",
        project_root=root,
        planner=planner,
        selection_engine=selector,
    )
    results.append(_pass("failed_hailuo_gets_advisory", advisory_failed is not None))
    results.append(
        _pass(
            "failed_recommends_failover",
            bool(advisory_failed and advisory_failed.get("failover_recommended") is True),
            str(advisory_failed.get("preferred_next_provider") if advisory_failed else ""),
        )
    )
    results.append(
        _pass(
            "candidate_chain_from_11c",
            bool(advisory_failed and len(advisory_failed.get("candidate_chain") or []) >= 1),
            ",".join((advisory_failed or {}).get("candidate_chain") or []),
        )
    )
    results.append(
        _pass(
            "selection_metadata_from_11d",
            bool(advisory_failed and advisory_failed.get("provider_selection")),
            json.dumps((advisory_failed or {}).get("provider_selection") or {}),
        )
    )
    results.append(_pass("advisory_only_flag", advisory_failed.get("advisory_only") is True))
    results.append(_pass("current_provider_recorded", advisory_failed.get("current_provider") == HAILUO_BROWSER_ROUTER_KEY))

    advisory_cancel = build_hailuo_failover_advisory(
        session={"provider": HAILUO_BROWSER_ROUTER_KEY},
        execution_runtime={"provider_resolved": HAILUO_BROWSER_ROUTER_KEY},
        outcome="CANCELLED",
        failure_code="OPERATIONS_CANCELLED",
        project_root=root,
    )
    results.append(_pass("cancelled_no_failover_recommended", advisory_cancel.get("failover_recommended") is False))
    results.append(_pass("cancelled_no_failover_allowed", advisory_cancel.get("failover_allowed") is False))
    results.append(_pass("cancelled_reason_operator", advisory_cancel.get("reason") == REASON_OPERATOR_CANCELLED))

    with tempfile.TemporaryDirectory() as tmp:
        partial_path = Path(tmp) / "clip_01.mp4"
        partial_path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 10))
        record = finalize_download_artifact(
            partial_path,
            mode=MODE_BROWSER,
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            clip_index=1,
            partial=True,
            source_url="https://cdn.test/hailuo.mp4",
        )
        runtime_partial = {
            "provider_resolved": HAILUO_BROWSER_ROUTER_KEY,
            "operations": {
                "cancellation": {
                    "partial_paths": [str(partial_path)],
                    "clip_results": [record],
                }
            },
            "provider_clip_results": [record],
        }
        advisory_partial = build_hailuo_failover_advisory(
            session={"provider": HAILUO_BROWSER_ROUTER_KEY},
            execution_runtime=runtime_partial,
            outcome="FAILED",
            failure_code="DOWNLOAD_FAILED",
            project_root=root,
            planner=planner,
            selection_engine=selector,
        )
        results.append(_pass("partial_artifacts_present", advisory_partial.get("partial_artifacts_present") is True))
        results.append(
            _pass(
                "partial_not_reusable_by_default",
                advisory_partial.get("partial_artifacts_safe_to_reuse") is False,
            )
        )
        results.append(_pass("partial_paths_recorded", len(advisory_partial.get("partial_paths") or []) >= 1))
        results.append(_pass("partial_file_not_deleted", partial_path.exists()))

    advisory_unsupported = build_hailuo_failover_advisory(
        session={"provider": HAILUO_BROWSER_ROUTER_KEY},
        execution_runtime={
            "provider_resolved": HAILUO_BROWSER_ROUTER_KEY,
            "prompt_bundle": {"capability": "image_to_video"},
        },
        outcome="FAILED",
        failure_code="CAPABILITY_RUNTIME_UNSUPPORTED",
        project_root=root,
        planner=planner,
        selection_engine=selector,
    )
    results.append(_pass("unsupported_blocks_failover", advisory_unsupported.get("failover_allowed") is False))
    results.append(
        _pass(
            "unsupported_blocked_reason",
            advisory_unsupported.get("blocked_reason") == "capability_unsupported",
        )
    )

    advisory_disabled = build_hailuo_failover_advisory(
        session={"provider": HAILUO_BROWSER_ROUTER_KEY},
        execution_runtime={"provider_resolved": HAILUO_BROWSER_ROUTER_KEY},
        outcome="FAILED",
        failure_code="HAILUO_BROWSER_DISABLED",
        project_root=root,
        planner=planner,
        selection_engine=selector,
    )
    results.append(_pass("provider_disabled_blocks_failover", advisory_disabled.get("failover_allowed") is False))

    plan = planner.plan_failover(CAPABILITY_TEXT_TO_VIDEO, preferred_provider=HAILUO_BROWSER_ROUTER_KEY)
    has_cost_warning = any("cost unknown" in item.lower() for item in plan.warnings)
    advisory_cost = build_hailuo_failover_advisory(
        session={"provider": HAILUO_BROWSER_ROUTER_KEY},
        execution_runtime={"provider_resolved": HAILUO_BROWSER_ROUTER_KEY},
        outcome="FAILED",
        failure_code="PROVIDER_RUNTIME_ERROR",
        project_root=root,
        planner=planner,
        selection_engine=selector,
    )
    results.append(
        _pass(
            "unknown_cost_warning",
            has_cost_warning or bool(advisory_cost.get("cost_warning")),
            advisory_cost.get("cost_warning") or "",
        )
    )

    results.append(_pass("is_hailuo_provider_browser", is_hailuo_provider("hailuo_browser")))
    results.append(_pass("is_hailuo_provider_runway_false", not is_hailuo_provider("runway_browser")))

    fail_session_id = "exec_11fe_fail_advisory"
    fail_session = _hailuo_session(root, fail_session_id)
    store.save_session(fail_session, overwrite=True)
    dispatch_calls = {"n": 0}

    def _fail_router(prompts, *, provider_override=None, cancel_check=None):
        dispatch_calls["n"] += 1
        raise RuntimeError("mock hailuo provider timeout")

    with patch.object(VideoProviderRouter, "generate_clips", side_effect=_fail_router):
        engine.dispatch_by_id(
            fail_session_id,
            actor="validate",
            policy=RuntimePolicy(require_queue_fingerprint=False, require_readiness=False),
        )

    final_failed = store.load_session(fail_session_id)
    ops_failed = (final_failed.get("execution_runtime") or {}).get("operations") or {}
    advisory_ops = ops_failed.get("failover_advisory") or {}
    results.append(_pass("runtime_failed_attached_advisory", bool(advisory_ops)))
    results.append(_pass("runtime_failed_state", final_failed.get("state") == "FAILED"))
    results.append(_pass("runtime_advisory_hailuo_version", advisory_ops.get("advisory_version") == "11f_e_v1"))
    results.append(_pass("no_second_dispatch", dispatch_calls["n"] == 1))
    results.append(_pass("no_requeue_action", ops_failed.get("requeue_requested") is not True))
    results.append(_pass("no_retry_action", ops_failed.get("retry_requested") is not True))

    cancel_session_id = "exec_11fe_cancel_advisory"
    cancel_session = _hailuo_session(root, cancel_session_id)
    store.save_session(cancel_session, overwrite=True)

    with patch.object(
        VideoProviderRouter,
        "generate_clips",
        side_effect=HailuoCancelledError("cancel", partial_paths=[]),
    ):
        engine.dispatch_by_id(
            cancel_session_id,
            actor="validate",
            policy=RuntimePolicy(require_queue_fingerprint=False, require_readiness=False),
        )

    final_cancel = store.load_session(cancel_session_id)
    advisory_cancel_ops = ((final_cancel.get("execution_runtime") or {}).get("operations") or {}).get(
        "failover_advisory"
    ) or {}
    results.append(_pass("runtime_cancel_attached_advisory", bool(advisory_cancel_ops)))
    results.append(_pass("runtime_cancel_no_recommend", advisory_cancel_ops.get("failover_recommended") is False))
    results.append(_pass("runtime_cancel_state", final_cancel.get("state") == "CANCELLED"))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
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
