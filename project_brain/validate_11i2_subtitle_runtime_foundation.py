"""
Phase 11I-2 — subtitle runtime foundation validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from content_brain.execution.category_runtime_compat import (
    SUBTITLE_SUPPORTED_FORMATS,
    build_category_runtime_view,
    ensure_multi_category_shell,
    get_category_slot,
    sync_subtitle_category_aliases,
)
from content_brain.execution.provider_categories import (
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_SUBTITLES,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.subtitle_artifact_validator import SubtitleArtifactValidator
from content_brain.execution.subtitle_preflight_runtime_slot import (
    SOURCE_NARRATION_TEXT_ONLY,
    SOURCE_NARRATION_WITH_TIMING,
    SOURCE_UNAVAILABLE,
    apply_subtitle_preflight_dry_run,
)
from ui.api.services.panel_extractor import PanelExtractor


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _session_with_narration(session_id: str) -> dict:
    return {
        "execution_session_id": session_id,
        "state": "COMPLETED",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {"beat_id": "HOOK", "narration": "Subtitle foundation narration text."},
                        ]
                    }
                }
            }
        },
        "execution_runtime": ensure_multi_category_shell(
            {"category_runtime": {}, "artifacts_by_category": {}}
        ),
    }


def _session_with_voice_manifest(session_id: str, manifest_path: Path) -> dict:
    session = _session_with_narration(session_id)
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


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    return result.returncode == 0


def _module_invokes_ffmpeg(module_path: Path) -> bool:
    import ast

    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "ffmpeg" in alias.name.lower():
                    return True
        if isinstance(node, ast.ImportFrom) and node.module and "ffmpeg" in node.module.lower():
            return True
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in {"run", "call", "Popen"}:
                if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if "ffmpeg" in arg.value.lower():
                                return True
    return False


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    # 1. Legacy subtitles aliases to subtitle_generation
    legacy_runtime = {
        "category_runtime": {
            CATEGORY_SUBTITLES: {
                "status": "planned",
                "provider": "internal",
                "runtime_notes": ["legacy"],
            }
        },
        "artifacts_by_category": {},
    }
    sync_subtitle_category_aliases(legacy_runtime["category_runtime"])
    legacy_slot = legacy_runtime["category_runtime"][CATEGORY_SUBTITLES]
    canon_slot = legacy_runtime["category_runtime"][CATEGORY_SUBTITLE_GENERATION]
    results.append(
        _pass(
            "legacy_subtitles_aliases_subtitle_generation",
            legacy_slot is canon_slot
            and legacy_slot.get("category_name") == CATEGORY_SUBTITLE_GENERATION,
            str(legacy_slot.get("category_name")),
        )
    )

    # 2. New sessions expose subtitle_generation
    shell = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    results.append(
        _pass(
            "new_session_exposes_subtitle_generation",
            CATEGORY_SUBTITLE_GENERATION in shell.get("category_runtime", {}),
        )
    )
    view_keys = [item.get("category_key") for item in build_category_runtime_view(shell)]
    results.append(
        _pass(
            "category_view_uses_subtitle_generation_key",
            CATEGORY_SUBTITLE_GENERATION in view_keys,
            ",".join(str(k) for k in view_keys),
        )
    )

    # 3. No source → skipped
    empty_session = {
        "execution_session_id": "exec_11i2_empty",
        "execution_runtime": ensure_multi_category_shell(
            {"category_runtime": {}, "artifacts_by_category": {}}
        ),
    }
    empty_runtime = apply_subtitle_preflight_dry_run(
        empty_session,
        empty_session["execution_runtime"],
    )
    empty_slot = get_category_slot({"execution_runtime": empty_runtime}, CATEGORY_SUBTITLE_GENERATION)
    results.append(
        _pass(
            "no_source_subtitle_skipped",
            empty_slot.get("status") == "skipped"
            and empty_slot.get("source_type") == SOURCE_UNAVAILABLE
            and empty_slot.get("source_ready") is False,
            str(empty_slot.get("status")),
        )
    )

    # 4. Narration text → pending / narration_text_only
    text_session = _session_with_narration("exec_11i2_text")
    text_runtime = apply_subtitle_preflight_dry_run(text_session, text_session["execution_runtime"])
    text_slot = get_category_slot({"execution_runtime": text_runtime}, CATEGORY_SUBTITLE_GENERATION)
    results.append(
        _pass(
            "narration_text_pending",
            text_slot.get("status") == "pending"
            and text_slot.get("source_type") == SOURCE_NARRATION_TEXT_ONLY
            and text_slot.get("source_ready") is True,
            str(text_slot.get("source_type")),
        )
    )

    # 5. Voice manifest/timing → pending / narration_with_timing
    with tempfile.TemporaryDirectory() as tmp_dir:
        manifest_path = Path(tmp_dir) / "voice_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "manifest_version": "11h2_mock_v1",
                    "segment_count": 1,
                    "duration_seconds": 7.4,
                    "tts_executed": True,
                    "files": [{"segment_index": 0, "file_path": str(Path(tmp_dir) / "seg_0.mp3")}],
                },
                indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        timing_session = _session_with_voice_manifest("exec_11i2_timing", manifest_path)
        timing_runtime = apply_subtitle_preflight_dry_run(timing_session, timing_session["execution_runtime"])
        timing_slot = get_category_slot({"execution_runtime": timing_runtime}, CATEGORY_SUBTITLE_GENERATION)
        results.append(
            _pass(
                "voice_manifest_timing_pending",
                timing_slot.get("status") == "pending"
                and timing_slot.get("source_type") == SOURCE_NARRATION_WITH_TIMING
                and timing_slot.get("source_ready") is True,
                str(timing_slot.get("source_type")),
            )
        )

    # 6. Supported formats
    results.append(
        _pass(
            "supported_formats_srt_ass_vtt",
            set(SUBTITLE_SUPPORTED_FORMATS) == {"srt", "ass", "vtt"},
            ",".join(SUBTITLE_SUPPORTED_FORMATS),
        )
    )

    # 7–9. Validator cases
    validator = SubtitleArtifactValidator()
    with tempfile.TemporaryDirectory() as tmp_dir:
        srt_path = Path(tmp_dir) / "sample.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nHello subtitle foundation.\n",
            encoding="utf-8",
        )
        valid_result = validator.validate([{"file_path": str(srt_path)}])
        results.append(_pass("validator_passes_nonempty_srt", valid_result.passed))

        missing_result = validator.validate([{"file_path": str(Path(tmp_dir) / "missing.srt")}])
        results.append(_pass("validator_fails_missing_file", not missing_result.passed))

        bad_ext_path = Path(tmp_dir) / "sample.txt"
        bad_ext_path.write_text("not a subtitle", encoding="utf-8")
        bad_ext_result = validator.validate([{"file_path": str(bad_ext_path)}])
        results.append(_pass("validator_fails_unsupported_extension", not bad_ext_result.passed))

    # 10. Preflight generates no subtitle files
    artifact_root = root / "storage/content_brain/execution/artifacts/exec_11i2_preflight_check/subtitle_generation"
    if artifact_root.exists():
        before = list(artifact_root.glob("*"))
    else:
        before = []
    preflight_session = _session_with_narration("exec_11i2_preflight_check")
    apply_subtitle_preflight_dry_run(preflight_session, preflight_session["execution_runtime"])
    after = list(artifact_root.glob("*")) if artifact_root.exists() else []
    results.append(
        _pass(
            "preflight_generates_no_subtitle_files",
            len(after) == len(before),
            f"before={len(before)} after={len(after)}",
        )
    )

    # 11. No FFmpeg in subtitle modules
    preflight_path = root / "content_brain/execution/subtitle_preflight_runtime_slot.py"
    validator_path = root / "content_brain/execution/subtitle_artifact_validator.py"
    results.append(
        _pass(
            "no_ffmpeg_in_subtitle_modules",
            not _module_invokes_ffmpeg(preflight_path) and not _module_invokes_ffmpeg(validator_path),
        )
    )

    # 12–13. Voice/video unchanged by subtitle preflight
    baseline_session = _session_with_narration("exec_11i2_slot_preserve")
    video_before = dict(_dict(baseline_session["execution_runtime"]["category_runtime"].get(CATEGORY_VIDEO)))
    voice_before = dict(_dict(baseline_session["execution_runtime"]["category_runtime"].get(CATEGORY_VOICE)))
    updated_runtime = apply_subtitle_preflight_dry_run(baseline_session, baseline_session["execution_runtime"])
    video_after = dict(_dict(updated_runtime["category_runtime"].get(CATEGORY_VIDEO)))
    voice_after = dict(_dict(updated_runtime["category_runtime"].get(CATEGORY_VOICE)))
    results.append(_pass("voice_slot_unchanged", voice_after == voice_before))
    results.append(_pass("video_slot_unchanged", video_after == video_before))

    # Panel exposure
    panel_session = {
        **baseline_session,
        "execution_runtime": updated_runtime,
    }
    panel = PanelExtractor().extract_provider_runtime(panel_session)
    panel_keys = [
        item.get("category_key")
        for item in (panel.get("data", {}).get("category_runtime_slots") or [])
    ]
    results.append(
        _pass(
            "panel_exposes_subtitle_generation",
            CATEGORY_SUBTITLE_GENERATION in panel_keys,
            ",".join(str(k) for k in panel_keys),
        )
    )

    # 14–15. Regression validators
    results.append(_pass("validate_11g_regression", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))
    results.append(
        _pass("validate_11h2d_regression", _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"))
    )

    passed = sum(1 for item in results if item["pass"])
    failed = [item for item in results if not item["pass"]]
    return {
        "phase": "11I-2",
        "title": "Subtitle Runtime Foundation",
        "passed": passed,
        "failed": len(failed),
        "total": len(results),
        "all_pass": len(failed) == 0,
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
