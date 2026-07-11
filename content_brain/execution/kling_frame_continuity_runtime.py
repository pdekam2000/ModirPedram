"""Kling Frame-to-Video continuity chain — Generate, recover, Use Frame, next clip."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_continuity_runtime import (
    KlingContinuityChainState,
    STATUS_CHAIN_AWAITING_APPROVAL,
    STATUS_CHAIN_COMPLETE,
    STATUS_CHAIN_STOPPED,
    STATUS_DOWNLOAD_FAILED_REPORT,
    clip_is_approved,
    write_continuity_chain_files,
)
from content_brain.execution.kling_frame_to_video_live_engine import (
    DEFAULT_CDP_URL,
    recover_kling_frame_output,
    run_kling_frame_to_video_live,
)
from content_brain.execution.kling_frame_to_video_models import (
    KLING_FRAME_TO_VIDEO_MODE,
    KlingFrameToVideoPlan,
)
from content_brain.execution.kling_multishot_live_engine import (
    STATUS_COMPLETED,
    STATUS_DOWNLOAD_FAILED,
    STATUS_FAILED,
    STATUS_PREPARED,
    verify_recovered_mp4,
)
from content_brain.execution.kling_starter_frame_generator import kling_frame_clip_dir
from content_brain.execution.kling_use_frame_runtime import (
    CONTINUITY_METHOD_USE_FRAME,
    UseFrameChainState,
    apply_continuity_for_next_clip,
    finalize_story_progression,
    load_use_frame_chain,
    record_clip_continuity_metadata,
    story_chapter_for_clip,
    write_use_frame_chain,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH


RUNTIME_VERSION = "kling_frame_continuity_runtime_v2"
CLIP_GENERATION_STATUS_COMPLETED = "completed"
CLIP_GENERATION_STATUS_FAILED = "failed"


def _clip_dir(run_dir: Path, clip_index: int) -> Path:
    return kling_frame_clip_dir(run_dir, clip_index)


def _resolve_clip_video(clip_dir: Path) -> str:
    canonical = clip_dir / "video.mp4"
    if canonical.is_file():
        return str(canonical.resolve())
    live = clip_dir / "live_run_result.json"
    if live.is_file():
        try:
            payload = json.loads(live.read_text(encoding="utf-8"))
            path = str(payload.get("clip_output_path") or payload.get("output_path") or "").strip()
            if path and Path(path).is_file():
                return str(Path(path).resolve())
        except (OSError, json.JSONDecodeError):
            pass
    return ""


def _resolve_approved_clips(payload: dict[str, Any], plan: KlingFrameToVideoPlan) -> set[int]:
    raw = payload.get("approved_clips")
    if isinstance(raw, list) and raw:
        return {int(x) for x in raw if str(x).strip().isdigit() or isinstance(x, int)}
    if payload.get("approve_all_clips"):
        return set(range(1, plan.clip_count + 1))
    if payload.get("approve_generate"):
        return {1}
    return set()


def _merge_live_payload(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(incoming)
    for key in ("story_chapter", "clip_index", "clip_dir", "frame_prompt", "locator_strategies", "steps", "screenshots"):
        if base.get(key) and not merged.get(key):
            merged[key] = base[key]
        elif key == "steps" and base.get(key):
            merged["prior_live_steps"] = list(base.get("steps") or [])
    if base.get("story_chapter"):
        merged["story_chapter"] = base["story_chapter"]
    if base.get("clip_dir"):
        merged["clip_dir"] = base["clip_dir"]
    if _clip_generation_success(base) and incoming.get("recovery_mode"):
        merged["generation_completed"] = True
        merged["ok"] = True
        if base.get("status") == STATUS_COMPLETED:
            merged["status"] = STATUS_COMPLETED
    return merged


def _quarantine_invalid_mp4(path: str | Path, clip_dir: Path) -> str:
    src = Path(path)
    if not src.is_file():
        return ""
    quarantine_dir = clip_dir / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest = quarantine_dir / f"invalid_{stamp}_{src.name}"
    try:
        if src.resolve() != dest.resolve():
            shutil.move(str(src), str(dest))
    except OSError:
        try:
            shutil.copy2(src, dest)
            src.unlink(missing_ok=True)
        except OSError:
            return ""
    canonical = clip_dir / "video.mp4"
    if canonical.is_file() and not verify_recovered_mp4(canonical).get("is_real_mp4"):
        try:
            shutil.move(str(canonical), str(quarantine_dir / f"invalid_{stamp}_video.mp4"))
        except OSError:
            canonical.unlink(missing_ok=True)
    return str(dest.resolve()).replace("\\", "/")


def _clip_generation_success(live_payload: dict[str, Any]) -> bool:
    if live_payload.get("generation_completed"):
        return True
    for step in live_payload.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if str(step.get("label") or "") == "generation_wait" and str(step.get("status") or "") == "passed":
            return True
    return str(live_payload.get("clip_generation_status") or "") == CLIP_GENERATION_STATUS_COMPLETED


def _clip_download_success(video_path: str, live_payload: dict[str, Any]) -> bool:
    if str(live_payload.get("download_status") or "") == "passed":
        if video_path and verify_recovered_mp4(video_path).get("is_real_mp4"):
            return True
    if not video_path:
        return False
    return bool(verify_recovered_mp4(video_path).get("is_real_mp4"))


def _browser_output_ready(cdp_url: str) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright

        from content_brain.execution.kling_frame_to_video_live_dry_run import _find_runway_generate_page
        from content_brain.execution.kling_multishot_live_engine import _detect_output_ready

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        page = _find_runway_generate_page(browser)
        if page is None:
            playwright.stop()
            return False, "no_runway_generate_page"
        ready, reason = _detect_output_ready(page)
        playwright.stop()
        return ready, reason
    except Exception as exc:
        return False, str(exc)[:160]


def evaluate_clip_download_gate(
    live_payload: dict[str, Any],
    video_path: str,
    *,
    cdp_url: str,
    browser_output_ready: bool | None = None,
    browser_output_detail: str = "",
) -> dict[str, Any]:
    generation_success = _clip_generation_success(live_payload)
    download_success = _clip_download_success(video_path, live_payload)
    if browser_output_ready is None and generation_success and not download_success:
        browser_output_ready, browser_output_detail = _browser_output_ready(cdp_url)
    elif browser_output_ready is None:
        browser_output_ready = False

    continuity_source_available = download_success or (generation_success and browser_output_ready)
    recovery_needed = generation_success and not download_success
    return {
        "generation_success": generation_success,
        "download_success": download_success,
        "continuity_source_available": continuity_source_available,
        "recovery_needed": recovery_needed,
        "recovery_available": recovery_needed,
        "clip_generation_status": CLIP_GENERATION_STATUS_COMPLETED if generation_success else CLIP_GENERATION_STATUS_FAILED,
        "download_status": "passed" if download_success else ("failed" if generation_success else "pending"),
        "browser_output_ready": bool(browser_output_ready),
        "browser_output_detail": browser_output_detail,
    }


def _ensure_frame_mp4(
    *,
    run_id: str,
    clip_index: int,
    clip_dir: Path,
    cdp_url: str,
    live_payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    base_payload = dict(live_payload)
    video_path = _resolve_clip_video(clip_dir)
    if video_path:
        verify = verify_recovered_mp4(video_path)
        if verify.get("is_real_mp4"):
            return video_path, live_payload
        quarantined = _quarantine_invalid_mp4(video_path, clip_dir)
        if quarantined:
            live_payload["quarantined_path"] = quarantined
            live_payload["download_verify_error"] = "Existing clip file is not a real MP4"
        video_path = ""

    if live_payload.get("generation_completed") or live_payload.get("status") == STATUS_DOWNLOAD_FAILED:
        gate_context = None
        if clip_index > 1:
            from content_brain.execution.kling_useframe_generation_completion_gate import (
                GenerationCompletionGateContext,
                build_prior_artifact_signatures_from_clip,
            )

            prior_clip_dir = clip_dir.parent / f"c{clip_index - 1}"
            prior_sigs = build_prior_artifact_signatures_from_clip(prior_clip_dir)
            gate_path = clip_dir / "generation_completion_gate_context.json"
            if gate_path.is_file():
                try:
                    loaded = json.loads(gate_path.read_text(encoding="utf-8"))
                    gate_context = GenerationCompletionGateContext(
                        require_new_artifact=bool(loaded.get("require_new_artifact")),
                        generate_clicked_at=str(loaded.get("generate_clicked_at") or ""),
                        prior_artifact_signatures=list(loaded.get("prior_artifact_signatures") or prior_sigs),
                        baseline_video_card_count=int(loaded.get("baseline_video_card_count") or 0),
                        baseline_card_fingerprints=list(loaded.get("baseline_card_fingerprints") or []),
                    )
                except Exception:
                    gate_context = None
            if gate_context is None and prior_sigs:
                gate_context = GenerationCompletionGateContext(
                    require_new_artifact=True,
                    prior_artifact_signatures=prior_sigs,
                )
        recover = recover_kling_frame_output(
            run_id=run_id,
            cdp_url=cdp_url,
            clip_index=clip_index,
            gate_context=gate_context,
        )
        live_payload = _merge_live_payload(base_payload, recover.to_dict())
        live_payload["clip_index"] = clip_index
        if recover.clip_output_path:
            src = Path(recover.clip_output_path)
            verify = verify_recovered_mp4(src)
            if verify.get("is_real_mp4"):
                dest = clip_dir / "video.mp4"
                if src.is_file() and src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                video_path = str(dest.resolve()) if dest.is_file() else recover.clip_output_path
            else:
                quarantined = _quarantine_invalid_mp4(src, clip_dir)
                live_payload["quarantined_path"] = quarantined
                live_payload["download_verify_error"] = "Recovered file is not a real MP4"
                live_payload["recovery_available"] = True
                video_path = ""
        (clip_dir / "live_run_result.json").write_text(json.dumps(live_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return video_path or _resolve_clip_video(clip_dir), live_payload


def run_kling_frame_continuity_chain(
    *,
    project_root: str | Path,
    run_id: str,
    run_dir: Path,
    plan: KlingFrameToVideoPlan,
    approved_by: str,
    confirm_credit_spend: bool,
    starter_frame_path: str | None,
    cdp_url: str = DEFAULT_CDP_URL,
    payload: dict[str, Any] | None = None,
    map_path: Path | str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    """Execute multi-clip Frame-to-Video chain with Use Frame continuity."""
    payload = dict(payload or {})
    approved_clips = _resolve_approved_clips(payload, plan)
    preflight = dict(payload.get("_preflight") or {})
    aspect_ratio = str(
        payload.get("aspect_ratio") or preflight.get("aspect_ratio") or "9:16"
    ).strip()
    if aspect_ratio not in {"9:16", "16:9"}:
        aspect_ratio = "9:16"
    runtime_state = KlingContinuityChainState(run_id=run_id, clip_count=plan.clip_count)
    use_frame_state = UseFrameChainState(
        run_id=run_id,
        clip_count=plan.clip_count,
        continuity_method=CONTINUITY_METHOD_USE_FRAME,
    )
    clip_results: list[dict[str, Any]] = []
    prior_frame = starter_frame_path
    continuity_frame_in_ui = False
    final_video = ""
    started = datetime.now(timezone.utc)
    plan_chain = {
        "version": plan.version,
        "run_id": run_id,
        "clip_count": plan.clip_count,
        "generation_mode": KLING_FRAME_TO_VIDEO_MODE,
        "links": [],
        "frame_sources": [],
    }

    for clip in plan.clips:
        clip_index = clip.clip_index
        if not clip_is_approved(clip_index, approved_clips):
            runtime_state.continuity_status = STATUS_CHAIN_AWAITING_APPROVAL
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"awaiting approval for clip {clip_index}"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            write_use_frame_chain(run_dir, use_frame_state)
            break

        clip_dir = _clip_dir(run_dir, clip_index)
        upload_frame = prior_frame if clip_index > 1 and not continuity_frame_in_ui else None
        prior_artifact_signatures: list[dict[str, Any]] = []
        require_new_artifact = False
        if clip_index > 1:
            from content_brain.execution.kling_useframe_generation_completion_gate import (
                build_prior_artifact_signatures_from_clip,
            )

            prior_clip_dir = _clip_dir(run_dir, clip_index - 1)
            prior_artifact_signatures = build_prior_artifact_signatures_from_clip(prior_clip_dir)
            require_new_artifact = bool(prior_artifact_signatures or continuity_frame_in_ui)
        if clip_index > 1 and not upload_frame and not continuity_frame_in_ui:
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = "prior_clip_frame_required"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            write_use_frame_chain(run_dir, use_frame_state)
            continuity_chain = write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            generation_report = {
                "version": RUNTIME_VERSION,
                "run_id": run_id,
                "status": STATUS_PREPARED,
                "precondition": "prior_clip_frame_required",
                "precondition_message": "Use Frame handoff required before clip 2+ Generate.",
                "generation_mode": KLING_FRAME_TO_VIDEO_MODE,
                "clip_results": clip_results,
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "continuity_status": runtime_state.continuity_status,
                "chain_complete": False,
            }
            download_report = {
                "run_id": run_id,
                "clip_count": plan.clip_count,
                "status": "pending",
                "final_video_path": "",
            }
            return clip_results, generation_report, download_report, "", {}, continuity_chain

        live = run_kling_frame_to_video_live(
            starter_frame_path=str(upload_frame) if upload_frame else None,
            frame_prompt=clip.prompt,
            topic=plan.topic,
            run_id=run_id,
            clip_index=clip_index,
            aspect_ratio=aspect_ratio,
            approve_generate=True,
            approved_by=approved_by,
            confirm_credit_spend=confirm_credit_spend,
            cdp_url=cdp_url,
            map_path=map_path or DEFAULT_MAP_PATH,
            continuity_frame_in_ui=continuity_frame_in_ui,
            prior_artifact_signatures=prior_artifact_signatures,
            require_new_artifact=require_new_artifact,
        )
        live_payload = live.to_dict()
        live_payload["clip_index"] = clip_index
        live_payload["story_chapter"] = story_chapter_for_clip(clip_index, clip_count=plan.clip_count)
        live_payload["clip_dir"] = str(clip_dir.resolve()).replace("\\", "/")
        clip_results.append(live_payload)
        (clip_dir / "live_run_result.json").write_text(json.dumps(live_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        video_path, live_payload = _ensure_frame_mp4(
            run_id=run_id,
            clip_index=clip_index,
            clip_dir=clip_dir,
            cdp_url=cdp_url,
            live_payload=live_payload,
        )
        gate = evaluate_clip_download_gate(live_payload, video_path, cdp_url=cdp_url)
        live_payload.update(gate)
        clip_results[-1] = live_payload
        (clip_dir / "live_run_result.json").write_text(json.dumps(live_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        chapter = str(
            live_payload.get("story_chapter")
            or story_chapter_for_clip(clip_index, clip_count=plan.clip_count)
        )
        live_payload["story_chapter"] = chapter

        if gate["download_success"] and video_path:
            dest = clip_dir / "video.mp4"
            src = Path(video_path)
            if src.is_file() and src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            final_video = str(dest.resolve())

        if not gate["generation_success"]:
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"clip {clip_index} generation failed"
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            write_use_frame_chain(run_dir, use_frame_state)
            break

        if not gate["continuity_source_available"]:
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = (
                f"clip {clip_index} download/recovery failed and no browser continuity source"
            )
            write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
            write_use_frame_chain(run_dir, use_frame_state)
            break

        continuity_video_path = final_video if gate["download_success"] else ""
        record_clip_continuity_metadata(
            use_frame_state,
            clip_index=clip_index,
            handoff={
                "continuity_method": CONTINUITY_METHOD_USE_FRAME,
                "used_for_next_clip": clip_index < plan.clip_count,
                "story_chapter": chapter,
                "use_frame_status": "clip_generated",
                "fallback_used": False,
                "video_path": continuity_video_path,
                "download_success": gate["download_success"],
                "recovery_needed": gate["recovery_needed"],
            },
            video_path=continuity_video_path,
        )
        runtime_state.clips.append(
            {
                "clip": clip_index,
                "video_path": continuity_video_path,
                "story_chapter": chapter,
                "next_clip": clip_index + 1 if clip_index < plan.clip_count else None,
                "generation_success": gate["generation_success"],
                "download_success": gate["download_success"],
                "continuity_source_available": gate["continuity_source_available"],
            }
        )

        if clip_index < plan.clip_count:
            try:
                from playwright.sync_api import sync_playwright

                playwright = sync_playwright().start()
                browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
                page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else None
                if page is None:
                    raise RuntimeError("No Runway CDP page for Use Frame handoff")
                handoff = apply_continuity_for_next_clip(
                    page,
                    run_dir=run_dir,
                    from_clip_index=clip_index,
                    to_clip_index=clip_index + 1,
                    video_path=continuity_video_path,
                    map_path=map_path or DEFAULT_MAP_PATH,
                    starter_frame_path=starter_frame_path,
                )
                playwright.stop()
                record_clip_continuity_metadata(
                    use_frame_state,
                    clip_index=clip_index,
                    handoff=handoff,
                    video_path=continuity_video_path,
                    story_chapter=chapter,
                )
                continuity_frame_in_ui = False
                extracted_frame = str(
                    handoff.get("extracted_frame_path") or handoff.get("frame_path") or ""
                ).strip()
                if handoff.get("used_for_next_clip") and extracted_frame:
                    prior_frame = extracted_frame
                elif (
                    handoff.get("used_for_next_clip")
                    and handoff.get("ok")
                    and handoff.get("continuity_method") == CONTINUITY_METHOD_USE_FRAME
                ):
                    continuity_frame_in_ui = bool(handoff.get("continuity_frame_in_ui", True))
                    prior_frame = None
                elif not handoff.get("used_for_next_clip") and not handoff.get("ok"):
                    runtime_state.continuity_status = STATUS_CHAIN_STOPPED
                    runtime_state.stopped_at_clip = clip_index + 1
                    runtime_state.stop_reason = f"continuity handoff failed after clip {clip_index}"
                    write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
                    write_use_frame_chain(run_dir, use_frame_state)
                    break
            except Exception as exc:
                runtime_state.continuity_status = STATUS_CHAIN_STOPPED
                runtime_state.stopped_at_clip = clip_index + 1
                runtime_state.stop_reason = f"Use Frame handoff error: {str(exc, ensure_ascii=False)[:160]}"
                write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
                write_use_frame_chain(run_dir, use_frame_state)
                break

        write_use_frame_chain(run_dir, use_frame_state)
        write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)

        if payload.get("stop_after_clip") and int(payload.get("stop_after_clip") or 0) == clip_index:
            runtime_state.continuity_status = STATUS_CHAIN_STOPPED
            runtime_state.stopped_at_clip = clip_index
            runtime_state.stop_reason = f"operator stop after clip {clip_index}"
            break

    completed = len(
        [
            item
            for item in clip_results
            if _clip_generation_success(item)
            or _resolve_clip_video(_clip_dir(run_dir, int(item.get("clip_index") or 1)))
        ]
    )
    finalize_story_progression(use_frame_state, completed_clips=completed, target_clips=plan.clip_count)
    if completed >= plan.clip_count and final_video:
        runtime_state.chain_complete = True
        runtime_state.continuity_status = STATUS_CHAIN_COMPLETE
        root_video = run_dir / "video.mp4"
        shutil.copy2(final_video, root_video)
        final_video = str(root_video.resolve())
        use_frame_state.chain_complete = True

    continuity_chain = write_continuity_chain_files(run_dir, plan_chain=plan_chain, runtime_state=runtime_state)
    use_frame_chain = write_use_frame_chain(run_dir, use_frame_state)
    continuity_chain["use_frame_chain"] = use_frame_chain

    generation_status = (
        STATUS_COMPLETED
        if final_video and use_frame_state.chain_complete
        else (
            STATUS_DOWNLOAD_FAILED_REPORT
            if any(r.get("status") == STATUS_DOWNLOAD_FAILED for r in clip_results)
            else STATUS_FAILED
        )
    )
    generation_report = {
        "version": RUNTIME_VERSION,
        "run_id": run_id,
        "status": generation_status,
        "generation_mode": KLING_FRAME_TO_VIDEO_MODE,
        "clip_results": clip_results,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "continuity_status": runtime_state.continuity_status,
        "chain_complete": runtime_state.chain_complete,
        "use_frame_chain": use_frame_chain,
    }
    download_report = {
        "run_id": run_id,
        "clip_count": plan.clip_count,
        "status": "completed" if final_video else "failed",
        "final_video_path": final_video,
        "continuity_method": use_frame_state.continuity_method,
        "fallback_used": use_frame_state.fallback_used,
        "story_progression_status": use_frame_state.story_progression_status,
    }
    return clip_results, generation_report, download_report, final_video, {}, continuity_chain


__all__ = [
    "RUNTIME_VERSION",
    "evaluate_clip_download_gate",
    "run_kling_frame_continuity_chain",
]
