"""
Phase 11J-8 — assembly runtime API (dry-run) validation.

Verifies the POST /sessions/{id}/assembly/run dry-run lifecycle end-to-end via the
service + engine + policy: plan building, executor dry-run invocation, slot updates,
fail-closed real-execution blocking, upstream-slot immutability, and FFmpeg/legacy
isolation. No FFmpeg, no FINAL_PUBLISH_READY.mp4, no upstream mutation.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from content_brain.execution.assembly_models import EXPECTED_OUTPUT
from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY,
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore
from ui.api.assembly_run_service import AssemblyRunService

POLICY_PATH = Path("content_brain/execution/assembly_run_action_policy.py")
ENGINE_PATH = Path("content_brain/execution/assembly_runtime_engine.py")
SERVICE_PATH = Path("ui/api/assembly_run_service.py")
SCAN_PATHS = (POLICY_PATH, ENGINE_PATH, SERVICE_PATH)


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": bool(ok), "detail": detail}


def _run_module(module: str, *, core_only: bool = True) -> bool:
    from project_brain.validation_policy import run_validator_module

    return run_validator_module(module, core_only=core_only)


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


def _invokes_ffmpeg(module_path: Path) -> bool:
    """Flag real FFmpeg / subprocess usage.

    Importing internal dry-run or availability modules (``assembly_ffmpeg_executor``,
    ``assembly_ffmpeg_availability``) is safe and is NOT flagged.
    """
    allowed_import_prefixes = (
        "content_brain.execution.assembly_ffmpeg_executor",
        "content_brain.execution.assembly_ffmpeg_availability",
    )

    def _allowed_module(name: str) -> bool:
        low = name.lower()
        return any(low == p or low.startswith(p + ".") for p in allowed_import_prefixes)

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                low = alias.name.lower()
                if low == "subprocess" or low == "ffmpeg" or low.startswith("ffmpeg."):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if _allowed_module(node.module):
                continue
            low = node.module.lower()
            if low == "subprocess" or low == "ffmpeg" or low.startswith("ffmpeg."):
                return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literal = node.value.strip().lower()
            if literal in {"ffmpeg.exe", "ffprobe"} or literal.startswith(
                ("ffmpeg -", "ffmpeg.exe ", "ffmpeg.exe-")
            ):
                return True
    return False


def _write(path: Path, content: str = "x") -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _build_session(
    tmp: Path,
    *,
    session_id: str = "exec_11j8",
    subtitle_exts: tuple[str, ...] = ("ass", "srt"),
) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    runtime = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    cr = runtime["category_runtime"]
    ar = runtime["artifacts_by_category"]

    clips = []
    for i in range(2):
        p = tmp / f"clip_{i + 1:03d}.mp4"
        _write(p)
        clips.append({"file_path": str(p)})
    ar[CATEGORY_VIDEO] = clips
    _write(tmp / "video_manifest.json", "{}")
    cr[CATEGORY_VIDEO]["video_manifest_path"] = str(tmp / "video_manifest.json")

    files = []
    for i in range(2):
        p = tmp / f"narration_{i + 1:03d}.mp3"
        _write(p)
        files.append({"segment_index": i, "file_path": str(p), "file_name": p.name})
    _write(tmp / "voice_manifest.json", json.dumps({"files": files}, ensure_ascii=False))
    cr[CATEGORY_VOICE]["voice_manifest_path"] = str(tmp / "voice_manifest.json")
    ar[CATEGORY_VOICE] = [{"file_path": f["file_path"]} for f in files]

    sub_files = []
    for ext in subtitle_exts:
        p = tmp / f"subtitles.{ext}"
        _write(p)
        sub_files.append({"format": ext, "file_path": str(p)})
    if sub_files:
        ar[CATEGORY_SUBTITLE_GENERATION] = sub_files
        _write(tmp / "subtitle_manifest.json", json.dumps({"files": sub_files}, ensure_ascii=False))
        cr[CATEGORY_SUBTITLE_GENERATION]["manifest_path"] = str(tmp / "subtitle_manifest.json")

    return {"execution_session_id": session_id, "execution_runtime": runtime}


def _upstream_slots(session: dict) -> dict:
    cr = (session.get("execution_runtime") or {}).get("category_runtime") or {}
    return {
        CATEGORY_VIDEO: deepcopy(cr.get(CATEGORY_VIDEO)),
        CATEGORY_VOICE: deepcopy(cr.get(CATEGORY_VOICE)),
        CATEGORY_SUBTITLE_GENERATION: deepcopy(cr.get(CATEGORY_SUBTITLE_GENERATION)),
    }


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    _ = project_root
    results: list[dict] = []

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        store = ExecutionSessionStore(root)
        service = AssemblyRunService(store)

        # --- Happy-path dry run -------------------------------------------------
        session = _build_session(root / "art_ok", session_id="exec_11j8")
        store.save_session(session, overwrite=True)
        before = _upstream_slots(store.load_session("exec_11j8"))

        resp = service.run("exec_11j8", dry_run=True)

        after_session = store.load_session("exec_11j8")
        after = _upstream_slots(after_session)
        slot = (
            (after_session.get("execution_runtime") or {})
            .get("category_runtime", {})
            .get(CATEGORY_ASSEMBLY_GENERATION)
            or {}
        )

        # 1. Dry-run request succeeds.
        results.append(_pass("dry_run_succeeds", resp.get("success") is True and resp.get("status") == "completed", str(resp.get("status"))))
        # 2. AssemblyPlan built (READY, modes resolved).
        results.append(_pass("assembly_plan_built", resp.get("validation_status") == "READY" and bool(resp.get("assembly_mode")), str(resp.get("validation_status"))))
        # 3. Executor invoked in dry-run mode (dry-run markers present).
        results.append(_pass("executor_dry_run_invoked", resp.get("real_assembly_executed") is False and resp.get("output_created") is False and resp.get("status") == "completed"))
        # 4. planned_steps returned.
        results.append(_pass("planned_steps_returned", len(resp.get("planned_steps") or []) >= 5, str(len(resp.get("planned_steps") or []))))
        # 5. expected_output returned.
        results.append(_pass("expected_output_returned", resp.get("expected_output") == EXPECTED_OUTPUT, str(resp.get("expected_output"))))
        # 6. output_created=false.
        results.append(_pass("output_created_false", resp.get("output_created") is False))
        # 7. real_assembly_executed=false.
        results.append(_pass("real_assembly_executed_false", resp.get("real_assembly_executed") is False))
        # 8. assembly_generation slot updated.
        results.append(
            _pass(
                "assembly_slot_updated",
                slot.get("status") == "completed"
                and slot.get("executed") is False
                and slot.get("dry_run") is True
                and len(slot.get("planned_steps") or []) >= 5,
                str(slot.get("status")),
            )
        )

        # --- Fail-closed: dry_run=false -----------------------------------------
        session2 = _build_session(root / "art_real", session_id="exec_11j8_real")
        store.save_session(session2, overwrite=True)
        resp_real = service.run("exec_11j8_real", dry_run=False)
        final_real = root / "artifacts" / "exec_11j8_real" / "assembly_generation" / EXPECTED_OUTPUT
        # 9. dry_run=false blocked without full real-run gates.
        blocked_codes = {
            "ASSEMBLY_REAL_EXECUTION_DISABLED",
            "ASSEMBLY_REAL_EXECUTION_NOT_CONFIRMED",
            "ASSEMBLY_DRY_RUN_NOT_COMPLETED",
            "ASSEMBLY_APPROVAL_REQUIRED",
        }
        results.append(
            _pass(
                "dry_run_false_blocked",
                resp_real.get("success") is False
                and resp_real.get("code") in blocked_codes
                and resp_real.get("real_assembly_executed") is False
                and resp_real.get("output_created") is False
                and not final_real.exists(),
                str(resp_real.get("code")),
            )
        )

        # 10–12. Mutation flags false in response.
        results.append(_pass("video_mutated_false", resp.get("video_mutated") is False))
        results.append(_pass("voice_mutated_false", resp.get("voice_mutated") is False))
        results.append(_pass("subtitle_mutated_false", resp.get("subtitle_mutated") is False))

        # 13–15. Upstream slots unchanged on disk.
        results.append(_pass("video_slot_unchanged", after[CATEGORY_VIDEO] == before[CATEGORY_VIDEO]))
        results.append(_pass("voice_slot_unchanged", after[CATEGORY_VOICE] == before[CATEGORY_VOICE]))
        results.append(_pass("subtitle_slot_unchanged", after[CATEGORY_SUBTITLE_GENERATION] == before[CATEGORY_SUBTITLE_GENERATION]))

        # No FINAL_PUBLISH_READY.mp4 anywhere under the store.
        final_ok = root / "artifacts" / "exec_11j8" / "assembly_generation" / EXPECTED_OUTPUT
        results.append(_pass("no_final_video_created", not final_ok.exists()))

    # 16. No FFmpeg import/call in policy/engine/service.
    #     (Importing the internal dry-run module assembly_ffmpeg_executor is allowed.)
    results.append(
        _pass(
            "no_ffmpeg_import_or_call",
            not any(_invokes_ffmpeg(p) for p in SCAN_PATHS),
        )
    )

    # 17. No full_video_pipeline import.
    results.append(
        _pass(
            "no_full_video_pipeline_import",
            not any(_imports_forbidden(p, "full_video_pipeline") for p in SCAN_PATHS),
        )
    )

    # 18–21. Regression validators.
    if include_regressions:
        results.append(
            _pass("validate_11j6_regression", _run_module("project_brain.validate_11j6_assembly_ffmpeg_executor_dry_run", core_only=True))
        )
        results.append(
            _pass("validate_11j4_regression", _run_module("project_brain.validate_11j4_assembly_plan_builder", core_only=True))
        )
        results.append(
            _pass("validate_11i8_regression", _run_module("project_brain.validate_11i8_subtitle_runtime_execution_api", core_only=True))
        )
        results.append(
            _pass(
                "validate_11h2d_regression",
                _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution", core_only=True),
            )
        )

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="11J-8",
        label="assembly_runtime_api",
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
