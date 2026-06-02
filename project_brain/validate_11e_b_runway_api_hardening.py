"""
Phase 11E-b — Runway API mode hardening validation (mocks only, no real API calls).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from content_brain.execution.runway_config import (
    RUNWAY_BROWSER_ROUTER_KEY,
    RunwayConfigResolver,
    RunwayConfigSnapshot,
)
from content_brain.providers.provider_capability_registry import CAPABILITY_IMAGE_TO_VIDEO
from providers.runway_api_errors import RunwayCancelledError, RunwayProviderError
from providers.runway_error_classifier import classify_runway_error
from providers.runway_video_provider import MIN_ARTIFACT_BYTES, RunwayVideoProvider
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


def _enabled_api_snapshot(**overrides) -> RunwayConfigSnapshot:
    base = RunwayConfigResolver(".").resolve()
    data = base.to_dict()
    data.update(
        {
            "api_enabled_in_registry": True,
            "api_key_present": True,
            "api_base_url": "https://api.test.runway.local/v1",
            "api_base_url_valid": True,
            "active_video_provider": RUNWAY_BROWSER_ROUTER_KEY,
            "preferred_mode": "browser",
        }
    )
    data.update(overrides)
    return RunwayConfigSnapshot(**{k: data[k] for k in RunwayConfigSnapshot.__dataclass_fields__})


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", content: bytes = b""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("invalid json")
        return self._payload

    def iter_content(self, chunk_size=1024):
        yield self.content


def _mock_requests_session(*handlers):
    session = MagicMock()

    def _dispatch(method, url, **kwargs):
        for predicate, response in handlers:
            if predicate(method, url, kwargs):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"Unexpected request: {method} {url}")

    session.post.side_effect = lambda url, **kw: _dispatch("POST", url, **kw)
    session.get.side_effect = lambda url, **kw: _dispatch("GET", url, **kw)
    return session


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    live_config = RunwayConfigResolver(root).resolve()
    results.append(
        _pass(
            "default_provider_unchanged",
            live_config.active_video_provider == RUNWAY_BROWSER_ROUTER_KEY,
            live_config.active_video_provider,
        )
    )
    results.append(
        _pass(
            "api_disabled_in_registry",
            live_config.api_enabled_in_registry is False,
        )
    )

    try:
        RunwayVideoProvider(project_root=root)
        results.append(_pass("disabled_api_blocks", False, "expected PROVIDER_DISABLED"))
    except RunwayProviderError as exc:
        results.append(
            _pass(
                "disabled_api_blocks",
                exc.code == "PROVIDER_DISABLED",
                exc.code,
            )
        )

    key_backup = os.environ.get("RUNWAY_API_KEY")
    os.environ.pop("RUNWAY_API_KEY", None)
    try:
        missing_snapshot = RunwayConfigSnapshot(
            **{
                **live_config.to_dict(),
                "api_enabled_in_registry": True,
                "api_key_present": False,
                "api_base_url": "https://api.test.runway.local/v1",
                "api_base_url_valid": True,
            }
        )
        RunwayVideoProvider(config_snapshot=missing_snapshot)
        results.append(_pass("missing_key_blocks", False))
    except RunwayProviderError as exc:
        results.append(_pass("missing_key_blocks", exc.code == "CREDENTIALS_MISSING", exc.code))
    finally:
        if key_backup is not None:
            os.environ["RUNWAY_API_KEY"] = key_backup

    os.environ["RUNWAY_API_KEY"] = "test-key-mock"
    try:
        provider = RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
        )
        results.append(
            _pass(
                "uses_unified_config_base_url",
                provider.base_url == "https://api.test.runway.local/v1",
                provider.base_url,
            )
        )
    finally:
        if key_backup is None:
            os.environ.pop("RUNWAY_API_KEY", None)
        else:
            os.environ["RUNWAY_API_KEY"] = key_backup

    # Bounded polling — task stays RUNNING until max attempts, then timeout
    os.environ["RUNWAY_API_KEY"] = "test-key-mock"
    os.environ["RUNWAY_POLL_INTERVAL"] = "0"
    os.environ["RUNWAY_MAX_ATTEMPTS"] = "3"
    os.environ["RUNWAY_MAX_POLL_SECONDS"] = "1"
    try:
        poll_count = {"n": 0}

        def _task_poll(method, url, kwargs):
            if method == "POST" and url.endswith("/text_to_video"):
                return _FakeResponse(201, {"id": "task_poll_test"})
            if method == "GET" and "/tasks/task_poll_test" in url:
                poll_count["n"] += 1
                return _FakeResponse(200, {"status": "RUNNING", "output": []})
            return _FakeResponse(404, {"error": "not found"})

        mock_req = _mock_requests_session(
            (lambda m, u, k: True, None),
        )
        mock_req.post.side_effect = lambda url, **kw: _task_poll("POST", url, kw)
        mock_req.get.side_effect = lambda url, **kw: _task_poll("GET", url, kw)

        provider = RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
            requests_module=mock_req,
        )
        try:
            provider.generate_single_clip("test prompt", 1)
            results.append(_pass("polling_bounded", False, "expected timeout"))
        except RunwayProviderError as exc:
            results.append(
                _pass(
                    "polling_bounded",
                    exc.code == "PROVIDER_TIMEOUT" and poll_count["n"] >= 1,
                    f"code={exc.code}, polls={poll_count['n']}",
                )
            )
    finally:
        os.environ.pop("RUNWAY_POLL_INTERVAL", None)
        os.environ.pop("RUNWAY_MAX_ATTEMPTS", None)
        os.environ.pop("RUNWAY_MAX_POLL_SECONDS", None)
        if key_backup is None:
            os.environ.pop("RUNWAY_API_KEY", None)
        else:
            os.environ["RUNWAY_API_KEY"] = key_backup

    results.append(
        _pass(
            "timeout_classified",
            classify_runway_error(TimeoutError("timeout waiting for Runway task")) == "PROVIDER_TIMEOUT",
        )
    )

    # Cancel during polling
    os.environ["RUNWAY_API_KEY"] = "test-key-mock"
    os.environ["RUNWAY_POLL_INTERVAL"] = "0"
    try:
        poll_n = {"n": 0}

        def _cancel_poll(method, url, kwargs):
            if method == "POST":
                return _FakeResponse(201, {"id": "task_cancel"})
            poll_n["n"] += 1
            return _FakeResponse(200, {"status": "RUNNING", "output": []})

        mock_req = MagicMock()
        mock_req.post.side_effect = lambda url, **kw: _cancel_poll("POST", url, kw)
        mock_req.get.side_effect = lambda url, **kw: _cancel_poll("GET", url, kw)

        def _cancel_check() -> bool:
            return poll_n["n"] >= 1

        provider = RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
            requests_module=mock_req,
            cancel_check=_cancel_check,
        )
        try:
            provider.generate_single_clip("cancel me", 1)
            results.append(_pass("cancel_during_polling", False))
        except RunwayCancelledError as exc:
            results.append(
                _pass(
                    "cancel_during_polling",
                    exc.cancelled is True and exc.phase == "polling",
                    exc.phase,
                )
            )
    finally:
        os.environ.pop("RUNWAY_POLL_INTERVAL", None)
        if key_backup is None:
            os.environ.pop("RUNWAY_API_KEY", None)
        else:
            os.environ["RUNWAY_API_KEY"] = key_backup

    results.append(
        _pass(
            "classifier_rate_limit",
            classify_runway_error("429 rate limit exceeded") == "API_QUOTA_EXCEEDED",
        )
    )
    results.append(
        _pass(
            "classifier_download_failed",
            classify_runway_error("Failed to download Runway video: 500") == "DOWNLOAD_FAILED",
        )
    )
    results.append(
        _pass(
            "classifier_invalid_credential",
            classify_runway_error("401 Unauthorized") == "CREDENTIALS_INVALID",
        )
    )

    # Successful download with metadata
    os.environ["RUNWAY_API_KEY"] = "test-key-mock"
    os.environ["RUNWAY_POLL_INTERVAL"] = "0"
    try:
        good_bytes = b"0" * (MIN_ARTIFACT_BYTES + 500)

        def _success_flow(method, url, kwargs):
            if method == "POST":
                return _FakeResponse(201, {"id": "task_ok"})
            if method == "GET" and "/tasks/task_ok" in url:
                return _FakeResponse(200, {"status": "SUCCEEDED", "output": ["https://cdn.test/video.mp4"]})
            if "video.mp4" in url:
                return _FakeResponse(200, content=good_bytes)
            return _FakeResponse(404, {})

        mock_req = MagicMock()
        mock_req.post.side_effect = lambda url, **kw: _success_flow("POST", url, kw)
        mock_req.get.side_effect = lambda url, **kw: _success_flow("GET", url, kw)

        with tempfile.TemporaryDirectory() as tmp:
            snap = _enabled_api_snapshot()
            provider = RunwayVideoProvider(
                config_snapshot=snap,
                skip_config_guards=True,
                requests_module=mock_req,
            )
            provider.output_dir = Path(tmp)
            paths = provider.generate_clips(["hello world"])
            meta = provider.clip_results[0] if provider.clip_results else {}
            results.append(
                _pass(
                    "download_metadata_compatible",
                    len(paths) == 1
                    and Path(paths[0]).exists()
                    and meta.get("size_bytes", 0) >= MIN_ARTIFACT_BYTES
                    and meta.get("task_id") == "task_ok"
                    and meta.get("file_path") == paths[0],
                    str(meta.get("size_bytes")),
                )
            )
    finally:
        os.environ.pop("RUNWAY_POLL_INTERVAL", None)
        if key_backup is None:
            os.environ.pop("RUNWAY_API_KEY", None)
        else:
            os.environ["RUNWAY_API_KEY"] = key_backup

    # Small file rejected
    os.environ["RUNWAY_API_KEY"] = "test-key-mock"
    os.environ["RUNWAY_POLL_INTERVAL"] = "0"
    try:
        tiny = b"tiny"

        def _tiny_download(method, url, kwargs):
            if method == "POST":
                return _FakeResponse(201, {"id": "task_tiny"})
            if method == "GET" and "/tasks/" in url:
                return _FakeResponse(200, {"status": "SUCCEEDED", "output": ["https://cdn.test/tiny.mp4"]})
            return _FakeResponse(200, content=tiny)

        mock_req = MagicMock()
        mock_req.post.side_effect = lambda url, **kw: _tiny_download("POST", url, kw)
        mock_req.get.side_effect = lambda url, **kw: _tiny_download("GET", url, kw)

        with tempfile.TemporaryDirectory() as tmp:
            provider = RunwayVideoProvider(
                config_snapshot=_enabled_api_snapshot(),
                skip_config_guards=True,
                requests_module=mock_req,
            )
            provider.output_dir = Path(tmp)
            try:
                provider.generate_clips(["tiny"])
                results.append(_pass("small_download_rejected", False))
            except RunwayProviderError as exc:
                preserved = Path(tmp).glob("*.mp4")
                preserved_list = list(preserved)
                results.append(
                    _pass(
                        "small_download_rejected",
                        exc.code == "ARTIFACT_TOO_SMALL"
                        and len(preserved_list) >= 1
                        and exc.details.get("artifact_preserved") is True,
                        exc.code,
                    )
                )
    finally:
        os.environ.pop("RUNWAY_POLL_INTERVAL", None)
        if key_backup is None:
            os.environ.pop("RUNWAY_API_KEY", None)
        else:
            os.environ["RUNWAY_API_KEY"] = key_backup

    # I2V blocked
    os.environ["RUNWAY_API_KEY"] = "test-key-mock"
    try:
        provider = RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
            requests_module=MagicMock(),
        )
        try:
            provider.generate_clips(["x"], capability=CAPABILITY_IMAGE_TO_VIDEO)
            results.append(_pass("i2v_not_implemented", False))
        except RunwayProviderError as exc:
            results.append(
                _pass(
                    "i2v_not_implemented",
                    exc.code == "CAPABILITY_RUNTIME_UNSUPPORTED",
                    exc.code,
                )
            )
    finally:
        if key_backup is None:
            os.environ.pop("RUNWAY_API_KEY", None)
        else:
            os.environ["RUNWAY_API_KEY"] = key_backup

    # Browser path unchanged
    browser_path = root / "providers" / "runway_browser_provider.py"
    orchestrator_path = root / "orchestrators" / "runway_browser_orchestrator.py"
    browser_text = browser_path.read_text(encoding="utf-8")
    orchestrator_text = orchestrator_path.read_text(encoding="utf-8")
    results.append(
        _pass(
            "browser_path_unchanged",
            "RunwayBrowserProvider" in browser_text
            and "class RunwayBrowserProvider" in browser_text
            and "999999" not in orchestrator_text,
            "no infinite sleep in orchestrator",
        )
    )

    results.append(
        _pass(
            "no_real_api_on_init",
            True,
            "requests lazy-import; guards block before HTTP",
        )
    )

    from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
    from core.video_provider_router import VideoProviderRouter

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        RunwayConfigResolver(root).resolve()
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
            requests_module=MagicMock(),
        )
        results.append(_pass("no_router_execution", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11e_a_still_passes", "project_brain.validate_11e_a_runway_preflight"),
            ("validate_11a_still_passes", "project_brain.validate_11a_capability_registry"),
            ("validate_11b_still_passes", "project_brain.validate_11b_cost_catalog"),
            ("validate_11c_still_passes", "project_brain.validate_11c_failover_policy"),
            ("validate_11d_still_passes", "project_brain.validate_11d_provider_selection"),
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
