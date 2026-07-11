"""
Phase 11J-2 — assembly runtime foundation validation.

Verifies category/alias support, slot schema, AssemblyPlan models, artifact
validator skeleton, and dry-run preflight metadata. No FFmpeg, no media
processing, no mutation of video/voice/subtitle slots.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from content_brain.execution.assembly_artifact_validator import AssemblyArtifactValidator
from content_brain.execution.assembly_models import (
    AssemblyInputArtifact,
    AssemblyManifestSkeleton,
    AssemblyPlan,
    AssemblyValidationResult,
    VALIDATION_FAILED,
    VALIDATION_PARTIAL,
    VALIDATION_READY,
)
from content_brain.execution.assembly_preflight_runtime_slot import (
    apply_assembly_preflight_dry_run,
)
from content_brain.execution.category_runtime_compat import (
    build_category_runtime_view,
    ensure_multi_category_shell,
    get_category_slot,
    normalize_category_runtime,
)
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY,
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)

EXECUTION_DIR = Path("content_brain/execution")
_ASSEMBLY_MODULES = (
    EXECUTION_DIR / "assembly_models.py",
    EXECUTION_DIR / "assembly_artifact_validator.py",
    EXECUTION_DIR / "assembly_preflight_runtime_slot.py",
)


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
    """Detect real ffmpeg imports or binary invocations (ignores prose/docstrings)."""
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
            if literal in {"ffmpeg", "ffmpeg.exe", "ffprobe"} or literal.startswith(("ffmpeg ", "ffmpeg.exe ")):
                return True
    return False


def _write(path: Path, content: str = "x") -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _build_runtime(
    tmp: Path,
    *,
    with_video: bool = True,
    with_voice: bool = True,
    with_subtitle: bool = True,
    video_manifest_ok: bool = True,
    voice_manifest_ok: bool = True,
    subtitle_manifest_ok: bool = True,
) -> dict:
    runtime = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    category_runtime = runtime["category_runtime"]
    artifacts = runtime["artifacts_by_category"]

    if with_video:
        clip = _write(tmp / "clip_001.mp4")
        artifacts[CATEGORY_VIDEO] = [{"file_path": clip}]
        manifest = tmp / "video_manifest.json"
        if video_manifest_ok:
            _write(manifest, "{}")
        category_runtime[CATEGORY_VIDEO]["video_manifest_path"] = str(manifest)

    if with_voice:
        narration = _write(tmp / "narration_001.mp3")
        artifacts[CATEGORY_VOICE] = [{"file_path": narration}]
        manifest = tmp / "voice_manifest.json"
        if voice_manifest_ok:
            _write(manifest, "{}")
        category_runtime[CATEGORY_VOICE]["voice_manifest_path"] = str(manifest)

    if with_subtitle:
        subs = _write(tmp / "subtitles.srt", "1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        artifacts[CATEGORY_SUBTITLE_GENERATION] = [{"file_path": subs}]
        artifacts["subtitles"] = [{"file_path": subs}]
        manifest = tmp / "subtitle_manifest.json"
        if subtitle_manifest_ok:
            _write(manifest, "{}")
        category_runtime[CATEGORY_SUBTITLE_GENERATION]["manifest_path"] = str(manifest)
        category_runtime["subtitles"]["manifest_path"] = str(manifest)

    return runtime


def run_matrix(project_root: str | Path = ".") -> dict:
    _ = project_root
    results: list[dict] = []

    # 1. New sessions expose assembly_generation.
    shell = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    view_keys = [item.get("category_key") for item in build_category_runtime_view(shell)]
    results.append(
        _pass(
            "new_session_exposes_assembly_generation",
            CATEGORY_ASSEMBLY_GENERATION in shell.get("category_runtime", {})
            and CATEGORY_ASSEMBLY_GENERATION in view_keys,
            ",".join(str(k) for k in view_keys),
        )
    )

    # 2. Legacy assembly alias maps safely to assembly_generation.
    legacy_runtime = {
        "category_runtime": {"assembly": {"status": "planned", "provider": "internal"}},
        "artifacts_by_category": {},
    }
    legacy_session = {"execution_runtime": legacy_runtime}
    legacy_slot = get_category_slot(legacy_session, CATEGORY_ASSEMBLY_GENERATION)
    normalized = normalize_category_runtime(legacy_runtime)
    legacy_view = [item.get("category_key") for item in build_category_runtime_view(legacy_runtime)]
    results.append(
        _pass(
            "legacy_assembly_alias_maps",
            legacy_slot.get("category_name") == CATEGORY_ASSEMBLY_GENERATION
            and CATEGORY_ASSEMBLY in normalized
            and CATEGORY_ASSEMBLY_GENERATION in legacy_view,
            legacy_slot.get("category_name"),
        )
    )

    # 3. No inputs → assembly slot skipped/partial safely.
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        empty_runtime = ensure_multi_category_shell(
            {"category_runtime": {}, "artifacts_by_category": {}}
        )
        updated_empty = apply_assembly_preflight_dry_run({}, empty_runtime)
        empty_slot = updated_empty["category_runtime"][CATEGORY_ASSEMBLY_GENERATION]
        results.append(
            _pass(
                "no_inputs_slot_safe",
                empty_slot.get("status") in {"skipped", "planned"}
                and empty_slot.get("validation_status") == VALIDATION_FAILED,
                f"{empty_slot.get('status')}/{empty_slot.get('validation_status')}",
            )
        )

        # 4. Video + voice + subtitle artifacts → validation READY.
        (tmp / "ready").mkdir(parents=True, exist_ok=True)
        ready_runtime = _build_runtime(tmp / "ready", with_video=True, with_voice=True, with_subtitle=True)
        updated_ready = apply_assembly_preflight_dry_run({}, ready_runtime)
        ready_slot = updated_ready["category_runtime"][CATEGORY_ASSEMBLY_GENERATION]
        results.append(
            _pass(
                "all_inputs_validation_ready",
                ready_slot.get("validation_status") == VALIDATION_READY
                and ready_slot.get("status") == "pending",
                f"{ready_slot.get('validation_status')}/{ready_slot.get('status')}",
            )
        )

        # 5. Missing one input group → validation PARTIAL.
        (tmp / "partial").mkdir(parents=True, exist_ok=True)
        partial_runtime = _build_runtime(
            tmp / "partial", with_video=True, with_voice=True, with_subtitle=False
        )
        updated_partial = apply_assembly_preflight_dry_run({}, partial_runtime)
        partial_slot = updated_partial["category_runtime"][CATEGORY_ASSEMBLY_GENERATION]
        results.append(
            _pass(
                "missing_one_group_partial",
                partial_slot.get("validation_status") == VALIDATION_PARTIAL,
                str(partial_slot.get("validation_status")),
            )
        )

        # 6. Missing manifests → PARTIAL / FAILED as designed.
        (tmp / "novmanifest").mkdir(parents=True, exist_ok=True)
        no_voice_manifest = _build_runtime(
            tmp / "novmanifest",
            with_video=True,
            with_voice=True,
            with_subtitle=True,
            voice_manifest_ok=False,
        )
        updated_nvm = apply_assembly_preflight_dry_run({}, no_voice_manifest)
        nvm_slot = updated_nvm["category_runtime"][CATEGORY_ASSEMBLY_GENERATION]

        (tmp / "novideomanifest").mkdir(parents=True, exist_ok=True)
        no_video_manifest = _build_runtime(
            tmp / "novideomanifest",
            with_video=True,
            with_voice=True,
            with_subtitle=True,
            video_manifest_ok=False,
        )
        updated_nvidm = apply_assembly_preflight_dry_run({}, no_video_manifest)
        nvidm_slot = updated_nvidm["category_runtime"][CATEGORY_ASSEMBLY_GENERATION]
        results.append(
            _pass(
                "missing_manifests_partial_or_failed",
                nvm_slot.get("validation_status") == VALIDATION_PARTIAL
                and nvidm_slot.get("validation_status") == VALIDATION_FAILED,
                f"voice_missing={nvm_slot.get('validation_status')},video_missing={nvidm_slot.get('validation_status')}",
            )
        )

        # 7–10. Preflight updates only assembly; upstream slots unchanged.
        (tmp / "isolation").mkdir(parents=True, exist_ok=True)
        iso_runtime = _build_runtime(
            tmp / "isolation", with_video=True, with_voice=True, with_subtitle=True
        )
        video_before = deepcopy(iso_runtime["category_runtime"][CATEGORY_VIDEO])
        voice_before = deepcopy(iso_runtime["category_runtime"][CATEGORY_VOICE])
        subtitle_before = deepcopy(iso_runtime["category_runtime"][CATEGORY_SUBTITLE_GENERATION])
        assembly_before = deepcopy(iso_runtime["category_runtime"][CATEGORY_ASSEMBLY_GENERATION])

        updated_iso = apply_assembly_preflight_dry_run({}, iso_runtime)
        iso_cr = updated_iso["category_runtime"]

        results.append(
            _pass(
                "preflight_updates_only_assembly",
                iso_cr[CATEGORY_ASSEMBLY_GENERATION] != assembly_before,
            )
        )
        results.append(_pass("video_slot_unchanged", iso_cr[CATEGORY_VIDEO] == video_before))
        results.append(_pass("voice_slot_unchanged", iso_cr[CATEGORY_VOICE] == voice_before))
        results.append(
            _pass(
                "subtitle_slot_unchanged",
                iso_cr[CATEGORY_SUBTITLE_GENERATION] == subtitle_before,
            )
        )

    # 11. No FFmpeg import/call.
    ffmpeg_clean = not any(
        _module_invokes_ffmpeg(path) or _module_imports_forbidden(path, "ffmpeg")
        for path in _ASSEMBLY_MODULES
    )
    results.append(_pass("no_ffmpeg_import_or_call", ffmpeg_clean))

    # 12. No full_video_pipeline import.
    pipeline_clean = not any(
        _module_imports_forbidden(path, "full_video_pipeline") for path in _ASSEMBLY_MODULES
    )
    results.append(_pass("no_full_video_pipeline_import", pipeline_clean))

    # Sanity: model + validator behave as designed.
    validator = AssemblyArtifactValidator()
    empty_result = validator.validate()
    plan = AssemblyPlan(
        session_id="exec_11j2",
        video_inputs=[AssemblyInputArtifact(category=CATEGORY_VIDEO, file_path="clip.mp4", role="clip")],
    )
    manifest = AssemblyManifestSkeleton(session_id="exec_11j2")
    results.append(
        _pass(
            "models_serialize",
            isinstance(empty_result, AssemblyValidationResult)
            and empty_result.status == VALIDATION_FAILED
            and plan.to_dict()["session_id"] == "exec_11j2"
            and manifest.to_dict()["category"] == CATEGORY_ASSEMBLY_GENERATION,
        )
    )

    # 13–15. Regression validators.
    results.append(
        _pass(
            "validate_11g_regression",
            _run_module("project_brain.validate_11g_multi_category_runtime_shell"),
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
        "phase": "11J-2",
        "label": "assembly_runtime_foundation",
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
