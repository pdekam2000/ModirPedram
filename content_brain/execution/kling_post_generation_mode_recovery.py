"""Post-generation mode recovery — restore Video/Kling composer after Clip 1 completes."""

from __future__ import annotations

import re
import time
from typing import Any

from content_brain.execution.kling_frame_to_video_map_loader import load_kling_frame_ui_map
from content_brain.execution.kling_multishot_live_engine import _detect_output_ready
from content_brain.execution.kling_multishot_locator import (
    detect_kling_3_pro_current_model,
    resolve_kling_3_pro_provider,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

RUNTIME_VERSION = "kling_post_generation_mode_recovery_v1"

MODE_IMAGE = "image"
MODE_VIDEO = "video"
MODE_AUDIO = "audio"
MODE_UNKNOWN = "unknown"

_DETECT_ACTIVE_TAB_JS = """() => {
    const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    const isSelected = (node) => {
        if (!node) return false;
        if (node.getAttribute('aria-selected') === 'true') return true;
        if (node.getAttribute('aria-current') === 'true') return true;
        const state = normalize(node.getAttribute('data-state') || '');
        if (state === 'active' || state === 'selected' || state === 'checked') return true;
        const cls = normalize(String(node.className || ''));
        return cls.includes('selected') || cls.includes('active');
    };
    for (const name of ['Image', 'Video', 'Audio']) {
        const nodes = Array.from(document.querySelectorAll('button, [role="tab"], label, a'));
        for (const node of nodes) {
            const text = normalize(node.innerText || node.textContent || '');
            if (text !== normalize(name)) continue;
            if (isSelected(node)) return name.toLowerCase();
        }
    }
    const url = String(location.href || '').toLowerCase();
    if (url.includes('tool=video')) return 'video';
    if (url.includes('tool=image')) return 'image';
    if (url.includes('tool=audio')) return 'audio';
    return 'unknown';
}"""


def _read_page_url(page: Any) -> str:
    try:
        return str(page.url or "")
    except Exception:
        return ""


def detect_active_runway_tool_tab(page: Any) -> dict[str, Any]:
    """Detect active Runway generate tool tab: image / video / audio / unknown."""
    active = MODE_UNKNOWN
    try:
        raw = str(page.evaluate(_DETECT_ACTIVE_TAB_JS) or "").strip().lower()
        if raw in {MODE_IMAGE, MODE_VIDEO, MODE_AUDIO}:
            active = raw
    except Exception:
        pass
    url = _read_page_url(page).lower()
    if active == MODE_UNKNOWN:
        if "tool=video" in url:
            active = MODE_VIDEO
        elif "tool=image" in url:
            active = MODE_IMAGE
        elif "tool=audio" in url:
            active = MODE_AUDIO
    return {
        "active_tab": active,
        "page_url": _read_page_url(page),
        "image_active": active == MODE_IMAGE,
        "video_active": active == MODE_VIDEO,
    }


def _click_video_tool_tab(page: Any) -> tuple[bool, str]:
    for strategy, factory in (
        ("role_tab_video", lambda: page.get_by_role("tab", name=re.compile(r"^Video$", re.I)).first),
        ("text_video_exact", lambda: page.get_by_text("Video", exact=True).first),
        ("label_video", lambda: page.locator('label:has-text("Video")').first),
        ("button_video", lambda: page.locator('button:has-text("Video")').first),
    ):
        try:
            loc = factory()
            if loc.count() <= 0 or not loc.is_visible(timeout=2000):
                continue
            loc.click(timeout=5000, force=True)
            time.sleep(0.5)
            return True, strategy
        except Exception:
            continue
    url = _read_page_url(page)
    if "tool=image" in url.lower():
        try:
            page.goto(url.replace("tool=image", "tool=video"), wait_until="domcontentloaded")
            time.sleep(0.8)
            return True, "url_tool_video"
        except Exception:
            pass
    return False, ""


def wait_for_video_composer_ready(page: Any, *, timeout_ms: int = 12000) -> dict[str, Any]:
    """Wait for Video prompt editor + Generate after tab recovery."""
    deadline = time.monotonic() + max(1, timeout_ms) / 1000.0
    last: dict[str, Any] = {
        "ready": False,
        "generate_visible": False,
        "prompt_editor_ready": False,
        "detail": "timeout",
    }
    while time.monotonic() < deadline:
        detection = detect_kling_3_pro_current_model(page, timeout_ms=1500)
        last["generate_visible"] = bool(detection.get("generate_visible"))
        last["prompt_editor_ready"] = bool(detection.get("prompt_editor_ready"))
        if last["generate_visible"] and last["prompt_editor_ready"]:
            last["ready"] = True
            last["detail"] = "generate_and_prompt_ready"
            return last
        time.sleep(0.35)
    return last


def recover_video_kling_mode_after_generation(
    page: Any,
    *,
    map_path: str | Any | None = None,
    timeout_ms: int = 15000,
) -> dict[str, Any]:
    """Restore Video tab + Kling 3.x Pro composer after post-generation UI drift."""
    ui_map = load_kling_frame_ui_map(map_path=map_path or DEFAULT_MAP_PATH)
    labels = dict(ui_map.get("labels") or {})
    provider_entry = labels.get("provider_kling_3_pro") or {}

    tab = detect_active_runway_tool_tab(page)
    result: dict[str, Any] = {
        "version": RUNTIME_VERSION,
        "recovered": False,
        "active_tab_before": tab.get("active_tab"),
        "video_tab_clicked": False,
        "video_tab_strategy": "",
        "composer_ready": False,
        "model_already_selected": False,
        "provider_strategy": "",
        "detail": "",
    }

    if tab.get("image_active") or tab.get("active_tab") == MODE_UNKNOWN:
        clicked, strategy = _click_video_tool_tab(page)
        result["video_tab_clicked"] = clicked
        result["video_tab_strategy"] = strategy
        if not clicked:
            result["detail"] = "video_tab_click_failed"
            return result
        time.sleep(0.5)

    composer = wait_for_video_composer_ready(page, timeout_ms=min(timeout_ms, 12000))
    result["composer_ready"] = bool(composer.get("ready"))
    if not composer.get("ready"):
        result["detail"] = f"composer_not_ready:{composer.get('detail')}"
        return result

    try:
        provider, model_detection = resolve_kling_3_pro_provider(page, provider_entry)
        result["provider_strategy"] = provider.strategy
        result["model_already_selected"] = bool(model_detection.get("model_already_selected"))
    except Exception as exc:
        result["detail"] = f"provider_resolve_failed:{str(exc)[:120]}"
        return result

    tab_after = detect_active_runway_tool_tab(page)
    result["active_tab_after"] = tab_after.get("active_tab")
    result["recovered"] = (
        tab_after.get("active_tab") in {MODE_VIDEO, MODE_UNKNOWN}
        or bool(composer.get("ready"))
    ) and bool(result.get("provider_strategy"))
    result["detail"] = "video_kling_mode_recovered" if result["recovered"] else "recovery_incomplete"
    return result


def detect_clip_output_visible(page: Any) -> dict[str, Any]:
    """Detect whether Clip 1 output is visible for Use Frame."""
    ready, reason = _detect_output_ready(page)
    return {
        "output_visible": ready,
        "detail": reason,
    }


def select_use_frame_dropdown_option(page: Any) -> dict[str, Any]:
    """Select continuity option when Use Frame opens a dropdown/menu."""
    options = (
        "First video frame",
        "First Video Frame",
        "Use as first frame",
        "Use frame",
        "Continue",
    )
    for option in options:
        for factory in (
            lambda o=option: page.get_by_role("menuitem", name=re.compile(re.escape(o), re.I)).first,
            lambda o=option: page.get_by_role("option", name=re.compile(re.escape(o), re.I)).first,
            lambda o=option: page.get_by_text(o, exact=False).first,
        ):
            try:
                loc = factory()
                if loc.count() <= 0 or not loc.is_visible(timeout=1500):
                    continue
                loc.click(timeout=4000, force=True)
                time.sleep(0.45)
                return {"selected": True, "option": option, "detail": f"dropdown:{option}"}
            except Exception:
                continue
    return {"selected": False, "option": "", "detail": "no_dropdown_or_already_applied"}


def wait_for_continuity_frame_populated(
    page: Any,
    *,
    map_path: str | Any | None = None,
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """Wait until First Video Frame slot shows a continuity reference."""
    from content_brain.execution.kling_use_frame_runtime import verify_reference_transferred

    deadline = time.monotonic() + max(1, timeout_ms) / 1000.0
    last: dict[str, Any] = {
        "continuity_frame_in_ui": False,
        "first_frame_upload_visible": False,
        "thumbnail_present": False,
        "detail": "timeout",
    }
    while time.monotonic() < deadline:
        verify = verify_reference_transferred(page, map_path=map_path)
        thumbnail_present = False
        try:
            panel = page.locator('[class*="left-panel"], [class*="leftPanel"]').first
            if panel.count() > 0:
                thumbnail_present = panel.locator("img, video, canvas").count() > 0
        except Exception:
            pass
        last = {
            "continuity_frame_in_ui": bool(verify.get("ok") or thumbnail_present),
            "first_frame_upload_visible": bool(verify.get("first_frame_upload_visible")),
            "thumbnail_present": thumbnail_present,
            "verify": verify,
            "detail": verify.get("detail") or "",
        }
        if last["continuity_frame_in_ui"]:
            return last
        time.sleep(0.4)
    return last


__all__ = [
    "MODE_AUDIO",
    "MODE_IMAGE",
    "MODE_UNKNOWN",
    "MODE_VIDEO",
    "RUNTIME_VERSION",
    "detect_active_runway_tool_tab",
    "detect_clip_output_visible",
    "recover_video_kling_mode_after_generation",
    "select_use_frame_dropdown_option",
    "wait_for_continuity_frame_populated",
    "wait_for_video_composer_ready",
]
