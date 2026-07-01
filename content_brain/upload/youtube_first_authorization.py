"""First-time YouTube OAuth authorization — browser flow, token persistence, refresh verify."""

from __future__ import annotations

import json
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore
from content_brain.upload.youtube_auth import (
    YOUTUBE_SCOPES,
    fetch_and_store_channel_info,
    load_account_info,
    load_oauth_client,
    load_token,
    refresh_access_token,
    resolve_oauth_client_path,
    save_token,
)

YOUTUBE_FIRST_AUTH_VERSION = "youtube_first_auth_v1"
YOUTUBE_AUTH_RESULT_NAME = "youtube_auth_result.json"
DEFAULT_OAUTH_PORT = 8080


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _auth_result_path(project_root: Path) -> Path:
    return project_root / "project_brain" / "upload" / YOUTUBE_AUTH_RESULT_NAME


def write_youtube_auth_result(project_root: str | Path, payload: dict[str, Any]) -> Path:
    root = Path(project_root).resolve()
    path = _auth_result_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["updated_at"] = _now_iso()
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_youtube_auth_result(project_root: str | Path) -> dict[str, Any] | None:
    path = _auth_result_path(Path(project_root).resolve())
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def discover_oauth_credentials(project_root: str | Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Locate downloaded Desktop OAuth JSON and expose client_id (never client_secret in API responses)."""
    root = Path(project_root).resolve()
    profile = profile or ProductChannelProfileStore(root).load()
    client_path = resolve_oauth_client_path(root, profile)
    client = load_oauth_client(root, profile) if client_path else None
    return {
        "ok": client_path is not None and client is not None,
        "oauth_client_path": str(client_path) if client_path else "",
        "client_id": str((client or {}).get("client_id") or ""),
        "credentials_configured": client_path is not None,
        "reason": "" if client_path else "oauth_client_missing",
    }


def get_youtube_oauth_readiness(project_root: str | Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Aggregate OAuth status for Results / Upload Center."""
    root = Path(project_root).resolve()
    profile = profile or ProductChannelProfileStore(root).load()
    from content_brain.upload.youtube_auth import get_youtube_auth_status

    auth = get_youtube_auth_status(root, profile)
    auth_result = load_youtube_auth_result(root) or {}
    credentials = discover_oauth_credentials(root, profile)
    upload_enabled = bool(profile.get("youtube_upload_enabled"))
    authorized = bool(auth.get("authenticated") and auth.get("refreshable"))
    credentials_ok = bool(credentials.get("credentials_configured") or auth.get("credentials_configured"))
    channel_name = str(auth.get("channel_name") or auth_result.get("channel_name") or "")
    channel_id = str(auth.get("channel_id") or auth_result.get("channel_id") or "")
    upload_ready = bool(credentials_ok and authorized and upload_enabled)

    if authorized:
        oauth_status = "authorized"
    elif credentials_ok:
        oauth_status = "credentials_ready"
    else:
        oauth_status = "not_configured"

    return {
        "oauth_status": oauth_status,
        "youtube_oauth_status": oauth_status,
        "youtube_authorized": authorized,
        "youtube_credentials_configured": credentials_ok,
        "youtube_oauth_client_path": str(credentials.get("oauth_client_path") or auth.get("oauth_client_path") or ""),
        "youtube_channel_id": channel_id,
        "youtube_channel_name": channel_name,
        "youtube_connected_channel": channel_name or channel_id or "",
        "youtube_upload_ready": upload_ready,
        "youtube_token_refresh_verified": bool(auth_result.get("token_refresh_verified")),
        "youtube_auth_result": auth_result,
    }


def _persist_credentials_path(project_root: Path, client_path: Path) -> None:
    store = ProductChannelProfileStore(project_root)
    store.save(
        {
            "youtube_oauth_client_path": str(client_path.resolve()).replace("\\", "/"),
            "youtube_credentials_configured": True,
        }
    )


def _token_from_credentials(credentials: Any) -> dict[str, Any]:
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or YOUTUBE_SCOPES),
    }


def _run_oauth_local_server(
    project_root: Path,
    client_path: Path,
    *,
    port: int = DEFAULT_OAUTH_PORT,
    open_browser: bool = True,
) -> dict[str, Any]:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes=YOUTUBE_SCOPES)
        credentials = flow.run_local_server(
            port=port,
            open_browser=open_browser,
            prompt="consent",
            access_type="offline",
            authorization_prompt_message="Opening browser for YouTube authorization…",
            success_message="YouTube authorization complete. You may close this window.",
        )
        token = _token_from_credentials(credentials)
        save_token(project_root, token)
        return {"ok": True, "method": "google_auth_oauthlib_local_server", "token_saved": True}
    except ImportError:
        return _run_oauth_manual_localhost(project_root, client_path, port=port, open_browser=open_browser)
    except Exception as exc:
        return {"ok": False, "reason": "oauth_local_server_failed", "error": str(exc)}


def _run_oauth_manual_localhost(
    project_root: Path,
    client_path: Path,
    *,
    port: int = DEFAULT_OAUTH_PORT,
    open_browser: bool = True,
) -> dict[str, Any]:
    client_payload = json.loads(client_path.read_text(encoding="utf-8"))
    installed = client_payload.get("installed") or client_payload.get("web") or client_payload
    client_id = str(installed.get("client_id") or "")
    client_secret = str(installed.get("client_secret") or "")
    token_uri = str(installed.get("token_uri") or "https://oauth2.googleapis.com/token")
    if not client_id or not client_secret:
        return {"ok": False, "reason": "oauth_client_invalid"}

    redirect_uri = f"http://localhost:{port}/"
    scope = " ".join(YOUTUBE_SCOPES)
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": scope,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
            }
        )
    )

    captured: dict[str, str] = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            captured["code"] = str((params.get("code") or [""])[0])
            captured["error"] = str((params.get("error") or [""])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>YouTube authorization complete.</h2>"
                b"<p>You can close this window and return to ModirAgentOS.</p></body></html>"
            )

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = HTTPServer(("localhost", port), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    if open_browser:
        webbrowser.open(auth_url, new=1)
    thread.join(timeout=300)
    server.server_close()

    if captured.get("error"):
        return {"ok": False, "reason": "oauth_denied", "error": captured["error"]}
    code = str(captured.get("code") or "").strip()
    if not code:
        return {"ok": False, "reason": "oauth_code_missing", "authorization_url": auth_url}

    import requests

    response = requests.post(
        token_uri,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    payload = response.json()
    if not response.ok or not payload.get("access_token"):
        return {"ok": False, "reason": "oauth_token_exchange_failed", "details": payload}

    token = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token") or "",
        "token_uri": token_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": YOUTUBE_SCOPES,
    }
    save_token(project_root, token)
    return {"ok": True, "method": "manual_localhost", "token_saved": True, "authorization_url": auth_url}


def run_first_youtube_authorization(
    project_root: str | Path,
    *,
    open_browser: bool = True,
    port: int = DEFAULT_OAUTH_PORT,
    enable_upload: bool = True,
) -> dict[str, Any]:
    """
    First-time OAuth: locate Desktop credentials, open browser, persist tokens + channel, verify refresh.
    Writes project_brain/upload/youtube_auth_result.json.
    """
    root = Path(project_root).resolve()
    profile = ProductChannelProfileStore(root).load()
    discovery = discover_oauth_credentials(root, profile)
    if not discovery.get("ok"):
        failure = {
            "authorized": False,
            "version": YOUTUBE_FIRST_AUTH_VERSION,
            "channel_name": "",
            "channel_id": "",
            "token_refresh_verified": False,
            "oauth_client_path": "",
            "error": discovery.get("reason") or "oauth_client_missing",
        }
        write_youtube_auth_result(root, failure)
        return failure

    client_path = Path(str(discovery["oauth_client_path"]))
    _persist_credentials_path(root, client_path)
    profile = ProductChannelProfileStore(root).load()

    oauth_step = _run_oauth_local_server(root, client_path, port=port, open_browser=open_browser)
    if not oauth_step.get("ok"):
        failure = {
            "authorized": False,
            "version": YOUTUBE_FIRST_AUTH_VERSION,
            "channel_name": "",
            "channel_id": "",
            "token_refresh_verified": False,
            "oauth_client_path": str(client_path),
            "error": oauth_step.get("reason") or "oauth_failed",
            "details": oauth_step,
        }
        write_youtube_auth_result(root, failure)
        return failure

    channel = fetch_and_store_channel_info(root, profile)
    account = load_account_info(root) or {}
    token = load_token(root) or {}
    refreshable = bool(token.get("refresh_token"))
    refresh_verified = False
    if refreshable:
        refreshed = refresh_access_token(root, profile)
        refresh_verified = bool(refreshed.get("ok"))

    if enable_upload:
        ProductChannelProfileStore(root).save({"youtube_upload_enabled": True})

    success = {
        "authorized": True,
        "version": YOUTUBE_FIRST_AUTH_VERSION,
        "channel_name": str(account.get("channel_name") or channel.get("channel_name") or ""),
        "channel_id": str(account.get("channel_id") or channel.get("channel_id") or ""),
        "youtube_account_id": str(account.get("youtube_account_id") or account.get("channel_id") or ""),
        "token_refresh_verified": refresh_verified,
        "oauth_client_path": str(client_path),
        "oauth_method": oauth_step.get("method") or "",
        "refresh_token_present": refreshable,
    }
    write_youtube_auth_result(root, success)
    return success


__all__ = [
    "YOUTUBE_AUTH_RESULT_NAME",
    "YOUTUBE_FIRST_AUTH_VERSION",
    "discover_oauth_credentials",
    "get_youtube_oauth_readiness",
    "load_youtube_auth_result",
    "run_first_youtube_authorization",
    "write_youtube_auth_result",
]
