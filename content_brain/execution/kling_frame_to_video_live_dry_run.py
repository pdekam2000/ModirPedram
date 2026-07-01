"""Kling Frame-to-Video live dry-run engine (P2) — CDP UI prepare, no Generate/credits/download."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.kling_frame_to_video_config import (
    BLOCKED_KLING_FRAME_CLICK_LABELS,
    BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS,
    KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS,
    KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS,
    KLING_FRAME_LIVE_DRY_RUN_P2_LABELS,
    KLING_FRAME_LIVE_DRY_RUN_P2_VERSION,
    KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
)
from content_brain.execution.kling_frame_to_video_locator import try_locate_frame_control
from content_brain.execution.kling_frame_to_video_map_loader import (
    load_kling_frame_ui_map,
    resolve_kling_frame_to_video_controls,
    verify_generate_approval_gate,
)
from content_brain.execution.kling_starter_frame_generator import validate_starter_frame_for_upload
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

DEFAULT_CDP_URL = "http://127.0.0.1:9222"
RUNWAY_URL_MARKER = "app.runwayml.com"
RUNWAY_GENERATE_URL_MARKER = "ai-tools/generate"


def _find_runway_generate_page(browser: Any) -> Any | None:
    generate_page = None
    fallback_page = None
    for context in browser.contexts:
        for candidate in context.pages:
            url = candidate.url or ""
            if RUNWAY_URL_MARKER not in url:
                continue
            if fallback_page is None:
                fallback_page = candidate
            if RUNWAY_GENERATE_URL_MARKER in url and "mode=tools" in url:
                return candidate
            if RUNWAY_GENERATE_URL_MARKER in url and generate_page is None:
                generate_page = candidate
    return generate_page or fallback_page


@dataclass
class DryRunStep:
    check_id: str
    label: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class KlingFrameLiveDryRunResult:
    ok: bool
    dry_run: bool
    connect_browser: bool
    generate_clicked: bool
    download_clicked: bool
    credits_spent: bool
    duration_seconds: int | None = None
    duration_display: str = ""
    duration_before_dismiss: str = ""
    duration_after_dismiss: str = ""
    duration_seconds_before_dismiss: int | None = None
    duration_seconds_after_dismiss: int | None = None
    popover_open_before_dismiss: bool = False
    popover_open_after_dismiss: bool = False
    starter_frame_path: str = ""
    starter_frame_ready: bool = False
    starter_frame_checks: dict[str, bool] = field(default_factory=dict)
    audio_state: str = ""
    checks: dict[str, bool] = field(default_factory=dict)
    steps: list[DryRunStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    locator_strategies: dict[str, str] = field(default_factory=dict)
    page_url: str = ""
    map_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": KLING_FRAME_LIVE_DRY_RUN_P2_VERSION,
            "ok": self.ok,
            "dry_run": self.dry_run,
            "connect_browser": self.connect_browser,
            "generate_clicked": self.generate_clicked,
            "download_clicked": self.download_clicked,
            "credits_spent": self.credits_spent,
            "duration_seconds": self.duration_seconds,
            "duration_display": self.duration_display,
            "duration_before_dismiss": self.duration_before_dismiss,
            "duration_after_dismiss": self.duration_after_dismiss,
            "duration_seconds_before_dismiss": self.duration_seconds_before_dismiss,
            "duration_seconds_after_dismiss": self.duration_seconds_after_dismiss,
            "popover_open_before_dismiss": self.popover_open_before_dismiss,
            "popover_open_after_dismiss": self.popover_open_after_dismiss,
            "starter_frame_path": self.starter_frame_path,
            "starter_frame_ready": self.starter_frame_ready,
            "starter_frame_checks": dict(self.starter_frame_checks),
            "duration_slider_15s": all(self.checks.get(c) for c in KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS),
            "audio_state": self.audio_state,
            "checks": dict(self.checks),
            "steps": [s.to_dict() for s in self.steps],
            "errors": list(self.errors),
            "locator_strategies": dict(self.locator_strategies),
            "page_url": self.page_url,
            "map_snapshot": dict(self.map_snapshot),
            "blocked_actions": sorted(BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS),
        }


def _step(result: KlingFrameLiveDryRunResult, check_id: str, label: str, status: str, detail: str = "") -> None:
    result.steps.append(DryRunStep(check_id=check_id, label=label, status=status, detail=detail))


def _mark_check(result: KlingFrameLiveDryRunResult, check_id: str, ok: bool, detail: str = "") -> None:
    result.checks[check_id] = ok
    _step(result, check_id, check_id, "passed" if ok else "failed", detail)
    if not ok:
        result.errors.append(f"{check_id}: {detail or 'failed'}")


def _read_duration_display_value(page: Any, labels: dict[str, Any]) -> tuple[str, int | None]:
    """Read duration from duration_display_value (Duration button or mapped control)."""
    entry = labels.get("duration_display_value") or {}
    located = try_locate_frame_control(page, "duration_display_value", entry, timeout_ms=3000)
    if located is not None:
        text = located.locator.inner_text(timeout=3000).replace("\n", " ").strip()
        match = re.search(r"(\d{1,2})s", text)
        if match:
            return text, int(match.group(1))
    return _read_duration(page)


def _duration_popover_open(page: Any) -> bool:
    try:
        duration_btn = page.get_by_role("button", name="Duration").first
        expanded = duration_btn.get_attribute("aria-expanded")
        if expanded == "false":
            return False
        if expanded == "true":
            return True
    except Exception:
        pass
    try:
        slider = page.get_by_role("slider").first
        return slider.is_visible(timeout=500)
    except Exception:
        return False


def _dismiss_duration_popover(page: Any, labels: dict[str, Any]) -> None:
    """Click a safe neutral area outside the duration popover (prompt box preferred)."""
    for _ in range(3):
        prompt_entry = labels.get("frame_prompt_box") or {}
        prompt = try_locate_frame_control(page, "frame_prompt_box", prompt_entry, timeout_ms=2000)
        if prompt is not None:
            prompt.locator.click(timeout=3000, force=True, position={"x": 12, "y": 12})
            time.sleep(0.35)
        else:
            mode_entry = labels.get("kling_frame_to_video_mode") or {}
            mode = try_locate_frame_control(page, "kling_frame_to_video_mode", mode_entry, timeout_ms=2000)
            if mode is not None:
                mode.locator.click(timeout=3000, force=True)
                time.sleep(0.35)
            else:
                panel = page.locator('[class*="left-panel"]').first
                box = panel.bounding_box()
                if box:
                    page.mouse.click(box["x"] + 24, box["y"] + 48)
                    time.sleep(0.35)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        time.sleep(0.25)
        try:
            duration_btn = page.get_by_role("button", name="Duration").first
            if duration_btn.get_attribute("aria-expanded") == "true":
                duration_btn.click(timeout=2000, force=True)
                time.sleep(0.35)
        except Exception:
            pass
        if not _duration_popover_open(page):
            return


def _locate_duration_slider_track(page: Any) -> tuple[Any, str]:
    root = page.locator('[class*="Slider__Root"]').first
    try:
        root.wait_for(state="visible", timeout=4000)
        return root, "slider_root_class"
    except Exception:
        pass
    slider = page.get_by_role("slider").first
    slider.wait_for(state="visible", timeout=4000)
    return slider, "role_slider"


def _set_duration_slider_to_max(page: Any) -> None:
    _ensure_duration_panel(page)
    track, strategy = _locate_duration_slider_track(page)
    tbox = track.bounding_box()
    if not tbox:
        if strategy == "role_slider":
            track.focus()
            page.keyboard.press("End")
            time.sleep(0.35)
            return
        raise RuntimeError("slider track bounding box missing")
    page.mouse.click(tbox["x"] + tbox["width"] - 8, tbox["y"] + tbox["height"] / 2)
    time.sleep(0.35)


def _run_duration_sequence(
    page: Any,
    labels: dict[str, Any],
    result: KlingFrameLiveDryRunResult,
) -> None:
    """Drag slider to 15s, dismiss popover, verify value stable before audio/generate checks."""
    try:
        _set_duration_slider_to_max(page)
        result.locator_strategies["duration_slider_track"] = "slider_root_class"

        before_text, before_seconds = _read_duration_display_value(page, labels)
        result.duration_before_dismiss = before_text
        result.duration_seconds_before_dismiss = before_seconds
        result.duration_display = before_text
        result.duration_seconds = before_seconds
        result.popover_open_before_dismiss = _duration_popover_open(page)

        reaches_ok = before_seconds == KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS
        _mark_check(
            result,
            "duration_reaches_15s",
            reaches_ok,
            f"duration_display_value={before_text}",
        )
        if not reaches_ok:
            for check_id in KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS:
                if check_id not in result.checks:
                    _mark_check(result, check_id, False, "duration not 15s before dismiss")
            return

        _dismiss_duration_popover(page, labels)
        result.popover_open_after_dismiss = _duration_popover_open(page)
        popover_closed_ok = not result.popover_open_after_dismiss
        _mark_check(
            result,
            "duration_popover_closed",
            popover_closed_ok,
            f"slider_visible_after_dismiss={result.popover_open_after_dismiss}",
        )

        after_text, after_seconds = _read_duration_display_value(page, labels)
        result.duration_after_dismiss = after_text
        result.duration_seconds_after_dismiss = after_seconds
        result.duration_display = after_text
        result.duration_seconds = after_seconds

        stable_ok = after_seconds == KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS
        _mark_check(
            result,
            "duration_stable_after_dismiss",
            stable_ok,
            f"duration_display_value={after_text}",
        )
    except Exception as exc:
        for check_id in KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS:
            if check_id not in result.checks:
                _mark_check(result, check_id, False, str(exc)[:120])


def _read_duration(page: Any) -> tuple[str, int | None]:
    btn = page.get_by_role("button", name="Duration")
    text = btn.inner_text(timeout=5000).replace("\n", " ").strip()
    match = re.search(r"(\d{1,2})s", text)
    return text, int(match.group(1)) if match else None


def _ensure_duration_panel(page: Any) -> None:
    try:
        from content_brain.execution.runway_focus_dependency_probe import activate_page_for_interaction

        activate_page_for_interaction(page)
    except Exception:
        pass
    if not _duration_popover_open(page):
        page.get_by_role("button", name="Duration").click(timeout=8000, force=True)
        time.sleep(0.5)
    if not _duration_popover_open(page):
        page.get_by_role("button", name="Duration").click(timeout=8000, force=True)
        time.sleep(0.5)
    page.get_by_role("slider").first.wait_for(state="visible", timeout=8000)


def _ensure_frames_mode(page: Any, labels: dict[str, Any], result: KlingFrameLiveDryRunResult) -> bool:
    entry = labels.get("kling_frame_to_video_mode") or {}
    located = try_locate_frame_control(page, "kling_frame_to_video_mode", entry, timeout_ms=2500)
    if located:
        try:
            located.locator.click(timeout=4000, force=True)
            time.sleep(0.35)
            result.locator_strategies["frame_mode"] = located.strategy
            return True
        except Exception as exc:
            _step(result, "frame_mode", "select_frames", "warn", str(exc)[:120])
    for clicker in (
        lambda: page.get_by_text("Frames", exact=True).first,
        lambda: page.locator('label:has-text("Frames")').first,
    ):
        try:
            clicker().click(timeout=3000, force=True)
            time.sleep(0.35)
            result.locator_strategies["frame_mode"] = "text_frames_fallback"
            return True
        except Exception:
            continue
    return False


def _verify_audio_on(page: Any, labels: dict[str, Any], result: KlingFrameLiveDryRunResult) -> bool:
    entry = labels.get("audio_toggle_on") or {}
    located = try_locate_frame_control(page, "audio_toggle_on", entry, timeout_ms=3000)
    if located is None:
        return False
    result.locator_strategies["audio_on"] = located.strategy
    try:
        panel_text = page.locator('[class*="left-panel"]').first.inner_text(timeout=3000).lower()
    except Exception:
        panel_text = ""
    if re.search(r"\bon\b", panel_text) and "off" in panel_text:
        result.audio_state = "on"
        return True
    try:
        btn = page.get_by_role("button", name=re.compile(r"Audio settings", re.I)).first
        label = btn.inner_text(timeout=2000).lower()
        if "on" in label:
            result.audio_state = "on"
            return True
    except Exception:
        pass
    result.audio_state = "unknown_visible"
    return True


def run_kling_frame_live_dry_run_p2(
    *,
    cdp_url: str = DEFAULT_CDP_URL,
    map_path: Path | str | None = None,
    dry_run: bool = True,
    connect_browser: bool = True,
    starter_frame_path: str | Path | None = None,
    starter_image_prompt: str = "",
    topic: str = "",
) -> KlingFrameLiveDryRunResult:
    if not dry_run:
        raise ValueError("P2 supports dry_run=True only — no Generate, credits, or download")

    result = KlingFrameLiveDryRunResult(
        ok=False,
        dry_run=True,
        connect_browser=connect_browser,
        generate_clicked=False,
        download_clicked=False,
        credits_spent=False,
    )

    ui_map = load_kling_frame_ui_map(map_path=map_path or DEFAULT_MAP_PATH)
    snapshot = resolve_kling_frame_to_video_controls(ui_map)
    result.map_snapshot = snapshot.to_dict()

    gate_ok, gate_reason = verify_generate_approval_gate(ui_map)
    if not gate_ok:
        result.errors.append(gate_reason)
        _step(result, "00", "approval_gate", "failed", gate_reason)
        return result
    if not snapshot.ok:
        result.errors.append(f"map invalid missing={snapshot.missing}")
        _step(result, "00", "map_snapshot", "failed", str(snapshot.missing))
        return result

    _step(result, "00", "map_snapshot", "passed", f"labels={len(snapshot.controls)}")

    if starter_frame_path:
        frame_ok, frame_checks, frame_errors = validate_starter_frame_for_upload(
            frame_path=starter_frame_path,
            topic=topic,
            starter_image_prompt=starter_image_prompt,
        )
        result.starter_frame_path = str(Path(starter_frame_path).resolve()).replace("\\", "/")
        result.starter_frame_checks = dict(frame_checks)
        result.starter_frame_ready = frame_ok
        _step(
            result,
            "starter_frame",
            "first_frame_upload_ready",
            "passed" if frame_ok else "failed",
            str(frame_checks),
        )
        if not frame_ok:
            result.errors.extend(frame_errors)
            return result

    if not connect_browser:
        for check_id in KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS:
            result.checks[check_id] = True
        result.ok = True
        _step(result, "01", "cdp", "skipped", "map-only mode")
        return result

    labels = dict(ui_map.get("labels") or {})
    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        result.connect_browser = True
        _step(result, "01", "cdp", "passed", cdp_url)

        page = _find_runway_generate_page(browser)
        if page is None:
            result.errors.append("No Runway tab found")
            _step(result, "01", "runway_tab", "failed", "missing")
            return result

        if RUNWAY_GENERATE_URL_MARKER not in (page.url or ""):
            result.errors.append(
                "Runway generate page not open — navigate to Video Tools → Generate (Frames mode)"
            )
            _step(result, "01", "runway_tab", "failed", page.url[:120])
            return result

        result.page_url = page.url
        _step(result, "01", "runway_tab", "passed", page.url[:120])

        _ensure_frames_mode(page, labels, result)
        mode_entry = labels.get("kling_frame_to_video_mode") or {}
        mode = try_locate_frame_control(page, "kling_frame_to_video_mode", mode_entry, timeout_ms=3000)
        mode_ok = mode is not None
        if mode:
            result.locator_strategies["frame_mode"] = mode.strategy
        _mark_check(result, "frame_mode", mode_ok, mode.strategy if mode else "not found")

        prompt_entry = labels.get("frame_prompt_box") or {}
        prompt = try_locate_frame_control(page, "frame_prompt_box", prompt_entry, timeout_ms=3000)
        prompt_ok = prompt is not None
        if prompt:
            result.locator_strategies["prompt"] = prompt.strategy
        _mark_check(result, "prompt", prompt_ok, prompt.strategy if prompt else "not found")

        upload_entry = labels.get("first_frame_upload") or {}
        upload = try_locate_frame_control(page, "first_frame_upload", upload_entry, timeout_ms=3000)
        upload_ok = upload is not None
        if upload:
            result.locator_strategies["first_frame_upload"] = upload.strategy
        _mark_check(
            result,
            "first_frame_upload",
            upload_ok,
            upload.strategy if upload else "not found",
        )

        _run_duration_sequence(page, labels, result)

        if not all(result.checks.get(c) for c in KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS):
            failed_checks = [c for c in KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS if not result.checks.get(c)]
            result.ok = not failed_checks
            return result

        audio_ok = _verify_audio_on(page, labels, result)
        _mark_check(result, "audio_on", audio_ok, result.audio_state)

        gen_entry = labels.get("generate_button") or {}
        gen = try_locate_frame_control(page, "generate_button", gen_entry, timeout_ms=3000)
        gen_ok = gen is not None
        if gen:
            result.locator_strategies["generate_visible"] = gen.strategy
        _mark_check(result, "generate_visible", gen_ok, "visible only — not clicked" if gen_ok else "not found")

        if "generate_button" in BLOCKED_KLING_FRAME_CLICK_LABELS:
            _step(result, "99", "generate_not_clicked", "passed", "dry_run guard")

        failed_checks = [c for c in KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS if not result.checks.get(c)]
        result.ok = not failed_checks
        return result
    except Exception as exc:
        result.errors.append(str(exc))
        _step(result, "99", "runtime", "failed", str(exc)[:240])
        return result
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


__all__ = [
    "DEFAULT_CDP_URL",
    "KlingFrameLiveDryRunResult",
    "run_kling_frame_live_dry_run_p2",
]
