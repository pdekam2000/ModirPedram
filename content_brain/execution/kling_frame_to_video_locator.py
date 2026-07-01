"""Stable Playwright locators for Kling Frame-to-Video controls."""

from __future__ import annotations

import re
from typing import Any, Callable

from content_brain.execution.kling_frame_to_video_config import REQUIRED_KLING_FRAME_LABELS
from content_brain.execution.kling_multishot_locator import (
    LocatedControl,
    _strategy_css,
    _strategy_playwright_role_button_name,
    _strategy_playwright_text_exact,
    css_selector_is_unstable,
)
from content_brain.execution.kling_multishot_map_loader import label_playwright_hint
from content_brain.execution.runway_ui_map_loader import _css_selector, _entry_metadata

LocatorFactory = Callable[[Any], Any]


def _css_from_entry(entry: dict[str, Any]) -> str:
    meta = _entry_metadata(entry)
    return _css_selector(entry, meta)


def _build_strategies(label: str, entry: dict[str, Any]) -> list[tuple[str, LocatorFactory]]:
    css = _css_from_entry(entry)
    strategies: list[tuple[str, LocatorFactory]] = []

    if label == "kling_frame_to_video_mode":
        strategies.extend(
            [
                ("text_frames_exact", lambda p: _strategy_playwright_text_exact(p, text="Frames")),
                ("label_frames", lambda p: p.locator('label:has-text("Frames")')),
            ]
        )
    elif label == "frame_prompt_box":
        strategies.extend(
            [
                ("contenteditable_first", lambda p: p.locator('div[contenteditable="true"]').first),
                ("placeholder_describe_shot", lambda p: p.get_by_text("Describe your shot", exact=False)),
            ]
        )
    elif label == "first_frame_upload":
        strategies.extend(
            [
                ("upload_near_first_frame", lambda p: p.locator('text=First Video Frame').locator("..").get_by_text("Upload")),
                ("role_button_upload_first", lambda p: p.get_by_role("button", name=re.compile(r"Upload", re.I)).first),
            ]
        )
    elif label == "end_frame_upload":
        strategies.extend(
            [
                ("upload_near_last_frame", lambda p: p.locator('text=Last Video Frame').locator("..").get_by_text("Upload")),
                ("role_button_upload_nth1", lambda p: p.get_by_role("button", name=re.compile(r"Upload", re.I)).nth(1)),
            ]
        )
    elif label == "duration_slider_handle":
        strategies.extend(
            [
                ("role_slider", lambda p: p.get_by_role("slider").first),
                ("css_role_slider", lambda p: _strategy_css(p, css='[role="slider"]')),
            ]
        )
    elif label == "duration_slider_track":
        strategies.extend(
            [
                ("slider_root_class", lambda p: p.locator('[class*="Slider__Root"]').first),
                ("slider_track_near_handle", lambda p: p.get_by_role("slider").first.locator("xpath=..")),
            ]
        )
    elif label == "duration_display_value":
        strategies.extend(
            [
                ("role_button_duration", lambda p: p.get_by_role("button", name="Duration")),
                ("css_duration_button", lambda p: _strategy_css(p, css='button[aria-label="Duration"]')),
            ]
        )
    elif label == "audio_toggle_on":
        strategies.extend(
            [
                ("role_button_audio_settings", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"Audio settings", re.I))),
                ("text_on_toggle", lambda p: p.get_by_text("On", exact=True).first),
            ]
        )
    elif label == "generate_button":
        strategies.extend(
            [
                ("role_button_generate", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"^Generate$", re.I))),
                ("button_has_text_generate", lambda p: p.locator('button:has-text("Generate")')),
            ]
        )
    elif label == "download_button":
        strategies.extend(
            [
                ("aria_download", lambda p: p.locator('[aria-label*="Download" i]').first),
                ("download_icon", lambda p: p.locator('button[aria-label*="Download" i]').first),
            ]
        )
    elif label == "use_frame_button":
        strategies.extend(
            [
                ("text_use_frame", lambda p: p.get_by_text("Use frame", exact=False)),
                ("span_use_frame", lambda p: p.locator('span:has-text("Use frame")').first),
            ]
        )

    if css and not css_selector_is_unstable(css):
        strategies.append(("map_css_stable", lambda p, c=css: _strategy_css(p, css=c)))
    elif css:
        strategies.append(("map_css_unstable_fallback", lambda p, c=css: _strategy_css(p, css=c)))

    pw_hint = label_playwright_hint(entry)
    if pw_hint and css and not css_selector_is_unstable(css):
        strategies.append(("map_playwright_hint_css", lambda p, c=css: _strategy_css(p, css=c)))

    return strategies


def locate_frame_control(
    page: Any,
    label: str,
    entry: dict[str, Any],
    *,
    timeout_ms: int = 8000,
    require_stable: bool = False,
) -> LocatedControl:
    if label not in REQUIRED_KLING_FRAME_LABELS:
        raise ValueError(f"Unsupported Kling Frame label: {label}")

    errors: list[str] = []
    for strategy_name, factory in _build_strategies(label, entry):
        if require_stable and strategy_name in {"map_css_unstable_fallback"}:
            continue
        try:
            locator = factory(page).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            if locator.count() <= 0:
                errors.append(f"{strategy_name}: count=0")
                continue
            return LocatedControl(label=label, strategy=strategy_name, locator=locator)
        except Exception as exc:
            errors.append(f"{strategy_name}: {exc}")

    raise RuntimeError(f"Unable to locate {label} — tried {len(errors)} strategies: {' | '.join(errors[:4])}")


def try_locate_frame_control(
    page: Any,
    label: str,
    entry: dict[str, Any],
    *,
    timeout_ms: int = 3000,
) -> LocatedControl | None:
    try:
        return locate_frame_control(page, label, entry, timeout_ms=timeout_ms, require_stable=False)
    except RuntimeError:
        return None


__all__ = ["LocatedControl", "locate_frame_control", "try_locate_frame_control"]
