"""Platform foundation service — credentials, auth, browser health, automation."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from content_brain.platform.automation_center_store import AutomationCenterStore
from content_brain.platform.browser_health_monitor import (
    get_browser_health,
    reconnect_browser,
    refresh_runway_page,
)
from content_brain.platform.local_credentials_store import LocalCredentialsStore
from content_brain.platform.local_user_store import LocalUserStore
from content_brain.platform.run_output_versioning import list_run_history
from content_brain.product_settings.channel_profile_store import ProductChannelProfileStore

_SESSIONS: dict[str, str] = {}
DEFAULT_LOCAL_USERNAME = "local"


class PlatformService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.credentials = LocalCredentialsStore(self.project_root)
        self.users = LocalUserStore(self.project_root)
        self.automation = AutomationCenterStore(self.project_root)
        self.credentials.apply_all_to_env()

    def is_local_mode_enabled(self) -> bool:
        profile = ProductChannelProfileStore(self.project_root).load()
        return bool(profile.get("local_mode", True))

    def get_auth_config(self) -> dict[str, Any]:
        local_mode = self.is_local_mode_enabled()
        user = self.users.get_public_user()
        return {
            "local_mode": local_mode,
            "user_exists": bool(user.get("exists")),
            "username": str(user.get("username") or ""),
        }

    def _ensure_local_user(self) -> dict[str, Any]:
        if self.users.user_exists():
            return self.users.get_public_user()
        return self.users.create_user(DEFAULT_LOCAL_USERNAME, secrets.token_urlsafe(24))

    def auto_login_local(self) -> dict[str, Any]:
        if not self.is_local_mode_enabled():
            return {
                "ok": False,
                "token": "",
                "username": "",
                "message": "Local mode is disabled.",
                "local_mode": False,
            }
        user = self._ensure_local_user()
        username = str(user.get("username") or DEFAULT_LOCAL_USERNAME)
        token = secrets.token_urlsafe(32)
        _SESSIONS[token] = username
        return {
            "ok": True,
            "token": token,
            "username": username,
            "message": "Auto-logged in (local single-user mode).",
            "local_mode": True,
        }

    def list_credentials(self) -> dict[str, Any]:
        return {"providers": self.credentials.list_masked()}

    def save_credential(self, provider_id: str, secret: str) -> dict[str, Any]:
        return self.credentials.save_provider_secret(provider_id, secret)

    def test_credential(self, provider_id: str) -> dict[str, Any]:
        self.credentials.apply_all_to_env()
        return self.credentials.test_provider_connection(provider_id)

    def get_local_user(self) -> dict[str, Any]:
        return self.users.get_public_user()

    def create_local_user(self, username: str, password: str) -> dict[str, Any]:
        return self.users.create_user(username, password)

    def login(self, username: str, password: str) -> dict[str, Any]:
        if not self.users.verify_login(username, password):
            return {"ok": False, "token": "", "username": "", "message": "Invalid username or password."}
        token = secrets.token_urlsafe(32)
        _SESSIONS[token] = (username or "").strip()
        return {"ok": True, "token": token, "username": (username or "").strip(), "message": "Logged in."}

    def logout(self, token: str) -> dict[str, Any]:
        _SESSIONS.pop(str(token or "").strip(), None)
        return {"ok": True, "message": "Logged out."}

    def me(self, token: str | None) -> dict[str, Any]:
        username = _SESSIONS.get(str(token or "").strip(), "")
        return {"authenticated": bool(username), "username": username}

    def browser_health(self) -> dict[str, Any]:
        return get_browser_health(self.project_root)

    def browser_reconnect(self) -> dict[str, Any]:
        return reconnect_browser(self.project_root)

    def browser_refresh_runway(self, *, force: bool = False) -> dict[str, Any]:
        return refresh_runway_page(self.project_root, force=force)

    def runway_session_status(self, *, validate: bool = False) -> dict[str, Any]:
        from content_brain.automation.runway_session_manager import get_runway_session_status

        return get_runway_session_status(self.project_root, validate=validate)

    def connect_runway_browser(self) -> dict[str, Any]:
        from content_brain.automation.runway_session_manager import connect_runway_browser

        return connect_runway_browser(self.project_root)

    def save_runway_browser_session(self) -> dict[str, Any]:
        from content_brain.automation.runway_session_manager import save_runway_session_from_cdp

        return save_runway_session_from_cdp(self.project_root)

    def run_history(self, *, limit: int = 20) -> dict[str, Any]:
        runs = list_run_history(self.project_root, limit=limit)
        latest = runs[0] if runs else None
        return {"latest": latest, "runs": runs}

    def get_automation_center(self) -> dict[str, Any]:
        return self.automation.load()

    def update_automation_center(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.automation.save(payload)

    def queue_automation_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.automation.queue_manual_job(payload)

    def start_next_automation_job(self) -> dict[str, Any]:
        return self.automation.pop_next_job() or self.automation.load()


def get_platform_service(project_root: str | Path | None = None) -> PlatformService:
    if project_root is None:
        from ui.api.dependencies import get_project_root

        project_root = get_project_root()
    return PlatformService(project_root)
