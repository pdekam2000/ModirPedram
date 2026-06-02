"""
Phase 11H-1g — voice approval write APIs backend validation (no live TTS).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_guard import (
    BLOCK_LIVE_TTS_NOT_REQUESTED,
    BLOCK_NO_NARRATION,
    BLOCK_VOICE_APPROVAL_REJECTED,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_REJECTED,
    STATE_REQUIRED,
)
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine
from ui.api.voice_approval_service import VoiceApprovalService


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    return result.returncode == 0


def _session_with_narration(session_id: str) -> dict:
    return {
        "execution_session_id": session_id,
        "state": "COMPLETED",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {"beat_id": "HOOK", "narration": "Narration for voice approval write API test."}
                        ]
                    }
                }
            }
        },
        "execution_runtime": {
            "category_runtime": {
                CATEGORY_VIDEO: {
                    "state": "COMPLETED",
                    "provider": "hailuo_browser",
                    "status": "completed",
                }
            },
            "artifacts_by_category": {},
        },
    }


def _session_no_narration(session_id: str) -> dict:
    return {
        "execution_session_id": session_id,
        "state": "COMPLETED",
        "brief_snapshot": {"run_context": {"story_intelligence": {}}},
        "execution_runtime": {"category_runtime": {}, "artifacts_by_category": {}},
    }


def _write(store: ExecutionSessionStore, session: dict) -> None:
    store.save_session(session, overwrite=True)


def _audit_events(session: dict) -> list[dict]:
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    events = operations.get("voice_approval_audit") or []
    return events if isinstance(events, list) else []


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    engine = VoiceApprovalOperationsEngine(store, project_root=root)
    service = VoiceApprovalService(store)
    results: list[dict] = []

    sid_no_narr = "exec_11h1g_no_narration"
    _write(store, _session_no_narration(sid_no_narr))
    blocked_no_narr = engine.approve(sid_no_narr, request_live_tts=True, approved_by="test")
    results.append(
        _pass(
            "approve_without_narration_blocks",
            not blocked_no_narr.success and BLOCK_NO_NARRATION in (blocked_no_narr.reject_reasons or []),
            str(blocked_no_narr.reject_reasons),
        )
    )

    sid_missing_key = "exec_11h1g_missing_key"
    _write(store, _session_with_narration(sid_missing_key))
    env_without_key = {k: v for k, v in os.environ.items() if k != "ELEVENLABS_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        blocked_key = engine.approve(sid_missing_key, request_live_tts=True, approved_by="test")
    results.append(
        _pass(
            "approve_missing_credentials_blocks",
            not blocked_key.success,
            str(blocked_key.reject_reasons),
        )
    )

    sid_no_request = "exec_11h1g_no_request"
    _write(store, _session_with_narration(sid_no_request))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        blocked_request = engine.approve(sid_no_request, request_live_tts=False, approved_by="test")
    results.append(
        _pass(
            "approve_without_request_live_tts_blocks",
            not blocked_request.success
            and BLOCK_LIVE_TTS_NOT_REQUESTED in (blocked_request.reject_reasons or []),
            str(blocked_request.reject_reasons),
        )
    )

    sid_approve = "exec_11h1g_approve_ok_v2"
    _write(store, _session_with_narration(sid_approve))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        approved = engine.approve(
            sid_approve,
            request_live_tts=True,
            reason="Test approval",
            approved_by="validator",
            ttl_minutes=60,
        )
    approval = _dict(_dict(approved.voice_slot).get("approval"))
    results.append(
        _pass(
            "approve_ready_preflight_succeeds",
            approved.success
            and approval.get("approval_state") == STATE_APPROVED
            and approval.get("live_tts_eligible") is True
            and approved.tts_executed is False,
            str(approval.get("approval_state")),
        )
    )

    sid_reject = "exec_11h1g_reject"
    _write(store, _session_with_narration(sid_reject))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        engine.approve(sid_reject, request_live_tts=True, approved_by="test")
        rejected = engine.reject(sid_reject, reason="Rejected in test", rejected_by="validator")
    reject_approval = _dict(_dict(rejected.voice_slot).get("approval"))
    results.append(
        _pass(
            "reject_sets_rejected_state",
            rejected.success
            and reject_approval.get("approval_state") == STATE_REJECTED
            and BLOCK_VOICE_APPROVAL_REJECTED in (reject_approval.get("live_tts_blocked_reasons") or []),
            str(reject_approval.get("approval_state")),
        )
    )

    sid_expire = "exec_11h1g_expire"
    _write(store, _session_with_narration(sid_expire))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        engine.approve(sid_expire, request_live_tts=True, approved_by="test")
        expired = engine.expire(sid_expire, reason="Expired in test", expired_by="validator")
    expire_approval = _dict(_dict(expired.voice_slot).get("approval"))
    results.append(
        _pass(
            "expire_sets_expired_state",
            expired.success and expire_approval.get("approval_state") == STATE_EXPIRED,
            str(expire_approval.get("approval_state")),
        )
    )

    sid_reset = "exec_11h1g_reset"
    _write(store, _session_with_narration(sid_reset))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        engine.approve(sid_reset, request_live_tts=True, approved_by="test")
        reset = engine.reset_approval(sid_reset, reset_by="validator", clear_live_tts_request=True)
    reset_approval = _dict(_dict(reset.voice_slot).get("approval"))
    results.append(
        _pass(
            "reset_returns_correct_state",
            reset.success
            and reset_approval.get("approval_state") in ("not_required", STATE_REQUIRED)
            and _dict(reset.voice_slot).get("live_tts_requested") is False,
            str(reset_approval.get("approval_state")),
        )
    )

    sid_audit = "exec_11h1g_audit"
    _write(store, _session_with_narration(sid_audit))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        engine.approve(sid_audit, request_live_tts=True, approved_by="audit_test")
    loaded_audit = store.load_session(sid_audit)
    events = _audit_events(loaded_audit)
    results.append(
        _pass(
            "audit_trail_appended_for_write",
            len(events) >= 1
            and events[-1].get("event_type") == "approve_voice"
            and events[-1].get("tts_executed") is False,
            str(len(events)),
        )
    )

    sid_video = "exec_11h1g_video_guard"
    video_before = {
        "state": "RUNNING",
        "provider": "hailuo_browser",
        "status": "running",
        "started_at": "2026-05-31 00:00:00",
    }
    session_video = _session_with_narration(sid_video)
    session_video["execution_runtime"]["category_runtime"][CATEGORY_VIDEO] = dict(video_before)
    _write(store, session_video)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        engine.approve(sid_video, request_live_tts=True, approved_by="test")
    loaded_video = store.load_session(sid_video)
    video_after = _dict(_dict(loaded_video.get("execution_runtime")).get("category_runtime")).get(CATEGORY_VIDEO)
    critical_keys = ("state", "provider", "status", "started_at")
    preserved = all(video_after.get(k) == video_before.get(k) for k in critical_keys)
    results.append(
        _pass(
            "no_video_generation_mutation",
            preserved,
            str(video_after.get("state")),
        )
    )

    engine_source = (root / "content_brain" / "execution" / "voice_approval_operations_engine.py").read_text(
        encoding="utf-8"
    )
    policy_source = (root / "content_brain" / "execution" / "voice_approval_action_policy.py").read_text(
        encoding="utf-8"
    )
    service_source = (root / "ui" / "api" / "voice_approval_service.py").read_text(encoding="utf-8")
    forbidden_tts = bool(
        re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", engine_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", policy_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", service_source, re.MULTILINE)
    )
    results.append(
        _pass(
            "no_elevenlabs_voice_provider_import",
            not forbidden_tts,
            "clean" if not forbidden_tts else "forbidden reference",
        )
    )

    sid_legacy = "exec_11h1g_legacy"
    _write(
        store,
        {
            "execution_session_id": sid_legacy,
            "state": "COMPLETED",
            "brief_snapshot": {},
        },
    )
    legacy_result = engine.reset_approval(sid_legacy, reset_by="validator")
    results.append(
        _pass(
            "legacy_session_safe",
            legacy_result.success or legacy_result.code is not None,
            str(legacy_result.success),
        )
    )

    sid_api = "exec_11h1g_api"
    _write(store, _session_with_narration(sid_api))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        api_payload = service.approve(
            sid_api,
            request_live_tts=True,
            approved_by="api_test",
            reason="API test",
        )
    results.append(
        _pass(
            "api_response_tts_executed_false",
            api_payload.get("tts_executed") is False and api_payload.get("success") is True,
            str(api_payload.get("success")),
        )
    )

    voice_panel = (root / "ui" / "web" / "src" / "components" / "VoiceRuntimeObservabilityPanel.tsx").read_text(
        encoding="utf-8"
    )
    forbidden_tts_labels = ["Generate Voice", "Run TTS", "Start TTS"]
    results.append(
        _pass(
            "no_forbidden_tts_ui_labels",
            not any(label in voice_panel for label in forbidden_tts_labels),
        )
    )

    slot_source = (root / "content_brain" / "execution" / "voice_preflight_runtime_slot.py").read_text(encoding="utf-8")
    forbidden_legacy = bool(
        re.search(r"^\s*(from|import)\s+.*TimelineEngine", slot_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*full_video_pipeline", engine_source, re.MULTILINE)
    )
    results.append(
        _pass(
            "legacy_pipeline_untouched",
            not forbidden_legacy,
            "clean" if not forbidden_legacy else "forbidden import",
        )
    )

    results.append(_pass("validate_11h1e_still_passes", _run_module("project_brain.validate_11h1e_voice_approval_guard")))
    results.append(_pass("validate_11g_still_passes", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11H-1g",
        "label": "voice_approval_write_apis",
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
