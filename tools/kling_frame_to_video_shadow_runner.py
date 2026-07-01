#!/usr/bin/env python3
"""Kling Frame-to-Video shadow runner — dry-run CDP validation (P1). No Generate. No credits."""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_config import (  # noqa: E402
    BLOCKED_KLING_FRAME_CLICK_LABELS,
    KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
    REQUIRED_KLING_FRAME_LABELS,
)
from content_brain.execution.kling_frame_to_video_locator import try_locate_frame_control  # noqa: E402
from content_brain.execution.kling_frame_to_video_map_loader import (  # noqa: E402
    load_kling_frame_ui_map,
    resolve_kling_frame_to_video_controls,
    verify_generate_approval_gate,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402

RUNNER_VERSION = "kling_frame_to_video_shadow_runner_v1"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
RUNWAY_URL_MARKER = "app.runwayml.com"
SCREENSHOT_DIR = ROOT / "project_brain" / "runway_ui_mapping" / "screenshots" / "kling_frame_to_video_p1"


@dataclass
class ShadowStep:
    step_id: str
    label: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"step_id": self.step_id, "label": self.label, "status": self.status, "detail": self.detail}


@dataclass
class KlingFrameShadowResult:
    ok: bool
    dry_run: bool
    connect_browser: bool
    generate_clicked: bool
    credits_spent: bool
    duration_before: str = ""
    duration_after_min: str = ""
    duration_after_max: str = ""
    duration_seconds_max: int | None = None
    steps: list[ShadowStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    locator_strategies: dict[str, str] = field(default_factory=dict)
    screenshots: dict[str, str] = field(default_factory=dict)
    map_snapshot: dict[str, Any] = field(default_factory=dict)
    page_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RUNNER_VERSION,
            "ok": self.ok,
            "dry_run": self.dry_run,
            "connect_browser": self.connect_browser,
            "generate_clicked": self.generate_clicked,
            "credits_spent": self.credits_spent,
            "duration_before": self.duration_before,
            "duration_after_min": self.duration_after_min,
            "duration_after_max": self.duration_after_max,
            "duration_seconds_max": self.duration_seconds_max,
            "steps": [s.to_dict() for s in self.steps],
            "errors": list(self.errors),
            "locator_strategies": dict(self.locator_strategies),
            "screenshots": dict(self.screenshots),
            "map_snapshot": dict(self.map_snapshot),
            "page_url": self.page_url,
        }


def _record_step(result: KlingFrameShadowResult, step_id: str, label: str, status: str, detail: str = "") -> None:
    result.steps.append(ShadowStep(step_id=step_id, label=label, status=status, detail=detail))


def _capture(page: Any, result: KlingFrameShadowResult, name: str) -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{stamp}.png"
    canonical = SCREENSHOT_DIR / f"{name}.png"
    last_error = ""

    try:
        session = page.context.new_cdp_session(page)
        shot = session.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        path.write_bytes(base64.b64decode(shot["data"]))
        shutil.copy2(path, canonical)
        result.screenshots[name] = str(canonical.resolve()).replace("\\", "/")
        return
    except Exception as exc:
        last_error = f"cdp: {exc}"

    try:
        page.locator('[class*="left-panel"]').first.screenshot(
            path=str(path),
            timeout=5000,
            animations="disabled",
        )
        shutil.copy2(path, canonical)
        result.screenshots[name] = str(canonical.resolve()).replace("\\", "/")
        return
    except Exception as exc:
        last_error = f"left_panel: {exc}"

    result.steps.append(
        ShadowStep(
            step_id="shot",
            label=f"screenshot_{name}",
            status="warn",
            detail=last_error[:180],
        )
    )


def _ensure_frames_mode(page: Any, labels: dict[str, Any], result: KlingFrameShadowResult) -> bool:
    entry = labels.get("kling_frame_to_video_mode") or {}
    located = try_locate_frame_control(page, "kling_frame_to_video_mode", entry, timeout_ms=2500)
    if located:
        try:
            located.locator.click(timeout=4000, force=True)
            time.sleep(0.4)
            _record_step(result, "19", "frames_mode", "passed", located.strategy)
            return True
        except Exception as exc:
            _record_step(result, "19", "frames_mode", "warn", str(exc)[:120])
    for clicker in (
        lambda: page.get_by_text("Frames", exact=True).first,
        lambda: page.locator('label:has-text("Frames")').first,
    ):
        try:
            tab = clicker()
            tab.click(timeout=3000, force=True)
            time.sleep(0.4)
            _record_step(result, "19", "frames_mode", "passed", "text_frames_fallback")
            return True
        except Exception:
            continue
    _record_step(result, "19", "frames_mode", "failed", "Frames tab not found")
    return False


def _read_duration_text(page: Any) -> tuple[str, int | None]:
    btn = page.get_by_role("button", name="Duration")
    text = btn.inner_text(timeout=5000).replace("\n", " ").strip()
    match = re.search(r"(\d{1,2})s", text)
    return text, int(match.group(1)) if match else None


def _ensure_duration_panel_open(page: Any) -> None:
    if page.get_by_role("slider").count() == 0:
        page.get_by_role("button", name="Duration").click(timeout=8000, force=True)
        time.sleep(0.4)
    page.get_by_role("slider").first.wait_for(state="visible", timeout=8000)


def run_kling_frame_to_video_shadow(
    *,
    cdp_url: str = DEFAULT_CDP_URL,
    map_path: Path | str | None = None,
    dry_run: bool = True,
    connect_browser: bool = True,
) -> KlingFrameShadowResult:
    if not dry_run:
        raise ValueError("Only dry_run=True is supported — Generate is never clicked")

    result = KlingFrameShadowResult(
        ok=False,
        dry_run=True,
        connect_browser=connect_browser,
        generate_clicked=False,
        credits_spent=False,
    )

    ui_map = load_kling_frame_ui_map(map_path=map_path or DEFAULT_MAP_PATH)
    snapshot = resolve_kling_frame_to_video_controls(ui_map)
    result.map_snapshot = snapshot.to_dict()
    gate_ok, gate_reason = verify_generate_approval_gate(ui_map)
    if not gate_ok:
        result.errors.append(gate_reason)
        _record_step(result, "00", "approval_gate", "failed", gate_reason)
        return result
    if not snapshot.ok:
        result.errors.append(f"missing={snapshot.missing} invalid={snapshot.invalid}")
        _record_step(result, "00", "map_snapshot", "failed", str(snapshot.missing))
        return result

    _record_step(result, "00", "map_snapshot", "passed", f"labels={len(snapshot.controls)}")
    if not connect_browser:
        result.ok = True
        _record_step(result, "01", "cdp", "skipped", "map-only mode")
        return result

    labels = dict(ui_map.get("labels") or {})
    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        result.connect_browser = True
        _record_step(result, "01", "cdp", "passed", cdp_url)

        page = None
        for context in browser.contexts:
            for candidate in context.pages:
                if RUNWAY_URL_MARKER in candidate.url:
                    page = candidate
                    break
            if page:
                break
        if page is None:
            result.errors.append("No Runway tab found")
            _record_step(result, "01", "runway_tab", "failed", "missing")
            return result

        result.page_url = page.url
        _record_step(result, "01", "runway_tab", "passed", page.url[:120])

        _ensure_frames_mode(page, labels, result)

        slider_panel_labels = frozenset({"duration_slider_handle", "duration_slider_track"})
        for idx, label in enumerate(REQUIRED_KLING_FRAME_LABELS, start=2):
            if label in slider_panel_labels or label == "generate_button":
                continue
            _locate_required_label(page, labels, label, result, step_id=f"{idx:02d}")

        frames_entry = labels.get("kling_frame_to_video_mode") or {}
        frames = try_locate_frame_control(page, "kling_frame_to_video_mode", frames_entry, timeout_ms=4000)
        if frames:
            try:
                frames.locator.click(timeout=5000, force=True)
                time.sleep(0.3)
            except Exception as exc:
                _record_step(result, "20", "frame_mode_selected", "warn", str(exc)[:120])
        _capture(page, result, "frame_mode_selected")

        try:
            _ensure_duration_panel_open(page)
        except Exception as exc:
            result.errors.append(f"duration panel: {exc}")
            _record_step(result, "21", "duration_panel", "failed", str(exc)[:120])
        else:
            for label in slider_panel_labels:
                _locate_required_label(page, labels, label, result, step_id="08")
            _locate_required_label(page, labels, "duration_display_value", result, step_id="08")

            before_text, _before_val = _read_duration_text(page)
            result.duration_before = before_text
            _capture(page, result, "duration_before")
            _record_step(result, "21", "duration_read_before", "passed", before_text)

            track = page.locator('[class*="Slider__Root"]').first
            try:
                track.wait_for(state="visible", timeout=4000)
                tbox = track.bounding_box()
            except Exception:
                _ensure_duration_panel_open(page)
                track.wait_for(state="visible", timeout=4000)
                tbox = track.bounding_box()
            if not tbox:
                result.errors.append("slider track bounding box missing")
                _record_step(result, "22", "duration_slider_track", "failed", "no bounding box")
            else:
                page.mouse.click(tbox["x"] + 8, tbox["y"] + tbox["height"] / 2)
                time.sleep(0.35)
                min_text, _ = _read_duration_text(page)
                result.duration_after_min = min_text
                page.mouse.click(tbox["x"] + tbox["width"] - 8, tbox["y"] + tbox["height"] / 2)
                time.sleep(0.35)
                max_text, max_val = _read_duration_text(page)
                result.duration_after_max = max_text
                result.duration_seconds_max = max_val
                _capture(page, result, "duration_after_15s")
                _record_step(result, "22", "duration_slider_move", "passed", f"min={min_text}; max={max_text}")
                if max_val != KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS:
                    result.errors.append(
                        f"max duration expected {KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS}s got {max_val}"
                    )

        audio_entry = labels.get("audio_toggle_on") or {}
        audio = try_locate_frame_control(page, "audio_toggle_on", audio_entry, timeout_ms=4000)
        if audio:
            result.locator_strategies.setdefault("audio_toggle_on", audio.strategy)
            _record_step(result, "23", "audio_on", "passed", audio.strategy)
        _capture(page, result, "audio_on")

        _locate_required_label(page, labels, "generate_button", result, step_id="24", optional=False)
        if "generate_button" in result.locator_strategies:
            _record_step(result, "24", "generate_visible", "passed", "visible only — not clicked")
        _capture(page, result, "generate_visible")

        for blocked in BLOCKED_KLING_FRAME_CLICK_LABELS:
            if blocked == "generate_button":
                _record_step(result, "25", "generate_not_clicked", "passed", "dry_run guard")

        result.ok = not result.errors
        return result
    except Exception as exc:
        result.errors.append(str(exc))
        _record_step(result, "99", "runtime", "failed", str(exc)[:240])
        return result
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def _locate_required_label(
    page: Any,
    labels: dict[str, Any],
    label: str,
    result: KlingFrameShadowResult,
    *,
    step_id: str,
    optional: bool = False,
) -> None:
    entry = labels.get(label)
    if label == "download_button" and not isinstance(entry, dict):
        entry = labels.get("download_mp4_button")
    if not isinstance(entry, dict):
        if optional:
            _record_step(result, step_id, label, "skipped", "missing map entry")
            return
        result.errors.append(f"missing map entry: {label}")
        _record_step(result, step_id, label, "failed", "missing map entry")
        return
    located = try_locate_frame_control(page, label, entry, timeout_ms=2500)
    if located is None:
        if optional or label in {"download_button", "use_frame_button"}:
            _record_step(result, step_id, label, "skipped", "not visible until needed")
            return
        result.errors.append(f"unable to locate {label}")
        _record_step(result, step_id, label, "failed", "not found")
        return
    result.locator_strategies[label] = located.strategy
    _record_step(result, step_id, label, "passed", f"strategy={located.strategy}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kling Frame-to-Video shadow dry-run (P1)")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    args = parser.parse_args()

    result = run_kling_frame_to_video_shadow(cdp_url=args.cdp_url, map_path=args.map_path, dry_run=True)
    summary_path = ROOT / "project_brain" / "kling_frame_to_video_shadow_summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2), flush=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
