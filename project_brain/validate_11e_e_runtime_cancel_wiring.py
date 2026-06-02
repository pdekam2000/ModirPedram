"""
Phase 11E-e — runtime cancel_check wiring validation (mocks/fakes only).
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.operations_cancel import CANCEL_REJECT_CODE
from content_brain.execution.provider_cancel_wiring import (
    call_with_optional_cancel_check,
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
from providers.runway_api_errors import RunwayCancelledError
from providers.runway_artifact_utils import MIN_ARTIFACT_BYTES, finalize_download_artifact, MODE_API
from providers.runway_video_provider import RunwayVideoProvider
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


def _demo_session(root: Path, session_id: str, *, provider: str) -> dict:
    base = json.loads(
        (root / "storage" / "content_brain" / "execution" / "sessions" / "exec_10i_dequeued_demo.json").read_text(
            encoding="utf-8"
        )
    )
    session = copy.deepcopy(base)
    session["execution_session_id"] = session_id
    session["state"] = "DEQUEUED"
    session["provider"] = provider
    session.setdefault("provider_selection", {})
    session["provider_selection"]["primary_provider"] = provider
    session["provider_selection"].setdefault("category_selections", {})
    session["provider_selection"]["category_selections"]["video_generation"] = {"provider": provider}
    session.pop("execution_runtime", None)
    session.pop("operations_control", None)
    return session


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    # Router passes cancel_check to Runway API provider
    captured: dict = {}

    class _FakeRunwayProvider:
        def generate_clips(self, prompts, *, cancel_check=None):
            captured["api_cancel_check"] = cancel_check
            return []

    with patch("providers.runway_video_provider.RunwayVideoProvider", _FakeRunwayProvider):
        router = VideoProviderRouter()
        router.generate_clips(["demo"], provider_override="runway", cancel_check=lambda: False)
    results.append(
        _pass(
            "router_passes_cancel_check_api",
            callable(captured.get("api_cancel_check")),
        )
    )

    # Router passes cancel_check to Runway browser orchestrator
    with patch("core.video_provider_router.call_with_optional_cancel_check") as mock_call:
        mock_call.side_effect = lambda fn, /, *args, cancel_check=None, **kwargs: fn(*args, **{**kwargs, **({"cancel_check": cancel_check} if cancel_check is not None else {})})
        with patch("orchestrators.runway_browser_orchestrator.RunwayBrowserOrchestrator") as mock_orch_cls:
            instance = mock_orch_cls.return_value
            instance.run.return_value = []
            router = VideoProviderRouter()
            sentinel = lambda: False
            router.generate_clips(["demo"], provider_override="runway_browser", cancel_check=sentinel)
            _, kwargs = mock_call.call_args
            results.append(
                _pass(
                    "router_passes_cancel_check_browser",
                    kwargs.get("cancel_check") is sentinel,
                )
            )

    # Providers without cancel_check still work
    def _legacy_run(prompts):
        return ["/tmp/mock.mp4"]

    output = call_with_optional_cancel_check(_legacy_run, ["demo"], cancel_check=lambda: True)
    results.append(_pass("unsupported_provider_ignores_cancel_check", output == ["/tmp/mock.mp4"]))

    results.append(_pass("supports_cancel_check_runway_api", supports_cancel_check(RunwayVideoProvider.generate_clips)))
    results.append(_pass("supports_cancel_check_legacy_false", not supports_cancel_check(_legacy_run)))
    results.append(_pass("provider_accepts_runway_browser", provider_accepts_runtime_cancel("runway_browser")))
    results.append(_pass("provider_accepts_hailuo_browser", provider_accepts_runtime_cancel("hailuo_browser")))

    store = ExecutionSessionStore(root)
    engine = ProviderRuntimeEngine(store)
    session = _demo_session(root, "exec_11ee_cancel_api", provider="runway")
    store.save_session(session, overwrite=True)

    # ProviderRuntimeEngine passes cancel_check into router.generate_clips
    engine_calls: dict = {}
    artifact_root = store.artifact_dir("exec_11ee_cancel_api", "video_generation")

    with tempfile.TemporaryDirectory() as router_tmp:
        router_tmp_path = Path(router_tmp)

        class _RecordingRouter:
            def generate_clips(self, prompts, *, provider_override=None, cancel_check=None):
                engine_calls["cancel_check"] = cancel_check
                engine_calls["provider_override"] = provider_override
                marker = router_tmp_path / "clip_01.mock"
                marker.write_text("mock clip\n", encoding="utf-8")
                return [str(marker)]

        with patch("core.video_provider_router.VideoProviderRouter", _RecordingRouter):
            engine._execute_clips(
                ["demo"],
                "runway",
                artifact_root,
                RuntimePolicy(),
                session_id="exec_11ee_cancel_api",
            )
    results.append(
        _pass(
            "runtime_engine_passes_cancel_check",
            callable(engine_calls.get("cancel_check")),
            engine_calls.get("provider_override", ""),
        )
    )

    # Cooperative cancel during provider call -> CANCELLED (not FAILED)
    cancel_session_id = "exec_11ee_live_cancel"
    cancel_session = _demo_session(root, cancel_session_id, provider="runway")
    cancel_session["operations_control"] = {
        "cancel_requested": False,
        "cancel_reason": "validation live cancel",
        "cancelled_by": "validate",
    }
    store.save_session(cancel_session, overwrite=True)

    with tempfile.TemporaryDirectory() as tmp:
        partial_path = Path(tmp) / "clip_01.mp4"
        partial_path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 20))
        cancel_exc = RunwayCancelledError(
            "Runway API generation cancelled during between_clips",
            partial_paths=[str(partial_path)],
            phase="between_clips",
            details={
                "clip_results": [
                    finalize_download_artifact(
                        partial_path,
                        mode=MODE_API,
                        provider_id="runway",
                        clip_index=1,
                        partial=True,
                    )
                ]
            },
        )

        router_calls: dict = {}

        def _cancel_router(prompts, *, provider_override=None, cancel_check=None):
            router_calls["cancel_check"] = cancel_check
            assert cancel_check is not None
            loaded = store.load_session(cancel_session_id)
            control = dict(loaded.get("operations_control") or {})
            control["cancel_requested"] = True
            loaded["operations_control"] = control
            store.save_session(loaded, overwrite=True)
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
        results.append(_pass("not_completed_state", final.get("state") != "COMPLETED"))
        results.append(_pass("partial_source_file_not_deleted", partial_path.exists()))

    # Browser provider wiring smoke (mock orchestrator)
    browser_session_id = "exec_11ee_cancel_browser"
    browser_session = _demo_session(root, browser_session_id, provider="runway_browser")
    store.save_session(browser_session, overwrite=True)
    browser_calls: dict = {}

    def _browser_side_effect(prompts, *, provider_override=None, cancel_check=None):
        browser_calls["cancel_check"] = cancel_check
        raise RunwayCancelledError("browser cancel", partial_paths=[], phase="before_browser_launch")

    with patch.object(VideoProviderRouter, "generate_clips", side_effect=_browser_side_effect):
        browser_result = engine.dispatch_by_id(
            browser_session_id,
            actor="validate",
            policy=RuntimePolicy(require_queue_fingerprint=False, require_readiness=False),
        )
    browser_final = store.load_session(browser_session_id)
    results.append(_pass("browser_cancel_check_passed", callable(browser_calls.get("cancel_check"))))
    results.append(_pass("browser_dispatch_cancelled", browser_final.get("state") == STATE_CANCELLED))
    results.append(_pass("browser_not_failed", browser_final.get("state") != "FAILED"))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11e_b_still_passes", "project_brain.validate_11e_b_runway_api_hardening"),
            ("validate_11e_c_still_passes", "project_brain.validate_11e_c_runway_browser_hardening"),
            ("validate_11e_d_still_passes", "project_brain.validate_11e_d_runway_artifacts"),
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
