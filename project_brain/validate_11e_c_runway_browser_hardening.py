"""
Phase 11E-c — Runway browser mode hardening validation (mocks only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from content_brain.execution.runway_config import RUNWAY_BROWSER_ROUTER_KEY, RunwayConfigResolver
from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator
from providers.runway_api_errors import RunwayCancelledError, RunwayProviderError
from providers.runway_browser_support import browser_max_wait_seconds
from project_brain.validate_11e_common import append_regression_checks
from providers.runway_artifact_utils import (
    MIN_ARTIFACT_BYTES,
    MODE_BROWSER,
    RUNWAY_BROWSER_ROUTER_KEY,
    finalize_download_artifact,
)
from providers.runway_error_classifier import classify_runway_error
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from core.video_provider_router import VideoProviderRouter


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


class _FakePage:
    def __init__(self, body_text: str = "", video_sources=None):
        self.body_text = body_text
        self.video_sources = list(video_sources or [])
        self._poll = 0

    def evaluate(self, script):
        if "innerText" in script:
            return self.body_text
        if "querySelectorAll" in script and "visible" in script:
            return [
                {
                    "index": 0,
                    "src": src,
                    "width": 200,
                    "height": 200,
                    "top": 100,
                    "left": 0,
                    "visible": True,
                }
                for src in self.video_sources
            ]
        if "querySelectorAll" in script:
            return list(self.video_sources)
        return None


class _FakeBrowserProvider:
    def __init__(self, *, cancel_check=None, browser_manager=None, runway_obs=None, **_kwargs):
        self._cancel_check = cancel_check
        self._runway_obs = runway_obs
        self.browser = MagicMock()
        self.page = _FakePage()
        self.closed = False

    def start(self):
        return None

    def prepare_gen45_page(self):
        return None

    def fill_prompt(self, prompt):
        return None

    def prepare_clip_for_generate(self, prompt):
        self.fill_prompt(prompt)
        self.apply_default_settings()

    def apply_default_settings(self):
        return None

    def click_generate(self):
        return None

    def close(self):
        self.closed = True


class _FakeDownloadProvider:
    instances: list["_FakeDownloadProvider"] = []

    def __init__(self, *, cancel_check=None, output_dir=None):
        self._cancel_check = cancel_check
        self.output_dir = Path(output_dir or ".")
        self.browser = None
        self.page = None
        _FakeDownloadProvider.instances.append(self)

    def download_video_url(self, video_url, filename_prefix="runway_clip", *, clip_index=None):
        path = self.output_dir / f"{filename_prefix}.mp4"
        path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 100))
        return finalize_download_artifact(
            path,
            mode=MODE_BROWSER,
            provider_id=RUNWAY_BROWSER_ROUTER_KEY,
            clip_index=clip_index,
            source_url=video_url,
        )

    def close(self):
        return None


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    orchestrator_src = (root / "orchestrators" / "runway_browser_orchestrator.py").read_text(encoding="utf-8")
    results.append(_pass("no_infinite_sleep", "999999" not in orchestrator_src))

    config = RunwayConfigResolver(root).resolve()
    results.append(
        _pass(
            "active_default_runway_browser",
            config.active_video_provider == RUNWAY_BROWSER_ROUTER_KEY,
            config.active_video_provider,
        )
    )

    results.append(
        _pass(
            "waits_bounded_default",
            browser_max_wait_seconds() <= 900,
            str(browser_max_wait_seconds()),
        )
    )

    # Timeout during generation wait
    os.environ["RUNWAY_BROWSER_MAX_WAIT_SECONDS"] = "0"
    os.environ["RUNWAY_BROWSER_POLL_INTERVAL"] = "0"
    try:
        page = _FakePage(body_text="generating", video_sources=[])
        orch = RunwayBrowserOrchestrator(wait_seconds=0)
        try:
            orch.wait_for_generated_video_url(page, [], clip_index=1, max_wait_seconds=0)
            results.append(_pass("browser_timeout_taxonomy", False))
        except RunwayProviderError as exc:
            results.append(
                _pass(
                    "browser_timeout_taxonomy",
                    exc.code == "PROVIDER_TIMEOUT",
                    exc.code,
                )
            )
    finally:
        os.environ.pop("RUNWAY_BROWSER_MAX_WAIT_SECONDS", None)
        os.environ.pop("RUNWAY_BROWSER_POLL_INTERVAL", None)

    # Session unavailable
    page = _FakePage(body_text="Please log in to continue", video_sources=[])
    orch = RunwayBrowserOrchestrator(wait_seconds=1)
    try:
        orch.wait_for_generated_video_url(page, [], clip_index=1, max_wait_seconds=1)
        results.append(_pass("session_unavailable_taxonomy", False))
    except RunwayProviderError as exc:
        results.append(
            _pass(
                "session_unavailable_taxonomy",
                exc.code == "BROWSER_SESSION_INVALID",
                exc.code,
            )
        )

    # Cancel during wait
    calls = {"n": 0}

    def _cancel_check() -> bool:
        calls["n"] += 1
        return calls["n"] >= 2

    page = _FakePage(body_text="generating", video_sources=[])
    orch = RunwayBrowserOrchestrator(wait_seconds=5, cancel_check=_cancel_check)
    os.environ["RUNWAY_BROWSER_POLL_INTERVAL"] = "0"
    try:
        orch.wait_for_generated_video_url(
            page,
            [],
            clip_index=1,
            max_wait_seconds=5,
            cancel_check=_cancel_check,
        )
        results.append(_pass("cancel_during_wait", False))
    except RunwayCancelledError as exc:
        results.append(
            _pass(
                "cancel_during_wait",
                exc.cancelled and exc.phase == "generation_wait",
                exc.phase,
            )
        )
    finally:
        os.environ.pop("RUNWAY_BROWSER_POLL_INTERVAL", None)

    # Successful mocked orchestration
    _FakeDownloadProvider.instances = []

    class _SuccessPage(_FakePage):
        def __init__(self):
            super().__init__(body_text="ready", video_sources=[])
            self._ticks = 0

        def evaluate(self, script):
            if "querySelectorAll" in script and "visible" not in script:
                self._ticks += 1
                if self._ticks >= 2:
                    return ["https://cdn.test/clip1.mp4"]
                return []
            return super().evaluate(script)

    with tempfile.TemporaryDirectory() as tmp:
        fake_browser = _FakeBrowserProvider

        class _TmpDownload(_FakeDownloadProvider):
            def __init__(self, *, cancel_check=None, output_dir=None):
                super().__init__(cancel_check=cancel_check, output_dir=Path(tmp))

        def _browser_factory(**kwargs):
            provider = fake_browser(**kwargs)
            provider.page = _SuccessPage()
            return provider

        orch = RunwayBrowserOrchestrator(
            wait_seconds=5,
            browser_provider_cls=_browser_factory,
            download_provider_cls=_TmpDownload,
        )
        os.environ["RUNWAY_BROWSER_POLL_INTERVAL"] = "0"
        try:
            paths = orch.run(["test prompt"])
            meta = orch.clip_results[0] if orch.clip_results else {}
            results.append(
                _pass(
                    "artifact_metadata_compatible",
                    len(paths) == 1
                    and meta.get("file_path") == paths[0]
                    and meta.get("size_bytes", 0) >= MIN_ARTIFACT_BYTES
                    and meta.get("provider_id") == RUNWAY_BROWSER_ROUTER_KEY,
                    str(meta.get("size_bytes")),
                )
            )
        finally:
            os.environ.pop("RUNWAY_BROWSER_POLL_INTERVAL", None)

    # Download failure mapping
    from providers.runway_download_provider import RunwayDownloadProvider

    class _BadResponse:
        status_code = 500
        text = "server error"

        def iter_content(self, chunk_size=1024):
            return iter([])

    provider = RunwayDownloadProvider()
    provider._http_get = lambda url: _BadResponse()  # type: ignore[method-assign]
    try:
        provider.download_video_url("https://cdn.test/bad.mp4")
        results.append(_pass("download_failure_taxonomy", False))
    except RunwayProviderError as exc:
        results.append(_pass("download_failure_taxonomy", exc.code == "DOWNLOAD_FAILED", exc.code))

    results.append(
        _pass(
            "classifier_video_url_missing",
            classify_runway_error("No generated video URL detected") == "PROVIDER_TASK_FAILED",
        )
    )

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        RunwayBrowserOrchestrator(wait_seconds=1)
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        RunwayBrowserOrchestrator(wait_seconds=1)
        results.append(_pass("no_router_change", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11e_a_still_passes", "project_brain.validate_11e_a_runway_preflight"),
            ("validate_11e_b_still_passes", "project_brain.validate_11e_b_runway_api_hardening"),
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
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["summary"]["all_pass"] else 1)
