"""YouTube OAuth helper — token storage and auth status."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.platform.json_utf8 import dumps_json

YOUTUBE_AUTH_VERSION = "youtube_auth_v2"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
]
TOKEN_FILENAME = "youtube_oauth_token.json"
TOKEN_SECRETS_FILENAME = "youtube_token.json"
ACCOUNT_FILENAME = "youtube_account.json"
LOCAL_CREDENTIALS = Path("project_brain") / "local_credentials" / "credentials.local.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_path(project_root: Path) -> Path:
    """Canonical OAuth token path used by youtube_uploader via get_valid_access_token()."""
    return project_root / "project_brain" / "upload" / TOKEN_FILENAME


def _token_secrets_path(project_root: Path) -> Path:
    """User-visible mirror path under secrets/ (written on every save)."""
    return project_root / "secrets" / TOKEN_SECRETS_FILENAME


def resolve_token_paths(project_root: Path) -> list[Path]:
    """All token locations checked on load (first match wins)."""
    root = Path(project_root).resolve()
    return [
        _token_path(root),
        _token_secrets_path(root),
        root / "secrets" / "token.json",
    ]


def resolve_oauth_client_path(project_root: Path, profile: dict[str, Any]) -> Path | None:
    configured = str(profile.get("youtube_oauth_client_path") or "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
        if not Path(configured).is_absolute():
            candidates.append(project_root / configured)
    candidates.extend(
        [
            project_root / "project_brain" / "local_credentials" / "youtube_client_secret.json",
            project_root / "project_brain" / "local_credentials" / "client_secret.json",
            project_root / LOCAL_CREDENTIALS,
        ]
    )
    secrets_dir = project_root / "secrets"
    if secrets_dir.is_dir():
        for match in sorted(secrets_dir.glob("client_secret*.json")):
            candidates.append(match)
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else (project_root / candidate)
        if resolved.is_file():
            return resolved.resolve()
    return None


def load_oauth_client(project_root: Path, profile: dict[str, Any]) -> dict[str, Any] | None:
    path = resolve_oauth_client_path(project_root, profile)
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and "installed" in payload:
        return dict(payload["installed"])
    if isinstance(payload, dict) and "web" in payload:
        return dict(payload["web"])
    if isinstance(payload, dict) and payload.get("client_id"):
        return payload
    return None


def load_token(project_root: Path) -> dict[str, Any] | None:
    for path in resolve_token_paths(project_root):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("access_token"):
            return payload
    return None


def save_token(project_root: Path, token: dict[str, Any]) -> Path:
    root = Path(project_root).resolve()
    payload = dict(token)
    payload["updated_at"] = _now()
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    primary = _token_path(root)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(encoded, encoding="utf-8")
    mirror = _token_secrets_path(root)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(encoded, encoding="utf-8")
    return primary


def _account_path(project_root: Path) -> Path:
    return project_root / "project_brain" / "upload" / ACCOUNT_FILENAME


def save_account_info(project_root: Path, account: dict[str, Any]) -> Path:
    path = _account_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(account)
    payload["updated_at"] = _now()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_account_info(project_root: Path) -> dict[str, Any] | None:
    path = _account_path(project_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def fetch_and_store_channel_info(project_root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    access_token = get_valid_access_token(project_root, profile)
    if not access_token:
        return {"ok": False, "reason": "not_authenticated"}
    try:
        import requests

        response = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        payload = response.json()
        if not response.ok:
            return {"ok": False, "reason": "channel_fetch_failed", "details": payload}
        items = list(payload.get("items") or [])
        if not items:
            return {"ok": False, "reason": "channel_not_found"}
        channel = items[0]
        snippet = dict(channel.get("snippet") or {})
        account = {
            "youtube_account_id": str(snippet.get("channelId") or channel.get("id") or ""),
            "channel_id": str(channel.get("id") or ""),
            "channel_name": str(snippet.get("title") or ""),
            "channel_title": str(snippet.get("title") or ""),
        }
        save_account_info(project_root, account)
        return {"ok": True, **account}
    except Exception as exc:
        return {"ok": False, "reason": "channel_fetch_exception", "error": str(exc)}


def get_youtube_auth_status(project_root: str | Path, profile: dict[str, Any]) -> dict[str, Any]:
    root = Path(project_root).resolve()
    client = load_oauth_client(root, profile)
    token = load_token(root)
    account = load_account_info(root) or {}
    authenticated = bool(token and token.get("access_token"))
    refreshable = bool(token and token.get("refresh_token"))
    client_path = resolve_oauth_client_path(root, profile)
    return {
        "version": YOUTUBE_AUTH_VERSION,
        "enabled": bool(profile.get("youtube_upload_enabled")),
        "credentials_configured": client is not None or bool(profile.get("youtube_credentials_configured")),
        "oauth_client_path": str(client_path) if client_path else "",
        "authenticated": authenticated,
        "refreshable": refreshable,
        "connect_required": bool(profile.get("youtube_upload_enabled")) and not authenticated,
        "token_path": str(_token_path(root)),
        "token_secrets_path": str(_token_secrets_path(root)),
        "token_search_paths": [str(path) for path in resolve_token_paths(root)],
        "youtube_account_id": str(account.get("youtube_account_id") or account.get("channel_id") or ""),
        "channel_id": str(account.get("channel_id") or ""),
        "channel_name": str(account.get("channel_name") or account.get("channel_title") or ""),
        "account_path": str(_account_path(root)),
    }


def build_oauth_authorization_url(project_root: Path, profile: dict[str, Any], *, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob") -> dict[str, Any]:
    client = load_oauth_client(project_root, profile)
    if client is None:
        return {"ok": False, "reason": "oauth_client_missing"}
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        client_id = str(client.get("client_id") or "")
        if not client_id:
            return {"ok": False, "reason": "oauth_client_invalid"}
        scope = " ".join(YOUTUBE_SCOPES)
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&access_type=offline&prompt=consent"
        )
        return {"ok": True, "authorization_url": url, "redirect_uri": redirect_uri, "method": "manual_url"}

    client_path = resolve_oauth_client_path(project_root, profile)
    flow = Flow.from_client_secrets_file(str(client_path), scopes=YOUTUBE_SCOPES)
    flow.redirect_uri = redirect_uri
    auth_url, _state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return {"ok": True, "authorization_url": auth_url, "redirect_uri": redirect_uri, "state": _state, "method": "google_auth_oauthlib"}


def exchange_authorization_code(project_root: Path, profile: dict[str, Any], code: str, *, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob") -> dict[str, Any]:
    client_path = resolve_oauth_client_path(project_root, profile)
    if client_path is None:
        return {"ok": False, "reason": "oauth_client_missing"}
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(str(client_path), scopes=YOUTUBE_SCOPES)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=str(code or "").strip())
        credentials = flow.credentials
        token = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes or YOUTUBE_SCOPES),
        }
        save_token(project_root, token)
        channel_info = fetch_and_store_channel_info(project_root, profile)
        return {
            "ok": True,
            "authenticated": True,
            "token_path": str(_token_path(project_root)),
            "channel": channel_info,
        }
    except ImportError:
        return {"ok": False, "reason": "google_auth_oauthlib_not_installed"}
    except Exception as exc:
        return {"ok": False, "reason": "oauth_exchange_failed", "error": str(exc)}


def refresh_access_token(project_root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    token = load_token(project_root)
    client = load_oauth_client(project_root, profile)
    if token is None or client is None:
        return {"ok": False, "reason": "token_or_client_missing"}

    refresh_token = str(token.get("refresh_token") or "").strip()
    if not refresh_token:
        return {"ok": False, "reason": "refresh_token_missing"}

    try:
        import requests

        response = requests.post(
            str(token.get("token_uri") or "https://oauth2.googleapis.com/token"),
            data={
                "client_id": str(token.get("client_id") or client.get("client_id") or ""),
                "client_secret": str(token.get("client_secret") or client.get("client_secret") or ""),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        payload = response.json()
        if response.ok and payload.get("access_token"):
            token["access_token"] = payload["access_token"]
            if payload.get("refresh_token"):
                token["refresh_token"] = payload["refresh_token"]
            save_token(project_root, token)
            return {"ok": True, "access_token": token["access_token"]}
        return {"ok": False, "reason": "refresh_failed", "details": payload}
    except Exception as exc:
        return {"ok": False, "reason": "refresh_exception", "error": str(exc)}


def get_valid_access_token(project_root: Path, profile: dict[str, Any]) -> str:
    token = load_token(project_root)
    if not token or not token.get("access_token"):
        return ""
    # Best-effort refresh when refresh token exists; token expiry is not tracked in V1.
    if token.get("refresh_token"):
        refreshed = refresh_access_token(project_root, profile)
        if refreshed.get("ok"):
            return str(refreshed.get("access_token") or "")
    return str(token.get("access_token") or "")


__all__ = [
    "ACCOUNT_FILENAME",
    "TOKEN_FILENAME",
    "TOKEN_SECRETS_FILENAME",
    "YOUTUBE_AUTH_VERSION",
    "build_oauth_authorization_url",
    "exchange_authorization_code",
    "fetch_and_store_channel_info",
    "get_valid_access_token",
    "get_youtube_auth_status",
    "load_account_info",
    "load_oauth_client",
    "resolve_oauth_client_path",
    "resolve_token_paths",
    "refresh_access_token",
    "save_account_info",
    "save_token",
]
