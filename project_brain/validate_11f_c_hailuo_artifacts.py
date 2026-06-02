"""
Phase 11F-c — Hailuo artifact continuity validation (mock files only).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from content_brain.execution.artifact_validation_engine import ArtifactValidationEngine
from content_brain.execution.hailuo_config import DEFAULT_ACTIVE_VIDEO_PROVIDER, HAILUO_BROWSER_ROUTER_KEY
from orchestrators.hailuo_multi_clip_orchestrator import HailuoMultiClipOrchestrator
from providers.hailuo_api_errors import HailuoCancelledError, HailuoProviderError
from providers.hailuo_artifact_utils import (
    MIN_ARTIFACT_BYTES,
    MODE_BROWSER,
    REQUIRED_ARTIFACT_FIELDS,
    build_job_id,
    clip_result_paths,
    compute_sha256,
    finalize_download_artifact,
    is_valid_source_url,
    mark_clip_results_partial,
    normalize_artifact_record,
    partial_artifact_bundle,
    require_file_path,
)
from providers.hailuo_error_classifier import classify_hailuo_error
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


def _has_required_fields(record: dict) -> bool:
    return REQUIRED_ARTIFACT_FIELDS.issubset(set(record.keys()))


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    with tempfile.TemporaryDirectory() as tmp:
        good_path = Path(tmp) / "hailuo_clip_01.mp4"
        good_path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 50))

        browser_record = finalize_download_artifact(
            good_path,
            mode=MODE_BROWSER,
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            clip_index=1,
            task_id=build_job_id(clip_index=1),
            source_url="https://cdn.test/hailuo.mp4",
        )
        results.append(
            _pass(
                "browser_artifact_record_shape",
                _has_required_fields(browser_record)
                and browser_record["mode"] == MODE_BROWSER
                and browser_record["provider_id"] == HAILUO_BROWSER_ROUTER_KEY
                and browser_record["job_id"] == build_job_id(clip_index=1)
                and browser_record["sha256"] is not None,
                browser_record.get("validation_status", ""),
            )
        )

        download_record = finalize_download_artifact(
            good_path,
            mode=MODE_BROWSER,
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            clip_index=2,
            source_url="blob:https://hailuoai.video/asset/abc",
        )
        results.append(
            _pass(
                "download_artifact_record_shape",
                _has_required_fields(download_record)
                and download_record["clip_index"] == 2
                and download_record["artifact_preserved"] is True,
            )
        )

        small_path = Path(tmp) / "small.mp4"
        small_path.write_bytes(b"tiny")
        try:
            finalize_download_artifact(
                small_path,
                mode=MODE_BROWSER,
                provider_id=HAILUO_BROWSER_ROUTER_KEY,
                clip_index=3,
            )
            results.append(_pass("too_small_artifact_flagged", False))
        except HailuoProviderError as exc:
            results.append(
                _pass(
                    "too_small_artifact_flagged",
                    exc.code == "ARTIFACT_TOO_SMALL"
                    and small_path.exists()
                    and exc.details.get("artifact_preserved") is True,
                    exc.code,
                )
            )

        try:
            require_file_path(None)
            results.append(_pass("missing_file_path_blocked", False))
        except HailuoProviderError as exc:
            results.append(_pass("missing_file_path_blocked", exc.code == "ARTIFACT_NULL_PATH", exc.code))

        results.append(_pass("invalid_source_url_rejected", is_valid_source_url("") is False))
        try:
            finalize_download_artifact(
                good_path,
                mode=MODE_BROWSER,
                provider_id=HAILUO_BROWSER_ROUTER_KEY,
                clip_index=4,
                source_url="not-a-valid-url",
            )
            results.append(_pass("invalid_source_url_blocked", False))
        except HailuoProviderError as exc:
            results.append(
                _pass(
                    "invalid_source_url_blocked",
                    exc.code == "DOWNLOAD_FAILED"
                    and classify_hailuo_error(str(exc)) == "DOWNLOAD_FAILED",
                    exc.code,
                )
            )

        sha = compute_sha256(good_path)
        results.append(_pass("sha256_available", sha is not None and sha.startswith("sha256:")))

        partial = mark_clip_results_partial([browser_record])
        bundle = partial_artifact_bundle(partial, [str(good_path)])
        results.append(
            _pass(
                "partial_artifact_preservation",
                bundle["partial"] is True
                and bundle["artifact_preserved"] is True
                and len(bundle["clip_results"]) == 1
                and bundle["clip_results"][0]["partial"] is True
                and bundle["clip_results"][0]["artifact_preserved"] is True,
            )
        )

        results.append(
            _pass(
                "clip_result_paths_no_none",
                clip_result_paths([browser_record]) == [str(good_path)],
            )
        )
        try:
            clip_result_paths([{"clip_index": 1}])
            results.append(_pass("clip_result_paths_blocks_missing", False))
        except HailuoProviderError as exc:
            results.append(_pass("clip_result_paths_blocks_missing", exc.code == "ARTIFACT_NULL_PATH"))

        engine = ArtifactValidationEngine()
        validation = engine.validate(
            [
                {
                    "artifact_id": "art_hailuo_test",
                    "artifact_type": "video_clip",
                    "provider": HAILUO_BROWSER_ROUTER_KEY,
                    "file_path": str(good_path),
                    "clip_number": 1,
                    "metadata": {"hailuo_clip_result": browser_record},
                }
            ],
            clip_target=1,
            min_artifact_bytes=MIN_ARTIFACT_BYTES,
        )
        results.append(_pass("artifact_validation_engine_passes", validation.passed is True))

        normalized_for_session = normalize_artifact_record(
            file_path=str(good_path),
            mode=MODE_BROWSER,
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            clip_index=1,
            metadata={"hailuo_clip_result": browser_record},
        )
        results.append(
            _pass(
                "session_metadata_compatible",
                normalized_for_session["file_path"] == str(good_path)
                and isinstance(normalized_for_session.get("metadata"), dict),
            )
        )

    # Orchestrator cancel partial bundle (mock)
    class _FakePage:
        def evaluate(self, script):
            if "innerText" in script:
                return "ready"
            return []

        def wait_for_load_state(self, *_a, **_k):
            return None

        def locator(self, *_a, **_k):
            m = MagicMock()
            m.count.return_value = 0
            return m

    class _FakeBrowser:
        def __init__(self, **kwargs):
            self.page = _FakePage()
            self.browser = MagicMock()

        def start(self):
            return None

        def open_hailuo(self):
            return None

        def fill_prompt(self, _p):
            return None

        def click_create(self):
            return None

        def close(self):
            return None

    class _FakeDownload:
        def __init__(self, **kwargs):
            self.browser = None
            self.page = None

        def open_assets(self):
            return None

        def open_video_for_clip(self, *, clip_index=None):
            return True

        def extract_and_save_video(self, *, clip_index=None):
            with tempfile.TemporaryDirectory() as tmp2:
                path = Path(tmp2) / f"clip_{clip_index}.mp4"
                path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 10))
                return finalize_download_artifact(
                    path,
                    mode=MODE_BROWSER,
                    provider_id=HAILUO_BROWSER_ROUTER_KEY,
                    clip_index=clip_index,
                    source_url="https://cdn.test/partial.mp4",
                )

        def close(self):
            return None

    cancel_flag = {"n": 0}

    def _cancel_check():
        cancel_flag["n"] += 1
        return cancel_flag["n"] >= 2

    orch = HailuoMultiClipOrchestrator(
        browser_provider_cls=_FakeBrowser,
        download_provider_cls=_FakeDownload,
        cancel_check=_cancel_check,
    )

    def _cancel_wait(page, *, before_sources, clip_index, cancel_check, partial_paths):
        from providers.hailuo_browser_support import check_cancel

        check_cancel(cancel_check, "generation_wait", partial_paths=partial_paths, clip_results=orch.clip_results)

    orch._wait_for_generation = _cancel_wait  # type: ignore[method-assign]

    with tempfile.TemporaryDirectory() as tmp3:
        class _PersistDownload(_FakeDownload):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.output_dir = Path(tmp3)

            def extract_and_save_video(self, *, clip_index=None):
                path = self.output_dir / f"clip_{clip_index}.mp4"
                path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 10))
                return finalize_download_artifact(
                    path,
                    mode=MODE_BROWSER,
                    provider_id=HAILUO_BROWSER_ROUTER_KEY,
                    clip_index=clip_index,
                    source_url="https://cdn.test/partial.mp4",
                )

        orch._download_provider_cls = _PersistDownload
        try:
            orch.run(["one", "two"])
            results.append(_pass("orchestrator_cancel_partial_bundle", False))
        except HailuoCancelledError as exc:
            results.append(
                _pass(
                    "orchestrator_cancel_partial_bundle",
                    exc.details.get("partial") is True
                    and exc.details.get("artifact_preserved") is True
                    and "clip_results" in exc.details,
                )
            )

    results.append(
        _pass(
            "active_default_runway_browser",
            DEFAULT_ACTIVE_VIDEO_PROVIDER == "runway_browser",
        )
    )

    results.append(
        _pass(
            "cancel_during_download_classified",
            classify_hailuo_error("Hailuo browser cancelled during download_stream") == "OPERATIONS_CANCELLED",
        )
    )

    with patch("core.video_provider_router.VideoProviderRouter.generate_clips") as mock_router:
        mock_router.side_effect = AssertionError("router unchanged")
        with tempfile.TemporaryDirectory() as tmp4:
            p = Path(tmp4) / "noop.mp4"
            p.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 1))
            normalize_artifact_record(
                file_path=str(p),
                mode=MODE_BROWSER,
                provider_id=HAILUO_BROWSER_ROUTER_KEY,
                clip_index=1,
            )
        results.append(_pass("no_router_dispatch_change", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11f_a_still_passes", "project_brain.validate_11f_a_hailuo_preflight"),
            ("validate_11f_b_still_passes", "project_brain.validate_11f_b_hailuo_browser_hardening"),
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
