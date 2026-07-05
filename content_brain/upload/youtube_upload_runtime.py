"""YouTube upload runtime — publish package → YouTube Data API upload."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.product_assembly_bridge import FINAL_PUBLISH_READY_NAME
from content_brain.execution.product_subtitle_branding_publish import FINAL_BRANDED_PUBLISH_READY_NAME
from content_brain.execution.pwmap_runway_agent_adapter import validate_mp4_path
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.publish.youtube_metadata_generator import YOUTUBE_METADATA_FILENAME, load_youtube_metadata
from content_brain.upload.youtube_auth import (
    fetch_and_store_channel_info,
    get_youtube_auth_status,
    load_account_info,
)
from content_brain.upload.youtube_uploader import upload_thumbnail_to_youtube, upload_video_to_youtube

YOUTUBE_UPLOAD_RUNTIME_VERSION = "youtube_upload_runtime_v1"
YOUTUBE_UPLOAD_RESULT_NAME = "youtube_upload_result.json"
PUBLISH_PACKAGE_NAME = "publish_package.json"

THUMBNAIL_CANDIDATES = (
    "thumbnail.jpg",
    "thumbnail.jpeg",
    "thumbnail.png",
    "thumbnail.webp",
    "youtube_thumbnail.jpg",
    "youtube_thumbnail.png",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_publish_video_path(publish_dir: Path) -> Path | None:
    branded = publish_dir / FINAL_BRANDED_PUBLISH_READY_NAME
    if validate_mp4_path(branded)["valid"]:
        return branded
    fallback = publish_dir / FINAL_PUBLISH_READY_NAME
    if validate_mp4_path(fallback)["valid"]:
        return fallback
    return None


def resolve_thumbnail_path(publish_dir: Path) -> Path | None:
    for name in THUMBNAIL_CANDIDATES:
        candidate = publish_dir / name
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    thumbs_dir = publish_dir / "thumbnails"
    if thumbs_dir.is_dir():
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            matches = sorted(thumbs_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def load_publish_package_inputs(publish_dir: str | Path) -> dict[str, Any]:
    publish_path = Path(publish_dir).resolve()
    metadata = load_youtube_metadata(publish_path) or {}
    publish_package = {}
    package_path = publish_path / PUBLISH_PACKAGE_NAME
    if package_path.is_file():
        try:
            publish_package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            publish_package = {}
    video = resolve_publish_video_path(publish_path)
    thumbnail = resolve_thumbnail_path(publish_path)
    return {
        "publish_dir": str(publish_path),
        "video_path": str(video.resolve()).replace("\\", "/") if video else "",
        "thumbnail_path": str(thumbnail.resolve()).replace("\\", "/") if thumbnail else "",
        "youtube_metadata": metadata,
        "publish_package": publish_package,
        "youtube_metadata_exists": (publish_path / YOUTUBE_METADATA_FILENAME).is_file(),
    }


def map_youtube_metadata_to_upload(metadata: dict[str, Any], *, profile: dict[str, Any]) -> dict[str, Any]:
    hashtags = [str(item).strip() for item in (metadata.get("hashtags") or []) if str(item).strip()]
    return {
        "title": str(metadata.get("title") or metadata.get("short_title") or profile.get("channel_topic") or "Untitled"),
        "description": str(metadata.get("description") or profile.get("youtube_default_description") or ""),
        "tags": [str(item).strip() for item in (metadata.get("tags") or metadata.get("seo_keywords") or []) if str(item).strip()],
        "hashtags": hashtags,
        "category": str(metadata.get("category") or ""),
        "language": str(metadata.get("language") or profile.get("language") or "en"),
        "made_for_kids": bool(metadata.get("made_for_kids", profile.get("youtube_made_for_kids", False))),
    }


def write_youtube_upload_result(publish_dir: Path, payload: dict[str, Any]) -> Path:
    publish_dir.mkdir(parents=True, exist_ok=True)
    path = publish_dir / YOUTUBE_UPLOAD_RESULT_NAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_youtube_upload_result(publish_dir: str | Path) -> dict[str, Any] | None:
    path = Path(publish_dir).resolve() / YOUTUBE_UPLOAD_RESULT_NAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def run_youtube_upload_from_publish_package(
    *,
    project_root: str | Path,
    publish_dir: str | Path,
    run_id: str = "",
    visibility: str = "",
    publish_now: bool = True,
    publish_at: str = "",
    confirmed: bool = False,
    upload_thumbnail: bool = True,
    automation_mode: bool = False,
) -> dict[str, Any]:
    """Upload FINAL_BRANDED_PUBLISH_READY.mp4 using publish/youtube_metadata.json."""
    root = Path(project_root).resolve()
    publish_path = Path(publish_dir).resolve()
    profile = ProductChannelProfileStore(root).load()
    inputs = load_publish_package_inputs(publish_path)
    auth = get_youtube_auth_status(root, profile)
    account = load_account_info(root) or {}

    base_failure = {
        "version": YOUTUBE_UPLOAD_RUNTIME_VERSION,
        "run_id": run_id,
        "uploaded": False,
        "upload_status": "upload_failed",
        "youtube_video_id": "",
        "youtube_url": "",
        "visibility": "",
        "publish_time": "",
        "upload_time": "",
        "publish_dir": str(publish_path),
        "video_path": inputs.get("video_path") or "",
        "thumbnail_uploaded": False,
        "youtube_metadata_exists": bool(inputs.get("youtube_metadata_exists")),
        "channel_id": str(account.get("channel_id") or auth.get("channel_id") or ""),
        "channel_name": str(account.get("channel_name") or auth.get("channel_name") or ""),
        "error": "",
        "created_at": _now_iso(),
    }

    if not bool(profile.get("youtube_upload_enabled")):
        base_failure["error"] = "youtube_upload_disabled"
        write_youtube_upload_result(publish_path, base_failure)
        return base_failure

    require_confirmation = bool(profile.get("youtube_require_confirmation", True))
    if automation_mode:
        require_confirmation = False
    if require_confirmation and not confirmed and not bool(profile.get("youtube_upload_confirmed")):
        base_failure["upload_status"] = "confirmation_required"
        base_failure["error"] = "first_upload_requires_confirmation"
        write_youtube_upload_result(publish_path, base_failure)
        return base_failure

    if not auth.get("authenticated"):
        base_failure["upload_status"] = "blocked"
        base_failure["error"] = "youtube_connect_required"
        write_youtube_upload_result(publish_path, base_failure)
        return base_failure

    if not inputs.get("video_path"):
        base_failure["error"] = "publish_video_missing"
        write_youtube_upload_result(publish_path, base_failure)
        return base_failure

    metadata = dict(inputs.get("youtube_metadata") or {})
    mapped = map_youtube_metadata_to_upload(metadata, profile=profile)
    effective_visibility = str(visibility or profile.get("youtube_privacy") or "public")
    if not account.get("channel_id"):
        fetch_and_store_channel_info(root, profile)
        account = load_account_info(root) or account

    upload_result = upload_video_to_youtube(
        project_root=root,
        profile=profile,
        video_path=str(inputs["video_path"]),
        title=mapped["title"],
        description=mapped["description"],
        tags=mapped["tags"],
        hashtags=mapped["hashtags"],
        category=mapped["category"],
        language=mapped["language"],
        made_for_kids=mapped["made_for_kids"],
        privacy=effective_visibility,
        publish_now=bool(publish_now),
        publish_at=str(publish_at or profile.get("youtube_publish_at") or ""),
    )

    if not upload_result.get("ok"):
        failure_status = str(upload_result.get("status") or "upload_failed")
        if failure_status == "failed":
            failure_status = "upload_failed"
        base_failure.update(
            {
                "upload_status": failure_status,
                "error": str(upload_result.get("reason") or upload_result.get("error") or "youtube_upload_failed"),
                "details": upload_result,
            }
        )
        write_youtube_upload_result(publish_path, base_failure)
        return base_failure

    video_id = str(upload_result.get("youtube_video_id") or upload_result.get("video_id") or "")
    thumbnail_result: dict[str, Any] = {"ok": False, "status": "skipped", "reason": "thumbnail_not_requested"}
    if upload_thumbnail and video_id and inputs.get("thumbnail_path"):
        thumbnail_result = upload_thumbnail_to_youtube(
            project_root=root,
            profile=profile,
            video_id=video_id,
            thumbnail_path=str(inputs["thumbnail_path"]),
        )

    success = {
        "version": YOUTUBE_UPLOAD_RUNTIME_VERSION,
        "run_id": run_id,
        "uploaded": True,
        "upload_status": "scheduled" if upload_result.get("scheduled") else "uploaded",
        "youtube_video_id": video_id,
        "youtube_url": str(upload_result.get("youtube_url") or upload_result.get("video_url") or ""),
        "visibility": str(upload_result.get("visibility") or upload_result.get("privacy") or effective_visibility),
        "publish_time": str(upload_result.get("publish_time") or ""),
        "upload_time": str(upload_result.get("upload_time") or _now_iso()),
        "scheduled": bool(upload_result.get("scheduled")),
        "publish_dir": str(publish_path),
        "video_path": inputs.get("video_path") or "",
        "thumbnail_path": inputs.get("thumbnail_path") or "",
        "thumbnail_uploaded": bool(thumbnail_result.get("ok")),
        "thumbnail_upload_status": thumbnail_result.get("status"),
        "youtube_metadata_exists": bool(inputs.get("youtube_metadata_exists")),
        "metadata_applied": mapped,
        "channel_id": str(account.get("channel_id") or auth.get("channel_id") or ""),
        "channel_name": str(account.get("channel_name") or auth.get("channel_name") or ""),
        "youtube_account_id": str(account.get("youtube_account_id") or account.get("channel_id") or ""),
        "created_at": _now_iso(),
    }
    write_youtube_upload_result(publish_path, success)
    return success


def resolve_publish_dir_for_run(project_root: str | Path, run_id: str, run_dir: str = "") -> Path | None:
    if run_dir:
        candidate = Path(run_dir).resolve() / "publish"
        if candidate.is_dir():
            return candidate
    if run_id:
        pwmap = Path(project_root).resolve() / "outputs" / "pwmap_agent_runs" / run_id / "publish"
        if pwmap.is_dir():
            return pwmap
    return None


__all__ = [
    "YOUTUBE_UPLOAD_RESULT_NAME",
    "YOUTUBE_UPLOAD_RUNTIME_VERSION",
    "load_publish_package_inputs",
    "load_youtube_upload_result",
    "map_youtube_metadata_to_upload",
    "resolve_publish_dir_for_run",
    "run_youtube_upload_from_publish_package",
    "write_youtube_upload_result",
]
