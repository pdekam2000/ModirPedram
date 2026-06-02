"""
Phase 11E-d — Runway artifact continuity validation (mock files only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from content_brain.execution.artifact_validation_engine import ArtifactValidationEngine
from content_brain.execution.runway_config import RUNWAY_BROWSER_ROUTER_KEY, RunwayConfigResolver
from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator
from providers.runway_api_errors import RunwayCancelledError, RunwayProviderError
from providers.runway_artifact_utils import (
    MIN_ARTIFACT_BYTES,
    MODE_API,
    MODE_BROWSER,
    compute_sha256,
    finalize_download_artifact,
    mark_clip_results_partial,
    normalize_artifact_record,
    partial_artifact_bundle,
    require_file_path,
)
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


REQUIRED_FIELDS = {
    "file_path",
    "provider",
    "provider_id",
    "mode",
    "capability",
    "clip_index",
    "size_bytes",
    "downloaded_at",
    "validation_status",
    "partial",
}


def _has_required_fields(record: dict) -> bool:
    return REQUIRED_FIELDS.issubset(set(record.keys()))


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    with tempfile.TemporaryDirectory() as tmp:
        good_path = Path(tmp) / "api_clip.mp4"
        good_path.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 50))

        api_record = finalize_download_artifact(
            good_path,
            mode=MODE_API,
            provider_id="runway",
            clip_index=1,
            task_id="task_123",
            source_url="https://cdn.test/a.mp4",
        )
        results.append(
            _pass(
                "api_artifact_record_shape",
                _has_required_fields(api_record)
                and api_record["mode"] == MODE_API
                and api_record["provider_id"] == "runway"
                and api_record["sha256"] is not None,
                api_record.get("validation_status", ""),
            )
        )

        browser_record = finalize_download_artifact(
            good_path,
            mode=MODE_BROWSER,
            provider_id=RUNWAY_BROWSER_ROUTER_KEY,
            clip_index=1,
            source_url="https://cdn.test/b.mp4",
        )
        results.append(
            _pass(
                "browser_artifact_record_shape",
                _has_required_fields(browser_record)
                and browser_record["mode"] == MODE_BROWSER
                and browser_record["provider_id"] == RUNWAY_BROWSER_ROUTER_KEY,
                browser_record.get("provider_id", ""),
            )
        )

        small_path = Path(tmp) / "small.mp4"
        small_path.write_bytes(b"tiny")
        try:
            finalize_download_artifact(
                small_path,
                mode=MODE_API,
                provider_id="runway",
                clip_index=2,
            )
            results.append(_pass("too_small_artifact_flagged", False))
        except RunwayProviderError as exc:
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
        except RunwayProviderError as exc:
            results.append(_pass("missing_file_path_blocked", exc.code == "ARTIFACT_NULL_PATH", exc.code))

        sha = compute_sha256(good_path)
        results.append(_pass("sha256_available", sha is not None and sha.startswith("sha256:")))

        partial = mark_clip_results_partial([api_record])
        bundle = partial_artifact_bundle(partial, [str(good_path)])
        results.append(
            _pass(
                "partial_artifact_preservation",
                bundle["partial"] is True
                and len(bundle["clip_results"]) == 1
                and bundle["clip_results"][0]["partial"] is True
                and bundle["clip_results"][0]["validation_status"] == "partial",
            )
        )

        # 10J-e compatibility
        engine = ArtifactValidationEngine()
        validation = engine.validate(
            [
                {
                    "artifact_id": "art_test",
                    "artifact_type": "video_clip",
                    "provider": "runway",
                    "file_path": str(good_path),
                    "clip_number": 1,
                    "metadata": {},
                }
            ],
            clip_target=1,
            min_artifact_bytes=MIN_ARTIFACT_BYTES,
        )
        results.append(_pass("artifact_validation_engine_passes", validation.passed is True))

        normalized_for_session = normalize_artifact_record(
            file_path=str(good_path),
            mode=MODE_BROWSER,
            provider_id=RUNWAY_BROWSER_ROUTER_KEY,
            clip_index=1,
            metadata={"runway_clip_result": browser_record},
        )
        results.append(
            _pass(
                "session_metadata_compatible",
                normalized_for_session["file_path"] == str(good_path)
                and isinstance(normalized_for_session.get("metadata"), dict),
            )
        )

    # API mock clip_results via provider
    os.environ["RUNWAY_API_KEY"] = "test-key"
    os.environ["RUNWAY_POLL_INTERVAL"] = "0"

    class _FakeResponse:
        def __init__(self, status_code, payload=None, content=b""):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload or {})
            self.content = content

        def json(self):
            return self._payload

        def iter_content(self, chunk_size=1024):
            yield self.content

    def _flow(method, url, kwargs):
        if method == "POST":
            return _FakeResponse(201, {"id": "task_d"})
        if "/tasks/" in url:
            return _FakeResponse(200, {"status": "SUCCEEDED", "output": ["https://cdn.test/d.mp4"]})
        return _FakeResponse(200, content=b"0" * (MIN_ARTIFACT_BYTES + 10))

    mock_req = MagicMock()
    mock_req.post.side_effect = lambda url, **kw: _flow("POST", url, kw)
    mock_req.get.side_effect = lambda url, **kw: _flow("GET", url, kw)

    from project_brain.validate_11e_b_runway_api_hardening import _enabled_api_snapshot

    with tempfile.TemporaryDirectory() as tmp:
        provider = RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
            requests_module=mock_req,
        )
        provider.output_dir = Path(tmp)
        paths = provider.generate_clips(["demo"])
        meta = provider.clip_results[0] if provider.clip_results else {}
        results.append(
            _pass(
                "api_provider_clip_results_normalized",
                _has_required_fields(meta) and meta["file_path"] == paths[0],
                meta.get("validation_status", ""),
            )
        )

    os.environ.pop("RUNWAY_API_KEY", None)
    os.environ.pop("RUNWAY_POLL_INTERVAL", None)

    # Cancel partial bundle on API provider
    os.environ["RUNWAY_API_KEY"] = "test-key"
    os.environ["RUNWAY_POLL_INTERVAL"] = "0"
    poll = {"n": 0}

    def _poll_flow(method, url, kwargs):
        if method == "POST":
            return _FakeResponse(201, {"id": "task_cancel"})
        poll["n"] += 1
        return _FakeResponse(200, {"status": "RUNNING", "output": []})

    mock_req2 = MagicMock()
    mock_req2.post.side_effect = lambda url, **kw: _poll_flow("POST", url, kw)
    mock_req2.get.side_effect = lambda url, **kw: _poll_flow("GET", url, kw)

    with tempfile.TemporaryDirectory() as tmp:
        provider = RunwayVideoProvider(
            config_snapshot=_enabled_api_snapshot(),
            skip_config_guards=True,
            requests_module=mock_req2,
        )
        provider.output_dir = Path(tmp)
        calls = {"n": 0}

        def _cancel():
            calls["n"] += 1
            return calls["n"] >= 2

        try:
            provider.generate_clips(["one"], cancel_check=_cancel)
            results.append(_pass("api_cancel_partial_bundle", False))
        except RunwayCancelledError as exc:
            results.append(
                _pass(
                    "api_cancel_partial_bundle",
                    exc.details.get("partial") is True and "clip_results" in exc.details,
                )
            )

    os.environ.pop("RUNWAY_API_KEY", None)
    os.environ.pop("RUNWAY_POLL_INTERVAL", None)

    results.append(
        _pass(
            "active_default_runway_browser",
            RunwayConfigResolver(root).resolve().active_video_provider == RUNWAY_BROWSER_ROUTER_KEY,
        )
    )

    with patch("core.video_provider_router.VideoProviderRouter.generate_clips") as mock_router:
        mock_router.side_effect = AssertionError("router unchanged")
        with tempfile.TemporaryDirectory() as tmp2:
            p = Path(tmp2) / "noop.mp4"
            p.write_bytes(b"0" * (MIN_ARTIFACT_BYTES + 1))
            normalize_artifact_record(
                file_path=str(p),
                mode=MODE_BROWSER,
                provider_id=RUNWAY_BROWSER_ROUTER_KEY,
                clip_index=1,
            )
        results.append(_pass("no_router_dispatch_change", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
            ("validate_11e_a_still_passes", "project_brain.validate_11e_a_runway_preflight"),
            ("validate_11e_b_still_passes", "project_brain.validate_11e_b_runway_api_hardening"),
            ("validate_11e_c_still_passes", "project_brain.validate_11e_c_runway_browser_hardening"),
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
