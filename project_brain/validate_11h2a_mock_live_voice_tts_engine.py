"""
Phase 11H-2a — mock live voice TTS engine validation (no real ElevenLabs).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.audio_artifact_validator import AudioArtifactValidator
from content_brain.execution.category_runtime_compat import STATUS_COMPLETED
from content_brain.execution.live_voice_tts_engine import LiveVoiceTtsEngine
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_CREDENTIALS_MISSING,
    BLOCK_VOICE_APPROVAL_REQUIRED,
    STATE_APPROVED,
)
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine
from ui.api.voice_approval_service import VoiceApprovalService
from ui.api.voice_run_service import VoiceRunService


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


def _session_with_narration(session_id: str, *, beats: list[dict] | None = None) -> dict:
    beat_plans = beats or [
        {"beat_id": "HOOK", "narration": "First narration segment for mock voice TTS."},
        {"beat_id": "BODY", "narration": "Second narration segment for mock voice TTS."},
    ]
    return {
        "execution_session_id": session_id,
        "state": "COMPLETED",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {"beat_plans": beat_plans}
                }
            }
        },
        "execution_runtime": {
            "category_runtime": {
                CATEGORY_VIDEO: {
                    "state": "COMPLETED",
                    "provider": "hailuo_browser",
                    "status": "completed",
                    "started_at": "2026-05-28 10:00:00",
                    "completed_at": "2026-05-28 10:05:00",
                }
            },
            "artifacts_by_category": {},
        },
    }


def _write(store: ExecutionSessionStore, session: dict) -> None:
    store.save_session(session, overwrite=True)


def _approve(store: ExecutionSessionStore, session_id: str) -> None:
    engine = VoiceApprovalOperationsEngine(store, project_root=store.project_root)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        result = engine.approve(session_id, request_live_tts=True, approved_by="validator")
    if not result.success:
        raise RuntimeError(f"Approve failed for {session_id}: {result.reject_reasons}")


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    run_engine = LiveVoiceTtsEngine(store, project_root=root)
    run_service = VoiceRunService(store)
    approval_service = VoiceApprovalService(store)
    results: list[dict] = []

    # 1. Blocks without approval
    sid_no_approval = "exec_11h2a_no_approval"
    _write(store, _session_with_narration(sid_no_approval))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        blocked = run_engine.run(sid_no_approval, triggered_by="validator")
    results.append(
        _pass(
            "run_blocks_without_approval",
            not blocked.success
            and blocked.code in ("APPROVAL_REQUIRED", BLOCK_VOICE_APPROVAL_REQUIRED)
            and blocked.tts_executed is False,
            str(blocked.code),
        )
    )

    # 2. Blocks expired approval
    sid_expired = "exec_11h2a_expired"
    _write(store, _session_with_narration(sid_expired))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_expired)
        approval_engine = VoiceApprovalOperationsEngine(store, project_root=root)
        approval_engine.expire(sid_expired, expired_by="validator")
        expired_run = run_engine.run(sid_expired, triggered_by="validator")
    results.append(
        _pass(
            "run_blocks_expired_approval",
            not expired_run.success
            and expired_run.code in ("APPROVAL_EXPIRED", BLOCK_APPROVAL_EXPIRED),
            str(expired_run.code),
        )
    )

    # 3. Blocks missing credentials / preflight not ready
    sid_missing_key = "exec_11h2a_missing_key"
    _write(store, _session_with_narration(sid_missing_key))
    env_without_key = {k: v for k, v in os.environ.items() if k != "ELEVENLABS_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        blocked_key = run_engine.run(sid_missing_key, triggered_by="validator")
    results.append(
        _pass(
            "run_blocks_missing_credentials",
            not blocked_key.success and BLOCK_CREDENTIALS_MISSING in (blocked_key.reject_reasons or []),
            str(blocked_key.reject_reasons),
        )
    )

    # 4–11. Successful mock run
    sid_ok = "exec_11h2a_mock_ok"
    video_before = dict(_session_with_narration(sid_ok)["execution_runtime"]["category_runtime"][CATEGORY_VIDEO])
    _write(store, _session_with_narration(sid_ok))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_ok)
        ok = run_service.run(sid_ok, triggered_by="validator", reason="Mock run test")
    voice_slot = _dict(ok.get("voice_slot"))
    progress = _dict(voice_slot.get("live_tts_progress"))
    artifact_root = store.artifact_dir(sid_ok, CATEGORY_VOICE)
    mp3_files = sorted(artifact_root.glob("narration_*.mp3"))
    manifest_path = artifact_root / "voice_manifest.json"

    results.append(
        _pass(
            "run_succeeds_with_approved_mock_session",
            ok.get("success") is True and ok.get("tts_executed") is True,
            str(ok.get("status")),
        )
    )
    results.append(
        _pass(
            "mock_mp3_files_created_non_empty",
            len(mp3_files) >= 2 and all(f.stat().st_size > 0 for f in mp3_files),
            str([f.name for f in mp3_files]),
        )
    )
    results.append(
        _pass(
            "voice_manifest_created",
            manifest_path.is_file(),
            str(manifest_path),
        )
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    artifact_dicts = [{"file_path": str(f.resolve())} for f in mp3_files]
    validation = AudioArtifactValidator().validate(artifact_dicts, dry_run=False)
    results.append(
        _pass(
            "audio_artifact_validator_passes",
            validation.passed,
            str(validation.reject_reasons),
        )
    )
    results.append(
        _pass(
            "voice_slot_lifecycle_completed",
            voice_slot.get("status") == STATUS_COMPLETED and voice_slot.get("state") == STATUS_COMPLETED,
            str(voice_slot.get("status")),
        )
    )
    results.append(
        _pass(
            "progress_reaches_100",
            progress.get("progress_percent") == 100,
            str(progress.get("progress_percent")),
        )
    )
    results.append(
        _pass(
            "executed_true_only_after_mock_run",
            voice_slot.get("executed") is True and voice_slot.get("live_tts_executed") is True,
            str(voice_slot.get("executed")),
        )
    )
    results.append(
        _pass(
            "real_provider_called_false",
            ok.get("real_provider_called") is False and manifest.get("real_provider_called") is False,
            str(ok.get("real_provider_called")),
        )
    )

    loaded = store.load_session(sid_ok)
    video_after = _dict(_dict(loaded.get("execution_runtime")).get("category_runtime")).get(CATEGORY_VIDEO)
    preserved = all(video_after.get(k) == video_before.get(k) for k in ("state", "provider", "started_at", "completed_at"))
    results.append(
        _pass(
            "video_generation_snapshot_unchanged",
            preserved and ok.get("video_mutated") is False,
            str(video_after.get("state")),
        )
    )

    # 13. Cancel before run
    sid_cancel = "exec_11h2a_cancel_before"
    _write(store, _session_with_narration(sid_cancel))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_cancel)
        session_cancel = store.load_session(sid_cancel)
        session_cancel["operations_control"] = {"cancel_requested": True, "cancel_reason": "test cancel"}
        _write(store, session_cancel)
        cancelled = run_engine.run(sid_cancel, triggered_by="validator")
    results.append(
        _pass(
            "cancel_before_run_blocked",
            not cancelled.success and cancelled.status in ("rejected", "cancelled"),
            str(cancelled.status),
        )
    )

    # 14. Provider failure simulation
    sid_fail = "exec_11h2a_provider_fail"
    _write(store, _session_with_narration(sid_fail))
    fail_engine = LiveVoiceTtsEngine(store, project_root=root, simulate_failure_at=1)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_fail)
        failed = fail_engine.run(sid_fail, triggered_by="validator")
    fail_slot = _dict(failed.voice_slot)
    results.append(
        _pass(
            "provider_failure_marks_failed",
            not failed.success and fail_slot.get("status") == "failed" and failed.tts_executed is False,
            str(fail_slot.get("status")),
        )
    )

    # 15. No real ElevenLabs HTTP import
    engine_source = (root / "content_brain" / "execution" / "live_voice_tts_engine.py").read_text(encoding="utf-8")
    mock_source = (root / "content_brain" / "execution" / "mock_voice_tts_provider.py").read_text(encoding="utf-8")
    service_source = (root / "ui" / "api" / "voice_run_service.py").read_text(encoding="utf-8")
    forbidden = bool(
        re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", engine_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", mock_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", service_source, re.MULTILINE)
        or "api.elevenlabs.io" in engine_source
        or "api.elevenlabs.io" in mock_source
    )
    results.append(
        _pass(
            "no_elevenlabs_real_http_import_or_call",
            not forbidden,
            "clean" if not forbidden else "forbidden reference",
        )
    )

    # 16. Approve does not auto-run
    sid_no_auto = "exec_11h2a_no_auto_run"
    _write(store, _session_with_narration(sid_no_auto))
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        approved_only = approval_service.approve(sid_no_auto, request_live_tts=True, approved_by="validator")
    approval_slot = _dict(approved_only.get("voice_slot"))
    auto_root = store.artifact_dir(sid_no_auto, CATEGORY_VOICE)
    auto_mp3 = list(auto_root.glob("narration_*.mp3"))
    results.append(
        _pass(
            "approve_does_not_auto_run",
            approved_only.get("tts_executed") is False
            and approval_slot.get("status") != STATUS_COMPLETED
            and len(auto_mp3) == 0,
            str(approval_slot.get("status")),
        )
    )

    # 17–18. Regression validators
    results.append(_pass("validate_11h1i_still_passes", _run_module("project_brain.validate_11h1i_voice_approval_ui_controls")))
    results.append(_pass("validate_11g_still_passes", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))

    # 19. API response provider_mode=mock
    results.append(
        _pass(
            "api_response_provider_mode_mock",
            ok.get("provider_mode") == "mock" and manifest.get("provider_mode") == "mock",
            str(ok.get("provider_mode")),
        )
    )

    # 20. Manifest required fields
    required_manifest = all(
        manifest.get(k) is not None
        for k in (
            "session_id",
            "category",
            "provider",
            "provider_mode",
            "segment_count",
            "character_count",
            "files",
            "validation_status",
            "created_at",
            "tts_executed",
            "real_provider_called",
        )
    )
    results.append(
        _pass(
            "manifest_required_fields_present",
            required_manifest and manifest.get("provider") == "mock_elevenlabs",
            json.dumps({k: manifest.get(k) for k in ("provider", "provider_mode", "tts_executed")}),
        )
    )

    passed = sum(1 for item in results if item["pass"])
    total = len(results)
    return {
        "phase": "11H-2a",
        "label": "mock_live_voice_tts_engine",
        "passed": passed,
        "total": total,
        "all_pass": passed == total,
        "results": results,
    }


def main() -> None:
    report = run_matrix(".")
    print(json.dumps(report, indent=2))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    if not report["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
