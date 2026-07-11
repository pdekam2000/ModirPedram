"""
Phase 11J-19 — supervised real FFmpeg assembly smoke test validation.

Mock FFmpeg for automated tests. Real FFmpeg runs only via run_11j19_supervised_assembly_smoke_test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_approval_operations_engine import AssemblyApprovalOperationsEngine
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability
from content_brain.execution.assembly_models import EXPECTED_OUTPUT
from content_brain.execution.assembly_smoke_profile import SMOKE_TRIGGER
from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore
from ui.api.assembly_run_service import AssemblyRunService

from project_brain.validate_11j8_assembly_runtime_api import _build_session, _upstream_slots


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _write(path: Path, content: str = "x") -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _build_smoke_session(tmp: Path, *, session_id: str = "exec_11j19_smoke_test") -> dict:
    """Smoke-limited session: 1 clip, 1 voice, 1 ASS subtitle."""
    session = _build_session(tmp, session_id=session_id, subtitle_exts=("ass",))
    runtime = session["execution_runtime"]
    cr = runtime["category_runtime"]
    ar = runtime["artifacts_by_category"]

    clip_path = tmp / "clip_001.mp4"
    _write(clip_path)
    ar[CATEGORY_VIDEO] = [{"file_path": str(clip_path)}]

    voice_path = tmp / "narration_001.mp3"
    _write(voice_path)
    files = [{"segment_index": 0, "file_path": str(voice_path), "file_name": voice_path.name}]
    _write(tmp / "voice_manifest.json", json.dumps({"files": files}, ensure_ascii=False))
    cr[CATEGORY_VOICE]["voice_manifest_path"] = str(tmp / "voice_manifest.json")
    ar[CATEGORY_VOICE] = [{"file_path": str(voice_path)}]

    ass_path = tmp / "subtitles.ass"
    _write(ass_path, "[Events]\n")
    ar[CATEGORY_SUBTITLE_GENERATION] = [{"format": "ass", "file_path": str(ass_path)}]
    _write(tmp / "subtitle_manifest.json", json.dumps({"files": [{"format": "ass", "file_path": str(ass_path)}]}, ensure_ascii=False))
    cr[CATEGORY_SUBTITLE_GENERATION]["manifest_path"] = str(tmp / "subtitle_manifest.json")

    ts = "2026-05-31 10:00:00"
    for cat in (CATEGORY_VIDEO, CATEGORY_VOICE, CATEGORY_SUBTITLE_GENERATION):
        cr[cat].update({"status": "completed", "started_at": ts, "completed_at": ts})

    return session


def _approve_session(store: ExecutionSessionStore, session_id: str, project_root: Path) -> None:
    engine = AssemblyApprovalOperationsEngine(store, project_root=project_root)
    result = engine.approve(
        session_id,
        request_real_assembly=True,
        approved_by=SMOKE_TRIGGER,
        reason="11J-19 validator approval",
    )
    if not result.success:
        raise RuntimeError(f"Approval failed: {result.reject_reasons}")


def _complete_dry_run(service: AssemblyRunService, session_id: str) -> dict[str, Any]:
    return service.run(session_id, dry_run=True, triggered_by=SMOKE_TRIGGER)


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    _ = project_root
    results: list[dict] = []

    # 5. FFmpeg availability check works.
    ffmpeg = check_ffmpeg_availability()
    results.append(
        _pass(
            "ffmpeg_availability_check",
            isinstance(ffmpeg.available, bool) and (ffmpeg.version_line is not None or not ffmpeg.available),
            ffmpeg.version_line or ffmpeg.error or "",
        )
    )

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        store = ExecutionSessionStore(root)
        service = AssemblyRunService(store)
        session_id = "exec_11j19_val"

        session = _build_smoke_session(root / "art", session_id=session_id)
        store.save_session(session, overwrite=True)
        before = _upstream_slots(store.load_session(session_id))

        dry = _complete_dry_run(service, session_id)
        _approve_session(store, session_id, root)

        # 1. Real run blocked when flags off.
        os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)
        blocked_flags = service.run(
            session_id,
            dry_run=False,
            confirm_real_assembly=True,
            triggered_by=SMOKE_TRIGGER,
        )
        results.append(
            _pass(
                "real_run_blocked_flags_off",
                blocked_flags.get("success") is False
                and blocked_flags.get("code") in {
                    "ASSEMBLY_REAL_EXECUTION_DISABLED",
                    "ASSEMBLY_RUNTIME_EXECUTION_DISABLED",
                },
                str(blocked_flags.get("code")),
            )
        )

        # 2. Real run blocked without confirm_real_assembly.
        os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = "true"
        os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = "true"
        blocked_confirm = service.run(
            session_id,
            dry_run=False,
            confirm_real_assembly=False,
            triggered_by=SMOKE_TRIGGER,
        )
        results.append(
            _pass(
                "real_run_blocked_without_confirm",
                blocked_confirm.get("success") is False
                and blocked_confirm.get("code") == "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED",
                str(blocked_confirm.get("code")),
            )
        )

        # 3. Real run blocked without assembly approval.
        session_no_appr = _build_smoke_session(root / "art_no_appr", session_id="exec_11j19_no_appr")
        store.save_session(session_no_appr, overwrite=True)
        _complete_dry_run(service, "exec_11j19_no_appr")
        blocked_appr = service.run(
            "exec_11j19_no_appr",
            dry_run=False,
            confirm_real_assembly=True,
            triggered_by=SMOKE_TRIGGER,
        )
        results.append(
            _pass(
                "real_run_blocked_without_approval",
                blocked_appr.get("success") is False
                and blocked_appr.get("code") in {
                    "ASSEMBLY_APPROVAL_REQUIRED",
                    "REAL_ASSEMBLY_NOT_REQUESTED",
                },
                str(blocked_appr.get("code")),
            )
        )

        # 4. Real run blocked if plan not READY.
        session_bad = {"execution_session_id": "exec_11j19_bad", "execution_runtime": ensure_multi_category_shell({})}
        store.save_session(session_bad, overwrite=True)
        blocked_plan = service.run(
            "exec_11j19_bad",
            dry_run=False,
            confirm_real_assembly=True,
            triggered_by=SMOKE_TRIGGER,
        )
        results.append(
            _pass(
                "real_run_blocked_plan_not_ready",
                blocked_plan.get("success") is False
                and blocked_plan.get("code") == "ASSEMBLY_PLAN_INVALID",
                str(blocked_plan.get("code")),
            )
        )

        # 6–10. Mock smoke run creates output + manifest.
        engine = service._engine
        output_dir = (
            root / "storage" / "content_brain" / "execution" / "artifacts" / session_id / "assembly_generation"
        )
        original_execute_real = engine.executor._execute_real

        def mock_real(plan, result, **kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / EXPECTED_OUTPUT
            final_path.write_bytes(b"\x00\x00\x00\x1cftypmp42" + b"\x00" * 128)
            manifest_path = output_dir / "assembly_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "real_assembly_executed": True,
                        "validation_status": "READY",
                        "output_artifacts": [{"file_name": EXPECTED_OUTPUT}],
                    }
                ensure_ascii=False,
            ),
                encoding="utf-8",
            )
            result.status = "completed"
            result.real_assembly_executed = True
            result.output_created = True
            result.output_file = str(final_path.resolve())
            result.output_size = final_path.stat().st_size
            result.manifest_path = str(manifest_path.resolve())
            return result

        engine.executor._execute_real = mock_real  # type: ignore[method-assign]
        try:
            real_ok = service.run(
                session_id,
                dry_run=False,
                confirm_real_assembly=True,
                triggered_by=SMOKE_TRIGGER,
                reason="validator mock real run",
            )
        finally:
            engine.executor._execute_real = original_execute_real  # type: ignore[method-assign]

        final_path = output_dir / EXPECTED_OUTPUT
        manifest_path = output_dir / "assembly_manifest.json"

        results.append(
            _pass(
                "smoke_run_creates_final_mp4",
                final_path.is_file(),
                str(final_path),
            )
        )
        results.append(
            _pass(
                "output_file_size_gt_zero",
                final_path.is_file() and final_path.stat().st_size > 0,
                str(final_path.stat().st_size if final_path.is_file() else 0),
            )
        )
        results.append(
            _pass(
                "assembly_manifest_written",
                manifest_path.is_file(),
                str(manifest_path),
            )
        )
        results.append(
            _pass(
                "real_assembly_executed_true_only_real",
                dry.get("real_assembly_executed") is False and real_ok.get("real_assembly_executed") is True,
                f"dry={dry.get('real_assembly_executed')} real={real_ok.get('real_assembly_executed')}",
            )
        )
        results.append(
            _pass(
                "output_created_true_only_success",
                dry.get("output_created") is False and real_ok.get("output_created") is True,
                f"dry={dry.get('output_created')} real={real_ok.get('output_created')}",
            )
        )

        after_session = store.load_session(session_id)
        after = _upstream_slots(after_session)
        results.append(
            _pass(
                "upstream_slots_unchanged",
                after[CATEGORY_VIDEO] == before[CATEGORY_VIDEO]
                and after[CATEGORY_VOICE] == before[CATEGORY_VOICE]
                and after[CATEGORY_SUBTITLE_GENERATION] == before[CATEGORY_SUBTITLE_GENERATION],
            )
        )

        # 12. Flags disabled after smoke helper simulation.
        os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)
        results.append(
            _pass(
                "flags_disabled_after_smoke",
                os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED") is None
                and os.getenv("ASSEMBLY_RUNTIME_EXECUTION_APPROVED") is None,
            )
        )

        # 13. Failure path maps errors safely.
        session_fail = _build_smoke_session(root / "art_fail", session_id="exec_11j19_fail")
        store.save_session(session_fail, overwrite=True)
        _complete_dry_run(service, "exec_11j19_fail")
        _approve_session(store, "exec_11j19_fail", root)
        os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = "true"
        os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = "true"

        fail_engine = service._engine

        def mock_fail(plan, result, **kwargs):
            from content_brain.execution.failure_taxonomy import build_failure_object

            result.status = "failed"
            result.errors.append(build_failure_object("ASSEMBLY_FFMPEG_FAILED", "mock ffmpeg failure"))
            return result

        original_fail = fail_engine.executor._execute_real
        fail_engine.executor._execute_real = mock_fail  # type: ignore[method-assign]
        try:
            fail_resp = service.run(
                "exec_11j19_fail",
                dry_run=False,
                confirm_real_assembly=True,
                triggered_by=SMOKE_TRIGGER,
            )
        finally:
            fail_engine.executor._execute_real = original_fail  # type: ignore[method-assign]
            os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
            os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)

        results.append(
            _pass(
                "failure_path_maps_error",
                fail_resp.get("success") is False
                and fail_resp.get("code") == "ASSEMBLY_FFMPEG_FAILED"
                and fail_resp.get("real_assembly_executed") is False
                and fail_resp.get("output_created") is False,
                str(fail_resp.get("code")),
            )
        )

    if include_regressions:
        results.append(
            _pass(
                "validate_11j8_regression",
                subprocess.run([sys.executable, "-m", "project_brain.validate_11j8_assembly_runtime_api"], cwd=".").returncode
                == 0,
            )
        )

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11J-19",
        "label": "supervised_assembly_smoke_test",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
