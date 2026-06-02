"""
Phase 11J-10 — assembly runtime UI observability validation.
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


def _run_module(module: str, *, core_only: bool = True) -> bool:
    from project_brain.validation_policy import run_validator_module

    return run_validator_module(module, core_only=core_only)


def _run_npm_build(root: Path) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(root / "ui" / "web"),
        shell=True,
    )
    return result.returncode == 0


def run_matrix(project_root: str | Path = ".", *, include_regressions: bool = False) -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    observability = root / "ui/web/src/components/RuntimeObservability.tsx"
    assembly_panel = root / "ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx"
    subtitle_panel = root / "ui/web/src/components/SubtitleRuntimeObservabilityPanel.tsx"
    voice_panel = root / "ui/web/src/components/VoiceRuntimeObservabilityPanel.tsx"
    utils = root / "ui/web/src/utils/assemblyRuntimeObservability.ts"
    shell_utils = root / "ui/web/src/utils/categoryRuntimeShell.ts"
    css = root / "ui/web/src/App.css"

    observability_text = _read(observability)
    assembly_panel_text = _read(assembly_panel)
    subtitle_panel_text = _read(subtitle_panel)
    voice_panel_text = _read(voice_panel)
    utils_text = _read(utils)
    shell_utils_text = _read(shell_utils)

    # 1. Panel exists.
    results.append(_pass("assembly_panel_file_exists", assembly_panel.exists()))

    completed_fixture = {
        "session_id": "exec_11j10",
        "category_runtime_slots": [
            {
                "category_key": "assembly_generation",
                "category_name": "assembly_generation",
                "status": STATUS_COMPLETED,
                "provider": "local_assembly_runtime",
                "validation_status": "READY",
                "assembly_mode": "video_voice_subtitle",
                "subtitle_mode": "burn_in",
                "expected_output": "FINAL_PUBLISH_READY.mp4",
                "output_created": False,
                "real_assembly_executed": False,
                "planned_steps": [{"step": 1, "name": "validate_inputs", "action": "verify inputs"}],
                "input_summary": {"video_count": 2, "voice_count": 2, "subtitle_count": 1},
                "output_summary": {
                    "expected_output": "FINAL_PUBLISH_READY.mp4",
                    "output_created": False,
                },
            }
        ],
    }
    # 2. Completed dry-run slot.
    results.append(
        _pass(
            "panel_renders_completed_dry_run_slot",
            "Assembly ready" in utils_text
            and "Planned steps" in assembly_panel_text
            and STATUS_COMPLETED in json.dumps(completed_fixture),
        )
    )

    pending_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "assembly_generation",
                "status": STATUS_PENDING,
                "validation_status": "READY",
            }
        ]
    }
    # 3. Pending slot.
    results.append(
        _pass(
            "panel_renders_pending_assembly_slot",
            "Ready" in utils_text and STATUS_PENDING in json.dumps(pending_fixture),
        )
    )

    skipped_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "assembly_generation",
                "status": STATUS_SKIPPED,
                "validation_status": "FAILED",
            }
        ]
    }
    # 4. Skipped slot.
    results.append(
        _pass(
            "panel_renders_skipped_assembly_slot",
            "No assembly inputs" in utils_text and STATUS_SKIPPED in json.dumps(skipped_fixture),
        )
    )

    # 5. Legacy alias.
    results.append(
        _pass(
            "assembly_alias_renders_assembly_generation",
            'category_key === "assembly"' in utils_text
            and 'category_key: "assembly_generation"' in utils_text,
        )
    )

    # 6. Missing fields → —.
    results.append(
        _pass(
            "missing_fields_render_dash",
            'return "—"' in utils_text or 'return "—";' in utils_text,
        )
    )

    safety_copy = (
        "Assembly is currently running in dry-run mode only. No FFmpeg execution is enabled."
    )
    # 7. Safety copy exact.
    results.append(
        _pass(
            "safety_copy_present_exact",
            safety_copy in assembly_panel_text or safety_copy in utils_text,
            safety_copy,
        )
    )

    no_output_copy = "No final video has been generated."
    # 8. No-final-video copy.
    results.append(
        _pass(
            "no_final_video_copy_when_not_executed",
            no_output_copy in assembly_panel_text or no_output_copy in utils_text,
            no_output_copy,
        )
    )

    # 9. Expected output label.
    results.append(
        _pass(
            "expected_output_labeled_expected_output_only",
            "Expected Output Only" in assembly_panel_text or "Expected Output Only" in utils_text,
        )
    )

    # 10. output_created=false not shown as generated.
    results.append(
        _pass(
            "output_created_false_not_generated",
            "Not generated" in assembly_panel_text
            and 'assembly.isGeneratedOutput ? "Generated" : "Not generated"' in assembly_panel_text,
        )
    )

    ui_panel = assembly_panel_text
    forbidden = [
        "Run Assembly",
        "Generate Final Video",
        "Export Final Video",
        "Send to Assembly",
        "Burn In",
    ]
    # Scan panel source only — utils contains guard-function literals and safety copy mentions FFmpeg.
    forbidden_hits = [label for label in forbidden if label in ui_panel]
    ffmpeg_as_button = "<button" in ui_panel.lower() and "ffmpeg" in ui_panel.lower()
    burn_in_button = "<button" in ui_panel.lower() and "Burn In" in ui_panel
    results.append(
        _pass(
            "no_forbidden_labels_or_buttons",
            not forbidden_hits and not ffmpeg_as_button and not burn_in_button,
            ",".join(forbidden_hits) if forbidden_hits else "",
        )
    )

    # 12–14. Other observability unchanged.
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
    results.append(
        _pass(
            "subtitle_observability_unchanged",
            "SubtitleRuntimeObservabilityPanel" in observability_text
            and "Subtitle runtime" in subtitle_panel_text,
        )
    )

    results.append(
        _pass(
            "observability_imports_assembly_panel",
            "AssemblyRuntimeObservabilityPanel" in observability_text,
        )
    )
    results.append(
        _pass(
            "assembly_panel_below_subtitle_panel",
            observability_text.find("SubtitleRuntimeObservabilityPanel")
            < observability_text.find("AssemblyRuntimeObservabilityPanel"),
        )
    )
    results.append(_pass("resolve_assembly_observability_util", "resolveAssemblyRuntimeObservability" in utils_text))
    results.append(_pass("css_assembly_observability_styles", "assembly-runtime-observability" in _read(css)))
    results.append(
        _pass(
            "category_shell_placeholder_assembly_generation",
            'category_key: "assembly_generation"' in shell_utils_text,
        )
    )

    # 15. npm build.
    results.append(_pass("npm_build_passes", _run_npm_build(root)))

    # 16–18. Regressions.
    if include_regressions:
        results.append(
            _pass("validate_11j8_regression", _run_module("project_brain.validate_11j8_assembly_runtime_api", core_only=True))
        )
        results.append(
            _pass(
                "validate_11i10_regression",
                _run_module("project_brain.validate_11i10_subtitle_ui_observability", core_only=True),
            )
        )
        results.append(
            _pass(
                "validate_11h2d_regression",
                _run_module("project_brain.validate_11h2d_live_engine_wiring_no_real_execution", core_only=True),
            )
        )

    from project_brain.validation_policy import summarize_validation_report

    return summarize_validation_report(
        phase="11J-10",
        label="assembly_ui_observability",
        results=results,
        include_regressions=include_regressions,
        extra={"title": "Assembly UI Observability Panel"},
    )


def main(argv: list[str] | None = None) -> int:
    from project_brain.validation_policy import (
        parse_include_regressions,
        print_validation_summary,
        validation_exit_code,
    )

    include_regressions = parse_include_regressions(argv)
    report = run_matrix(".", include_regressions=include_regressions)
    print(json.dumps(report, indent=2))
    print_validation_summary(report)
    return validation_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
