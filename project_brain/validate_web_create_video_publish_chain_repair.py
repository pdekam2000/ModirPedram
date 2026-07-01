#!/usr/bin/env python3
"""Validate WEB-CREATE-VIDEO-PUBLISH-CHAIN-REPAIR phase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.product_assembly_bridge import FINAL_PUBLISH_READY_NAME  # noqa: E402
from content_brain.execution.product_publish_pipeline_trace import (  # noqa: E402
    ORCHESTRATOR_VERSION,
    PIPELINE_STAGES,
    load_pipeline_trace,
)
from content_brain.execution.product_subtitle_branding_publish import (  # noqa: E402
    FINAL_BRANDED_PUBLISH_READY_NAME,
    PUBLISH_PACKAGE_NAME,
)
from content_brain.platform.api_runtime_diagnostics import (  # noqa: E402
    build_runtime_diagnostics,
    compute_api_build_id,
    get_publish_chain_capabilities,
)
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME  # noqa: E402

RUN_ID = "pwmap_20260627T153920_b27a7273"
RUN_DIR = ROOT / "outputs" / "pwmap_agent_runs" / RUN_ID

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {name}{suffix}")


def main() -> int:
    print("validate_web_create_video_publish_chain_repair")
    print(f"run_id={RUN_ID}")

    orchestrator_src = (ROOT / "content_brain" / "execution" / "product_multiclip_orchestrator.py").read_text(
        encoding="utf-8"
    )
    record(
        "orchestrator_calls_publish_chain",
        "run_publish_post_processing_chain" in orchestrator_src,
        "static scan",
    )
    record(
        "orchestrator_version_constant",
        "ORCHESTRATOR_VERSION" in orchestrator_src,
        "import from product_publish_pipeline_trace",
    )

    main_src = (ROOT / "ui" / "api" / "main.py").read_text(encoding="utf-8")
    record("startup_diagnostics_wired", "init_api_runtime_diagnostics" in main_src, "static scan")
    record("health_build_id", "api_build_id" in main_src, "static scan")
    record("runtime_diagnostics_endpoint", "/platform/runtime-diagnostics" in main_src, "static scan")

    service_src = (ROOT / "ui" / "api" / "product_studio_service.py").read_text(encoding="utf-8")
    record("results_pipeline_trace", "pipeline_trace" in service_src, "static scan")
    record("results_no_pwmap_agent_override", '"assembly_status": "PWMAP_AGENT"' not in service_src, "static scan")

    caps = get_publish_chain_capabilities(ROOT)
    record("assembly_bridge_enabled", bool(caps.get("assembly_bridge_enabled")))
    record("branding_publish_enabled", bool(caps.get("branding_publish_enabled")))
    record("youtube_metadata_enabled", bool(caps.get("youtube_metadata_enabled")))

    diagnostics = build_runtime_diagnostics(ROOT, api_version="test")
    record("api_build_id_present", bool(diagnostics.get("api_build_id")))
    record("orchestrator_version_present", diagnostics.get("orchestrator_version") == ORCHESTRATOR_VERSION)

    publish_dir = RUN_DIR / "publish"
    record("publish_dir_exists", publish_dir.is_dir(), str(publish_dir))
    record(
        "final_publish_ready_exists",
        (publish_dir / FINAL_PUBLISH_READY_NAME).is_file(),
        FINAL_PUBLISH_READY_NAME,
    )
    record(
        "final_branded_publish_ready_exists",
        (publish_dir / FINAL_BRANDED_PUBLISH_READY_NAME).is_file(),
        FINAL_BRANDED_PUBLISH_READY_NAME,
    )
    record(
        "youtube_metadata_exists",
        (publish_dir / YOUTUBE_METADATA_FILENAME).is_file(),
        YOUTUBE_METADATA_FILENAME,
    )
    record(
        "publish_package_exists",
        (publish_dir / PUBLISH_PACKAGE_NAME).is_file(),
        PUBLISH_PACKAGE_NAME,
    )

    trace = load_pipeline_trace(RUN_DIR) or {}
    record("pipeline_trace_exists", bool(trace), "pipeline_trace.json")
    if trace:
        stages = dict(trace.get("stages") or {})
        for stage in PIPELINE_STAGES:
            if stage == "youtube_upload_runtime":
                record(
                    f"stage_{stage}_skipped",
                    stages.get(stage, {}).get("status") == "skipped",
                    str(stages.get(stage)),
                )
            else:
                record(
                    f"stage_{stage}_completed",
                    stages.get(stage, {}).get("status") == "completed",
                    str(stages.get(stage)),
                )
        record("stop_stage_empty", not trace.get("stop_stage"), str(trace.get("stop_stage")))
        record(
            "last_completed_publish_chain",
            trace.get("last_completed_stage") == "subtitle_branding_publish",
            str(trace.get("last_completed_stage")),
        )

    upload_result_path = publish_dir / "youtube_upload_result.json"
    record(
        "upload_not_auto_triggered",
        not upload_result_path.is_file(),
        "no youtube_upload_result.json",
    )

    profile_path = ROOT / "project_brain" / "product_settings" / "channel_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.is_file() else {}
    record("upload_private_default", profile.get("youtube_privacy") == "private")
    record("upload_requires_confirmation", bool(profile.get("youtube_require_confirmation")))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\nSummary: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
