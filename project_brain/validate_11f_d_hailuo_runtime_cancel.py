"""
Phase 11F-d — Hailuo runtime cancel_check wiring validation (mocks/fakes only).
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
from content_brain.execution.operations_cancel import CANCEL_REJECT_CODE
from content_brain.execution.provider_cancel_wiring import (
    HAILUO_CANCEL_AWARE_PROVIDERS,
    call_with_optional_cancel_check,
    is_provider_cooperative_cancel,
    provider_accepts_runtime_cancel,
    supports_cancel_check,
)
from content_brain.execution.provider_runtime_engine import (
    FAILURE_CODE_OPERATIONS_CANCELLED,
    ProviderRuntimeEngine,
    RuntimePolicy,
    STATE_CANCELLED,
)
from content_brain.execution.session_store import ExecutionSessionStore
from core.video_provider_router import VideoProviderRouter
from orchestrators.hailuo_multi_clip_orchestrator import HailuoMultiClipOrchestrator
from providers.hailuo_api_errors import HailuoCancelledError
from providers.hailuo_artifact_utils import MIN_ARTIFACT_BYTES, MODE_BROWSER, finalize_download_artifact
from providers.hailuo_download_provider import HailuoDownloadProvider
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
    results: list[dict] = []

    results.append(
        _pass(
            "hailuo_cancel_aware_ids",
            HAILUO_CANCEL_AWARE_PROVIDERS == frozenset({"hailuo", "hailuo_browser"}),
        )
    )
    results.append(_pass("provider_accepts_hailuo", provider_accepts_runtime_cancel("hailuo")))
    results.append(_pass("provider_accepts_hailuo_browser", provider_accepts_runtime_cancel("hailuo_browser")))
    results.append(_pass("supports_cancel_check_orchestrator", supports_cancel_check(HailuoMultiClipOrchestrator.run)))
    results.append(
        _pass(
            "hailuo_cancel_error_is_cooperative",
            is_provider_cooperative_cancel(HailuoCancelledError("cancelled")),
        )
    )

    # Router passes cancel_check to Hailuo orchestrator
    with patch("core.video_provider_router.call_with_optional_cancel_check") as mock_call:
        mock_call.side_effect = lambda fn, /, *args, cancel_check=None, **kwargs: fn(
            *args, **{**kwargs, **({"cancel_check": cancel_check} if cancel_check is not None else {})}
        )
        with patch("orchestrators.hailuo_multi_clip_orchestrator.HailuoMultiClipOrchestrator") as mock_orch_cls:
            instance = mock_orch_cls.return_value
            instance.run.return_value = []
            router = VideoProviderRouter()
            sentinel = lambda: False
            router.generate_clips(["demo"], provider_override="hailuo_browser", cancel_check=sentinel)
            _, kwargs = mock_call.call_args
            results.append(
                _pass(
                    "router_passes_cancel_check_hailuo",
                    kwargs.get("cancel_check") is sentinel,
                )
            )

    store = ExecutionSessionStore(root)
    engine = ProviderRuntimeEngine(store)
    session_id = "exec_11fd_cancel_hailuo"
    session = _hailuo_session(root, session_id)
    store.save_session(session, overwrite=True)

    engine_calls: dict = {}
    artifact_root = store.artifact_dir(session_id, "video_generation")

    with tempfile.TemporaryDirectory() as router_tmp:
        router_tmp_path = Path(router_tmp)

        class _RecordingRouter:
            def generate_clips(self, prompts, *, provider_override=None, cancel_check=None):
                engine_calls["cancel_check"] = cancel_check
                engine_calls["provider_override"] = provider_override
                marker = router_tmp_path / "clip_01.mp4"
                marker.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 20))
                return [str(marker)]

        with patch("core.video_provider_router.VideoProviderRouter", _RecordingRouter):
            engine._execute_clips(
                ["demo"],
                "hailuo_browser",
                artifact_root,
                RuntimePolicy(),
                session_id=session_id,
            )

    results.append(
        _pass(
            "runtime_engine_passes_cancel_check",
            callable(engine_calls.get("cancel_check")),
            engine_calls.get("provider_override", ""),
        )
    )

    # Orchestrator receives cancel_check via call_with_optional_cancel_check
    captured: dict = {}

    class _FakeOrch:
        def __init__(self, *args, **kwargs):
            captured["init_cancel_check"] = kwargs.get("cancel_check")

        def run(self, prompts, *, cancel_check=None):
            captured["run_cancel_check"] = cancel_check
            return []

    with patch("orchestrators.hailuo_multi_clip_orchestrator.HailuoMultiClipOrchestrator", _FakeOrch):
        router = VideoProviderRouter()
        call_with_optional_cancel_check(
            router.generate_clips,
            ["demo"],
            cancel_check=lambda: False,
            provider_override="hailuo_browser",
        )
    results.append(_pass("orchestrator_run_receives_cancel_check", callable(captured.get("run_cancel_check"))))

    # Download provider accepts cancel_check in constructor
    downloader = HailuoDownloadProvider(cancel_check=lambda: False)
    results.append(_pass("download_provider_cancel_check", callable(getattr(downloader, "_cancel_check", None))))

    # Live cooperative cancel -> CANCELLED with partial artifacts
    cancel_session_id = "exec_11fd_live_cancel"
    cancel_session = _hailuo_session(root, cancel_session_id)
    cancel_session["operations_control"] = {
        "cancel_requested": False,
        "cancel_reason": "validation hailuo live cancel",
        "cancelled_by": "validate",
    }
    store.save_session(cancel_session, overwrite=True)

    with tempfile.TemporaryDirectory() as tmp:
        partial_path = Path(tmp) / "clip_01.mp4"
        partial_path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 20))
        clip_result = finalize_download_artifact(
            partial_path,
            mode=MODE_BROWSER,
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            clip_index=1,
            source_url="https://cdn.test/hailuo.mp4",
            partial=True,
        )
        cancel_exc = HailuoCancelledError(
            "Hailuo browser cancelled during generation_wait",
            partial_paths=[str(partial_path)],
            clip_results=[clip_result],
            phase="generation_wait",
            details={"clip_results": [clip_result], "partial_paths": [str(partial_path)]},
        )

        router_calls: dict = {}

        def _cancel_router(prompts, *, provider_override=None, cancel_check=None):
            router_calls["cancel_check"] = cancel_check
            loaded = store.load_session(cancel_session_id)
            control = dict(loaded.get("operations_control") or {})
            control["cancel_requested"] = True
            loaded["operations_control"] = control
            store.save_session(loaded, overwrite=True)
            assert cancel_check is not None
            assert cancel_check() is True
            raise cancel_exc

        with patch.object(VideoProviderRouter, "generate_clips", side_effect=_cancel_router):
            dispatch_result = engine.dispatch_by_id(
                cancel_session_id,
                actor="validate",
                policy=RuntimePolicy(require_queue_fingerprint=False, require_readiness=False),
            )

        final = store.load_session(cancel_session_id)
        runtime = final.get("execution_runtime") or {}
        failure = runtime.get("failure") or {}
        cancellation = (runtime.get("operations") or {}).get("cancellation") or {}
        artifacts = (runtime.get("artifacts_by_category") or {}).get("video_generation") or []

        results.append(_pass("live_cancel_check_invoked", callable(router_calls.get("cancel_check"))))
        results.append(_pass("dispatch_not_success", dispatch_result.success is False))
        results.append(_pass("final_state_cancelled", final.get("state") == STATE_CANCELLED))
        results.append(_pass("runtime_state_cancelled", runtime.get("state") == STATE_CANCELLED))
        results.append(_pass("not_failed_state", final.get("state") != "FAILED"))
        results.append(_pass("reject_code_operator_cancelled", dispatch_result.reject_code == CANCEL_REJECT_CODE))
        results.append(
            _pass(
                "failure_code_operations_cancelled",
                failure.get("code") == FAILURE_CODE_OPERATIONS_CANCELLED,
                failure.get("code", ""),
            )
        )
        results.append(_pass("partial_artifacts_preserved_flag", cancellation.get("partial_artifacts_preserved") is True))
        results.append(_pass("partial_paths_recorded", len(cancellation.get("partial_paths") or []) >= 1))
        results.append(_pass("clip_results_recorded", len(cancellation.get("clip_results") or []) >= 1))
        results.append(_pass("not_completed_state", final.get("state") != "COMPLETED"))
        results.append(_pass("partial_source_file_not_deleted", partial_path.exists()))
        results.append(
            _pass(
                "artifact_metadata_hailuo_clip_result",
                any(
                    (item.get("metadata") or {}).get("hailuo_clip_result")
                    for item in artifacts
                )
                if artifacts
                else bool(cancellation.get("clip_results")),
            )
        )

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11e_e_still_passes", "project_brain.validate_11e_e_runtime_cancel_wiring"),
            ("validate_11f_a_still_passes", "project_brain.validate_11f_a_hailuo_preflight"),
            ("validate_11f_b_still_passes", "project_brain.validate_11f_b_hailuo_browser_hardening"),
            ("validate_11f_c_still_passes", "project_brain.validate_11f_c_hailuo_artifacts"),
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
