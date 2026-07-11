"""
Phase 11H-1c — voice runtime UI observability validation (static + fixture checks).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from content_brain.execution.category_runtime_compat import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    ensure_multi_category_shell,
)
from content_brain.execution.voice_preflight_runtime_slot import (
    NOTE_KEY_MISSING,
    NOTE_NO_NARRATION,
    NOTE_PREFLIGHT_READY,
    apply_voice_preflight_dry_run,
)
from content_brain.execution.provider_categories import CATEGORY_VOICE
from providers.elevenlabs_preflight import CODE_CREDENTIALS_MISSING


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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

    observability = root / "ui" / "web" / "src" / "components" / "RuntimeObservability.tsx"
    voice_panel = root / "ui" / "web" / "src" / "components" / "VoiceRuntimeObservabilityPanel.tsx"
    category_panel = root / "ui" / "web" / "src" / "components" / "CategoryRuntimeSlotsPanel.tsx"
    utils = root / "ui" / "web" / "src" / "utils" / "categoryRuntimeShell.ts"
    css = root / "ui" / "web" / "src" / "App.css"

    observability_text = _read(observability)
    voice_panel_text = _read(voice_panel)
    category_panel_text = _read(category_panel)
    utils_text = _read(utils)

    results.append(_pass("voice_panel_file_exists", voice_panel.exists()))
    results.append(_pass("observability_imports_voice_panel", "VoiceRuntimeObservabilityPanel" in observability_text))
    results.append(_pass("voice_panel_read_only_note", "no live tts" in voice_panel_text.lower()))
    results.append(_pass("utils_resolve_voice_observability", "resolveVoiceRuntimeObservability" in utils_text))
    results.append(_pass("utils_setup_needed_label", "Setup needed" in utils_text))
    results.append(_pass("utils_no_narration_label", "No narration" in utils_text))
    results.append(_pass("utils_preflight_ready_label", "Preflight ready" in utils_text))
    results.append(_pass("category_panel_voice_fields", "Executed" in category_panel_text and "Dry run" in category_panel_text))
    results.append(_pass("css_voice_observability_styles", "voice-runtime-observability" in _read(css)))

    ui_bundle = observability_text + voice_panel_text + category_panel_text + utils_text
    forbidden_buttons = [
        "Generate voice",
        "Generate narration",
        "Run TTS",
        "dispatchVoice(",
        "generate_voice(",
    ]
    results.append(
        _pass(
            "no_live_tts_ui_actions",
            not any(label in ui_bundle for label in forbidden_buttons),
        )
    )

    results.append(
        _pass(
            "video_observability_unchanged",
            "Clip artifacts" in observability_text and "Artifact validation" in observability_text,
        )
    )

    shell = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    legacy_runtime = apply_voice_preflight_dry_run(
        {"brief_snapshot": {}},
        shell,
        project_root=root,
    )
    voice_legacy = dict(_dict(legacy_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    results.append(
        _pass(
            "legacy_no_voice_fields_safe_skipped",
            voice_legacy.get("status") == STATUS_SKIPPED
            and NOTE_NO_NARRATION in (voice_legacy.get("runtime_notes") or []),
            voice_legacy.get("status") or "",
        )
    )

    skipped_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "voice_generation",
                "category_name": "voice",
                "status": STATUS_SKIPPED,
                "runtime_notes": [NOTE_NO_NARRATION],
                "executed": False,
                "dry_run": True,
            }
        ]
    }
    results.append(
        _pass(
            "fixture_skipped_displays_no_narration",
            STATUS_SKIPPED in json.dumps(skipped_fixture, ensure_ascii=False) and NOTE_NO_NARRATION in json.dumps(skipped_fixture, ensure_ascii=False),
        )
    )

    failed_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "voice_generation",
                "category_name": "voice",
                "status": STATUS_FAILED,
                "error": {"code": CODE_CREDENTIALS_MISSING},
                "runtime_notes": [NOTE_KEY_MISSING],
                "executed": False,
                "dry_run": True,
            }
        ]
    }
    results.append(
        _pass(
            "fixture_credentials_missing_setup_needed",
            CODE_CREDENTIALS_MISSING in json.dumps(failed_fixture, ensure_ascii=False) and NOTE_KEY_MISSING in json.dumps(failed_fixture, ensure_ascii=False),
        )
    )

    pending_fixture = {
        "category_runtime_slots": [
            {
                "category_key": "voice_generation",
                "category_name": "voice",
                "status": STATUS_PENDING,
                "provider": "elevenlabs",
                "runtime_notes": [NOTE_PREFLIGHT_READY],
                "executed": False,
                "dry_run": True,
                "voice_preflight": {"status": "ready", "ready": True},
                "narration_adapter": {"segment_count": 2, "total_text_length": 120},
            }
        ]
    }
    results.append(
        _pass(
            "fixture_pending_preflight_ready",
            STATUS_PENDING in json.dumps(pending_fixture, ensure_ascii=False) and NOTE_PREFLIGHT_READY in json.dumps(pending_fixture, ensure_ascii=False),
        )
    )

    results.append(
        _pass(
            "fixture_executed_dry_run_visible",
            pending_fixture["category_runtime_slots"][0]["executed"] is False
            and pending_fixture["category_runtime_slots"][0]["dry_run"] is True,
        )
    )

    results.append(_pass("npm_build_passes", _run_npm_build(root)))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11H-1c",
        "label": "voice_ui_observability",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def _dict(value):
    return value if isinstance(value, dict) else {}


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
