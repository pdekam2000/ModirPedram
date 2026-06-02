"""Browser launcher API service (Phase 12I-A)."""

from __future__ import annotations

from pathlib import Path

from automation.browser_launcher import (
    get_browser_operator_status,
    launch_controlled_chrome,
)
from ui.api.schemas.browser_operations import (
    BrowserCheckDTO,
    BrowserLaunchResponse,
    BrowserStatusResponse,
)


class BrowserOperationsService:
    def __init__(self, project_root: Path):
        self._project_root = Path(project_root).resolve()

    def launch(self) -> BrowserLaunchResponse:
        payload = launch_controlled_chrome(self._project_root)
        return BrowserLaunchResponse(
            success=bool(payload.get("success")),
            already_running=bool(payload.get("already_running")),
            message=str(payload.get("message") or ""),
            profile_path=str(payload.get("profile_path") or ""),
            cdp_url=str(payload.get("cdp_url") or ""),
            chrome_executable=payload.get("chrome_executable"),
            cdp_port=int(payload.get("cdp_port") or 9222),
            pid=payload.get("pid"),
        )

    def status(self) -> BrowserStatusResponse:
        payload = get_browser_operator_status(self._project_root, probe_login=True)
        checks = [
            BrowserCheckDTO(
                id=str(item.get("id") or ""),
                passed=bool(item.get("passed")),
                message=str(item.get("message") or ""),
            )
            for item in payload.get("checks") or []
        ]
        return BrowserStatusResponse(
            browser_running=bool(payload.get("browser_running")),
            cdp_connected=bool(payload.get("cdp_connected")),
            profile_loaded=bool(payload.get("profile_loaded")),
            runway_login_detected=bool(payload.get("runway_login_detected")),
            ready_for_runway_browser=bool(payload.get("ready_for_runway_browser")),
            profile_path=str(payload.get("profile_path") or ""),
            profile_path_relative=str(payload.get("profile_path_relative") or ""),
            cdp_url=str(payload.get("cdp_url") or ""),
            chrome_executable=payload.get("chrome_executable"),
            chrome_error=payload.get("chrome_error"),
            message=str(payload.get("message") or ""),
            checks=checks,
            last_launch=payload.get("last_launch"),
        )
