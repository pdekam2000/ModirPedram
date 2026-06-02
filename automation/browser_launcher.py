"""
Phase 12I-A — controlled Chrome launcher for Runway/Hailuo browser providers.

Launches Google Chrome with persistent profile + CDP port (operator login workflow).
Does not store credentials or automate Runway sign-in.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_brain.execution.browser_connectivity_probe import (
    probe_browser_profile,
    probe_cdp_socket,
    probe_playwright_attach,
)
from content_brain.execution.provider_mode_catalog import ProviderModeCatalog

LAUNCHER_VERSION = "12i_a_v1"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DEFAULT_PROFILE_REL = "storage/real_chrome_profile"
RUNWAY_FAMILY = "runway"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

CHROME_CANDIDATE_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)

FORBIDDEN_EXECUTABLE_MARKERS = ("msedge", "edge.exe", "microsoft-edge")


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _parse_cdp_port(cdp_url: str) -> int:
    parsed = urlparse(str(cdp_url or DEFAULT_CDP_URL))
    return int(parsed.port or 9222)


def resolve_chrome_executable() -> Path:
    """Resolve Chrome path; never return Edge."""
    override = str(os.getenv("MODIR_CHROME_PATH", "")).strip()
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    candidates.extend(Path(path) for path in CHROME_CANDIDATE_PATHS)

    for candidate in candidates:
        name = candidate.name.lower()
        if any(marker in name for marker in FORBIDDEN_EXECUTABLE_MARKERS):
            continue
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError(
        "Google Chrome not found. Set MODIR_CHROME_PATH to chrome.exe "
        "(Microsoft Edge is not supported for Runway browser mode)."
    )


def resolve_runway_browser_config(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    catalog = ProviderModeCatalog.load(root)
    family = catalog.get_family(RUNWAY_FAMILY) or {}
    browser_config = dict(family.get("browser_config") or {})
    profile_rel = str(browser_config.get("profile_path") or DEFAULT_PROFILE_REL)
    profile_path = Path(profile_rel)
    if not profile_path.is_absolute():
        profile_path = root / profile_path
    return {
        "cdp_url": str(browser_config.get("cdp_url") or DEFAULT_CDP_URL),
        "profile_path": str(profile_path.resolve()),
        "profile_path_relative": profile_rel,
        "download_dir": str(browser_config.get("download_dir") or "downloads/runway"),
        "launcher_version": LAUNCHER_VERSION,
    }


def _state_path(project_root: Path) -> Path:
    return project_root / "storage" / "browser_launcher_state.json"


def _read_state(project_root: Path) -> dict[str, Any]:
    path = _state_path(project_root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(project_root: Path, payload: dict[str, Any]) -> None:
    path = _state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_cdp_reachable(cdp_url: str, *, timeout_seconds: float = 1.5) -> bool:
    ok, _ = probe_cdp_socket(cdp_url, timeout_seconds=timeout_seconds)
    return ok


def probe_runway_login_detected(cdp_url: str, *, timeout_ms: int = 4000) -> tuple[bool, str]:
    """
    Heuristic: inspect open CDP tabs for Runway workspace (no credential storage).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright is not installed."

    playwright = None
    browser = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(str(cdp_url), timeout=timeout_ms)
        for context in browser.contexts:
            for page in context.pages:
                url = str(page.url or "").lower()
                if "runwayml.com" not in url:
                    continue
                if any(token in url for token in ("/login", "/sign-in", "/signup", "auth.")):
                    continue
                try:
                    if page.get_by_text("Generate Video", exact=False).count() > 0:
                        return True, "Runway workspace detected (Generate Video visible)."
                except Exception:
                    pass
                if "app.runwayml.com" in url:
                    return True, f"Runway app tab open: {page.url}"
        return False, "No logged-in Runway tab detected. Open https://app.runwayml.com and sign in manually."
    except Exception as exc:
        return False, f"Runway login probe failed: {exc}"
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if playwright is not None:
                playwright.stop()
        except Exception:
            pass


def launch_controlled_chrome(
    project_root: str | Path,
    *,
    family: str = RUNWAY_FAMILY,
) -> dict[str, Any]:
    """
    Launch Chrome with persistent profile for operator manual Runway login.
    If CDP is already reachable, does not start a second browser.
    """
    root = Path(project_root).resolve()
    config = resolve_runway_browser_config(root)
    cdp_url = config["cdp_url"]
    profile_path = Path(config["profile_path"])
    chrome_exe = resolve_chrome_executable()

    profile_path.mkdir(parents=True, exist_ok=True)

    if is_cdp_reachable(cdp_url):
        payload = {
            "launcher_version": LAUNCHER_VERSION,
            "launched_at": _now(),
            "chrome_executable": str(chrome_exe),
            "profile_path": str(profile_path),
            "cdp_url": cdp_url,
            "launch_skipped": True,
            "reason": "CDP already reachable",
        }
        _write_state(root, payload)
        return {
            "success": True,
            "already_running": True,
            "message": "Controlled browser already listening on CDP (port in use).",
            "chrome_executable": str(chrome_exe),
            "profile_path": str(profile_path),
            "cdp_url": cdp_url,
            "cdp_port": _parse_cdp_port(cdp_url),
        }

    port = _parse_cdp_port(cdp_url)
    args = [
        str(chrome_exe),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    process = subprocess.Popen(args)

    payload = {
        "launcher_version": LAUNCHER_VERSION,
        "launched_at": _now(),
        "pid": process.pid,
        "chrome_executable": str(chrome_exe),
        "profile_path": str(profile_path),
        "cdp_url": cdp_url,
        "launch_skipped": False,
    }
    _write_state(root, payload)

    return {
        "success": True,
        "already_running": False,
        "message": "Chrome launched with controlled profile. Log into Runway manually and keep the browser open.",
        "chrome_executable": str(chrome_exe),
        "profile_path": str(profile_path),
        "cdp_url": cdp_url,
        "cdp_port": port,
        "pid": process.pid,
    }


def get_browser_operator_status(
    project_root: str | Path,
    *,
    probe_login: bool = True,
) -> dict[str, Any]:
    """Status card fields for Execution Center / UAT."""
    root = Path(project_root).resolve()
    config = resolve_runway_browser_config(root)
    cdp_url = config["cdp_url"]
    profile_path = str(config["profile_path"])

    checks: list[dict[str, Any]] = []

    browser_running, running_msg = probe_cdp_socket(cdp_url)
    checks.append({"id": "browser_running", "passed": browser_running, "message": running_msg})

    profile_loaded, profile_msg = probe_browser_profile(profile_path, root)
    checks.append({"id": "profile_loaded", "passed": profile_loaded, "message": profile_msg})

    cdp_connected = False
    cdp_msg = "CDP not connected."
    if browser_running:
        cdp_connected, cdp_msg = probe_playwright_attach(cdp_url)
    checks.append({"id": "cdp_connected", "passed": cdp_connected, "message": cdp_msg})

    runway_login_detected = False
    runway_login_message = "CDP unavailable; login state unknown."
    if cdp_connected and probe_login:
        runway_login_detected, runway_login_message = probe_runway_login_detected(cdp_url)
    checks.append(
        {
            "id": "runway_login_detected",
            "passed": runway_login_detected,
            "message": runway_login_message,
        }
    )

    chrome_executable: str | None = None
    chrome_error: str | None = None
    try:
        chrome_executable = str(resolve_chrome_executable())
    except FileNotFoundError as exc:
        chrome_error = str(exc)

    state = _read_state(root)
    ready = browser_running and profile_loaded and cdp_connected and runway_login_detected

    return {
        "launcher_version": LAUNCHER_VERSION,
        "browser_running": browser_running,
        "cdp_connected": cdp_connected,
        "profile_loaded": profile_loaded,
        "runway_login_detected": runway_login_detected,
        "ready_for_runway_browser": ready,
        "profile_path": profile_path,
        "profile_path_relative": config["profile_path_relative"],
        "cdp_url": cdp_url,
        "chrome_executable": chrome_executable,
        "chrome_error": chrome_error,
        "last_launch": state or None,
        "checks": checks,
        "message": (
            "Runway browser ready."
            if ready
            else "Complete: Open Runway Browser → sign in to Runway → keep Chrome open."
        ),
    }


__all__ = [
    "LAUNCHER_VERSION",
    "DEFAULT_CDP_URL",
    "DEFAULT_PROFILE_REL",
    "resolve_chrome_executable",
    "resolve_runway_browser_config",
    "launch_controlled_chrome",
    "get_browser_operator_status",
    "probe_runway_login_detected",
    "is_cdp_reachable",
]
