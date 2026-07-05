"""Runway browser session persistence — cookies + localStorage via Playwright storage_state."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNWAY_APP_URL = "https://app.runwayml.com/"
RUNWAY_GENERATE_URL = (
    "https://app.runwayml.com/video-tools/teams/kamangarpedram/"
    "ai-tools/generate?tool=video&mode=tools"
)
SESSION_REL = Path("project_brain") / "sessions" / "runway_session.json"
STATUS_REL = Path("project_brain") / "sessions" / "runway_session_status.json"

_logger = logging.getLogger("modiragent.runway_session")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def runway_session_path(project_root: str | Path) -> Path:
    path = Path(project_root).resolve() / SESSION_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def runway_session_status_path(project_root: str | Path) -> Path:
    path = Path(project_root).resolve() / STATUS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def is_runway_login_page(url: str) -> bool:
    lowered = str(url or "").lower()
    return any(token in lowered for token in ("/login", "/sign-in", "/signup", "auth."))


def write_session_status(
    project_root: str | Path,
    *,
    connected: bool,
    message: str,
    validated: bool = False,
) -> dict[str, Any]:
    payload = {
        "connected": connected,
        "disconnected": not connected,
        "message": message,
        "validated": validated,
        "updated_at": _now(),
        "session_path": str(runway_session_path(project_root)),
    }
    runway_session_status_path(project_root).write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return payload


def read_session_status(project_root: str | Path) -> dict[str, Any]:
    path = runway_session_status_path(project_root)
    if not path.is_file():
        return {
            "connected": False,
            "disconnected": True,
            "message": "No Runway session saved yet.",
            "validated": False,
            "updated_at": "",
            "session_path": str(runway_session_path(project_root)),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return write_session_status(
            project_root,
            connected=False,
            message="Runway session status unreadable.",
        )
    if not isinstance(payload, dict):
        return write_session_status(
            project_root,
            connected=False,
            message="Runway session status invalid.",
        )
    return payload


def save_runway_session(context: Any, project_root: str | Path) -> Path:
    path = runway_session_path(project_root)
    context.storage_state(path=str(path))
    write_session_status(
        project_root,
        connected=True,
        message="Runway session saved OK",
        validated=False,
    )
    _logger.info("Runway session saved: %s", path)
    return path


def validate_runway_session_on_page(page: Any) -> tuple[bool, str]:
    try:
        page.goto(RUNWAY_APP_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1500)
        url = str(page.url or "")
        if is_runway_login_page(url):
            return False, "Runway session expired — manual login required"
        return True, "Runway session restored OK"
    except Exception as exc:
        return False, f"Session validation failed: {exc}"


def validate_runway_session_file(
    project_root: str | Path,
    *,
    headless: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    session_path = runway_session_path(root)
    if not session_path.is_file() or session_path.stat().st_size == 0:
        return write_session_status(
            root,
            connected=False,
            message="Runway: ● Disconnected — no saved session.",
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return write_session_status(
            root,
            connected=True,
            message="Runway session file present (Playwright unavailable to validate).",
        )

    playwright = None
    browser = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=headless, channel="chrome")
        context = browser.new_context(storage_state=str(session_path))
        page = context.new_page()
        ok, message = validate_runway_session_on_page(page)
        context.close()
        if ok:
            _logger.info(message)
            return write_session_status(root, connected=True, message=message, validated=True)
        _logger.warning(message)
        return write_session_status(root, connected=False, message=message, validated=True)
    except Exception as exc:
        return write_session_status(
            root,
            connected=False,
            message=f"Runway session validation error: {exc}",
        )
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


def get_runway_session_status(
    project_root: str | Path,
    *,
    validate: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    session_path = runway_session_path(root)
    if validate and session_path.is_file():
        return validate_runway_session_file(root)
    status = read_session_status(root)
    if session_path.is_file() and session_path.stat().st_size > 0:
        if not status.get("updated_at"):
            status = write_session_status(
                root,
                connected=True,
                message="Runway session file present.",
            )
    elif not status.get("connected"):
        status.setdefault("message", "Runway: ● Disconnected — connect browser and log in.")
    return status


def _open_runway_in_cdp(cdp_url: str, *, runway_url: str = RUNWAY_GENERATE_URL) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright is not installed."

    playwright = None
    browser = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=5000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for candidate in context.pages:
            url = str(candidate.url or "").lower()
            if "runwayml.com" in url:
                page = candidate
                break
        if page is None:
            page = context.new_page()
            page.goto(runway_url, wait_until="domcontentloaded", timeout=60_000)
        elif "generate" not in str(page.url or "").lower():
            page.goto(runway_url, wait_until="domcontentloaded", timeout=60_000)
        return True, str(page.url or runway_url)
    except Exception as exc:
        return False, str(exc)[:200]
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


def save_runway_session_from_cdp(project_root: str | Path) -> dict[str, Any]:
    from automation.browser_launcher import resolve_runway_browser_config

    root = Path(project_root).resolve()
    config = resolve_runway_browser_config(root)
    cdp_url = str(config.get("cdp_url") or "")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "message": "Playwright is not installed.", "connected": False}

    playwright = None
    browser = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=5000)
        if not browser.contexts:
            return {"ok": False, "message": "No browser context found.", "connected": False}
        context = browser.contexts[0]
        save_runway_session(context, root)
        page = context.pages[0] if context.pages else context.new_page()
        ok, message = validate_runway_session_on_page(page)
        status = write_session_status(root, connected=ok, message=message, validated=True)
        return {"ok": ok, "connected": ok, "message": message, "status": status}
    except Exception as exc:
        return {"ok": False, "connected": False, "message": str(exc)[:200]}
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


MSG_RUNWAY_NOT_CONNECTED = (
    "❌ Runway browser not connected. Click 'Connect Runway Browser' first."
)
MSG_RUNWAY_SESSION_EXPIRED = (
    "⚠️ Runway session expired. Click 'Connect Runway Browser' to reconnect."
)


def require_runway_session_for_generation(
    project_root: str | Path,
    *,
    validate: bool = False,
) -> dict[str, Any]:
    """Pre-flight gate before pwmap/Runway generation."""
    root = Path(project_root).resolve()
    session_path = runway_session_path(root)
    if not session_path.is_file() or session_path.stat().st_size == 0:
        write_session_status(root, connected=False, message=MSG_RUNWAY_NOT_CONNECTED)
        return {
            "ok": False,
            "exit_code": 2,
            "reason": "no_session_file",
            "message": MSG_RUNWAY_NOT_CONNECTED,
            "session_path": str(session_path),
        }

    if validate:
        status = validate_runway_session_file(root)
    else:
        status = get_runway_session_status(root, validate=False)

    if status.get("connected"):
        return {
            "ok": True,
            "exit_code": 0,
            "reason": "",
            "message": str(status.get("message") or "Runway session ready."),
            "session_path": str(session_path),
            "status": status,
        }

    message = str(status.get("message") or "")
    lowered = message.lower()
    if any(token in lowered for token in ("expired", "login", "sign-in", "sign in")):
        return {
            "ok": False,
            "exit_code": 2,
            "reason": "session_expired",
            "message": MSG_RUNWAY_SESSION_EXPIRED,
            "session_path": str(session_path),
            "status": status,
        }

    return {
        "ok": False,
        "exit_code": 2,
        "reason": "not_connected",
        "message": MSG_RUNWAY_NOT_CONNECTED,
        "session_path": str(session_path),
        "status": status,
    }


def connect_runway_browser(project_root: str | Path) -> dict[str, Any]:
    from automation.browser_launcher import (
        launch_controlled_chrome,
        probe_runway_login_detected,
        resolve_runway_browser_config,
    )

    root = Path(project_root).resolve()
    launch = launch_controlled_chrome(root)
    config = resolve_runway_browser_config(root)
    cdp_url = str(config.get("cdp_url") or "")

    opened, open_msg = _open_runway_in_cdp(cdp_url)
    logged_in, login_msg = probe_runway_login_detected(cdp_url)

    if logged_in:
        saved = save_runway_session_from_cdp(root)
        return {
            "ok": True,
            "connected": bool(saved.get("connected")),
            "awaiting_login": False,
            "message": str(saved.get("message") or "Runway session saved ✓"),
            "launch": launch,
            "status": saved.get("status") or get_runway_session_status(root),
        }

    write_session_status(
        root,
        connected=False,
        message="Browser open — log in to Runway. Session saves automatically when login is detected.",
    )
    detail = login_msg if not opened else open_msg
    return {
        "ok": bool(launch.get("success")),
        "connected": False,
        "awaiting_login": True,
        "message": f"Browser ready. Sign in to Runway manually. ({detail})",
        "launch": launch,
        "status": get_runway_session_status(root),
    }


__all__ = [
    "MSG_RUNWAY_NOT_CONNECTED",
    "MSG_RUNWAY_SESSION_EXPIRED",
    "RUNWAY_APP_URL",
    "connect_runway_browser",
    "get_runway_session_status",
    "is_runway_login_page",
    "require_runway_session_for_generation",
    "runway_session_path",
    "save_runway_session",
    "save_runway_session_from_cdp",
    "validate_runway_session_file",
    "validate_runway_session_on_page",
    "write_session_status",
]
