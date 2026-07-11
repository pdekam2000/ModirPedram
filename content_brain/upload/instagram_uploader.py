"""Instagram Reels upload via Meta Graph API (Instagram Login + Facebook Login)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.upload.instagram_auth import (
    FACEBOOK_GRAPH_HOST,
    resolve_instagram_api_context,
)
from content_brain.upload.instagram_video_stager import (
    build_instagram_public_video_url,
    stage_local_video_for_instagram,
)

INSTAGRAM_UPLOADER_VERSION = "instagram_uploader_v2_instagram_login"
GRAPH_API_VERSION = "v19.0"
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
        "instagram_public_base_url",
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


def _poll_container_ready(
    *,
    api_host: str,
    container_id: str,
    access_token: str,
    requests_module: Any,
) -> tuple[bool, str]:
    for _ in range(POLL_MAX_ATTEMPTS):
        response = requests_module.get(
            f"{api_host}/{container_id}",
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


def _create_reel_container_video_url(
    *,
    api_host: str,
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption_text: str,
    requests_module: Any,
) -> tuple[str, str]:
    response = requests_module.post(
        f"{api_host}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption_text,
            "access_token": access_token,
        },
        timeout=60,
    )
    if response.status_code != 200:
        return "", response.text[:500]
    container_id = str((response.json() or {}).get("id") or "")
    if not container_id:
        return "", "instagram_missing_container_id"
    return container_id, ""


def _upload_resumable_facebook_login(
    *,
    account_id: str,
    access_token: str,
    caption_text: str,
    path: Path,
    requests_module: Any,
) -> tuple[str, str]:
    file_size = path.stat().st_size
    create = requests_module.post(
        f"{FACEBOOK_GRAPH_HOST}/{account_id}/media",
        data={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption_text,
            "access_token": access_token,
        },
        timeout=60,
    )
    if create.status_code != 200:
        return "", create.text[:500]
    container_id = str((create.json() or {}).get("id") or "")
    if not container_id:
        return "", "instagram_missing_container_id"

    with path.open("rb") as handle:
        upload = requests_module.post(
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
        return "", upload.text[:500]
    return container_id, ""


def _publish_container(
    *,
    api_host: str,
    ig_user_id: str,
    container_id: str,
    access_token: str,
    requests_module: Any,
) -> tuple[dict[str, Any], str]:
    publish = requests_module.post(
        f"{api_host}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    if publish.status_code != 200:
        return {}, publish.text[:500]
    return publish.json() if publish.text else {}, ""


def upload_reel_to_instagram(
    *,
    profile: dict[str, Any],
    video_path: str | Path,
    title: str = "",
    caption: str = "",
    hashtags: list[str] | None = None,
    video_url: str = "",
    run_id: str = "",
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Upload a Reel to Instagram using Instagram Login or Facebook Login tokens."""
    profile = _load_channel_profile(profile, project_root)
    access_token = str(profile.get("instagram_access_token") or "").strip()
    if not access_token:
        return {
            "ok": False,
            "uploaded": False,
            "status": "blocked",
            "reason": "instagram_credentials_missing",
            "platform": "instagram_reels",
        }

    api_context = resolve_instagram_api_context(profile)
    if not api_context.get("ok"):
        return {
            "ok": False,
            "uploaded": False,
            "status": "blocked",
            "reason": "instagram_token_invalid",
            "details": str(api_context.get("message") or ""),
            "token_kind": str(api_context.get("token_kind") or ""),
            "platform": "instagram_reels",
        }

    api_host = str(api_context.get("api_host") or FACEBOOK_GRAPH_HOST)
    ig_user_id = str(api_context.get("ig_user_id") or profile.get("instagram_account_id") or "").strip()
    token_kind = str(api_context.get("token_kind") or "")
    caption_text = _build_caption(title=title, caption=caption, hashtags=list(hashtags or []))
    path = Path(video_path) if video_path else None

    try:
        import requests
    except ImportError:
        return {"ok": False, "uploaded": False, "status": "failed", "reason": "requests_unavailable"}

    public_url = str(video_url or profile.get("instagram_video_public_url") or "").strip()
    container_id = ""
    details = ""
    upload_method = ""

    if token_kind == "facebook_login" and path and path.is_file():
        upload_method = "resumable_facebook_login"
        container_id, details = _upload_resumable_facebook_login(
            account_id=ig_user_id,
            access_token=access_token,
            caption_text=caption_text,
            path=path,
            requests_module=requests,
        )
        if not container_id:
            return {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "reason": "instagram_resumable_init_failed",
                "details": details,
                "token_kind": token_kind,
            }
    else:
        upload_method = "video_url_instagram_login"
        if not public_url and str(run_id or "").strip() and project_root is not None:
            staged = build_instagram_public_video_url(
                project_root=project_root,
                profile=profile,
                run_id=run_id,
            )
            if staged.get("ok"):
                public_url = str(staged.get("public_url") or "")
            elif token_kind == "instagram_login":
                return {
                    "ok": False,
                    "uploaded": False,
                    "status": "blocked",
                    "reason": "instagram_public_video_url_required",
                    "details": str(staged.get("message") or ""),
                    "token_kind": token_kind,
                    "upload_method": upload_method,
                    "public_url": str(staged.get("public_url") or ""),
                }
        if not public_url and path and path.is_file() and project_root is not None:
            staged = stage_local_video_for_instagram(
                video_path=path,
                project_root=project_root,
                profile=profile,
                run_id=run_id,
            )
            if staged.get("ok"):
                public_url = str(staged.get("public_url") or "")
            elif token_kind == "instagram_login":
                return {
                    "ok": False,
                    "uploaded": False,
                    "status": "blocked",
                    "reason": "instagram_public_video_url_required",
                    "details": str(staged.get("message") or ""),
                    "token_kind": token_kind,
                    "upload_method": upload_method,
                }

        if not public_url:
            return {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "reason": "instagram_video_url_missing",
                "details": "Provide video_url or configure instagram_public_base_url for local files.",
                "token_kind": token_kind,
            }

        container_id, details = _create_reel_container_video_url(
            api_host=api_host,
            ig_user_id=ig_user_id,
            access_token=access_token,
            video_url=public_url,
            caption_text=caption_text,
            requests_module=requests,
        )
        if token_kind == "facebook_login":
            upload_method = "video_url_facebook_login"
        if not container_id:
            return {
                "ok": False,
                "uploaded": False,
                "status": "failed",
                "reason": "instagram_media_create_failed",
                "details": details,
                "token_kind": token_kind,
            }

    ready, poll_error = _poll_container_ready(
        api_host=api_host,
        container_id=container_id,
        access_token=access_token,
        requests_module=requests,
    )
    if not ready:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "instagram_container_not_ready",
            "details": poll_error,
            "container_id": container_id,
            "token_kind": token_kind,
        }

    publish_payload, publish_error = _publish_container(
        api_host=api_host,
        ig_user_id=ig_user_id,
        container_id=container_id,
        access_token=access_token,
        requests_module=requests,
    )
    if publish_error:
        return {
            "ok": False,
            "uploaded": False,
            "status": "failed",
            "reason": "instagram_publish_failed",
            "details": publish_error,
            "container_id": container_id,
            "token_kind": token_kind,
        }

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
        "token_kind": token_kind,
        "api_host": api_host,
        "ig_user_id": ig_user_id,
        "upload_method": upload_method,
    }


__all__ = ["INSTAGRAM_UPLOADER_VERSION", "upload_reel_to_instagram"]
