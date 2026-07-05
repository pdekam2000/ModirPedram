"""Instagram Reels upload via Meta Graph API (resumable local file upload)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INSTAGRAM_UPLOADER_VERSION = "instagram_uploader_v1"
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
RUPLOAD_BASE = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}"

POLL_INTERVAL_SECONDS = 5
POLL_MAX_ATTEMPTS = 60


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
        "instagram_privacy",
        "instagram_video_public_url",
        "tiktok_upload_enabled",
        "tiktok_client_key",
        "tiktok_client_secret",
        "tiktok_access_token",
        "tiktok_privacy",
    ):
        if not str(merged.get(key) or "").strip() and key in stored:
            merged[key] = stored.get(key)
    return merged


def _build_caption(*, title: str, caption: str, hashtags: list[str]) -> str:
    base = str(caption or title or "").strip()
    tags = []
    for item in hashtags:
        text = str(item or "").strip()
        if not text:
            continue
        tags.append(text if text.startswith("#") else f"#{text.lstrip('#')}")
    if tags and not any(tag.lower().lstrip("#") in base.lower() for tag in tags):
        base = f"{base}\n\n{' '.join(tags)}".strip()
    return base[:2200]


def _poll_container_ready(*, container_id: str, access_token: str, requests_module: Any) -> tuple[bool, str]:
    for _ in range(POLL_MAX_ATTEMPTS):
        response = requests_module.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=30,
        )
        if response.status_code != 200:
            return False, response.text[:500]
        payload = response.json() if response.text else {}
        status = str(payload.get("status_code") or payload.get("status") or "").upper()
        if status in {"FINISHED", "PUBLISHED"}:
            return True, ""
        if status in {"ERROR", "FAILED", "EXPIRED"}:
            return False, str(payload)
        time.sleep(POLL_INTERVAL_SECONDS)
    return False, "instagram_container_timeout"


def upload_reel_to_instagram(
    *,
    profile: dict[str, Any],
    video_path: str | Path,
    title: str = "",
    caption: str = "",
    hashtags: list[str] | None = None,
    video_url: str = "",
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Upload a Reel to Instagram. Uses resumable upload for local files or video_url when provided."""
    profile = _load_channel_profile(profile, project_root)
    account_id = str(profile.get("instagram_account_id") or "").strip()
    access_token = str(profile.get("instagram_access_token") or "").strip()
    if not account_id or not access_token:
        return {
            "ok": False,
            "uploaded": False,
            "status": "blocked",
            "reason": "instagram_credentials_missing",
            "platform": "instagram_reels",
        }

    caption_text = _build_caption(title=title, caption=caption, hashtags=list(hashtags or []))
    path = Path(video_path) if video_path else None

    try:
        import requests
    except ImportError:
        return {"ok": False, "uploaded": False, "status": "failed", "reason": "requests_unavailable"}

    # Remote URL path (optional CDN / public hosting)
    public_url = str(video_url or profile.get("instagram_video_public_url") or "").strip()
    if public_url and not (path and path.is_file()):
        create = requests.post(
            f"{GRAPH_BASE}/{account_id}/media",
            data={
                "media_type": "REELS",
                "video_url": public_url,
                "caption": caption_text,
                "access_token": access_token,
            },
            timeout=60,
        )
        if create.status_code != 200:
            return {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "reason": "instagram_media_create_failed",
                "details": create.text[:500],
            }
        container_id = str((create.json() or {}).get("id") or "")
    else:
        if not path or not path.is_file() or path.stat().st_size <= 0:
            return {"ok": False, "uploaded": False, "status": "failed", "reason": "video_missing"}

        file_size = path.stat().st_size
        create = requests.post(
            f"{GRAPH_BASE}/{account_id}/media",
            data={
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption_text,
                "access_token": access_token,
            },
            timeout=60,
        )
        if create.status_code != 200:
            return {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "reason": "instagram_resumable_init_failed",
                "details": create.text[:500],
            }
        container_id = str((create.json() or {}).get("id") or "")
        if not container_id:
            return {"ok": False, "uploaded": False, "status": "failed", "reason": "instagram_missing_container_id"}

        with path.open("rb") as handle:
            upload = requests.post(
                f"{RUPLOAD_BASE}/{container_id}",
                headers={
                    "Authorization": f"OAuth {access_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                    "Content-Type": "video/mp4",
                },
                data=handle.read(),
                timeout=max(120, file_size // (512 * 1024)),
            )
        if upload.status_code not in {200, 201}:
            return {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "reason": "instagram_rupload_failed",
                "details": upload.text[:500],
            }

    if not container_id:
        return {"ok": False, "uploaded": False, "status": "failed", "reason": "instagram_missing_container_id"}

    ready, poll_error = _poll_container_ready(container_id=container_id, access_token=access_token, requests_module=requests)
    if not ready:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "instagram_container_not_ready",
            "details": poll_error,
            "container_id": container_id,
        }

    publish = requests.post(
        f"{GRAPH_BASE}/{account_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    if publish.status_code != 200:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "instagram_publish_failed",
            "details": publish.text[:500],
            "container_id": container_id,
        }

    publish_payload = publish.json() if publish.text else {}
    media_id = str(publish_payload.get("id") or container_id)
    return {
        "ok": True,
        "uploaded": True,
        "status": "uploaded",
        "platform": "instagram_reels",
        "privacy": str(profile.get("instagram_privacy") or "public"),
        "media_id": media_id,
        "post_url": f"https://www.instagram.com/reel/{media_id}/" if media_id else "",
        "upload_time": _now_iso(),
        "version": INSTAGRAM_UPLOADER_VERSION,
    }


__all__ = ["INSTAGRAM_UPLOADER_VERSION", "upload_reel_to_instagram"]
