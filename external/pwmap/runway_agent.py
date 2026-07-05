#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runway video generation agent — Kling 3.0 Pro automation.

Single clip:
    python runway_agent.py --prompt "your prompt here"

Batch clips (clip 1 = fresh, clip 2+ = Use frame from last second of previous video):
    python runway_agent.py --job agent_inbox/batch.json

Job JSON:
    {"prompts": ["clip1", "clip2"], "duration": 15, "aspect": "9:16", "use_frame_second": 14}
    use_frame_second defaults to duration - 1 (14 for 15s clips).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, sync_playwright

from pwmap import launch_browser_context
from exit_codes import EXIT_CODE_MEANINGS, EXIT_RUNTIME_ERROR, EXIT_SESSION_NOT_READY

_logger = logging.getLogger("runway_agent")
RUNWAY_APP_URL = "https://app.runwayml.com/"
SESSION_REL = Path("project_brain") / "sessions" / "runway_session.json"

from download_selection import (
    build_clip_status,
    detect_new_output,
    feed_download_pattern,
    reject_duplicate_mp4,
    reject_stale_source,
    sha256_file,
    write_inspection_report,
)

MAX_PROMPT_LEN = 2500
DEFAULT_RUNWAY_URL = (
    "https://app.runwayml.com/video-tools/teams/kamangarpedram/"
    "ai-tools/generate?tool=video&mode=tools"
)
DOWNLOADS_DIR = Path.cwd() / "runway_downloads"
INBOX_DIR = Path.cwd() / "agent_inbox"


def resolve_project_root() -> Path:
    env = os.environ.get("MODIR_PROJECT_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for candidate in (here.parent.parent, here.parent, Path.cwd(), *here.parents):
        if (candidate / "project_brain").is_dir():
            return candidate.resolve()
    return Path.cwd().resolve()


def runway_session_path(project_root: Path | None = None) -> Path:
    root = project_root or resolve_project_root()
    path = root / SESSION_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def is_runway_login_page(url: str) -> bool:
    lowered = str(url or "").lower()
    return any(token in lowered for token in ("/login", "/sign-in", "/signup", "auth."))


def save_runway_session(context: BrowserContext, project_root: Path | None = None) -> Path:
    path = runway_session_path(project_root)
    context.storage_state(path=str(path))
    _logger.info("Runway session saved: %s", path)
    print(f"[OK] Runway session saved: {path}")
    return path


def validate_runway_session(page: Page) -> tuple[bool, str]:
    try:
        page.goto(RUNWAY_APP_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1500)
        if is_runway_login_page(str(page.url or "")):
            return False, "Runway session expired — manual login required"
        return True, "Runway session restored OK"
    except Exception as exc:
        return False, f"Session validation failed: {exc}"


def _notify_session_status(project_root: Path, *, connected: bool, message: str) -> None:
    status_path = project_root / "project_brain" / "sessions" / "runway_session_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(
            {
                "connected": connected,
                "disconnected": not connected,
                "message": message,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def resolve_browser_launch_options(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or resolve_project_root()
    profile_dir = root / "storage" / "real_chrome_profile"
    session_path = runway_session_path(root)
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        from automation.browser_launcher import resolve_runway_browser_config

        config = resolve_runway_browser_config(root)
        profile_dir = Path(config["profile_path"])
    except Exception:
        pass
    return {
        "project_root": root,
        "profile_dir": profile_dir,
        "storage_state_path": session_path if session_path.is_file() else None,
    }


def launch_runway_browser_context(
    playwright: Any,
    *,
    headless: bool,
    stealth: bool,
    project_root: Path | None = None,
) -> BrowserContext:
    options = resolve_browser_launch_options(project_root)
    return launch_browser_context(
        playwright,
        headless=headless,
        stealth=stealth,
        profile_dir=options["profile_dir"],
        storage_state_path=options["storage_state_path"],
        prefer_cdp=not headless,
    )


MODEL_LABELS = ("Kling 3.0 Pro", "Kling 3 Pro", "Kling 3.0")
ASPECT_LABELS = ("9:16", "9 : 16", "Portrait", "Vertical")
DURATION_LABELS = ("15s", "15 s", "15 sec", "15 seconds", "15")


class RunwayAgentError(Exception):
    pass


def prepare_runway_session(page: Page, context: BrowserContext, project_root: Path) -> None:
    session_path = runway_session_path(project_root)
    if not session_path.is_file() or session_path.stat().st_size == 0:
        message = (
            "No Runway session file at project_brain/sessions/runway_session.json. "
            "Connect Runway Browser first."
        )
        print(f"[ERROR] {message}")
        _notify_session_status(project_root, connected=False, message=message)
        raise RunwayAgentError(message)

    ok, message = validate_runway_session(page)
    if ok:
        print(message)
        save_runway_session(context, project_root)
        _notify_session_status(project_root, connected=True, message=message)
        return
    print(message)
    _notify_session_status(project_root, connected=False, message=message)
    raise RunwayAgentError(message)


def clamp_prompt(text: str, limit: int = MAX_PROMPT_LEN) -> str:
    text = text.strip()
    if not text:
        raise RunwayAgentError("Prompt is empty.")
    if len(text) > limit:
        print(f"[warn] Prompt trimmed from {len(text)} to {limit} chars.")
        return text[:limit]
    return text


def load_job(path: Path) -> tuple[list[str], dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        job = json.load(fh)

    if "prompts" in job:
        raw = job["prompts"]
        if not isinstance(raw, list) or not raw:
            raise RunwayAgentError("'prompts' must be a non-empty list.")
        return [clamp_prompt(str(p)) for p in raw], job

    prompt = job.get("prompt") or job.get("text") or job.get("message")
    if not prompt:
        raise RunwayAgentError(f"No 'prompt' or 'prompts' in job file: {path}")
    return [clamp_prompt(str(prompt))], job


def load_prompt_from_job(path: Path) -> tuple[str, dict[str, Any]]:
    prompts, job = load_job(path)
    return prompts[0], job


def load_prompt_from_stdin() -> str:
    raw = sys.stdin.read().strip()
    if not raw:
        raise RunwayAgentError("Empty stdin.")
    try:
        payload = json.loads(raw)
        prompt = payload.get("prompt") or payload.get("text") or payload
        if isinstance(prompt, dict):
            raise RunwayAgentError("JSON stdin must contain a prompt string.")
        return clamp_prompt(str(prompt))
    except json.JSONDecodeError:
        return clamp_prompt(raw)


def click_popover_option(page: Page, *patterns: str, timeout_ms: int = 10_000) -> bool:
    """Click an option inside an open popover/menu."""
    deadline = time.time() + timeout_ms / 1000
    selectors = (
        "[role='menuitem']",
        "[role='option']",
        "[role='radio']",
        "[data-radix-collection-item]",
        "button",
        "li",
        "div",
    )
    while time.time() < deadline:
        for pattern in patterns:
            regex = re.compile(pattern, re.I)
            for sel in selectors:
                try:
                    items = page.locator(sel).filter(has_text=regex)
                    count = items.count()
                    for i in range(min(count, 8)):
                        item = items.nth(i)
                        if item.is_visible(timeout=300):
                            item.click()
                            return True
                except Exception:
                    continue
        page.wait_for_timeout(300)
    return False


def click_first_match(page: Page, labels: tuple[str, ...], timeout_ms: int = 8000) -> bool:
    """Click the first visible element matching any label (menuitem/option/button/text)."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for label in labels:
            pattern = re.compile(re.escape(label), re.I)
            locators = [
                page.get_by_role("menuitem", name=pattern),
                page.get_by_role("option", name=pattern),
                page.get_by_role("radio", name=pattern),
                page.get_by_role("button", name=pattern),
                page.get_by_text(pattern),
            ]
            for loc in locators:
                try:
                    target = loc.first
                    if target.is_visible(timeout=500):
                        target.click()
                        return True
                except Exception:
                    continue
        page.wait_for_timeout(300)
    return False


def wait_and_click(page: Page, locator_fn, description: str, timeout_ms: int = 30_000) -> None:
    deadline = time.time() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            loc = locator_fn()
            loc.wait_for(state="visible", timeout=2000)
            loc.click()
            return
        except Exception as exc:
            last_error = exc
            page.wait_for_timeout(400)
    raise RunwayAgentError(f"Could not click {description}: {last_error}")


def ensure_video_mode(page: Page) -> None:
    video = page.get_by_role("radio", name="Video")
    try:
        if video.is_visible(timeout=3000) and not video.is_checked():
            video.click()
            page.wait_for_timeout(400)
    except Exception:
        pass


def select_model(page: Page, model: str) -> None:
    print("[step] Selecting video model...")
    wait_and_click(
        page,
        lambda: page.get_by_test_id("select-base-model"),
        "Video models button",
    )
    page.wait_for_timeout(800)
    labels = (model, *MODEL_LABELS)
    if not click_first_match(page, labels, timeout_ms=12_000):
        if not click_popover_option(page, *labels):
            raise RunwayAgentError(f"Could not select model: {model}")
    print(f"[OK] Model selected: {model}")
    page.wait_for_timeout(500)


def select_aspect_ratio(page: Page, aspect: str = "9:16") -> None:
    print("[step] Setting aspect ratio...")
    btn = page.get_by_role("button", name="Aspect ratio")
    try:
        if aspect.replace(" ", "") in (btn.inner_text() or "").replace(" ", ""):
            print(f"[OK] Aspect already {aspect}")
            return
    except Exception:
        pass
    wait_and_click(page, lambda: btn, "Aspect ratio button")
    page.wait_for_timeout(600)
    labels = (aspect, *ASPECT_LABELS)
    if not click_first_match(page, labels, timeout_ms=10_000):
        if not click_popover_option(page, *labels, r"9.?16", r"portrait", r"vertical"):
            raise RunwayAgentError(f"Could not select aspect ratio: {aspect}")
    print(f"[OK] Aspect ratio: {aspect}")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)


def _duration_button_text(page: Page) -> str:
    btn = page.get_by_role("button", name="Duration")
    try:
        return (btn.inner_text() or "").strip()
    except Exception:
        return ""


def _duration_is_set(page: Page, seconds: int) -> bool:
    text = _duration_button_text(page)
    return bool(re.search(rf"\b{seconds}\s*s\b", text, re.I))


def _find_duration_popover(page: Page):
    """Locate the open Duration popover (contains title + 3s + 15s labels)."""
    return page.locator("div").filter(
        has=page.get_by_text("Duration", exact=True)
    ).filter(has=page.get_by_text("3s", exact=True)).filter(
        has=page.get_by_text("15s", exact=True)
    ).last


def set_duration_slider(page: Page, seconds: int = 15) -> bool:
    """Set Runway duration slider to max (15s) inside the Duration popover."""
    popover = _find_duration_popover(page)
    try:
        popover.wait_for(state="visible", timeout=5000)
    except Exception:
        return False

    slider = popover.locator('[role="slider"]').first

    # Method 1: keyboard End = jump to max on ARIA slider
    if slider.count() > 0:
        try:
            slider.focus()
            page.wait_for_timeout(150)
            page.keyboard.press("End")
            page.wait_for_timeout(500)
            if _duration_is_set(page, seconds):
                return True
            for _ in range(15):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(80)
            if _duration_is_set(page, seconds):
                return True
        except Exception:
            pass

    # Method 2: click the numeric box (top-right "5 s") and type 15
    try:
        num_box = popover.get_by_text(re.compile(r"^\d+\s*s$", re.I)).first
        if num_box.is_visible(timeout=1000):
            num_box.click(click_count=3)
            page.wait_for_timeout(100)
            page.keyboard.press("Control+A")
            page.keyboard.type(str(seconds))
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
            if _duration_is_set(page, seconds):
                return True
    except Exception:
        pass

    try:
        num_input = popover.locator("input").first
        if num_input.is_visible(timeout=1000):
            num_input.click(click_count=3)
            num_input.fill(str(seconds))
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
            if _duration_is_set(page, seconds):
                return True
    except Exception:
        pass

    label_3 = label_15 = None
    try:
        label_3 = popover.get_by_text("3s", exact=True).first.bounding_box()
        label_15 = popover.get_by_text("15s", exact=True).first.bounding_box()
    except Exception:
        pass

    # Method 3: click on the slider track at the far right (near "15s")
    if label_3 and label_15:
        try:
            slider_box = slider.bounding_box() if slider.count() > 0 else None
            y = (
                slider_box["y"] + slider_box["height"] / 2
                if slider_box
                else label_3["y"] + label_3["height"] / 2
            )
            x = label_15["x"] - 6
            page.mouse.click(x, y)
            page.wait_for_timeout(500)
            if _duration_is_set(page, seconds):
                return True
        except Exception:
            pass

    # Method 4: drag thumb to the right end of the track
    if slider.count() > 0 and label_3 and label_15:
        try:
            handle_box = slider.bounding_box()
            if handle_box:
                hx = handle_box["x"] + handle_box["width"] / 2
                hy = handle_box["y"] + handle_box["height"] / 2
                target_x = label_15["x"] - 4
                page.mouse.move(hx, hy)
                page.mouse.down()
                page.mouse.move(target_x, hy, steps=30)
                page.mouse.up()
                page.wait_for_timeout(600)
                if _duration_is_set(page, seconds):
                    return True
        except Exception:
            pass

    return _duration_is_set(page, seconds)


def select_duration(page: Page, seconds: int = 15) -> None:
    print("[step] Setting duration...")
    if _duration_is_set(page, seconds):
        print(f"[OK] Duration already {seconds}s")
        return

    btn = page.get_by_role("button", name="Duration")
    wait_and_click(page, lambda: btn, "Duration button")
    page.wait_for_timeout(900)

    for attempt in range(1, 4):
        print(f"[i] Duration slider attempt {attempt}/3...")
        if set_duration_slider(page, seconds):
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            print(f"[OK] Duration: {seconds}s (button shows: {_duration_button_text(page)})")
            return
        page.wait_for_timeout(500)

    page.keyboard.press("Escape")
    raise RunwayAgentError(
        f"Duration still not {seconds}s (current: {_duration_button_text(page) or 'unknown'})"
    )


def fill_prompt(page: Page, prompt: str) -> None:
    print("[step] Filling prompt...")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    box = page.get_by_role("textbox", name="Prompt")
    box.scroll_into_view_if_needed()
    try:
        box.click(force=True, timeout=5000)
    except Exception:
        page.locator("#text-prompt").click(force=True, timeout=5000)
    page.wait_for_timeout(200)

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(prompt)
    page.wait_for_timeout(300)
    print(f"[OK] Prompt filled ({len(prompt)} chars)")


def click_generate(page: Page) -> None:
    print("[step] Clicking Generate...")
    btn = page.get_by_role("button", name=re.compile(r"^Generate$", re.I))
    wait_and_click(page, lambda: btn, "Generate button")
    print("[i] Generate clicked — waiting for video (this can take several minutes)...")


def _feed_panel(page: Page):
    return page.get_by_test_id("virtuoso-scroller").first


def _feed_top_card(page: Page):
    """Newest generation card — first video inside the feed scroller."""
    feed = _feed_panel(page)
    video = feed.locator("video").first
    if video.count() == 0:
        return feed.locator("div").first
    return video.locator("xpath=ancestor::div[contains(@class,'group') or @data-index][1]").first


def ensure_feed_view(page: Page) -> None:
    """Make sure the generation feed panel is visible."""
    try:
        feed_btn = page.get_by_role("button", name=re.compile(r"Feed view", re.I))
        if feed_btn.is_visible(timeout=2000):
            feed_btn.click()
            page.wait_for_timeout(600)
    except Exception:
        pass


def snapshot_feed(page: Page) -> dict[str, Any]:
    """Capture feed state before Generate so we only track the new clip."""
    feed = _feed_panel(page)
    videos = feed.locator("video")
    count = videos.count()
    srcs: list[str] = []
    for i in range(count):
        src = videos.nth(i).get_attribute("src") or ""
        if src:
            srcs.append(src)
    item_count = feed.locator("[data-index]").count()
    feed_text = ""
    try:
        feed_text = feed.inner_text(timeout=1500)[:800]
    except Exception:
        pass
    return {"count": count, "srcs": srcs, "item_count": item_count, "feed_text": feed_text}


def _page_shows_generating(page: Page) -> bool:
    """Runway UI hints that a generation job is in progress."""
    try:
        if page.get_by_role("button", name=re.compile(r"Helpful Apps when generating", re.I)).is_visible(timeout=400):
            return True
    except Exception:
        pass
    try:
        if page.get_by_text(re.compile(r"generating|processing|queued|creating", re.I)).first.is_visible(timeout=400):
            return True
    except Exception:
        pass
    return False


def _feed_has_new_generation(page: Page, baseline: dict[str, Any]) -> bool:
    feed = _feed_panel(page)
    videos = feed.locator("video")
    count = videos.count()
    baseline_count = baseline.get("video_count", baseline.get("count", 0))
    if count > baseline_count:
        return True
    if count == 0:
        pass
    else:
        top_src = videos.first.get_attribute("src") or ""
        baseline_srcs = baseline.get("srcs")
        if baseline_srcs is None:
            baseline_srcs = [
                str(entry.get("currentSrc") or entry.get("src") or "")
                for entry in (baseline.get("videos") or [])
            ]
        if top_src and top_src not in baseline_srcs:
            return True

    try:
        item_count = feed.locator("[data-index]").count()
        if item_count > baseline.get("item_count", 0):
            return True
    except Exception:
        pass

    try:
        if feed.get_by_text(re.compile(r"generating|processing|queued|\d+\s*%", re.I)).first.is_visible(timeout=400):
            return True
    except Exception:
        pass

    try:
        text = feed.inner_text(timeout=1000)[:800]
        if text != baseline.get("feed_text", "") and re.search(
            r"generating|processing|queued|\d+\s*%", text, re.I
        ):
            return True
    except Exception:
        pass

    if _page_shows_generating(page):
        return True

    return False


def _reveal_top_card(page: Page) -> Any:
    """Scroll to and hover the newest clip so action buttons appear underneath."""
    feed = _feed_panel(page)
    video = feed.locator("video").first
    if video.count() > 0 and video.first.is_visible(timeout=1000):
        video.first.scroll_into_view_if_needed()
        box = video.first.bounding_box()
        if box:
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(700)
        else:
            video.first.hover()
            page.wait_for_timeout(600)
    card = _feed_top_card(page)
    if card.count() > 0:
        card.first.scroll_into_view_if_needed()
    return card


def _card_action_buttons(card: Any):
    """Buttons that only appear after a clip has fully finished generating."""
    use_frame = card.get_by_role("button", name=re.compile(r"use\s*(as\s*)?frame", re.I))
    if use_frame.count() == 0:
        use_frame = card.get_by_text(re.compile(r"use\s*(as\s*)?frame", re.I))
    download = card.get_by_role("button", name=re.compile(r"download", re.I))
    return use_frame, download


def _clip_fully_built(page: Page) -> bool:
    """
    A clip is done only when Download or Use frame is visible under that clip.
    Video src alone is NOT enough — the button appears only after full render.
    """
    try:
        card = _reveal_top_card(page)
        if card.count() == 0:
            return False

        use_frame, download = _card_action_buttons(card)
        if use_frame.count() > 0 and use_frame.first.is_visible(timeout=600):
            return True

        for i in range(download.count()):
            btn = download.nth(i)
            label = ((btn.get_attribute("aria-label") or "") + " " + btn.inner_text()).lower()
            if "all" in label:
                continue
            if btn.is_visible(timeout=400):
                return True
    except Exception:
        pass

    return False


def _top_card_still_generating(page: Page) -> bool:
    """Check loading state on the newest feed item only."""
    try:
        card = _feed_top_card(page)
        if card.count() == 0:
            return True
        text = card.inner_text(timeout=500).lower()
        if re.search(r"generating|processing|queued|creating|loading|\d+\s*%", text):
            return True
    except Exception:
        pass

    try:
        feed = _feed_panel(page)
        spinner = feed.locator("[class*='loading'], [class*='spinner'], [class*='progress']").first
        if spinner.is_visible(timeout=200):
            return True
    except Exception:
        pass

    return False


def _generation_finished(page: Page, baseline: dict[str, Any]) -> bool:
    """Clip is complete only when action buttons show under the new clip card."""
    if not _feed_has_new_generation(page, baseline):
        return False

    if _top_card_still_generating(page):
        return False

    return _clip_fully_built(page)


def wait_for_video_ready(page: Page, baseline: dict[str, Any], timeout_sec: int = 900) -> None:
    """Wait until the new clip is fully rendered (Download / Use frame visible)."""
    deadline = time.time() + timeout_sec
    last_log = 0.0
    saw_new_item = False
    ensure_feed_view(page)

    while time.time() < deadline:
        try:
            if _feed_has_new_generation(page, baseline):
                saw_new_item = True

            if saw_new_item and _generation_finished(page, baseline):
                print("[OK] Clip fully built — Download / Use frame visible.")
                return

            if time.time() - last_log > 20:
                if not saw_new_item:
                    if _page_shows_generating(page):
                        print("[i] Generation started — waiting for clip in feed...")
                        saw_new_item = True
                    else:
                        print("[i] Waiting for generation to start in feed...")
                elif _top_card_still_generating(page):
                    print("[i] Clip still generating — waiting until fully built...")
                else:
                    print("[i] Clip rendering — waiting for Download / Use frame button...")
                last_log = time.time()

            page.wait_for_timeout(4000)
        except Exception as exc:
            if "closed" in str(exc).lower():
                raise RunwayAgentError("Browser was closed while waiting for video generation.") from exc
            raise

    raise RunwayAgentError(f"Generation timed out after {timeout_sec}s.")


def _wait_for_top_video_identity(page: Page, timeout_ms: int = 6000) -> None:
    """After the 'fully built' signal (Download/Use-frame buttons visible),
    wait until the newest video element actually exposes a currentSrc/src/poster.
    The action buttons can render slightly before the <video> tag's identity
    is populated, which would otherwise make detect_new_output() unable to
    tell the new clip apart from the previous one."""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        feed = _feed_panel(page)
        videos = feed.locator("video")
        if videos.count() > 0:
            top = videos.first
            try:
                identity = top.evaluate(
                    "el => (el.currentSrc || el.getAttribute('src') || el.getAttribute('poster') || '')"
                )
            except Exception:
                identity = ""
            if str(identity or "").strip():
                return
        page.wait_for_timeout(300)


def wait_for_use_frame_button(page: Page, timeout_sec: int = 900) -> None:
    """Wait until 'Use frame' appears under the previous (completed) clip."""
    print("[i] Waiting for 'Use frame' under previous clip (appears only when video is done)...")
    deadline = time.time() + timeout_sec
    last_log = 0.0

    while time.time() < deadline:
        try:
            card = _reveal_top_card(page)
            use_frame, _ = _card_action_buttons(card)
            if use_frame.count() > 0 and use_frame.first.is_visible(timeout=800):
                print("[OK] 'Use frame' is visible under previous clip.")
                return
        except Exception:
            pass

        if time.time() - last_log > 20:
            print("[i] Previous clip not ready yet — 'Use frame' not shown. Still waiting...")
            last_log = time.time()

        page.wait_for_timeout(4000)

    raise RunwayAgentError(
        "'Use frame' never appeared — previous clip may not have finished generating."
    )


def hover_latest_generation(page: Page) -> None:
    """Hover the newest generated video card in the feed panel."""
    feed = _feed_panel(page)
    if feed.count() == 0:
        raise RunwayAgentError("Feed panel not found.")

    _reveal_top_card(page)


def _feed_top_video(page: Page):
    return _feed_panel(page).locator("video").first


def seek_video_for_use_frame(
    page: Page,
    duration_sec: int,
    *,
    frame_second: float | None = None,
) -> float:
    """
    Seek the previous clip preview to the last frame before Use frame.
    For 15s clips we target second 14 (duration - 1).
    """
    target = frame_second if frame_second is not None else max(float(duration_sec) - 1.0, 0.0)
    print(f"[step] Seeking previous clip to second {target:g} (last frame)...")

    video = _feed_top_video(page)
    if video.count() == 0:
        raise RunwayAgentError("No video in feed to seek for Use frame.")

    video.first.scroll_into_view_if_needed()
    try:
        video.first.click(timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(400)

    try:
        video.first.evaluate(
            """(el, t) => {
                el.pause();
                const dur = Number.isFinite(el.duration) && el.duration > 0 ? el.duration : t + 1;
                el.currentTime = Math.min(t, Math.max(dur - 0.05, 0));
            }""",
            target,
        )
        page.wait_for_timeout(700)
        current = float(video.first.evaluate("el => el.currentTime"))
        print(f"[OK] Video at {current:.2f}s (target {target:g}s)")
        if current >= target - 1.0 or current >= max(duration_sec - 2, 0):
            return current
    except Exception as exc:
        print(f"[i] JS seek note: {exc}")

    card = _feed_top_card(page)
    for sel in ("input[type='range']", "[role='slider']"):
        try:
            slider = card.locator(sel).first
            if slider.count() > 0 and slider.is_visible(timeout=500):
                box = slider.bounding_box()
                if box:
                    ratio = min(target / max(float(duration_sec), 1.0), 0.98)
                    page.mouse.click(
                        box["x"] + box["width"] * ratio,
                        box["y"] + box["height"] / 2,
                    )
                    page.wait_for_timeout(600)
                    print(f"[OK] Timeline scrubbed to ~{target:g}s")
                    return target
        except Exception:
            continue

    print(f"[warn] Seek to {target:g}s not verified — continuing with Use frame.")
    return target


def click_use_frame(
    page: Page,
    *,
    duration: int,
    frame_second: float | None = None,
) -> None:
    """Seek to the last frame, then click Use frame under the previous clip."""
    print("[step] Use frame from previous clip (last frame)...")
    wait_for_use_frame_button(page)

    card = _feed_top_card(page)
    _reveal_top_card(page)
    seek_video_for_use_frame(page, duration, frame_second=frame_second)
    _reveal_top_card(page)

    for attempt in range(1, 4):
        use_frame, _ = _card_action_buttons(card)
        try:
            if use_frame.count() > 0:
                for i in range(use_frame.count()):
                    btn = use_frame.nth(i)
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        page.wait_for_timeout(1500)
                        print("[OK] Use frame clicked (last frame).")
                        return
        except Exception:
            pass

        try:
            buttons = card.locator("button:visible")
            for i in range(buttons.count()):
                btn = buttons.nth(i)
                label = ((btn.get_attribute("aria-label") or "") + " " + btn.inner_text()).lower()
                if ("use" in label and "frame" in label) or label.strip() in {"use frame", "use as frame"}:
                    btn.click()
                    page.wait_for_timeout(1500)
                    print(f"[OK] Use frame clicked ({label.strip()[:40]}).")
                    return
        except Exception:
            pass

        print(f"[i] Use frame click attempt {attempt}/3 — retrying...")
        seek_video_for_use_frame(page, duration, frame_second=frame_second)
        _reveal_top_card(page)
        page.wait_for_timeout(1000)

    raise RunwayAgentError("Could not click 'Use frame' under the previous clip.")


def capture_output_snapshot(page: Page, *, label: str = "") -> dict[str, Any]:
    """Capture feed output state for pre/post generation comparison."""
    feed = _feed_panel(page)
    videos = feed.locator("video")
    count = videos.count()
    entries: list[dict[str, Any]] = []
    for index in range(count):
        video = videos.nth(index)
        src = video.get_attribute("src") or ""
        meta = {"src": src, "currentSrc": "", "poster": ""}
        try:
            meta = video.evaluate(
                """el => ({
                    src: el.getAttribute('src') || '',
                    currentSrc: el.currentSrc || '',
                    poster: el.getAttribute('poster') || '',
                })"""
            )
        except Exception:
            pass
        card = video.locator("xpath=ancestor::div[contains(@class,'group') or @data-index][1]")
        data_index = None
        card_text_hash = ""
        try:
            if card.count() > 0:
                data_index = card.first.get_attribute("data-index")
                card_text = card.first.inner_text(timeout=500)[:200]
                if card_text:
                    import hashlib

                    card_text_hash = hashlib.sha256(card_text.encode("utf-8")).hexdigest()[:16]
        except Exception:
            pass
        entries.append(
            {
                "index": index,
                "src": str(meta.get("src") or src),
                "currentSrc": str(meta.get("currentSrc") or ""),
                "poster": str(meta.get("poster") or ""),
                "data_index": data_index,
                "card_text_hash": card_text_hash,
            }
        )

    download_count = 0
    try:
        download_count = feed.get_by_role("button", name=feed_download_pattern()).count()
    except Exception:
        pass

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "video_count": count,
        "videos": entries,
        "download_button_count": download_count,
        "item_count": feed.locator("[data-index]").count(),
    }


def _feed_top_video_src(page: Page) -> str | None:
    """Return feed-scoped top video src/currentSrc — never page-wide first video."""
    video = _feed_top_video(page)
    if video.count() == 0:
        return None
    try:
        src = video.evaluate("el => (el.currentSrc || el.src || '').trim()")
        if src and str(src).startswith(("http", "blob:")):
            return str(src)
    except Exception:
        pass
    src = video.get_attribute("src") or ""
    return src if src.startswith(("http", "blob:")) else None


def _latest_video_src(page: Page) -> str | None:
    """Deprecated page-wide lookup — kept for diagnostics only."""
    return _feed_top_video_src(page)


def download_clip_output(
    page: Page,
    output_dir: Path,
    filename: str,
    *,
    clip_index: int,
    pre_snapshot: dict[str, Any],
    post_snapshot: dict[str, Any],
    prior_clips: list[dict[str, Any]],
    use_frame_required: bool,
    generation_success: bool,
    use_frame_success: bool | None,
    quarantine_dir: Path,
) -> tuple[Path | None, dict[str, Any]]:
    """Download only a provably new feed output for the current clip attempt."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / filename

    new_output = detect_new_output(
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        prior_clips=prior_clips,
    )
    if not new_output.get("ok"):
        status = build_clip_status(
            clip_index=clip_index,
            use_frame_required=use_frame_required,
            generation_success=generation_success,
            use_frame_success=use_frame_success,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            new_output=new_output,
        )
        print(f"[FAIL] {status.get('error') or new_output.get('detail')}")
        return None, status

    selected_source = str(new_output.get("selected_source") or "")
    card_fp = str(new_output.get("output_card_fingerprint") or "")
    source_check = reject_stale_source(
        selected_source=selected_source,
        output_card_fingerprint=card_fp,
        prior_clips=prior_clips,
    )
    if not source_check.get("ok"):
        status = build_clip_status(
            clip_index=clip_index,
            use_frame_required=use_frame_required,
            generation_success=generation_success,
            use_frame_success=use_frame_success,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            new_output=new_output,
            source_check=source_check,
        )
        print(f"[FAIL] {status.get('error') or source_check.get('detail')}")
        return None, status

    _reveal_top_card(page)
    page.wait_for_timeout(400)
    card = _feed_top_card(page)
    download_method = ""
    downloaded = False

    _, download_buttons = _card_action_buttons(card)
    for index in range(download_buttons.count()):
        btn = download_buttons.nth(index)
        try:
            label = ((btn.get_attribute("aria-label") or "") + " " + btn.inner_text()).lower()
            if "all" in label or not btn.is_visible(timeout=800):
                continue
            btn.scroll_into_view_if_needed()
            with page.expect_download(timeout=180_000) as dl_info:
                btn.click()
            dl_info.value.save_as(str(dest))
            download_method = "top_card_button"
            downloaded = True
            break
        except Exception:
            continue

    if not downloaded:
        src = selected_source or _feed_top_video_src(page)
        if src:
            print("[i] Download via feed-scoped video URL...")
            response = page.request.get(src)
            if response.ok:
                dest.write_bytes(response.body())
                download_method = "feed_scoped_url"
                downloaded = True

    if not downloaded:
        status = build_clip_status(
            clip_index=clip_index,
            use_frame_required=use_frame_required,
            generation_success=generation_success,
            use_frame_success=use_frame_success,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            new_output=new_output,
            source_check=source_check,
            download_attempted=True,
        )
        status["error"] = "Could not download video — no top-card download button or feed-scoped URL."
        print(f"[FAIL] {status['error']}")
        return None, status

    mp4_check = reject_duplicate_mp4(
        downloaded_path=dest,
        prior_clips=prior_clips,
        quarantine_dir=quarantine_dir,
    )
    if not mp4_check.get("ok"):
        status = build_clip_status(
            clip_index=clip_index,
            use_frame_required=use_frame_required,
            generation_success=generation_success,
            use_frame_success=use_frame_success,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            new_output=new_output,
            source_check=source_check,
            download_attempted=True,
            download_method=download_method,
            mp4_check=mp4_check,
        )
        print(f"[FAIL] {status.get('error') or mp4_check.get('detail')}")
        return None, status

    status = build_clip_status(
        clip_index=clip_index,
        use_frame_required=use_frame_required,
        generation_success=generation_success,
        use_frame_success=use_frame_success,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        new_output=new_output,
        source_check=source_check,
        download_attempted=True,
        download_path=str(dest.resolve()),
        download_method=download_method,
        mp4_check=mp4_check,
        final_clip_registered=True,
    )
    print(f"[OK] Downloaded: {dest}")
    return dest, status


def download_latest_video(
    page: Page,
    output_dir: Path,
    filename: str | None = None,
    *,
    clip_index: int = 1,
    pre_snapshot: dict[str, Any] | None = None,
    post_snapshot: dict[str, Any] | None = None,
    prior_clips: list[dict[str, Any]] | None = None,
    use_frame_required: bool = False,
    generation_success: bool = True,
    use_frame_success: bool | None = None,
) -> Path:
    """Backward-compatible wrapper that routes through stale-safe selection."""
    pre_snapshot = pre_snapshot or capture_output_snapshot(page, label=f"clip_{clip_index}_pre_fallback")
    post_snapshot = post_snapshot or capture_output_snapshot(page, label=f"clip_{clip_index}_post_fallback")
    quarantine_dir = output_dir / "quarantine"
    path, status = download_clip_output(
        page,
        output_dir,
        filename or f"clip_{clip_index:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
        clip_index=clip_index,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        prior_clips=list(prior_clips or []),
        use_frame_required=use_frame_required,
        generation_success=generation_success,
        use_frame_success=use_frame_success,
        quarantine_dir=quarantine_dir,
    )
    if path is None or not status.get("download_success"):
        raise RunwayAgentError(status.get("error") or "Download rejected by selection guard.")
    return path


def configure_native_audio(page: Page, enabled: bool) -> None:
    """Enable native audio when requested (best-effort)."""
    if not enabled:
        return
    print("[step] Enabling native audio...")
    try:
        audio_btn = page.get_by_role("button", name=re.compile(r"Audio settings", re.I))
        if audio_btn.is_visible(timeout=3000):
            audio_btn.click()
            page.wait_for_timeout(500)
        for pattern in (r"native\s*audio", r"generate\s*audio", r"audio\s*on"):
            toggle = page.get_by_text(re.compile(pattern, re.I))
            if toggle.count() > 0 and toggle.first.is_visible(timeout=800):
                toggle.first.click()
                page.wait_for_timeout(400)
                print("[OK] Native audio enabled.")
                page.keyboard.press("Escape")
                return
        print("[i] Native audio requested — no toggle found; continuing.")
        page.keyboard.press("Escape")
    except Exception as exc:
        print(f"[i] Native audio setup skipped: {exc}")


def configure_runway(
    page: Page,
    *,
    model: str,
    aspect: str,
    duration: int,
    native_audio: bool = False,
) -> None:
    ensure_video_mode(page)
    select_model(page, model)
    select_aspect_ratio(page, aspect)
    select_duration(page, duration)
    configure_native_audio(page, native_audio)


def generate_one_clip(
    page: Page,
    prompt: str,
    clip_index: int,
    total: int,
    *,
    use_frame: bool,
    model: str,
    aspect: str,
    duration: int,
    output_dir: Path,
    gen_timeout: int,
    use_frame_second: float | None = None,
    native_audio: bool = False,
    prior_clips: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    print(f"\n{'=' * 50}")
    print(f"  CLIP {clip_index}/{total}")
    print(f"{'=' * 50}")

    use_frame_success: bool | None = None
    if clip_index == 1:
        configure_runway(
            page,
            model=model,
            aspect=aspect,
            duration=duration,
            native_audio=native_audio,
        )
    else:
        click_use_frame(page, duration=duration, frame_second=use_frame_second)
        use_frame_success = True
        if not _duration_is_set(page, duration):
            select_duration(page, duration)

    fill_prompt(page, prompt)
    ensure_feed_view(page)
    pre_snapshot = capture_output_snapshot(page, label=f"clip_{clip_index}_pre")
    click_generate(page)
    wait_for_video_ready(page, pre_snapshot, timeout_sec=gen_timeout)
    _wait_for_top_video_identity(page)
    post_snapshot = capture_output_snapshot(page, label=f"clip_{clip_index}_post")

    filename = f"clip_{clip_index:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    quarantine_dir = output_dir / "quarantine"
    path, clip_status = download_clip_output(
        page,
        output_dir,
        filename,
        clip_index=clip_index,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        prior_clips=list(prior_clips or []),
        use_frame_required=use_frame,
        generation_success=True,
        use_frame_success=use_frame_success,
        quarantine_dir=quarantine_dir,
    )
    if path is None or not clip_status.get("download_success"):
        raise RunwayAgentError(clip_status.get("error") or "Download rejected for current clip.")

    result = {
        "clip": clip_index,
        "prompt_len": len(prompt),
        "download": str(path.resolve()),
        "used_frame_from_previous": use_frame,
        "use_frame_second": (use_frame_second if use_frame_second is not None else max(duration - 1, 0)) if use_frame else None,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "generation_success": True,
        "download_success": True,
        "selected_source": clip_status.get("selected_source") or "",
        "output_card_fingerprint": clip_status.get("output_card_fingerprint") or "",
        "download_status": clip_status.get("download_status") or "fresh",
        "download_method": clip_status.get("download_method") or "",
        "sha256": clip_status.get("sha256") or sha256_file(path),
        "duplicate_guard_status": clip_status.get("duplicate_guard_status") or "pass",
        "clip_status": clip_status,
    }
    return result


def run_batch_pipeline(
    page: Page,
    prompts: list[str],
    *,
    runway_url: str,
    model: str,
    duration: int,
    aspect: str,
    output_dir: Path,
    gen_timeout: int,
    use_frame_second: float | None = None,
    native_audio: bool = False,
) -> list[dict[str, Any]]:
    print("[step] Opening Runway generate page...")
    ensure_on_generate_page(page, runway_url)

    results: list[dict[str, Any]] = []
    total = len(prompts)

    for index, prompt in enumerate(prompts, start=1):
        result = generate_one_clip(
            page,
            prompt,
            index,
            total,
            use_frame=index > 1,
            model=model,
            aspect=aspect,
            duration=duration,
            output_dir=output_dir,
            gen_timeout=gen_timeout,
            use_frame_second=use_frame_second,
            native_audio=native_audio,
            prior_clips=results,
        )
        results.append(result)

    return results


def ensure_on_generate_page(page: Page, url: str) -> None:
    if "generate" not in page.url or "login" in page.url:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1500)

    if "login" in page.url:
        print("\n[i] Login required. Log in inside Chrome, then press Enter here.")
        input("[i] Press Enter after login... ")
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1500)

    if "login" in page.url:
        raise RunwayAgentError("Still on login page. Run pwmap first to save session.")


def run_generation(
    page: Page,
    prompt: str,
    *,
    runway_url: str,
    model: str,
    duration: int,
    aspect: str,
    output_dir: Path,
    gen_timeout: int,
    native_audio: bool = False,
) -> Path:
    results = run_batch_pipeline(
        page,
        [prompt],
        runway_url=runway_url,
        model=model,
        duration=duration,
        aspect=aspect,
        output_dir=output_dir,
        gen_timeout=gen_timeout,
        native_audio=native_audio,
    )
    return Path(results[0]["download"])


def open_browser_only(
    page: Page,
    runway_url: str,
    *,
    context: BrowserContext | None = None,
    project_root: Path | None = None,
) -> None:
    """Open Chrome on Runway and keep it running for login / manual use."""
    root = project_root or resolve_project_root()
    print("[step] Opening browser...")
    ensure_on_generate_page(page, runway_url)
    print(f"[OK] Browser open: {page.url}")
    print("\n[i] Log in to Runway if needed.")
    print("[i] Press Enter here when done (Chrome stays open; session will be saved)...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        print("\n[i] Done.")
        return

    if context is not None:
        ok, message = validate_runway_session(page)
        if ok:
            save_runway_session(context, root)
            print(message)
            _notify_session_status(root, connected=True, message=message)
        else:
            print(message)
            _notify_session_status(root, connected=False, message=message)


def inspect_existing_outputs(page: Page, *, output_dir: Path, runway_url: str) -> None:
    """Diagnostic mode — inspect visible outputs without Generate or credits."""
    print("[step] Inspect existing outputs (no Generate, no credits)...")
    ensure_on_generate_page(page, runway_url)
    ensure_feed_view(page)
    snapshot = capture_output_snapshot(page, label="inspect_existing_outputs")
    report_path = output_dir / "inspect_existing_outputs.json"
    write_inspection_report(report_path=report_path, snapshot=snapshot)
    print(f"[OK] Output snapshot written: {report_path}")
    print(f"[i] Visible videos: {snapshot.get('video_count')} | download buttons: {snapshot.get('download_button_count')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runway Kling 3.0 Pro video generation agent.")
    src = parser.add_mutually_exclusive_group(required=False)
    src.add_argument("--prompt", help="Prompt text (max 2500 chars)")
    src.add_argument("--job", type=Path, help="JSON job file from another agent")
    src.add_argument("--stdin", action="store_true", help="Read prompt from stdin (plain text or JSON)")
    src.add_argument(
        "--watch-inbox",
        action="store_true",
        help=f"Process {INBOX_DIR}/job.json when it appears",
    )
    src.add_argument(
        "--open-browser",
        action="store_true",
        help="Open Chrome on Runway page only (login / manual use)",
    )
    src.add_argument(
        "--menu",
        action="store_true",
        help="Interactive menu (open browser, single clip, batch)",
    )

    parser.add_argument("--url", default=DEFAULT_RUNWAY_URL, help="Runway generate page URL")
    parser.add_argument("--model", default="Kling 3.0 Pro", help="Video model name")
    parser.add_argument("--duration", type=int, default=15, help="Duration in seconds")
    parser.add_argument("--aspect", default="9:16", help="Aspect ratio (vertical = 9:16)")
    parser.add_argument("--output", type=Path, default=DOWNLOADS_DIR, help="Download folder")
    parser.add_argument("--timeout", type=int, default=900, help="Generation timeout (seconds)")
    parser.add_argument("--headless", action="store_true", help="Headless Chrome (not recommended)")
    parser.add_argument("--no-stealth", action="store_true", help="Disable stealth patches")
    parser.add_argument(
        "--inspect-existing-outputs",
        action="store_true",
        help="Inspect visible feed outputs only (no Generate, no credits)",
    )
    parser.add_argument("--close-browser", action="store_true", help="Close Chrome on exit")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="ModirAgentOS project root (session + profile paths)",
    )
    return parser.parse_args()


def resolve_prompts(args: argparse.Namespace) -> tuple[list[str], dict[str, Any]]:
    extras: dict[str, Any] = {}
    if args.prompt:
        return [clamp_prompt(args.prompt)], extras
    if args.job:
        return load_job(args.job)
    if args.stdin:
        text = load_prompt_from_stdin()
        return [text], extras
    inbox_job = INBOX_DIR / "job.json"
    if args.watch_inbox:
        if not inbox_job.exists():
            raise RunwayAgentError(f"Waiting for job file: {inbox_job}")
        return load_job(inbox_job)
    raise RunwayAgentError("No prompt source specified.")


def run_menu() -> argparse.Namespace:
    """Simple numbered menu when no CLI args given."""
    print("\n=== Runway Agent ===")
    print("  1. Open Browser (Runway login)")
    print("  2. Single clip (--prompt)")
    print("  3. Batch job (agent_inbox/batch.json)")
    print("  4. Quit")
    choice = input("\nChoice [1-4]: ").strip()

    class Args:
        pass

    args = Args()
    args.open_browser = choice == "1"
    args.menu = False
    args.prompt = None
    args.job = None
    args.stdin = False
    args.watch_inbox = False
    args.url = DEFAULT_RUNWAY_URL
    args.model = "Kling 3.0 Pro"
    args.duration = 15
    args.aspect = "9:16"
    args.output = DOWNLOADS_DIR
    args.timeout = 900
    args.headless = False
    args.no_stealth = False
    args.close_browser = False

    if choice == "1":
        return args
    if choice == "2":
        args.prompt = input("Prompt: ").strip()
        if not args.prompt:
            raise RunwayAgentError("Prompt is empty.")
        return args
    if choice == "3":
        args.job = INBOX_DIR / "batch.json"
        if not args.job.exists():
            args.job = INBOX_DIR / "batch.example.json"
        return args
    if choice == "4":
        print("Bye.")
        sys.exit(0)
    raise RunwayAgentError("Invalid choice.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            try:
                sys.stdout.reconfigure(line_buffering=True)
            except Exception:
                pass

    args = parse_args()
    if (
        not args.open_browser
        and not args.inspect_existing_outputs
        and not args.menu
        and not args.prompt
        and not args.job
        and not args.stdin
        and not args.watch_inbox
    ):
        args = run_menu()

    if args.open_browser:
        stealth = not args.no_stealth
        project_root = args.project_root or resolve_project_root()
        playwright = sync_playwright().start()
        context = launch_runway_browser_context(
            playwright,
            headless=False,
            stealth=stealth,
            project_root=project_root,
        )
        page = context.pages[0] if context.pages else context.new_page()
        runway_url = args.url
        try:
            open_browser_only(
                page,
                runway_url,
                context=context,
                project_root=project_root,
            )
        finally:
            if args.close_browser:
                try:
                    context.close()
                except Exception:
                    pass
                playwright.stop()
            else:
                print("[i] Chrome left open.")
        return

    if args.inspect_existing_outputs:
        stealth = not args.no_stealth
        project_root = args.project_root or resolve_project_root()
        playwright = sync_playwright().start()
        context = launch_runway_browser_context(
            playwright,
            headless=False,
            stealth=stealth,
            project_root=project_root,
        )
        page = context.pages[0] if context.pages else context.new_page()
        output_dir = Path(args.output)
        try:
            inspect_existing_outputs(page, output_dir=output_dir, runway_url=args.url)
        finally:
            if args.close_browser:
                try:
                    context.close()
                except Exception:
                    pass
                playwright.stop()
            else:
                print("[i] Chrome left open.")
        return

    prompts, job = resolve_prompts(args)

    model = job.get("model", args.model)
    duration = int(job.get("duration", args.duration))
    aspect = str(job.get("aspect", args.aspect))
    runway_url = str(job.get("url", args.url))
    output_dir = Path(job.get("output", args.output))
    use_frame_second = job.get("use_frame_second")
    if use_frame_second is not None:
        use_frame_second = float(use_frame_second)
    native_audio = bool(job.get("native_audio", False))
    frame_at = use_frame_second if use_frame_second is not None else max(duration - 1, 0)

    print(f"[i] Clips to generate: {len(prompts)}")
    print(f"[i] Model: {model} | Duration: {duration}s | Aspect: {aspect}")
    if native_audio:
        print("[i] Native audio: enabled")
    if len(prompts) > 1:
        print(f"[i] Use frame at second: {frame_at:g} (last frame of each clip)")
    for i, p in enumerate(prompts, start=1):
        print(f"[i]   Clip {i}: {len(p)} chars")

    stealth = not args.no_stealth
    project_root = args.project_root or resolve_project_root()
    playwright = sync_playwright().start()
    context = launch_runway_browser_context(
        playwright,
        headless=args.headless,
        stealth=stealth,
        project_root=project_root,
    )
    page = context.pages[0] if context.pages else context.new_page()

    try:
        prepare_runway_session(page, context, project_root)
        ensure_on_generate_page(page, runway_url)
        if len(prompts) == 1:
            result_path = run_generation(
                page,
                prompts[0],
                runway_url=runway_url,
                model=model,
                duration=duration,
                aspect=aspect,
                output_dir=output_dir,
                gen_timeout=args.timeout,
                native_audio=native_audio,
            )
            results = [{
                "clip": 1,
                "download": str(result_path.resolve()),
                "prompt_len": len(prompts[0]),
            }]
        else:
            results = run_batch_pipeline(
                page,
                prompts,
                runway_url=runway_url,
                model=model,
                duration=duration,
                aspect=aspect,
                output_dir=output_dir,
                gen_timeout=args.timeout,
                use_frame_second=use_frame_second,
                native_audio=native_audio,
            )

        result_json = {
            "status": "ok",
            "clip_count": len(results),
            "model": model,
            "duration": duration,
            "aspect": aspect,
            "native_audio": native_audio,
            "clips": results,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
        out_json = output_dir / "last_result.json"
        out_json.write_text(json.dumps(result_json, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[OK] Batch complete — {len(results)} clip(s).")
        print(f"[OK] Result metadata: {out_json}")
    except RunwayAgentError as exc:
        print(f"[ERROR] {exc}")
        lowered = str(exc).lower()
        if any(token in lowered for token in ("session", "login", "connect runway")):
            sys.exit(EXIT_SESSION_NOT_READY)
        sys.exit(EXIT_RUNTIME_ERROR)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(EXIT_RUNTIME_ERROR)
    finally:
        if args.close_browser:
            try:
                context.close()
            except Exception:
                pass
            playwright.stop()
        else:
            print("[i] Chrome left open. Close it manually when done.")


if __name__ == "__main__":
    main()
