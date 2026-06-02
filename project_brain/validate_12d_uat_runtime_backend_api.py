"""
Phase 12D — UAT runtime backend API validation.
"""

from __future__ import annotations

import ast
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.uat_runtime_engine import UATRuntimeEngine, UatRunAlreadyActiveError
from content_brain.execution.uat_runtime_profile import UatRuntimeConfig
from project_brain import run_12b_uat_supervised_pipeline as uat_runner
from ui.api.main import app
from ui.api.uat_runtime_service import UatRuntimeService

ENGINE_PATH = Path("content_brain/execution/uat_runtime_engine.py")
SERVICE_PATH = Path("ui/api/uat_runtime_service.py")
SCHEMA_PATH = Path("ui/api/schemas/uat_runtime.py")
MAIN_PATH = Path("ui/api/main.py")
RUNNER_PATH = Path("project_brain/run_12b_uat_supervised_pipeline.py")


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _imports_forbidden(module_path: Path, forbidden: str) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if forbidden in alias.name:
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and forbidden in node.module:
            return True
    return False


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    _ = project_root
    results: list[dict] = []
    root = Path(".").resolve()

    results.append(_pass("engine_module_exists", ENGINE_PATH.is_file(), str(ENGINE_PATH)))
    results.append(_pass("service_module_exists", SERVICE_PATH.is_file(), str(SERVICE_PATH)))
    results.append(_pass("schema_module_exists", SCHEMA_PATH.is_file(), str(SCHEMA_PATH)))

    engine_src = ENGINE_PATH.read_text(encoding="utf-8")
    results.append(_pass("uat_runtime_engine_class", "class UATRuntimeEngine" in engine_src))

    main_src = MAIN_PATH.read_text(encoding="utf-8")
    results.append(
        _pass(
            "routes_registered",
            '"/uat/run"' in main_src
            and '"/uat/status/{session_id}"' in main_src
            and '"/uat/review/{session_id}"' in main_src,
        )
    )

    results.append(
        _pass(
            "no_full_video_pipeline_import",
            not _imports_forbidden(ENGINE_PATH, "full_video_pipeline")
            and not _imports_forbidden(SERVICE_PATH, "full_video_pipeline")
            and not _imports_forbidden(RUNNER_PATH, "full_video_pipeline"),
        )
    )

    runner_src = RUNNER_PATH.read_text(encoding="utf-8")
    results.append(
        _pass(
            "no_batch_or_auto_publish",
            "for topic in" not in runner_src
            and "batch_mode" not in runner_src.lower()
            and "auto_publish" not in runner_src.lower(),
        )
    )

    results.append(_pass("cli_runner_reexports_pipeline", callable(uat_runner.run_uat_pipeline)))
    results.append(_pass("cli_runner_reexports_stages", callable(uat_runner._run_voice_stage)))

    config = UatRuntimeConfig(
        topic="12D validator mock topic",
        platform="youtube_shorts",
        duration_seconds=30,
        video_provider="mock",
        voice_provider="mock",
    )
    session_id = f"exec_uat_val_{uuid.uuid4().hex[:8]}"
    engine = UATRuntimeEngine(root)
    try:
        sync_payload = engine.run_sync(
            config,
            mock_paid_providers=True,
            mock_assembly_executor=True,
            allow_mock_assembly_fallback=True,
            session_id=session_id,
        )
        sync_ok = sync_payload.get("success") is True and bool(sync_payload.get("final_video_path"))
    except Exception as exc:
        sync_ok = False
        sync_payload = {"error": str(exc)}
    results.append(
        _pass(
            "engine_run_sync_mock_completes",
            sync_ok,
            str(sync_payload.get("final_video_path") or sync_payload.get("error")),
        )
    )

    store = ExecutionSessionStore(root)
    if sync_ok:
        blocked_asm = uat_runner._run_assembly_stage(
            store,
            session_id,
            UatRuntimeConfig(topic="x", confirm_real_assembly=False),
            mock_paid_providers=False,
            mock_assembly_executor=False,
            allow_mock_assembly_fallback=False,
        )
        asm_block_ok = blocked_asm.get("code") == "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED"
    else:
        asm_block_ok = False
        blocked_asm = {}
    results.append(
        _pass(
            "real_assembly_blocked_without_confirm",
            asm_block_ok,
            str(blocked_asm.get("code")),
        )
    )

    client = TestClient(app)
    run_body = {
        "topic": "12D API validator mock topic",
        "platform": "youtube_shorts",
        "duration_seconds": 30,
        "video_provider": "mock",
        "voice_provider": "mock",
        "confirm_real_voice": False,
        "confirm_real_assembly": False,
    }

    UATRuntimeEngine._active_session_id = "exec_uat_validator_lock_probe"
    try:
        try:
            UATRuntimeEngine(root).start(
                UatRuntimeConfig(
                    topic="12D lock probe topic",
                    platform="youtube_shorts",
                    duration_seconds=30,
                    video_provider="mock",
                    voice_provider="mock",
                )
            )
            conflict_ok = False
        except UatRunAlreadyActiveError:
            conflict_ok = True
    finally:
        UATRuntimeEngine._active_session_id = None

    results.append(_pass("active_run_conflict_engine", conflict_ok))

    UATRuntimeEngine._active_session_id = "exec_uat_validator_http_lock"
    try:
        conflict_http = client.post("/uat/run", json=run_body)
        http_conflict_ok = conflict_http.status_code == 409
    finally:
        UATRuntimeEngine._active_session_id = None
    results.append(_pass("active_run_conflict_http_409", http_conflict_ok))

    start_resp = client.post("/uat/run", json=run_body)
    api_start_ok = start_resp.status_code == 202 and str(start_resp.json().get("session_id", "")).startswith("exec_uat_")
    results.append(
        _pass(
            "post_uat_run_accepts",
            api_start_ok,
            str(start_resp.status_code) if not api_start_ok else start_resp.json().get("session_id"),
        )
    )

    if sync_ok:
        status_resp = client.get(f"/uat/status/{session_id}")
        status_payload = status_resp.json() if status_resp.status_code == 200 else {}
        status_ok = (
            status_resp.status_code == 200
            and status_payload.get("status") == "completed"
            and bool(status_payload.get("final_video_path"))
        )
        results.append(
            _pass(
                "get_uat_status_completed_session",
                status_ok,
                str(status_payload.get("status")),
            )
        )

        review_resp = client.post(
            f"/uat/review/{session_id}",
            json={
                "story_quality_score": 7,
                "visual_quality_score": 6,
                "voice_quality_score": 8,
                "subtitle_quality_score": 7,
                "continuity_score": 5,
                "overall_quality_score": 6,
                "comments": "12D validator review",
                "publishable": False,
            },
        )
        review_path = Path(review_resp.json().get("review_path") or "")
        review_ok = review_resp.status_code == 201 and review_path.is_file()
        results.append(_pass("post_uat_review_persists", review_ok, str(review_path)))

        dup_resp = client.post(
            f"/uat/review/{session_id}",
            json={
                "story_quality_score": 7,
                "visual_quality_score": 6,
                "voice_quality_score": 8,
                "subtitle_quality_score": 7,
                "continuity_score": 5,
                "overall_quality_score": 6,
                "comments": "duplicate",
                "publishable": False,
            },
        )
        results.append(_pass("review_duplicate_409", dup_resp.status_code == 409, str(dup_resp.status_code)))
    else:
        results.append(_pass("get_uat_status_completed_session", False, "sync pipeline failed"))
        results.append(_pass("post_uat_review_persists", False, "sync pipeline failed"))
        results.append(_pass("review_duplicate_409", False, "skipped"))

    from ui.api.schemas.uat_runtime import UatRunRequest

    service = UatRuntimeService(ExecutionSessionStore(root))
    try:
        service.start_run(UatRunRequest(topic="   "))
        invalid_ok = False
    except ValueError:
        invalid_ok = True
    except Exception:
        invalid_ok = False
    results.append(_pass("invalid_topic_rejected", invalid_ok))

    schema_10 = UatRunRequest(
        topic="smoke duration schema test",
        duration_seconds=10,
        video_provider="runway_browser",
        voice_provider="elevenlabs",
        confirm_real_voice=True,
        confirm_real_assembly=True,
    )
    results.append(
        _pass(
            "schema_accepts_10s_live_voice",
            schema_10.duration_seconds == 10,
            str(schema_10.duration_seconds),
        )
    )

    UATRuntimeEngine._active_session_id = None
    live_10_resp = client.post(
        "/uat/run",
        json={
            "topic": "Runway ElevenLabs real assembly 10s acceptance",
            "platform": "youtube_shorts",
            "duration_seconds": 10,
            "video_provider": "runway_browser",
            "voice_provider": "elevenlabs",
            "confirm_real_voice": True,
            "confirm_real_assembly": True,
            "open_folder": False,
            "niche": "general",
        },
    )
    results.append(
        _pass(
            "post_uat_run_10s_live_voice_not_422",
            live_10_resp.status_code == 202,
            str(live_10_resp.status_code),
        )
    )
    UATRuntimeEngine._active_session_id = None

    smoke_narration_path = Path("content_brain/execution/uat_smoke_narration_adapter.py")
    engine_src = ENGINE_PATH.read_text(encoding="utf-8")
    results.append(
        _pass(
            "uat_smoke_narration_module_exists",
            smoke_narration_path.is_file(),
            str(smoke_narration_path),
        )
    )
    results.append(
        _pass(
            "uat_engine_wires_smoke_narration",
            "apply_uat_smoke_narration_session" in engine_src,
        )
    )
    results.append(
        _pass(
            "uat_engine_persists_failed_stage",
            "failed_stage" in engine_src,
        )
    )

    if include_regressions:
        from project_brain.validation_policy import run_validator_module

        results.append(
            _pass(
                "validate_12b_regression",
                run_validator_module("project_brain.validate_12b_uat_supervised_pipeline", core_only=True),
            )
        )

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="12D",
        label="uat_runtime_backend_api",
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
    print(json.dumps(report, indent=2))
    print_validation_summary(report)
    return validation_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
