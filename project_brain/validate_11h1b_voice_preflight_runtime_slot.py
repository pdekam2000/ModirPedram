"""
Phase 11H-1b — voice preflight runtime slot validation (no live TTS).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.category_runtime_compat import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    build_category_runtime_view,
    ensure_multi_category_shell,
    get_category_slot,
)
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.voice_preflight_runtime_slot import (
    NOTE_KEY_MISSING,
    NOTE_NO_NARRATION,
    NOTE_PREFLIGHT_READY,
    apply_voice_preflight_dry_run,
)
from providers.elevenlabs_preflight import CODE_CREDENTIALS_MISSING
from ui.api.services.panel_extractor import PanelExtractor


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


def _session_no_narration() -> dict:
    return {
        "execution_session_id": "exec_11h1b_no_narration",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "schema_director_shots": [{"clip_number": 1, "prompt": "visual only"}]
                }
            }
        },
    }


def _session_with_narration() -> dict:
    return {
        "execution_session_id": "exec_11h1b_with_narration",
        "provider_selection": {
            "category_selections": {"voice_generation": {"provider": "elevenlabs"}},
        },
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {"beat_id": "HOOK", "narration": "Narration line for preflight test."}
                        ]
                    }
                }
            }
        },
    }


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    runtime_shell = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})

    skipped_runtime = apply_voice_preflight_dry_run(_session_no_narration(), runtime_shell, project_root=root)
    voice_skipped = dict(_dict(skipped_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    results.append(
        _pass(
            "no_narration_voice_skipped",
            voice_skipped.get("status") == STATUS_SKIPPED
            and NOTE_NO_NARRATION in (voice_skipped.get("runtime_notes") or []),
            voice_skipped.get("status") or "",
        )
    )

    env_without_key = {k: v for k, v in os.environ.items() if k != "ELEVENLABS_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        missing_runtime = apply_voice_preflight_dry_run(
            _session_with_narration(),
            ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}}),
            project_root=root,
        )
    voice_missing = dict(_dict(missing_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    error = _dict(voice_missing.get("error"))
    results.append(
        _pass(
            "narration_missing_key_credentials_missing",
            voice_missing.get("status") == STATUS_FAILED
            and error.get("code") == CODE_CREDENTIALS_MISSING
            and NOTE_KEY_MISSING in (voice_missing.get("runtime_notes") or []),
            error.get("code") or "",
        )
    )

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        ready_runtime = apply_voice_preflight_dry_run(
            _session_with_narration(),
            ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}}),
            project_root=root,
        )
    voice_ready = dict(_dict(ready_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    results.append(
        _pass(
            "narration_key_present_voice_pending",
            voice_ready.get("status") == STATUS_PENDING
            and voice_ready.get("provider") == "elevenlabs"
            and NOTE_PREFLIGHT_READY in (voice_ready.get("runtime_notes") or []),
            voice_ready.get("status") or "",
        )
    )

    slot_source = (root / "content_brain" / "execution" / "voice_preflight_runtime_slot.py").read_text(encoding="utf-8")
    engine_source = (root / "content_brain" / "execution" / "provider_runtime_engine.py").read_text(encoding="utf-8")
    forbidden_tts = bool(
        re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", slot_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", engine_source, re.MULTILINE)
        or "generate_voice" in slot_source
    )
    results.append(
        _pass(
            "no_live_tts_import_or_call",
            not forbidden_tts,
            "clean" if not forbidden_tts else "forbidden reference",
        )
    )

    results.append(
        _pass(
            "voice_slot_executed_false",
            voice_ready.get("executed") is False
            and voice_skipped.get("executed") is False
            and _dict(ready_runtime.get("operations")).get("voice_preflight_dry_run", {}).get("executed") is False,
            str(voice_ready.get("executed")),
        )
    )

    video_before = {
        "state": "RUNNING",
        "provider": "hailuo_browser",
        "status": "running",
        "started_at": "2026-05-31 00:00:00",
    }
    shell = ensure_multi_category_shell(
        {
            "category_runtime": {CATEGORY_VIDEO: dict(video_before)},
            "artifacts_by_category": {},
        }
    )
    after = apply_voice_preflight_dry_run(_session_with_narration(), shell, project_root=root)
    video_after = dict(_dict(after.get("category_runtime")).get(CATEGORY_VIDEO))
    results.append(
        _pass(
            "video_slot_unchanged_by_voice_preflight",
            video_after.get("state") == video_before["state"]
            and video_after.get("provider") == video_before["provider"]
            and video_after.get("started_at") == video_before["started_at"],
            video_after.get("state") or "",
        )
    )

    legacy_session = {"execution_session_id": "exec_legacy_no_runtime", "brief_snapshot": {}}
    legacy_slot = get_category_slot(legacy_session, CATEGORY_VOICE)
    results.append(
        _pass(
            "legacy_session_without_runtime_safe",
            legacy_slot.get("status") in ("planned", STATUS_SKIPPED) and legacy_slot.get("executed") is False,
            legacy_slot.get("status") or "",
        )
    )

    panel = PanelExtractor().extract_provider_runtime(
        {
            "execution_runtime": ready_runtime,
            "provider_audit_log": [],
        }
    )
    panel_data = panel.get("data", {})
    slots = panel_data.get("category_runtime_slots") or []
    voice_panel = next((s for s in slots if s.get("category_key") == CATEGORY_VOICE), {})
    results.append(
        _pass(
            "panel_exposes_voice_generation_slot",
            panel_data.get("voice_generation_status") == STATUS_PENDING
            and panel_data.get("voice_generation_executed") is False
            and voice_panel.get("status") == STATUS_PENDING,
            str(panel_data.get("voice_generation_status")),
        )
    )

    forbidden_legacy = bool(
        re.search(r"^\s*(from|import)\s+.*TimelineEngine", slot_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*full_video_pipeline", slot_source, re.MULTILINE)
    )
    results.append(
        _pass(
            "no_legacy_pipeline_imports",
            not forbidden_legacy,
            "clean" if not forbidden_legacy else "forbidden import",
        )
    )

    results.append(_pass("validate_11g_still_passes", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11H-1b",
        "label": "voice_preflight_runtime_slot",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def _dict(value):
    return value if isinstance(value, dict) else {}


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
