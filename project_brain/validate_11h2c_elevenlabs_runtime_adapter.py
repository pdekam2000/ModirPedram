"""
Phase 11H-2c — ElevenLabs runtime adapter validation (mocked HTTP only).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.audio_artifact_validator import AudioArtifactValidator
from content_brain.execution.elevenlabs_runtime_adapter import (
    CODE_ELEVENLABS_CANCELLED,
    CODE_ELEVENLABS_EMPTY_AUDIO,
    CODE_ELEVENLABS_KEY_MISSING,
    CODE_ELEVENLABS_RATE_LIMIT,
    CODE_ELEVENLABS_TIMEOUT,
    ElevenLabsRuntimeAdapter,
    build_live_manifest_extras,
)
from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_guard import BLOCK_VOICE_COST_LIMIT_EXCEEDED
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine
from content_brain.execution.voice_live_tts_action_policy import (
    CODE_APPROVAL_EXPIRED,
    CODE_APPROVAL_REQUIRED,
    CODE_ESTIMATES_MISSING,
    CODE_LIVE_TTS_DISABLED,
    CODE_LIVE_TTS_NOT_CONFIRMED,
    PROVIDER_MODE_LIVE,
    PROVIDER_MODE_MOCK,
    evaluate_voice_live_tts_live_caps,
    evaluate_voice_live_tts_run,
    evaluate_voice_run_mode_request,
)
from content_brain.execution.voice_provider_factory import build_elevenlabs_runtime_adapter
from providers.elevenlabs_config import ElevenLabsConfigResolver
from ui.api.voice_run_service import VoiceRunService


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


class ConfigSnapshotStub:
    config_version = "test"
    provider_id = "elevenlabs"
    api_key_env = "ELEVENLABS_API_KEY"
    has_api_key = True
    voice_id = "voice_test"
    model_id = "eleven_multilingual_v2"
    output_format = "mp3_44100_128"
    enabled_in_registry = True


def _adapter(http: SequentialMockHttp, *, cancel=False) -> ElevenLabsRuntimeAdapter:
    cancel_state = {"v": cancel}

    def cancel_check():
        return cancel_state["v"]

    return ElevenLabsRuntimeAdapter(
        config=ConfigSnapshotStub(),
        api_key="test-key-never-logged",
        http_client=http,
        sleep_fn=lambda _s: None,
        cancel_check=cancel_check if cancel else None,
    )


def _session_with_narration(session_id: str) -> dict:
    return {
        "execution_session_id": session_id,
        "state": "COMPLETED",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {"beat_id": "HOOK", "narration": "Adapter test narration segment one."},
                            {"beat_id": "BODY", "narration": "Adapter test narration segment two."},
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
                    "started_at": "2026-05-28 10:00:00",
                    "completed_at": "2026-05-28 10:05:00",
                }
            }
        },
    }


def _approve(store: ExecutionSessionStore, session_id: str) -> None:
    engine = VoiceApprovalOperationsEngine(store, project_root=store.project_root)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        result = engine.approve(session_id, request_live_tts=True, approved_by="validator")
    if not result.success:
        raise RuntimeError(str(result.reject_reasons))


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    service = VoiceRunService(store)
    results: list[dict] = []

    # 1. Live mode blocked unless confirm_live_tts=true
    not_confirmed = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=False)
    results.append(
        _pass(
            "live_mode_blocked_without_confirm",
            not not_confirmed.allowed and not_confirmed.code == CODE_LIVE_TTS_NOT_CONFIRMED,
            str(not_confirmed.code),
        )
    )

    # 2. Live mode blocked on /voice/run (11H-2c hard gate)
    live_disabled = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=True)
    results.append(
        _pass(
            "live_mode_blocked_runtime_not_approved",
            not live_disabled.allowed and live_disabled.code == CODE_LIVE_TTS_DISABLED,
            str(live_disabled.code),
        )
    )

    sid = "exec_11h2c_policy"
    store.save_session(_session_with_narration(sid), overwrite=True)

    from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
    from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        session_loaded = store.load_session(sid)
        session_loaded["execution_runtime"] = apply_voice_preflight_dry_run(
            session_loaded,
            ensure_multi_category_shell(session_loaded.get("execution_runtime") or {}),
            project_root=root,
        )
        voice_slot = session_loaded["execution_runtime"]["category_runtime"]["voice_generation"]

        # 3. Live policy blocked without approval
        no_approval = evaluate_voice_live_tts_run(
            session_loaded,
            voice_slot,
            provider_mode=PROVIDER_MODE_LIVE,
            project_root=str(root),
        )
    results.append(
        _pass(
            "live_mode_blocked_without_approval",
            not no_approval.allowed and no_approval.code == CODE_APPROVAL_REQUIRED,
            str(no_approval.code),
        )
    )

    # 4. Live policy blocked expired approval
    sid_exp = "exec_11h2c_expired"
    store.save_session(_session_with_narration(sid_exp), overwrite=True)
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-mock-only"}, clear=False):
        _approve(store, sid_exp)
        VoiceApprovalOperationsEngine(store, project_root=root).expire(sid_exp, expired_by="validator")
        session_exp = store.load_session(sid_exp)
        session_exp["execution_runtime"] = apply_voice_preflight_dry_run(
            session_exp,
            ensure_multi_category_shell(session_exp.get("execution_runtime") or {}),
            project_root=root,
        )
        vslot_exp = session_exp["execution_runtime"]["category_runtime"]["voice_generation"]
        expired_policy = evaluate_voice_live_tts_run(
            session_exp,
            vslot_exp,
            provider_mode=PROVIDER_MODE_LIVE,
            project_root=str(root),
        )
    results.append(
        _pass(
            "live_mode_blocked_expired_approval",
            not expired_policy.allowed and expired_policy.code == CODE_APPROVAL_EXPIRED,
            str(expired_policy.code),
        )
    )

    # 5. Live caps — estimates exceed cost cap
    over_cap_slot = {
        "approval": {
            "estimated_character_count": 100,
            "estimated_segment_count": 2,
            "estimated_voice_cost": 99.0,
        },
        "segment_count": 2,
    }
    caps = evaluate_voice_live_tts_live_caps(over_cap_slot)
    results.append(
        _pass(
            "live_mode_blocked_estimates_exceed_cap",
            not caps.allowed and BLOCK_VOICE_COST_LIMIT_EXCEEDED in (caps.reject_reasons or []),
            str(caps.code),
        )
    )

    missing_est = evaluate_voice_live_tts_live_caps({"approval": {}, "segment_count": 0})
    results.append(
        _pass(
            "live_mode_blocked_missing_estimates",
            not missing_est.allowed and missing_est.code == CODE_ESTIMATES_MISSING,
            str(missing_est.code),
        )
    )

    # 6. Mock /voice/run still works
    sid_mock = "exec_11h2c_mock_ok"
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

    # 7–12. Adapter unit tests (mocked HTTP)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "narration_001.mp3"
        ok_http = SequentialMockHttp(
            [MockResponse(200, b"\xff\xfb" + b"\x00" * 128, headers={"x-request-id": "req_ok"})]
        )
        ok_result = _adapter(ok_http).synthesize_segment("Hello", out, segment_index=1)
        results.append(
            _pass(
                "adapter_mock_http_success",
                ok_result.success and out.is_file() and out.stat().st_size > 0,
                str(ok_result.http_status),
            )
        )

        retry_http = SequentialMockHttp(
            [
                MockResponse(429, b"rate limited"),
                MockResponse(200, b"\xff\xfb" + b"\x00" * 64),
            ]
        )
        out2 = Path(tmp) / "narration_002.mp3"
        retry_result = _adapter(retry_http).synthesize_segment("Retry", out2, segment_index=2)
        results.append(
            _pass(
                "adapter_mock_http_429_retry_success",
                retry_result.success and retry_result.retried and retry_result.retry_count >= 1,
                str(retry_result.retry_count),
            )
        )

        fail_http = SequentialMockHttp(
            [MockResponse(429, b""), MockResponse(429, b""), MockResponse(429, b"")]
        )
        out3 = Path(tmp) / "narration_003.mp3"
        fail_result = _adapter(fail_http).synthesize_segment("Fail", out3, segment_index=3)
        results.append(
            _pass(
                "adapter_mock_http_429_exhausted",
                not fail_result.success and fail_result.reject_code == CODE_ELEVENLABS_RATE_LIMIT,
                str(fail_result.reject_code),
            )
        )

        class TimeoutHttp:
            def post(self, url, *, headers, json, timeout):
                raise TimeoutError("timed out")

        out4 = Path(tmp) / "narration_004.mp3"
        timeout_result = ElevenLabsRuntimeAdapter(
            config=ConfigSnapshotStub(),
            api_key="test-key",
            http_client=TimeoutHttp(),
            max_retry_attempts=1,
            sleep_fn=lambda _s: None,
        ).synthesize_segment("Timeout", out4, segment_index=4)
        results.append(
            _pass(
                "adapter_mock_timeout",
                not timeout_result.success and timeout_result.reject_code == CODE_ELEVENLABS_TIMEOUT,
                str(timeout_result.reject_code),
            )
        )

        empty_http = SequentialMockHttp([MockResponse(200, b"")])
        out5 = Path(tmp) / "narration_005.mp3"
        empty_result = _adapter(empty_http).synthesize_segment("Empty", out5, segment_index=5)
        results.append(
            _pass(
                "adapter_mock_empty_audio",
                not empty_result.success and empty_result.reject_code == CODE_ELEVENLABS_EMPTY_AUDIO,
                str(empty_result.reject_code),
            )
        )

        validation = AudioArtifactValidator().validate(
            [{"file_path": str(out.resolve())}],
            dry_run=False,
        )
        results.append(
            _pass(
                "adapter_output_passes_artifact_validator",
                validation.passed,
                str(validation.reject_reasons),
            )
        )

        cancel_flag = {"v": False}
        cancel_http = SequentialMockHttp([MockResponse(200, b"\xff\xfb" + b"\x01" * 8)])

        def cancel_check():
            cancel_flag["v"] = True
            return cancel_flag["v"]

        out6 = Path(tmp) / "narration_006.mp3"
        cancel_result = ElevenLabsRuntimeAdapter(
            config=ConfigSnapshotStub(),
            api_key="test-key",
            http_client=cancel_http,
            cancel_check=cancel_check,
            sleep_fn=lambda _s: None,
        ).synthesize_segment("Cancel", out6, segment_index=6)
        results.append(
            _pass(
                "adapter_cancel_before_http",
                not cancel_result.success and cancel_result.reject_code == CODE_ELEVENLABS_CANCELLED,
                str(cancel_result.reject_code),
            )
        )

    # 13. No key exposure in adapter to_dict / HTTP audit
    http = SequentialMockHttp([MockResponse(200, b"\xff\xfb" + b"\x00" * 8)])
    http_adapter = _adapter(http)
    with tempfile.TemporaryDirectory() as tmp:
        result_dict = http_adapter.synthesize_segment(
            "Secret",
            Path(tmp) / "n.mp3",
            segment_index=1,
        ).to_dict()
    key_leak = "test-key-never-logged" in json.dumps(result_dict)
    header_has_key = any(c["headers"].get("xi-api-key") == "test-key-never-logged" for c in http.calls)
    results.append(
        _pass(
            "no_api_key_in_normalized_result",
            not key_leak and header_has_key,
            "result clean" if not key_leak else "key leaked to result",
        )
    )

    # 14. real_provider_called true only for adapter success path
    results.append(
        _pass(
            "real_provider_called_true_on_adapter_success",
            ok_result.real_provider_called is True,
            str(ok_result.real_provider_called),
        )
    )
    results.append(
        _pass(
            "real_provider_called_false_on_mock_run",
            mock_run.get("real_provider_called") is False,
            str(mock_run.get("real_provider_called")),
        )
    )

    # 15. Service blocks live request
    live_service = service.run(
        sid_mock,
        provider_mode=PROVIDER_MODE_LIVE,
        confirm_live_tts=True,
        triggered_by="validator",
    )
    results.append(
        _pass(
            "service_blocks_live_elevenlabs_request",
            not live_service.get("success") and live_service.get("code") == CODE_LIVE_TTS_DISABLED,
            str(live_service.get("code")),
        )
    )

    # 16. Adapter rejects construction without http_client
    try:
        ElevenLabsRuntimeAdapter(config=ConfigSnapshotStub(), api_key="k", allow_real_http=False)
        no_client_ok = False
    except RuntimeError:
        no_client_ok = True
    results.append(
        _pass(
            "adapter_blocks_real_http_without_injection",
            no_client_ok,
            "RuntimeError raised",
        )
    )

    # 17. Missing key at construction
    try:
        ElevenLabsRuntimeAdapter(
            config=ConfigSnapshotStub(),
            api_key="",
            http_client=SequentialMockHttp([]),
        )
        missing_key_ok = False
    except ValueError as exc:
        missing_key_ok = str(exc) == CODE_ELEVENLABS_KEY_MISSING
    results.append(
        _pass(
            "adapter_missing_key_rejected",
            missing_key_ok,
            CODE_ELEVENLABS_KEY_MISSING,
        )
    )

    # 18. Manifest extras prep
    config = ElevenLabsConfigResolver(root).resolve({})
    extras = build_live_manifest_extras(config, total_retry_count=2)
    results.append(
        _pass(
            "live_manifest_extras_prepared",
            extras.get("provider") == "elevenlabs"
            and extras.get("provider_mode") == PROVIDER_MODE_LIVE
            and extras.get("real_provider_called") is True,
            json.dumps({k: extras.get(k) for k in ("provider", "provider_mode")}),
        )
    )

    # 19. Factory builds adapter with injected client
    session_factory = _session_with_narration("exec_11h2c_factory")
    factory_http = SequentialMockHttp([MockResponse(200, b"\xff\xfb" + b"\x00" * 16)])
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "factory-test-key"}, clear=False):
        factory_adapter = build_elevenlabs_runtime_adapter(
            session_factory,
            project_root=root,
            http_client=factory_http,
        )
    results.append(
        _pass(
            "provider_factory_injection_works",
            isinstance(factory_adapter, ElevenLabsRuntimeAdapter),
            "built",
        )
    )

    # 20. Static grep — no legacy provider import
    adapter_source = (root / "content_brain" / "execution" / "elevenlabs_runtime_adapter.py").read_text(
        encoding="utf-8"
    )
    factory_source = (root / "content_brain" / "execution" / "voice_provider_factory.py").read_text(
        encoding="utf-8"
    )
    forbidden = bool(
        re.search(r"elevenlabs_voice_provider", adapter_source)
        or re.search(r"elevenlabs_voice_provider", factory_source)
        or "api.elevenlabs.io" not in adapter_source
    )
    results.append(
        _pass(
            "no_legacy_elevenlabs_voice_provider_import",
            not re.search(r"elevenlabs_voice_provider", adapter_source)
            and not re.search(r"elevenlabs_voice_provider", factory_source),
            "clean",
        )
    )

    # Regression
    results.append(_pass("validate_11h2a_still_passes", _run_module("project_brain.validate_11h2a_mock_live_voice_tts_engine")))
    results.append(_pass("validate_11h1i_still_passes", _run_module("project_brain.validate_11h1i_voice_approval_ui_controls")))
    results.append(_pass("validate_11g_still_passes", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))

    passed = sum(1 for item in results if item["pass"])
    total = len(results)
    return {
        "phase": "11H-2c",
        "label": "elevenlabs_runtime_adapter",
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
