"""
Phase 10J-b — CDP/browser readiness probes without modifying BrowserManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import socket


@dataclass
class BrowserProbeResult:
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    reject_code: str | None = None
    message: str = ""


def _check(check_id: str, passed: bool, message: str = "") -> dict[str, Any]:
    return {"id": check_id, "passed": passed, "message": message}


def _parse_cdp_host_port(cdp_url: str) -> tuple[str, int]:
    parsed = urlparse(str(cdp_url or "http://127.0.0.1:9222"))
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9222
    return host, int(port)


def probe_cdp_socket(cdp_url: str, *, timeout_seconds: float = 2.0) -> tuple[bool, str]:
    host, port = _parse_cdp_host_port(cdp_url)
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True, f"CDP port reachable at {host}:{port}"
    except OSError as exc:
        return False, f"CDP not reachable at {host}:{port}: {exc}"


def probe_playwright_attach(cdp_url: str, *, timeout_ms: int = 5000) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright is not installed."

    playwright = None
    browser = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(str(cdp_url), timeout=timeout_ms)
        version = browser.version if browser else "unknown"
        return True, f"Playwright CDP attach OK (browser version: {version})"
    except Exception as exc:
        return False, f"Playwright CDP attach failed: {exc}"
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


def probe_browser_profile(profile_path: str | Path, project_root: str | Path | None = None) -> tuple[bool, str]:
    path = Path(profile_path)
    if not path.is_absolute() and project_root is not None:
        path = Path(project_root).resolve() / path
    if path.exists():
        return True, f"Browser profile path exists: {path}"
    return False, f"Browser profile path missing: {path}"


def probe_download_dir(download_dir: str | Path, project_root: str | Path | None = None) -> tuple[bool, str]:
    path = Path(download_dir)
    if not path.is_absolute() and project_root is not None:
        path = Path(project_root).resolve() / path
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".preflight_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, f"Download path writable: {path}"
    except OSError as exc:
        return False, f"Download path not writable: {path} ({exc})"


def run_browser_probes(
    browser_config: dict[str, Any],
    *,
    project_root: str | Path | None = None,
    require_playwright_attach: bool = True,
) -> BrowserProbeResult:
    checks: list[dict[str, Any]] = []
    cdp_url = str(browser_config.get("cdp_url") or "http://127.0.0.1:9222")

    ok, msg = probe_cdp_socket(cdp_url)
    checks.append(_check("BROWSER_AVAILABLE", ok, msg))
    if not ok:
        return BrowserProbeResult(False, checks, "BROWSER_UNAVAILABLE", msg)

    profile_path = browser_config.get("profile_path") or "storage/real_chrome_profile"
    ok, msg = probe_browser_profile(profile_path, project_root)
    checks.append(_check("BROWSER_PROFILE", ok, msg))
    if not ok:
        return BrowserProbeResult(False, checks, "BROWSER_PROFILE_MISSING", msg)

    if require_playwright_attach:
        ok, msg = probe_playwright_attach(cdp_url)
        checks.append(_check("BROWSER_AUTOMATION_READY", ok, msg))
        if not ok:
            code = "BROWSER_AUTOMATION_NOT_READY"
            if "attach failed" in msg.lower() and "connect" in msg.lower():
                code = "BROWSER_UNAVAILABLE"
            return BrowserProbeResult(False, checks, code, msg)
        checks.append(_check("BROWSER_SESSION_VALID", ok, "CDP attach succeeded (session assumed valid if attach works)"))

    download_dir = browser_config.get("download_dir") or "downloads"
    ok, msg = probe_download_dir(download_dir, project_root)
    checks.append(_check("DOWNLOAD_PATH_READY", ok, msg))
    if not ok:
        return BrowserProbeResult(False, checks, "DOWNLOAD_PATH_NOT_WRITABLE", msg)

    return BrowserProbeResult(True, checks)


__all__ = [
    "BrowserProbeResult",
    "probe_cdp_socket",
    "probe_playwright_attach",
    "probe_browser_profile",
    "probe_download_dir",
    "run_browser_probes",
]
