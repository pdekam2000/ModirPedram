"""
Phase 11F-b — Hailuo browser mode hardening validation (mocks only).
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

from content_brain.execution.hailuo_config import DEFAULT_ACTIVE_VIDEO_PROVIDER, HailuoConfigResolver
from orchestrators.hailuo_multi_clip_orchestrator import (
    HailuoMultiClipOrchestrator,
    SESSION_REUSE_MODE,
)
from providers.hailuo_api_errors import HailuoCancelledError, HailuoProviderError
from providers.hailuo_artifact_utils import (
    HAILUO_BROWSER_ROUTER_KEY,
    MIN_ARTIFACT_BYTES,
    MODE_BROWSER,
    finalize_download_artifact,
    partial_artifact_bundle,
)
from providers.hailuo_browser_support import browser_max_wait_seconds
from providers.hailuo_error_classifier import classify_hailuo_error
from project_brain.validate_11e_common import append_regression_checks
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
        self.url = "https://hailuoai.video/mine/detail"
        self._poll = 0

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def evaluate(self, script):
        if "innerText" in script:
            return self.body_text
        if "querySelectorAll" in script and "video" in script:
            return list(self.video_sources)
        return None

    def locator(self, selector):
        mock = MagicMock()
        if selector == "video":
            mock.count.return_value = len(self.video_sources)
            mock.nth.return_value = MagicMock()
        elif "contenteditable" in selector:
            mock.first = MagicMock()
        return mock

    @property
    def keyboard(self):
        return MagicMock()


class _FakeBrowserProvider:
    instances: list["_FakeBrowserProvider"] = []

    def __init__(self, *, cancel_check=None, browser_manager=None):
        self._cancel_check = cancel_check
        self.browser = MagicMock()
        self.page = _FakePage(body_text="generating", video_sources=[])
        self.closed = False
        _FakeBrowserProvider.instances.append(self)

    def start(self):
        return None

    def open_hailuo(self):
        return None

    def fill_prompt(self, prompt):
        return None

    def click_create(self):
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

    def open_assets(self):
        return None

    def open_video_for_clip(self, *, clip_index=None):
        return True

    def open_latest_video_by_video_element(self, *, clip_index=None):
        return self.open_video_for_clip(clip_index=clip_index)

    def extract_and_save_video(self, *, clip_index=None):
        path = self.output_dir / f"hailuo_clip_{clip_index or 0}.mp4"
        path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 100))
        return finalize_download_artifact(
            path,
            mode=MODE_BROWSER,
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            clip_index=clip_index,
            source_url="https://example.test/video.mp4",
        )

    def close(self):
        return None


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    orchestrator_src = (root / "orchestrators" / "hailuo_multi_clip_orchestrator.py").read_text(encoding="utf-8")
    results.append(_pass("no_fixed_150_sleep", "sleep(150)" not in orchestrator_src))
    results.append(_pass("bounded_polling_present", "_wait_for_generation" in orchestrator_src))
    results.append(_pass("monotonic_deadline_used", "time.monotonic()" in orchestrator_src))

    config = HailuoConfigResolver(root).resolve()
    results.append(
        _pass(
            "active_default_runway_browser",
            config.active_video_provider == DEFAULT_ACTIVE_VIDEO_PROVIDER,
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

    results.append(
        _pass(
            "session_reuse_documented",
            SESSION_REUSE_MODE == "single_session_per_run",
            SESSION_REUSE_MODE,
        )
    )

    router_src = (root / "core" / "video_provider_router.py").read_text(encoding="utf-8")
    results.append(_pass("router_no_wait_seconds_150", "wait_seconds=150" not in router_src))

    # Timeout during generation wait
    os.environ["HAILUO_BROWSER_MAX_WAIT_SECONDS"] = "0"
    os.environ["HAILUO_BROWSER_POLL_INTERVAL"] = "0"
    try:
        _FakeBrowserProvider.instances.clear()
        _FakeDownloadProvider.instances.clear()
        timeout_orch = HailuoMultiClipOrchestrator(
            wait_seconds=0,
            browser_provider_cls=_FakeBrowserProvider,
            download_provider_cls=_FakeDownloadProvider,
        )
        try:
            timeout_orch.run(["prompt"])
            results.append(_pass("timeout_raises", False, "expected PROVIDER_TIMEOUT"))
        except HailuoProviderError as exc:
            results.append(
                _pass(
                    "timeout_raises",
                    exc.code == "PROVIDER_TIMEOUT",
                    exc.code,
                )
            )
            results.append(
                _pass(
                    "timeout_classified",
                    classify_hailuo_error(str(exc)) == "PROVIDER_TIMEOUT",
                )
            )
    finally:
        os.environ.pop("HAILUO_BROWSER_MAX_WAIT_SECONDS", None)
        os.environ.pop("HAILUO_BROWSER_POLL_INTERVAL", None)

    # Download failure
    class _FailDownload(_FakeDownloadProvider):
        def open_video_for_clip(self, *, clip_index=None):
            return False

        def open_latest_video_by_video_element(self, *, clip_index=None):
            return False

    _FakeBrowserProvider.instances.clear()
    _FakeDownloadProvider.instances.clear()
    fail_orch = HailuoMultiClipOrchestrator(
        browser_provider_cls=_FakeBrowserProvider,
        download_provider_cls=_FailDownload,
    )

    class _ReadyPage(_FakePage):
        def __init__(self):
            super().__init__(body_text="ready download", video_sources=["https://x/v.mp4"])

    def _ready_wait(page, *, before_sources, clip_index, cancel_check, partial_paths):
        return None

    fail_orch._wait_for_generation = _ready_wait  # type: ignore[method-assign]
    try:
        fail_orch.run(["prompt"])
        results.append(_pass("download_failure_raises", False))
    except HailuoProviderError as exc:
        results.append(
            _pass(
                "download_failure_raises",
                exc.code == "DOWNLOAD_FAILED",
                exc.code,
            )
        )
        results.append(
            _pass(
                "download_failure_classified",
                classify_hailuo_error(str(exc)) == "DOWNLOAD_FAILED",
            )
        )

    # Cancel during generation wait
    _FakeBrowserProvider.instances.clear()
    _FakeDownloadProvider.instances.clear()
    cancel_flag = {"value": False}

    def _cancel_check():
        return cancel_flag["value"]

    cancel_orch = HailuoMultiClipOrchestrator(
        browser_provider_cls=_FakeBrowserProvider,
        download_provider_cls=_FakeDownloadProvider,
        cancel_check=_cancel_check,
    )

    def _slow_wait(page, *, before_sources, clip_index, cancel_check, partial_paths):
        cancel_flag["value"] = True
        time.sleep(0.01)
        from providers.hailuo_browser_support import check_cancel

        check_cancel(_cancel_check, "generation_wait", partial_paths=[], clip_results=[])

    cancel_orch._wait_for_generation = _slow_wait  # type: ignore[method-assign]
    try:
        cancel_orch.run(["prompt"])
        results.append(_pass("cancel_exits_cleanly", False))
    except HailuoCancelledError as exc:
        results.append(_pass("cancel_exits_cleanly", exc.code == "OPERATIONS_CANCELLED", exc.code))
        results.append(_pass("cancel_classified", classify_hailuo_error(str(exc)) == "OPERATIONS_CANCELLED"))

    # Session reuse: one browser provider start, downloader shares browser
    _FakeBrowserProvider.instances.clear()
    _FakeDownloadProvider.instances.clear()

    class _PollReadyPage(_FakePage):
        def __init__(self):
            super().__init__(body_text="ready", video_sources=["https://x/new.mp4"])

    class _ReuseBrowser(_FakeBrowserProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.page = _PollReadyPage()

    def _instant_ready(page, *, before_sources, clip_index, cancel_check, partial_paths):
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        class _ReuseDownload(_FakeDownloadProvider):
            def __init__(self, **kwargs):
                super().__init__(output_dir=tmp_path, **kwargs)

        reuse_orch = HailuoMultiClipOrchestrator(
            browser_provider_cls=_ReuseBrowser,
            download_provider_cls=_ReuseDownload,
        )
        reuse_orch._wait_for_generation = _instant_ready  # type: ignore[method-assign]
        paths = reuse_orch.run(["clip-a", "clip-b"])
        results.append(_pass("session_reuse_single_start", len(_FakeBrowserProvider.instances) == 1))
        results.append(
            _pass(
                "downloader_shares_browser",
                len(_FakeDownloadProvider.instances) >= 1
                and _FakeDownloadProvider.instances[-1].browser is _FakeBrowserProvider.instances[0].browser,
            )
        )
        results.append(_pass("returns_paths_no_none", len(paths) == 2 and all(paths)))

    # Artifact metadata shape
    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "clip.mp4"
        artifact_path.write_bytes(b"x" * (MIN_ARTIFACT_BYTES + 50))
        record = finalize_download_artifact(artifact_path, clip_index=1)
        required = {"file_path", "provider_id", "mode", "clip_index", "size_bytes", "validation_status"}
        results.append(
            _pass(
                "artifact_metadata_shape",
                required.issubset(record.keys()) and record["provider_id"] == HAILUO_BROWSER_ROUTER_KEY,
                ",".join(sorted(record.keys())),
            )
        )

    # Partial artifact bundle
    bundle = partial_artifact_bundle(
        [{"file_path": "/tmp/a.mp4", "validation_status": "valid", "partial": False}],
        ["/tmp/a.mp4"],
    )
    results.append(
        _pass(
            "partial_artifact_preservation",
            bundle.get("partial") is True and len(bundle.get("clip_results") or []) == 1,
        )
    )

    results.append(
        _pass(
            "selector_error_classified",
            classify_hailuo_error("selector not found on page") == "BROWSER_AUTOMATION_NOT_READY",
        )
    )

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        HailuoMultiClipOrchestrator(
            browser_provider_cls=_FakeBrowserProvider,
            download_provider_cls=_FakeDownloadProvider,
        )
        results.append(_pass("no_router_execution_in_unit", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11f_a_still_passes", "project_brain.validate_11f_a_hailuo_preflight"),
            ("validate_11e_matrix_still_passes", "project_brain.validate_11e_matrix"),
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
