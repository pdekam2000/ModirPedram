from automation.browser_manager import BrowserManager
import re
import time
from typing import Any

from providers.runway_api_errors import RunwayProviderError
from providers.runway_output_url_classifier import (
    is_real_runway_output_url,
    runway_output_rejection_reason,
)
from providers.runway_browser_support import (
    PROMPT_EDGE_COMPARE_CHARS,
    PROMPT_INJECTION_INCOMPLETE,
    PROMPT_MIN_LENGTH_RATIO,
    PROMPT_PLACEHOLDER_MARKERS,
    RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS,
    browser_generate_click_wait_seconds,
    browser_generate_editor_wait_seconds,
    browser_page_settle_seconds,
    browser_prepare_step_timeout_ms,
    browser_ratio_duration_post_settle_seconds,
    browser_ratio_duration_stable_poll_interval,
    browser_ratio_duration_stable_polls,
    browser_ratio_duration_stabilize_timeout_seconds,
    capture_runway_prep_debug,
    check_cancel,
    wrap_browser_error,
)


class RunwayBrowserProvider:

    def __init__(self, *, cancel_check=None, browser_manager=None, runway_obs=None):
        self.browser = browser_manager or BrowserManager()
        self.page = None
        self._cancel_check = cancel_check
        self._runway_obs = runway_obs
        self._last_filled_prompt = ""

    def start(self):
        check_cancel(self._cancel_check, "browser_launch")
        try:
            self.page = self.browser.launch()
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="BROWSER_UNAVAILABLE",
                details={"phase": "browser_launch"},
            ) from exc

    def _set_obs_step(self, step: str, *, detail: str | None = None) -> None:
        print(f"[RUNWAY_PREP] step={step}" + (f" detail={detail}" if detail else ""))
        if self._runway_obs is not None and hasattr(self._runway_obs, "set_step"):
            self._runway_obs.set_step(step, detail=detail)

    def _persist_prep_debug(self, debug: dict) -> None:
        if self._runway_obs is None or not hasattr(self._runway_obs, "_persist"):
            return
        try:
            self._runway_obs._persist({"prep_debug": debug})
        except Exception:
            pass

    def _fail_prep(self, phase: str, message: str) -> None:
        debug = capture_runway_prep_debug(self.page)
        self._persist_prep_debug(debug)
        detail = f"{phase}: {message}"
        if self._runway_obs is not None and hasattr(self._runway_obs, "mark_failed"):
            self._runway_obs.mark_failed(detail[:240])
        raise wrap_browser_error(
            RuntimeError(f"[Runway Browser] {detail} | debug={debug}"),
            default_code="BROWSER_AUTOMATION_NOT_READY",
            details={"phase": phase, "prep_debug": debug},
        )

    def open_runway(self):
        print("[Runway Browser] Opening Runway dashboard...")
        check_cancel(self._cancel_check, "page_load")
        try:
            self.browser.goto("https://app.runwayml.com/")
            self.page.wait_for_load_state("domcontentloaded", timeout=browser_prepare_step_timeout_ms())
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="BROWSER_AUTOMATION_NOT_READY",
                details={"phase": "open_runway"},
            ) from exc
        time.sleep(browser_page_settle_seconds())

    def select_video_mode(self):
        """Enter Runway video generation workspace (Video tab / Generate Video)."""
        print("[Runway Browser] Selecting Video mode / workspace...")
        check_cancel(self._cancel_check, "select_video_mode")
        self._set_obs_step("selecting_video_mode")

        if self.is_video_workspace_ready():
            print("[Runway Browser] Already inside video workspace.")
            return

        selectors = [
            lambda: self.page.get_by_role("button", name=re.compile(r"^Generate$", re.I)),
            lambda: self.page.get_by_role("button", name=re.compile(r"Generate\s+Video", re.I)),
            lambda: self.page.get_by_role("tab", name=re.compile(r"^Video$", re.I)),
            lambda: self.page.get_by_role("link", name=re.compile(r"^Video$", re.I)),
            lambda: self.page.locator("button").filter(has_text=re.compile(r"^Video$", re.I)),
            lambda: self.page.locator("button").filter(has_text=re.compile(r"Generate\s+Video", re.I)),
            lambda: self.page.get_by_text("Generate Video", exact=False),
            lambda: self.page.get_by_text("Video", exact=True),
        ]

        try:
            self._click_first(selectors, "Video / Generate Video")
        except Exception as exc:
            self._fail_prep("select_video_mode", f"Could not enter Video generation workspace: {exc}")

        time.sleep(browser_page_settle_seconds())
        if not self.is_video_workspace_ready():
            self._fail_prep("select_video_mode", "Video workspace markers not visible after mode selection")

    def click_generate_video_home(self):
        """Backward-compatible alias for select_video_mode."""
        self.select_video_mode()

    def is_video_workspace_ready(self):
        try:
            if self.page.get_by_text("Describe your shot", exact=False).count() > 0:
                return True
            if self.page.get_by_text("First Video Frame", exact=False).count() > 0:
                return True
            if self.page.get_by_text("Gen-4.5", exact=True).count() > 0:
                return True
        except Exception:
            return False
        return False

    def select_gen45(self):
        print("[Runway Browser] Selecting Gen-4.5 top tab...")
        check_cancel(self._cancel_check, "select_gen45")
        self._set_obs_step("selecting_gen45_model")

        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

        clicked = self.click_text_in_region(text="Gen-4.5", min_x=450, max_y=550)
        if not clicked:
            selectors = [
                lambda: self.page.get_by_text("Gen-4.5", exact=True).nth(0),
                lambda: self.page.locator("button").filter(has_text="Gen-4.5").nth(0),
                lambda: self.page.get_by_role("tab", name=re.compile(r"Gen-4\.5", re.I)),
            ]
            try:
                self._click_first(selectors, "Gen-4.5")
                clicked = True
            except Exception as exc:
                self._fail_prep("select_gen45", f"Could not select Gen-4.5 model tab: {exc}")

        if clicked:
            print("[Runway Browser] Clicked Gen-4.5 top tab.")
        time.sleep(3)

        try:
            if self.page.get_by_text("Gen-4.5", exact=True).count() == 0:
                self._fail_prep("select_gen45", "Gen-4.5 tab not visible after selection")
        except Exception as exc:
            self._fail_prep("select_gen45", f"Gen-4.5 visibility check failed: {exc}")

    def _page_url(self) -> str:
        try:
            return str(self.page.url or "")
        except Exception:
            return ""

    def _page_body_snippet(self, limit: int = 400) -> str:
        try:
            text = self.page.evaluate("() => document.body.innerText || ''") or ""
            return str(text)[:limit]
        except Exception:
            return ""

    def _has_editor_markers(self) -> bool:
        body = self._page_body_snippet().lower()
        return "describe your shot" in body or "first video frame" in body

    def is_apps_landing_page(self) -> bool:
        """Gen-4.5 card/landing (mode=apps) before the generate editor opens."""
        if self.is_prompt_box_ready() and self._has_editor_markers():
            return False
        url = self._page_url().lower()
        body = self._page_body_snippet().lower()
        if "mode=apps" in url and not self.is_prompt_box_ready():
            return True
        if "everything you need to make" in body and not self.is_prompt_box_ready():
            return True
        return self.is_try_it_now_visible() and not self.is_prompt_box_ready()

    def is_try_it_now_visible(self) -> bool:
        try:
            probes = [
                self.page.get_by_role("button", name=re.compile(r"Try it now", re.I)),
                self.page.locator("button").filter(has_text=re.compile(r"Try it now", re.I)),
                self.page.get_by_text(re.compile(r"Try it now", re.I)),
                self.page.locator("a").filter(has_text=re.compile(r"Try it now", re.I)),
            ]
            for locator in probes:
                if locator.count() > 0:
                    return True
        except Exception:
            pass
        return "try it now" in self._page_body_snippet().lower()

    def is_generate_editor_ready(self) -> bool:
        if not self.is_prompt_box_ready():
            return False
        url = self._page_url().lower()
        if "mode=apps" in url and not self._has_editor_markers():
            return False
        return True

    def click_try_it_now(self) -> None:
        """Click Gen-4.5 landing CTA to open the generate editor (no Generate / no credits)."""
        print("[Runway Browser] Clicking Try it now...")
        check_cancel(self._cancel_check, "click_try_it_now")

        if self.is_generate_editor_ready():
            print("[Runway Browser] Generate editor already open. Skipping Try it now.")
            return

        if not self.is_try_it_now_visible():
            if self.is_prompt_box_ready():
                return
            self._fail_prep(
                "click_try_it_now",
                "Expected Try it now on Gen-4.5 landing but button not found",
            )

        self._set_obs_step("clicking_try_it_now")

        clicked = False
        try:
            clicked = self.click_text_in_region(text="Try it now", min_x=0, max_y=9999, contains=True)
        except Exception:
            clicked = False

        if not clicked:
            selectors = [
                lambda: self.page.get_by_role("button", name=re.compile(r"Try it now", re.I)),
                lambda: self.page.locator("button").filter(has_text=re.compile(r"Try it now", re.I)),
                lambda: self.page.get_by_text(re.compile(r"^Try it now$", re.I)),
                lambda: self.page.get_by_text("Try it now", exact=False),
                lambda: self.page.locator("a").filter(has_text=re.compile(r"Try it now", re.I)),
            ]
            try:
                self._click_first(selectors, "Try it now")
                clicked = True
            except Exception as exc:
                self._fail_prep("click_try_it_now", f"Could not click Try it now: {exc}")

        print("[Runway Browser] Try it now clicked.")
        self._set_obs_step("try_it_now_clicked")
        time.sleep(browser_page_settle_seconds())

    def click_try_it(self):
        """Backward-compatible alias."""
        self.click_try_it_now()

    def wait_for_generate_editor(self) -> None:
        print("[Runway Browser] Waiting for generate editor...")
        check_cancel(self._cancel_check, "wait_for_generate_editor")
        self._set_obs_step("waiting_for_generate_editor")

        deadline = time.monotonic() + browser_generate_editor_wait_seconds()
        last_debug: dict = {}
        while time.monotonic() < deadline:
            check_cancel(self._cancel_check, "wait_for_generate_editor")
            if self.is_generate_editor_ready():
                print("[Runway Browser] Generate editor ready.")
                self._set_obs_step("generate_editor_ready")
                return
            last_debug = capture_runway_prep_debug(self.page)
            time.sleep(0.75)

        self._persist_prep_debug(last_debug)
        self._fail_prep(
            "waiting_for_generate_editor",
            "Generate editor did not open after Try it now "
            f"(prompt_box_count={last_debug.get('prompt_box_count', 0)}, "
            f"mode_apps={last_debug.get('mode_apps')}, url={last_debug.get('url', '')[:120]})",
        )

    def enter_generate_editor(self) -> None:
        """Leave mode=apps landing and open the Gen-4.5 generate editor."""
        if self.is_generate_editor_ready():
            self._set_obs_step("generate_editor_ready")
            self._set_obs_step("prompt_box_ready")
            return

        if self.is_try_it_now_visible() or self.is_apps_landing_page():
            self.click_try_it_now()
        elif not self.is_prompt_box_ready():
            self.click_try_it_now()

        self.wait_for_generate_editor()

        if not self.is_prompt_box_ready():
            debug = capture_runway_prep_debug(self.page)
            self._persist_prep_debug(debug)
            self._fail_prep(
                "prompt_box_ready",
                "Prompt box missing after Try it now "
                f"(textarea_count={debug.get('textarea_count', 0)}, "
                f"prompt_box_count={debug.get('prompt_box_count', 0)})",
            )
        self._set_obs_step("prompt_box_ready")

    def ensure_prompt_box_ready(self):
        self.enter_generate_editor()

    def is_prompt_box_ready(self):
        try:
            if self.page.locator("textarea").count() > 0:
                return True
            if self.page.get_by_text("Describe your shot", exact=False).count() > 0:
                return True
            if self.page.locator("[contenteditable='true']").count() > 0:
                return True
        except Exception:
            return False
        return False

    def _normalize_prompt_compare(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip())

    def _read_prompt_field_text(self, box) -> str:
        try:
            return str(box.input_value(timeout=2000) or "")
        except Exception:
            pass
        try:
            return str(box.inner_text(timeout=2000) or "")
        except Exception:
            pass
        try:
            return str(
                box.evaluate(
                    """(el) => {
                        if (!el) return '';
                        if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                            return el.value || '';
                        }
                        return el.innerText || el.textContent || '';
                    }"""
                )
                or ""
            )
        except Exception:
            return ""

    def _resolve_prompt_box(self):
        selectors = ["textarea", "[contenteditable='true']", "input[type='text']"]
        last_error = None
        for selector in selectors:
            try:
                boxes = self.page.locator(selector)
                for i in range(boxes.count()):
                    box = boxes.nth(i)
                    try:
                        box.wait_for(state="visible", timeout=3000)
                        return box
                    except Exception as inner_error:
                        last_error = inner_error
            except Exception as exc:
                last_error = exc
        raise wrap_browser_error(
            RuntimeError(f"[Runway Browser] Prompt box not found: {last_error}"),
            default_code="BROWSER_AUTOMATION_NOT_READY",
            details={"phase": "resolve_prompt_box"},
        )

    def _inject_prompt_into_box(self, box, prompt: str) -> None:
        box.click(force=True, timeout=browser_prepare_step_timeout_ms())
        time.sleep(0.25)
        try:
            box.fill(prompt, timeout=browser_prepare_step_timeout_ms())
            return
        except Exception:
            pass
        try:
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
        except Exception:
            pass
        try:
            box.evaluate(
                """(el, text) => {
                    el.focus();
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                        el.value = text;
                    } else {
                        el.textContent = text;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                prompt,
            )
            return
        except Exception:
            pass
        self.page.keyboard.type(prompt, delay=0)

    def _clear_prompt_box(self, box) -> None:
        try:
            box.click(force=True, timeout=3000)
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
            time.sleep(0.2)
        except Exception:
            pass

    def _record_clip_prep_obs(self, **fields: Any) -> None:
        if self._runway_obs is not None and hasattr(self._runway_obs, "record_clip_prep"):
            self._runway_obs.record_clip_prep(**fields)

    def _verify_prompt_injection(self, expected: str) -> tuple[int, int]:
        expected_norm = self._normalize_prompt_compare(expected)
        box = self._resolve_prompt_box()
        actual_raw = self._read_prompt_field_text(box)
        actual_norm = self._normalize_prompt_compare(actual_raw)
        expected_len = len(expected_norm)
        actual_len = len(actual_norm)
        min_ok = max(32, int(expected_len * PROMPT_MIN_LENGTH_RATIO))

        issues: list[str] = []
        if actual_len < min_ok:
            issues.append(f"length {actual_len} < minimum {min_ok} (expected {expected_len})")

        edge = min(PROMPT_EDGE_COMPARE_CHARS, expected_len)
        if edge > 0:
            if expected_norm[:edge] != actual_norm[:edge]:
                issues.append(
                    f"prefix mismatch expected={expected_norm[:edge]!r} actual={actual_norm[:edge]!r}"
                )
            if expected_norm[-edge:] != actual_norm[-edge:]:
                issues.append(
                    f"suffix mismatch expected={expected_norm[-edge:]!r} actual={actual_norm[-edge:]!r}"
                )

        actual_lower = actual_norm.lower()
        expected_lower = expected_norm.lower()
        for marker in PROMPT_PLACEHOLDER_MARKERS:
            if marker in actual_lower and marker not in expected_lower and actual_len < expected_len:
                issues.append(f"placeholder remains: {marker!r}")

        print(
            f"[RUNWAY_PROMPT_VERIFY] expected_len={expected_len} actual_len={actual_len} "
            f"ok={not issues}"
        )
        if issues:
            raise wrap_browser_error(
                RuntimeError(
                    "[Runway Browser] PROMPT_INJECTION_INCOMPLETE: "
                    + "; ".join(issues)
                ),
                default_code=PROMPT_INJECTION_INCOMPLETE,
                details={
                    "phase": "prompt_verify",
                    "expected_len": expected_len,
                    "actual_len": actual_len,
                    "actual_preview": actual_norm[:120],
                    "issues": issues,
                },
            )
        return expected_len, actual_len

    def set_prompt_verified(self, prompt: str) -> None:
        """Paste/fill full prompt and verify before any ratio/duration changes."""
        print("[RUNWAY_PROMPT_SET_START]")
        check_cancel(self._cancel_check, "set_prompt_verified")

        prompt = str(prompt).strip()
        if not prompt:
            raise wrap_browser_error(
                RuntimeError("[Runway Browser] Refusing to fill empty prompt"),
                default_code="BROWSER_AUTOMATION_NOT_READY",
                details={"phase": "set_prompt_verified"},
            )

        if self._runway_obs is not None and hasattr(self._runway_obs, "log_prompt_typing_start"):
            self._runway_obs.log_prompt_typing_start()

        expected_len = len(self._normalize_prompt_compare(prompt))
        last_error: Exception | None = None
        for attempt in range(2):
            check_cancel(self._cancel_check, "set_prompt_verified")
            try:
                box = self._resolve_prompt_box()
                if attempt > 0:
                    self._clear_prompt_box(box)
                self._inject_prompt_into_box(box, prompt)
                time.sleep(0.35)
                verified_expected, actual_len = self._verify_prompt_injection(prompt)
                self._last_filled_prompt = prompt
                self._record_clip_prep_obs(
                    prompt_expected_length=verified_expected,
                    prompt_actual_length=actual_len,
                    prompt_verified=True,
                )
                print("[RUNWAY_PROMPT_SET_DONE]")
                return
            except Exception as exc:
                last_error = exc
                actual_len = 0
                try:
                    box = self._resolve_prompt_box()
                    actual_len = len(
                        self._normalize_prompt_compare(self._read_prompt_field_text(box))
                    )
                except Exception:
                    pass
                self._record_clip_prep_obs(
                    prompt_expected_length=expected_len,
                    prompt_actual_length=actual_len,
                    prompt_verified=False,
                )
                if attempt == 0:
                    print("[Runway Browser] Prompt verify failed; retrying clear + paste once.")
                    continue
                break

        if isinstance(last_error, RunwayProviderError):
            raise last_error
        raise wrap_browser_error(
            RuntimeError(f"[Runway Browser] Could not set verified prompt: {last_error}"),
            default_code=PROMPT_INJECTION_INCOMPLETE,
            details={"phase": "set_prompt_verified"},
        )

    def fill_prompt(self, prompt: str):
        """Backward-compatible alias — always verifies full prompt injection."""
        self.set_prompt_verified(prompt)
        print("[Runway Browser] Prompt filled.")

    def _verify_ratio_16_9_selected(self) -> bool:
        snippet = self._page_body_snippet(4000).lower()
        return "16:9" in snippet

    def _verify_duration_selected(self) -> bool:
        target = RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS
        snippet = self._page_body_snippet(4000).lower()
        return f"{target}s" in snippet or f"{target} s" in snippet

    def _prompt_still_verified(self, prompt: str) -> bool:
        try:
            self._verify_prompt_injection(prompt)
            return True
        except Exception:
            return False

    def _wait_for_ratio_duration_ui_stable(self) -> tuple[bool, bool, bool]:
        """
        After ratio + duration clicks, poll until both remain visible through re-renders.
        Returns (ratio_ok, duration_ok, ui_stabilized).
        """
        post_settle = browser_ratio_duration_post_settle_seconds()
        poll_every = browser_ratio_duration_stable_poll_interval()
        required_stable = browser_ratio_duration_stable_polls()
        timeout = browser_ratio_duration_stabilize_timeout_seconds()

        print(
            f"[RUNWAY_UI_STABILIZE] waiting up to {timeout}s "
            f"(post_settle={post_settle}s stable_polls={required_stable})"
        )
        time.sleep(post_settle)

        stable_count = 0
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            check_cancel(self._cancel_check, "ratio_duration_ui_stabilize")
            ratio_ok = self._verify_ratio_16_9_selected()
            duration_ok = self._verify_duration_selected()
            if ratio_ok and duration_ok:
                stable_count += 1
                if stable_count >= required_stable:
                    print(
                        f"[RUNWAY_UI_STABILIZE] stable ratio+duration "
                        f"({stable_count}/{required_stable} polls)"
                    )
                    return True, True, True
            else:
                if stable_count > 0:
                    print(
                        f"[RUNWAY_UI_STABILIZE] reset detected "
                        f"ratio={ratio_ok} duration={duration_ok}"
                    )
                stable_count = 0
            time.sleep(poll_every)

        ratio_ok = self._verify_ratio_16_9_selected()
        duration_ok = self._verify_duration_selected()
        ui_stable = False
        print(
            f"[RUNWAY_UI_STABILIZE] timeout ratio={ratio_ok} duration={duration_ok} "
            f"last_stable_polls={stable_count}"
        )
        return ratio_ok, duration_ok, ui_stable

    def _stabilize_and_verify_before_generate(self, prompt: str) -> None:
        """Wait for UI settle; retry 16:9 once if reset; re-verify prompt and 10s."""
        ratio_ok, duration_ok, ui_stable = self._wait_for_ratio_duration_ui_stable()

        if not ratio_ok:
            print("[RUNWAY_RATIO_RETRY] 16:9 not stable; retrying ratio selection once")
            self.set_ratio_16_9(strict=True)

            prompt_ok = self._prompt_still_verified(prompt)
            if not prompt_ok:
                print("[RUNWAY_PROMPT_REVERIFY] re-applying prompt after ratio retry")
                self.set_prompt_verified(prompt)
                prompt_ok = True
            else:
                print("[RUNWAY_PROMPT_REVERIFY] prompt still complete after ratio retry")

            print("[RUNWAY_DURATION_REVERIFY] re-checking 10s duration after ratio retry")
            self.set_duration_10s(strict=True)

            ratio_ok, duration_ok, ui_stable = self._wait_for_ratio_duration_ui_stable()
            prompt_ok = self._prompt_still_verified(prompt)
        else:
            prompt_ok = self._prompt_still_verified(prompt)
            if not prompt_ok:
                print("[RUNWAY_PROMPT_REVERIFY] prompt incomplete before generate; re-applying")
                self.set_prompt_verified(prompt)
                prompt_ok = True

        print(
            f"[RUNWAY_PREP_BEFORE_GENERATE] ratio={ratio_ok} duration={duration_ok} "
            f"prompt={prompt_ok} ui_stabilized={ui_stable}"
        )
        self._record_clip_prep_obs(
            ratio_selected_before_generate=ratio_ok,
            duration_selected_before_generate=duration_ok,
            prompt_still_verified_before_generate=prompt_ok,
            ui_stabilized_after_ratio=ui_stable,
            ratio_verified=ratio_ok,
            duration_verified=duration_ok,
            prompt_verified=prompt_ok,
        )

        if not ratio_ok:
            self._fail_prep(
                "ready_for_generate",
                "16:9 ratio not selected after UI stabilization and one retry",
            )
        if not duration_ok:
            self._fail_prep(
                "ready_for_generate",
                f"Duration {RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS}s not selected "
                "after UI stabilization and re-check",
            )
        if not prompt_ok:
            self._fail_prep(
                "ready_for_generate",
                "Prompt no longer complete before Generate",
            )

    def set_ratio_16_9(self, *, strict: bool = False):
        print("[Runway Browser] Setting ratio 16:9...")
        clicked = False
        try:
            clicked = bool(self.click_text_in_region(text="16:9", min_x=0, max_y=1200))
            if clicked:
                print("[Runway Browser] Ratio 16:9 selected.")
                time.sleep(min(1.0, browser_ratio_duration_post_settle_seconds()))
        except Exception as e:
            print(f"[Runway Browser] Ratio region click skipped: {e}")

        verified = self._verify_ratio_16_9_selected()
        print(f"[RUNWAY_RATIO_SET] selected={verified} clicked={clicked}")
        self._record_clip_prep_obs(ratio_verified=verified)
        if strict and not verified:
            self._fail_prep("setting_ratio_16_9", "16:9 not visible after ratio selection")
        if not clicked and not verified:
            print("[Runway Browser] Ratio setting skipped.")

    def set_duration_10s(self, *, strict: bool = False):
        target = RUNWAY_BROWSER_DEFAULT_CLIP_DURATION_SECONDS
        print(f"[Runway Browser] Setting duration {target}s...")
        self._set_obs_step("setting_duration_10s")

        duration_set = False
        try:
            clicked_5s = self.click_text_in_region(text="5s", min_x=0, max_y=1200)
            if clicked_5s:
                print("[Runway Browser] Opened duration menu from 5s.")
                time.sleep(1)
                for _ in range(5):
                    self.page.keyboard.press("ArrowDown")
                    time.sleep(0.2)
                self.page.keyboard.press("Enter")
                time.sleep(1)
                duration_set = True
                print(f"[Runway Browser] Duration {target}s selected with keyboard.")
        except Exception as e:
            print(f"[Runway Browser] Keyboard duration selection failed: {e}")

        if not duration_set:
            for label in (f"{target}s", "10s"):
                try:
                    if self.click_text_in_region(text=label, min_x=0, max_y=1200):
                        duration_set = True
                        print(f"[Runway Browser] Duration {label} selected via click.")
                        break
                except Exception:
                    pass

        verified = self._verify_duration_selected()
        print(
            f"[RUNWAY_DURATION_SET] target={target}s menu_opened={duration_set} "
            f"verified={verified}"
        )
        self._record_clip_prep_obs(duration_verified=verified)
        if strict and not duration_set:
            self._fail_prep("setting_duration_10s", f"Could not set Runway clip duration to {target}s")
        if strict and not verified:
            self._fail_prep(
                "setting_duration_10s",
                f"Duration {target}s not visible after duration selection",
            )
        if not duration_set:
            print("[Runway Browser] Duration setting skipped. Current duration may remain unchanged.")

    def apply_default_settings(self, *, strict: bool = True):
        """Ratio + duration only — call after prompt is verified (12J-E0 order)."""
        print("[Runway Browser] Applying ratio and duration after prompt...")
        check_cancel(self._cancel_check, "apply_settings")
        self.set_ratio_16_9(strict=strict)
        self.set_duration_10s(strict=strict)

    def prepare_clip_for_generate(self, prompt: str) -> None:
        """
        Per-clip order: full prompt → verify → 16:9 → 10s → verify → ready for Generate.
        """
        check_cancel(self._cancel_check, "prepare_clip_for_generate")
        self._record_clip_prep_obs(
            prompt_verified=False,
            ratio_verified=False,
            duration_verified=False,
        )
        self.set_prompt_verified(prompt)
        self.set_ratio_16_9(strict=True)
        self.set_duration_10s(strict=True)
        self._stabilize_and_verify_before_generate(prompt)
        print("[RUNWAY_READY_TO_GENERATE]")
        self._set_obs_step("ready_for_generate")

    def _page_body_lower(self) -> str:
        try:
            return (self.page.evaluate("() => document.body.innerText || ''") or "").lower()
        except Exception:
            return ""

    def _is_already_generating(self) -> bool:
        body = self._page_body_lower()
        if "in queue" in body or "your generation is in queue" in body:
            return True
        if "generating" in body:
            return True
        return False

    def _infer_page_generation_state(self) -> str:
        body = self._page_body_lower()
        if "log in" in body or "sign in" in body:
            return "LOGIN_REQUIRED"
        if "session expired" in body:
            return "SESSION_EXPIRED"
        if "in queue" in body or "your generation is in queue" in body:
            return "IN_QUEUE"
        if "generating" in body:
            return "GENERATING"
        if "error" in body and "generation" in body:
            return "GENERATION_ERROR"
        if "downloaded" in body or "download" in body:
            return "READY_OR_HISTORY"
        return "UNKNOWN"

    def _visible_video_srcs(self) -> list[str]:
        if self.page is None:
            return []
        try:
            items = self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll("video"))
                    .map(v => v.currentSrc || v.src || "")
                    .filter(Boolean)
                """
            )
            return [str(item).strip() for item in (items or []) if str(item).strip()]
        except Exception:
            return []

    def _generating_block_context(self) -> str:
        page_state = self._infer_page_generation_state()
        body = self._page_body_lower()
        job_snippet = " ".join(body.split())[:160]
        visible = self._visible_video_srcs()
        real_urls = [url for url in visible if is_real_runway_output_url(url)]
        placeholder_urls = [
            url
            for url in visible
            if runway_output_rejection_reason(url) is not None
        ]
        return (
            f"page_state={page_state}; "
            f"real_output_url_found={bool(real_urls)}; "
            f"placeholder_visible_count={len(placeholder_urls)}; "
            f"visible_job_text={job_snippet!r}"
        )

    def _prompt_has_text(self, *, min_chars: int = 3) -> bool:
        expected = (self._last_filled_prompt or "").strip()
        if len(expected) < min_chars:
            return False
        try:
            self._verify_prompt_injection(expected)
            return True
        except Exception:
            return False

    def _resolve_generate_button(self):
        timeout = browser_prepare_step_timeout_ms()
        candidates = [
            ("role_generate", lambda: self.page.get_by_role("button", name=re.compile(r"Generate", re.I))),
            ("text_generate", lambda: self.page.get_by_text("Generate", exact=True)),
            ("text_generate_video", lambda: self.page.get_by_text("Generate Video", exact=False)),
            ("button_filter_generate", lambda: self.page.locator("button").filter(has_text=re.compile(r"Generate", re.I))),
            ("aria_generate", lambda: self.page.locator("button[aria-label*='Generate' i]")),
        ]
        last_error = None
        for label, factory in candidates:
            check_cancel(self._cancel_check, "resolve_generate_button")
            try:
                locator = factory()
                if locator.count() == 0:
                    continue
                item = locator.first
                item.wait_for(state="visible", timeout=timeout)
                return label, item
            except Exception as exc:
                last_error = exc
        raise RuntimeError(
            "Generate button not found. Tried role=button /Generate/i, text Generate, "
            f"Generate Video, filtered buttons, aria-label. Last error: {last_error}"
        )

    def _button_is_enabled(self, button) -> bool:
        try:
            if button.is_disabled():
                return False
        except Exception:
            pass
        try:
            if button.get_attribute("disabled") is not None:
                return False
        except Exception:
            pass
        return True

    def click_generate(self):
        print("[Runway Browser] Clicking final Generate...")
        check_cancel(self._cancel_check, "click_generate")

        expected = (self._last_filled_prompt or "").strip()
        if not expected:
            self._fail_prep("click_generate", "Refusing to click Generate: no verified prompt on record")
        try:
            self._verify_prompt_injection(expected)
        except RunwayProviderError as exc:
            self._fail_prep(
                "click_generate",
                f"Refusing to click Generate: prompt verification failed ({exc})",
            )
        except Exception as exc:
            self._fail_prep(
                "click_generate",
                f"Refusing to click Generate: prompt verification failed ({exc})",
            )
        if self._is_already_generating():
            context = self._generating_block_context()
            self._fail_prep(
                "click_generate",
                "Refusing to click Generate: generation already in progress "
                f"({context})",
            )

        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

        print("[Runway Browser] Looking for Generate button...")
        try:
            _strategy, button = self._resolve_generate_button()
        except Exception as exc:
            self._fail_prep("click_generate", f"Generate button not found: {exc}")

        if not self._button_is_enabled(button):
            self._fail_prep("click_generate", "Generate button is visible but disabled")

        try:
            button.click(timeout=browser_prepare_step_timeout_ms(), force=True)
        except Exception as exc:
            if not self.click_text_in_region(text="Generate", min_x=0, max_y=1200):
                self._fail_prep("click_generate", f"Generate click failed: {exc}")

        if self._runway_obs is not None and hasattr(self._runway_obs, "log_generate_clicked"):
            self._runway_obs.log_generate_clicked()
        print("[RUNWAY_GENERATE_CLICKED]")
        print("[Runway Browser] Generate clicked. Waiting for queue state...")
        time.sleep(browser_generate_click_wait_seconds())

    def prepare_gen45_page(self):
        """Open Gen-4.5 editor only (12J-E0). Ratio/duration/prompt run per clip before Generate."""
        check_cancel(self._cancel_check, "prepare_page")
        self._set_obs_step("preparing_gen45_page")

        self.open_runway()
        check_cancel(self._cancel_check, "prepare_page")
        self.select_video_mode()
        check_cancel(self._cancel_check, "prepare_page")
        self.select_gen45()
        check_cancel(self._cancel_check, "prepare_page")
        self.enter_generate_editor()
        check_cancel(self._cancel_check, "prepare_page")
        print("[Runway Browser] Editor ready — prompt/ratio/duration applied per clip before Generate.")

    def click_text_in_region(self, text, min_x=0, max_y=9999, *, contains: bool = False):
        script = """
        (args) => {
            const text = args.text;
            const minX = args.minX;
            const maxY = args.maxY;
            const contains = !!args.contains;
            const elements = Array.from(document.querySelectorAll("button, div, span, a"));
            const candidates = elements.filter(el => {
                const value = (el.innerText || el.textContent || "").trim();
                const match = contains
                    ? value.toLowerCase().includes(text.toLowerCase())
                    : value === text;
                if (!match) return false;
                const rect = el.getBoundingClientRect();
                if (!rect || rect.width <= 0 || rect.height <= 0) return false;
                if (rect.left < minX) return false;
                if (rect.top > maxY) return false;
                return true;
            });
            if (!candidates.length) return false;
            candidates.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
            candidates[0].click();
            return true;
        }
        """
        return self.page.evaluate(
            script,
            {"text": text, "minX": min_x, "maxY": max_y, "contains": contains},
        )

    def _click_first(self, selectors, label):
        last_error = None
        for selector in selectors:
            check_cancel(self._cancel_check, f"click_{label}")
            try:
                item = selector()
                if hasattr(item, "count") and item.count() == 0:
                    continue
                target = item.first if hasattr(item, "first") else item
                target.click(timeout=browser_prepare_step_timeout_ms(), force=True)
                print(f"[Runway Browser] Clicked: {label}")
                return
            except Exception as e:
                last_error = e
                time.sleep(1)
        raise wrap_browser_error(
            RuntimeError(f"[Runway Browser] Could not click {label}: {last_error}"),
            default_code="BROWSER_AUTOMATION_NOT_READY",
            details={"phase": f"click_{label}"},
        )

    def close(self):
        print("[Runway Browser] Disconnect requested.")
        try:
            self.browser.close()
        except Exception as exc:
            print(f"[Runway Browser] Disconnect warning: {exc}")
