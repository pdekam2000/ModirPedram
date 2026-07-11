"""TikTok video upload via Content Posting API (direct post)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIKTOK_UPLOADER_VERSION = "tiktok_uploader_v1"
TIKTOK_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

POLL_INTERVAL_SECONDS = 3
POLL_MAX_ATTEMPTS = 40


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_channel_profile(profile: dict[str, Any], project_root: str | Path | None = None) -> dict[str, Any]:
    """Merge persisted channel_profile.json credentials with any caller-provided profile."""
    merged = dict(profile or {})
    if project_root is None:
        return merged
    from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

    stored = ProductChannelProfileStore(project_root).load()
    for key in (
        "instagram_upload_enabled",
        "instagram_access_token",
        "instagram_account_id",
        "tiktok_upload_enabled",
        "tiktok_client_key",
        "tiktok_client_secret",
        "tiktok_access_token",
        "tiktok_privacy",
    ):
        if not str(merged.get(key) or "").strip() and key in stored:
            merged[key] = stored.get(key)
    return merged


def _resolve_access_token(profile: dict[str, Any]) -> str:
    return str(profile.get("tiktok_access_token") or "").strip()


def _poll_publish_status(*, publish_id: str, access_token: str, requests_module: Any) -> tuple[bool, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}
    for _ in range(POLL_MAX_ATTEMPTS):
        response = requests_module.post(
            TIKTOK_STATUS_URL,
            headers=headers,
            json={"publish_id": publish_id},
            timeout=30,
        )
        if response.status_code != 200:
            return False, {"error": response.text[:500], "http_status": response.status_code}
        payload = response.json() if response.text else {}
        data = dict(payload.get("data") or payload)
        status = str(data.get("status") or "").upper()
        if status in {"PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "POST_PUBLISH_COMPLETE"}:
            return True, data
        if status in {"FAILED", "PUBLISH_FAILED"}:
            return False, data
        time.sleep(POLL_INTERVAL_SECONDS)
    return False, {"error": "tiktok_publish_timeout"}


def upload_video_to_tiktok(
    *,
    profile: dict[str, Any],
    video_path: str | Path,
    title: str = "",
    caption: str = "",
    privacy_level: str = "PUBLIC_TO_EVERYONE",
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    profile = _load_channel_profile(profile, project_root)
    access_token = _resolve_access_token(profile)
    if not access_token:
        return {
            "ok": False,
            "uploaded": False,
            "status": "blocked",
            "reason": "tiktok_credentials_missing",
            "platform": "tiktok",
        }

    path = Path(video_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "uploaded": False, "status": "failed", "reason": "video_missing", "platform": "tiktok"}

    try:
        import requests
    except ImportError:
        return {"ok": False, "uploaded": False, "status": "failed", "reason": "requests_unavailable"}

    file_size = path.stat().st_size
    chunk_size = min(file_size, 10 * 1024 * 1024)
    post_title = str(caption or title or "Short video")[:150]
    privacy = str(privacy_level or profile.get("tiktok_privacy") or "PUBLIC_TO_EVERYONE").upper()
    if privacy not in {"PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"}:
        privacy = "PUBLIC_TO_EVERYONE"

    init_body = {
        "post_info": {
            "title": post_title,
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk_size,
            "total_chunk_count": max(1, (file_size + chunk_size - 1) // chunk_size),
        },
    }
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}

    init_response = requests.post(TIKTOK_INIT_URL, headers=headers, json=init_body, timeout=60)
    if init_response.status_code != 200:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "tiktok_init_failed",
            "details": init_response.text[:500],
            "http_status": init_response.status_code,
        }

    init_payload = init_response.json() if init_response.text else {}
    data = dict(init_payload.get("data") or init_payload)
    upload_url = str(data.get("upload_url") or "")
    publish_id = str(data.get("publish_id") or "")
    if not upload_url or not publish_id:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "tiktok_init_missing_upload_url",
            "details": json.dumps(init_payload, ensure_ascii=False)[:500],
        }

    with path.open("rb") as handle:
        video_bytes = handle.read()

    upload_headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(file_size),
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
    }
    upload_response = requests.put(upload_url, headers=upload_headers, data=video_bytes, timeout=max(120, file_size // (512 * 1024)))
    if upload_response.status_code not in {200, 201, 204}:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "tiktok_video_upload_failed",
            "details": upload_response.text[:500],
            "http_status": upload_response.status_code,
        }

    ok, status_payload = _poll_publish_status(
        publish_id=publish_id,
        access_token=access_token,
        requests_module=requests,
    )
    if not ok:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "tiktok_publish_failed",
            "publish_id": publish_id,
            "details": status_payload,
        }

    post_url = str(status_payload.get("share_url") or status_payload.get("publicaly_available_post_id") or "")
    return {
        "ok": True,
        "uploaded": True,
        "status": "uploaded",
        "platform": "tiktok",
        "privacy": privacy,
        "publish_id": publish_id,
        "post_url": post_url,
        "upload_time": _now_iso(),
        "version": TIKTOK_UPLOADER_VERSION,
    }


__all__ = ["TIKTOK_UPLOADER_VERSION", "upload_video_to_tiktok"]
