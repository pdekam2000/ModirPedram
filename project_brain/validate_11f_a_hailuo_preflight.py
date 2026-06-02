"""
Phase 11F-a — Hailuo preflight, config, and error taxonomy validation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.hailuo_config import (
    DEFAULT_ACTIVE_VIDEO_PROVIDER,
    HAILUO_API_ROUTER_KEY,
    HAILUO_BROWSER_ROUTER_KEY,
    MINIMAX_API_ROUTER_KEY,
    HailuoConfigResolver,
)
from content_brain.execution.hailuo_preflight import HailuoPreflightEngine
from content_brain.execution.provider_preflight_validator import ProviderPreflightValidator
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.providers.provider_capability_registry import (
    CAPABILITY_IMAGE_TO_VIDEO,
    CAPABILITY_SUBTITLE_GENERATION,
    CAPABILITY_TEXT_TO_VIDEO,
)
from core.video_provider_router import VideoProviderRouter
from project_brain.validate_11e_common import append_regression_checks
from providers.hailuo_error_classifier import classify_hailuo_error, classify_hailuo_failure


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


def _hailuo_browser_session() -> dict:
    return {
        "provider": "hailuo_browser",
        "provider_selection": {
            "primary_provider": "hailuo_browser",
            "category_selections": {
                "video_generation": {
                    "provider": "hailuo",
                    "execution_mode": "browser",
                }
            },
        },
        "brief_snapshot": {
            "video_format_plan": {
                "clip_count": 1,
                "format_type": "multi_clip_hailuo",
                "capability": CAPABILITY_TEXT_TO_VIDEO,
            },
            "run_context": {
                "story_intelligence": {
                    "schema_director_shots": [
                        {"clip_number": 1, "prompt": "Hailuo preflight validation clip."}
                    ]
                }
            },
        },
    }


def _hailuo_api_session() -> dict:
    return {
        "provider": "hailuo_api",
        "provider_selection": {
            "primary_provider": "hailuo_api",
            "category_selections": {
                "video_generation": {
                    "provider": "hailuo",
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
                        {"clip_number": 1, "prompt": "Hailuo API preflight validation clip."}
                    ]
                }
            },
        },
    }


def _minimax_api_session() -> dict:
    return {
        "provider": "minimax_api",
        "provider_selection": {
            "primary_provider": "minimax_api",
            "category_selections": {
                "video_generation": {
                    "provider": "minimax",
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
                        {"clip_number": 1, "prompt": "MiniMax API preflight validation clip."}
                    ]
                }
            },
        },
    }


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []
    config = HailuoConfigResolver(root).resolve()
    engine = HailuoPreflightEngine(root)

    results.append(
        _pass(
            "active_default_runway_browser",
            config.active_video_provider == DEFAULT_ACTIVE_VIDEO_PROVIDER
            and config.active_default_is_runway is True,
            config.active_video_provider,
        )
    )
    results.append(
        _pass(
            "hailuo_api_metadata_only",
            config.hailuo_api_implemented is False
            and config.hailuo_api_implementation_status == "planned",
            config.hailuo_api_implementation_status,
        )
    )
    results.append(
        _pass(
            "minimax_api_stub_status",
            config.minimax_api_implemented is False
            and config.minimax_api_implementation_status == "stub",
            config.minimax_api_implementation_status,
        )
    )

    browser_preflight = engine.evaluate(
        _hailuo_browser_session(),
        mode="browser",
        provider_id=HAILUO_BROWSER_ROUTER_KEY,
        skip_browser_probes=True,
    )
    browser_block = browser_preflight.to_dict()
    results.append(
        _pass(
            "hailuo_browser_preflight_structured",
            all(
                key in browser_block
                for key in (
                    "ready",
                    "provider_id",
                    "mode",
                    "blocking_issues",
                    "warnings",
                    "capability_supported",
                    "runtime_supported",
                    "api_implemented",
                    "browser_available",
                )
            )
            and browser_block["provider_id"] == HAILUO_BROWSER_ROUTER_KEY
            and browser_block["mode"] == "browser",
            f"provider_id={browser_block.get('provider_id')}, mode={browser_block.get('mode')}",
        )
    )

    api_preflight = engine.evaluate(
        _hailuo_api_session(),
        mode="api",
        provider_id=HAILUO_API_ROUTER_KEY,
    )
    results.append(
        _pass(
            "hailuo_api_not_implemented_blocker",
            not api_preflight.ready
            and api_preflight.api_implemented is False
            and any(
                i.get("code") == "PROVIDER_NOT_IMPLEMENTED"
                for i in api_preflight.blocking_issues
            ),
            ",".join(i.get("code", "") for i in api_preflight.blocking_issues),
        )
    )

    minimax_preflight = engine.evaluate(
        _minimax_api_session(),
        mode="api",
        provider_id=MINIMAX_API_ROUTER_KEY,
    )
    results.append(
        _pass(
            "minimax_api_stub_blocker",
            not minimax_preflight.ready
            and any(
                i.get("check_id") == "MINIMAX_API_STUB"
                for i in minimax_preflight.blocking_issues
            ),
            ",".join(i.get("check_id", "") for i in minimax_preflight.blocking_issues),
        )
    )

    hailuo_key_backup = os.environ.get("HAILUO_API_KEY")
    minimax_key_backup = os.environ.get("MINIMAX_API_KEY")
    os.environ.pop("HAILUO_API_KEY", None)
    os.environ.pop("MINIMAX_API_KEY", None)
    try:
        no_key_browser = engine.evaluate(
            _hailuo_browser_session(),
            mode="browser",
            provider_id=HAILUO_BROWSER_ROUTER_KEY,
            skip_browser_probes=True,
        )
        results.append(
            _pass(
                "browser_mode_no_api_key_required",
                not any(
                    i.get("code") == "CREDENTIALS_MISSING"
                    for i in no_key_browser.blocking_issues
                ),
                ",".join(i.get("code", "") for i in no_key_browser.blocking_issues),
            )
        )
    finally:
        if hailuo_key_backup is not None:
            os.environ["HAILUO_API_KEY"] = hailuo_key_backup
        if minimax_key_backup is not None:
            os.environ["MINIMAX_API_KEY"] = minimax_key_backup

    unsupported = engine.evaluate(
        {
            "provider": "hailuo",
            "brief_snapshot": {
                "video_format_plan": {"capability": CAPABILITY_SUBTITLE_GENERATION}
            },
        },
        mode="browser",
        provider_id=HAILUO_BROWSER_ROUTER_KEY,
        capability=CAPABILITY_SUBTITLE_GENERATION,
        skip_browser_probes=True,
    )
    results.append(
        _pass(
            "unsupported_capability_blocker",
            not unsupported.ready
            and any(
                i.get("code") == "CAPABILITY_RUNTIME_UNSUPPORTED"
                for i in unsupported.blocking_issues
            ),
        )
    )

    i2v_block = engine.evaluate(
        {"provider": "hailuo"},
        mode="browser",
        provider_id=HAILUO_BROWSER_ROUTER_KEY,
        capability=CAPABILITY_IMAGE_TO_VIDEO,
        skip_browser_probes=True,
    )
    results.append(
        _pass(
            "i2v_drift_blocker_when_requested",
            not i2v_block.ready
            and i2v_block.i2v_drift_detected
            and any(i.get("check_id") == "HAILUO_I2V_DRIFT" for i in i2v_block.blocking_issues),
        )
    )

    results.append(
        _pass(
            "taxonomy_browser_unavailable",
            classify_hailuo_error("Chrome is not running with remote debugging") == "BROWSER_UNAVAILABLE",
        )
    )
    results.append(
        _pass(
            "taxonomy_session_expired",
            classify_hailuo_error("browser session invalid: login required") == "BROWSER_SESSION_INVALID",
        )
    )
    results.append(
        _pass(
            "taxonomy_generation_timeout",
            classify_hailuo_error(TimeoutError("generation timeout after wait_seconds")) == "PROVIDER_TIMEOUT",
        )
    )
    results.append(
        _pass(
            "taxonomy_download_failed",
            classify_hailuo_error("[Hailuo Download] Download failed: extraction error") == "DOWNLOAD_FAILED",
        )
    )
    results.append(
        _pass(
            "taxonomy_artifact_too_small",
            classify_hailuo_failure("artifact too small: file too small").get("code") == "ARTIFACT_TOO_SMALL",
        )
    )
    results.append(
        _pass(
            "taxonomy_unsupported_capability",
            classify_hailuo_error(
                "unsupported capability image_to_video",
                context={"capability": "image_to_video", "runtime_supported": False},
            )
            == "CAPABILITY_RUNTIME_UNSUPPORTED",
        )
    )
    results.append(
        _pass(
            "taxonomy_provider_not_implemented",
            classify_hailuo_error(NotImplementedError("MiniMax stub"))
            == "PROVIDER_NOT_IMPLEMENTED",
        )
    )
    results.append(
        _pass(
            "taxonomy_api_credential_missing",
            classify_hailuo_error("HAILUO_API_KEY not found in environment") == "CREDENTIALS_MISSING",
        )
    )
    results.append(
        _pass(
            "taxonomy_provider_disabled",
            classify_hailuo_error("provider disabled", context={"provider_disabled": True})
            == "PROVIDER_DISABLED",
        )
    )
    results.append(
        _pass(
            "taxonomy_cancel_requested",
            classify_hailuo_error("cancel requested by operator", context={"cancel_requested": True})
            == "OPERATIONS_CANCELLED",
        )
    )

    store = ExecutionSessionStore(str(root))
    integrated = ProviderPreflightValidator(store).validate(
        _hailuo_browser_session(),
        skip_browser_probes=True,
        skip_api_connectivity=True,
    )
    hp = integrated.hailuo_preflight or {}
    results.append(
        _pass(
            "integrated_hailuo_preflight_block",
            hp.get("provider_id") == HAILUO_BROWSER_ROUTER_KEY
            and hp.get("mode") == "browser"
            and isinstance(hp.get("blocking_issues"), list),
            f"passed={integrated.passed}, provider_id={hp.get('provider_id')}",
        )
    )

    with patch.object(ProviderRuntimeEngine, "dispatch") as mock_dispatch:
        mock_dispatch.side_effect = AssertionError("dispatch must not run")
        engine.evaluate(_hailuo_browser_session(), mode="browser", skip_browser_probes=True)
        results.append(_pass("no_runtime_dispatch", True))

    with patch.object(VideoProviderRouter, "generate_clips") as mock_clips:
        mock_clips.side_effect = AssertionError("router must not run")
        HailuoPreflightEngine(root).evaluate(_hailuo_browser_session())
        results.append(_pass("no_router_execution", True))

    append_regression_checks(
        results,
        _pass,
        _run_module,
        [
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
