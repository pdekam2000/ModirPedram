"""Exchange Instagram / Facebook short-lived tokens for long-lived tokens (60 days)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

GRAPH_API_VERSION = "v19.0"
EXCHANGE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
IG_EXCHANGE_URL = "https://graph.instagram.com/access_token"
IG_REFRESH_URL = "https://graph.instagram.com/refresh_access_token"


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


def _expires_at_from_seconds(expires_in: Any) -> str:
    if expires_in is None:
        return ""
    try:
        return (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        ).isoformat()
    except (TypeError, ValueError):
        return ""


def _parse_exchange_error(response: Any, payload: dict[str, Any]) -> str:
    error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
    if isinstance(error, dict):
        message = str(error.get("message") or error.get("type") or error)
    else:
        message = str(error or getattr(response, "text", "")[:300])
    status = getattr(response, "status_code", "?")
    return message or f"Token exchange failed (HTTP {status})."


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
        return {"ok": False, "message": _parse_exchange_error(response, payload if isinstance(payload, dict) else {})}

    expires_in = payload.get("expires_in")
    return {
        "ok": True,
        "access_token": str(payload["access_token"]),
        "expires_in": expires_in,
        "expires_at": _expires_at_from_seconds(expires_in),
        "token_type": str(payload.get("token_type") or "bearer"),
        "message": "Instagram token exchanged for long-lived token (60 days).",
    }


def exchange_instagram_login_token(
    *,
    access_token: str,
    app_secret: str = "",
) -> dict[str, Any]:
    """Exchange/refresh Instagram Login tokens (IG… prefix).

    Prefer refresh_access_token for already long-lived tokens.
    Fall back to ig_exchange_token when a short-lived IG token + app secret are available.
    """
    token = str(access_token or "").strip()
    if not token:
        return {"ok": False, "message": "Instagram access token is empty."}

    try:
        import requests
    except ImportError:
        return {"ok": False, "message": "requests package is not installed."}

    # 1) Refresh long-lived Instagram Login token (does not need app secret).
    try:
        refresh_response = requests.get(
            IG_REFRESH_URL,
            params={
                "grant_type": "ig_refresh_token",
                "access_token": token,
            },
            timeout=30,
        )
        try:
            refresh_payload = refresh_response.json() if refresh_response.text else {}
        except ValueError:
            refresh_payload = {"raw": refresh_response.text[:500]}
        if (
            refresh_response.status_code == 200
            and isinstance(refresh_payload, dict)
            and refresh_payload.get("access_token")
        ):
            expires_in = refresh_payload.get("expires_in")
            return {
                "ok": True,
                "access_token": str(refresh_payload["access_token"]),
                "expires_in": expires_in,
                "expires_at": _expires_at_from_seconds(expires_in),
                "token_type": str(refresh_payload.get("token_type") or "bearer"),
                "message": "Instagram Login token refreshed (long-lived, ~60 days).",
                "method": "ig_refresh_token",
            }
    except Exception as exc:
        refresh_error = f"IG refresh failed: {exc}"
    else:
        refresh_error = _parse_exchange_error(
            refresh_response,
            refresh_payload if isinstance(refresh_payload, dict) else {},
        )

    # 2) Short-lived → long-lived exchange (requires Instagram app secret).
    secret = str(app_secret or "").strip()
    if not secret:
        return {
            "ok": False,
            "message": (
                f"Instagram Login refresh failed ({refresh_error}). "
                "App secret required for ig_exchange_token fallback."
            ),
        }

    try:
        exchange_response = requests.get(
            IG_EXCHANGE_URL,
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": secret,
                "access_token": token,
            },
            timeout=30,
        )
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Instagram Login exchange failed after refresh error ({refresh_error}): {exc}",
        }

    try:
        exchange_payload = exchange_response.json() if exchange_response.text else {}
    except ValueError:
        exchange_payload = {"raw": exchange_response.text[:500]}

    if (
        exchange_response.status_code != 200
        or not isinstance(exchange_payload, dict)
        or not exchange_payload.get("access_token")
    ):
        exchange_error = _parse_exchange_error(
            exchange_response,
            exchange_payload if isinstance(exchange_payload, dict) else {},
        )
        return {
            "ok": False,
            "message": (
                f"Instagram Login refresh failed ({refresh_error}); "
                f"exchange failed ({exchange_error})."
            ),
        }

    expires_in = exchange_payload.get("expires_in")
    return {
        "ok": True,
        "access_token": str(exchange_payload["access_token"]),
        "expires_in": expires_in,
        "expires_at": _expires_at_from_seconds(expires_in),
        "token_type": str(exchange_payload.get("token_type") or "bearer"),
        "message": "Instagram Login token exchanged for long-lived token (~60 days).",
        "method": "ig_exchange_token",
    }


def maybe_exchange_instagram_token(
    *,
    short_lived_token: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Exchange/refresh token for Instagram Login (IG…) or Facebook Login tokens."""
    token = str(short_lived_token or "").strip()
    if token.startswith("IG"):
        _app_id, app_secret = resolve_facebook_app_credentials(profile)
        return exchange_instagram_login_token(access_token=token, app_secret=app_secret)
    app_id, app_secret = resolve_facebook_app_credentials(profile)
    return exchange_short_lived_token(
        short_lived_token=short_lived_token,
        app_id=app_id,
        app_secret=app_secret,
    )


__all__ = [
    "EXCHANGE_URL",
    "GRAPH_API_VERSION",
    "IG_EXCHANGE_URL",
    "IG_REFRESH_URL",
    "exchange_instagram_login_token",
    "exchange_short_lived_token",
    "maybe_exchange_instagram_token",
    "resolve_facebook_app_credentials",
]
