"""
Phase 11H-1e — voice approval gate read-only guard validation (no live TTS).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from content_brain.execution.category_runtime_compat import (
    STATUS_PENDING,
    ensure_multi_category_shell,
    get_category_slot,
    normalize_category_slot,
)
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.voice_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_CREDENTIALS_MISSING,
    BLOCK_LIVE_TTS_NOT_REQUESTED,
    BLOCK_NO_NARRATION,
    BLOCK_VOICE_APPROVAL_REQUIRED,
    STATE_APPROVED,
    STATE_NOT_REQUIRED,
    STATE_REQUIRED,
    can_run_live_voice_tts,
    evaluate_voice_approval_gate,
)
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run
from ui.api.services.panel_extractor import PanelExtractor


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


def _run_npm_build(root: Path) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(root / "ui" / "web"),
        shell=True,
    )
    return result.returncode == 0


def _session_no_narration() -> dict:
    return {
        "execution_session_id": "exec_11h1e_no_narration",
        "brief_snapshot": {"run_context": {"story_intelligence": {}}},
    }


def _session_with_narration() -> dict:
    return {
        "execution_session_id": "exec_11h1e_with_narration",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {"beat_id": "HOOK", "narration": "Narration line for approval gate test."}
                        ]
                    }
                }
            }
        },
    }


def _approval_block(voice_slot: dict) -> dict:
    return _dict(voice_slot.get("approval"))


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        dry_runtime = apply_voice_preflight_dry_run(
            _session_with_narration(),
            ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}}),
            project_root=root,
        )
    voice_dry = dict(_dict(dry_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    approval_dry = _approval_block(voice_dry)
    results.append(
        _pass(
            "dry_run_only_live_tts_not_requested",
            approval_dry.get("approval_required") is False
            and approval_dry.get("approval_state") == STATE_NOT_REQUIRED
            and approval_dry.get("live_tts_eligible") is False
            and BLOCK_LIVE_TTS_NOT_REQUESTED in (approval_dry.get("live_tts_blocked_reasons") or []),
            str(approval_dry.get("live_tts_blocked_reasons")),
        )
    )

    skipped_runtime = apply_voice_preflight_dry_run(
        _session_no_narration(),
        ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}}),
        project_root=root,
    )
    voice_skipped = dict(_dict(skipped_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    approval_skipped = _approval_block(voice_skipped)
    results.append(
        _pass(
            "no_narration_blocked_reason",
            approval_skipped.get("approval_state") == STATE_NOT_REQUIRED
            and BLOCK_NO_NARRATION in (approval_skipped.get("live_tts_blocked_reasons") or []),
            str(approval_skipped.get("live_tts_blocked_reasons")),
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
    approval_missing = _approval_block(voice_missing)
    results.append(
        _pass(
            "missing_credentials_blocked_reason",
            approval_missing.get("approval_state") == STATE_NOT_REQUIRED
            and BLOCK_CREDENTIALS_MISSING in (approval_missing.get("live_tts_blocked_reasons") or []),
            str(approval_missing.get("live_tts_blocked_reasons")),
        )
    )

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        ready_shell = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
        ready_runtime = apply_voice_preflight_dry_run(
            _session_with_narration(),
            ready_shell,
            project_root=root,
        )
    voice_ready = dict(_dict(ready_runtime.get("category_runtime")).get(CATEGORY_VOICE))
    approval_ready = _approval_block(voice_ready)
    results.append(
        _pass(
            "preflight_ready_live_tts_not_requested",
            voice_ready.get("status") == STATUS_PENDING
            and approval_ready.get("approval_required") is False
            and BLOCK_LIVE_TTS_NOT_REQUESTED in (approval_ready.get("live_tts_blocked_reasons") or []),
            str(approval_ready.get("live_tts_blocked_reasons")),
        )
    )

    voice_ready["live_tts_requested"] = True
    approval_requested = evaluate_voice_approval_gate(
        voice_ready,
        _session_with_narration(),
        live_tts_requested=True,
        project_root=root,
    )
    results.append(
        _pass(
            "live_tts_requested_voice_approval_required",
            approval_requested.get("approval_required") is True
            and approval_requested.get("approval_state") == STATE_REQUIRED
            and approval_requested.get("live_tts_eligible") is False
            and BLOCK_VOICE_APPROVAL_REQUIRED in (approval_requested.get("live_tts_blocked_reasons") or []),
            str(approval_requested.get("approval_state")),
        )
    )

    expired_at = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    voice_expired = dict(voice_ready)
    voice_expired["approval"] = {
        "approval_state": STATE_APPROVED,
        "approved_by": "operator",
        "approved_at": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "approval_expires_at": expired_at,
    }
    approval_expired = evaluate_voice_approval_gate(
        voice_expired,
        _session_with_narration(),
        live_tts_requested=True,
        project_root=root,
    )
    results.append(
        _pass(
            "existing_approved_expired",
            approval_expired.get("live_tts_eligible") is False
            and BLOCK_APPROVAL_EXPIRED in (approval_expired.get("live_tts_blocked_reasons") or []),
            str(approval_expired.get("live_tts_blocked_reasons")),
        )
    )

    future_expires = (datetime.now() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    voice_approved = dict(voice_ready)
    voice_approved["approval"] = {
        "approval_state": STATE_APPROVED,
        "approved_by": "operator",
        "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "approval_expires_at": future_expires,
        "estimated_character_count": voice_ready.get("narration_adapter", {}).get("total_text_length", 0),
        "estimated_segment_count": voice_ready.get("segment_count", 0),
    }
    approval_valid = evaluate_voice_approval_gate(
        voice_approved,
        _session_with_narration(),
        live_tts_requested=True,
        project_root=root,
    )
    guard_valid = can_run_live_voice_tts({**voice_approved, "approval": approval_valid}, _session_with_narration())
    results.append(
        _pass(
            "approved_not_expired_guard_allowed_metadata",
            approval_valid.get("live_tts_eligible") is True
            and guard_valid.allowed is True
            and guard_valid.blocked is False,
            str(guard_valid.to_dict()),
        )
    )

    guard_source = (root / "content_brain" / "execution" / "voice_approval_guard.py").read_text(encoding="utf-8")
    slot_source = (root / "content_brain" / "execution" / "voice_preflight_runtime_slot.py").read_text(encoding="utf-8")
    engine_source = (root / "content_brain" / "execution" / "provider_runtime_engine.py").read_text(encoding="utf-8")
    forbidden_tts = bool(
        re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", guard_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", slot_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*elevenlabs_voice_provider", engine_source, re.MULTILINE)
        or "generate_voice" in guard_source
        or "generate_voice" in slot_source
    )
    results.append(
        _pass(
            "no_live_tts_import_or_call",
            not forbidden_tts,
            "clean" if not forbidden_tts else "forbidden reference",
        )
    )

    legacy_session = {"execution_session_id": "exec_legacy_no_runtime", "brief_snapshot": {}}
    legacy_slot = get_category_slot(legacy_session, CATEGORY_VOICE)
    normalized_legacy = normalize_category_slot(legacy_slot, category_key=CATEGORY_VOICE)
    results.append(
        _pass(
            "legacy_session_missing_approval_block_safe",
            "approval" not in normalized_legacy or normalized_legacy.get("approval") is None,
            str(normalized_legacy.get("status")),
        )
    )

    voice_panel = (root / "ui" / "web" / "src" / "components" / "VoiceRuntimeObservabilityPanel.tsx").read_text(
        encoding="utf-8"
    )
    utils = (root / "ui" / "web" / "src" / "utils" / "categoryRuntimeShell.ts").read_text(encoding="utf-8")
    ui_bundle = voice_panel + utils
    results.append(
        _pass(
            "voice_ui_displays_approval_block",
            "Approval required" in voice_panel
            and "Blocked because" in voice_panel
            and "resolveVoiceRuntimeObservability" in utils
            and "approvalRequired" in utils,
        )
    )
    forbidden_buttons = ["Generate voice", "Generate Voice", "Run TTS", "Start TTS"]
    results.append(
        _pass(
            "no_forbidden_tts_labels",
            not any(label in ui_bundle for label in forbidden_buttons),
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
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key-not-used-for-tts"}, clear=False):
        after = apply_voice_preflight_dry_run(_session_with_narration(), shell, project_root=root)
    video_after = dict(_dict(after.get("category_runtime")).get(CATEGORY_VIDEO))
    results.append(
        _pass(
            "video_slot_unchanged",
            video_after.get("state") == video_before["state"]
            and video_after.get("provider") == video_before["provider"],
            video_after.get("state") or "",
        )
    )

    panel = PanelExtractor().extract_provider_runtime(
        {
            "execution_runtime": ready_runtime,
            "provider_audit_log": [],
        }
    )
    panel_data = panel.get("data", {})
    voice_panel_slot = next(
        (s for s in (panel_data.get("category_runtime_slots") or []) if s.get("category_key") == CATEGORY_VOICE),
        {},
    )
    results.append(
        _pass(
            "panel_exposes_approval_block",
            bool(_dict(voice_panel_slot.get("approval")).get("gate_version"))
            and panel_data.get("voice_approval_gate") is not None,
            str(_dict(voice_panel_slot.get("approval")).get("gate_version")),
        )
    )

    forbidden_legacy = bool(
        re.search(r"^\s*(from|import)\s+.*TimelineEngine", slot_source, re.MULTILINE)
        or re.search(r"^\s*(from|import)\s+.*full_video_pipeline", slot_source, re.MULTILINE)
    )
    results.append(
        _pass(
            "legacy_pipeline_untouched",
            not forbidden_legacy,
            "clean" if not forbidden_legacy else "forbidden import",
        )
    )

    results.append(_pass("validate_11h1b_still_passes", _run_module("project_brain.validate_11h1b_voice_preflight_runtime_slot")))
    results.append(_pass("validate_11h1c_still_passes", _run_module("project_brain.validate_11h1c_voice_ui_observability")))
    results.append(_pass("validate_11g_still_passes", _run_module("project_brain.validate_11g_multi_category_runtime_shell")))
    results.append(_pass("npm_build_passes", _run_npm_build(root)))

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11H-1e",
        "label": "voice_approval_guard_readonly",
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
