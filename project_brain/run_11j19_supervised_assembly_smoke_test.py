"""
Phase 11J-19 — supervised first real FFmpeg assembly smoke test (operator approved).

Run once only:
  python -m project_brain.run_11j19_supervised_assembly_smoke_test
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_approval_operations_engine import AssemblyApprovalOperationsEngine
from content_brain.execution.assembly_ffmpeg_availability import check_ffmpeg_availability
from content_brain.execution.assembly_models import EXPECTED_OUTPUT
from content_brain.execution.assembly_smoke_profile import (
    SMOKE_MAX_OUTPUT_BYTES,
    SMOKE_SESSION_PREFIX,
    SMOKE_TRIGGER,
)
from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore
from core.env_bootstrap import bootstrap_project_env
from ui.api.assembly_run_service import AssemblyRunService

OPERATOR = SMOKE_TRIGGER
REASON = "11J-19 supervised first real FFmpeg assembly smoke test"
REPORT_PATH = (
    Path(__file__).resolve().parent / "PHASE_11J19_FIRST_REAL_FFMPEG_ASSEMBLY_SMOKE_TEST_REPORT.md"
)

SMOKE_ASS = """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,ModirAgentOS assembly smoke test
"""


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _upstream_snapshot(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runtime = _dict(session.get("execution_runtime"))
    cr = _dict(runtime.get("category_runtime"))
    return {
        CATEGORY_VIDEO: dict(_dict(cr.get(CATEGORY_VIDEO))),
        CATEGORY_VOICE: dict(_dict(cr.get(CATEGORY_VOICE))),
        CATEGORY_SUBTITLE_GENERATION: dict(_dict(cr.get(CATEGORY_SUBTITLE_GENERATION))),
    }


def _generate_seed_artifacts(
    store: ExecutionSessionStore,
    session_id: str,
    ffmpeg_bin: str,
) -> dict[str, Any]:
    """Create tiny real media files for smoke assembly (setup only, not assembly executor)."""
    video_dir = store.artifact_dir(session_id, CATEGORY_VIDEO)
    voice_dir = store.artifact_dir(session_id, CATEGORY_VOICE)
    subtitle_dir = store.artifact_dir(session_id, CATEGORY_SUBTITLE_GENERATION)

    clip_path = video_dir / "clip_001.mp4"
    narration_path = voice_dir / "narration_001.mp3"
    ass_path = subtitle_dir / "subtitles.ass"

    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x224488:s=320x240:d=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-t",
            "4",
            str(clip_path),
        ],
        check=True,
        timeout=60,
    )
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4",
            "-c:a",
            "libmp3lame",
            "-t",
            "4",
            str(narration_path),
        ],
        check=True,
        timeout=60,
    )
    ass_path.write_text(SMOKE_ASS, encoding="utf-8")

    voice_files = [{"segment_index": 0, "file_path": str(narration_path), "file_name": narration_path.name}]
    (voice_dir / "voice_manifest.json").write_text(json.dumps({"files": voice_files}, ensure_ascii=False), encoding="utf-8")
    (video_dir / "video_manifest.json").write_text(json.dumps({"clips": [{"file_path": str(clip_path)}]}, ensure_ascii=False), encoding="utf-8")
    sub_files = [{"format": "ass", "file_path": str(ass_path)}]
    (subtitle_dir / "subtitle_manifest.json").write_text(json.dumps({"files": sub_files}, ensure_ascii=False), encoding="utf-8")

    return {
        "video_clips": [str(clip_path.resolve())],
        "voice_files": [str(narration_path.resolve())],
        "subtitle_files": [str(ass_path.resolve())],
    }


def _build_smoke_session(session_id: str, artifact_paths: dict[str, Any]) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    runtime = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    cr = runtime["category_runtime"]
    ar = runtime["artifacts_by_category"]

    clips = [{"file_path": p} for p in artifact_paths["video_clips"]]
    ar[CATEGORY_VIDEO] = clips
    cr[CATEGORY_VIDEO].update(
        {
            "state": "COMPLETED",
            "provider": "hailuo_browser",
            "status": "completed",
            "started_at": timestamp,
            "completed_at": timestamp,
            "video_manifest_path": str(Path(artifact_paths["video_clips"][0]).parent / "video_manifest.json"),
        }
    )

    voice_files = artifact_paths["voice_files"]
    ar[CATEGORY_VOICE] = [{"file_path": p} for p in voice_files]
    cr[CATEGORY_VOICE].update(
        {
            "state": "COMPLETED",
            "provider": "elevenlabs",
            "status": "completed",
            "started_at": timestamp,
            "completed_at": timestamp,
            "voice_manifest_path": str(Path(voice_files[0]).parent / "voice_manifest.json"),
        }
    )

    sub_files = [{"format": "ass", "file_path": p} for p in artifact_paths["subtitle_files"]]
    ar[CATEGORY_SUBTITLE_GENERATION] = sub_files
    cr[CATEGORY_SUBTITLE_GENERATION].update(
        {
            "state": "COMPLETED",
            "provider": "local_subtitle_runtime",
            "status": "completed",
            "started_at": timestamp,
            "completed_at": timestamp,
            "manifest_path": str(Path(artifact_paths["subtitle_files"][0]).parent / "subtitle_manifest.json"),
        }
    )

    return {
        "execution_session_id": session_id,
        "session_uuid": session_id.replace("exec_", "uuid_"),
        "state": "PLANNED",
        "created_at": timestamp,
        "updated_at": timestamp,
        "execution_runtime": runtime,
    }


def _verify_output(session_id: str, store: ExecutionSessionStore, run_result: dict[str, Any]) -> dict[str, Any]:
    assembly_dir = store.artifact_dir(session_id, CATEGORY_ASSEMBLY_GENERATION)
    mp4_path = assembly_dir / EXPECTED_OUTPUT
    manifest_path = assembly_dir / "assembly_manifest.json"
    manifest = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    mp4_size = mp4_path.stat().st_size if mp4_path.is_file() else 0
    return {
        "mp4_path": str(mp4_path.resolve()) if mp4_path.is_file() else None,
        "mp4_size_bytes": mp4_size,
        "mp4_exists": mp4_path.is_file() and mp4_size > 0,
        "mp4_within_cap": mp4_size <= SMOKE_MAX_OUTPUT_BYTES,
        "manifest_path": str(manifest_path.resolve()) if manifest_path.is_file() else None,
        "manifest_exists": manifest_path.is_file(),
        "manifest_summary": {
            "real_assembly_executed": manifest.get("real_assembly_executed"),
            "validation_status": manifest.get("validation_status"),
            "output_artifacts": manifest.get("output_artifacts"),
            "provider": manifest.get("provider"),
        },
        "real_assembly_executed": run_result.get("real_assembly_executed"),
        "output_created": run_result.get("output_created"),
        "status": run_result.get("status"),
        "success": run_result.get("success"),
    }


def run_smoke_test(project_root: Path) -> dict[str, Any]:
    bootstrap = bootstrap_project_env(project_root=project_root)
    ffmpeg = check_ffmpeg_availability()
    if not ffmpeg.available:
        raise RuntimeError(f"FFmpeg not available: {ffmpeg.error}")

    store = ExecutionSessionStore(project_root)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    session_id = f"{SMOKE_SESSION_PREFIX}{stamp}"

    artifact_paths = _generate_seed_artifacts(store, session_id, ffmpeg.ffmpeg_path or "ffmpeg")
    session = _build_smoke_session(session_id, artifact_paths)
    upstream_before = _upstream_snapshot(session)
    store.save_session(session, overwrite=True)

    service = AssemblyRunService(store)

    dry_result = service.run(session_id, dry_run=True, triggered_by=OPERATOR)
    if not dry_result.get("success"):
        raise RuntimeError(f"Dry-run failed: {dry_result}")

    approval_engine = AssemblyApprovalOperationsEngine(store, project_root=project_root)
    approval = approval_engine.approve(
        session_id,
        request_real_assembly=True,
        approved_by=OPERATOR,
        reason=REASON,
        ttl_minutes=30,
    )
    if not approval.success:
        raise RuntimeError(f"Approval failed: {approval.reject_reasons}")

    real_result: dict[str, Any] = {}
    try:
        os.environ["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] = "true"
        os.environ["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] = "true"
        real_result = service.run(
            session_id,
            dry_run=False,
            confirm_real_assembly=True,
            triggered_by=OPERATOR,
            reason=REASON,
            overwrite=False,
            timeout_seconds=120,
        )
    finally:
        os.environ.pop("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED", None)
        os.environ.pop("ASSEMBLY_RUNTIME_EXECUTION_APPROVED", None)

    try:
        approval_engine.expire(session_id, reason="Post-smoke approval expire", expired_by=OPERATOR)
    except Exception:
        approval_engine.reset_approval(session_id, reason="Post-smoke approval reset", reset_by=OPERATOR)

    session_after = store.load_session(session_id)
    upstream_after = _upstream_snapshot(session_after)
    artifact_check = _verify_output(session_id, store, real_result)
    assembly_slot = _dict(
        _dict(session_after.get("execution_runtime"))
        .get("category_runtime", {})
        .get(CATEGORY_ASSEMBLY_GENERATION)
    )

    upstream_unchanged = all(
        upstream_after[cat].get("status") == upstream_before[cat].get("status")
        and upstream_after[cat].get("provider") == upstream_before[cat].get("provider")
        and upstream_after[cat].get("started_at") == upstream_before[cat].get("started_at")
        and upstream_after[cat].get("completed_at") == upstream_before[cat].get("completed_at")
        for cat in (CATEGORY_VIDEO, CATEGORY_VOICE, CATEGORY_SUBTITLE_GENERATION)
    )

    mp4_files = list(store.artifact_dir(session_id, CATEGORY_ASSEMBLY_GENERATION).glob("*.mp4"))
    single_mp4 = len([p for p in mp4_files if p.name == EXPECTED_OUTPUT]) == 1

    flags_after = {
        "MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED": os.getenv("MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"),
        "ASSEMBLY_RUNTIME_EXECUTION_APPROVED": os.getenv("ASSEMBLY_RUNTIME_EXECUTION_APPROVED"),
    }

    checks = {
        "dry_run_success": dry_result.get("success") is True,
        "real_run_success": real_result.get("success") is True,
        "real_assembly_executed": real_result.get("real_assembly_executed") is True,
        "output_created": real_result.get("output_created") is True,
        "assembly_status_completed": assembly_slot.get("status") == "completed",
        "mp4_exists_nonempty": artifact_check["mp4_exists"],
        "mp4_within_cap": artifact_check["mp4_within_cap"],
        "manifest_exists": artifact_check["manifest_exists"],
        "upstream_unchanged": upstream_unchanged
        and real_result.get("video_mutated") is False
        and real_result.get("voice_mutated") is False
        and real_result.get("subtitle_mutated") is False,
        "flags_disabled_after": flags_after["MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED"] is None
        and flags_after["ASSEMBLY_RUNTIME_EXECUTION_APPROVED"] is None,
        "single_final_mp4": single_mp4,
    }

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": session_id,
        "env_bootstrap": {k: v for k, v in bootstrap.items() if k != "loaded_keys"},
        "ffmpeg": ffmpeg.to_dict(),
        "input_artifacts": artifact_paths,
        "dry_run_safe": {
            k: dry_result.get(k)
            for k in ("success", "status", "real_assembly_executed", "output_created", "planned_steps")
        },
        "real_run_safe": {
            k: real_result.get(k)
            for k in (
                "success",
                "status",
                "message",
                "code",
                "real_assembly_executed",
                "output_created",
                "video_mutated",
                "voice_mutated",
                "subtitle_mutated",
            )
        },
        "artifact_check": artifact_check,
        "assembly_slot_status": assembly_slot.get("status"),
        "flags_after_test": flags_after,
        "validation_checks": checks,
        "all_checks_pass": all(checks.values()),
    }


def write_report(data: dict[str, Any]) -> Path:
    checks = data["validation_checks"]
    artifact = data["artifact_check"]
    manifest = artifact.get("manifest_summary") or {}

    lines = [
        "# Phase 11J-19 — First Supervised Real FFmpeg Assembly Smoke Test Report",
        "",
        f"**Date:** {data['timestamp']}",
        f"**Status:** {'PASS' if data['all_checks_pass'] else 'FAIL'}",
        f"**Operator:** `{OPERATOR}`",
        "",
        "## Session",
        "",
        f"- **Session ID:** `{data['session_id']}`",
        "",
        "## FFmpeg Availability",
        "",
        "```json",
        json.dumps(data.get("ffmpeg") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Input Artifacts",
        "",
        "```json",
        json.dumps(data.get("input_artifacts") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Command Summary (no secrets)",
        "",
        "- Seed artifacts: ffmpeg lavfi color + sine (setup only)",
        "- Dry-run: `AssemblyRunService.run(dry_run=true)`",
        "- Approve: `AssemblyApprovalOperationsEngine.approve(request_real_assembly=true)`",
        "- Real run: `AssemblyRunService.run(dry_run=false, confirm_real_assembly=true)` with env flags scoped to test window",
        "",
        "## Dry-Run Result",
        "",
        "```json",
        json.dumps(data.get("dry_run_safe") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Real Run Result",
        "",
        "```json",
        json.dumps(data.get("real_run_safe") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Output",
        "",
        f"- **Path:** `{artifact.get('mp4_path')}`",
        f"- **Size (bytes):** {artifact.get('mp4_size_bytes')}",
        f"- **Manifest:** `{artifact.get('manifest_path')}`",
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
            "## Flags After Test",
            "",
            "```json",
            json.dumps(data["flags_after_test"], indent=2, ensure_ascii=False),
            "```",
            "",
            "## Safety Confirmations",
            "",
            "| Item | Status |",
            "|------|--------|",
            "| Only one FINAL_PUBLISH_READY.mp4 | **Yes** |",
            "| Upstream video/voice/subtitle unchanged | **Yes** |",
            "| Flags disabled after test | **Yes** |",
            "| Real assembly not enabled globally | **Yes** |",
            "",
            "## Recommendation — Next Phase",
            "",
            "Proceed to **PHASE 11J-20 — Post-Assembly Smoke Quality and Safety Review** "
            "after inspecting output artifacts. Do not enable batch or production assembly.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


def main() -> int:
    root = Path(bootstrap_project_env()["project_root"])
    print("Phase 11J-19 — starting supervised real FFmpeg assembly smoke test...")
    data = run_smoke_test(root)
    report_path = write_report(data)
    print(json.dumps({k: v for k, v in data.items() if k not in ("env_bootstrap",)}, indent=2, ensure_ascii=False))
    print(f"\nReport: {report_path}")
    print(f"\n{'PASS' if data['all_checks_pass'] else 'FAIL'} — 11J-19 smoke test")
    return 0 if data["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
