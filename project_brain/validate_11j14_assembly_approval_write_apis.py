"""
Phase 11J-14 — assembly approval write APIs backend validation (no FFmpeg).
"""

from __future__ import annotations

import ast
import json
import tempfile
from copy import deepcopy
from pathlib import Path

from content_brain.execution.assembly_approval_action_policy import CODE_DRY_RUN_NOT_COMPLETED
from content_brain.execution.assembly_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_APPROVAL_REJECTED,
    BLOCK_PLAN_NOT_READY,
    BLOCK_REAL_ASSEMBLY_NOT_REQUESTED,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_REJECTED,
)
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.assembly_approval_operations_engine import AssemblyApprovalOperationsEngine
from project_brain.validate_11j8_assembly_runtime_api import _build_session as _build_ready_session
from ui.api.assembly_approval_service import AssemblyApprovalService
from ui.api.assembly_run_service import AssemblyRunService

SCAN_PATHS = (
    Path("content_brain/execution/assembly_approval_action_policy.py"),
    Path("content_brain/execution/assembly_approval_operations_engine.py"),
    Path("ui/api/assembly_approval_service.py"),
)


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _build_session(
    tmp: Path,
    *,
    session_id: str = "exec_11j14",
) -> dict:
    session = _build_ready_session(tmp, session_id=session_id)
    cr = session["execution_runtime"]["category_runtime"]
    cr[CATEGORY_VIDEO]["state"] = "COMPLETED"
    cr[CATEGORY_VIDEO]["provider"] = "hailuo_browser"
    cr[CATEGORY_VIDEO]["status"] = "completed"
    cr[CATEGORY_VIDEO]["started_at"] = "2026-05-31 00:00:00"
    cr[CATEGORY_VOICE]["state"] = "COMPLETED"
    cr[CATEGORY_VOICE]["provider"] = "elevenlabs"
    cr[CATEGORY_VOICE]["status"] = "completed"
    cr[CATEGORY_SUBTITLE_GENERATION]["status"] = "completed"
    return session


def _upstream_slots(session: dict) -> dict:
    cr = (session.get("execution_runtime") or {}).get("category_runtime") or {}
    return {
        CATEGORY_VIDEO: deepcopy(cr.get(CATEGORY_VIDEO)),
        CATEGORY_VOICE: deepcopy(cr.get(CATEGORY_VOICE)),
        CATEGORY_SUBTITLE_GENERATION: deepcopy(cr.get(CATEGORY_SUBTITLE_GENERATION)),
    }


def _audit_events(session: dict) -> list[dict]:
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    events = operations.get("assembly_approval_audit") or []
    return events if isinstance(events, list) else []


def _invokes_ffmpeg(module_path: Path) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                low = alias.name.lower()
                if low in {"subprocess", "ffmpeg"} or low.startswith("ffmpeg."):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            low = node.module.lower()
            if low in {"subprocess", "ffmpeg"} or low.startswith("ffmpeg."):
                return True
    return False


def _imports_full_video_pipeline(module_path: Path) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "full_video_pipeline" in alias.name:
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and "full_video_pipeline" in node.module:
            return True
    return False


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = True) -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    engine = AssemblyApprovalOperationsEngine(store, project_root=root)
    service = AssemblyApprovalService(store)
    run_service = AssemblyRunService(store)
    results: list[dict] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1. Approve without READY plan blocks.
        sid_not_ready = "exec_11j14_not_ready"
        session_not_ready = _build_session(tmp / "art_not_ready", session_id=sid_not_ready)
        session_not_ready["execution_runtime"]["artifacts_by_category"][CATEGORY_VOICE] = []
        cr_not_ready = session_not_ready["execution_runtime"]["category_runtime"]
        cr_not_ready[CATEGORY_VOICE]["voice_manifest_path"] = str(tmp / "art_not_ready" / "missing_voice_manifest.json")
        store.save_session(session_not_ready, overwrite=True)
        blocked_plan = engine.approve(sid_not_ready, request_real_assembly=True, approved_by="test")
        results.append(
            _pass(
                "approve_without_ready_plan_blocks",
                not blocked_plan.success and BLOCK_PLAN_NOT_READY in (blocked_plan.reject_reasons or []),
                str(blocked_plan.reject_reasons),
            )
        )

        # 2. Approve without dry-run completed blocks.
        sid_no_dry = "exec_11j14_no_dry"
        session_no_dry = _build_session(tmp / "art_no_dry", session_id=sid_no_dry)
        store.save_session(session_no_dry, overwrite=True)
        blocked_dry = engine.approve(sid_no_dry, request_real_assembly=True, approved_by="test")
        results.append(
            _pass(
                "approve_without_dry_run_completed_blocks",
                not blocked_dry.success
                and CODE_DRY_RUN_NOT_COMPLETED in (blocked_dry.reject_reasons or []),
                str(blocked_dry.reject_reasons),
            )
        )

        # 3. Approve without request_real_assembly blocks.
        sid_no_req = "exec_11j14_no_req"
        session_no_req = _build_session(tmp / "art_no_req", session_id=sid_no_req)
        store.save_session(session_no_req, overwrite=True)
        run_service.run(sid_no_req, dry_run=True, triggered_by="validator")
        blocked_req = engine.approve(sid_no_req, request_real_assembly=False, approved_by="test")
        results.append(
            _pass(
                "approve_without_request_real_assembly_blocks",
                not blocked_req.success
                and BLOCK_REAL_ASSEMBLY_NOT_REQUESTED in (blocked_req.reject_reasons or []),
                str(blocked_req.reject_reasons),
            )
        )

        # 4. Approve with READY plan succeeds.
        sid_ok = "exec_11j14_approve_ok"
        session_ok = _build_session(tmp / "art_ok", session_id=sid_ok)
        store.save_session(session_ok, overwrite=True)
        run_service.run(sid_ok, dry_run=True, triggered_by="validator")
        approved = engine.approve(
            sid_ok,
            request_real_assembly=True,
            reason="Validator approval",
            approved_by="validator",
            ttl_minutes=60,
        )
        approval = _dict(_dict(approved.assembly_slot).get("approval"))
        results.append(
            _pass(
                "approve_with_ready_plan_succeeds",
                approved.success
                and approval.get("approval_state") == STATE_APPROVED
                and approved.real_assembly_executed is False,
                str(approval.get("approval_state")),
            )
        )

        # 5. Reject sets rejected state.
        sid_reject = "exec_11j14_reject"
        session_reject = _build_session(tmp / "art_reject", session_id=sid_reject)
        store.save_session(session_reject, overwrite=True)
        run_service.run(sid_reject, dry_run=True, triggered_by="validator")
        engine.approve(sid_reject, request_real_assembly=True, approved_by="test")
        rejected = engine.reject(sid_reject, reason="Rejected in test", rejected_by="validator")
        reject_approval = _dict(_dict(rejected.assembly_slot).get("approval"))
        results.append(
            _pass(
                "reject_sets_rejected_state",
                rejected.success
                and reject_approval.get("approval_state") == STATE_REJECTED
                and BLOCK_APPROVAL_REJECTED in (reject_approval.get("assembly_blocked_reasons") or []),
                str(reject_approval.get("approval_state")),
            )
        )

        # 6. Expire sets expired state.
        sid_expire = "exec_11j14_expire"
        session_expire = _build_session(tmp / "art_expire", session_id=sid_expire)
        store.save_session(session_expire, overwrite=True)
        run_service.run(sid_expire, dry_run=True, triggered_by="validator")
        engine.approve(sid_expire, request_real_assembly=True, approved_by="test")
        expired = engine.expire(sid_expire, reason="Expired in test", expired_by="validator")
        expire_approval = _dict(_dict(expired.assembly_slot).get("approval"))
        results.append(
            _pass(
                "expire_sets_expired_state",
                expired.success
                and expire_approval.get("approval_state") == STATE_EXPIRED
                and BLOCK_APPROVAL_EXPIRED in (expire_approval.get("assembly_blocked_reasons") or []),
                str(expire_approval.get("approval_state")),
            )
        )

        # 7. Reset clears grant fields.
        sid_reset = "exec_11j14_reset"
        session_reset = _build_session(tmp / "art_reset", session_id=sid_reset)
        store.save_session(session_reset, overwrite=True)
        run_service.run(sid_reset, dry_run=True, triggered_by="validator")
        engine.approve(sid_reset, request_real_assembly=True, approved_by="test")
        reset = engine.reset_approval(sid_reset, reset_by="validator")
        reset_approval = _dict(_dict(reset.assembly_slot).get("approval"))
        results.append(
            _pass(
                "reset_clears_grant_fields",
                reset.success
                and reset_approval.get("approved_by") is None
                and reset_approval.get("approved_at") is None
                and reset_approval.get("approval_expires_at") is None,
                str(reset_approval.get("approval_state")),
            )
        )

        # 8. Audit trail appended for every action.
        sid_audit = "exec_11j14_audit"
        session_audit = _build_session(tmp / "art_audit", session_id=sid_audit)
        store.save_session(session_audit, overwrite=True)
        run_service.run(sid_audit, dry_run=True, triggered_by="validator")
        service.approve(sid_audit, request_real_assembly=True, approved_by="audit_test")
        loaded_audit = store.load_session(sid_audit)
        events = _audit_events(loaded_audit)
        results.append(
            _pass(
                "audit_trail_appended_for_every_action",
                len(events) >= 1
                and events[-1].get("event_type") == "assembly_approval_approved"
                and events[-1].get("real_assembly_executed") is False,
                str(len(events)),
            )
        )

        # 9–11. Upstream slots unchanged.
        sid_upstream = "exec_11j14_upstream"
        session_upstream = _build_session(tmp / "art_upstream", session_id=sid_upstream)
        before = _upstream_slots(session_upstream)
        store.save_session(session_upstream, overwrite=True)
        run_service.run(sid_upstream, dry_run=True, triggered_by="validator")
        engine.approve(sid_upstream, request_real_assembly=True, approved_by="test")
        loaded_upstream = store.load_session(sid_upstream)
        after = _upstream_slots(loaded_upstream)
        critical_keys = ("state", "provider", "status", "started_at")
        video_ok = all(
            _dict(after[CATEGORY_VIDEO]).get(k) == _dict(before[CATEGORY_VIDEO]).get(k)
            for k in critical_keys
        )
        voice_ok = all(
            _dict(after[CATEGORY_VOICE]).get(k) == _dict(before[CATEGORY_VOICE]).get(k)
            for k in critical_keys
        )
        subtitle_ok = all(
            _dict(after[CATEGORY_SUBTITLE_GENERATION]).get(k) == _dict(before[CATEGORY_SUBTITLE_GENERATION]).get(k)
            for k in ("status",)
        )
        results.append(_pass("assembly_approval_does_not_mutate_video_slot", video_ok, str(after[CATEGORY_VIDEO].get("state"))))
        results.append(_pass("assembly_approval_does_not_mutate_voice_slot", voice_ok, str(after[CATEGORY_VOICE].get("state"))))
        results.append(
            _pass(
                "assembly_approval_does_not_mutate_subtitle_slot",
                subtitle_ok,
                str(_dict(after[CATEGORY_SUBTITLE_GENERATION]).get("status")),
            )
        )

        # 12. Response always has real_assembly_executed=false.
        wrapped = service.approve(
            "exec_11j14_approve_ok",
            request_real_assembly=True,
            approved_by="wrap_test",
        )
        results.append(
            _pass(
                "response_always_real_assembly_executed_false",
                wrapped.get("real_assembly_executed") is False,
                str(wrapped.get("real_assembly_executed")),
            )
        )

        # 14. No FINAL_PUBLISH_READY.mp4 created.
        mp4_candidates = list(tmp.rglob("FINAL_PUBLISH_READY.mp4"))
        results.append(
            _pass(
                "no_final_publish_ready_mp4_created",
                len(mp4_candidates) == 0,
                str(len(mp4_candidates)),
            )
        )

    # 13. No FFmpeg import/call.
    ffmpeg_free = all(not _invokes_ffmpeg(root / path) for path in SCAN_PATHS)
    no_pipeline = all(not _imports_full_video_pipeline(root / path) for path in SCAN_PATHS)
    results.append(
        _pass(
            "no_ffmpeg_import_or_call",
            ffmpeg_free and no_pipeline,
            ",".join(str(p) for p in SCAN_PATHS),
        )
    )

    if include_regressions:
        from project_brain.validate_11j12_assembly_approval_guard import run_matrix as run_11j12
        from project_brain.validate_11j8_assembly_runtime_api import run_matrix as run_11j8
        from project_brain.validate_11h2d_live_engine_wiring_no_real_execution import run_matrix as run_11h2d

        results.append(
            _pass(
                "validate_11j12_regression",
                run_11j12(".", include_regressions=False)["all_pass"],
            )
        )
        results.append(
            _pass(
                "validate_11j8_regression",
                run_11j8(".", include_regressions=False)["all_pass"],
            )
        )
        results.append(_pass("validate_11h2d_regression", run_11h2d(".")["all_pass"]))

    passed = sum(1 for item in results if item["pass"])
    total = len(results)
    return {
        "phase": "11J-14",
        "passed": passed,
        "total": total,
        "all_pass": passed == total,
        "results": results,
    }


def main() -> int:
    report = run_matrix(".")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
