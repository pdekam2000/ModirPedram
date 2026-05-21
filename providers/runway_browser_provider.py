from automation.browser_manager import BrowserManager
import time


class RunwayBrowserProvider:

    def __init__(self):
        self.browser = BrowserManager()
        self.page = None

    def start(self):
        self.page = self.browser.launch()

    def open_runway(self):
        print("[Runway Browser] Opening Runway dashboard...")
        self.browser.goto("https://app.runwayml.com/")
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(8)

    def click_generate_video_home(self):
        print("[Runway Browser] Checking Generate Video / Video workspace...")

        if self.is_video_workspace_ready():
            print("[Runway Browser] Already inside video workspace.")
            return

        selectors = [
            lambda: self.page.get_by_role("button", name="Generate Video"),
            lambda: self.page.locator("button").filter(has_text="Generate Video"),
            lambda: self.page.get_by_text("Generate Video", exact=True),
        ]

        self._click_first(selectors, "Generate Video")
        time.sleep(8)

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

        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

        clicked = self.click_text_in_region(
            text="Gen-4.5",
            min_x=450,
            max_y=550,
        )

        if clicked:
            print("[Runway Browser] Clicked Gen-4.5 top tab.")
            time.sleep(3)
            return

        selectors = [
            lambda: self.page.get_by_text("Gen-4.5", exact=True).nth(0),
            lambda: self.page.locator("button").filter(has_text="Gen-4.5").nth(0),
        ]

        self._click_first(selectors, "Gen-4.5")
        time.sleep(3)

    def click_try_it(self):
        print("[Runway Browser] Clicking Try it...")

        if self.is_prompt_box_ready():
            print("[Runway Browser] Prompt box already ready. Skipping Try it.")
            return

        selectors = [
            lambda: self.page.get_by_role("button", name="Try it"),
            lambda: self.page.locator("button").filter(has_text="Try it"),
            lambda: self.page.get_by_text("Try it", exact=True),
            lambda: self.page.get_by_text("Try it now", exact=True),
            lambda: self.page.get_by_text("Try in Edit Studio", exact=False),
        ]

        self._click_first(selectors, "Try it")
        time.sleep(8)

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

    def fill_prompt(self, prompt: str):
        print("[Runway Browser] Filling prompt...")

        prompt = str(prompt).strip()

        selectors = [
            "textarea",
            "[contenteditable='true']",
            "input[type='text']",
        ]

        last_error = None

        for selector in selectors:
            try:
                boxes = self.page.locator(selector)
                count = boxes.count()

                for i in range(count):
                    box = boxes.nth(i)

                    try:
                        box.wait_for(timeout=5000)
                        box.click(force=True)
                        time.sleep(0.5)

                        self.page.keyboard.press("Control+A")
                        self.page.keyboard.press("Backspace")
                        self.page.keyboard.type(prompt, delay=5)

                        print("[Runway Browser] Prompt filled.")
                        time.sleep(1)
                        return

                    except Exception as inner_error:
                        last_error = inner_error

            except Exception as e:
                last_error = e
                time.sleep(1)

        raise RuntimeError(
            f"[Runway Browser] Could not fill prompt: {last_error}"
        )

    def set_ratio_16_9(self):
        print("[Runway Browser] Setting ratio 16:9...")

        try:
            clicked = self.click_text_in_region(
                text="16:9",
                min_x=0,
                max_y=1200,
            )

            if clicked:
                print("[Runway Browser] Ratio 16:9 selected.")
                time.sleep(1)
                return

        except Exception as e:
            print(f"[Runway Browser] Ratio region click skipped: {e}")

        print("[Runway Browser] Ratio setting skipped.")
        
    def set_duration_10s(self):
        print("[Runway Browser] Setting duration 10s...")

        try:
            clicked_5s = self.click_text_in_region(
                text="5s",
                min_x=0,
                max_y=1200,
            )

            if clicked_5s:
                print("[Runway Browser] Opened duration menu from 5s.")
                time.sleep(1)

                for _ in range(5):
                    self.page.keyboard.press("ArrowDown")
                    time.sleep(0.2)

                self.page.keyboard.press("Enter")
                time.sleep(1)

                print("[Runway Browser] Duration 10s selected with keyboard.")
                return

        except Exception as e:
            print(f"[Runway Browser] Keyboard duration selection failed: {e}")

        print("[Runway Browser] Duration setting skipped. Current duration may remain unchanged.")
    def apply_default_settings(self):
        print("[Runway Browser] Applying default settings...")
        self.set_ratio_16_9()
        self.set_duration_10s()
        print("[Runway Browser] Default settings applied.")

    def click_generate(self):
        print("[Runway Browser] Clicking final Generate...")

        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

        # Prefer the bottom visible Generate button near the prompt panel.
        clicked = self.click_text_in_region(
            text="Generate",
            min_x=0,
            max_y=1200,
        )

        if clicked:
            print("[Runway Browser] Generate clicked.")
            time.sleep(5)
            return

        selectors = [
            lambda: self.page.get_by_role("button", name="Generate"),
            lambda: self.page.locator("button").filter(has_text="Generate"),
            lambda: self.page.get_by_text("Generate", exact=True),
        ]

        self._click_first(selectors, "Generate")
        print("[Runway Browser] Generate clicked.")
        time.sleep(5)

    def prepare_gen45_page(self):
        self.open_runway()
        self.click_generate_video_home()
        self.select_gen45()
        self.click_try_it()

    def click_text_in_region(self, text, min_x=0, max_y=9999):
        script = """
        (args) => {
            const text = args.text;
            const minX = args.minX;
            const maxY = args.maxY;

            const elements = Array.from(document.querySelectorAll(
                "button, div, span, a"
            ));

            const candidates = elements.filter(el => {
                const value = (el.innerText || el.textContent || "").trim();
                if (value !== text) return false;

                const rect = el.getBoundingClientRect();
                if (!rect) return false;
                if (rect.width <= 0 || rect.height <= 0) return false;
                if (rect.left < minX) return false;
                if (rect.top > maxY) return false;

                return true;
            });

            if (!candidates.length) {
                return false;
            }

            candidates.sort((a, b) => {
                const ra = a.getBoundingClientRect();
                const rb = b.getBoundingClientRect();
                return rb.top - ra.top;
            });

            candidates[0].click();
            return true;
        }
        """

        return self.page.evaluate(
            script,
            {
                "text": text,
                "minX": min_x,
                "maxY": max_y,
            }
        )

    def _click_first(self, selectors, label):
        last_error = None

        for selector in selectors:
            try:
                item = selector()
                item.click(timeout=15000, force=True)
                print(f"[Runway Browser] Clicked: {label}")
                return
            except Exception as e:
                last_error = e
                time.sleep(1)

        raise RuntimeError(
            f"[Runway Browser] Could not click {label}: {last_error}"
        )

    def close(self):
        print("[Runway Browser] Disconnect requested.")
        self.browser.close()