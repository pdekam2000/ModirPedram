"""
Phase 11I-8 — subtitle runtime execution API validation.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from content_brain.execution.category_runtime_compat import (
    SUBTITLE_ARTIFACT_CATEGORY,
    ensure_multi_category_shell,
)
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.subtitle_format_writer import (
    DEFAULT_FILENAMES,
    MANIFEST_FILENAME,
)
from ui.api.subtitle_run_service import SubtitleRunService


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    return result.returncode == 0


def _module_imports_forbidden(module_path: Path, forbidden: str) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if forbidden in alias.name:
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and forbidden in node.module:
            return True
    return False


def _module_invokes_ffmpeg(module_path: Path) -> bool:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "ffmpeg" in alias.name.lower():
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and "ffmpeg" in node.module.lower():
            return True
    return False


def _session_narration_only(session_id: str, *, beats: list[dict] | None = None) -> dict:
    beat_plans = beats or [
        {
            "beat_id": "HOOK",
            "narration": "Watch this hidden replay angle before the final decision.",
        }
    ]
    return {
        "execution_session_id": session_id,
        "topic": "football VAR controversy",
        "brief_snapshot": {
            "topic": "football VAR controversy",
            "content_format": {"default_duration_seconds": 24},
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {"beat_plans": beat_plans}
                }
            },
        },
        "execution_runtime": ensure_multi_category_shell(
            {"category_runtime": {}, "artifacts_by_category": {}}
        ),
    }


def _session_with_manifest(session_id: str, manifest_path: Path, *, beats: list[dict] | None = None) -> dict:
    session = _session_narration_only(session_id, beats=beats)
    runtime = session["execution_runtime"]
    category_runtime = dict(_dict(runtime.get("category_runtime")))
    category_runtime[CATEGORY_VOICE] = {
        **dict(_dict(category_runtime.get(CATEGORY_VOICE))),
        "status": "completed",
        "executed": True,
        "voice_manifest_path": str(manifest_path.resolve()),
    }
    runtime["category_runtime"] = category_runtime
    session["execution_runtime"] = runtime
    return session


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    service = SubtitleRunService(store)
    results: list[dict] = []
    example_artifact_dir = ""

    # 1. Narration text run
    text_sid = "exec_11i8_narration_text"
    text_session = _session_narration_only(text_sid)
    store.save_session(text_session, overwrite=True)
    text_result = service.run(text_sid, overwrite=True, triggered_by="validator")
    text_slot = _dict(text_result.get("subtitle_slot"))
    artifact_dir = store.artifact_dir(text_sid, SUBTITLE_ARTIFACT_CATEGORY)
    example_artifact_dir = str(artifact_dir.resolve())
    results.append(
        _pass(
            "generates_subtitles_from_narration_text",
            text_result.get("success") is True and text_result.get("cue_count", 0) >= 1,
            str(text_result.get("cue_count")),
        )
    )

    # 2. Voice manifest timing run
    with tempfile.TemporaryDirectory() as tmp_dir:
        manifest_path = Path(tmp_dir) / "voice_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "duration_seconds": 18.0,
                    "tts_executed": True,
                    "files": [
                        {
                            "segment_index": 0,
                            "duration_seconds": 8.0,
                            "file_path": str(Path(tmp_dir) / "seg_0.mp3"),
                        },
                        {
                            "segment_index": 1,
                            "duration_seconds": 10.0,
                            "file_path": str(Path(tmp_dir) / "seg_1.mp3"),
                        },
                    ],
                },
                indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        timing_sid = "exec_11i8_voice_timing"
        timing_session = _session_with_manifest(
            timing_sid,
            manifest_path,
            beats=[
                {"beat_id": "HOOK", "narration": "First segment about the replay angle."},
                {"beat_id": "PAYOFF", "narration": "Second segment explains the final decision."},
            ],
        )
        store.save_session(timing_session, overwrite=True)
        timing_result = service.run(timing_sid, overwrite=True, triggered_by="validator")
        results.append(
            _pass(
                "generates_subtitles_from_voice_manifest_timing",
                timing_result.get("success") is True
                and timing_result.get("timing_strategy") == "audio_duration",
                str(timing_result.get("timing_strategy")),
            )
        )

    # 3. Writes SRT/VTT/ASS
    srt_path = artifact_dir / DEFAULT_FILENAMES["srt"]
    vtt_path = artifact_dir / DEFAULT_FILENAMES["vtt"]
    ass_path = artifact_dir / DEFAULT_FILENAMES["ass"]
    results.append(
        _pass(
            "writes_srt_vtt_ass",
            srt_path.is_file() and vtt_path.is_file() and ass_path.is_file(),
            f"srt={srt_path.is_file()} vtt={vtt_path.is_file()} ass={ass_path.is_file()}",
        )
    )

    # 4. Slot completed
    results.append(
        _pass(
            "subtitle_slot_status_completed",
            text_slot.get("status") == "completed" and text_slot.get("executed") is True,
            str(text_slot.get("status")),
        )
    )

    # 5. video_mutated / voice_mutated false
    results.append(
        _pass(
            "response_video_mutated_false",
            text_result.get("video_mutated") is False,
        )
    )
    results.append(
        _pass(
            "response_voice_mutated_false",
            text_result.get("voice_mutated") is False,
        )
    )

    # 6. Unsupported format
    bad_sid = "exec_11i8_unsupported"
    store.save_session(_session_narration_only(bad_sid), overwrite=True)
    bad_result = service.run(bad_sid, formats=["txt"], overwrite=True)
    results.append(
        _pass(
            "unsupported_format_fails_safely",
            bad_result.get("success") is False and bad_result.get("code") == "UNSUPPORTED_FORMAT",
            str(bad_result.get("code")),
        )
    )

    # 7. overwrite=False blocks
    block_sid = "exec_11i8_overwrite_block"
    block_dir = store.artifact_dir(block_sid, SUBTITLE_ARTIFACT_CATEGORY)
    if block_dir.exists():
        shutil.rmtree(block_dir)
    store.save_session(_session_narration_only(block_sid), overwrite=True)
    first = service.run(block_sid, overwrite=False)
    second = service.run(block_sid, overwrite=False)
    results.append(
        _pass(
            "overwrite_false_blocks_existing",
            first.get("success") is True
            and second.get("success") is False
            and second.get("code") in {"FILE_EXISTS", "OVERWRITE_REQUIRED"},
            str(second.get("code")),
        )
    )

    # 8. overwrite=True rewrites
    rewrite_sid = "exec_11i8_overwrite_allow"
    rewrite_dir = store.artifact_dir(rewrite_sid, SUBTITLE_ARTIFACT_CATEGORY)
    if rewrite_dir.exists():
        shutil.rmtree(rewrite_dir)
    store.save_session(_session_narration_only(rewrite_sid), overwrite=True)
    rewrite_first = service.run(rewrite_sid, overwrite=False)
    rewrite_second = service.run(rewrite_sid, overwrite=True)
    results.append(
        _pass(
            "overwrite_true_rewrites_safely",
            rewrite_first.get("success") is True and rewrite_second.get("success") is True,
        )
    )

    # 9-11. Safety scans
    engine_path = root / "content_brain/execution/subtitle_runtime_engine.py"
    policy_path = root / "content_brain/execution/subtitle_run_action_policy.py"
    service_path = root / "ui/api/subtitle_run_service.py"
    scan_paths = [engine_path, policy_path, service_path]
    results.append(
        _pass(
            "no_ffmpeg_import",
            all(not _module_invokes_ffmpeg(path) for path in scan_paths),
        )
    )
    results.append(
        _pass(
            "no_legacy_subtitle_engine_import",
            all(not _module_imports_forbidden(path, "subtitle_engine") for path in scan_paths),
        )
    )
    results.append(
        _pass(
            "no_full_video_pipeline_import",
            all(not _module_imports_forbidden(path, "full_video_pipeline") for path in scan_paths),
        )
    )

    # 12-13. Voice/video unchanged
    preserve_sid = "exec_11i8_preserve_slots"
    preserve_dir = store.artifact_dir(preserve_sid, SUBTITLE_ARTIFACT_CATEGORY)
    if preserve_dir.exists():
        shutil.rmtree(preserve_dir)
    preserve_session = _session_narration_only(preserve_sid)
    voice_before = deepcopy(
        preserve_session["execution_runtime"]["category_runtime"][CATEGORY_VOICE]
    )
    video_before = deepcopy(
        preserve_session["execution_runtime"]["category_runtime"][CATEGORY_VIDEO]
    )
    store.save_session(preserve_session, overwrite=True)
    service.run(preserve_sid, overwrite=True)
    loaded = store.load_session(preserve_sid)
    voice_after = deepcopy(loaded["execution_runtime"]["category_runtime"][CATEGORY_VOICE])
    video_after = deepcopy(loaded["execution_runtime"]["category_runtime"][CATEGORY_VIDEO])
    results.append(_pass("voice_slot_unchanged", voice_after == voice_before))
    results.append(_pass("video_slot_unchanged", video_after == video_before))

    # Manifest written
    manifest_path = artifact_dir / MANIFEST_FILENAME
    results.append(
        _pass(
            "writes_subtitle_manifest",
            manifest_path.is_file(),
            str(manifest_path),
        )
    )

    # Regressions
    results.append(_pass("validate_11i6_regression", _run_module("project_brain.validate_11i6_subtitle_format_writers")))
    results.append(_pass("validate_11i4_regression", _run_module("project_brain.validate_11i4_subtitle_cue_generation_engine")))
    results.append(_pass("validate_11i2_regression", _run_module("project_brain.validate_11i2_subtitle_runtime_foundation")))
    results.append(
        _pass(
            "validate_11h2d_regression",
            _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"),
        )
    )

    passed = sum(1 for item in results if item["pass"])
    failed = [item for item in results if not item["pass"]]
    return {
        "phase": "11I-8",
        "title": "Subtitle Runtime Execution API",
        "passed": passed,
        "failed": len(failed),
        "total": len(results),
        "all_pass": len(failed) == 0,
        "example_artifact_dir": example_artifact_dir,
        "endpoint": "POST /sessions/{session_id}/subtitle/run",
        "results": results,
        "failures": failed,
    }


def main() -> int:
    report = run_matrix(".")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for item in report["results"]:
        status = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{status}] {item['test']}{detail}")
    print(f"\nSummary: {report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
