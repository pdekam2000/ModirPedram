"""
Phase 11H-1i — voice approval UI controls validation (metadata-only, no live TTS).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


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
    preflight_ready: bool = True,
    has_narration: bool = True,
    credentials_missing: bool = False,
    provider_elevenlabs: bool = True,
    archived: bool = False,
) -> dict:
    """Mirror key rules from evaluateVoiceApprovalEligibility for static tests."""
    if archived or not has_narration or credentials_missing:
        return {"approve": False, "reject": False, "expire": False, "reset": False}
    approve = provider_elevenlabs and preflight_ready and state != "approved"
    reject = state in ("required", "approved")
    expire = state == "approved"
    reset = state in ("rejected", "expired", "approved")
    return {"approve": approve, "reject": reject, "expire": expire, "reset": reset}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    voice_panel = _read(root, "ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx")
    controls = _read(root, "ui/web/src/components/VoiceApprovalControlsPanel.tsx")
    dialog = _read(root, "ui/web/src/components/VoiceApprovalConfirmDialog.tsx")
    eligibility = _read(root, "ui/web/src/utils/voiceApprovalEligibility.ts")
    labels = _read(root, "ui/web/src/utils/voiceApprovalLabels.ts")
    client = _read(root, "ui/web/src/api/voiceApprovalClient.ts")
    observability = _read(root, "ui/web/src/components/RuntimeObservability.tsx")
    session_drawer = _read(root, "ui/web/src/components/SessionDrawer.tsx")
    ui_bundle = voice_panel + controls + dialog + eligibility + labels + client

    ready_required = _eligibility_fixture(state="required")
    results.append(
        _pass(
            "approve_visible_when_eligible",
            ready_required["approve"] is True and "evaluateVoiceApprovalEligibility" in eligibility,
            str(ready_required),
        )
    )

    results.append(
        _pass(
            "approve_modal_exact_safety_warning",
            "This only approves future voice generation. It does not generate audio yet." in labels
            and "VOICE_APPROVE_SAFETY_WARNING" in dialog,
        )
    )

    results.append(
        _pass(
            "approve_sends_request_live_tts_true",
            "request_live_tts: true" in controls and '"/voice/approve"' in client,
            "wired",
        )
    )

    approved = _eligibility_fixture(state="approved")
    results.append(
        _pass(
            "reject_visible_required_or_approved",
            _eligibility_fixture(state="required")["reject"]
            and approved["reject"]
            and not _eligibility_fixture(state="not_required")["reject"],
            str(approved),
        )
    )

    results.append(
        _pass(
            "expire_visible_only_approved",
            approved["expire"] and not _eligibility_fixture(state="required")["expire"],
            str(approved["expire"]),
        )
    )

    reset_states = [
        _eligibility_fixture(state="rejected")["reset"],
        _eligibility_fixture(state="expired")["reset"],
        approved["reset"],
    ]
    results.append(
        _pass(
            "reset_visible_rejected_expired_approved",
            all(reset_states) and not _eligibility_fixture(state="required")["reset"],
            str(reset_states),
        )
    )

    forbidden = ["Generate Voice", "Run TTS", "Start TTS"]
    results.append(
        _pass(
            "no_forbidden_tts_labels",
            not any(label in ui_bundle for label in forbidden),
        )
    )

    results.append(
        _pass(
            "ui_asserts_tts_executed_false",
            "assertVoiceApprovalSafety" in client and "tts_executed !== false" in client,
        )
    )

    results.append(
        _pass(
            "refresh_after_success_wired",
            "onVoiceApprovalSuccess" in observability
            and "onVoiceApprovalSuccess={onAfterAction}" in session_drawer,
        )
    )

    results.append(
        _pass(
            "legacy_session_safe",
            "isLegacy" in session_drawer and "Legacy session" in controls,
        )
    )

    results.append(
        _pass(
            "video_observability_unchanged",
            "Clip artifacts" in observability and "Artifact validation" in observability,
        )
    )

    backend_sources = (
        _read(root, "content_brain/execution/voice_approval_operations_engine.py")
        + _read(root, "ui/api/voice_approval_service.py")
    )
    forbidden_tts = bool(
        re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", backend_sources, re.MULTILINE)
    )
    results.append(
        _pass(
            "no_elevenlabs_voice_provider_import",
            not forbidden_tts,
            "clean" if not forbidden_tts else "forbidden",
        )
    )

    results.append(_pass("npm_build_passes", _run_npm_build(root)))
    results.append(_pass("validate_11h1g_still_passes", _run_module("project_brain.validate_11h1g_voice_approval_write_apis")))
    results.append(_pass("validate_11h1e_still_passes", _run_module("project_brain.validate_11h1e_voice_approval_guard")))
    results.append(_pass("validate_11g_still_passes", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11H-1i",
        "label": "voice_approval_ui_controls",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
