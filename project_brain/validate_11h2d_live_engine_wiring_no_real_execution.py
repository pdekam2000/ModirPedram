"""
Phase 11H-2d — live engine wiring validation (no real ElevenLabs execution).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.live_voice_tts_engine import LiveVoiceTtsEngine
from content_brain.execution.mock_voice_tts_provider import PROVIDER_ID as MOCK_PROVIDER_ID
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine
from content_brain.execution.voice_live_tts_action_policy import (
    CODE_APPROVAL_REQUIRED,
    CODE_LIVE_TTS_DISABLED,
    CODE_LIVE_TTS_NOT_CONFIRMED,
    PROVIDER_MODE_LIVE,
    PROVIDER_MODE_MOCK,
    evaluate_voice_live_tts_run,
    evaluate_voice_run_mode_request,
)
from content_brain.execution.voice_live_tts_smoke_profile import (
    SMOKE_MAX_CHARACTERS,
    SMOKE_MAX_SEGMENTS,
    evaluate_voice_live_tts_smoke_caps,
)
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run
from ui.api.voice_run_service import VoiceRunService


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _run_module(module: str, *, core_only: bool = True) -> bool:
    from project_brain.validation_policy import run_validator_module

    return run_validator_module(module, core_only=core_only)


class MockResponse:
    def __init__(self, status_code: int, content: bytes = b"", headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


class SequentialMockHttp:
    def __init__(self, responses: list[MockResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "json": dict(json), "timeout": timeout})
        if not self.responses:
            return MockResponse(500, b"")
        return self.responses.pop(0)


def _session_with_narration(
    session_id: str,
    *,
    beats: list[dict] | None = None,
) -> dict:
    beat_plans = beats or [
        {"beat_id": "HOOK", "narration": "Short smoke narration for live wiring test."},
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


def _approve(store: ExecutionSessionStore, session_id: str) -> None:
    engine = VoiceApprovalOperationsEngine(store, project_root=store.project_root)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        result = engine.approve(session_id, request_live_tts=True, approved_by="validator")
    if not result.success:
        raise RuntimeError(str(result.reject_reasons))


def _preflight_session(store: ExecutionSessionStore, session_id: str) -> dict:
    session = store.load_session(session_id)
    session["execution_runtime"] = apply_voice_preflight_dry_run(
        session,
        ensure_multi_category_shell(session.get("execution_runtime") or {}),
        project_root=store.project_root,
    )
    store.save_session(session, overwrite=True)
    return session


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    service = VoiceRunService(store)
    results: list[dict] = []

    import content_brain.execution.voice_live_tts_action_policy as policy_module

    # 1. Default live request blocked with LIVE_TTS_DISABLED
    default_live = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=True)
    results.append(
        _pass(
            "default_live_request_blocked",
            not default_live.allowed and default_live.code == CODE_LIVE_TTS_DISABLED,
            str(default_live.code),
        )
    )

    # 2. Live request blocked when confirm_live_tts=false
    not_confirmed = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=False)
    results.append(
        _pass(
            "live_blocked_without_confirm",
            not not_confirmed.allowed and not_confirmed.code == CODE_LIVE_TTS_NOT_CONFIRMED,
            str(not_confirmed.code),
        )
    )

    # 3. Live request blocked when LIVE_RUNTIME_EXECUTION_APPROVED=False (env on)
    with patch.dict(os.environ, {"MODIR_VOICE_LIVE_TTS_ENABLED": "true"}, clear=False):
        with patch.object(policy_module, "LIVE_RUNTIME_EXECUTION_APPROVED", False):
            blocked_runtime = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=True)
    results.append(
        _pass(
            "live_blocked_runtime_not_approved",
            not blocked_runtime.allowed and blocked_runtime.code == CODE_LIVE_TTS_DISABLED,
            str(blocked_runtime.code),
        )
    )

    # 4. Live request blocked when env switch false
    with patch.object(policy_module, "LIVE_RUNTIME_EXECUTION_APPROVED", True):
        with patch.dict(os.environ, {"MODIR_VOICE_LIVE_TTS_ENABLED": "false"}, clear=False):
            blocked_env = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=True)
    results.append(
        _pass(
            "live_blocked_env_switch_false",
            not blocked_env.allowed and blocked_env.code == CODE_LIVE_TTS_DISABLED,
            str(blocked_env.code),
        )
    )

    # 5. Live request blocked without approval
    sid_no_approval = "exec_11h2d_no_approval"
    store.save_session(_session_with_narration(sid_no_approval), overwrite=True)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        session_na = _preflight_session(store, sid_no_approval)
        voice_slot_na = session_na["execution_runtime"]["category_runtime"][CATEGORY_VOICE]
        with patch.object(policy_module, "LIVE_RUNTIME_EXECUTION_APPROVED", True):
            with patch.dict(os.environ, {"MODIR_VOICE_LIVE_TTS_ENABLED": "true"}, clear=False):
                no_approval = evaluate_voice_live_tts_run(
                    session_na,
                    voice_slot_na,
                    provider_mode=PROVIDER_MODE_LIVE,
                    confirm_live_tts=True,
                    project_root=str(root),
                )
    results.append(
        _pass(
            "live_blocked_without_approval",
            not no_approval.allowed and no_approval.code == CODE_APPROVAL_REQUIRED,
            str(no_approval.code),
        )
    )

    # 6. Live request blocked when smoke caps exceeded
    over_segments = {
        "approval": {
            "estimated_character_count": 50,
            "estimated_segment_count": SMOKE_MAX_SEGMENTS + 1,
            "estimated_voice_cost": 0.01,
        },
        "segment_count": SMOKE_MAX_SEGMENTS + 1,
    }
    caps = evaluate_voice_live_tts_smoke_caps(over_segments)
    over_chars = {
        "approval": {
            "estimated_character_count": SMOKE_MAX_CHARACTERS + 50,
            "estimated_segment_count": 1,
            "estimated_voice_cost": 0.01,
        },
    }
    caps_chars = evaluate_voice_live_tts_smoke_caps(over_chars)
    results.append(
        _pass(
            "live_blocked_smoke_caps_exceeded",
            not caps.allowed and not caps_chars.allowed,
            f"seg={caps.code} char={caps_chars.code}",
        )
    )

    # 7. Mock mode still works
    sid_mock = "exec_11h2d_mock_ok"
    store.save_session(_session_with_narration(sid_mock), overwrite=True)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_mock)
        mock_run = service.run(sid_mock, triggered_by="validator", provider_mode=PROVIDER_MODE_MOCK)
    results.append(
        _pass(
            "mock_mode_still_works",
            mock_run.get("success") is True
            and mock_run.get("provider_mode") == PROVIDER_MODE_MOCK
            and mock_run.get("real_provider_called") is False,
            str(mock_run.get("status")),
        )
    )

    # 8. Mock manifest unchanged
    manifest = _dict(mock_run.get("manifest"))
    results.append(
        _pass(
            "mock_manifest_unchanged",
            manifest.get("provider") == MOCK_PROVIDER_ID
            and manifest.get("provider_mode") == PROVIDER_MODE_MOCK
            and manifest.get("real_provider_called") is False,
            str(manifest.get("provider_mode")),
        )
    )

    # 9. Live manifest extras with mocked adapter only
    sid_live = "exec_11h2d_live_manifest"
    store.save_session(_session_with_narration(sid_live), overwrite=True)
    mock_http = SequentialMockHttp(
        [MockResponse(200, b"\xff\xfb" + b"\x00" * 128, headers={"x-request-id": "req_smoke_11h2d"})]
    )
    live_engine = LiveVoiceTtsEngine(store, project_root=root, http_client=mock_http)
    live_service = VoiceRunService(store, engine=live_engine)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_live)
        with patch.object(policy_module, "LIVE_RUNTIME_EXECUTION_APPROVED", True):
            with patch.dict(
                os.environ,
                {"MODIR_VOICE_LIVE_TTS_ENABLED": "true", "ELEVENLABS_API_KEY": "test-key-mock-only"},
                clear=False,
            ):
                live_run = live_service.run(
                    sid_live,
                    triggered_by="validator",
                    provider_mode=PROVIDER_MODE_LIVE,
                    confirm_live_tts=True,
                )
    live_manifest = _dict(live_run.get("manifest"))
    results.append(
        _pass(
            "live_manifest_extras_mocked_adapter",
            live_run.get("success") is True
            and live_manifest.get("provider") == "elevenlabs"
            and live_manifest.get("provider_mode") == PROVIDER_MODE_LIVE
            and live_manifest.get("real_provider_called") is True
            and live_manifest.get("voice_id")
            and live_manifest.get("model_id")
            and live_manifest.get("retry_count") is not None
            and len(mock_http.calls) == 1,
            str(live_manifest.get("provider_mode")),
        )
    )

    # 10. VoiceRunService passes provider_mode correctly
    blocked_live = service.run(
        sid_no_approval,
        provider_mode=PROVIDER_MODE_LIVE,
        confirm_live_tts=True,
    )
    results.append(
        _pass(
            "service_passes_provider_mode",
            blocked_live.get("provider_mode") == PROVIDER_MODE_LIVE
            and mock_run.get("provider_mode") == PROVIDER_MODE_MOCK,
            f"blocked={blocked_live.get('provider_mode')} mock={mock_run.get('provider_mode')}",
        )
    )

    # 11. Preflight hook does not clobber completed executed=true voice slot
    sid_preflight = "exec_11h2d_preflight_preserve"
    store.save_session(_session_with_narration(sid_preflight), overwrite=True)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_preflight)
        completed = service.run(sid_preflight, provider_mode=PROVIDER_MODE_MOCK)
    manifest_path = completed.get("manifest_path")
    artifacts_before = list(completed.get("artifacts") or [])
    session_after_run = store.load_session(sid_preflight)
    runtime_before = dict(session_after_run.get("execution_runtime") or {})
    voice_before = dict(
        _dict(runtime_before.get("category_runtime")).get(CATEGORY_VOICE) or {}
    )
    session_after_run["execution_runtime"] = apply_voice_preflight_dry_run(
        session_after_run,
        ensure_multi_category_shell(runtime_before),
        project_root=root,
    )
    voice_after = _dict(
        _dict(session_after_run["execution_runtime"].get("category_runtime")).get(CATEGORY_VOICE)
    )
    ops = _dict(session_after_run["execution_runtime"].get("operations")).get("voice_preflight_dry_run")
    results.append(
        _pass(
            "preflight_does_not_clobber_completed_run",
            voice_before.get("executed") is True
            and voice_after.get("executed") is True
            and voice_after.get("dry_run") is False
            and voice_after.get("status") == "completed"
            and voice_after.get("voice_manifest_path") == voice_before.get("voice_manifest_path")
            and len(voice_after.get("artifacts") or []) == len(artifacts_before)
            and ops.get("completed_run_preserved") is True,
            str(voice_after.get("executed")),
        )
    )

    # 12. real_provider_called=false unless mocked live adapter simulates live
    results.append(
        _pass(
            "real_provider_called_gate",
            mock_run.get("real_provider_called") is False and live_run.get("real_provider_called") is True,
            f"mock={mock_run.get('real_provider_called')} live={live_run.get('real_provider_called')}",
        )
    )

    # 13. No real network call in validator (injected mock HTTP only)
    validator_source = Path(__file__).read_text(encoding="utf-8")
    uses_real_http_client = bool(
        re.search(r"RequestsHttpClient\s*\(", validator_source)
        or re.search(r"from\s+requests\s+import", validator_source)
        or re.search(r"allow_real_http\s*=\s*True", validator_source.replace('"allow_real_http=True"', ""))
    )
    results.append(
        _pass(
            "no_real_network_in_validator",
            not uses_real_http_client
            and isinstance(mock_http, SequentialMockHttp)
            and len(mock_http.calls) >= 1,
            f"mock_http_calls={len(mock_http.calls)}",
        )
    )

    # 14. Video slot unchanged
    sid_video = sid_mock
    loaded = store.load_session(sid_video)
    video_after = _dict(_dict(loaded.get("execution_runtime")).get("category_runtime")).get(CATEGORY_VIDEO)
    video_before = _session_with_narration(sid_video)["execution_runtime"]["category_runtime"][CATEGORY_VIDEO]
    preserved = all(video_after.get(k) == video_before.get(k) for k in ("state", "provider", "started_at", "completed_at"))
    results.append(
        _pass(
            "video_slot_unchanged",
            preserved and mock_run.get("video_mutated") is False,
            str(video_after.get("state")),
        )
    )

    # 15–17. Existing validators still pass (optional regression slice).
    if include_regressions:
        results.append(
            _pass(
                "validator_11h2c_still_passes",
                _run_module("project_brain.validate_11h2c_elevenlabs_runtime_adapter", core_only=True),
            )
        )
        results.append(
            _pass(
                "validator_11h2a_still_passes",
                _run_module("project_brain.validate_11h2a_mock_live_voice_tts_engine", core_only=True),
            )
        )
        results.append(
            _pass(
                "validator_11g_still_passes",
                _run_module("project_brain.validate_11g_multi_category_runtime_shell", core_only=True),
            )
        )

    from project_brain.validation_policy import summarize_validation_report

    report = summarize_validation_report(
        phase="11H-2d",
        label="live_engine_wiring_no_real_execution",
        results=results,
        include_regressions=include_regressions,
    )
    report["failed"] = report["total"] - report["passed"]
    report["failures"] = [r for r in results if not r.get("pass")]
    return report


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
    if validation_exit_code(report) == 0:
        print(f"\nPASS — {report['passed']}/{report['total']} tests")
        return 0
    print(f"\nFAIL — {report['failed']} failing test(s)")
    for failure in report.get("failures") or []:
        print(f"  - {failure['test']}: {failure.get('detail', '')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
