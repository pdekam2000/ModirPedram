"""
Phase 12J-C2a — Runway browser timeout authority validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from core.video_provider_router import VideoProviderRouter
from providers.runway_browser_support import (
    DEFAULT_BROWSER_MAX_WAIT_SECONDS,
    browser_max_wait_seconds,
    clamp_browser_max_wait_seconds,
    resolve_runway_browser_max_wait_seconds,
)


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    router_src = (root / "core" / "video_provider_router.py").read_text(encoding="utf-8")
    support_src = (root / "providers" / "runway_browser_support.py").read_text(encoding="utf-8")

    results.append(_pass("router_no_hardcoded_180", "wait_seconds=180" not in router_src))
    results.append(_pass("router_uses_log_runway_wait_config", "log_runway_wait_config" in router_src))
    results.append(_pass("support_resolve_helper", "resolve_runway_browser_max_wait_seconds" in support_src))
    results.append(_pass("support_wait_config_log", "[RUNWAY_WAIT_CONFIG]" in support_src))
    results.append(_pass("support_floor_ceiling", "BROWSER_MAX_WAIT_FLOOR_SECONDS = 60" in support_src))

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RUNWAY_BROWSER_MAX_WAIT_SECONDS", None)
        seconds, source = resolve_runway_browser_max_wait_seconds()
        results.append(
            _pass(
                "default_resolves_900",
                seconds == 900 and source == "default:900",
                f"seconds={seconds} source={source}",
            )
        )
        results.append(
            _pass(
                "browser_max_wait_matches_resolve",
                browser_max_wait_seconds() == seconds,
            )
        )

    with patch.dict(os.environ, {"RUNWAY_BROWSER_MAX_WAIT_SECONDS": "600"}, clear=False):
        seconds, source = resolve_runway_browser_max_wait_seconds()
        results.append(
            _pass(
                "env_override_works",
                seconds == 600 and source == "env:RUNWAY_BROWSER_MAX_WAIT_SECONDS",
                f"seconds={seconds} source={source}",
            )
        )

    with patch.dict(os.environ, {"RUNWAY_BROWSER_MAX_WAIT_SECONDS": "30"}, clear=False):
        seconds, _ = resolve_runway_browser_max_wait_seconds()
        results.append(_pass("env_floor_60", seconds == 60, f"seconds={seconds}"))

    with patch.dict(os.environ, {"RUNWAY_BROWSER_MAX_WAIT_SECONDS": "9999"}, clear=False):
        seconds, _ = resolve_runway_browser_max_wait_seconds()
        results.append(_pass("env_ceiling_1800", seconds == 1800, f"seconds={seconds}"))

    session_seconds, session_source = resolve_runway_browser_max_wait_seconds(
        {"operations": {"runway_browser_max_wait_seconds": 240}}
    )
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RUNWAY_BROWSER_MAX_WAIT_SECONDS", None)
        results.append(
            _pass(
                "session_override_when_no_env",
                session_seconds == 240 and "session:" in session_source,
                f"seconds={session_seconds} source={session_source}",
            )
        )

    results.append(
        _pass(
            "clamp_helper",
            clamp_browser_max_wait_seconds(1) == 60
            and clamp_browser_max_wait_seconds(5000) == 1800
            and clamp_browser_max_wait_seconds(450) == 450,
        )
    )

    results.append(
        _pass(
            "default_constant",
            DEFAULT_BROWSER_MAX_WAIT_SECONDS == 900,
        )
    )

    hailuo_src = (root / "orchestrators" / "hailuo_multi_clip_orchestrator.py").read_text(encoding="utf-8")
    results.append(_pass("hailuo_unchanged_no_180_router", "wait_seconds=180" not in hailuo_src))

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RUNWAY_BROWSER_MAX_WAIT_SECONDS", None)
        with patch(
            "orchestrators.runway_browser_orchestrator.RunwayBrowserOrchestrator"
        ) as mock_orch_cls:
            mock_orch_cls.return_value.run.return_value = []
            VideoProviderRouter().generate_clips(["prompt"], provider_override="runway_browser")
            call = mock_orch_cls.call_args
            wait_passed = (call.kwargs or {}).get("wait_seconds") if call else None
            results.append(
                _pass(
                    "router_passes_resolved_wait_to_orchestrator",
                    wait_passed == 900,
                    f"wait_seconds={wait_passed}",
                )
            )

    composer_src = (root / "content_brain" / "execution" / "runway_prompt_composer.py").read_text(
        encoding="utf-8"
    )
    results.append(_pass("composer_module_untouched", "RunwayPromptComposer" in composer_src))

    passed = sum(1 for item in results if item["pass"])
    return {"passed": passed, "total": len(results), "results": results}


if __name__ == "__main__":
    summary = run_matrix()
    for item in summary["results"]:
        status = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{status}] {item['test']}{detail}")
    print(f"\n{summary['passed']}/{summary['total']} passed")
    raise SystemExit(0 if summary["passed"] == summary["total"] else 1)
