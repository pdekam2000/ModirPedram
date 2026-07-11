"""
Phase 11J-6 — assembly FFmpeg executor dry-run validation.

Verifies the dry-run execution contract, planned-step preview, failure taxonomy,
cancellation hook, and output planning — with NO FFmpeg, NO FINAL_PUBLISH_READY.mp4,
and NO upstream slot mutation.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from content_brain.execution.assembly_ffmpeg_executor import (
    AssemblyExecutionResult,
    AssemblyFFmpegExecutor,
)
from content_brain.execution.assembly_models import EXPECTED_OUTPUT
from content_brain.execution.assembly_plan_builder import AssemblyPlanBuilder
from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)

EXECUTOR_PATH = Path("content_brain/execution/assembly_ffmpeg_executor.py")


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


def _invokes_ffmpeg_or_subprocess(module_path: Path) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                low = alias.name.lower()
                if "ffmpeg" in low or low == "subprocess":
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            low = node.module.lower()
            if "ffmpeg" in low or low == "subprocess":
                return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literal = node.value.strip().lower()
            if literal in {"ffmpeg", "ffmpeg.exe", "ffprobe"} or literal.startswith(
                ("ffmpeg ", "ffmpeg.exe ")
            ):
                return True
    return False


def _write(path: Path, content: str = "x") -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _build_session(tmp: Path, *, with_video: bool = True, subtitle_exts=("ass", "srt")) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    runtime = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    cr = runtime["category_runtime"]
    ar = runtime["artifacts_by_category"]

    if with_video:
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

    return {"execution_session_id": "exec_11j6", "execution_runtime": runtime}


def _error_codes(result: AssemblyExecutionResult) -> set[str]:
    return {str(err.get("code")) for err in result.errors}


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = True) -> dict:
    _ = project_root
    builder = AssemblyPlanBuilder(".")
    executor = AssemblyFFmpegExecutor()
    results: list[dict] = []

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)

        ready_plan = builder.build(_build_session(root / "ready"))
        dry = executor.execute(ready_plan)

        # 1. Dry-run accepts READY plan.
        results.append(_pass("dry_run_accepts_ready", dry.status == "dry_run", dry.status))
        # 2. Returns planned steps.
        results.append(_pass("returns_planned_steps", len(dry.planned_steps) >= 5, str(len(dry.planned_steps))))
        # 3. Does not create FINAL_PUBLISH_READY.mp4.
        final_path = Path(ready_plan.output_dir or "") / EXPECTED_OUTPUT
        results.append(_pass("no_final_video_created", not final_path.exists()))
        # 4. real_assembly_executed=false.
        results.append(_pass("real_execution_false", dry.real_assembly_executed is False))
        # 5. output_created=false.
        results.append(_pass("output_created_false", dry.output_created is False))

        # 6. dry_run=False without real_execution_allowed → ASSEMBLY_REAL_EXECUTION_DISABLED.
        real = executor.execute(ready_plan, dry_run=False, real_execution_allowed=False)
        results.append(
            _pass(
                "real_execution_disabled",
                real.status == "failed" and "ASSEMBLY_REAL_EXECUTION_DISABLED" in _error_codes(real),
                ",".join(_error_codes(real)),
            )
        )

        # 7. Invalid plan → ASSEMBLY_PLAN_INVALID.
        partial_plan = builder.build(_build_session(root / "nosub", subtitle_exts=()))  # PARTIAL
        invalid = executor.execute(partial_plan)
        none_result = executor.execute(None)  # type: ignore[arg-type]
        results.append(
            _pass(
                "invalid_plan_rejected",
                "ASSEMBLY_PLAN_INVALID" in _error_codes(invalid)
                and "ASSEMBLY_PLAN_INVALID" in _error_codes(none_result),
                ",".join(_error_codes(invalid)),
            )
        )

        # 8. Missing video fails or blocks safely.
        novideo_plan = builder.build(_build_session(root / "novideo", with_video=False))
        novideo = executor.execute(novideo_plan)
        results.append(
            _pass(
                "missing_video_blocks_safely",
                novideo.status == "failed"
                and bool(_error_codes(novideo) & {"ASSEMBLY_PLAN_INVALID", "ASSEMBLY_VIDEO_MISSING"}),
                f"{novideo.status}:{','.join(_error_codes(novideo))}",
            )
        )

        # 9. Cancellation before execution → ASSEMBLY_CANCELLED.
        cancelled = executor.execute(ready_plan, cancel_check=lambda: True)
        results.append(
            _pass(
                "cancellation_returns_cancelled",
                cancelled.status == "cancelled" and "ASSEMBLY_CANCELLED" in _error_codes(cancelled),
                cancelled.status,
            )
        )

        # 10. Expected output under assembly_generation artifact dir.
        out = (ready_plan.output_dir or "").replace("\\", "/")
        results.append(
            _pass(
                "output_under_assembly_dir",
                out.endswith("artifacts/exec_11j6/assembly_generation")
                and dry.expected_output == EXPECTED_OUTPUT,
                out,
            )
        )

        # 13. Upstream slots not mutated.
        iso_session = _build_session(root / "iso")
        cr = iso_session["execution_runtime"]["category_runtime"]
        video_before = deepcopy(cr[CATEGORY_VIDEO])
        voice_before = deepcopy(cr[CATEGORY_VOICE])
        subtitle_before = deepcopy(cr[CATEGORY_SUBTITLE_GENERATION])
        iso_plan = builder.build(iso_session)
        executor.execute(iso_plan)
        results.append(
            _pass(
                "upstream_slots_unchanged",
                cr[CATEGORY_VIDEO] == video_before
                and cr[CATEGORY_VOICE] == voice_before
                and cr[CATEGORY_SUBTITLE_GENERATION] == subtitle_before,
            )
        )

    # 11. Real FFmpeg gated to executor module only (subprocess allowed in 11J-19+).
    results.append(
        _pass(
            "no_full_video_pipeline_import",
            not _imports_forbidden(EXECUTOR_PATH, "full_video_pipeline"),
        )
    )

    # 14–17. Regression validators.
    if include_regressions:
        results.append(_pass("validate_11j4_regression", _run_module("project_brain.validate_11j4_assembly_plan_builder")))
        results.append(_pass("validate_11j2_regression", _run_module("project_brain.validate_11j2_assembly_runtime_foundation")))
        results.append(_pass("validate_11i8_regression", _run_module("project_brain.validate_11i8_subtitle_runtime_execution_api")))
        results.append(_pass("validate_11h2d_regression", _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution")))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11J-6",
        "label": "assembly_ffmpeg_executor_dry_run",
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
