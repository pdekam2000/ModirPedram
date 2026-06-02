"""
Hailuo browser provider — Phase 11F-b hardened.

Structured errors, cancel checkpoints, capped page settles.
"""

from __future__ import annotations

import time

from providers.hailuo_api_errors import HailuoProviderError
from providers.hailuo_browser_support import (
    CancelCheck,
    browser_page_settle_seconds,
    browser_step_timeout_ms,
    check_cancel,
    wrap_browser_error,
)


class HailuoBrowserProvider:
    def __init__(self, *, cancel_check: CancelCheck | None = None, browser_manager=None):
        self._cancel_check = cancel_check
        if browser_manager is not None:
            self.browser = browser_manager
        else:
            from automation.browser_manager import BrowserManager

            self.browser = BrowserManager()
        self.page = None

    def start(self):
        check_cancel(self._cancel_check, "before_browser_launch")
        try:
            self.page = self.browser.launch()
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="BROWSER_UNAVAILABLE",
                details={"phase": "browser_launch"},
            ) from exc

    def open_hailuo(self):
        print("[Hailuo] Opening Hailuo...")
        check_cancel(self._cancel_check, "before_open_hailuo")
        try:
            self.browser.goto("https://hailuoai.video/")
            self.page.wait_for_load_state("domcontentloaded")
            settle = browser_page_settle_seconds()
            if settle > 0:
                time.sleep(settle)
        except Exception as exc:
            raise wrap_browser_error(exc, details={"phase": "open_hailuo"}) from exc
        self._detect_session_state()

    def _detect_session_state(self) -> None:
        try:
            text = (self.page.evaluate("() => document.body.innerText || ''") or "").lower()
        except Exception:
            return
        if "log in" in text or "sign in" in text:
            raise HailuoProviderError(
                "[Hailuo] Login required",
                code="BROWSER_SESSION_INVALID",
                details={"page_state": "LOGIN_REQUIRED"},
            )
        if "session expired" in text:
            raise HailuoProviderError(
                "[Hailuo] Browser session expired",
                code="BROWSER_SESSION_INVALID",
                details={"page_state": "SESSION_EXPIRED"},
            )

    def fill_prompt(self, prompt: str):
        print("[Hailuo] Filling prompt...")
        check_cancel(self._cancel_check, "before_prompt_submit")
        timeout = browser_step_timeout_ms()
        try:
            prompt_box = self.page.locator("[contenteditable='true']").first
            prompt_box.wait_for(timeout=timeout)
            prompt_box.click(force=True)
            time.sleep(min(0.5, browser_page_settle_seconds()))
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
            self.page.keyboard.type(prompt, delay=8)
            time.sleep(min(1.0, browser_page_settle_seconds()))
            print("[Hailuo] Prompt filled.")
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="BROWSER_AUTOMATION_NOT_READY",
                details={"phase": "fill_prompt"},
            ) from exc

    def set_duration_10s(self):
        print("[Hailuo] Setting duration to 10s...")
        try:
            duration_button = self.page.get_by_text("6s", exact=True)
            duration_button.click(timeout=5000, force=True)
            time.sleep(min(1.0, browser_page_settle_seconds()))
            option_10s = self.page.get_by_text("10s", exact=True)
            option_10s.click(timeout=5000, force=True)
            print("[Hailuo] Duration set to 10s.")
        except Exception as exc:
            print(f"[Hailuo] Duration setting skipped: {exc}")

    def set_resolution_768p(self):
        print("[Hailuo] Checking resolution...")
        try:
            resolution_button = self.page.get_by_text("768p", exact=True)
            resolution_button.click(timeout=5000, force=True)
            print("[Hailuo] Resolution already 768p / opened.")
        except Exception as exc:
            print(f"[Hailuo] Resolution setting skipped: {exc}")

    def disable_start_end_frame_if_needed(self):
        print("[Hailuo] Checking Start/End Frame mode...")
        try:
            start_end = self.page.get_by_text("Start/End Frame", exact=True)
            if start_end.count() > 0:
                print("[Hailuo] Start/End Frame option detected.")
        except Exception as exc:
            print(f"[Hailuo] Start/End Frame check skipped: {exc}")

    def apply_default_settings(self):
        print("[Hailuo] Applying default video settings...")
        self.disable_start_end_frame_if_needed()
        self.set_resolution_768p()
        self.set_duration_10s()
        print("[Hailuo] Default settings applied.")

    def click_create(self):
        print("[Hailuo] Clicking Create...")
        check_cancel(self._cancel_check, "before_create_click")
        self.apply_default_settings()

        selectors = [
            lambda: self.page.get_by_role("button", name="Create"),
            lambda: self.page.get_by_text("Create", exact=True),
            lambda: self.page.locator("button").filter(has_text="Create"),
            lambda: self.page.locator("button").filter(has_text="Generate"),
            lambda: self.page.locator("button").last,
        ]

        last_error = None
        for selector in selectors:
            try:
                button = selector()
                button.click(timeout=browser_step_timeout_ms(), force=True)
                print("[Hailuo] Create clicked.")
                return
            except Exception as exc:
                last_error = exc
                time.sleep(min(1.0, browser_page_settle_seconds()))

        raise HailuoProviderError(
            f"[Hailuo] Could not click Create button: {last_error}",
            code="BROWSER_AUTOMATION_NOT_READY",
            details={"phase": "click_create", "selector_not_found": True},
        )

    def close(self):
        self.browser.close()
