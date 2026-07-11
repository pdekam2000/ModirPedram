"""Exchange Instagram / Facebook short-lived tokens for long-lived tokens (60 days)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

GRAPH_API_VERSION = "v19.0"
EXCHANGE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"


def resolve_facebook_app_credentials(profile: dict[str, Any]) -> tuple[str, str]:
    """Resolve Meta app id + secret from profile fields or environment."""
    app_id = str(
        profile.get("instagram_app_id")
        or os.getenv("INSTAGRAM_APP_ID")
        or os.getenv("FACEBOOK_APP_ID")
        or os.getenv("META_APP_ID")
        or ""
    ).strip()
    app_secret = str(
        profile.get("instagram_app_secret")
        or os.getenv("INSTAGRAM_APP_SECRET")
        or os.getenv("FACEBOOK_APP_SECRET")
        or os.getenv("META_APP_SECRET")
        or ""
    ).strip()
    return app_id, app_secret


def exchange_short_lived_token(
    *,
    short_lived_token: str,
    app_id: str,
    app_secret: str,
) -> dict[str, Any]:
    """Call Meta oauth/access_token with grant_type=fb_exchange_token."""
    token = str(short_lived_token or "").strip()
    client_id = str(app_id or "").strip()
    client_secret = str(app_secret or "").strip()
    if not token:
        return {"ok": False, "message": "Instagram access token is empty."}
    if not client_id or not client_secret:
        return {
            "ok": False,
            "message": "Facebook App ID and App Secret are required to exchange the token.",
        }

    try:
        import requests
    except ImportError:
        return {"ok": False, "message": "requests package is not installed."}

    try:
        response = requests.get(
            EXCHANGE_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "fb_exchange_token": token,
            },
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "message": f"Token exchange request failed: {exc}"}

    try:
        payload = response.json() if response.text else {}
    except ValueError:
        payload = {"raw": response.text[:500]}

    if response.status_code != 200 or not isinstance(payload, dict) or not payload.get("access_token"):
        error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("type") or error)
        else:
            message = str(error or response.text[:300])
        return {"ok": False, "message": message or f"Token exchange failed (HTTP {response.status_code})."}

    expires_in = payload.get("expires_in")
    expires_at = ""
    if expires_in is not None:
        try:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            ).isoformat()
        except (TypeError, ValueError):
            expires_at = ""

    return {
        "ok": True,
        "access_token": str(payload["access_token"]),
        "expires_in": expires_in,
        "expires_at": expires_at,
        "token_type": str(payload.get("token_type") or "bearer"),
        "message": "Instagram token exchanged for long-lived token (60 days).",
    }


def maybe_exchange_instagram_token(
    *,
    short_lived_token: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Exchange token when app credentials are available."""
    token = str(short_lived_token or "").strip()
    if token.startswith("IG"):
        return {
            "ok": True,
            "access_token": token,
            "message": "Instagram Login token detected — no Facebook exchange needed.",
            "skipped": True,
        }
    app_id, app_secret = resolve_facebook_app_credentials(profile)
    return exchange_short_lived_token(
        short_lived_token=short_lived_token,
        app_id=app_id,
        app_secret=app_secret,
    )


__all__ = [
    "EXCHANGE_URL",
    "GRAPH_API_VERSION",
    "exchange_short_lived_token",
    "maybe_exchange_instagram_token",
    "resolve_facebook_app_credentials",
]
