"""
Phase 11E-a — Runway preflight, config, and error taxonomy validation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.provider_preflight_validator import ProviderPreflightValidator
from content_brain.execution.runway_config import (
    RUNWAY_API_ROUTER_KEY,
    RUNWAY_BROWSER_ROUTER_KEY,
    RunwayConfigResolver,
)
from content_brain.execution.runway_preflight import RunwayPreflightEngine
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.providers.provider_capability_registry import (
    CAPABILITY_IMAGE_TO_VIDEO,
    CAPABILITY_SUBTITLE_GENERATION,
    CAPABILITY_TEXT_TO_VIDEO,
)
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from project_brain.validate_11e_common import append_regression_checks
from core.video_provider_router import VideoProviderRouter
from providers.runway_error_classifier import classify_runway_error, classify_runway_failure


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


def _runway_browser_session() -> dict:
    return {
        "provider": "runway_browser",
        "provider_selection": {
            "primary_provider": "runway_browser",
            "category_selections": {
                "video_generation": {
                    "provider": "runway",
                    "execution_mode": "browser",
                }
            },
        },
        "brief_snapshot": {
            "video_format_plan": {
                "clip_count": 1,
                "format_type": "multi_clip_runway",
                "capability": CAPABILITY_TEXT_TO_VIDEO,
            },
            "run_context": {
                "story_intelligence": {
                    "schema_director_shots": [
                        {"clip_number": 1, "prompt": "Runway preflight validation clip."}
                    ]
                }
            },
        },
    }


def _runway_api_session() -> dict:
    return {
        "provider": "runway",
        "provider_selection": {
            "primary_provider": "runway",
            "category_selections": {
                "video_generation": {
                    "provider": "runway",
                    "execution_mode": "api",
                }
            },
        },
        "brief_snapshot": {
            "video_format_plan": {
                "clip_count": 1,
                "capability": CAPABILITY_TEXT_TO_VIDEO,
            },
            "run_context": {
                "story_intelligence": {
                    "schema_director_shots": [
                        {"clip_number": 1, "prompt": "Runway API preflight validation clip."}
                    ]
                }
            },
        },
    }


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []
    config = RunwayConfigResolver(root).resolve()
    engine = RunwayPreflightEngine(root)

    results.append(
        _pass(
            "browser_default_unchanged",
            config.active_video_provider == RUNWAY_BROWSER_ROUTER_KEY,
            config.active_video_provider,
        )
    )
    results.append(
        _pass(
            "preferred_mode_browser",
            config.preferred_mode == "browser",
            config.preferred_mode,
        )
    )
    results.append(
        _pass(
            "api_disabled_in_registry",
            config.api_enabled_in_registry is False,
            str(config.api_enabled_in_registry),
        )
    )

    api_disabled = engine.evaluate(
        _runway_api_session(),
        mode="api",
        provider_id=RUNWAY_API_ROUTER_KEY,
    )
    results.append(
        _pass(
            "api_mode_disabled_blocker",
            not api_disabled.ready
            and any(i.get("code") == "PROVIDER_DISABLED" for i in api_disabled.blocking_issues),
            ",".join(i.get("code", "") for i in api_disabled.blocking_issues),
        )
    )

    env_backup = os.environ.get("RUNWAY_API_KEY")
    os.environ.pop("RUNWAY_API_KEY", None)
    try:
        missing_key = engine.evaluate(
            _runway_api_session(),
            mode="api",
            provider_id=RUNWAY_API_ROUTER_KEY,
        )
        results.append(
            _pass(
                "missing_api_key_blocker",
                not missing_key.ready
                and any(i.get("code") == "CREDENTIALS_MISSING" for i in missing_key.blocking_issues),
            )
        )
    finally:
        if env_backup is not None:
            os.environ["RUNWAY_API_KEY"] = env_backup

    url_backup = os.environ.get("RUNWAY_API_BASE_URL")
    os.environ["RUNWAY_API_BASE_URL"] = "not-a-valid-url"
    try:
        invalid_url = RunwayConfigResolver(root).resolve()
        invalid_preflight = RunwayPreflightEngine(
            root,
            config_resolver=RunwayConfigResolver(root),
        ).evaluate(_runway_api_session(), mode="api", provider_id=RUNWAY_API_ROUTER_KEY)
        results.append(
            _pass(
                "invalid_base_url_blocker",
                not invalid_url.api_base_url_valid
                and not invalid_preflight.ready
                and any(
                    i.get("check_id") == "RUNWAY_API_BASE_URL_INVALID"
                    for i in invalid_preflight.blocking_issues
                ),
            )
        )
    finally:
        if url_backup is None:
            os.environ.pop("RUNWAY_API_BASE_URL", None)
        else:
            os.environ["RUNWAY_API_BASE_URL"] = url_backup

    unsupported = engine.evaluate(
        {
            "provider": "runway",
            "brief_snapshot": {
                "video_format_plan": {"capability": CAPABILITY_SUBTITLE_GENERATION}
            },
        },
        mode="browser",
        provider_id=RUNWAY_BROWSER_ROUTER_KEY,
        capability=CAPABILITY_SUBTITLE_GENERATION,
    )
    results.append(
        _pass(
            "unsupported_capability_blocker",
            not unsupported.ready
            and any(i.get("code") == "CAPABILITY_RUNTIME_UNSUPPORTED" for i in unsupported.blocking_issues),
        )
    )

    i2v_block = engine.evaluate(
        {"provider": "runway"},
        mode="browser",
        provider_id=RUNWAY_BROWSER_ROUTER_KEY,
        capability=CAPABILITY_IMAGE_TO_VIDEO,
    )
    results.append(
        _pass(
            "i2v_drift_blocker_when_requested",
            not i2v_block.ready
            and i2v_block.i2v_drift_detected
            and any(i.get("check_id") == "RUNWAY_I2V_DRIFT" for i in i2v_block.blocking_issues),
        )
    )

    i2v_warn = engine.evaluate(
        _runway_browser_session(),
        mode="browser",
        provider_id=RUNWAY_BROWSER_ROUTER_KEY,
        capability=CAPABILITY_TEXT_TO_VIDEO,
    )
    results.append(
        _pass(
            "i2v_drift_warning_when_not_requested",
            i2v_warn.ready
            and i2v_warn.i2v_drift_detected
            and any(w.get("check_id") == "RUNWAY_I2V_DRIFT" for w in i2v_warn.warnings),
        )
    )

    results.append(
        _pass(
            "taxonomy_missing_credential",
            classify_runway_error("RUNWAY_API_KEY not found in .env") == "CREDENTIALS_MISSING",
        )
    )
    results.append(
        _pass(
            "taxonomy_invalid_credential",
            classify_runway_error("401 Unauthorized") == "CREDENTIALS_INVALID",
        )
    )
    results.append(
        _pass(
            "taxonomy_rate_limit",
            classify_runway_error("429 rate limit exceeded") == "API_QUOTA_EXCEEDED",
        )
    )
    results.append(
        _pass(
            "taxonomy_timeout",
            classify_runway_error(TimeoutError("timeout waiting for Runway task")) == "PROVIDER_TIMEOUT",
        )
    )
    results.append(
        _pass(
            "taxonomy_download_failed",
            classify_runway_error("[Runway Download] Download failed: 500") == "DOWNLOAD_FAILED",
        )
    )
    results.append(
        _pass(
            "taxonomy_artifact_invalid",
            classify_runway_failure("artifact validation failed").get("code") == "ARTIFACT_VALIDATION_FAILED",
        )
    )
    results.append(
        _pass(
            "taxonomy_browser_unavailable",
            classify_runway_error("Chrome is not running with remote debugging") == "BROWSER_UNAVAILABLE",
        )
    )
    results.append(
        _pass(
            "taxonomy_provider_disabled",
            classify_runway_error("provider disabled", context={"provider_disabled": True}) == "PROVIDER_DISABLED",
        )
    )

    store = ExecutionSessionStore(str(root))
    integrated = ProviderPreflightValidator(store).validate(
        _runway_browser_session(),
        skip_browser_probes=True,
        skip_api_connectivity=True,
    )
    rp = integrated.runway_preflight or {}
    results.append(
        _pass(
            "integrated_runway_preflight_block",
            integrated.passed is True
            and rp.get("provider_id") == RUNWAY_BROWSER_ROUTER_KEY
            and rp.get("mode") == "browser",
            f"passed={integrated.passed}, provider_id={rp.get('provider_id')}",
        )
    )

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        engine.evaluate(_runway_browser_session(), mode="browser")
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        RunwayPreflightEngine(root).evaluate(_runway_browser_session())
        results.append(_pass("no_router_execution", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
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
