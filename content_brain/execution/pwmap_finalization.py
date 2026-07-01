"""pwmap agent — post-generation finalization, registration, and Results resolution."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.pwmap_runway_agent_adapter import (
    MIN_REAL_MP4_BYTES,
    OUTPUT_ROOT_NAME,
    PWMAP_AGENT_RUNTIME,
    validate_mp4_path,
)
from content_brain.platform.run_isolation import load_latest_run_attempt, record_latest_run_attempt

STAGE_CLIPS_GENERATED = "clips_generated"
STAGE_DOWNLOADS_VERIFIED = "downloads_verified"
STAGE_MANIFEST_WRITTEN = "manifest_written"
STAGE_RESULT_REGISTERED = "result_registered"
STAGE_BROWSER_CLOSED = "browser_closed"

FINALIZATION_STAGES = (
    STAGE_CLIPS_GENERATED,
    STAGE_DOWNLOADS_VERIFIED,
    STAGE_MANIFEST_WRITTEN,
    STAGE_RESULT_REGISTERED,
    STAGE_BROWSER_CLOSED,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip_entries_from_last_result(last_result: dict[str, Any]) -> list[dict[str, Any]]:
    clips = last_result.get("clips") or []
    if not isinstance(clips, list):
        return []
    return [dict(item) for item in clips if isinstance(item, dict)]


def verify_and_recover_clip_downloads(
    *,
    run_dir: Path,
    last_result: dict[str, Any],
    copied_clips: list[dict[str, Any]],
    subprocess_stdout: str = "",
    expected_clip_count: int = 0,
) -> dict[str, Any]:
    """Verify local MP4s exist; recover from pwmap source paths when missing."""
    from content_brain.execution.pwmap_clip_duplicate_guard import apply_pwmap_clip_registration_guards

    run_dir.mkdir(parents=True, exist_ok=True)
    last_clips = _clip_entries_from_last_result(last_result)
    verified: list[dict[str, Any]] = []
    recovered: list[str] = []
    missing: list[str] = []

    for index, item in enumerate(copied_clips, start=1):
        entry = dict(item)
        modir_path = Path(str(entry.get("modir_path") or run_dir / f"clip_{index}.mp4"))
        source_path = Path(
            str(
                entry.get("source_path")
                or (last_clips[index - 1].get("download") if index - 1 < len(last_clips) else "")
            )
        )
        verify = validate_mp4_path(modir_path)
        if not verify["valid"] and source_path.is_file():
            dest = run_dir / f"clip_{index}.mp4"
            if source_path.resolve() != dest.resolve():
                shutil.copy2(source_path, dest)
            modir_path = dest
            verify = validate_mp4_path(modir_path)
            if verify["valid"]:
                recovered.append(str(modir_path.resolve()).replace("\\", "/"))
                entry["recovered_from_source"] = True
        entry["modir_path"] = str(modir_path.resolve()).replace("\\", "/")
        entry["size_bytes"] = verify["size_bytes"]
        entry["valid"] = verify["valid"]
        verified.append(entry)
        if not verify["valid"]:
            missing.append(entry["modir_path"])

    guard = apply_pwmap_clip_registration_guards(
        copied_clips=verified,
        last_result=last_result,
        subprocess_stdout=subprocess_stdout,
        expected_clip_count=expected_clip_count or len(copied_clips) or len(last_clips),
    )
    verified = list(guard.get("guarded_clips") or verified)
    valid_count = sum(1 for clip in verified if clip.get("valid"))
    expected = int(guard.get("expected_clip_count") or len(copied_clips) or len(last_clips))
    duplicate_failed = bool(guard.get("duplicate_chain_failed"))
    return {
        "verified_clips": verified,
        "valid_clip_count": valid_count,
        "expected_clip_count": expected,
        "recovered_paths": recovered,
        "missing_paths": missing,
        "recovery_available": bool(recovered or (valid_count and missing)),
        "downloads_verified": valid_count > 0 and not missing and not duplicate_failed,
        "duplicate_guard": guard,
        "duplicate_chain_failed": duplicate_failed,
        "clip_3_not_applicable": bool(guard.get("clip_3_not_applicable")),
    }


def _resolve_final_video_path(*, run_dir: Path, verified_clips: list[dict[str, Any]]) -> str:
    merged = run_dir / "video.mp4"
    if validate_mp4_path(merged)["valid"]:
        return str(merged.resolve()).replace("\\", "/")
    valid_paths = [
        str(Path(clip["modir_path"]).resolve()).replace("\\", "/")
        for clip in verified_clips
        if clip.get("valid") and clip.get("modir_path")
    ]
    if not valid_paths:
        return ""
    if len(valid_paths) == 1:
        single = run_dir / "video.mp4"
        src = Path(valid_paths[0])
        if src.resolve() != single.resolve():
            shutil.copy2(src, single)
        return str(single.resolve()).replace("\\", "/")
    last = Path(valid_paths[-1])
    if last.is_file():
        shutil.copy2(last, merged)
        return str(merged.resolve()).replace("\\", "/")
    return ""


def _browser_close_reason(*, subprocess_stdout: str, close_browser_requested: bool) -> dict[str, Any]:
    stdout = subprocess_stdout or ""
    if "[i] Chrome left open" in stdout:
        return {
            "browser_closed": False,
            "close_reason": "pwmap_left_browser_open",
            "close_browser_requested": close_browser_requested,
        }
    if close_browser_requested or "context.close" in stdout.lower():
        return {
            "browser_closed": True,
            "close_reason": "pwmap_close_browser_flag",
            "close_browser_requested": close_browser_requested,
        }
    return {
        "browser_closed": False,
        "close_reason": "subprocess_exited_before_explicit_close_signal",
        "close_browser_requested": close_browser_requested,
    }


def write_finalization_artifacts(
    *,
    run_dir: Path,
    run_id: str,
    finalization: dict[str, Any],
    adapter_payload: dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    execution_report = {
        "version": "pwmap_finalization_v1",
        "run_id": run_id,
        "provider_runtime": PWMAP_AGENT_RUNTIME,
        "finalization": finalization,
        "adapter_result": {
            "ok": adapter_payload.get("ok"),
            "status": adapter_payload.get("status"),
            "clip_count": adapter_payload.get("clip_count"),
            "video_path": adapter_payload.get("video_path"),
            "subprocess_exit_code": adapter_payload.get("subprocess_exit_code"),
        },
        "finished_at": _now_iso(),
    }
    agent_result = {
        "version": "pwmap_agent_result_v1",
        "run_id": run_id,
        "ok": adapter_payload.get("ok"),
        "status": adapter_payload.get("status"),
        "clip_count": adapter_payload.get("clip_count"),
        "expected_clip_count": adapter_payload.get("expected_clip_count"),
        "clips_completed": adapter_payload.get("clips_completed"),
        "clips": adapter_payload.get("clips") or [],
        "video_path": adapter_payload.get("video_path"),
        "download_path": adapter_payload.get("download_path"),
        "finalization_stage": finalization.get("current_stage"),
        "finalization_stages": finalization.get("stages") or {},
        "recovery_available": finalization.get("recovery_available"),
        "failure_stage": adapter_payload.get("failure_stage"),
        "failed_clip_index": adapter_payload.get("failed_clip_index"),
        "error": adapter_payload.get("error"),
        "browser_close": finalization.get("browser_close") or {},
        "topic": str((adapter_payload.get("preflight_snapshot") or {}).get("authoritative_topic") or ""),
        "finished_at": _now_iso(),
    }
    (run_dir / "execution_report.json").write_text(json.dumps(execution_report, indent=2), encoding="utf-8")
    (run_dir / "agent_result.json").write_text(json.dumps(agent_result, indent=2, ensure_ascii=False), encoding="utf-8")
    error_payload = finalization.get("error")
    if error_payload:
        (run_dir / "error.json").write_text(json.dumps(error_payload, indent=2), encoding="utf-8")


def register_pwmap_product_studio_run(
    *,
    project_root: str | Path,
    run_id: str,
    topic: str,
    ok: bool,
    clips: list[dict[str, Any]],
    video_path: str,
    run_dir: str,
    partial: bool = False,
) -> dict[str, Any]:
    downloaded_paths = [
        str(clip.get("modir_path"))
        for clip in clips
        if clip.get("valid") and clip.get("modir_path")
    ]
    valid_clip_count = len(downloaded_paths)
    duplicate_failed = any(str(clip.get("status") or "") == "duplicate_failed" for clip in clips)
    candidate_video_path = "" if duplicate_failed else (
        video_path if validate_mp4_path(video_path)["valid"] else ""
    )
    return record_latest_run_attempt(
        project_root,
        {
            "run_id": run_id,
            "topic": topic,
            "ok": ok and valid_clip_count > 0 and not duplicate_failed,
            "simulate": False,
            "clips_completed": valid_clip_count,
            "downloaded_file_paths": downloaded_paths,
            "candidate_video_path": candidate_video_path,
            "final_branded_video_path": candidate_video_path,
            "versioned_run_dir": run_dir,
            "provider_runtime": PWMAP_AGENT_RUNTIME,
            "partial_finalization": partial,
            "stopped_reason": "partial_finalization" if partial else "",
        },
    )


def finalize_pwmap_run(
    *,
    project_root: str | Path,
    run_dir: Path,
    run_id: str,
    last_result: dict[str, Any],
    copied_clips: list[dict[str, Any]],
    adapter_payload: dict[str, Any],
    preflight: dict[str, Any] | None = None,
    subprocess_stdout: str = "",
    close_browser_requested: bool = False,
) -> dict[str, Any]:
    """Run staged finalization after pwmap subprocess completes."""
    stages: dict[str, Any] = {}
    preflight = preflight or dict(adapter_payload.get("preflight_snapshot") or {})
    topic = str(preflight.get("authoritative_topic") or adapter_payload.get("topic") or "")

    clip_count = int(last_result.get("clip_count") or len(copied_clips) or 0)
    stages[STAGE_CLIPS_GENERATED] = {
        "status": "completed" if clip_count > 0 else "failed",
        "clip_count": clip_count,
        "finished_at": _now_iso(),
    }
    current_stage = STAGE_CLIPS_GENERATED

    verify = verify_and_recover_clip_downloads(
        run_dir=run_dir,
        last_result=last_result,
        copied_clips=copied_clips,
        subprocess_stdout=subprocess_stdout,
        expected_clip_count=int(
            (preflight.get("duration_plan") or {}).get("clip_count")
            or last_result.get("clip_count")
            or len(copied_clips)
        ),
    )
    verified_clips = list(verify["verified_clips"])
    duplicate_failed = bool(verify.get("duplicate_chain_failed"))
    downloads_ok = bool(verify["downloads_verified"])
    stages[STAGE_DOWNLOADS_VERIFIED] = {
        "status": "failed" if duplicate_failed else ("completed" if downloads_ok else ("partial" if verify["valid_clip_count"] else "failed")),
        "valid_clip_count": verify["valid_clip_count"],
        "expected_clip_count": verify["expected_clip_count"],
        "recovered_paths": verify["recovered_paths"],
        "missing_paths": verify["missing_paths"],
        "duplicate_chain_failed": duplicate_failed,
        "duplicate_guard": verify.get("duplicate_guard") or {},
        "finished_at": _now_iso(),
    }
    current_stage = STAGE_DOWNLOADS_VERIFIED

    video_path = _resolve_final_video_path(run_dir=run_dir, verified_clips=verified_clips) if not duplicate_failed else ""
    output_ready = validate_mp4_path(video_path)["valid"] if video_path and not duplicate_failed else False
    partial = verify["valid_clip_count"] > 0 and not downloads_ok and not duplicate_failed

    adapter_payload = dict(adapter_payload)
    adapter_payload["clips"] = verified_clips
    adapter_payload["clip_count"] = verify["valid_clip_count"]
    adapter_payload["video_path"] = video_path
    adapter_payload["download_path"] = video_path
    adapter_payload["output_ready"] = output_ready
    adapter_payload["recovery_available"] = bool(verify["recovery_available"] or partial)
    adapter_payload["duplicate_chain_failed"] = duplicate_failed
    adapter_payload["duplicate_guard"] = verify.get("duplicate_guard") or {}
    adapter_payload["status"] = (
        "duplicate_failed"
        if duplicate_failed
        else (
            "completed"
            if output_ready
            else ("partial" if partial else "download_failed")
        )
    )
    adapter_payload["ok"] = (output_ready or partial) and not duplicate_failed
    adapter_payload["finalization"] = {
        "stages": stages,
        "current_stage": current_stage,
        "partial": partial,
        "recovery_available": adapter_payload["recovery_available"],
    }

    adapter_payload["finalization"] = {
        "version": "pwmap_finalization_v1",
        "stages": stages,
        "current_stage": STAGE_DOWNLOADS_VERIFIED,
        "partial": partial,
        "recovery_available": adapter_payload["recovery_available"],
    }

    (run_dir / "normalized_result.json").write_text(json.dumps(adapter_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    stages[STAGE_MANIFEST_WRITTEN] = {
        "status": "completed",
        "files": ["normalized_result.json"],
        "finished_at": _now_iso(),
    }

    registration = register_pwmap_product_studio_run(
        project_root=project_root,
        run_id=run_id,
        topic=topic,
        ok=output_ready,
        clips=verified_clips,
        video_path=video_path,
        run_dir=str(run_dir.resolve()).replace("\\", "/"),
        partial=partial,
    )
    stages[STAGE_RESULT_REGISTERED] = {
        "status": "completed",
        "latest_run_attempt_status": registration.get("status"),
        "run_id": run_id,
        "finished_at": _now_iso(),
    }

    browser_close = _browser_close_reason(
        subprocess_stdout=subprocess_stdout,
        close_browser_requested=close_browser_requested,
    )
    stages[STAGE_BROWSER_CLOSED] = {
        "status": "completed" if browser_close["browser_closed"] else "deferred",
        **browser_close,
        "finished_at": _now_iso(),
    }

    finalization = {
        "version": "pwmap_finalization_v1",
        "stages": stages,
        "current_stage": STAGE_BROWSER_CLOSED,
        "partial": partial,
        "recovery_available": adapter_payload["recovery_available"],
        "browser_close": browser_close,
        "error": None if output_ready or partial else {
            "reason": "downloads_not_verified",
            "missing_paths": verify["missing_paths"],
            "valid_clip_count": verify["valid_clip_count"],
        },
    }
    adapter_payload["finalization"] = finalization
    adapter_payload["finished_at"] = _now_iso()

    write_finalization_artifacts(
        run_dir=run_dir,
        run_id=run_id,
        finalization=finalization,
        adapter_payload=adapter_payload,
    )
    stages[STAGE_MANIFEST_WRITTEN]["files"] = [
        "normalized_result.json",
        "execution_report.json",
        "agent_result.json",
    ]
    finalization["stages"] = stages
    (run_dir / "normalized_result.json").write_text(json.dumps(adapter_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return adapter_payload


def parse_pwmap_run_id_timestamp(run_id: str) -> datetime | None:
    match = re.match(r"pwmap_(\d{8}T\d{6})_", str(run_id or ""))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_subprocess_failure_details(stdout: str) -> dict[str, Any]:
    text = stdout or ""
    expected_clip_count = 0
    current_clip = 0
    error = ""
    for line in text.splitlines():
        planned = re.search(r"Clips to generate:\s*(\d+)", line)
        if planned:
            expected_clip_count = int(planned.group(1))
        header = re.search(r"CLIP\s+(\d+)/(\d+)", line)
        if header:
            current_clip = int(header.group(1))
            expected_clip_count = int(header.group(2))
        if "[ERROR]" in line:
            error = line.split("[ERROR]", 1)[-1].strip()
    failed_clip_index = current_clip if error else 0
    clips_completed = max(0, failed_clip_index - 1) if failed_clip_index else 0
    if not error:
        downloads = len(re.findall(r"\[OK\] Downloaded:", text))
        clips_completed = max(clips_completed, downloads)
    return {
        "expected_clip_count": expected_clip_count,
        "failed_clip_index": failed_clip_index,
        "clips_completed": clips_completed,
        "error": error,
        "failure_stage": "clip_generation" if error else "",
    }


def scan_runway_downloads_for_run_window(
    downloads_dir: Path,
    *,
    run_started: datetime,
    run_ended: datetime | None = None,
) -> list[Path]:
    if not downloads_dir.is_dir():
        return []
    found: list[tuple[float, Path]] = []
    for path in downloads_dir.glob("clip_*.mp4"):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime >= run_started:
            found.append((mtime.timestamp(), path))
    found.sort(key=lambda item: item[0])
    return [path for _, path in found]


def recover_partial_clips_to_run_dir(
    *,
    run_dir: Path,
    downloads_dir: Path,
    run_started: datetime,
    run_ended: datetime | None = None,
) -> list[dict[str, Any]]:
    run_dir.mkdir(parents=True, exist_ok=True)
    sources = scan_runway_downloads_for_run_window(
        downloads_dir,
        run_started=run_started,
        run_ended=run_ended,
    )
    recovered: list[dict[str, Any]] = []
    for index, src in enumerate(sources, start=1):
        verify = validate_mp4_path(src)
        if not verify["valid"]:
            continue
        dest = run_dir / f"clip_{index}.mp4"
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        recovered.append(
            {
                "clip": index,
                "source_path": str(src.resolve()).replace("\\", "/"),
                "modir_path": str(dest.resolve()).replace("\\", "/"),
                "size_bytes": verify["size_bytes"],
                "valid": True,
                "recovered_from_downloads_scan": True,
            }
        )
    if len(recovered) == 1:
        single = run_dir / "video.mp4"
        src = Path(recovered[0]["modir_path"])
        if src.resolve() != single.resolve():
            shutil.copy2(src, single)
    return recovered


def finalize_partial_pwmap_run(
    *,
    project_root: str | Path,
    run_dir: Path,
    run_id: str,
    pwmap_root: Path,
    adapter_payload: dict[str, Any],
    preflight: dict[str, Any] | None = None,
    subprocess_stdout: str = "",
    close_browser_requested: bool = False,
    clip_timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Preserve partial clip progress when pwmap subprocess exits before full batch completion."""
    preflight = preflight or dict(adapter_payload.get("preflight_snapshot") or {})
    topic = str(preflight.get("authoritative_topic") or "")
    failure = parse_subprocess_failure_details(subprocess_stdout)
    run_started = parse_pwmap_run_id_timestamp(run_id)
    if run_started is None and (run_dir / "job.json").is_file():
        run_started = datetime.fromtimestamp((run_dir / "job.json").stat().st_mtime, tz=timezone.utc)
    if run_started is None:
        run_started = datetime.now(timezone.utc)

    downloads_dir = pwmap_root / "runway_downloads"
    recovered_clips = recover_partial_clips_to_run_dir(
        run_dir=run_dir,
        downloads_dir=downloads_dir,
        run_started=run_started,
    )
    expected_clip_count = int(
        failure.get("expected_clip_count")
        or (preflight.get("multiclip_execution_plan") or {}).get("clip_count")
        or (preflight.get("duration_plan") or {}).get("clip_count")
        or preflight.get("kling_clip_count")
        or len(recovered_clips)
        or 1
    )
    clips_completed = max(int(failure.get("clips_completed") or 0), len(recovered_clips))
    failed_clip_index = int(failure.get("failed_clip_index") or (clips_completed + 1))
    error_text = str(
        failure.get("error")
        or adapter_payload.get("message")
        or f"pwmap agent failed with exit code {adapter_payload.get('subprocess_exit_code')}"
    )

    video_path = _resolve_final_video_path(run_dir=run_dir, verified_clips=recovered_clips)
    partial = clips_completed > 0 and clips_completed < expected_clip_count
    recovery_available = bool(recovered_clips)

    stages: dict[str, Any] = {
        STAGE_CLIPS_GENERATED: {
            "status": "partial",
            "clip_count": clips_completed,
            "expected_clip_count": expected_clip_count,
            "finished_at": _now_iso(),
        },
        STAGE_DOWNLOADS_VERIFIED: {
            "status": "partial" if partial else "failed",
            "valid_clip_count": clips_completed,
            "expected_clip_count": expected_clip_count,
            "recovered_paths": [c["modir_path"] for c in recovered_clips],
            "finished_at": _now_iso(),
        },
    }

    adapter_payload = dict(adapter_payload)
    adapter_payload.update(
        {
            "ok": False,
            "status": "partial_failed" if recovery_available else "failed",
            "clip_count": clips_completed,
            "expected_clip_count": expected_clip_count,
            "clips_completed": clips_completed,
            "clips": recovered_clips,
            "video_path": video_path,
            "download_path": video_path,
            "output_ready": bool(video_path and validate_mp4_path(video_path)["valid"]),
            "recovery_available": recovery_available,
            "failure_stage": failure.get("failure_stage") or "clip_generation",
            "failed_clip_index": failed_clip_index,
            "error": error_text,
            "clip_timeout_seconds": clip_timeout_seconds,
            "preflight_snapshot": preflight,
            "finished_at": _now_iso(),
        }
    )

    (run_dir / "normalized_result.json").write_text(
        json.dumps(adapter_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    stages[STAGE_MANIFEST_WRITTEN] = {
        "status": "completed",
        "files": ["normalized_result.json", "execution_report.json", "agent_result.json"],
        "partial": True,
        "finished_at": _now_iso(),
    }

    registration = register_pwmap_product_studio_run(
        project_root=project_root,
        run_id=run_id,
        topic=topic,
        ok=False,
        clips=recovered_clips,
        video_path=video_path,
        run_dir=str(run_dir.resolve()).replace("\\", "/"),
        partial=True,
    )
    stages[STAGE_RESULT_REGISTERED] = {
        "status": "completed",
        "latest_run_attempt_status": registration.get("status"),
        "run_id": run_id,
        "partial": True,
        "finished_at": _now_iso(),
    }

    browser_close = _browser_close_reason(
        subprocess_stdout=subprocess_stdout,
        close_browser_requested=close_browser_requested,
    )
    stages[STAGE_BROWSER_CLOSED] = {
        "status": "completed" if browser_close["browser_closed"] else "deferred",
        **browser_close,
        "finished_at": _now_iso(),
    }

    finalization = {
        "version": "pwmap_finalization_v1",
        "stages": stages,
        "current_stage": STAGE_MANIFEST_WRITTEN,
        "partial": True,
        "recovery_available": recovery_available,
        "browser_close": browser_close,
        "error": {
            "reason": adapter_payload.get("failure_stage"),
            "failed_clip_index": failed_clip_index,
            "clips_completed": clips_completed,
            "expected_clip_count": expected_clip_count,
            "message": error_text,
        },
    }
    adapter_payload["finalization"] = finalization
    write_finalization_artifacts(
        run_dir=run_dir,
        run_id=run_id,
        finalization=finalization,
        adapter_payload=adapter_payload,
    )
    (run_dir / "normalized_result.json").write_text(
        json.dumps(adapter_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return adapter_payload


def _load_run_payload(run_dir: Path) -> dict[str, Any] | None:
    normalized_path = run_dir / "normalized_result.json"
    if not normalized_path.is_file():
        return None
    try:
        payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _score_pwmap_run(run_dir: Path, payload: dict[str, Any]) -> tuple[int, float]:
    score = 0
    if payload.get("preflight_snapshot"):
        score += 100
    if payload.get("multiclip_execution_plan"):
        score += 20
    if payload.get("provider_runtime") == PWMAP_AGENT_RUNTIME:
        score += 10
    status = str(payload.get("status") or "")
    if payload.get("ok"):
        score += 50
    elif status in {"partial", "partial_failed"}:
        score += 35
    video_path = str(payload.get("video_path") or payload.get("download_path") or "")
    if video_path and validate_mp4_path(video_path)["valid"]:
        score += 40
    elif any(validate_mp4_path(run_dir / f"clip_{i}.mp4")["valid"] for i in range(1, 7)):
        score += 25
    mtime = run_dir.stat().st_mtime
    return score, mtime


def load_latest_product_studio_pwmap_results(project_root: str | Path) -> dict[str, Any] | None:
    """Prefer latest Product Studio pwmap run over stale canonical runway runs."""
    root = Path(project_root).resolve()
    base = root / "outputs" / OUTPUT_ROOT_NAME
    if not base.is_dir():
        return None

    candidates: list[tuple[int, float, Path, dict[str, Any]]] = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith("pwmap_"):
            continue
        payload = _load_run_payload(run_dir)
        if not payload:
            continue
        if not payload.get("preflight_snapshot") and not payload.get("multiclip_execution_plan"):
            continue
        score, mtime = _score_pwmap_run(run_dir, payload)
        candidates.append((score, mtime, run_dir, payload))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[1], item[0]), reverse=True)
    _, _, run_dir, payload = candidates[0]
    return build_pwmap_results_payload(run_dir, payload)


def build_pwmap_results_payload(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or run_dir.name)
    video_path = str(payload.get("video_path") or payload.get("download_path") or "")
    video_valid = validate_mp4_path(video_path)["valid"] if video_path else False
    if not video_valid:
        for index in range(1, int(payload.get("clip_count") or 0) + 1):
            candidate = run_dir / f"clip_{index}.mp4"
            if validate_mp4_path(candidate)["valid"]:
                video_path = str(candidate.resolve()).replace("\\", "/")
                video_valid = True
                break

    finalization = dict(payload.get("finalization") or {})
    recovery_available = bool(
        payload.get("recovery_available")
        or finalization.get("recovery_available")
        or (not video_valid and int(payload.get("clip_count") or 0) > 0)
    )
    status = str(payload.get("status") or ("completed" if video_valid else "failed"))
    if status == "completed" and not video_valid:
        status = "partial_failed" if recovery_available else "download_failed"
    expected_clip_count = int(
        payload.get("expected_clip_count")
        or (payload.get("multiclip_execution_plan") or {}).get("clip_count")
        or payload.get("clip_count")
        or 0
    )
    clips_completed = int(payload.get("clips_completed") or payload.get("clip_count") or 0)

    publish_package_path = str((run_dir / "publish").resolve()).replace("\\", "/") if (run_dir / "publish").is_dir() else ""
    youtube_metadata: dict[str, Any] = dict(payload.get("youtube_metadata") or {})
    assembly_state: dict[str, Any] = {}
    publish_package_state: dict[str, Any] = {}
    try:
        from content_brain.execution.product_assembly_bridge import load_product_assembly_state

        assembly_state = load_product_assembly_state(run_dir)
        if assembly_state.get("publish_package_path"):
            publish_package_path = str(assembly_state.get("publish_package_path") or publish_package_path)
    except Exception:
        assembly_state = {}
    try:
        from content_brain.execution.product_subtitle_branding_publish import load_product_publish_package_state

        publish_package_state = load_product_publish_package_state(run_dir)
        if publish_package_state.get("publish_package_path"):
            publish_package_path = str(publish_package_state.get("publish_package_path") or publish_package_path)
    except Exception:
        publish_package_state = {}
    youtube_upload: dict[str, Any] = {}
    if publish_package_path:
        try:
            from content_brain.upload.youtube_upload_runtime import load_youtube_upload_result

            youtube_upload = load_youtube_upload_result(publish_package_path) or {}
        except Exception:
            youtube_upload = {}
    if not youtube_metadata and publish_package_path:
        try:
            from content_brain.publish.youtube_metadata_generator import load_youtube_metadata

            youtube_metadata = load_youtube_metadata(publish_package_path) or {}
        except Exception:
            youtube_metadata = {}

    visual_diversity: dict[str, Any] = dict(payload.get("visual_diversity") or {})
    if not visual_diversity:
        try:
            from content_brain.execution.product_visual_diversity_guard import load_visual_diversity_report

            visual_diversity = load_visual_diversity_report(run_dir) or load_visual_diversity_report(publish_package_path) or {}
        except Exception:
            visual_diversity = {}

    from content_brain.execution.product_visual_diversity_guard import merge_results_visual_diversity_fields

    base_payload = {
        "found": True,
        "run_id": run_id,
        "selected_run_id": run_id,
        "run_dir": str(run_dir.resolve()).replace("\\", "/"),
        "run_folder": str(run_dir.resolve()).replace("\\", "/"),
        "output_folder": str(run_dir.resolve()).replace("\\", "/"),
        "video_path": video_path if video_valid else "",
        "download_path": video_path if video_valid else "",
        "clip_count": clips_completed,
        "expected_clip_count": expected_clip_count,
        "clips_completed": clips_completed,
        "clips": list(payload.get("clips") or []),
        "provider_runtime": PWMAP_AGENT_RUNTIME,
        "provider_used": "kling_via_pwmap_agent",
        "native_audio_status": "completed" if video_valid else ("partial" if recovery_available else "failed"),
        "generation_status": status,
        "output_ready": video_valid,
        "recovery_available": recovery_available,
        "failure_stage": payload.get("failure_stage") or "",
        "failed_clip_index": payload.get("failed_clip_index"),
        "error": payload.get("error") or "",
        "topic": str((payload.get("preflight_snapshot") or {}).get("authoritative_topic") or ""),
        "metadata": payload,
        "multiclip_execution_plan": payload.get("multiclip_execution_plan") or {},
        "generation_runtime_status": payload.get("generation_runtime_status") or {},
        "execution_mode": payload.get("execution_mode") or "",
        "generation_time_seconds": payload.get("generation_time_seconds"),
        "final_video_duration_seconds": payload.get("final_video_duration_seconds"),
        "finalization": finalization,
        "is_product_studio_pwmap": True,
        "provider_runtime_note": "Executed via external pwmap Runway Agent adapter.",
        "publish_package_path": publish_package_path,
        "youtube_metadata": youtube_metadata,
        "youtube_title": str(youtube_metadata.get("title") or ""),
        "youtube_hashtags": list(youtube_metadata.get("hashtags") or []),
        "youtube_tags_count": len(list(youtube_metadata.get("tags") or [])),
        "youtube_category": str(youtube_metadata.get("category") or ""),
        "youtube_thumbnail_prompt": str(youtube_metadata.get("thumbnail_prompt") or ""),
        "assembly_status": str(assembly_state.get("assembly_status") or payload.get("assembly_status") or ""),
        "assembly_complete": bool(assembly_state.get("assembly_complete") or payload.get("assembly_complete")),
        "publish_package_ready": bool(assembly_state.get("publish_package_ready") or payload.get("publish_package_ready")),
        "final_publish_video_path": str(
            assembly_state.get("final_publish_video_path")
            or payload.get("final_publish_video_path")
            or ""
        ),
        "source_clip_count": int(
            assembly_state.get("source_clip_count")
            or payload.get("source_clip_count")
            or clips_completed
        ),
        "missing_clip_index": assembly_state.get("missing_clip_index") or payload.get("missing_clip_index"),
        "assembly_recovery_possible": bool(
            assembly_state.get("recovery_possible") or payload.get("recovery_possible")
        ),
        "assembly_manifest": assembly_state.get("assembly_manifest") or {},
        "publish_metadata": assembly_state.get("publish_metadata") or {},
        "publish_ready": bool(publish_package_state.get("publish_ready") or payload.get("publish_ready")),
        "final_branded_publish_video_path": str(
            publish_package_state.get("final_branded_publish_video_path")
            or payload.get("final_branded_publish_video_path")
            or ""
        ),
        "subtitle_status": str(publish_package_state.get("subtitle_status") or payload.get("subtitle_status") or ""),
        "branding_status": str(publish_package_state.get("branding_status") or payload.get("branding_status") or ""),
        "audio_status": str(publish_package_state.get("audio_status") or payload.get("audio_status") or ""),
        "logo_status": str(publish_package_state.get("logo_status") or payload.get("logo_status") or ""),
        "cta_status": str(publish_package_state.get("cta_status") or payload.get("cta_status") or ""),
        "intro_status": str(publish_package_state.get("intro_status") or payload.get("intro_status") or ""),
        "outro_status": str(publish_package_state.get("outro_status") or payload.get("outro_status") or ""),
        "subtitle_count": int(publish_package_state.get("subtitle_count") or payload.get("subtitle_count") or 0),
        "subtitle_language": str(publish_package_state.get("subtitle_language") or payload.get("subtitle_language") or ""),
        "normalization_applied": bool(
            publish_package_state.get("normalization_applied") or payload.get("normalization_applied")
        ),
        "lufs_value": publish_package_state.get("lufs_value") or payload.get("lufs_value"),
        "branding_layers": list(publish_package_state.get("branding_layers") or payload.get("branding_layers") or []),
        "publish_package": publish_package_state.get("publish_package") or {},
        "youtube_upload": youtube_upload,
        "youtube_upload_status": str(youtube_upload.get("upload_status") or payload.get("youtube_upload_status") or ""),
        "youtube_video_id": str(youtube_upload.get("youtube_video_id") or payload.get("youtube_video_id") or ""),
        "youtube_url": str(youtube_upload.get("youtube_url") or payload.get("youtube_url") or ""),
        "youtube_visibility": str(youtube_upload.get("visibility") or payload.get("youtube_visibility") or ""),
        "youtube_publish_time": str(youtube_upload.get("publish_time") or payload.get("youtube_publish_time") or ""),
        "youtube_upload_time": str(youtube_upload.get("upload_time") or payload.get("youtube_upload_time") or ""),
    }
    return merge_results_visual_diversity_fields(base_payload, visual_diversity)


def list_pwmap_product_studio_run_history(project_root: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    base = root / "outputs" / OUTPUT_ROOT_NAME
    if not base.is_dir():
        return []
    rows: list[tuple[float, dict[str, Any]]] = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith("pwmap_"):
            continue
        payload = _load_run_payload(run_dir)
        if not payload or not payload.get("preflight_snapshot"):
            continue
        rows.append(
            (
                run_dir.stat().st_mtime,
                {
                    "run_id": run_dir.name,
                    "topic": str((payload.get("preflight_snapshot") or {}).get("authoritative_topic") or ""),
                    "run_dir": str(run_dir.resolve()).replace("\\", "/"),
                    "status": payload.get("status"),
                    "clip_count": payload.get("clip_count"),
                    "created_at": payload.get("finished_at") or "",
                },
            )
        )
    rows.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in rows[: max(1, int(limit))]]


__all__ = [
    "FINALIZATION_STAGES",
    "STAGE_BROWSER_CLOSED",
    "STAGE_CLIPS_GENERATED",
    "STAGE_DOWNLOADS_VERIFIED",
    "STAGE_MANIFEST_WRITTEN",
    "STAGE_RESULT_REGISTERED",
    "build_pwmap_results_payload",
    "finalize_partial_pwmap_run",
    "finalize_pwmap_run",
    "list_pwmap_product_studio_run_history",
    "load_latest_product_studio_pwmap_results",
    "parse_subprocess_failure_details",
    "recover_partial_clips_to_run_dir",
    "register_pwmap_product_studio_run",
    "scan_runway_downloads_for_run_window",
    "verify_and_recover_clip_downloads",
    "write_finalization_artifacts",
]
