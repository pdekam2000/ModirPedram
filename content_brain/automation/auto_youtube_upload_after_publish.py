"""Auto YouTube upload after publish package is ready (Create Video post-chain)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from content_brain.automation.youtube_auto_upload_config import load_youtube_auto_upload_config
from content_brain.execution.product_subtitle_branding_publish import (
    FINAL_BRANDED_PUBLISH_READY_NAME,
    PUBLISH_PACKAGE_NAME,
)
from content_brain.execution.product_visual_diversity_guard import load_visual_diversity_report
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME
from content_brain.upload.youtube_auth import get_youtube_auth_status
from content_brain.upload.youtube_upload_runtime import (
    load_publish_package_inputs,
    run_youtube_upload_from_publish_package,
    write_youtube_upload_result,
)

AUTO_YOUTUBE_UPLOAD_VERSION = "auto_youtube_upload_after_publish_v1"


def evaluate_auto_youtube_upload_eligibility(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    publish_dir: str | Path,
    branding_publish_result: dict[str, Any] | None = None,
    assembly_result: dict[str, Any] | None = None,
    visual_diversity: dict[str, Any] | None = None,
    expected_clip_count: int = 0,
    youtube_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return {eligible: bool, blocked_reason: str, visibility: str, publish_now: bool, confirmed: bool}."""
    root = Path(project_root).resolve()
    run_path = Path(run_dir).resolve()
    publish_path = Path(publish_dir).resolve()
    config = dict(youtube_config or load_youtube_auto_upload_config(root))
    profile = ProductChannelProfileStore(root).load()
    branding = dict(branding_publish_result or {})
    assembly = dict(assembly_result or {})

    visibility = str(config.get("default_visibility") or profile.get("youtube_privacy") or "private").lower()
    publish_now = bool(config.get("publish_now", True))
    confirmed = True

    if not bool(config.get("auto_upload_enabled", True)):
        return {
            "eligible": False,
            "blocked_reason": "auto_upload_disabled",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    if not bool(profile.get("youtube_upload_enabled", True)):
        return {
            "eligible": False,
            "blocked_reason": "youtube_upload_disabled",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    if visibility in {"public", "unlisted"} and not bool(config.get("allow_public_auto_upload")):
        return {
            "eligible": False,
            "blocked_reason": "public_upload_requires_manual_approval",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": False,
        }

    diversity = dict(visual_diversity or {})
    if not diversity:
        diversity = load_visual_diversity_report(run_path) or load_visual_diversity_report(publish_path) or {}
    if diversity.get("status") == "visual_repetition_failed" or not bool(diversity.get("youtube_upload_allowed", True)):
        return {
            "eligible": False,
            "blocked_reason": "upload_blocked_visual_diversity",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    if assembly and not assembly.get("ok"):
        return {
            "eligible": False,
            "blocked_reason": "upload_blocked_publish_failed",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    if branding.get("branding_status") == "branding_failed":
        return {
            "eligible": False,
            "blocked_reason": "upload_blocked_publish_failed",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    publish_package = {}
    package_path = publish_path / PUBLISH_PACKAGE_NAME
    if package_path.is_file():
        try:
            publish_package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            publish_package = {}

    if not bool(branding.get("publish_ready") or publish_package.get("publish_ready")):
        return {
            "eligible": False,
            "blocked_reason": "publish_not_ready",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    branded_video = publish_path / FINAL_BRANDED_PUBLISH_READY_NAME
    if not branded_video.is_file():
        return {
            "eligible": False,
            "blocked_reason": "publish_video_missing",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    if not (publish_path / YOUTUBE_METADATA_FILENAME).is_file():
        return {
            "eligible": False,
            "blocked_reason": "metadata_missing",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    if expected_clip_count > 0:
        source_count = int(assembly.get("source_clip_count") or 0)
        if source_count < expected_clip_count:
            return {
                "eligible": False,
                "blocked_reason": "upload_blocked_missing_clips",
                "visibility": visibility,
                "publish_now": publish_now,
                "confirmed": confirmed,
            }

    auth = get_youtube_auth_status(root, profile)
    if not auth.get("authenticated"):
        return {
            "eligible": False,
            "blocked_reason": "oauth_not_available",
            "visibility": visibility,
            "publish_now": publish_now,
            "confirmed": confirmed,
        }

    return {
        "eligible": True,
        "blocked_reason": "",
        "visibility": visibility,
        "publish_now": publish_now,
        "confirmed": confirmed,
        "auto_upload_enabled": True,
    }


def _write_blocked_upload_result(
    publish_dir: Path,
    *,
    run_id: str,
    blocked_reason: str,
    visibility: str = "",
) -> dict[str, Any]:
    payload = {
        "version": AUTO_YOUTUBE_UPLOAD_VERSION,
        "run_id": run_id,
        "uploaded": False,
        "upload_status": "blocked",
        "auto_upload": True,
        "auto_upload_started": False,
        "blocked_reason": blocked_reason,
        "error": blocked_reason,
        "visibility": visibility,
        "youtube_video_id": "",
        "youtube_url": "",
        "upload_time": "",
        "publish_dir": str(publish_dir.resolve()),
    }
    write_youtube_upload_result(publish_dir, payload)
    return payload


def maybe_auto_youtube_upload_after_publish(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    run_id: str,
    publish_dir: str | Path,
    branding_publish_result: dict[str, Any] | None = None,
    assembly_result: dict[str, Any] | None = None,
    visual_diversity: dict[str, Any] | None = None,
    expected_clip_count: int = 0,
) -> dict[str, Any]:
    """Attempt private auto-upload when publish package is ready; never raises."""
    root = Path(project_root).resolve()
    publish_path = Path(publish_dir).resolve()
    config = load_youtube_auto_upload_config(root)

    eligibility = evaluate_auto_youtube_upload_eligibility(
        project_root=root,
        run_dir=run_dir,
        publish_dir=publish_path,
        branding_publish_result=branding_publish_result,
        assembly_result=assembly_result,
        visual_diversity=visual_diversity,
        expected_clip_count=expected_clip_count,
        youtube_config=config,
    )

    base = {
        "auto_upload_enabled": bool(config.get("auto_upload_enabled", True)),
        "auto_upload_started": False,
        "upload_status": "skipped",
        "blocked_reason": eligibility.get("blocked_reason") or "",
        "visibility": eligibility.get("visibility") or "private",
        "publish_now": bool(eligibility.get("publish_now", True)),
    }

    if not eligibility.get("eligible"):
        if eligibility.get("blocked_reason") and eligibility.get("blocked_reason") != "auto_upload_disabled":
            blocked = _write_blocked_upload_result(
                publish_path,
                run_id=run_id,
                blocked_reason=str(eligibility.get("blocked_reason") or "upload_blocked"),
                visibility=str(eligibility.get("visibility") or ""),
            )
            base.update(blocked)
        else:
            base["upload_status"] = "skipped"
            base["blocked_reason"] = str(eligibility.get("blocked_reason") or "auto_upload_disabled")
        return base

    inputs = load_publish_package_inputs(publish_path)
    if not inputs.get("video_path") or not inputs.get("youtube_metadata_exists"):
        blocked = _write_blocked_upload_result(
            publish_path,
            run_id=run_id,
            blocked_reason="publish_package_incomplete",
        )
        return {**base, **blocked, "auto_upload_started": True}

    base["auto_upload_started"] = True
    upload_result = run_youtube_upload_from_publish_package(
        project_root=root,
        publish_dir=publish_path,
        run_id=run_id,
        visibility=str(eligibility.get("visibility") or "private"),
        publish_now=bool(eligibility.get("publish_now", True)),
        confirmed=bool(eligibility.get("confirmed", True)),
        upload_thumbnail=True,
    )
    upload_result["auto_upload"] = True
    upload_result["auto_upload_enabled"] = True
    upload_result["auto_upload_started"] = True
    upload_result["blocked_reason"] = "" if upload_result.get("uploaded") else str(upload_result.get("error") or "")
    return upload_result


__all__ = [
    "AUTO_YOUTUBE_UPLOAD_VERSION",
    "evaluate_auto_youtube_upload_eligibility",
    "maybe_auto_youtube_upload_after_publish",
]
