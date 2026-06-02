"""Browser operator endpoints (Phase 12I-A)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class BrowserCheckDTO(BaseModel):
    id: str
    passed: bool
    message: str = ""


class BrowserLaunchResponse(BaseModel):
    success: bool = True
    already_running: bool = False
    message: str = ""
    profile_path: str
    cdp_url: str = "http://127.0.0.1:9222"
    chrome_executable: Optional[str] = None
    cdp_port: int = 9222
    pid: Optional[int] = None
    api_version: str = "12i_a_v1"


class BrowserStatusResponse(BaseModel):
    browser_running: bool = False
    cdp_connected: bool = False
    profile_loaded: bool = False
    runway_login_detected: bool = False
    ready_for_runway_browser: bool = False
    profile_path: str
    profile_path_relative: str = "storage/real_chrome_profile"
    cdp_url: str = "http://127.0.0.1:9222"
    chrome_executable: Optional[str] = None
    chrome_error: Optional[str] = None
    message: str = ""
    checks: list[BrowserCheckDTO] = Field(default_factory=list)
    last_launch: Optional[dict[str, Any]] = None
    api_version: str = "12i_a_v1"
