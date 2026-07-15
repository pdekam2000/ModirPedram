"""Auto-upload completed videos to configured social platforms after automation jobs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from content_brain.upload.upload_models import PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_YOUTUBE
from content_brain.upload.media_video_resolver import verify_run_platform_for_upload

AUTO_PLATFORM_UPLOAD_VERSION = "auto_platform_upload_v1"
logger = logging.getLogger(__name__)


def _upload_debug(step: str, result: Any) -> None:
    summary = result
    if isinstance(result, dict):
        summary = {
            key: result.get(key)
            for key in (
                "ok",
                "uploaded",
                "status",
                "reason",
                "error",
                "video_path",
                "video_id",
                "video_url",
                "post_url",
                "platforms",
            )
            if key in result
        }
    message = f"[UPLOAD DEBUG] step: {step} result: {summary}"
    print(message, flush=True)
    logger.info(message)


def _resolve_video_path(*, video_path: str, publish_package_path: str, upload_package: dict[str, Any]) -> str:
    candidates = [
        video_path,
        str(upload_package.get("video_path") or ""),
        str(upload_package.get("publish_package_path") or ""),
    ]
    publish = publish_package_path or str(upload_package.get("publish_package_path") or "")
    if publish:
        publish_dir = Path(publish)
        for name in (
            "FINAL_BRANDED_PUBLISH_READY.mp4",
            "FINAL_PUBLISH_READY.mp4",
            "FINAL_BRANDED_VIDEO_CANONICAL.mp4",
            "FINAL_RUNWAY_PHASE_I_NARRATED.mp4",
        ):
            candidate = publish_dir / name
            if candidate.is_file():
                candidates.insert(0, str(candidate))
    for candidate in candidates:
        path = Path(str(candidate or ""))
        if path.is_file() and path.stat().st_size > 0:
            return str(path.resolve())
    return ""


def _platform_meta(upload_package: dict[str, Any], platform: str) -> dict[str, Any]:
    for target in upload_package.get("targets") or []:
        if isinstance(target, dict) and str(target.get("platform") or "") == platform:
            return dict(target)
    bundle = dict(upload_package.get("platform_metadata") or {})
    platforms = dict(bundle.get("platforms") or {})
    key = "instagram_reels" if platform == PLATFORM_INSTAGRAM else platform
    if platform == PLATFORM_TIKTOK:
        key = "tiktok"
    if platform == PLATFORM_YOUTUBE:
        key = "youtube_shorts"
    return dict(platforms.get(key) or platforms.get(platform) or {})


def _record_history(
    project_root: Path,
    *,
    platform: str,
    title: str,
    success: bool,
    run_id: str,
    post_url: str,
    error: str,
    video_id: str = "",
    thumbnail_uploaded: bool | None = None,
    thumbnail_path: str = "",
) -> None:
    from content_brain.automation.upload_history_store import UploadHistoryStore

    UploadHistoryStore(project_root).record(
        platform=platform,
        title=title,
        success=success,
        run_id=run_id,
        youtube_url=post_url,
        post_url=post_url,
        error=error,
        video_id=video_id,
        thumbnail_uploaded=thumbnail_uploaded,
        thumbnail_path=thumbnail_path,
    )


def submit_automation_platform_uploads(
    *,
    project_root: str | Path,
    platform_targets: list[str],
    video_path: str,
    publish_package_path: str = "",
    upload_package: dict[str, Any] | None = None,
    run_id: str = "",
    topic: str = "",
    automation_mode: bool = True,
    job_platform: str = "",
    skip_youtube_if_already_uploaded: bool = True,
    generation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upload to each enabled platform in platform_targets. Never raises."""
    root = Path(project_root).resolve()
    package = dict(upload_package or {})
    resolved_video = _resolve_video_path(
        video_path=video_path,
        publish_package_path=publish_package_path,
        upload_package=package,
    )
    results: dict[str, Any] = {"ok": True, "platforms": {}, "video_path": resolved_video}
    report = dict(generation_report or {})

    if not resolved_video:
        results["ok"] = False
        results["error"] = "video_missing_for_upload"
        _upload_debug("video_missing_for_upload", results)
        return results

    from content_brain.automation.fail_closed_upload_gate import evaluate_automation_upload_gate
    from content_brain.automation.platform_upload_guard import normalize_platform

    upload_allowed, upload_block_reason = evaluate_automation_upload_gate(
        project_root=root,
        generation_report=report,
        run_id=run_id,
        planned_clip_count=int(report.get("expected_clip_count") or report.get("clip_count") or 0),
        publish_package_path=publish_package_path,
    )
    if not upload_allowed:
        results["ok"] = False
        results["error"] = upload_block_reason
        results["platforms"] = {
            normalize_platform(job_platform or (platform_targets[0] if platform_targets else "")): {
                "ok": False,
                "uploaded": False,
                "status": "blocked",
                "reason": upload_block_reason,
            }
        }
        _upload_debug("fail_closed_upload_gate_blocked", results)
        return results

    _upload_debug("resolved_video", {"video_path": resolved_video, "platform_targets": platform_targets})

    from content_brain.automation.platform_upload_guard import (
        guard_upload_or_block,
        resolve_job_upload_targets,
    )
    from content_brain.upload.upload_manager import UploadManager

    manager = UploadManager(root)
    title = str(topic or package.get("topic") or "Automation video")
    job_platform_key = normalize_platform(
        job_platform or (platform_targets[0] if platform_targets else "")
    )
    from content_brain.automation.platform_daily_scheduler import display_platform_topic
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    profile = ProductChannelProfileStore(root).load()
    display_title = display_platform_topic(
        job_platform_key or (platform_targets[0] if platform_targets else ""),
        profile,
        title,
    )
    allowed_targets = resolve_job_upload_targets(platform_targets)

    for platform in allowed_targets:
        normalized = str(platform or "").strip().lower()
        allowed, block_reason = guard_upload_or_block(
            job_platform=job_platform_key,
            upload_platform=normalized,
            topic=display_title,
        )
        if not allowed:
            results["platforms"][normalized] = {
                "ok": False,
                "uploaded": False,
                "status": "blocked",
                "reason": block_reason,
            }
            _upload_debug(f"guard_blocked_{normalized}", results["platforms"][normalized])
            continue
        try:
            if normalized in {PLATFORM_YOUTUBE, "youtube"}:
                yt_upload = dict(report.get("youtube_upload") or {})
                if skip_youtube_if_already_uploaded and yt_upload.get("uploaded"):
                    already_url = str(yt_upload.get("youtube_url") or yt_upload.get("video_url") or "")
                    from content_brain.upload.youtube_uploader import extract_youtube_video_id

                    results["platforms"][normalized] = {
                        "ok": True,
                        "uploaded": True,
                        "status": "already_uploaded",
                        "video_id": str(yt_upload.get("video_id") or extract_youtube_video_id(already_url) or ""),
                        "video_url": already_url,
                        "post_url": already_url,
                        "thumbnail_uploaded": bool(yt_upload.get("thumbnail_uploaded")),
                        "thumbnail_path": str(yt_upload.get("thumbnail_path") or ""),
                    }
                    continue
                upload_result = manager.submit_youtube_upload(
                    upload_package=package,
                    run_id=run_id,
                    automation_mode=automation_mode,
                )
                _upload_debug("submit_youtube_upload", upload_result)
                results["platforms"][normalized] = upload_result
                _record_history(
                    root,
                    platform=PLATFORM_YOUTUBE,
                    title=display_title,
                    success=bool(upload_result.get("ok")),
                    run_id=run_id,
                    post_url=str(upload_result.get("video_url") or ""),
                    error=str(upload_result.get("reason") or upload_result.get("error") or ""),
                    video_id=str(upload_result.get("video_id") or ""),
                    thumbnail_uploaded=bool(upload_result.get("thumbnail_uploaded"))
                    if "thumbnail_uploaded" in upload_result
                    else None,
                    thumbnail_path=str(upload_result.get("thumbnail_path") or ""),
                )
            elif normalized in {PLATFORM_INSTAGRAM, "instagram", "instagram_reels"}:
                ok_platform, platform_reason, run_platform = verify_run_platform_for_upload(
                    root,
                    run_id,
                    job_platform=job_platform_key or normalized,
                )
                if not ok_platform:
                    upload_result = {
                        "ok": False,
                        "uploaded": False,
                        "status": "blocked",
                        "reason": platform_reason,
                        "run_platform": run_platform,
                    }
                    results["platforms"][normalized] = upload_result
                    _upload_debug(f"instagram_run_platform_blocked_{normalized}", upload_result)
                    _record_history(
                        root,
                        platform=PLATFORM_INSTAGRAM,
                        title=display_title,
                        success=False,
                        run_id=run_id,
                        post_url="",
                        error=platform_reason,
                    )
                    continue
                meta = _platform_meta(package, PLATFORM_INSTAGRAM)
                upload_result = manager.submit_instagram_upload(
                    upload_package=package,
                    video_path=resolved_video,
                    run_id=run_id,
                    title=str(meta.get("title") or meta.get("caption") or title),
                    caption=str(meta.get("caption") or meta.get("description") or title),
                    hashtags=list(meta.get("hashtags") or []),
                    automation_mode=automation_mode,
                )
                results["platforms"][normalized] = upload_result
                _record_history(
                    root,
                    platform=PLATFORM_INSTAGRAM,
                    title=display_title,
                    success=bool(upload_result.get("ok")),
                    run_id=run_id,
                    post_url=str(upload_result.get("post_url") or ""),
                    error=str(upload_result.get("reason") or upload_result.get("error") or ""),
                )
            elif normalized in {PLATFORM_TIKTOK, "tiktok"}:
                meta = _platform_meta(package, PLATFORM_TIKTOK)
                upload_result = manager.submit_tiktok_upload(
                    upload_package=package,
                    video_path=resolved_video,
                    run_id=run_id,
                    title=str(meta.get("title") or meta.get("caption") or title),
                    caption=str(meta.get("caption") or meta.get("description") or title),
                    automation_mode=automation_mode,
                )
                results["platforms"][normalized] = upload_result
                _record_history(
                    root,
                    platform=PLATFORM_TIKTOK,
                    title=display_title,
                    success=bool(upload_result.get("ok")),
                    run_id=run_id,
                    post_url=str(upload_result.get("post_url") or ""),
                    error=str(upload_result.get("reason") or upload_result.get("error") or ""),
                )
        except Exception as exc:
            results["platforms"][normalized] = {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "error": str(exc),
            }
            _record_history(
                root,
                platform=normalized,
                title=title,
                success=False,
                run_id=run_id,
                post_url="",
                error=str(exc),
            )

    if results["platforms"]:
        results["ok"] = any(item.get("ok") or item.get("uploaded") for item in results["platforms"].values())
    _upload_debug("submit_automation_platform_uploads_done", results)
    return results


__all__ = ["AUTO_PLATFORM_UPLOAD_VERSION", "submit_automation_platform_uploads"]
