"""Runway browser health monitor — CDP heartbeat and safe refresh."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.browser_launcher import (
    get_browser_operator_status,
    is_cdp_reachable,
    launch_controlled_chrome,
    probe_runway_login_detected,
    resolve_runway_browser_config,
)

HEALTH_STATE_FILENAME = "browser_health_state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _health_state_path(project_root: Path) -> Path:
    return project_root / "project_brain" / "runtime_state" / HEALTH_STATE_FILENAME


def _read_generation_active(project_root: Path) -> tuple[bool, str]:
    for rel in (
        Path("project_brain") / "runway_phase_i_3clip_last_report.json",
        Path("project_brain") / "runway_live_smoke_last_report.json",
    ):
        path = project_root / rel
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("video_generation_started") and not payload.get("ok"):
            return True, "runway_generation_in_progress"
        timeline = payload.get("auto_execution_timeline") or []
        if isinstance(timeline, list):
            for step in reversed(timeline):
                if not isinstance(step, dict):
                    continue
                state = str(step.get("runtime_state") or step.get("state") or "").lower()
                if state in {"running", "waiting_completion", "generating"}:
                    return True, state
    return False, ""


def _write_health_state(project_root: Path, payload: dict[str, Any]) -> None:
    path = _health_state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_browser_health(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config = resolve_runway_browser_config(root)
    cdp_url = str(config.get("cdp_url") or "")
    status = get_browser_operator_status(root, probe_login=True)
    generation_active, generation_reason = _read_generation_active(root)
    runway_tab_found = bool(status.get("runway_login_detected"))
    connected = bool(status.get("browser_connected") or status.get("browser_running"))
    responsive = bool(status.get("cdp_connected"))
    payload = {
        "connected": connected,
        "disconnected": not connected,
        "cdp_reachable": bool(status.get("cdp_reachable")),
        "runway_tab_found": runway_tab_found,
        "page_responsive": responsive,
        "generation_active": generation_active,
        "generation_reason": generation_reason,
        "last_heartbeat": _now(),
        "cdp_url": cdp_url,
        "message": str(status.get("message") or ""),
        "checks": list(status.get("checks") or []),
        "refresh_allowed": connected and not generation_active,
        "reconnect_allowed": True,
    }
    _write_health_state(root, payload)
    return payload


def reconnect_browser(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    launch = launch_controlled_chrome(root)
    health = get_browser_health(root)
    return {
        "ok": bool(launch.get("success")),
        "message": str(launch.get("message") or ""),
        "launch": launch,
        "health": health,
    }


def refresh_runway_page(project_root: str | Path, *, force: bool = False) -> dict[str, Any]:
    root = Path(project_root).resolve()
    health = get_browser_health(root)
    if health.get("generation_active") and not force:
        return {
            "ok": False,
            "blocked": True,
            "requires_confirmation": True,
            "message": "Refresh blocked while generation is active.",
            "health": health,
        }
    config = resolve_runway_browser_config(root)
    cdp_url = str(config.get("cdp_url") or "")
    if not is_cdp_reachable(cdp_url):
        return {"ok": False, "message": "CDP not reachable.", "health": health}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "message": "Playwright is not installed.", "health": health}

    playwright = None
    browser = None
    refreshed = False
    target_url = ""
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=5000)
        for context in browser.contexts:
            for page in context.pages:
                url = str(page.url or "")
                if "runwayml.com" not in url.lower():
                    continue
                target_url = url
                page.reload(wait_until="domcontentloaded", timeout=15000)
                refreshed = True
                break
            if refreshed:
                break
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:200], "health": get_browser_health(root)}
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

    if not refreshed:
        return {"ok": False, "message": "No Runway tab found to refresh.", "health": get_browser_health(root)}
    return {
        "ok": True,
        "message": f"Runway page refreshed: {target_url}",
        "health": get_browser_health(root),
    }
