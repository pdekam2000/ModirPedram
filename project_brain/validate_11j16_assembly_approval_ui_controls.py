"""
Phase 11J-16 — assembly approval UI controls validation (metadata-only, no FFmpeg).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    return result.returncode == 0


def _run_npm_build(root: Path) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(root / "ui" / "web"),
        shell=True,
    )
    return result.returncode == 0


def _eligibility_fixture(
    *,
    state: str,
    dry_run_done: bool = True,
    plan_ready: bool = True,
    has_slot: bool = True,
    archived: bool = False,
    running: bool = False,
) -> dict[str, bool]:
    """Mirror key rules from evaluateAssemblyApprovalEligibility for static tests."""
    if archived or not has_slot or running:
        return {"approve": False, "reject": False, "expire": False, "reset": False}
    approve = (
        dry_run_done
        and plan_ready
        and state in ("required", "not_required", "rejected", "expired")
        and state != "approved"
    )
    reject = state in ("required", "approved")
    expire = state == "approved"
    reset = state in ("rejected", "expired", "approved")
    return {"approve": approve, "reject": reject, "expire": expire, "reset": reset}


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = True) -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    assembly_panel = _read(root, "ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx")
    controls = _read(root, "ui/web/src/components/AssemblyApprovalControlsPanel.tsx")
    dialog = _read(root, "ui/web/src/components/AssemblyApprovalConfirmDialog.tsx")
    eligibility = _read(root, "ui/web/src/utils/assemblyApprovalEligibility.ts")
    labels = _read(root, "ui/web/src/utils/assemblyApprovalLabels.ts")
    client = _read(root, "ui/web/src/api/assemblyApprovalClient.ts")
    observability = _read(root, "ui/web/src/components/RuntimeObservability.tsx")
    session_drawer = _read(root, "ui/web/src/components/SessionDrawer.tsx")
    ui_bundle = assembly_panel + controls + dialog + eligibility + labels + client

    results.append(
        _pass(
            "assembly_approval_controls_panel_exists",
            "AssemblyApprovalControlsPanel" in controls and "export function AssemblyApprovalControlsPanel" in controls,
        )
    )

    results.append(
        _pass(
            "assembly_approval_confirm_dialog_exists",
            "AssemblyApprovalConfirmDialog" in dialog and "export function AssemblyApprovalConfirmDialog" in dialog,
        )
    )

    results.append(
        _pass(
            "client_asserts_real_assembly_executed_false",
            "assertAssemblyApprovalSafety" in client and "real_assembly_executed !== false" in client,
        )
    )

    exact_warning = (
        "This only approves future real assembly execution. "
        "It does not run FFmpeg or generate the final video yet."
    )
    results.append(
        _pass(
            "approve_modal_exact_safety_warning",
            exact_warning in labels and "ASSEMBLY_APPROVE_SAFETY_WARNING" in dialog,
        )
    )

    results.append(
        _pass(
            "approve_sends_request_real_assembly_true",
            "request_real_assembly: true" in controls and '"/assembly/approve"' in client,
        )
    )

    results.append(
        _pass(
            "reject_expire_reset_endpoints_wired",
            '"/assembly/reject"' in client
            and '"/assembly/expire"' in client
            and '"/assembly/reset-approval"' in client
            and "postAssemblyReject" in controls
            and "postAssemblyExpire" in controls
            and "postAssemblyResetApproval" in controls,
        )
    )

    ready_required = _eligibility_fixture(state="required")
    results.append(
        _pass(
            "approve_visible_only_when_eligible",
            ready_required["approve"] is True
            and not _eligibility_fixture(state="required", dry_run_done=False)["approve"]
            and not _eligibility_fixture(state="required", plan_ready=False)["approve"]
            and "evaluateAssemblyApprovalEligibility" in eligibility,
            str(ready_required),
        )
    )

    results.append(
        _pass(
            "blocked_reasons_shown_when_unavailable",
            "formatAssemblyBlockedReasons" in controls and "assembly-approval-blocked-note" in controls,
        )
    )

    forbidden = [
        "Run Assembly",
        "Generate Final Video",
        "Export Final Video",
        "Run FFmpeg",
        "Create MP4",
        "Build Final",
    ]
    button_forbidden = []
    for label in forbidden:
        if re.search(rf"<button[^>]*>[^<]*{re.escape(label)}", ui_bundle, re.IGNORECASE):
            button_forbidden.append(label)
    results.append(
        _pass(
            "no_forbidden_labels_on_buttons",
            not button_forbidden,
            ",".join(button_forbidden),
        )
    )

    results.append(
        _pass(
            "no_assembly_run_dry_run_false",
            "dry_run: false" not in ui_bundle and "dry_run=false" not in ui_bundle.lower(),
        )
    )

    ffmpeg_button = bool(re.search(r"<button[^>]*>[^<]*ffmpeg", ui_bundle, re.IGNORECASE))
    results.append(_pass("no_ffmpeg_control_labels", not ffmpeg_button))

    results.append(
        _pass(
            "refresh_callback_after_success",
            "onAssemblyApprovalSuccess" in observability
            and "onAssemblyApprovalSuccess={onAfterAction}" in session_drawer
            and "onAfterAction" in controls,
        )
    )

    if include_regressions:
        from project_brain.validate_11j14_assembly_approval_write_apis import run_matrix as run_11j14
        from project_brain.validate_11j12_assembly_approval_guard import run_matrix as run_11j12
        from project_brain.validate_11j10_assembly_ui_observability import run_matrix as run_11j10
        from project_brain.validate_11h2d_live_engine_wiring_no_real_execution import run_matrix as run_11h2d

        results.append(_pass("validate_11j14_regression", run_11j14(".", include_regressions=False)["all_pass"]))
        results.append(_pass("validate_11j12_regression", run_11j12(".", include_regressions=False)["all_pass"]))
        results.append(_pass("validate_11j10_regression", run_11j10(".", include_regressions=False)["all_pass"]))
        results.append(_pass("validate_11h2d_regression", run_11h2d(".")["all_pass"]))

    results.append(_pass("npm_build_passes", _run_npm_build(root)))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11J-16",
        "label": "assembly_approval_ui_controls",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
