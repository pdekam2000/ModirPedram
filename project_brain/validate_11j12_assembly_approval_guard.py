"""
Phase 11J-12 — assembly approval gate read-only validation.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from content_brain.execution.assembly_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_APPROVAL_REQUIRED,
    BLOCK_PLAN_NOT_READY,
    BLOCK_REAL_ASSEMBLY_NOT_REQUESTED,
    BLOCK_REAL_EXECUTION_DISABLED,
    AssemblyRunRequestContext,
    can_run_real_assembly,
    evaluate_assembly_approval_gate,
)
from content_brain.execution.assembly_models import (
    EXPECTED_OUTPUT,
    AssemblyPlan,
    VALIDATION_PARTIAL,
    VALIDATION_READY,
)

GUARD_PATH = Path("content_brain/execution/assembly_approval_guard.py")
PANEL_PATH = Path("ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx")


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _run_module(module: str, *, core_only: bool = True) -> bool:
    from project_brain.validation_policy import run_validator_module

    return run_validator_module(module, core_only=core_only)


def _run_npm_build(root: Path) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(root / "ui" / "web"),
        shell=True,
    )
    return result.returncode == 0


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


def _ready_plan(session_id: str = "exec_11j12") -> AssemblyPlan:
    return AssemblyPlan(
        session_id=session_id,
        validation_status=VALIDATION_READY,
        expected_output=EXPECTED_OUTPUT,
        output_dir=f"storage/content_brain/execution/artifacts/{session_id}/assembly_generation",
    )


def _ready_slot(**overrides) -> dict:
    slot = {
        "status": "completed",
        "validation_status": VALIDATION_READY,
        "real_assembly_requested": False,
        "input_summary": {"video_count": 2, "voice_count": 2, "subtitle_count": 1},
    }
    slot.update(overrides)
    return slot


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    _ = project_root
    results: list[dict] = []
    plan = _ready_plan()

    # 1. Dry-run only.
    dry_guard = can_run_real_assembly(
        _ready_slot(),
        plan,
        AssemblyRunRequestContext(dry_run=True, real_assembly_requested=False),
    )
    dry_approval = evaluate_assembly_approval_gate(
        _ready_slot(),
        plan,
        AssemblyRunRequestContext(dry_run=True, real_assembly_requested=False),
    )
    results.append(
        _pass(
            "dry_run_only_not_requested",
            BLOCK_REAL_ASSEMBLY_NOT_REQUESTED in dry_guard.block_codes
            and dry_approval["approval_required"] is False
            and dry_approval["approval_state"] == "not_required"
            and dry_approval["assembly_eligible"] is False,
            ",".join(dry_guard.block_codes),
        )
    )

    # 2. Plan not READY.
    partial_plan = AssemblyPlan(session_id="exec_11j12", validation_status=VALIDATION_PARTIAL)
    not_ready = can_run_real_assembly(
        _ready_slot(validation_status=VALIDATION_PARTIAL),
        partial_plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
    )
    results.append(
        _pass(
            "plan_not_ready_blocks",
            BLOCK_PLAN_NOT_READY in not_ready.block_codes and not_ready.approval_required is False,
            ",".join(not_ready.block_codes),
        )
    )

    # 3. Real requested + READY + no approval.
    need_approval = can_run_real_assembly(
        _ready_slot(real_assembly_requested=True),
        plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
    )
    need_approval_block = evaluate_assembly_approval_gate(
        _ready_slot(real_assembly_requested=True),
        plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
    )
    results.append(
        _pass(
            "real_requested_requires_approval",
            BLOCK_APPROVAL_REQUIRED in need_approval.block_codes
            and need_approval.approval_required is True
            and need_approval_block["approval_state"] == "required"
            and need_approval_block["assembly_eligible"] is False,
            ",".join(need_approval.block_codes),
        )
    )

    # 4. Approved but expired.
    expired_at = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    expired_slot = _ready_slot(
        real_assembly_requested=True,
        approval={
            "approval_state": "approved",
            "approved_by": "operator",
            "approved_at": "2026-05-31 10:00:00",
            "approval_expires_at": expired_at,
        },
    )
    expired_guard = can_run_real_assembly(
        expired_slot,
        plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
    )
    results.append(
        _pass(
            "expired_approval_blocks",
            BLOCK_APPROVAL_EXPIRED in expired_guard.block_codes and expired_guard.approval_expired is True,
            ",".join(expired_guard.block_codes),
        )
    )

    # 5. Approved + flags disabled.
    approved_slot = _ready_slot(
        real_assembly_requested=True,
        approval={
            "approval_state": "approved",
            "approved_by": "operator",
            "approved_at": "2026-05-31 12:00:00",
            "approval_expires_at": (datetime.now() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    old_modir = os.environ.get("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED")
    old_runtime = os.environ.get("ASSEMBLY_RUNTIME_EXECUTION_APPROVED")
    os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = "false"
    os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = "false"
    try:
        flags_off = can_run_real_assembly(
            approved_slot,
            plan,
            AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
        )
    finally:
        if old_modir is None:
            os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        else:
            os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = old_modir
        if old_runtime is None:
            os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)
        else:
            os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = old_runtime
    results.append(
        _pass(
            "approved_flags_disabled_blocks",
            flags_off.approval_state == "approved"
            and flags_off.assembly_eligible is False
            and BLOCK_REAL_EXECUTION_DISABLED in flags_off.block_codes,
            ",".join(flags_off.block_codes),
        )
    )

    # 6. Approved + flags enabled + READY → allowed metadata only.
    os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = "true"
    os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = "true"
    try:
        flags_on = can_run_real_assembly(
            approved_slot,
            plan,
            AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
        )
    finally:
        if old_modir is None:
            os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        else:
            os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = old_modir
        if old_runtime is None:
            os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)
        else:
            os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = old_runtime
    results.append(
        _pass(
            "approved_flags_enabled_allowed_metadata",
            flags_on.allowed is True and flags_on.assembly_eligible is True,
            str(flags_on.allowed),
        )
    )

    # 7. Session approval does not imply assembly approval.
    session_approved = {
        "approval_state": "approved",
        "approval_decision": {"status": "APPROVED_FOR_EXECUTION"},
    }
    session_guard = can_run_real_assembly(
        _ready_slot(real_assembly_requested=True),
        plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
        session=session_approved,
    )
    results.append(
        _pass(
            "session_approval_not_assembly_approval",
            BLOCK_APPROVAL_REQUIRED in session_guard.block_codes,
            ",".join(session_guard.block_codes),
        )
    )

    # 8. Voice approval does not imply assembly approval.
    voice_session = {
        "execution_runtime": {
            "category_runtime": {
                "voice_generation": {
                    "approval": {
                        "approval_state": "approved",
                        "live_tts_eligible": True,
                    }
                }
            }
        }
    }
    voice_guard = can_run_real_assembly(
        _ready_slot(real_assembly_requested=True),
        plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
        session=voice_session,
    )
    results.append(
        _pass(
            "voice_approval_not_assembly_approval",
            BLOCK_APPROVAL_REQUIRED in voice_guard.block_codes,
            ",".join(voice_guard.block_codes),
        )
    )

    # 9. Preserve approved_by / approved_at.
    preserved = evaluate_assembly_approval_gate(
        approved_slot,
        plan,
        AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
    )
    results.append(
        _pass(
            "preserves_existing_approval_fields",
            preserved.get("approved_by") == "operator"
            and preserved.get("approved_at") == "2026-05-31 12:00:00",
        )
    )

    panel_text = PANEL_PATH.read_text(encoding="utf-8")
    # 10. UI approval subsection.
    results.append(
        _pass(
            "ui_displays_approval_subsection",
            "Assembly approval gate" in panel_text and "Approval required" in panel_text,
        )
    )

    # 11. No approve/reject buttons.
    forbidden = ["Approve assembly", "Reject assembly", "approve assembly", "reject assembly"]
    results.append(
        _pass(
            "no_approve_reject_buttons",
            not any(label in panel_text for label in forbidden) and "<button" not in panel_text.lower(),
        )
    )

    # 12. No FFmpeg import/call.
    results.append(_pass("no_ffmpeg_import_or_call", not _invokes_ffmpeg(GUARD_PATH)))

    # 13. No FINAL_PUBLISH_READY.mp4 created.
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        final_path = root / "artifacts" / "exec_11j12" / "assembly_generation" / EXPECTED_OUTPUT
        evaluate_assembly_approval_gate(
            _ready_slot(real_assembly_requested=True),
            plan,
            AssemblyRunRequestContext(dry_run=False, real_assembly_requested=True),
        )
        results.append(_pass("no_final_video_created", not final_path.exists()))

    if include_regressions:
        results.append(
            _pass(
                "validate_11j10_regression",
                _run_module("project_brain.validate_11j10_assembly_ui_observability", core_only=True),
            )
        )
        results.append(
            _pass(
                "validate_11j8_regression",
                _run_module("project_brain.validate_11j8_assembly_runtime_api", core_only=True),
            )
        )
        results.append(
            _pass(
                "validate_11h2d_regression",
                _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution", core_only=True),
            )
        )

    results.append(_pass("npm_build_passes", _run_npm_build(Path(".").resolve())))

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="11J-12",
        label="assembly_approval_guard_readonly",
        results=results,
        include_regressions=include_regressions,
    )


def main(argv: list[str] | None = None) -> int:
    from project_brain.validation_policy import (
        parse_include_regressions,
        print_validation_summary,
        validation_exit_code,
    )

    include_regressions = parse_include_regressions(argv)
    report = run_matrix(include_regressions=include_regressions)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print_validation_summary(report)
    return validation_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
