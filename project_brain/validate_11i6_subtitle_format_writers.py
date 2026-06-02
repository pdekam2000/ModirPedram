"""
Phase 11I-6 — subtitle format writers validation.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from content_brain.execution.category_runtime_compat import (
    SUBTITLE_ARTIFACT_CATEGORY,
    ensure_multi_category_shell,
)
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.subtitle_artifact_validator import (
    SubtitleArtifactValidator,
    _SRT_TIMESTAMP,
)
from content_brain.execution.subtitle_cue_generation_engine import (
    SubtitleCueGenerationEngine,
    SubtitleCueGenerationRequest,
)
from content_brain.execution.subtitle_format_writer import (
    DEFAULT_FILENAMES,
    MANIFEST_FILENAME,
    SubtitleFormatWriter,
    SubtitleWriteRequest,
    SUPPORTED_FORMATS,
)


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


def _session(session_id: str) -> dict:
    return {
        "execution_session_id": session_id,
        "topic": "football VAR controversy",
        "brief_snapshot": {
            "topic": "football VAR controversy",
            "content_format": {"default_duration_seconds": 24},
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {
                                "beat_id": "HOOK",
                                "narration": "Watch this hidden replay angle before the final decision.",
                            }
                        ]
                    }
                }
            },
        },
        "execution_runtime": ensure_multi_category_shell(
            {"category_runtime": {}, "artifacts_by_category": {}}
        ),
    }


def _batch_for_session(store: ExecutionSessionStore, session_id: str):
    session = _session(session_id)
    result = SubtitleCueGenerationEngine(store.project_root).generate(
        SubtitleCueGenerationRequest(session=session)
    )
    if not result.passed or result.batch is None:
        raise RuntimeError(f"Cue generation failed: {result.reject_reasons}")
    return session, result.batch


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    store = ExecutionSessionStore(root)
    writer = SubtitleFormatWriter(store)
    results: list[dict] = []

    session_id = "exec_11i6_format_writers"
    session, batch = _batch_for_session(store, session_id)
    write_result = writer.write(
        SubtitleWriteRequest(batch=batch, session_id=session_id, overwrite=True)
    )
    artifact_dir = store.artifact_dir(session_id, SUBTITLE_ARTIFACT_CATEGORY)

    srt_path = artifact_dir / DEFAULT_FILENAMES["srt"]
    vtt_path = artifact_dir / DEFAULT_FILENAMES["vtt"]
    ass_path = artifact_dir / DEFAULT_FILENAMES["ass"]
    manifest_path = artifact_dir / MANIFEST_FILENAME

    results.append(_pass("writes_srt_file", write_result.passed and srt_path.is_file(), str(srt_path)))
    srt_text = srt_path.read_text(encoding="utf-8") if srt_path.is_file() else ""
    results.append(
        _pass(
            "srt_timestamp_format_correct",
            bool(_SRT_TIMESTAMP.search(srt_text)),
        )
    )
    results.append(_pass("writes_vtt_file", vtt_path.is_file(), str(vtt_path)))
    vtt_text = vtt_path.read_text(encoding="utf-8") if vtt_path.is_file() else ""
    results.append(
        _pass(
            "vtt_has_webvtt_header",
            vtt_text.lstrip().upper().startswith("WEBVTT"),
        )
    )
    results.append(_pass("writes_ass_file", ass_path.is_file(), str(ass_path)))
    ass_text = ass_path.read_text(encoding="utf-8") if ass_path.is_file() else ""
    results.append(
        _pass(
            "ass_has_dialogue_lines",
            len(re.findall(r"^Dialogue:\s*\d", ass_text, re.MULTILINE | re.IGNORECASE)) >= batch.cue_count,
            str(len(re.findall(r"^Dialogue:\s*\d", ass_text, re.MULTILINE | re.IGNORECASE))),
        )
    )
    results.append(
        _pass(
            "writes_subtitle_manifest",
            write_result.passed and manifest_path.is_file(),
            str(manifest_path),
        )
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    results.append(
        _pass(
            "manifest_cue_count_matches_batch",
            manifest.get("cue_count") == batch.cue_count,
            f"manifest={manifest.get('cue_count')} batch={batch.cue_count}",
        )
    )

    bad_session_id = "exec_11i6_unsupported"
    _, bad_batch = _batch_for_session(store, bad_session_id)
    bad_result = writer.write(
        SubtitleWriteRequest(batch=bad_batch, session_id=bad_session_id, formats=["txt"])
    )
    results.append(
        _pass(
            "unsupported_format_fails_safely",
            not bad_result.passed and bad_result.reject_code == "UNSUPPORTED_FORMAT",
            str(bad_result.reject_code),
        )
    )

    block_session_id = "exec_11i6_overwrite_block"
    block_dir = store.artifact_dir(block_session_id, SUBTITLE_ARTIFACT_CATEGORY)
    if block_dir.exists():
        shutil.rmtree(block_dir)
    _, block_batch = _batch_for_session(store, block_session_id)
    first = writer.write(SubtitleWriteRequest(batch=block_batch, session_id=block_session_id, overwrite=False))
    second = writer.write(SubtitleWriteRequest(batch=block_batch, session_id=block_session_id, overwrite=False))
    results.append(
        _pass(
            "overwrite_false_blocks_existing",
            first.passed and not second.passed and second.reject_code == "FILE_EXISTS",
            str(second.reject_code),
        )
    )

    rewrite_session_id = "exec_11i6_overwrite_allow"
    rewrite_dir = store.artifact_dir(rewrite_session_id, SUBTITLE_ARTIFACT_CATEGORY)
    if rewrite_dir.exists():
        shutil.rmtree(rewrite_dir)
    _, rewrite_batch = _batch_for_session(store, rewrite_session_id)
    rewrite_first = writer.write(SubtitleWriteRequest(batch=rewrite_batch, session_id=rewrite_session_id, overwrite=False))
    rewrite_second = writer.write(
        SubtitleWriteRequest(batch=rewrite_batch, session_id=rewrite_session_id, overwrite=True)
    )
    results.append(
        _pass(
            "overwrite_true_allows_rewrite",
            rewrite_first.passed and rewrite_second.passed,
        )
    )

    artifact_payloads = [
        {
            "format": record.format,
            "file_name": record.file_name,
            "file_path": record.file_path,
        }
        for record in write_result.files
    ]
    artifact_validation = SubtitleArtifactValidator().validate(artifact_payloads)
    results.append(_pass("post_write_artifact_validator_passes", artifact_validation.passed))

    writer_path = root / "content_brain/execution/subtitle_format_writer.py"
    results.append(_pass("no_ffmpeg_import", not _module_invokes_ffmpeg(writer_path)))
    results.append(
        _pass(
            "no_legacy_subtitle_engine_import",
            not _module_imports_forbidden(writer_path, "subtitle_engine"),
        )
    )

    preserve_session_id = "exec_11i6_preserve_slots"
    preserve_dir = store.artifact_dir(preserve_session_id, SUBTITLE_ARTIFACT_CATEGORY)
    if preserve_dir.exists():
        shutil.rmtree(preserve_dir)
    preserve_session, preserve_batch = _batch_for_session(store, preserve_session_id)
    video_before = deepcopy(preserve_session["execution_runtime"]["category_runtime"][CATEGORY_VIDEO])
    voice_before = deepcopy(preserve_session["execution_runtime"]["category_runtime"][CATEGORY_VOICE])
    writer.write(
        SubtitleWriteRequest(batch=preserve_batch, session_id=preserve_session_id, overwrite=True)
    )
    video_after = deepcopy(preserve_session["execution_runtime"]["category_runtime"][CATEGORY_VIDEO])
    voice_after = deepcopy(preserve_session["execution_runtime"]["category_runtime"][CATEGORY_VOICE])
    results.append(_pass("voice_slot_unchanged", voice_after == voice_before))
    results.append(_pass("video_slot_unchanged", video_after == video_before))

    results.append(_pass("validate_11i4_regression", _run_module("project_brain.validate_11i4_subtitle_cue_generation_engine")))
    results.append(_pass("validate_11i2_regression", _run_module("project_brain.validate_11i2_subtitle_runtime_foundation")))
    results.append(
        _pass("validate_11h2d_regression", _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"))
    )

    passed = sum(1 for item in results if item["pass"])
    failed = [item for item in results if not item["pass"]]
    return {
        "phase": "11I-6",
        "title": "Subtitle Format Writers",
        "passed": passed,
        "failed": len(failed),
        "total": len(results),
        "all_pass": len(failed) == 0,
        "supported_formats": sorted(SUPPORTED_FORMATS),
        "example_artifact_dir": str(artifact_dir.resolve()),
        "results": results,
        "failures": failed,
    }


def main() -> int:
    report = run_matrix(".")
    print(json.dumps(report, indent=2))
    for item in report["results"]:
        status = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{status}] {item['test']}{detail}")
    print(f"\nSummary: {report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
