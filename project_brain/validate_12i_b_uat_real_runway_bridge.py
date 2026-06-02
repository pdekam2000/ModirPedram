"""
Phase 12I-B — UAT real Runway execution bridge validation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from content_brain.execution.uat_real_video_bridge import (
    apply_uat_supervised_video_dispatch_readiness,
    uat_supervised_real_runway_requested,
)
from content_brain.execution.uat_runtime_profile import UatRuntimeConfig


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    bridge_path = root / "content_brain" / "execution" / "uat_real_video_bridge.py"
    engine_path = root / "content_brain" / "execution" / "uat_runtime_engine.py"
    profile_path = root / "content_brain" / "execution" / "uat_runtime_profile.py"

    results.append(_pass("bridge_module_exists", bridge_path.is_file(), str(bridge_path)))

    engine_src = engine_path.read_text(encoding="utf-8")
    results.append(_pass("engine_imports_bridge", "uat_real_video_bridge" in engine_src))
    results.append(
        _pass(
            "engine_uses_queue_prepare",
            "uat_runway_queue_and_dispatch_prepare" in engine_src,
        )
    )
    results.append(
        _pass(
            "placeholder_blocked_for_supervised",
            "UAT_PLACEHOLDER_BLOCKED" in engine_src and "supervised_runway" in engine_src,
        )
    )

    tree = ast.parse(engine_src)
    run_video_src = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_video_stage":
            run_video_src = ast.get_source_segment(engine_src, node) or ""
            break
    results.append(
        _pass(
            "mock_fallback_after_supervised_guard",
            "supervised_runway" in run_video_src and "_apply_mock_video_artifacts" in run_video_src,
            "mock fallback remains for non-supervised paths",
        )
    )

    profile_src = profile_path.read_text(encoding="utf-8")
    results.append(_pass("confirm_real_video_in_profile", "confirm_real_video" in profile_src))

    cfg_mock = UatRuntimeConfig(topic="t", video_provider="mock").normalized()
    cfg_runway_off = UatRuntimeConfig(topic="t", video_provider="runway_browser", confirm_real_video=False).normalized()
    cfg_runway_on = UatRuntimeConfig(topic="t", video_provider="runway_browser", confirm_real_video=True).normalized()
    results.append(
        _pass(
            "supervised_flag_mock",
            not uat_supervised_real_runway_requested(cfg_mock, mock_paid_providers=False),
        )
    )
    results.append(
        _pass(
            "supervised_flag_runway_off",
            not uat_supervised_real_runway_requested(cfg_runway_off, mock_paid_providers=False),
        )
    )
    results.append(
        _pass(
            "supervised_flag_runway_on",
            uat_supervised_real_runway_requested(cfg_runway_on, mock_paid_providers=False),
        )
    )

    from content_brain.execution.simulation_report_builder import SimulationReportBuilder

    session = {
        "execution_session_id": "exec_uat_test",
        "state": "REJECTED",
        "approval_decision": {
            "status": "REJECTED",
            "evaluated_by": {"engine": "test"},
        },
        "budget_decision": {
            "budget_allowed": True,
            "budget_status": "WITHIN_LIMIT",
            "evaluated_by": {"engine": "test"},
        },
        "story_quality": {"composite_score": 80, "decision": "REVISE", "score": 80},
        "provider_selection": {"primary_provider": "runway_browser"},
        "provider": "runway_browser",
        "brief_snapshot": {
            "video_format_plan": {"clip_count": 2, "clip_duration_seconds": 10},
            "run_context": {"story_intelligence": {"schema_director_shots": [{"clip_number": 1, "prompt": "test"}]}},
        },
        "session_uuid": "00000000-0000-4000-8000-000000000001",
        "brief_id": "brief_x",
        "execution_confidence_score": 75.0,
    }
    session = SimulationReportBuilder().enrich_session(session)
    patched = apply_uat_supervised_video_dispatch_readiness(session)
    readiness = patched.get("execution_readiness") or {}
    results.append(
        _pass(
            "readiness_override_eligible",
            patched.get("approval_decision", {}).get("status") == "APPROVED_FOR_EXECUTION"
            and readiness.get("decision") in {"READY", "READY_WITH_WARNINGS"},
            str(readiness.get("decision")),
        )
    )

    schema_path = root / "ui" / "api" / "schemas" / "uat_runtime.py"
    results.append(
        _pass("api_schema_confirm_real_video", "confirm_real_video" in schema_path.read_text(encoding="utf-8"))
    )

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "12I-B",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


if __name__ == "__main__":
    import json
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    print(json.dumps(run_matrix(root), indent=2))
