"""
Phase 11I-4 — subtitle cue generation engine validation.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.subtitle_cue_generation_engine import (
    SubtitleCueGenerationEngine,
    SubtitleCueGenerationRequest,
)
from content_brain.execution.subtitle_cue_validator import SubtitleCueValidator
from content_brain.execution.subtitle_highlight_terms import (
    NEUTRAL_FALLBACK_TERMS,
    contains_skincare_marker,
    resolve_session_highlight_terms,
)
from content_brain.execution.subtitle_models import SubtitleCue, SubtitleCueBatch, SubtitleTimingStrategy


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
        {"beat_id": "HOOK", "narration": "Watch this hidden detail before the replay angle changes everything."},
    ]
    return {
        "execution_session_id": session_id,
        "topic": "football VAR controversy",
        "brief_snapshot": {
            "topic": "football VAR controversy",
            "content_format": {"default_duration_seconds": 24},
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {"beat_plans": beat_plans},
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
    engine = SubtitleCueGenerationEngine(root)
    results: list[dict] = []

    text_session = _session_narration_only("exec_11i4_text")
    text_result = engine.generate(SubtitleCueGenerationRequest(session=text_session))
    batch = text_result.batch
    results.append(
        _pass(
            "generates_cues_from_narration_text",
            text_result.passed and batch is not None and batch.cue_count >= 1,
            str(batch.cue_count if batch else 0),
        )
    )

    ordered = batch is not None and all(
        batch.cues[i].start_time <= batch.cues[i + 1].start_time for i in range(len(batch.cues) - 1)
    )
    results.append(_pass("generates_ordered_timestamps", bool(batch) and ordered))

    non_empty = batch is not None and all(cue.text.strip() for cue in batch.cues)
    results.append(_pass("cue_text_non_empty", bool(batch) and non_empty))

    long_text = (
        "This is a long narration segment designed to test subtitle splitting behavior. "
        "It should produce multiple readable cues when the max line length is enforced. "
        "The engine must preserve sentence boundaries whenever possible during wrapping."
    )
    long_session = _session_narration_only(
        "exec_11i4_long",
        beats=[{"beat_id": "HOOK", "narration": long_text}],
    )
    long_result = engine.generate(SubtitleCueGenerationRequest(session=long_session))
    results.append(
        _pass(
            "long_narration_splits_multiple_cues",
            long_result.passed
            and long_result.batch is not None
            and long_result.batch.cue_count >= 2,
            str(long_result.batch.cue_count if long_result.batch else 0),
        )
    )

    equal_result = engine.generate(
        SubtitleCueGenerationRequest(
            session=text_session,
            timing_strategy=SubtitleTimingStrategy.EQUAL_CHUNK.value,
        )
    )
    results.append(
        _pass(
            "uses_equal_chunk_without_audio_duration",
            equal_result.passed
            and equal_result.batch is not None
            and equal_result.batch.timing_strategy == SubtitleTimingStrategy.EQUAL_CHUNK.value,
            str(equal_result.batch.timing_strategy if equal_result.batch else ""),
        )
    )

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
                indent=2,
            ),
            encoding="utf-8",
        )
        timing_session = _session_with_manifest(
            "exec_11i4_audio",
            manifest_path,
            beats=[
                {"beat_id": "HOOK", "narration": "First segment about the replay angle."},
                {"beat_id": "PAYOFF", "narration": "Second segment explains the final decision."},
            ],
        )
        audio_result = engine.generate(SubtitleCueGenerationRequest(session=timing_session))
        results.append(
            _pass(
                "uses_audio_duration_with_voice_manifest",
                audio_result.passed
                and audio_result.batch is not None
                and audio_result.batch.timing_strategy == SubtitleTimingStrategy.AUDIO_DURATION.value,
                str(audio_result.batch.timing_strategy if audio_result.batch else ""),
            )
        )

    default_terms, sources = resolve_session_highlight_terms(
        text_session,
        profile=None,
        narration_texts=["Watch this hidden detail before the replay angle changes everything."],
    )
    results.append(
        _pass(
            "highlight_terms_no_skincare_by_default",
            not contains_skincare_marker(default_terms),
            ",".join(default_terms[:8]),
        )
    )
    results.append(
        _pass(
            "highlight_terms_use_neutral_or_derived_sources",
            not contains_skincare_marker(default_terms)
            and (
                "neutral_fallback" in sources
                or "narration_derived" in sources
                or "brief_topic" in sources
            ),
            ",".join(sources),
        )
    )

    profile_session = _session_narration_only("exec_11i4_profile")
    profile = {"highlight_keywords": ["VAR", "replay", "referee"]}
    profile_result = engine.generate(
        SubtitleCueGenerationRequest(session=profile_session, profile=profile)
    )
    profile_terms, _sources = resolve_session_highlight_terms(profile_session, profile=profile)
    cue_highlights = (
        profile_result.batch.cues[0].highlight_terms if profile_result.batch and profile_result.batch.cues else []
    )
    results.append(
        _pass(
            "custom_profile_highlight_keywords_used",
            "var" in profile_terms or "replay" in profile_terms,
            ",".join(profile_terms),
        )
    )
    results.append(
        _pass(
            "profile_keywords_applied_to_cues",
            any(term in {"var", "replay", "referee"} for term in cue_highlights),
            ",".join(cue_highlights),
        )
    )

    bad_batch = SubtitleCueBatch(
        cues=[
            SubtitleCue(index=1, start_time=-1.0, end_time=2.0, text="Bad timing"),
        ],
        language="en",
        source_type="narration_text_only",
        timing_strategy="equal_chunk",
        total_duration=2.0,
    )
    bad_validation = SubtitleCueValidator().validate(bad_batch)
    results.append(
        _pass(
            "validator_catches_negative_timestamps",
            not bad_validation.passed,
            str(bad_validation.reject_code),
        )
    )

    empty_batch = SubtitleCueBatch(
        cues=[SubtitleCue(index=1, start_time=0.0, end_time=1.0, text="   ")],
        language="en",
        source_type="narration_text_only",
        timing_strategy="equal_chunk",
        total_duration=1.0,
    )
    empty_validation = SubtitleCueValidator().validate(empty_batch)
    results.append(
        _pass(
            "validator_catches_empty_cue_text",
            not empty_validation.passed,
            str(empty_validation.reject_reasons),
        )
    )

    artifact_dir = root / "storage/content_brain/execution/artifacts/exec_11i4_no_files/subtitle_generation"
    before = list(artifact_dir.glob("*")) if artifact_dir.exists() else []
    engine.generate(SubtitleCueGenerationRequest(session=text_session))
    after = list(artifact_dir.glob("*")) if artifact_dir.exists() else []
    results.append(
        _pass(
            "no_subtitle_files_written",
            len(before) == len(after),
            f"before={len(before)} after={len(after)}",
        )
    )

    module_paths = [
        root / "content_brain/execution/subtitle_cue_generation_engine.py",
        root / "content_brain/execution/subtitle_cue_validator.py",
        root / "content_brain/execution/subtitle_highlight_terms.py",
        root / "content_brain/execution/subtitle_text_normalizer.py",
        root / "content_brain/execution/subtitle_models.py",
    ]
    results.append(
        _pass(
            "no_ffmpeg_in_subtitle_cue_modules",
            all(not _module_invokes_ffmpeg(path) for path in module_paths),
        )
    )
    results.append(
        _pass(
            "no_legacy_subtitle_engine_import",
            all(
                not _module_imports_forbidden(path, "engines.subtitle_engine")
                and not _module_imports_forbidden(path, "subtitle_engine")
                for path in module_paths
            ),
        )
    )

    preserve_session = _session_narration_only("exec_11i4_preserve")
    video_before = dict(_dict(preserve_session["execution_runtime"]["category_runtime"].get(CATEGORY_VIDEO)))
    voice_before = dict(_dict(preserve_session["execution_runtime"]["category_runtime"].get(CATEGORY_VOICE)))
    engine.generate(SubtitleCueGenerationRequest(session=preserve_session))
    video_after = dict(_dict(preserve_session["execution_runtime"]["category_runtime"].get(CATEGORY_VIDEO)))
    voice_after = dict(_dict(preserve_session["execution_runtime"]["category_runtime"].get(CATEGORY_VOICE)))
    results.append(_pass("voice_slot_unchanged", voice_after == voice_before))
    results.append(_pass("video_slot_unchanged", video_after == video_before))

    results.append(
        _pass("validate_11i2_regression", _run_module("project_brain.validate_11i2_subtitle_runtime_foundation"))
    )
    results.append(
        _pass("validate_11i2b_regression", _run_module("project_brain.validate_11i2b_hardcoded_niche_fixes"))
    )
    results.append(
        _pass("validate_11h2d_regression", _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"))
    )

    passed = sum(1 for item in results if item["pass"])
    failed = [item for item in results if not item["pass"]]
    return {
        "phase": "11I-4",
        "title": "Subtitle Cue Generation Engine V1",
        "passed": passed,
        "failed": len(failed),
        "total": len(results),
        "all_pass": len(failed) == 0,
        "neutral_fallback_terms": list(NEUTRAL_FALLBACK_TERMS),
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
