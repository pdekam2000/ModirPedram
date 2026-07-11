"""Kling Native Audio — Product Studio generate orchestration and output package.

LEGACY PRODUCT EXECUTION: For Product Studio video generation, prefer
``provider_runtime=pwmap_agent`` via ``pwmap_runway_agent_adapter``.
This module remains available for diagnostics and internal live tests.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_continuity_runtime import run_kling_continuity_chain
from content_brain.execution.kling_frame_to_video_models import (
    KLING_FRAME_TO_VIDEO_MODE,
    KlingFrameToVideoPlan,
)
from content_brain.execution.kling_multishot_config import MULTISHOT_STRATEGY
from content_brain.execution.kling_multishot_live_engine import (
    ESTIMATED_CREDIT_RISK,
    OUTPUT_ROOT,
    STATUS_AWAITING_APPROVAL,
    STATUS_COMPLETED,
    STATUS_DOWNLOAD_FAILED,
    STATUS_FAILED,
    STATUS_PREPARED,
    KlingMultishotLiveResult,
    recover_kling_multishot_output,
    verify_recovered_mp4,
)
from content_brain.execution.kling_native_audio_models import (
    KLING_AUDIO_STRATEGY,
    KLING_CONTINUITY_CHAIN_VERSION,
    KLING_PROVIDER_ID,
    KlingNativeAudioPlan,
    build_continuity_chain_from_plan,
)

PRODUCT_RUN_VERSION = "kling_product_run_v1"
LEGACY_PRODUCT_EXECUTION = True
LEGACY_PRODUCT_EXECUTION_NOTE = (
    "Internal Kling live engines are legacy for Product Studio generation. "
    "Use content_brain.execution.pwmap_runway_agent_adapter with provider_runtime=pwmap_agent."
)
STATUS_DOWNLOAD_FAILED_REPORT = "download_failed"
PRODUCT_STUDIO_APPROVED_BY = "product_studio"


def create_kling_product_run_id(*, frame_mode: bool = False) -> str:
    if frame_mode:
        from content_brain.execution.kling_starter_frame_generator import create_kling_frame_run_id

        return create_kling_frame_run_id()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"kling_ms_{stamp}_{uuid.uuid4().hex[:8]}"


def kling_run_dir(project_root: str | Path, run_id: str) -> Path:
    root = Path(project_root).resolve()
    parent = str(resolve_kling_parent_run_id(run_id))
    if parent.startswith("kling_ft_"):
        from content_brain.execution.kling_starter_frame_generator import kling_frame_run_dir

        return kling_frame_run_dir(root, parent)
    return root / "outputs" / "kling_multishot_live" / parent


def resolve_kling_parent_run_id(run_id: str) -> str:
    text = str(run_id or "").strip()
    if "_c" in text:
        base, suffix = text.rsplit("_c", 1)
        if suffix.isdigit():
            return base
    return text


def kling_clip_dir(run_dir: Path, clip_index: int) -> Path:
    path = run_dir / "clips" / f"c{clip_index}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_sibling_run_dir(project_root: str | Path, run_id: str, clip_index: int) -> Path:
    root = Path(project_root).resolve()
    parent_run_id = resolve_kling_parent_run_id(run_id)
    return root / "outputs" / "kling_multishot_live" / f"{parent_run_id}_c{clip_index}"


def _record_legacy_sibling(*, clip_dir: Path, legacy_dir: Path) -> None:
    if not legacy_dir.is_dir() or legacy_dir.resolve() == clip_dir.resolve():
        return
    payload = {
        "status": "legacy_partial",
        "legacy_run_dir": str(legacy_dir.resolve()).replace("\\", "/"),
        "canonical_clip_dir": str(clip_dir.resolve()).replace("\\", "/"),
        "note": "Legacy sibling run folder retained for recovery; canonical clip output lives under parent/clips/.",
    }
    (clip_dir / "legacy_sibling_run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _clip_generation_completed(payload: dict[str, Any]) -> bool:
    if payload.get("generation_completed"):
        return True
    return any(
        str(step.get("label") or "") == "generation_wait" and str(step.get("status") or "") == "passed"
        for step in payload.get("steps") or []
        if isinstance(step, dict)
    )


def _clip_download_failed(payload: dict[str, Any]) -> bool:
    if payload.get("download_status") == "failed" or payload.get("status") == STATUS_DOWNLOAD_FAILED:
        return True
    if _clip_generation_completed(payload) and not str(payload.get("download_path") or "").strip():
        return True
    return any(
        str(step.get("label") or "") == "download" and str(step.get("status") or "") == "failed"
        for step in payload.get("steps") or []
        if isinstance(step, dict)
    )


def _summarize_generation_status(clip_results: list[dict[str, Any]], *, final_video: str) -> str:
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


def _kling_approval_complete(payload: dict[str, Any]) -> bool:
    return (
        bool(payload.get("approve_generate"))
        and bool(str(payload.get("approved_by") or "").strip())
        and bool(payload.get("confirm_credit_spend"))
    )


def _kling_awaiting_approval_response(
    base_response: dict[str, Any],
    *,
    approved_by: str = "",
    message: str = "",
) -> dict[str, Any]:
    base_response.update(
        {
            "ok": True,
            "status": STATUS_AWAITING_APPROVAL,
            "message": message
            or "Kling Native Audio run prepared. Operator approval required before credit spend.",
            "approval_required": True,
            "generate_clicked": False,
            "credits_spent": False,
            "native_audio_status": "planned",
            "approved_by": approved_by,
        }
    )
    return base_response


def _resolve_kling_execution_outcome(
    *,
    ok: bool,
    clip_results: list[dict[str, Any]],
    generation_report: dict[str, Any],
    continuity_chain: dict[str, Any],
    approval_complete: bool,
) -> tuple[str, str, bool]:
    """Return (status, native_audio_status, approval_required)."""
    generate_attempted = any(bool(item.get("generate_clicked")) for item in clip_results)
    generation_status = str(generation_report.get("status") or STATUS_FAILED)
    continuity_status = str(continuity_chain.get("continuity_status") or "")

    if ok:
        return STATUS_COMPLETED, "completed", False

    if continuity_status == "awaiting_approval":
        return STATUS_AWAITING_APPROVAL, "planned", True

    if not approval_complete:
        return STATUS_AWAITING_APPROVAL, "planned", True

    if not generate_attempted:
        blocked_status = (
            generation_status
            if generation_status in {STATUS_AWAITING_APPROVAL, STATUS_PREPARED}
            else STATUS_PREPARED
        )
        return blocked_status, "planned", False

    if generation_status == STATUS_DOWNLOAD_FAILED_REPORT:
        return STATUS_DOWNLOAD_FAILED, "download_failed", False

    return STATUS_FAILED, "failed", False


def build_approval_summary(*, preflight: dict[str, Any]) -> dict[str, Any]:
    duration_plan = dict(preflight.get("duration_plan") or {})
    kling_duration = dict(preflight.get("kling_duration_plan") or {})
    return {
        "provider": str(preflight.get("provider") or KLING_PROVIDER_ID),
        "audio_strategy": str(preflight.get("audio_strategy") or KLING_AUDIO_STRATEGY),
        "planned_duration_seconds": int(
            kling_duration.get("planned_duration_seconds")
            or duration_plan.get("duration_seconds")
            or preflight.get("kling_clip_count", 1) * 15
        ),
        "clip_count": int(preflight.get("kling_clip_count") or duration_plan.get("clip_count") or 1),
        "shot_mode": str(preflight.get("kling_shot_mode") or MULTISHOT_STRATEGY),
        "estimated_credit_risk": ESTIMATED_CREDIT_RISK,
        "native_audio_required": bool(preflight.get("native_audio_required", True)),
        "use_elevenlabs": bool(preflight.get("use_elevenlabs", False)),
        "use_external_music": bool(preflight.get("use_external_music", False)),
        "confirmation_required": True,
    }


def write_kling_output_package(
    run_dir: Path,
    *,
    run_id: str,
    preflight: dict[str, Any],
    approval: dict[str, Any] | None = None,
    continuity_chain: dict[str, Any] | None = None,
    generation_report: dict[str, Any] | None = None,
    download_report: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "preflight.json").write_text(json.dumps(preflight, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "approval.json").write_text(
        json.dumps(
            approval
            or {
                "status": "pending",
                "approved_by": "",
                "confirm_credit_spend": False,
                "approval_summary": build_approval_summary(preflight=preflight),
            },
            indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if continuity_chain is not None:
        (run_dir / "continuity_chain.json").write_text(json.dumps(continuity_chain, indent=2, ensure_ascii=False), encoding="utf-8")
    if generation_report is not None:
        (run_dir / "generation_report.json").write_text(json.dumps(generation_report, indent=2, ensure_ascii=False), encoding="utf-8")
    if download_report is not None:
        (run_dir / "download_report.json").write_text(json.dumps(download_report, indent=2, ensure_ascii=False), encoding="utf-8")

    meta = dict(metadata or {})
    meta.setdefault("run_id", run_id)
    meta.setdefault("provider", KLING_PROVIDER_ID)
    meta.setdefault("audio_strategy", KLING_AUDIO_STRATEGY)
    meta.setdefault("shot_mode", preflight.get("kling_shot_mode") or MULTISHOT_STRATEGY)
    meta.setdefault("clip_count", preflight.get("kling_clip_count"))
    meta.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _resolve_plan(preflight: dict[str, Any]) -> KlingNativeAudioPlan | None:
    raw = dict(preflight.get("kling_native_audio_plan") or {})
    if not raw:
        return None
    return KlingNativeAudioPlan.from_dict(raw)


def _resolve_frame_plan(preflight: dict[str, Any]) -> KlingFrameToVideoPlan | None:
    raw = dict(preflight.get("kling_frame_to_video_plan") or {})
    if not raw:
        return None
    return KlingFrameToVideoPlan.from_dict(raw)


def _uses_frame_to_video(preflight: dict[str, Any]) -> bool:
    shot_mode = str(preflight.get("kling_shot_mode") or "")
    return shot_mode == KLING_FRAME_TO_VIDEO_MODE or bool(preflight.get("kling_frame_to_video_plan"))


def ensure_kling_starter_frame_path(
    *,
    project_root: str | Path,
    run_id: str,
    run_dir: Path,
    preflight: dict[str, Any],
    first_frame_path: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Ensure clip-1 starter frame exists; generate locally when missing (no credits)."""
    from content_brain.execution.kling_starter_frame_generator import (
        generate_kling_starter_frame,
        starter_frame_path,
    )

    explicit = str(first_frame_path or "").strip()
    if explicit and Path(explicit).is_file():
        return explicit, {"status": "existing", "starter_frame_path": explicit}

    existing = starter_frame_path(run_dir)
    if existing.is_file():
        resolved = str(existing.resolve()).replace("\\", "/")
        return resolved, {"status": "existing", "starter_frame_path": resolved}

    topic = str(preflight.get("authoritative_topic") or "").strip()
    if not topic:
        return None, {"status": "failed", "error": "authoritative_topic required for starter frame"}

    result = generate_kling_starter_frame(
        topic=topic,
        project_root=project_root,
        run_id=run_id,
        story_summary=topic,
        mood=str(preflight.get("style") or "cinematic"),
        style=str(preflight.get("style") or "cinematic"),
    )
    report = result.to_dict()
    (run_dir / "starter_frame_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if result.ok and result.starter_frame_path:
        return result.starter_frame_path, report
    return None, report


def _clip_output_dir(run_dir: Path, clip_index: int) -> Path:
    return kling_clip_dir(run_dir, clip_index)


def _execute_kling_clips(
    *,
    project_root: Path,
    run_id: str,
    run_dir: Path,
    plan: KlingNativeAudioPlan | None,
    approved_by: str,
    confirm_credit_spend: bool,
    first_frame_path: str | None,
    cdp_url: str,
    topic: str = "",
    payload: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    preflight = dict(preflight or {})
    frame_plan = _resolve_frame_plan(preflight)
    if _uses_frame_to_video(preflight) and frame_plan is not None:
        from content_brain.execution.kling_frame_continuity_runtime import run_kling_frame_continuity_chain

        return run_kling_frame_continuity_chain(
            project_root=project_root,
            run_id=run_id,
            run_dir=run_dir,
            plan=frame_plan,
            approved_by=approved_by,
            confirm_credit_spend=confirm_credit_spend,
            starter_frame_path=first_frame_path,
            cdp_url=cdp_url,
            payload={**dict(payload or {}), "_preflight": dict(preflight or {})},
        )
    if plan is None:
        raise ValueError("multishot plan required when not using frame-to-video route")
    clip_results, generation_report, download_report, final_video, quality_pipeline, continuity_chain = (
        run_kling_continuity_chain(
            project_root=project_root,
            run_id=run_id,
            run_dir=run_dir,
            plan=plan,
            approved_by=approved_by,
            confirm_credit_spend=confirm_credit_spend,
            first_frame_path=first_frame_path,
            cdp_url=cdp_url,
            payload=dict(payload or {}),
            topic=topic,
        )
    )
    return clip_results, generation_report, download_report, final_video, quality_pipeline, continuity_chain


def run_kling_product_studio_generate(
    *,
    project_root: str | Path,
    payload: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    """Route Product Studio Generate to Kling Native Audio workflow."""
    root = Path(project_root).resolve()
    run_id = str(payload.get("run_id") or create_kling_product_run_id(frame_mode=_uses_frame_to_video(preflight)))
    run_dir = kling_run_dir(root, run_id)
    plan = _resolve_plan(preflight)
    frame_plan = _resolve_frame_plan(preflight)
    approval_summary = build_approval_summary(preflight=preflight)
    continuity_chain = (
        build_continuity_chain_from_plan(plan, run_id=run_id).to_dict()
        if plan
        else {"version": KLING_CONTINUITY_CHAIN_VERSION, "run_id": run_id, "clip_count": 0, "links": []}
    )

    write_kling_output_package(
        run_dir,
        run_id=run_id,
        preflight=preflight,
        continuity_chain=continuity_chain,
        metadata={
            "topic": preflight.get("authoritative_topic") or "",
            "platform": preflight.get("platform") or "",
            "native_audio_status": "planned",
        },
    )

    approve_generate = bool(payload.get("approve_generate"))
    approved_by = str(payload.get("approved_by") or "").strip()
    confirm_credit_spend = bool(payload.get("confirm_credit_spend"))

    from content_brain.execution.credit_safety_guard import (
        attach_credit_safety_to_report,
        evaluate_credit_safety,
    )

    credit_decision = evaluate_credit_safety(
        payload=payload,
        preflight=preflight,
        provider=KLING_PROVIDER_ID,
        dry_run=bool(payload.get("dry_run")),
        operator_paid_approval=_kling_approval_complete(payload),
    )
    if credit_decision.blocked and not bool(payload.get("dry_run")):
        blocked = {
            "ok": False,
            "wired": True,
            "status": "paid_credit_blocked",
            "message": credit_decision.block_reason,
            "run_id": run_id,
            "provider": KLING_PROVIDER_ID,
            "approval_required": True,
            "credits_spent": False,
        }
        return attach_credit_safety_to_report(blocked, credit_decision)

    base_response: dict[str, Any] = {
        "ok": True,
        "wired": True,
        "provider": KLING_PROVIDER_ID,
        "audio_strategy": KLING_AUDIO_STRATEGY,
        "run_id": run_id,
        "session_id": run_id,
        "project_id": run_id,
        "authoritative_topic": str(preflight.get("authoritative_topic") or ""),
        "clip_count": int(preflight.get("kling_clip_count") or 1),
        "kling_clip_count": int(preflight.get("kling_clip_count") or 1),
        "kling_shot_mode": str(preflight.get("kling_shot_mode") or MULTISHOT_STRATEGY),
        "duration_plan": preflight.get("duration_plan") or {},
        "pipeline_steps": preflight.get("pipeline_steps") or [],
        "output_folder": str(run_dir.resolve()).replace("\\", "/"),
        "kling_output_package": {
            "run_id": run_id,
            "output_folder": str(run_dir.resolve()).replace("\\", "/"),
            "preflight_path": str((run_dir / "preflight.json").resolve()).replace("\\", "/"),
            "continuity_chain_path": str((run_dir / "continuity_chain.json").resolve()).replace("\\", "/"),
        },
        "approval_summary": approval_summary,
        "native_audio_required": True,
        "use_elevenlabs": False,
        "use_external_music": False,
        "preflight_mode": "preview_only",
    }
    base_response = attach_credit_safety_to_report(base_response, credit_decision)

    approval_payload = {
        "approve_generate": approve_generate,
        "approved_by": approved_by,
        "confirm_credit_spend": confirm_credit_spend,
    }
    if not _kling_approval_complete(approval_payload):
        partial = approve_generate or approved_by or confirm_credit_spend
        return _kling_awaiting_approval_response(
            base_response,
            approved_by=approved_by,
            message=(
                "Kling Native Audio requires approve_generate, approved_by, and confirm_credit_spend."
                if partial
                else "Kling Native Audio run prepared. Operator approval required before credit spend."
            ),
        )

    if _uses_frame_to_video(preflight):
        if frame_plan is None or not frame_plan.clips:
            return {
                **base_response,
                "ok": False,
                "status": STATUS_FAILED,
                "message": "Kling frame-to-video plan missing from preflight.",
            }
        from content_brain.execution.kling_frame_to_video_planner import validate_kling_frame_content_plan
        from content_brain.story.story_first_prompt_engine import audit_kling_frame_plan_prompts

        content_ok, content_errors = validate_kling_frame_content_plan(frame_plan)
        story_audits = audit_kling_frame_plan_prompts(frame_plan)
        base_response["story_first_audits"] = story_audits
        if not content_ok:
            return {
                **base_response,
                "ok": False,
                "status": STATUS_FAILED,
                "message": "; ".join(content_errors[:8]),
                "story_first_audits": story_audits,
            }
    elif plan is None or not plan.clips:
        return {
            **base_response,
            "ok": False,
            "status": STATUS_FAILED,
            "message": "Kling native audio plan missing from preflight.",
        }

    cdp_url = str(payload.get("cdp_url") or "http://127.0.0.1:9222")
    first_frame_path = str(payload.get("first_frame_path") or "").strip() or None
    if _uses_frame_to_video(preflight):
        # Clip 1 = text-to-video (prompt only). Clip 2+ = Use Frame continuity.
        # Never auto-generate placeholder starter PNGs for Product Studio.
        if first_frame_path and not Path(first_frame_path).is_file():
            first_frame_path = None
        frame_plan = _resolve_frame_plan(preflight)
        if frame_plan is not None and frame_plan.clips:
            frame_plan.clips[0].first_frame_path = ""
            frame_plan.clips[0].first_frame_source = "prompt_only"
    runtime_payload = dict(payload)
    if not str(runtime_payload.get("aspect_ratio") or "").strip():
        runtime_payload["aspect_ratio"] = str(preflight.get("aspect_ratio") or "9:16")
    clip_results, generation_report, download_report, final_video, quality_pipeline, continuity_chain = _execute_kling_clips(
        project_root=root,
        run_id=run_id,
        run_dir=run_dir,
        plan=plan,
        approved_by=approved_by,
        confirm_credit_spend=confirm_credit_spend,
        first_frame_path=first_frame_path,
        cdp_url=cdp_url,
        topic=str(preflight.get("authoritative_topic") or ""),
        payload=runtime_payload,
        preflight=preflight,
    )

    ok = bool(final_video)
    generation_status = str(generation_report.get("status") or STATUS_FAILED)
    resolved_status, native_status, approval_required = _resolve_kling_execution_outcome(
        ok=ok,
        clip_results=clip_results,
        generation_report=generation_report,
        continuity_chain=continuity_chain,
        approval_complete=_kling_approval_complete(approval_payload),
    )
    use_frame_chain = dict(continuity_chain.get("use_frame_chain") or generation_report.get("use_frame_chain") or {})
    resolved_clip_count = (
        frame_plan.clip_count
        if _uses_frame_to_video(preflight) and frame_plan is not None
        else (plan.clip_count if plan is not None else int(preflight.get("kling_clip_count") or 1))
    )
    resolved_shot_mode = (
        KLING_FRAME_TO_VIDEO_MODE if _uses_frame_to_video(preflight) else str(plan.strategy if plan else MULTISHOT_STRATEGY)
    )
    write_kling_output_package(
        run_dir,
        run_id=run_id,
        preflight=preflight,
        approval={
            "status": "approved" if _kling_approval_complete(approval_payload) else "pending",
            "approved_by": approved_by,
            "confirm_credit_spend": confirm_credit_spend,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approval_summary": approval_summary,
            "execution_status": resolved_status,
        },
        continuity_chain=continuity_chain,
        generation_report=generation_report,
        download_report=download_report,
        metadata={
            "topic": preflight.get("authoritative_topic") or "",
            "platform": preflight.get("platform") or "",
            "provider": KLING_PROVIDER_ID,
            "audio_strategy": KLING_AUDIO_STRATEGY,
            "native_audio_status": native_status,
            "clip_count": resolved_clip_count,
            "shot_mode": resolved_shot_mode,
            "continuity_method": use_frame_chain.get("continuity_method") or download_report.get("continuity_method"),
            "fallback_used": use_frame_chain.get("fallback_used", download_report.get("fallback_used")),
            "story_progression_status": use_frame_chain.get("story_progression_status")
            or download_report.get("story_progression_status"),
            "story_progression": dict(
                (frame_plan.story_progression if frame_plan else {})
                or continuity_chain.get("story_progression")
                or {}
            ),
            "download_path": final_video,
            "generation_time_seconds": generation_report.get("generation_time_seconds"),
            "approved_by": approved_by,
            "output_ready": bool(final_video),
            "recovery_available": bool(generation_report.get("recovery_available")),
            "generation_status": generation_status,
            "continuity_status": generation_report.get("continuity_status") or continuity_chain.get("continuity_status"),
            "frames_extracted_count": generation_report.get("frames_extracted_count")
            or continuity_chain.get("frames_extracted_count"),
            "frames_uploaded_count": generation_report.get("frames_uploaded_count")
            or continuity_chain.get("frames_uploaded_count"),
            "chain_complete": bool(generation_report.get("chain_complete") or continuity_chain.get("chain_complete")),
        },
    )

    base_response.update(
        {
            "ok": ok or resolved_status in {STATUS_AWAITING_APPROVAL, STATUS_PREPARED},
            "status": resolved_status,
            "message": (
                "Kling Native Audio generation completed."
                if ok
                else (
                    "Kling generation completed but MP4 download failed. Recovery available."
                    if native_status == "download_failed"
                    else (
                        f"Kling continuity chain paused: {continuity_chain.get('stop_reason') or generation_status}"
                        if resolved_status == STATUS_AWAITING_APPROVAL
                        else (
                            str(generation_report.get("precondition_message") or generation_report.get("precondition") or "").replace("_", " ").strip()
                            or "Kling run prepared — live Generate not started yet."
                            if resolved_status == STATUS_PREPARED
                            else "Kling Native Audio generation failed."
                        )
                    )
                )
            ),
            "approval_required": approval_required,
            "approved_by": approved_by,
            "generate_clicked": any(bool(item.get("generate_clicked")) for item in clip_results),
            "credits_spent": any(bool(item.get("credits_spent")) for item in clip_results),
            "download_path": final_video,
            "video_path": final_video,
            "output_ready": bool(final_video),
            "recovery_available": bool(generation_report.get("recovery_available")),
            "generation_status": generation_status,
            "generation_report": generation_report,
            "download_report": download_report,
            "continuity_chain": continuity_chain,
            "clip_results": clip_results,
            "native_audio_status": native_status,
            "video_quality_judge": dict(quality_pipeline.get("judge") or {}),
            "video_quality_judge_path": str(quality_pipeline.get("video_quality_judge_path") or ""),
            "video_quality_learning_proposed": bool(quality_pipeline.get("proposed_updates_path")),
            "video_quality_proposed_updates_path": str(quality_pipeline.get("proposed_updates_path") or ""),
            "continuity_status": continuity_chain.get("continuity_status"),
            "frames_extracted_count": continuity_chain.get("frames_extracted_count"),
            "frames_uploaded_count": continuity_chain.get("frames_uploaded_count"),
            "chain_complete": continuity_chain.get("chain_complete"),
        }
    )
    return base_response


def recover_kling_product_run(
    *,
    project_root: str | Path,
    run_id: str,
    clip_index: int = 1,
    cdp_url: str = "http://127.0.0.1:9222",
) -> dict[str, Any]:
    """Recover/download an already-generated clip output without spending new credits."""
    root = Path(project_root).resolve()
    parent_run_id = resolve_kling_parent_run_id(run_id)
    run_dir = kling_run_dir(root, parent_run_id)
    if not run_dir.is_dir():
        return {"ok": False, "status": STATUS_FAILED, "message": f"Run folder not found: {run_dir}"}

    clip_dir = kling_clip_dir(run_dir, clip_index)
    legacy_dir = legacy_sibling_run_dir(root, parent_run_id, clip_index)
    _record_legacy_sibling(clip_dir=clip_dir, legacy_dir=legacy_dir)

    live = recover_kling_multishot_output(
        run_id=parent_run_id,
        output_dir=clip_dir,
        cdp_url=cdp_url,
        clip_index=clip_index,
    )
    payload = live.to_dict()
    payload["clip_index"] = clip_index
    payload["clip_dir"] = str(clip_dir.resolve()).replace("\\", "/")
    (clip_dir / "live_run_result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    final_video = ""
    if live.download_path:
        src = Path(live.download_path)
        dest = clip_dir / "video.mp4"
        if src.is_file():
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            final_video = str(dest.resolve())

    verify = verify_recovered_mp4(final_video) if final_video else {"is_real_mp4": False}
    if final_video and not verify.get("is_real_mp4"):
        final_video = ""

    preflight = _read_json(run_dir / "preflight.json")
    generation_report = _read_json(run_dir / "generation_report.json")
    download_report = _read_json(run_dir / "download_report.json")
    clip_results = list(generation_report.get("clip_results") or [])
    updated = False
    for item in clip_results:
        if int(item.get("clip_index") or 0) == clip_index:
            item.update(payload)
            updated = True
            break
    if not updated:
        clip_results.append(payload)

    generation_status = _summarize_generation_status(clip_results, final_video=final_video)
    generation_report.update(
        {
            "run_id": parent_run_id,
            "status": generation_status,
            "clip_results": clip_results,
            "recovery_available": generation_status == STATUS_DOWNLOAD_FAILED_REPORT,
            "output_ready": bool(final_video),
            "recovered_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    download_report.update(
        {
            "run_id": parent_run_id,
            "status": "completed" if final_video else "failed",
            "downloads": [
                {
                    "clip_index": item.get("clip_index"),
                    "download_path": item.get("download_path"),
                    "output_path": item.get("output_path"),
                    "clip_dir": item.get("clip_dir"),
                    "ok": item.get("ok"),
                    "download_status": item.get("download_status"),
                    "generation_completed": item.get("generation_completed"),
                    "recovery_mode": item.get("recovery_mode"),
                }
                for item in clip_results
            ],
            "final_video_path": final_video,
            "recovery_available": generation_status == STATUS_DOWNLOAD_FAILED_REPORT,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if final_video:
        root_video = run_dir / "video.mp4"
        shutil.copy2(final_video, root_video)
        final_video = str(root_video.resolve())

    metadata = _read_json(run_dir / "metadata.json")
    native_status = "completed" if final_video else ("download_failed" if generation_status == STATUS_DOWNLOAD_FAILED_REPORT else "failed")
    metadata.update(
        {
            "run_id": parent_run_id,
            "native_audio_status": native_status,
            "download_path": final_video,
            "output_ready": bool(final_video),
            "recovery_available": generation_status == STATUS_DOWNLOAD_FAILED_REPORT,
            "generation_status": generation_status,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_kling_output_package(
        run_dir,
        run_id=parent_run_id,
        preflight=preflight,
        approval=_read_json(run_dir / "approval.json"),
        continuity_chain=_read_json(run_dir / "continuity_chain.json"),
        generation_report=generation_report,
        download_report=download_report,
        metadata=metadata,
    )

    return {
        "ok": bool(final_video),
        "status": STATUS_COMPLETED if final_video else STATUS_DOWNLOAD_FAILED,
        "run_id": parent_run_id,
        "clip_index": clip_index,
        "recovery_mode": True,
        "generate_clicked": False,
        "credits_spent": False,
        "video_path": final_video,
        "download_path": final_video,
        "output_ready": bool(final_video),
        "recovery_available": generation_status == STATUS_DOWNLOAD_FAILED_REPORT,
        "generation_status": generation_status,
        "native_audio_status": native_status,
        "clip_result": payload,
        "mp4_verify": verify,
        "generation_report": generation_report,
        "download_report": download_report,
        "message": "Recovered Kling output." if final_video else "Recovery attempted but MP4 still missing.",
    }


def load_kling_product_run_results(project_root: str | Path, *, run_id: str = "") -> dict[str, Any] | None:
    root = Path(project_root).resolve()
    run_id_text = resolve_kling_parent_run_id(str(run_id or "").strip())
    if not run_id_text:
        for output_name in ("kling_frame_to_video", "kling_multishot_live"):
            kling_root = root / "outputs" / output_name
            if not kling_root.is_dir():
                continue
            candidates = sorted(
                [
                    path
                    for path in kling_root.iterdir()
                    if path.is_dir() and not re.search(r"_c\d+$", path.name)
                ],
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                run_dir = candidates[0]
                run_id_text = resolve_kling_parent_run_id(run_dir.name)
                break
        else:
            return None
    else:
        run_dir = kling_run_dir(root, run_id_text)
        if not run_dir.is_dir():
            legacy_parent = resolve_kling_parent_run_id(run_id_text)
            if legacy_parent != run_id_text:
                run_dir = kling_run_dir(root, legacy_parent)
        if not run_dir.is_dir():
            return None

    metadata = _read_json(run_dir / "metadata.json")
    preflight = _read_json(run_dir / "preflight.json")
    approval = _read_json(run_dir / "approval.json")
    continuity = _read_json(run_dir / "continuity_chain.json")
    if not continuity:
        continuity = _read_json(run_dir / "continuity" / "continuity_chain_v1.json")
    use_frame_chain = _read_json(run_dir / "use_frame_chain.json")
    if not use_frame_chain:
        use_frame_chain = _read_json(run_dir / "continuity" / "use_frame_chain.json")
    generation_report = _read_json(run_dir / "generation_report.json")
    download_report = _read_json(run_dir / "download_report.json")
    video_path = str((run_dir / "video.mp4").resolve()) if (run_dir / "video.mp4").is_file() else str(
        metadata.get("download_path") or download_report.get("final_video_path") or ""
    )
    if not video_path:
        clip_glob = sorted((run_dir / "clips").glob("c*/video.mp4")) if (run_dir / "clips").is_dir() else []
        if clip_glob:
            video_path = str(clip_glob[-1].resolve())

    legacy_folders: list[str] = []
    clip_count = int(metadata.get("clip_count") or preflight.get("kling_clip_count") or 0)
    for clip_index in range(1, max(clip_count, 1) + 1):
        legacy_dir = legacy_sibling_run_dir(root, run_id_text, clip_index)
        if legacy_dir.is_dir() and legacy_dir.resolve() != (run_dir / "clips" / f"c{clip_index}").resolve():
            legacy_folders.append(str(legacy_dir.resolve()).replace("\\", "/"))

    generation_status = str(
        metadata.get("generation_status")
        or generation_report.get("status")
        or ("completed" if video_path else "unknown")
    )
    output_ready = bool(video_path) or bool(metadata.get("output_ready"))
    recovery_available = bool(
        metadata.get("recovery_available")
        if metadata.get("recovery_available") is not None
        else generation_status == STATUS_DOWNLOAD_FAILED_REPORT
    )
    video_quality_judge = _read_json(run_dir / "quality" / "video_quality_judge.json")
    video_quality_judge_p1 = _read_json(run_dir / "quality" / "video_quality_judge_p1.json")
    proposed_updates_path = root / "project_brain" / "quality_learning" / "proposed_updates" / f"{run_id_text}.json"
    proposed_updates_p1_path = root / "project_brain" / "quality_learning" / "proposed_updates_p1" / f"{run_id_text}.json"

    continuity_status = str(
        continuity.get("continuity_status")
        or metadata.get("continuity_status")
        or ("ready" if continuity.get("links") else "pending")
    )
    frames_extracted_count = int(
        continuity.get("frames_extracted_count")
        or len(list(continuity.get("frames_extracted") or []))
    )
    frames_uploaded_count = int(
        continuity.get("frames_uploaded_count")
        or len(list(continuity.get("frames_uploaded") or []))
    )
    chain_complete = bool(
        continuity.get("chain_complete")
        if continuity.get("chain_complete") is not None
        else metadata.get("chain_complete")
    )

    return {
        "found": True,
        "provider_used": metadata.get("provider") or KLING_PROVIDER_ID,
        "audio_strategy_used": metadata.get("audio_strategy") or preflight.get("audio_strategy") or KLING_AUDIO_STRATEGY,
        "native_audio_status": metadata.get("native_audio_status") or "unknown",
        "generation_status": generation_status,
        "output_ready": output_ready,
        "recovery_available": recovery_available,
        "legacy_run_folders": legacy_folders,
        "clip_count": clip_count,
        "shot_mode": metadata.get("shot_mode") or preflight.get("kling_shot_mode") or MULTISHOT_STRATEGY,
        "continuity_status": continuity_status,
        "frames_extracted_count": frames_extracted_count,
        "frames_uploaded_count": frames_uploaded_count,
        "chain_complete": chain_complete,
        "output_folder": str(run_dir.resolve()).replace("\\", "/"),
        "download_path": video_path,
        "video_path": video_path,
        "generation_time_seconds": metadata.get("generation_time_seconds") or generation_report.get(
            "generation_time_seconds"
        ),
        "approval_information": approval,
        "continuity_chain": continuity,
        "use_frame_chain": use_frame_chain,
        "continuity_method": str(
            use_frame_chain.get("continuity_method")
            or continuity.get("use_frame_chain", {}).get("continuity_method")
            or metadata.get("continuity_method")
            or ""
        ),
        "use_frame_status": str(
            use_frame_chain.get("story_progression_status")
            or continuity.get("use_frame_chain", {}).get("story_progression_status")
            or ""
        ),
        "fallback_used": bool(
            use_frame_chain.get("fallback_used")
            if use_frame_chain.get("fallback_used") is not None
            else metadata.get("fallback_used")
        ),
        "story_progression_status": str(
            use_frame_chain.get("story_progression_status")
            or metadata.get("story_progression_status")
            or ""
        ),
        "story_progression": dict(
            preflight.get("story_progression")
            or (preflight.get("kling_frame_to_video_plan") or {}).get("story_progression")
            or metadata.get("story_progression")
            or {}
        ),
        "kling_clip_prompts": list(preflight.get("kling_clip_prompts") or []),
        "metadata": metadata,
        "preflight": preflight,
        "generation_report": generation_report,
        "download_report": download_report,
        "selected_run_id": run_id_text,
        "run_folder": str(run_dir.resolve()).replace("\\", "/"),
        "run_dir": str(run_dir.resolve()).replace("\\", "/"),
        "topic": str(metadata.get("topic") or preflight.get("authoritative_topic") or ""),
        "video_quality_judge": video_quality_judge,
        "video_quality_judge_p1": video_quality_judge_p1,
        "video_quality_learning_proposed": proposed_updates_path.is_file(),
        "video_quality_proposed_updates_path": str(proposed_updates_path.resolve()).replace("\\", "/")
        if proposed_updates_path.is_file()
        else "",
        "video_quality_learning_p1_proposed": proposed_updates_p1_path.is_file(),
        "video_quality_proposed_updates_p1_path": str(proposed_updates_p1_path.resolve()).replace("\\", "/")
        if proposed_updates_p1_path.is_file()
        else "",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = [
    "PRODUCT_RUN_VERSION",
    "STATUS_DOWNLOAD_FAILED_REPORT",
    "build_approval_summary",
    "create_kling_product_run_id",
    "kling_clip_dir",
    "kling_run_dir",
    "legacy_sibling_run_dir",
    "load_kling_product_run_results",
    "recover_kling_product_run",
    "resolve_kling_parent_run_id",
    "ensure_kling_starter_frame_path",
    "PRODUCT_STUDIO_APPROVED_BY",
    "run_kling_product_studio_generate",
    "write_kling_output_package",
]
