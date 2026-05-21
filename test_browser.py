from automation.browser_manager import BrowserManager


browser = BrowserManager(
    headless=False
)

page = browser.launch()

browser.goto("https://www.google.com")

input("Press ENTER to close browser...")

browser.close()