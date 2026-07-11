"""Stage local videos for Instagram video_url publishing (Instagram Login tokens)."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

STAGING_SUBDIR = Path("project_brain") / "staging" / "instagram_public"
DEFAULT_PUBLIC_BASE_URL = "http://127.0.0.1:8765"


def _public_base_url(profile: dict[str, Any]) -> str:
    return str(
        os.getenv("INSTAGRAM_PUBLIC_BASE_URL")
        or profile.get("instagram_public_base_url")
        or profile.get("instagram_video_public_url")
        or DEFAULT_PUBLIC_BASE_URL
    ).strip().rstrip("/")


def _is_local_base_url(base_url: str) -> bool:
    host = str(urlparse(base_url).hostname or "").lower()
    return host in {"", "localhost", "127.0.0.1", "::1"}


def build_instagram_public_video_url(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    run_id: str = "",
) -> dict[str, Any]:
    """Build a public video URL for Instagram Graph API video_url uploads."""
    base_url = _public_base_url(profile)
    run_id_text = str(run_id or "").strip()
    if not run_id_text:
        return {"ok": False, "message": "run_id_missing"}

    from content_brain.upload.media_video_resolver import resolve_pwmap_run_video

    video_path = resolve_pwmap_run_video(project_root, run_id_text)
    if video_path is None:
        return {"ok": False, "message": f"video_not_found_for_run:{run_id_text}"}

    public_url = f"{base_url}/media/video/{run_id_text}"
    if _is_local_base_url(base_url):
        return {
            "ok": False,
            "message": (
                "Instagram requires a public HTTPS URL (not localhost). "
                "Set instagram_public_base_url to your ngrok URL (e.g. https://abc.ngrok.io)."
            ),
            "public_url": public_url,
            "video_path": str(video_path),
        }

    return {
        "ok": True,
        "public_url": public_url,
        "video_path": str(video_path),
        "base_url": base_url,
        "run_id": run_id_text,
    }


def stage_local_video_for_instagram(
    *,
    video_path: str | Path,
    project_root: str | Path,
    profile: dict[str, Any],
    run_id: str = "",
) -> dict[str, Any]:
    """Return a public video URL for Instagram Login tokens."""
    if str(run_id or "").strip():
        media_url = build_instagram_public_video_url(
            project_root=project_root,
            profile=profile,
            run_id=run_id,
        )
        if media_url.get("ok"):
            return media_url

    path = Path(video_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "message": "video_missing"}

    base_url = _public_base_url(profile)
    if not base_url:
        return {
            "ok": False,
            "message": (
                "Instagram Login tokens require a public video URL. "
                "Set instagram_public_base_url in channel profile (e.g. your ngrok URL) "
                "or INSTAGRAM_PUBLIC_BASE_URL in .env."
            ),
        }

    if _is_local_base_url(base_url):
        return {
            "ok": False,
            "message": (
                "Instagram requires a public HTTPS URL (not localhost). "
                "Set instagram_public_base_url to your ngrok URL (e.g. https://abc.ngrok.io)."
            ),
        }

    root = Path(project_root).resolve()
    staging_dir = root / STAGING_SUBDIR
    staging_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(f"{path.resolve()}:{path.stat().st_size}:{secrets.token_hex(4)}".encode()).hexdigest()[:16]
    token = digest
    staged_path = staging_dir / f"{token}.mp4"
    shutil.copy2(path, staged_path)

    public_url = f"{base_url}/upload/instagram/public/{token}.mp4"
    return {
        "ok": True,
        "public_url": public_url,
        "staged_path": str(staged_path),
        "token": token,
    }


def resolve_staged_video_path(project_root: str | Path, token: str) -> Path | None:
    safe = "".join(ch for ch in str(token or "") if ch.isalnum())
    if not safe:
        return None
    path = Path(project_root).resolve() / STAGING_SUBDIR / f"{safe}.mp4"
    return path if path.is_file() else None


__all__ = [
    "DEFAULT_PUBLIC_BASE_URL",
    "STAGING_SUBDIR",
    "build_instagram_public_video_url",
    "resolve_staged_video_path",
    "stage_local_video_for_instagram",
]
