from automation.browser_manager import BrowserManager
import time


class HailuoBrowserProvider:
    def __init__(self):
        self.browser = BrowserManager()
        self.page = None

    def start(self):
        self.page = self.browser.launch()

    def open_hailuo(self):
        print("[Hailuo] Opening Hailuo...")
        self.browser.goto("https://hailuoai.video/")
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(8)

    def fill_prompt(self, prompt: str):
        print("[Hailuo] Filling prompt...")

        prompt_box = self.page.locator("[contenteditable='true']").first
        prompt_box.wait_for(timeout=20000)
        prompt_box.click(force=True)

        time.sleep(0.5)

        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")
        self.page.keyboard.type(prompt, delay=8)

        time.sleep(1)

        print("[Hailuo] Prompt filled.")

    def set_duration_10s(self):
        print("[Hailuo] Setting duration to 10s...")

        try:
            duration_button = self.page.get_by_text("6s", exact=True)
            duration_button.click(timeout=5000, force=True)
            time.sleep(1)

            option_10s = self.page.get_by_text("10s", exact=True)
            option_10s.click(timeout=5000, force=True)

            print("[Hailuo] Duration set to 10s.")
            time.sleep(1)

        except Exception as e:
            print(f"[Hailuo] Duration setting skipped: {e}")

    def set_resolution_768p(self):
        print("[Hailuo] Checking resolution...")

        try:
            resolution_button = self.page.get_by_text("768p", exact=True)
            resolution_button.click(timeout=5000, force=True)
            time.sleep(0.5)
            print("[Hailuo] Resolution already 768p / opened.")
        except Exception as e:
            print(f"[Hailuo] Resolution setting skipped: {e}")

    def disable_start_end_frame_if_needed(self):
        print("[Hailuo] Checking Start/End Frame mode...")

        try:
            start_end = self.page.get_by_text("Start/End Frame", exact=True)
            # فعلاً فقط تشخیص می‌دهیم، خاموش/روشن نمی‌کنیم که خراب نشود
            if start_end.count() > 0:
                print("[Hailuo] Start/End Frame option detected.")
        except Exception as e:
            print(f"[Hailuo] Start/End Frame check skipped: {e}")

    def apply_default_settings(self):
        print("[Hailuo] Applying default video settings...")

        self.disable_start_end_frame_if_needed()
        self.set_resolution_768p()
        self.set_duration_10s()

        print("[Hailuo] Default settings applied.")

    def click_create(self):
        print("[Hailuo] Clicking Create...")

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
                button.click(timeout=15000, force=True)
                print("[Hailuo] Create clicked.")
                return
            except Exception as e:
                last_error = e
                time.sleep(1)

        raise RuntimeError(f"[Hailuo] Could not click Create button: {last_error}")

    def close(self):
        self.browser.close()