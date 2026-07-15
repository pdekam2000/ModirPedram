"""YouTube Data API upload client — resumable upload, metadata, thumbnail, scheduling."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.upload.upload_models import PRIVACY_PRIVATE
from content_brain.upload.youtube_auth import get_valid_access_token
from content_brain.upload.youtube_category_map import resolve_youtube_category_id

logger = logging.getLogger(__name__)

YOUTUBE_UPLOADER_VERSION = "youtube_uploader_v2"
YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
THUMBNAIL_UPLOAD_ATTEMPTS = 4
THUMBNAIL_RETRY_DELAYS_SECONDS = (2, 5, 10, 20)


def extract_youtube_video_id(*candidates: Any) -> str:
    """Pull a YouTube video id from a raw id or watch/short URL."""
    for raw in candidates:
        text = str(raw or "").strip()
        if not text:
            continue
        if re.fullmatch(r"[\w-]{6,}", text):
            return text
        for pattern in (
            r"[?&]v=([\w-]{6,})",
            r"youtu\.be/([\w-]{6,})",
            r"youtube\.com/shorts/([\w-]{6,})",
            r"youtube\.com/embed/([\w-]{6,})",
        ):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return ""


def _safe_privacy(value: str) -> str:
    privacy = str(value or PRIVACY_PRIVATE).strip().lower()
    if privacy not in {PRIVACY_PRIVATE, "unlisted", "public"}:
        return PRIVACY_PRIVATE
    return privacy


def _append_hashtags(description: str, hashtags: list[str]) -> str:
    base = str(description or "").strip()
    tags = [str(item).strip() for item in hashtags if str(item).strip()]
    if not tags:
        return base
    missing = [tag for tag in tags if tag.lower().lstrip("#") not in base.lower()]
    if not missing:
        return base
    suffix = " ".join(missing)
    return f"{base}\n\n{suffix}".strip()


def _normalize_publish_at(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except ValueError:
        return ""


def add_video_to_youtube_playlist(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    video_id: str,
    playlist_id: str = "",
) -> dict[str, Any]:
    resolved_playlist = str(playlist_id or profile.get("youtube_playlist_id") or "").strip()
    if not resolved_playlist:
        return {"ok": False, "status": "skipped", "reason": "playlist_id_not_configured"}
    if not str(video_id or "").strip():
        return {"ok": False, "status": "failed", "reason": "video_id_missing"}

    access_token = get_valid_access_token(Path(project_root).resolve(), profile)
    if not access_token:
        return {"ok": False, "status": "failed", "reason": "youtube_not_authenticated"}

    try:
        import requests

        response = requests.post(
            YOUTUBE_PLAYLIST_ITEMS_URL,
            params={"part": "snippet"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={
                "snippet": {
                    "playlistId": resolved_playlist,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": str(video_id),
                    },
                }
            },
            timeout=60,
        )
        if response.status_code not in {200, 201}:
            return {
                "ok": False,
                "status": "failed",
                "reason": "playlist_insert_failed",
                "http_status": response.status_code,
                "details": response.text[:500],
            }
        payload = response.json() if response.text else {}
        return {
            "ok": True,
            "status": "added",
            "playlist_id": resolved_playlist,
            "video_id": video_id,
            "playlist_item_id": str(payload.get("id") or ""),
        }
    except Exception as exc:
        return {"ok": False, "status": "failed", "reason": "playlist_insert_exception", "error": str(exc)}


def upload_thumbnail_to_youtube(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    video_id: str,
    thumbnail_path: str | Path,
) -> dict[str, Any]:
    path = Path(thumbnail_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "status": "skipped", "reason": "thumbnail_missing"}

    resolved_id = extract_youtube_video_id(video_id)
    if not resolved_id:
        return {"ok": False, "status": "failed", "reason": "video_id_missing"}

    content_type = "image/jpeg"
    suffix = path.suffix.lower()
    if suffix == ".png":
        content_type = "image/png"
    elif suffix == ".webp":
        content_type = "image/webp"

    last_error: dict[str, Any] = {}
    try:
        import requests
    except ImportError:
        return {"ok": False, "status": "failed", "reason": "requests_unavailable"}

    for attempt in range(1, THUMBNAIL_UPLOAD_ATTEMPTS + 1):
        access_token = get_valid_access_token(Path(project_root).resolve(), profile)
        if not access_token:
            return {"ok": False, "status": "failed", "reason": "youtube_not_authenticated"}
        try:
            with path.open("rb") as handle:
                payload = handle.read()
            response = requests.post(
                YOUTUBE_THUMBNAIL_URL,
                params={"videoId": resolved_id},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": content_type,
                },
                data=payload,
                timeout=120,
            )
            if response.status_code in {200, 201}:
                return {
                    "ok": True,
                    "status": "uploaded",
                    "video_id": resolved_id,
                    "thumbnail_path": str(path.resolve()),
                    "attempts": attempt,
                }
            details = response.text[:500]
            last_error = {
                "ok": False,
                "status": "failed",
                "reason": "thumbnail_upload_failed",
                "http_status": response.status_code,
                "details": details,
                "attempts": attempt,
            }
            retryable = response.status_code in {409, 429, 500, 503} or any(
                marker in details.lower()
                for marker in ("processing", "failedprecondition", "not been processed", "backenderror")
            )
            if not retryable or attempt >= THUMBNAIL_UPLOAD_ATTEMPTS:
                return last_error
            delay = THUMBNAIL_RETRY_DELAYS_SECONDS[min(attempt - 1, len(THUMBNAIL_RETRY_DELAYS_SECONDS) - 1)]
            logger.warning(
                "Thumbnail upload retry %s/%s for %s after HTTP %s (sleep %ss)",
                attempt,
                THUMBNAIL_UPLOAD_ATTEMPTS,
                resolved_id,
                response.status_code,
                delay,
            )
            time.sleep(delay)
        except Exception as exc:
            last_error = {
                "ok": False,
                "status": "failed",
                "reason": "thumbnail_upload_exception",
                "error": str(exc),
                "attempts": attempt,
            }
            if attempt >= THUMBNAIL_UPLOAD_ATTEMPTS:
                return last_error
            delay = THUMBNAIL_RETRY_DELAYS_SECONDS[min(attempt - 1, len(THUMBNAIL_RETRY_DELAYS_SECONDS) - 1)]
            time.sleep(delay)
    return last_error or {"ok": False, "status": "failed", "reason": "thumbnail_upload_failed"}


def upload_video_to_youtube(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    video_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy: str = PRIVACY_PRIVATE,
    made_for_kids: bool | None = None,
    category_id: str = "28",
    category: str = "",
    language: str = "en",
    hashtags: list[str] | None = None,
    publish_at: str = "",
    publish_now: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "status": "failed", "reason": "video_missing", "uploaded": False}

    access_token = get_valid_access_token(root, profile)
    if not access_token:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "youtube_not_authenticated",
            "connect_required": True,
            "uploaded": False,
        }

    privacy_status = _safe_privacy(str(privacy or profile.get("youtube_privacy") or PRIVACY_PRIVATE))
    kids = bool(profile.get("youtube_made_for_kids", False)) if made_for_kids is None else bool(made_for_kids)
    resolved_category = resolve_youtube_category_id(category or category_id)
    description_text = _append_hashtags(description, list(hashtags or []))
    publish_at_iso = _normalize_publish_at(publish_at)
    scheduled = bool(publish_at_iso) and not publish_now

    status_block: dict[str, Any] = {
        "privacyStatus": "private" if scheduled else "public",
        "selfDeclaredMadeForKids": kids,
    }
    if scheduled:
        status_block["publishAt"] = publish_at_iso

    metadata = {
        "snippet": {
            "title": str(title or "Untitled Short")[:100],
            "description": description_text[:4900],
            "tags": [str(item).strip() for item in (tags or []) if str(item).strip()][:30],
            "categoryId": resolved_category,
            "defaultLanguage": str(language or "en")[:10],
        },
        "status": status_block,
    }

    try:
        import requests
    except ImportError:
        return {"ok": False, "status": "failed", "reason": "requests_unavailable", "uploaded": False}

    upload_time = datetime.now(timezone.utc).isoformat()
    try:
        init = requests.post(
            YOUTUBE_UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(path.stat().st_size),
            },
            data=json.dumps(metadata, ensure_ascii=False),
            timeout=60,
        )
        if init.status_code not in {200, 201}:
            return {
                "ok": False,
                "status": "failed",
                "reason": "youtube_init_failed",
                "http_status": init.status_code,
                "details": init.text[:500],
                "privacy": privacy_status,
                "uploaded": False,
            }

        upload_url = init.headers.get("Location", "")
        if not upload_url:
            return {
                "ok": False,
                "status": "failed",
                "reason": "missing_upload_location",
                "privacy": privacy_status,
                "uploaded": False,
            }

        with path.open("rb") as handle:
            upload = requests.put(
                upload_url,
                data=handle,
                headers={"Content-Type": "video/mp4"},
                timeout=max(120, path.stat().st_size // (1024 * 512)),
            )
        if upload.status_code not in {200, 201}:
            return {
                "ok": False,
                "status": "failed",
                "reason": "youtube_upload_failed",
                "http_status": upload.status_code,
                "details": upload.text[:500],
                "privacy": privacy_status,
                "uploaded": False,
            }

        payload = upload.json() if upload.text else {}
        video_id = str(payload.get("id") or "")
        effective_visibility = "private" if scheduled else privacy_status
        effective_publish_time = publish_at_iso if scheduled else upload_time
        playlist_result: dict[str, Any] = {"ok": False, "status": "skipped", "reason": "playlist_id_not_configured"}
        thumbnail_result: dict[str, Any] = {"ok": False, "status": "skipped", "reason": "thumbnail_not_attempted"}
        if video_id and not scheduled:
            playlist_result = add_video_to_youtube_playlist(
                project_root=root,
                profile=profile,
                video_id=video_id,
            )
            from content_brain.branding.thumbnail_generator import maybe_generate_and_upload_youtube_thumbnail

            # YouTube often rejects custom thumbnails until the new video finishes initial processing.
            time.sleep(3)
            thumbnail_result = maybe_generate_and_upload_youtube_thumbnail(
                project_root=root,
                profile=profile,
                video_path=path,
                video_id=video_id,
                title=str(title or ""),
            )
            if thumbnail_result.get("ok"):
                logger.info("Thumbnail uploaded: %s", thumbnail_result.get("thumbnail_path"))
            else:
                logger.warning(
                    "Thumbnail upload failed for %s: %s",
                    video_id,
                    (thumbnail_result.get("upload_result") or {}).get("reason")
                    or thumbnail_result.get("reason")
                    or thumbnail_result,
                )
        return {
            "ok": True,
            "status": "scheduled" if scheduled else "uploaded",
            "uploaded": True,
            "privacy": effective_visibility,
            "visibility": effective_visibility,
            "publish_time": effective_publish_time,
            "upload_time": upload_time,
            "scheduled": scheduled,
            "video_id": video_id,
            "youtube_video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            "playlist_result": playlist_result,
            "thumbnail_result": thumbnail_result,
            "thumbnail_path": str(thumbnail_result.get("thumbnail_path") or ""),
            "thumbnail_uploaded": bool(thumbnail_result.get("ok")),
            "response": payload,
            "version": YOUTUBE_UPLOADER_VERSION,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "failed",
            "reason": "youtube_upload_exception",
            "error": str(exc),
            "privacy": privacy_status,
            "uploaded": False,
        }


def delete_video_from_youtube(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    video_id: str,
) -> dict[str, Any]:
    """Delete a YouTube video by ID using the configured OAuth token."""
    resolved_id = str(video_id or "").strip()
    if not resolved_id:
        return {"ok": False, "status": "failed", "reason": "video_id_missing"}

    access_token = get_valid_access_token(Path(project_root).resolve(), profile)
    if not access_token:
        return {"ok": False, "status": "failed", "reason": "youtube_not_authenticated"}

    try:
        import requests

        response = requests.delete(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"id": resolved_id},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=60,
        )
        if response.status_code in {200, 204}:
            return {
                "ok": True,
                "status": "deleted",
                "video_id": resolved_id,
                "version": YOUTUBE_UPLOADER_VERSION,
            }
        return {
            "ok": False,
            "status": "failed",
            "reason": "youtube_delete_failed",
            "video_id": resolved_id,
            "details": response.text[:500],
            "http_status": response.status_code,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "failed",
            "reason": "youtube_delete_exception",
            "video_id": resolved_id,
            "error": str(exc),
        }


__all__ = [
    "YOUTUBE_UPLOADER_VERSION",
    "add_video_to_youtube_playlist",
    "delete_video_from_youtube",
    "extract_youtube_video_id",
    "upload_thumbnail_to_youtube",
    "upload_video_to_youtube",
]
