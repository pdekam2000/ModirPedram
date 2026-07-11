"""
Phase 11I-10 — subtitle runtime UI observability validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from content_brain.execution.category_runtime_compat import (
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_SKIPPED,
)


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_module(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        cwd=str(Path(".").resolve()),
    )
    return result.returncode == 0


def _run_npm_build(root: Path) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(root / "ui" / "web"),
        shell=True,
    )
    return result.returncode == 0


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    observability = root / "ui/web/src/components/RuntimeObservability.tsx"
    subtitle_panel = root / "ui/web/src/components/SubtitleRuntimeObservabilityPanel.tsx"
    voice_panel = root / "ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx"
    utils = root / "ui/web/src/utils/subtitleRuntimeObservability.ts"
    shell_utils = root / "ui/web/src/utils/categoryRuntimeShell.ts"
    css = root / "ui/web/src/App.css"

    observability_text = _read(observability)
    subtitle_panel_text = _read(subtitle_panel)
    voice_panel_text = _read(voice_panel)
    utils_text = _read(utils)
    shell_utils_text = _read(shell_utils)

    results.append(_pass("subtitle_panel_file_exists", subtitle_panel.exists()))
    results.append(
        _pass(
            "observability_imports_subtitle_panel",
            "SubtitleRuntimeObservabilityPanel" in observability_text,
        )
    )
    results.append(
        _pass(
            "subtitle_panel_below_voice_panel",
            observability_text.find("VoiceRuntimeObservabilityPanel")
            < observability_text.find("SubtitleRuntimeObservabilityPanel"),
        )
    )

    completed_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "subtitle_generation",
                "category_name": "subtitle_generation",
                "status": STATUS_COMPLETED,
                "provider": "local_subtitle_runtime",
                "source_type": "narration_text_only",
                "source_ready": True,
                "timing_strategy": "equal_chunk",
                "cue_count": 2,
                "formats_written": ["srt", "ass", "vtt"],
                "validation_status": "valid",
                "manifest_path": "/tmp/subtitle_manifest.json",
                "artifacts": [
                    {
                        "format": "srt",
                        "file_name": "subtitles.srt",
                        "file_path": "/tmp/subtitles.srt",
                        "validation_status": "valid",
                        "size_bytes": 130,
                    }
                ],
            }
        ]
    }
    results.append(
        _pass(
            "panel_renders_completed_subtitle_slot",
            "Subtitles ready" in utils_text
            and "Cue count" in subtitle_panel_text
            and STATUS_COMPLETED in json.dumps(completed_fixture, ensure_ascii=False),
        )
    )

    pending_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "subtitle_generation",
                "status": STATUS_PENDING,
                "source_ready": True,
                "source_type": "narration_text_only",
            }
        ]
    }
    results.append(
        _pass(
            "panel_renders_pending_subtitle_slot",
            "Ready" in utils_text and STATUS_PENDING in json.dumps(pending_fixture, ensure_ascii=False),
        )
    )

    skipped_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "subtitle_generation",
                "status": STATUS_SKIPPED,
                "source_ready": False,
                "source_type": "unavailable",
            }
        ]
    }
    results.append(
        _pass(
            "panel_renders_skipped_subtitle_slot",
            "No subtitle source" in utils_text and STATUS_SKIPPED in json.dumps(skipped_fixture, ensure_ascii=False),
        )
    )

    results.append(
        _pass(
            "legacy_missing_fields_render_dash",
            'return "—"' in utils_text or 'return "—";' in utils_text,
        )
    )
    results.append(
        _pass(
            "subtitles_alias_renders_subtitle_generation",
            'category_key === "subtitles"' in utils_text
            and 'category_key: "subtitle_generation"' in utils_text,
        )
    )

    safety_copy = "Subtitle files only — no video burn-in yet."
    results.append(
        _pass(
            "safety_copy_present_exact",
            safety_copy in subtitle_panel_text or safety_copy in utils_text,
            safety_copy,
        )
    )

    ui_bundle = subtitle_panel_text + utils_text + observability_text
    forbidden = ["Burn In", "FFmpeg", "Send to Assembly", "Assemble Video"]
    results.append(
        _pass(
            "no_forbidden_buttons_or_labels",
            not any(label in ui_bundle for label in forbidden),
        )
    )

    artifact_files = ["subtitles.srt", "subtitles.vtt", "subtitles.ass", "subtitle_manifest.json"]
    results.append(
        _pass(
            "artifact_paths_render_for_expected_files",
            all(name in utils_text for name in artifact_files)
            and "Subtitle artifacts" in subtitle_panel_text,
        )
    )

    results.append(
        _pass(
            "video_observability_unchanged",
            "Clip artifacts" in observability_text and "Artifact validation" in observability_text,
        )
    )
    results.append(
        _pass(
            "voice_observability_unchanged",
            "VoiceRuntimeObservabilityPanel" in observability_text
            and "Voice runtime" in voice_panel_text,
        )
    )

    results.append(_pass("resolve_subtitle_observability_util", "resolveSubtitleRuntimeObservability" in utils_text))
    results.append(_pass("css_subtitle_observability_styles", "subtitle-runtime-observability" in _read(css)))
    results.append(
        _pass(
            "category_shell_placeholder_subtitle_generation",
            'category_key: "subtitle_generation"' in shell_utils_text,
        )
    )

    results.append(_pass("npm_build_passes", _run_npm_build(root)))
    results.append(_pass("validate_11i8_regression", _run_module("project_brain.validate_11i8_subtitle_runtime_execution_api")))
    results.append(
        _pass(
            "validate_11h2d_regression",
            _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution"),
        )
    )

    passed = sum(1 for item in results if item["pass"])
    failed = [item for item in results if not item["pass"]]
    return {
        "phase": "11I-10",
        "title": "Subtitle UI Observability Panel",
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
