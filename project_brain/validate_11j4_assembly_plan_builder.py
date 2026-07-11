"""
Phase 11J-4 — assembly plan builder validation.

Verifies deterministic artifact selection, subtitle/assembly mode resolution,
validation status mapping, upstream-slot immutability, and FFmpeg/legacy isolation.
No FFmpeg, no media processing, no FINAL_PUBLISH_READY.mp4 generation.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from content_brain.execution.assembly_plan_builder import AssemblyPlanBuilder
from content_brain.execution.assembly_models import (
    EXPECTED_OUTPUT,
    MODE_VIDEO_VOICE,
    MODE_VIDEO_VOICE_SUBTITLE,
    SUBTITLE_MODE_BURN_IN,
    SUBTITLE_MODE_NONE,
    SUBTITLE_MODE_SIDECAR,
    VALIDATION_FAILED,
    VALIDATION_PARTIAL,
    VALIDATION_READY,
)
from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)

BUILDER_PATH = Path("content_brain/execution/assembly_plan_builder.py")


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


def _invokes_ffmpeg(module_path: Path) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "ffmpeg" in alias.name.lower():
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and "ffmpeg" in node.module.lower():
            return True
        if isinstance(node, ast.Attribute) and "ffmpeg" in node.attr.lower():
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


def _build_session(
    tmp: Path,
    *,
    clips: int = 2,
    narration: int = 2,
    subtitle_exts: tuple[str, ...] = ("ass", "srt"),
    manifests: bool = True,
    reverse_clip_order: bool = True,
    reverse_segment_index: bool = True,
) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    runtime = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    cr = runtime["category_runtime"]
    ar = runtime["artifacts_by_category"]

    video_entries = []
    for i in range(clips):
        p = tmp / f"clip_{i + 1:03d}.mp4"
        _write(p)
        video_entries.append({"file_path": str(p)})
    if reverse_clip_order and len(video_entries) >= 2:
        video_entries = list(reversed(video_entries))
    ar[CATEGORY_VIDEO] = video_entries
    if clips and manifests:
        _write(tmp / "video_manifest.json", "{}")
        cr[CATEGORY_VIDEO]["video_manifest_path"] = str(tmp / "video_manifest.json")

    if narration:
        files = []
        for i in range(narration):
            p = tmp / f"narration_{i + 1:03d}.mp3"
            _write(p)
            seg = (narration - 1 - i) if reverse_segment_index else i
            files.append({"segment_index": seg, "file_path": str(p), "file_name": p.name})
        if manifests:
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
        if manifests:
            _write(tmp / "subtitle_manifest.json", json.dumps({"files": sub_files}, ensure_ascii=False))
            cr[CATEGORY_SUBTITLE_GENERATION]["manifest_path"] = str(tmp / "subtitle_manifest.json")

    return {"execution_session_id": "exec_11j4", "execution_runtime": runtime}


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = True) -> dict:
    _ = project_root
    builder = AssemblyPlanBuilder(".")
    results: list[dict] = []

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)

        # 1. Builds plan with video + voice + ass subtitle.
        s1 = _build_session(root / "t1", subtitle_exts=("ass", "srt", "vtt"))
        p1 = builder.build(s1)
        results.append(
            _pass(
                "builds_full_plan",
                p1.assembly_mode == MODE_VIDEO_VOICE_SUBTITLE
                and p1.validation_status == VALIDATION_READY
                and any(i.role == "clip" for i in p1.video_inputs)
                and any(i.role == "narration" for i in p1.audio_inputs),
                f"{p1.assembly_mode}/{p1.validation_status}",
            )
        )

        # 2. Picks ASS before SRT/VTT.
        results.append(
            _pass(
                "picks_ass_first",
                any(i.role == "subtitle_ass" for i in p1.subtitle_inputs)
                and p1.subtitle_mode == SUBTITLE_MODE_BURN_IN,
                p1.subtitle_mode,
            )
        )

        # 3. Falls back to SRT when ASS missing.
        s3 = _build_session(root / "t3", subtitle_exts=("srt", "vtt"))
        p3 = builder.build(s3)
        results.append(
            _pass(
                "fallback_srt_sidecar",
                any(i.role == "subtitle_srt" for i in p3.subtitle_inputs)
                and p3.subtitle_mode == SUBTITLE_MODE_SIDECAR,
                p3.subtitle_mode,
            )
        )

        # 4. subtitle_mode=none when no subtitles.
        s4 = _build_session(root / "t4", subtitle_exts=())
        p4 = builder.build(s4)
        results.append(
            _pass(
                "no_subtitle_mode_none",
                p4.subtitle_mode == SUBTITLE_MODE_NONE and p4.assembly_mode == MODE_VIDEO_VOICE,
                f"{p4.subtitle_mode}/{p4.assembly_mode}",
            )
        )

        # 5. Orders video clips by clip index.
        clip_names = [i.file_name for i in p1.video_inputs if i.role == "clip"]
        results.append(
            _pass(
                "orders_clips_by_index",
                clip_names == sorted(clip_names),
                ",".join(str(n) for n in clip_names),
            )
        )

        # 6. Orders voice inputs by segment_index.
        s6 = _build_session(root / "t6", narration=3, reverse_segment_index=True)
        p6 = builder.build(s6)
        narration_names = [i.file_name for i in p6.audio_inputs if i.role == "narration"]
        # segment_index reversed => narration_003 (seg 0) first ... narration_001 (seg 2) last.
        expected = ["narration_003.mp3", "narration_002.mp3", "narration_001.mp3"]
        results.append(
            _pass(
                "orders_voice_by_segment_index",
                narration_names == expected,
                ",".join(narration_names),
            )
        )

        # 7. Dedupes duplicate artifact paths.
        s7 = _build_session(root / "t7", subtitle_exts=("ass",))
        s7["execution_runtime"]["artifacts_by_category"][CATEGORY_VIDEO] = (
            s7["execution_runtime"]["artifacts_by_category"][CATEGORY_VIDEO] * 3
        )
        p7 = builder.build(s7)
        results.append(
            _pass(
                "dedupes_duplicate_paths",
                sum(1 for i in p7.video_inputs if i.role == "clip") == 2,
                str(sum(1 for i in p7.video_inputs if i.role == "clip")),
            )
        )

        # 8. READY when required artifacts/manifests exist.
        results.append(_pass("ready_when_complete", p1.validation_status == VALIDATION_READY))

        # 9. PARTIAL when one input group missing (subtitle missing).
        results.append(_pass("partial_when_group_missing", p4.validation_status == VALIDATION_PARTIAL, p4.validation_status))

        # 10. FAILED when no usable video.
        s10 = _build_session(root / "t10", clips=0, subtitle_exts=("ass",))
        p10 = builder.build(s10)
        results.append(_pass("failed_when_no_video", p10.validation_status == VALIDATION_FAILED, p10.validation_status))

        # 11–13. Upstream slots unchanged.
        s_iso = _build_session(root / "tiso", subtitle_exts=("ass", "srt"))
        cr = s_iso["execution_runtime"]["category_runtime"]
        video_before = deepcopy(cr[CATEGORY_VIDEO])
        voice_before = deepcopy(cr[CATEGORY_VOICE])
        subtitle_before = deepcopy(cr[CATEGORY_SUBTITLE_GENERATION])
        builder.build(s_iso)
        results.append(_pass("video_slot_unchanged", cr[CATEGORY_VIDEO] == video_before))
        results.append(_pass("voice_slot_unchanged", cr[CATEGORY_VOICE] == voice_before))
        results.append(_pass("subtitle_slot_unchanged", cr[CATEGORY_SUBTITLE_GENERATION] == subtitle_before))

        # 14. Does not write FINAL_PUBLISH_READY.mp4.
        s14 = _build_session(root / "t14", subtitle_exts=("ass",))
        p14 = builder.build(s14)
        final_path = Path(p14.output_dir or "") / EXPECTED_OUTPUT
        results.append(
            _pass(
                "no_final_video_written",
                not final_path.exists() and p14.expected_output == EXPECTED_OUTPUT,
            )
        )

    # 15. No FFmpeg import/call.
    results.append(
        _pass(
            "no_ffmpeg_import_or_call",
            not (_invokes_ffmpeg(BUILDER_PATH) or _imports_forbidden(BUILDER_PATH, "ffmpeg")),
        )
    )

    # 16. No full_video_pipeline import.
    results.append(
        _pass("no_full_video_pipeline_import", not _imports_forbidden(BUILDER_PATH, "full_video_pipeline"))
    )

    # 17–19. Regression validators.
    if include_regressions:
        results.append(
            _pass(
                "validate_11j2_regression",
                _run_module("project_brain.validate_11j2_assembly_runtime_foundation"),
            )
        )
        results.append(
            _pass(
                "validate_11i8_regression",
                _run_module("project_brain.validate_11i8_subtitle_runtime_execution_api"),
            )
        )
        results.append(
            _pass(
                "validate_11h2d_regression",
                _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"),
            )
        )

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11J-4",
        "label": "assembly_plan_builder",
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
