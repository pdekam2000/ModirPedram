"""Kling Continuity Chain V1 — generate, recover, extract frame, upload, next clip."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_last_frame_extractor import (
    continuity_dir,
    continuity_frame_path,
    extract_and_save_continuity_frame,
    validate_frame,
)
from content_brain.execution.kling_multishot_locator import try_locate_control
from content_brain.execution.kling_multishot_map_loader import load_kling_ui_map
from content_brain.execution.kling_native_audio_models import (
    FIRST_FRAME_PRIOR_CLIP,
    FIRST_FRAME_USER_UPLOAD,
    KLING_CONTINUITY_CHAIN_VERSION,
    KlingNativeAudioPlan,
    build_continuity_chain_from_plan,
)
from content_brain.execution.kling_multishot_live_engine import (
    STATUS_DOWNLOAD_FAILED,
    recover_kling_multishot_output,
    run_kling_multishot_live,
    verify_recovered_mp4,
)

RUNTIME_VERSION = "kling_continuity_runtime_v1"
CONTINUITY_CHAIN_FILENAME = "continuity_chain_v1.json"
STATUS_CHAIN_IN_PROGRESS = "in_progress"
STATUS_CHAIN_COMPLETE = "complete"
STATUS_CHAIN_STOPPED = "stopped"
STATUS_CHAIN_AWAITING_APPROVAL = "awaiting_approval"
STATUS_DOWNLOAD_FAILED_REPORT = "download_failed"


def _clip_dir(run_dir: Path, clip_index: int) -> Path:
    path = run_dir / "clips" / f"c{clip_index}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_sibling_run_dir(project_root: Path, run_id: str, clip_index: int) -> Path:
    return project_root / "outputs" / "kling_multishot_live" / f"{run_id}_c{clip_index}"


def _clip_download_failed(payload: dict[str, Any]) -> bool:
    if payload.get("download_status") == "failed" or payload.get("status") == STATUS_DOWNLOAD_FAILED:
        return True
    if payload.get("generation_completed") and not str(payload.get("download_path") or "").strip():
        return True
    return any(
        str(step.get("label") or "") == "download" and str(step.get("status") or "") == "failed"
        for step in payload.get("steps") or []
        if isinstance(step, dict)
    )


def _summarize_generation_status(clip_results: list[dict[str, Any]], *, final_video: str) -> str:
    from content_brain.execution.kling_multishot_live_engine import STATUS_COMPLETED, STATUS_FAILED

    if final_video:
        return STATUS_COMPLETED
    if not clip_results:
        return STATUS_FAILED
    last = clip_results[-1]
    if _clip_download_failed(last):
        return STATUS_DOWNLOAD_FAILED_REPORT
    if last.get("ok"):
        return STATUS_COMPLETED
    return STATUS_FAILED


@dataclass
class FrameUploadStatus:
    clip_index: int
    frame_path: str
    uploaded: bool
    control_label: str = "first_frame_upload"
    strategy: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "frame_path": self.frame_path,
            "uploaded": self.uploaded,
            "control_label": self.control_label,
            "strategy": self.strategy,
            "detail": self.detail,
        }


@dataclass
class KlingContinuityChainState:
    run_id: str
    clip_count: int
    continuity_status: str = STATUS_CHAIN_IN_PROGRESS
    chain_complete: bool = False
    frames_extracted: list[dict[str, Any]] = field(default_factory=list)
    frames_uploaded: list[dict[str, Any]] = field(default_factory=list)
    clips: list[dict[str, Any]] = field(default_factory=list)
    stopped_at_clip: int | None = None
    stop_reason: str = ""
    version: str = KLING_CONTINUITY_CHAIN_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "runtime_version": RUNTIME_VERSION,
            "run_id": self.run_id,
            "clip_count": self.clip_count,
            "continuity_status": self.continuity_status,
            "chain_complete": self.chain_complete,
            "frames_extracted_count": len(self.frames_extracted),
            "frames_uploaded_count": len(self.frames_uploaded),
            "frames_extracted": self.frames_extracted,
            "frames_uploaded": self.frames_uploaded,
            "clips": self.clips,
            "stopped_at_clip": self.stopped_at_clip,
            "stop_reason": self.stop_reason,
        }


def continuity_chain_v1_path(run_dir: str | Path) -> Path:
    return continuity_dir(run_dir) / CONTINUITY_CHAIN_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_approved_clips(payload: dict[str, Any], plan: KlingNativeAudioPlan) -> set[int]:
    raw = payload.get("approved_clips")
    if isinstance(raw, list) and raw:
        return {int(x) for x in raw if str(x).strip().isdigit() or isinstance(x, int)}
    if payload.get("approve_all_clips"):
        return set(range(1, plan.clip_count + 1))
    if payload.get("approve_generate"):
        return {1}
    return set()


def clip_is_approved(clip_index: int, approved_clips: set[int]) -> bool:
    return clip_index in approved_clips


def record_upload_status(
    *,
    clip_index: int,
    frame_path: str,
    uploaded: bool,
    strategy: str = "",
    detail: str = "",
) -> dict[str, Any]:
    status = FrameUploadStatus(
        clip_index=clip_index,
        frame_path=frame_path,
        uploaded=uploaded,
        strategy=strategy,
        detail=detail,
    ).to_dict()
    status["recorded_at"] = _now_iso()
    return status


def verify_upload_visible(page: Any, *, map_path: str | Path | None = None) -> dict[str, Any]:
    ui_map = load_kling_ui_map(map_path=map_path)
    labels = dict(ui_map.get("labels") or {})
    entry = labels.get("first_frame_upload")
    if not isinstance(entry, dict):
        return {"ok": False, "control_label": "first_frame_upload", "detail": "map entry missing"}
    located = try_locate_control(page, "first_frame_upload", entry, timeout_ms=4000)
    if located is None:
        return {"ok": False, "control_label": "first_frame_upload", "detail": "control not visible"}
    return {
        "ok": True,
        "control_label": "first_frame_upload",
        "strategy": located.strategy,
        "detail": "first_frame_upload control visible",
    }


def upload_frame_for_next_clip(
    page: Any,
    *,
    frame_path: str | Path,
    clip_index: int,
    map_path: str | Path | None = None,
) -> dict[str, Any]:
    """Upload continuity frame using mapped ``first_frame_upload`` control."""
    upload_path = Path(frame_path).resolve()
    if not upload_path.is_file():
        return record_upload_status(
            clip_index=clip_index,
            frame_path=str(upload_path),
            uploaded=False,
            detail="frame_path missing",
        )

    visible = verify_upload_visible(page, map_path=map_path)
    if not visible.get("ok"):
        return record_upload_status(
            clip_index=clip_index,
            frame_path=str(upload_path),
            uploaded=False,
            detail=str(visible.get("detail") or "upload control not visible"),
        )

    ui_map = load_kling_ui_map(map_path=map_path)
    labels = dict(ui_map.get("labels") or {})
    entry = labels.get("first_frame_upload") or {}
    located = try_locate_control(page, "first_frame_upload", entry, timeout_ms=4000)
    if located is None:
        return record_upload_status(
            clip_index=clip_index,
            frame_path=str(upload_path),
            uploaded=False,
            detail="first_frame_upload control not found",
        )

    try:
        with page.expect_file_chooser(timeout=8000) as fc_info:
            located.locator.click(timeout=8000)
        fc_info.value.set_files(str(upload_path))
    except Exception:
        page.locator('input[type="file"]').first.set_input_files(str(upload_path))

    return record_upload_status(
        clip_index=clip_index,
        frame_path=str(upload_path),
        uploaded=True,
        strategy=str(located.strategy),
        detail="uploaded via first_frame_upload mapped control",
    )


def merge_plan_chain_with_runtime(
    *,
    plan_chain: dict[str, Any],
    runtime_state: KlingContinuityChainState,
) -> dict[str, Any]:
    merged = dict(plan_chain)
    merged.update(runtime_state.to_dict())
    merged["links"] = list(plan_chain.get("links") or merged.get("links") or [])
    merged["frame_sources"] = list(plan_chain.get("frame_sources") or merged.get("frame_sources") or [])
    merged["continuity_notes"] = list(plan_chain.get("continuity_notes") or merged.get("continuity_notes") or [])
    return merged


def write_continuity_chain_files(
    run_dir: Path,
    *,
    plan_chain: dict[str, Any],
    runtime_state: KlingContinuityChainState,
) -> dict[str, Any]:
    payload = merge_plan_chain_with_runtime(plan_chain=plan_chain, runtime_state=runtime_state)
    continuity_dir(run_dir).mkdir(parents=True, exist_ok=True)
    v1_path = continuity_chain_v1_path(run_dir)
    v1_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (run_dir / "continuity_chain.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["continuity_chain_v1_path"] = str(v1_path.resolve()).replace("\\", "/")
    return payload


def _resolve_clip_video(clip_dir: Path) -> str:
    canonical = clip_dir / "video.mp4"
    if canonical.is_file():
        return str(canonical.resolve())
    live = clip_dir / "live_run_result.json"
    if live.is_file():
        try:
            payload = json.loads(live.read_text(encoding="utf-8"))
            path = str(payload.get("download_path") or payload.get("output_path") or "").strip()
            if path and Path(path).is_file():
                return str(Path(path).resolve())
        except (OSError, json.JSONDecodeError):
            pass
    return ""


def _ensure_clip_mp4(
    *,
    project_root: Path,
    run_id: str,
    clip_index: int,
    clip_dir: Path,
    cdp_url: str,
    live_payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    video_path = _resolve_clip_video(clip_dir)
    if video_path:
        verify = verify_recovered_mp4(video_path)
        if verify.get("is_real_mp4"):
            return video_path, live_payload

    if _clip_download_failed(live_payload) or not video_path:
        live = recover_kling_multishot_output(
            run_id=run_id,
            output_dir=clip_dir,
            cdp_url=cdp_url,
            clip_index=clip_index,
        )
        live_payload = live.to_dict()
        live_payload["clip_index"] = clip_index
        live_payload["clip_dir"] = str(clip_dir.resolve()).replace("\\", "/")
        if live.download_path:
            src = Path(live.download_path)
            dest = clip_dir / "video.mp4"
            if src.is_file():
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                video_path = str(dest.resolve())
        (clip_dir / "live_run_result.json").write_text(json.dumps(live_payload, indent=2), encoding="utf-8")
    return video_path, live_payload


def run_kling_continuity_chain(
    *,
    project_root: str | Path,
    run_id: str,
    run_dir: Path,
    plan: KlingNativeAudioPlan,
    approved_by: str,
    confirm_credit_spend: bool,
    first_frame_path: str | None,
    cdp_url: str,
    payload: dict[str, Any],
    topic: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    """Execute multi-clip continuity chain with per-clip approval and frame handoff."""
    root = Path(project_root).resolve()
    approved_clips = _resolve_approved_clips(payload, plan)
    plan_chain = build_continuity_chain_from_plan(plan, run_id=run_id).to_dict()
    runtime_state = KlingContinuityChainState(run_id=run_id, clip_count=plan.clip_count)
    clip_results: list[dict[str, Any]] = []
    prior_frame = first_frame_path
    final_video = ""
    started = datetime.now(timezone.utc)

    for clip in plan.clips:
        clip_index = clip.clip_index
        if not clip_is_approved(clip_index, approved_clips):
            runtime_state.continuity_status = STATUS_CHAIN_AWAITING_APPROVAL
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"awaiting approval for clip {clip_index}"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            break

        clip_dir = _clip_dir(run_dir, clip_index)
        legacy_dir = _legacy_sibling_run_dir(root, run_id, clip_index)
        if legacy_dir.is_dir() and legacy_dir.resolve() != clip_dir.resolve():
            legacy_payload = {
                "status": "legacy_partial",
                "legacy_run_dir": str(legacy_dir.resolve()).replace("\\", "/"),
                "canonical_clip_dir": str(clip_dir.resolve()).replace("\\", "/"),
            }
            (clip_dir / "legacy_sibling_run.json").write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")

        upload_frame = prior_frame if clip_index > 1 else first_frame_path
        live = run_kling_multishot_live(
            shot_1_prompt=clip.shot_1.prompt,
            shot_2_prompt=clip.shot_2.prompt,
            first_frame_path=upload_frame,
            approve_generate=True,
            approved_by=approved_by,
            confirm_credit_spend=confirm_credit_spend,
            run_id=run_id,
            output_dir=clip_dir,
            cdp_url=cdp_url,
        )
        live_payload = live.to_dict()
        live_payload["clip_index"] = clip_index
        live_payload["clip_dir"] = str(clip_dir.resolve()).replace("\\", "/")
        live_payload["continuity_frame_source"] = (
            FIRST_FRAME_PRIOR_CLIP if clip_index > 1 else (FIRST_FRAME_USER_UPLOAD if first_frame_path else "")
        )
        live_payload["prior_clip_reference"] = clip.prior_clip_reference if clip_index > 1 else ""
        if upload_frame:
            live_payload["first_frame_upload"] = record_upload_status(
                clip_index=clip_index,
                frame_path=str(upload_frame),
                uploaded=bool(live.approval_checklist.get("first_frame_uploaded")),
                detail="via run_kling_multishot_live",
            )
            if live_payload["first_frame_upload"].get("uploaded"):
                runtime_state.frames_uploaded.append(live_payload["first_frame_upload"])

        clip_results.append(live_payload)
        (clip_dir / "live_run_result.json").write_text(json.dumps(live_payload, indent=2), encoding="utf-8")

        video_path, live_payload = _ensure_clip_mp4(
            project_root=root,
            run_id=run_id,
            clip_index=clip_index,
            clip_dir=clip_dir,
            cdp_url=cdp_url,
            live_payload=live_payload,
        )
        clip_results[-1] = live_payload

        if video_path:
            dest = clip_dir / "video.mp4"
            src = Path(video_path)
            if src.is_file() and src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            final_video = str(dest.resolve())

        if not live.ok and not _clip_download_failed(live_payload):
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"clip {clip_index} generation failed"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            break

        if not final_video:
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"clip {clip_index} download/recovery failed"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            break

        clip_entry = {
            "clip": clip_index,
            "video_path": final_video,
            "last_frame": "",
            "next_clip": clip_index + 1 if clip_index < plan.clip_count else None,
            "prior_clip_reference": clip.prior_clip_reference if clip_index > 1 else "",
            "continuity_anchor": clip.shot_2.continuity_anchor,
        }

        if clip_index < plan.clip_count:
            extracted = extract_and_save_continuity_frame(
                video_path=final_video,
                run_dir=run_dir,
                clip_index=clip_index,
            )
            clip_entry["last_frame"] = extracted.frame_path
            runtime_state.frames_extracted.append(extracted.to_dict())
            prior_frame = extracted.frame_path

            for link in plan_chain.get("links") or []:
                if int(link.get("from_clip_index") or 0) == clip_index:
                    link["frame_source_path"] = extracted.frame_path
                    link["handoff_status"] = "extracted"
            for source in plan_chain.get("frame_sources") or []:
                if int(source.get("clip_index") or 0) == clip_index + 1:
                    source["asset_path"] = extracted.frame_path
                    source["source"] = FIRST_FRAME_PRIOR_CLIP
        else:
            extracted = extract_and_save_continuity_frame(
                video_path=final_video,
                run_dir=run_dir,
                clip_index=clip_index,
            )
            clip_entry["last_frame"] = extracted.frame_path
            clip_entry["next_clip"] = None
            runtime_state.frames_extracted.append(extracted.to_dict())

        runtime_state.clips.append(clip_entry)
        write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)

        if payload.get("stop_after_clip") and int(payload.get("stop_after_clip") or 0) == clip_index:
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"operator stop after clip {clip_index}"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            break

    finished = datetime.now(timezone.utc)
    completed_clips = len(
        [
            item
            for item in clip_results
            if item.get("ok") or _resolve_clip_video(_clip_dir(run_dir, int(item.get("clip_index") or 0)))
        ]
    )
    if completed_clips >= plan.clip_count and final_video:
        runtime_state.chain_complete = True
        runtime_state.continuity_status = STATUS_CHAIN_COMPLETE
        root_video = run_dir / "video.mp4"
        shutil.copy2(final_video, root_video)
        final_video = str(root_video.resolve())
    elif runtime_state.continuity_status == STATUS_CHAIN_IN_PROGRESS:
        runtime_state.continuity_status = STATUS_CHAIN_STOPPED if runtime_state.stopped_at_clip else STATUS_CHAIN_IN_PROGRESS

    continuity_chain = write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)

    generation_status = _summarize_generation_status(clip_results, final_video=final_video)
    generation_report = {
        "version": RUNTIME_VERSION,
        "run_id": run_id,
        "status": generation_status,
        "clip_results": clip_results,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "generation_time_seconds": round((finished - started).total_seconds(), 2),
        "recovery_available": generation_status == STATUS_DOWNLOAD_FAILED_REPORT,
        "output_ready": bool(final_video),
        "continuity_status": runtime_state.continuity_status,
        "chain_complete": runtime_state.chain_complete,
        "frames_extracted_count": len(runtime_state.frames_extracted),
        "frames_uploaded_count": len(runtime_state.frames_uploaded),
    }
    download_report = {
        "run_id": run_id,
        "clip_count": plan.clip_count,
        "status": "completed" if final_video else ("failed" if generation_status == STATUS_DOWNLOAD_FAILED_REPORT else "pending"),
        "downloads": [
            {
                "clip_index": item.get("clip_index"),
                "download_path": item.get("download_path"),
                "output_path": item.get("output_path"),
                "clip_dir": item.get("clip_dir"),
                "ok": item.get("ok"),
                "download_status": item.get("download_status"),
                "generation_completed": item.get("generation_completed"),
                "first_frame_upload": item.get("first_frame_upload"),
            }
            for item in clip_results
        ],
        "final_video_path": final_video,
        "recovery_available": generation_status == STATUS_DOWNLOAD_FAILED_REPORT,
        "continuity_status": runtime_state.continuity_status,
        "chain_complete": runtime_state.chain_complete,
    }

    quality_pipeline: dict[str, Any] = {"skipped": True, "reason": "generation_failed"}
    if final_video and runtime_state.chain_complete:
        from content_brain.execution.kling_native_audio_models import KLING_AUDIO_STRATEGY
        from content_brain.quality.video_quality_judge import run_post_processing_quality_pipeline

        quality_pipeline = run_post_processing_quality_pipeline(
            project_root=root,
            run_dir=run_dir,
            run_id=run_id,
            video_path=final_video,
            topic=topic,
            clip_count=plan.clip_count,
            audio_strategy=KLING_AUDIO_STRATEGY,
        )

    return clip_results, generation_report, download_report, final_video, quality_pipeline, continuity_chain


__all__ = [
    "CONTINUITY_CHAIN_FILENAME",
    "RUNTIME_VERSION",
    "STATUS_CHAIN_AWAITING_APPROVAL",
    "STATUS_CHAIN_COMPLETE",
    "STATUS_CHAIN_IN_PROGRESS",
    "STATUS_CHAIN_STOPPED",
    "FrameUploadStatus",
    "KlingContinuityChainState",
    "clip_is_approved",
    "continuity_chain_v1_path",
    "merge_plan_chain_with_runtime",
    "record_upload_status",
    "run_kling_continuity_chain",
    "upload_frame_for_next_clip",
    "verify_upload_visible",
    "write_continuity_chain_files",
]
