"""
Phase 12E — Premium UAT Runtime UI validation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _run_npm_build(root: Path) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(root / "ui" / "web"),
        shell=True,
    )
    return result.returncode == 0


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    page_path = root / "ui/web/src/pages/UatRuntimePage.tsx"
    execution_page = root / "ui/web/src/pages/ExecutionCenterPage.tsx"
    client_path = root / "ui/web/src/api/uatRuntimeClient.ts"
    labels_path = root / "ui/web/src/utils/uatRuntimeLabels.ts"
    css_path = root / "ui/web/src/styles/uat-runtime.css"
    main_api = root / "ui/api/main.py"

    results.append(_pass("uat_runtime_page_exists", page_path.is_file(), str(page_path)))
    results.append(_pass("uat_runtime_client_exists", client_path.is_file(), str(client_path)))
    results.append(_pass("uat_runtime_css_exists", css_path.is_file(), str(css_path)))

    page = _read(root, "ui/web/src/pages/UatRuntimePage.tsx") if page_path.is_file() else ""
    execution = _read(root, "ui/web/src/pages/ExecutionCenterPage.tsx") if execution_page.is_file() else ""
    labels = _read(root, "ui/web/src/utils/uatRuntimeLabels.ts") if labels_path.is_file() else ""
    client = _read(root, "ui/web/src/api/uatRuntimeClient.ts") if client_path.is_file() else ""
    css = _read(root, "ui/web/src/styles/uat-runtime.css") if css_path.is_file() else ""
    api_src = _read(root, "ui/api/main.py") if main_api.is_file() else ""
    bundle = page + execution + labels + client + css

    results.append(
        _pass(
            "execution_center_tabs_wired",
            "UAT Runtime" in execution and "<UatRuntimePage" in execution and 'centerTab === "uat"' in execution,
        )
    )

    results.append(
        _pass(
            "modir_branding_present",
            "MODIR AGENT OS" in labels and "Pedram AI Content Factory" in labels,
        )
    )

    ui_bundle = page + execution + client + css

    results.append(
        _pass(
            "generate_uat_video_hero_label",
            "Generate UAT Video" in labels
            and ("Generate UAT Video" in page or "UAT_GENERATE_LABEL" in page),
        )
    )

    forbidden = [
        "Batch Generate",
        "Auto Publish",
        "Publish To YouTube",
        "Publish To TikTok",
        "Upload",
        "Scheduler",
        "Production Queue",
        "Run Pipeline",
        "Execute Runtime",
    ]
    results.append(
        _pass(
            "no_forbidden_publish_batch_labels",
            not any(label in ui_bundle for label in forbidden),
        )
    )

    results.append(
        _pass(
            "uat_api_client_routes",
            '"/uat/run"' in client or "/uat/run" in client,
            "postUatRun" in client,
        )
    )

    results.append(
        _pass(
            "status_poll_hook",
            (root / "ui/web/src/hooks/useUatStatusPoll.ts").is_file(),
        )
    )

    results.append(
        _pass(
            "provider_stack_cards",
            "Provider Stack" in page and "Runway Browser" in page and "ElevenLabs" in page,
        )
    )

    results.append(
        _pass(
            "safety_gate_warning",
            "billable content" in labels.lower() or "billable content" in page.lower(),
        )
    )

    results.append(
        _pass(
            "runtime_monitor_stepper",
            "Runtime Monitor" in page and "Content Brain" in labels and "Final Video" in labels,
        )
    )

    results.append(
        _pass(
            "pedram_review_system",
            "Pedram Review System" in page and "Save Review" in page,
        )
    )

    results.append(
        _pass(
            "premium_dark_theme_tokens",
            "#0B0F17" in css.upper() or "#0b0f17" in css,
            "#121826" in css,
        )
    )

    results.append(
        _pass(
            "video_preview_endpoint",
            "/uat/artifacts/" in api_src and "final-video" in api_src,
        )
    )

    results.append(
        _pass(
            "workspace_status_pill",
            "uat-status-pill" in css and "RUNNING" in labels,
        )
    )

    eligibility = _read(root, "ui/web/src/utils/uatRuntimeEligibility.ts") if (root / "ui/web/src/utils/uatRuntimeEligibility.ts").is_file() else ""

    results.append(
        _pass(
            "live_voice_smoke_duration_min_runway",
            "uatDurationMinSeconds" in eligibility
            and "uatSingleSegmentSafeDuration" in eligibility
            and "return 10" in eligibility,
        )
    )

    results.append(
        _pass(
            "live_voice_smoke_duration_min_hailuo",
            "hailuo_browser" in eligibility and "return 6" in eligibility,
        )
    )

    results.append(
        _pass(
            "live_voice_smoke_duration_helper_copy",
            "For real voice smoke UAT, duration may be auto-reduced to one provider-safe segment."
            in eligibility,
        )
    )

    results.append(
        _pass(
            "duration_not_hardcoded_15_only",
            "UAT_DEFAULT_MIN_DURATION_SECONDS = 15" in eligibility
            and "Duration must be between ${min} and ${max} seconds." in eligibility,
        )
    )

    results.append(
        _pass(
            "uat_api_422_error_parser",
            "formatValidationDetail" in client and "Validation failed" in client,
        )
    )

    labels = (root / "ui" / "web" / "src" / "utils" / "uatRuntimeLabels.ts").read_text(encoding="utf-8")
    results.append(
        _pass(
            "uat_failed_stage_not_mapped_to_content_brain",
            'if (value === "failed") return null' in labels and "inferFailedStage" in labels,
        )
    )

    results.append(_pass("npm_build_passes", _run_npm_build(root)))

    if include_regressions:
        from project_brain.validation_policy import run_validator_module

        results.append(
            _pass(
                "validate_12d_regression",
                run_validator_module("project_brain.validate_12d_uat_runtime_backend_api", core_only=True),
            )
        )

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="12E",
        label="premium_uat_runtime_ui",
        results=results,
        include_regressions=include_regressions,
    )


def main(argv: list[str] | None = None) -> int:
    from project_brain.validation_policy import (
        parse_include_regressions,
        print_validation_summary,
        validation_exit_code,
    )

    include_regressions = parse_include_regressions(argv)
    report = run_matrix(include_regressions=include_regressions)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print_validation_summary(report)
    return validation_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
