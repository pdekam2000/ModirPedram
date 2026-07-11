"""
Phase E2E-40S — Collect end-to-end pipeline metrics from a UAT session (read-only).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


def _runtime_seconds(created_at: str | None, updated_at: str | None) -> float | None:
    start = _parse_ts(created_at)
    end = _parse_ts(updated_at)
    if start and end:
        return max(0.0, (end - start).total_seconds())
    return None


def collect_e2e_40s_metrics(
    project_root: Path,
    session_id: str,
    *,
    requested_duration_seconds: int | None = None,
) -> dict[str, Any]:
    store = ExecutionSessionStore(project_root)
    session = store.load_session(session_id)
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    uat_run = _dict(operations.get("uat_run"))
    brief = _dict(session.get("brief_snapshot"))
    vfp = _dict(brief.get("video_format_plan"))
    stages = _dict(uat_run.get("stages"))

    planned_clip_count = int(
        vfp.get("clip_count")
        or stages.get("content_brain", {}).get("clip_count")
        or uat_run.get("estimated_clip_count")
        or 0
    )

    artifact_root = store.artifact_dir(session_id, CATEGORY_VIDEO).parent
    video_dir = artifact_root / "video_generation"
    voice_dir = artifact_root / "voice_generation"
    subtitle_dir = artifact_root / "subtitle_generation"
    assembly_dir = artifact_root / "assembly_generation"

    downloaded_paths: list[str] = []
    generated_clip_count = 0
    for pattern in ("clip_*.mp4", "runway_clip_*.mp4"):
        for path in sorted(video_dir.glob(pattern)):
            if path.is_file() and path.stat().st_size > 0:
                downloaded_paths.append(str(path.resolve()))
    downloaded_clip_count = len(downloaded_paths)

    artifacts = _dict(runtime.get("artifacts_by_category"))
    video_artifacts = list(artifacts.get("video_generation") or [])
    if video_artifacts:
        generated_clip_count = len(
            [a for a in video_artifacts if _dict(a).get("validation_status") == "valid"]
        )
    else:
        generated_clip_count = downloaded_clip_count

    continuity_notes: list[dict[str, Any]] = []
    shots = brief.get("schema_director_shots")
    si = _dict(brief.get("story_intelligence"))
    if not si:
        si = _dict(_dict(brief.get("run_context")).get("story_intelligence"))
    if shots is None:
        shots = si.get("schema_director_shots")
    if shots is None:
        cdp = _dict(brief.get("content_decision_package"))
        shots = _dict(cdp.get("story_intelligence")).get("schema_director_shots")
    if shots is None:
        explain = _dict(brief.get("story_intelligence_explainability"))
        shots = explain.get("schema_director_shots")
    shot_list: list[Any] = []
    if isinstance(shots, list):
        shot_list = shots
    elif isinstance(shots, dict):
        shot_list = list(shots.get("shots") or shots.get("director_shots") or [])
    for shot in shot_list:
        if not isinstance(shot, dict):
            continue
        note = str(shot.get("continuity_notes") or "").strip()
        if note:
            continuity_notes.append(
                {
                    "clip_number": shot.get("clip_number"),
                    "beat_id": shot.get("beat_id"),
                    "continuity_notes": note,
                }
            )
    if not continuity_notes:
        for meta in vfp.get("clip_metadata") or []:
            if not isinstance(meta, dict):
                continue
            note = str(meta.get("continuity_notes") or "").strip()
            if note:
                continuity_notes.append(
                    {
                        "clip_number": meta.get("clip_number"),
                        "beat_id": meta.get("beat_id"),
                        "continuity_notes": note,
                    }
                )

    narration_path = None
    voice_manifest = voice_dir / "voice_manifest.json"
    if voice_manifest.is_file():
        vm = json.loads(voice_manifest.read_text(encoding="utf-8"))
        segments = vm.get("segments") or []
        if segments and isinstance(segments[0], dict):
            narration_path = segments[0].get("file_path")
    if not narration_path:
        mp3s = sorted(voice_dir.glob("narration_*.mp3"))
        if mp3s:
            narration_path = str(mp3s[0].resolve())

    subtitle_path = subtitle_dir / "subtitles.srt"
    if not subtitle_path.is_file():
        ass = subtitle_dir / "subtitles.ass"
        subtitle_path = ass if ass.is_file() else None

    final_video = assembly_dir / "FINAL_PUBLISH_READY.mp4"
    assembly_manifest = assembly_dir / "assembly_manifest.json"

    warnings = list(uat_run.get("warnings") or [])
    errors = list(uat_run.get("errors") or [])

    smoke_guard = uat_run.get("smoke_duration_guard") or {}
    effective_duration = int(
        uat_run.get("target_duration_seconds")
        or smoke_guard.get("smoke_adjusted_duration_seconds")
        or vfp.get("total_duration_seconds")
        or requested_duration_seconds
        or 0
    )

    dispatch = _dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO))
    clip_results = dispatch.get("clip_results") or []

    return {
        "session_id": session_id,
        "topic": uat_run.get("topic") or brief.get("topic"),
        "status": uat_run.get("status") or session.get("state"),
        "requested_duration_seconds": requested_duration_seconds
        or uat_run.get("requested_duration_seconds")
        or smoke_guard.get("original_duration_seconds"),
        "effective_duration_seconds": effective_duration,
        "planned_clip_count": planned_clip_count,
        "target_clip_count": int(vfp.get("target_clip_count") or planned_clip_count),
        "generated_clip_count": generated_clip_count,
        "downloaded_clip_count": downloaded_clip_count,
        "downloaded_file_paths": downloaded_paths,
        "clip_results_count": len(clip_results) if clip_results else downloaded_clip_count,
        "continuity_notes": continuity_notes,
        "continuity_note_count": len(continuity_notes),
        "narration_path": narration_path,
        "subtitle_path": str(subtitle_path.resolve()) if subtitle_path else None,
        "assembly_path": str(assembly_manifest.resolve()) if assembly_manifest.is_file() else None,
        "final_video_path": str(final_video.resolve()) if final_video.is_file() else None,
        "final_video_exists": final_video.is_file(),
        "final_video_bytes": final_video.stat().st_size if final_video.is_file() else 0,
        "stages": stages,
        "warnings": warnings,
        "errors": errors,
        "smoke_duration_guard": smoke_guard,
        "smoke_narration": uat_run.get("smoke_narration"),
        "total_runtime_seconds": _runtime_seconds(
            str(session.get("created_at") or uat_run.get("started_at") or ""),
            str(session.get("updated_at") or uat_run.get("completed_at") or ""),
        ),
        "artifact_folder": str(artifact_root.resolve()),
        "video_provider": uat_run.get("video_provider") or session.get("provider"),
        "voice_provider": uat_run.get("voice_provider"),
        "confirm_real_video": uat_run.get("confirm_real_video"),
        "confirm_real_voice": uat_run.get("confirm_real_voice"),
        "confirm_real_assembly": uat_run.get("confirm_real_assembly"),
    }


def render_e2e_40s_report_markdown(metrics: dict[str, Any], *, test_config: dict[str, Any]) -> str:
    def ok(flag: bool) -> str:
        return "PASS" if flag else "FAIL"

    planned = int(metrics.get("planned_clip_count") or 0)
    generated = int(metrics.get("generated_clip_count") or 0)
    downloaded = int(metrics.get("downloaded_clip_count") or 0)
    final_ok = bool(metrics.get("final_video_exists"))

    objectives = [
        ("Clip planning", planned > 0, f"planned_clip_count={planned}"),
        ("All clips generated", generated >= planned and planned > 0, f"generated={generated}/{planned}"),
        ("All clips downloaded", downloaded >= planned and planned > 0, f"downloaded={downloaded}/{planned}"),
        (
            "Clip continuity documented",
            int(metrics.get("continuity_note_count") or 0) > 0,
            f"continuity_notes={metrics.get('continuity_note_count')}",
        ),
        ("ElevenLabs narration", bool(metrics.get("narration_path")), metrics.get("narration_path") or "missing"),
        ("Subtitles generated", bool(metrics.get("subtitle_path")), metrics.get("subtitle_path") or "missing"),
        ("Assembly completed", bool(metrics.get("assembly_path")), metrics.get("assembly_path") or "missing"),
        ("FINAL_PUBLISH_READY.mp4", final_ok, metrics.get("final_video_path") or "missing"),
    ]

    lines = [
        "# PHASE E2E-40S — End-to-End Production Pipeline Validation",
        "",
        f"**Session:** `{metrics.get('session_id')}`",
        f"**Status:** {metrics.get('status')}",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## Test configuration",
        "",
        f"- **Topic:** {test_config.get('topic')}",
        f"- **Video provider:** {test_config.get('video_provider')}",
        f"- **Requested duration (s):** {test_config.get('duration_seconds')}",
        f"- **Effective duration (s):** {metrics.get('effective_duration_seconds')}",
        f"- **Voice:** {test_config.get('voice_provider')} (real={test_config.get('confirm_real_voice')})",
        f"- **Assembly:** real={test_config.get('confirm_real_assembly')}",
        f"- **Subtitles:** enabled",
        f"- **E2E full-duration mode:** {test_config.get('e2e_full_duration')}",
        "",
        "## Objectives",
        "",
        "| # | Objective | Result | Detail |",
        "|---|-----------|--------|--------|",
    ]
    for idx, (label, passed, detail) in enumerate(objectives, start=1):
        lines.append(f"| {idx} | {label} | {ok(passed)} | {detail} |")

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"- **planned_clip_count:** {planned}",
            f"- **generated_clip_count:** {generated}",
            f"- **downloaded_clip_count:** {downloaded}",
            f"- **total_runtime_seconds:** {metrics.get('total_runtime_seconds')}",
            "",
            "### Downloaded clip paths",
            "",
        ]
    )
    for path in metrics.get("downloaded_file_paths") or []:
        lines.append(f"- `{path}`")
    if not metrics.get("downloaded_file_paths"):
        lines.append("- _(none)_")

    lines.extend(
        [
            "",
            "### Artifact paths",
            "",
            f"- **narration_path:** `{metrics.get('narration_path') or '—'}`",
            f"- **subtitle_path:** `{metrics.get('subtitle_path') or '—'}`",
            f"- **assembly_path:** `{metrics.get('assembly_path') or '—'}`",
            f"- **final_video_path:** `{metrics.get('final_video_path') or '—'}`",
            f"- **final_video_bytes:** {metrics.get('final_video_bytes')}",
            "",
            "## Warnings",
            "",
        ]
    )
    for item in metrics.get("warnings") or []:
        lines.append(f"- {item}")
    if not metrics.get("warnings"):
        lines.append("- _(none)_")

    lines.extend(["", "## Failures / errors", ""])
    for item in metrics.get("errors") or []:
        lines.append(f"- {item}")
    if not metrics.get("errors"):
        lines.append("- _(none)_")

    lines.extend(["", "## Stage summary", "", "```json"])
    lines.append(json.dumps(metrics.get("stages") or {}, indent=2, ensure_ascii=False))
    lines.extend(["```", ""])

    if metrics.get("smoke_duration_guard"):
        lines.extend(["## Smoke guard (if applied)", "", "```json"])
        lines.append(json.dumps(metrics.get("smoke_duration_guard"), indent=2, ensure_ascii=False))
        lines.extend(["```", ""])

    overall = final_ok and all(p for _, p, _ in objectives)
    lines.extend(
        [
            "## Overall",
            "",
            f"**Pipeline validation:** {ok(overall)}",
            "",
        ]
    )
    return "\n".join(lines)
