"""Instagram upload auth helpers — token kind detection and API routing."""

from __future__ import annotations

import os
from typing import Any

from content_brain.upload.instagram_token_exchange import GRAPH_API_VERSION

INSTAGRAM_LOGIN_HOST = f"https://graph.instagram.com/{GRAPH_API_VERSION}"
FACEBOOK_GRAPH_HOST = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def detect_instagram_token_kind(access_token: str) -> str:
    token = str(access_token or "").strip()
    if token.startswith("IG"):
        return "instagram_login"
    if token.startswith("EAA"):
        return "facebook_login"
    return "unknown"


def _instagram_me(access_token: str) -> dict[str, Any]:
    try:
        import requests
    except ImportError:
        return {"ok": False, "message": "requests_unavailable"}

    try:
        response = requests.get(
            f"{INSTAGRAM_LOGIN_HOST}/me",
            params={"fields": "id,username,user_id", "access_token": access_token},
            timeout=30,
        )
        payload = response.json() if response.text else {}
        if response.status_code == 200 and isinstance(payload, dict) and payload.get("id"):
            return {"ok": True, **payload}
        error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or error)
        return {"ok": False, "message": message or response.text[:300]}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def validate_instagram_credentials(
    *,
    access_token: str,
    account_id: str = "",
) -> dict[str, Any]:
    """Validate token and return API routing metadata."""
    token = str(access_token or "").strip()
    if not token:
        return {"ok": False, "message": "Instagram access token is empty.", "token_kind": "missing"}

    kind = detect_instagram_token_kind(token)
    if kind == "instagram_login":
        me = _instagram_me(token)
        if not me.get("ok"):
            return {
                "ok": False,
                "token_kind": kind,
                "message": str(me.get("message") or "Instagram token invalid on graph.instagram.com"),
            }
        return {
            "ok": True,
            "token_kind": kind,
            "api_host": INSTAGRAM_LOGIN_HOST,
            "ig_user_id": str(me.get("id") or ""),
            "instagram_business_user_id": str(me.get("user_id") or account_id or ""),
            "username": str(me.get("username") or ""),
            "supports_resumable": False,
            "supports_video_url": True,
            "message": "Instagram Login token valid.",
        }

    ig_id = str(account_id or "").strip()
    if not ig_id:
        return {
            "ok": False,
            "token_kind": kind,
            "message": "Facebook Login token requires instagram_account_id.",
        }

    try:
        import requests
    except ImportError:
        return {"ok": False, "token_kind": kind, "message": "requests_unavailable"}

    try:
        response = requests.get(
            f"{FACEBOOK_GRAPH_HOST}/{ig_id}",
            params={"fields": "id,username", "access_token": token},
            timeout=30,
        )
        payload = response.json() if response.text else {}
        if response.status_code == 200 and isinstance(payload, dict) and payload.get("id"):
            return {
                "ok": True,
                "token_kind": kind,
                "api_host": FACEBOOK_GRAPH_HOST,
                "ig_user_id": str(payload.get("id") or ig_id),
                "instagram_business_user_id": str(payload.get("id") or ig_id),
                "username": str(payload.get("username") or ""),
                "supports_resumable": True,
                "supports_video_url": True,
                "message": "Facebook Graph token valid.",
            }
        error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or error)
        return {
            "ok": False,
            "token_kind": kind,
            "message": message or response.text[:300],
        }
    except Exception as exc:
        return {"ok": False, "token_kind": kind, "message": str(exc)}


def resolve_instagram_api_context(profile: dict[str, Any]) -> dict[str, Any]:
    """Resolve upload API host + IG user id from profile credentials."""
    token = str(profile.get("instagram_access_token") or os.getenv("INSTAGRAM_ACCESS_TOKEN") or "").strip()
    account_id = str(profile.get("instagram_account_id") or os.getenv("INSTAGRAM_ACCOUNT_ID") or "").strip()
    validation = validate_instagram_credentials(access_token=token, account_id=account_id)
    if not validation.get("ok"):
        return validation
    return validation


def refresh_instagram_profile_ids(profile: dict[str, Any]) -> dict[str, Any]:
    """Update instagram_account_id from a valid token when possible."""
    updated = dict(profile or {})
    validation = resolve_instagram_api_context(updated)
    if not validation.get("ok"):
        return updated
    business_id = str(validation.get("instagram_business_user_id") or "").strip()
    if business_id:
        updated["instagram_account_id"] = business_id
    return updated


__all__ = [
    "FACEBOOK_GRAPH_HOST",
    "INSTAGRAM_LOGIN_HOST",
    "detect_instagram_token_kind",
    "refresh_instagram_profile_ids",
    "resolve_instagram_api_context",
    "validate_instagram_credentials",
]
