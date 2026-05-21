from playwright.sync_api import sync_playwright
import os


class BrowserManager:

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def launch(self):
        self.playwright = sync_playwright().start()

        download_path = os.path.abspath("downloads")

        print(f"[BrowserManager] Download path: {download_path}")

        try:
            self.browser = self.playwright.chromium.connect_over_cdp(
                "http://127.0.0.1:9222"
            )
        except Exception as e:
            print("\n[BrowserManager ERROR]")
            print("Chrome is not running with remote debugging.")
            print("First open Chrome from the app Open Browser button.")
            print("Then run the pipeline again.")
            raise e

        if not self.browser.contexts:
            self.context = self.browser.new_context(
                accept_downloads=True
            )
        else:
            self.context = self.browser.contexts[0]

        self.context.set_default_timeout(30000)

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        return self.page

    def goto(self, url):
        print(f"[BrowserManager] Navigating to: {url}")

        self.page.goto(
            url,
            wait_until="domcontentloaded"
        )

    def close(self):
        print("[BrowserManager] Disconnecting from Chrome session...")

        try:
            if self.playwright is not None:
                self.playwright.stop()
        except Exception as e:
            print(f"[BrowserManager] Playwright stop skipped: {e}")

        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

        print("[BrowserManager] Disconnected. Chrome remains open.")