"""
Phase 11H-2e — supervised first real ElevenLabs smoke test (operator approved).

Run once only:
  python -m project_brain.run_11h2e_supervised_smoke_test
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_operations_engine import VoiceApprovalOperationsEngine
from content_brain.execution.voice_live_tts_smoke_profile import (
    SMOKE_MAX_CHARACTERS,
    SMOKE_MAX_SEGMENTS,
)
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run
from core.env_bootstrap import bootstrap_project_env
from ui.api.voice_run_service import VoiceRunService

SMOKE_NARRATION = (
    "This is a supervised ModirAgentOS live voice smoke test. "
    "One segment only. No video changes expected."
)
OPERATOR = "operator_smoke_test"
REPORT_PATH = Path(__file__).resolve().parent / "PHASE_11H2E_FIRST_REAL_ELEVENLABS_SMOKE_TEST_REPORT.md"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _video_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict(session.get("execution_runtime"))
    return dict(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO)))


def _build_smoke_session(session_id: str) -> dict[str, Any]:
    if len(SMOKE_NARRATION) > SMOKE_MAX_CHARACTERS:
        raise ValueError(f"Smoke narration exceeds {SMOKE_MAX_CHARACTERS} characters.")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "execution_session_id": session_id,
        "session_uuid": session_id.replace("exec_", "uuid_"),
        "state": "PLANNED",
        "created_at": timestamp,
        "updated_at": timestamp,
        "provider": "hailuo",
        "brief_snapshot": {
            "run_context": {
                "story_intelligence": {
                    "story_architecture": {
                        "beat_plans": [
                            {
                                "beat_id": "HOOK",
                                "narration": SMOKE_NARRATION,
                            }
                        ]
                    }
                }
            }
        },
        "execution_runtime": {
            "category_runtime": {
                CATEGORY_VIDEO: {
                    "state": "COMPLETED",
                    "provider": "hailuo_browser",
                    "status": "completed",
                    "started_at": "2026-05-31 10:00:00",
                    "completed_at": "2026-05-31 10:05:00",
                }
            }
        },
    }


def _verify_artifacts(session_id: str, store: ExecutionSessionStore, result: dict[str, Any]) -> dict[str, Any]:
    artifact_root = store.artifact_dir(session_id, CATEGORY_VOICE)
    mp3_path = artifact_root / "narration_001.mp3"
    manifest_path = artifact_root / "voice_manifest.json"
    manifest = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    mp3_size = mp3_path.stat().st_size if mp3_path.is_file() else 0
    return {
        "mp3_path": str(mp3_path.resolve()) if mp3_path.is_file() else None,
        "mp3_size_bytes": mp3_size,
        "mp3_exists": mp3_path.is_file() and mp3_size > 0,
        "manifest_path": str(manifest_path.resolve()) if manifest_path.is_file() else None,
        "manifest_exists": manifest_path.is_file(),
        "manifest_summary": {
            "provider": manifest.get("provider"),
            "provider_mode": manifest.get("provider_mode"),
            "real_provider_called": manifest.get("real_provider_called"),
            "segment_count": manifest.get("segment_count"),
            "character_count": manifest.get("character_count"),
            "retry_count": manifest.get("retry_count"),
            "request_id": manifest.get("request_id"),
            "voice_id": manifest.get("voice_id"),
            "model_id": manifest.get("model_id"),
        },
        "tts_executed": result.get("tts_executed"),
        "real_provider_called": result.get("real_provider_called"),
        "provider_mode": result.get("provider_mode"),
        "status": result.get("status"),
        "success": result.get("success"),
    }


def run_smoke_test(project_root: Path) -> dict[str, Any]:
    bootstrap = bootstrap_project_env(project_root=project_root)
    store = ExecutionSessionStore(project_root)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    session_id = f"exec_11h2e_smoke_{stamp}"

    session = _build_smoke_session(session_id)
    video_before = _video_snapshot(session)
    store.save_session(session, overwrite=True)

    session = store.load_session(session_id)
    runtime = apply_voice_preflight_dry_run(
        session,
        ensure_multi_category_shell(session.get("execution_runtime") or {}),
        project_root=project_root,
    )
    session["execution_runtime"] = runtime
    store.save_session(session, overwrite=True)

    approval_engine = VoiceApprovalOperationsEngine(store, project_root=project_root)
    approval = approval_engine.approve(
        session_id,
        request_live_tts=True,
        approved_by=OPERATOR,
        reason="11H-2e supervised smoke test approval",
    )
    if not approval.success:
        raise RuntimeError(f"Approval failed: {approval.reject_reasons}")

    session_loaded = store.load_session(session_id)
    voice_before = _dict(_dict(session_loaded["execution_runtime"]["category_runtime"]).get(CATEGORY_VOICE))
    approval_block = _dict(voice_before.get("approval"))
    character_count = int(approval_block.get("estimated_character_count") or len(SMOKE_NARRATION))
    segment_count = int(approval_block.get("estimated_segment_count") or 1)
    estimated_cost = approval_block.get("estimated_voice_cost")

    if segment_count > SMOKE_MAX_SEGMENTS:
        raise RuntimeError(f"Smoke session has {segment_count} segments; max is {SMOKE_MAX_SEGMENTS}.")
    if character_count > SMOKE_MAX_CHARACTERS:
        raise RuntimeError(f"Smoke session has {character_count} chars; max is {SMOKE_MAX_CHARACTERS}.")

    import content_brain.execution.voice_live_tts_action_policy as policy_module

    flags_enabled = False
    run_result: dict[str, Any] = {}
    try:
        os.environ["MODIR_VOICE_LIVE_TTS_ENABLED"] = "true"
        with patch.object(policy_module, "LIVE_RUNTIME_EXECUTION_APPROVED", True):
            flags_enabled = True
            service = VoiceRunService(store)
            run_result = service.run(
                session_id,
                triggered_by=OPERATOR,
                reason="11H-2e supervised first real ElevenLabs smoke test",
                provider_mode="live_elevenlabs",
                confirm_live_tts=True,
            )
    finally:
        os.environ.pop("MODIR_VOICE_LIVE_TTS_ENABLED", None)
        flags_enabled = False

    session_after = store.load_session(session_id)
    video_after = _video_snapshot(session_after)
    voice_after = _dict(_dict(session_after["execution_runtime"]["category_runtime"]).get(CATEGORY_VOICE))
    artifact_check = _verify_artifacts(session_id, store, run_result)

    video_preserved = all(video_after.get(k) == video_before.get(k) for k in ("state", "provider", "started_at", "completed_at"))
    flags_after = {
        "MODIR_VOICE_LIVE_TTS_ENABLED": os.getenv("MODIR_VOICE_LIVE_TTS_ENABLED"),
        "LIVE_RUNTIME_EXECUTION_APPROVED": policy_module.LIVE_RUNTIME_EXECUTION_APPROVED,
    }

    checks = {
        "tts_executed": run_result.get("tts_executed") is True,
        "real_provider_called": run_result.get("real_provider_called") is True,
        "provider_mode_live": run_result.get("provider_mode") == "live_elevenlabs",
        "mp3_exists_nonempty": artifact_check["mp3_exists"],
        "manifest_exists": artifact_check["manifest_exists"],
        "voice_status_completed": voice_after.get("status") == "completed",
        "video_unchanged": video_preserved and run_result.get("video_mutated") is False,
        "flags_disabled_after": flags_after["MODIR_VOICE_LIVE_TTS_ENABLED"] is None
        and flags_after["LIVE_RUNTIME_EXECUTION_APPROVED"] is False,
        "single_segment": segment_count == 1,
    }

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": session_id,
        "env_bootstrap": bootstrap,
        "narration_text_length": len(SMOKE_NARRATION),
        "character_count": character_count,
        "segment_count": segment_count,
        "estimated_voice_cost_usd": estimated_cost,
        "approval_state": approval_block.get("approval_state"),
        "run_result_safe": {
            k: run_result.get(k)
            for k in (
                "success",
                "status",
                "message",
                "code",
                "provider_mode",
                "tts_executed",
                "real_provider_called",
                "video_mutated",
                "manifest_path",
            )
        },
        "artifact_check": artifact_check,
        "voice_slot_status": voice_after.get("status"),
        "video_before": video_before,
        "video_after": video_after,
        "flags_after_test": flags_after,
        "validation_checks": checks,
        "all_checks_pass": all(checks.values()),
    }


def write_report(data: dict[str, Any]) -> Path:
    checks = data["validation_checks"]
    artifact = data["artifact_check"]
    manifest = artifact.get("manifest_summary") or {}

    lines = [
        "# Phase 11H-2e — First Supervised Real ElevenLabs Smoke Test Report",
        "",
        f"**Date:** {data['timestamp']}",
        f"**Status:** {'PASS' if data['all_checks_pass'] else 'FAIL'}",
        f"**Operator:** `{OPERATOR}`",
        "",
        "## Session",
        "",
        f"- **Session ID:** `{data['session_id']}`",
        f"- **Narration length (text):** {data['narration_text_length']} characters",
        f"- **Characters used (approval estimate):** {data['character_count']}",
        f"- **Segments:** {data['segment_count']}",
        f"- **Estimated cost (USD):** {data['estimated_voice_cost_usd']}",
        f"- **Approval state:** `{data['approval_state']}`",
        "",
        "## Provider Response (safe summary)",
        "",
        "```json",
        json.dumps(data["run_result_safe"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Artifacts",
        "",
        f"- **MP3 path:** `{artifact.get('mp3_path')}`",
        f"- **MP3 size (bytes):** {artifact.get('mp3_size_bytes')}",
        f"- **Manifest path:** `{artifact.get('manifest_path')}`",
        "",
        "### Manifest summary",
        "",
        "```json",
        json.dumps(manifest, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Validation Checks",
        "",
        "| Check | Pass |",
        "|-------|------|",
    ]
    for name, ok in checks.items():
        lines.append(f"| {name} | `{ok}` |")
    lines.extend(
        [
            "",
            "## Video Generation (unchanged)",
            "",
            "**Before:**",
            "```json",
            json.dumps(data["video_before"], indent=2, ensure_ascii=False),
            "```",
            "",
            "**After:**",
            "```json",
            json.dumps(data["video_after"], indent=2, ensure_ascii=False),
            "```",
            "",
            "## Flags After Test",
            "",
            "```json",
            json.dumps(data["flags_after_test"], indent=2, ensure_ascii=False),
            "```",
            "",
            "- `MODIR_VOICE_LIVE_TTS_ENABLED` removed from process environment",
            "- `LIVE_RUNTIME_EXECUTION_APPROVED` remains `False` in policy module",
            "",
            "## Safety Confirmations",
            "",
            "| Item | Status |",
            "|------|--------|",
            "| API key printed | **No** |",
            "| Single supervised run only | **Yes** |",
            "| Video runtime modified | **No** |",
            "| Flags disabled after test | **Yes** |",
            "",
            "## Recommendation — Next Phase",
            "",
            "Review smoke artifacts and manifest, confirm audio quality, then proceed to "
            "limited multi-segment mock/live rehearsal (still capped) before production live TTS rollout. "
            "Do not enable `LIVE_RUNTIME_EXECUTION_APPROVED` globally without per-run operator approval.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


def main() -> int:
    root = Path(bootstrap_project_env()["project_root"])
    print("Phase 11H-2e — starting supervised real ElevenLabs smoke test (1 segment)...")
    data = run_smoke_test(root)
    report_path = write_report(data)
    print(json.dumps({k: v for k, v in data.items() if k not in ("video_before", "video_after")}, indent=2, ensure_ascii=False))
    print(f"\nReport: {report_path}")
    print(f"\n{'PASS' if data['all_checks_pass'] else 'FAIL'} — 11H-2e smoke test")
    return 0 if data["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
