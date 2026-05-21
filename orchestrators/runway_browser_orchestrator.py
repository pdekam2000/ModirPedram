from providers.runway_browser_provider import RunwayBrowserProvider
from providers.runway_download_provider import RunwayDownloadProvider
import time


class RunwayBrowserOrchestrator:

    def __init__(self, wait_seconds=180):
        self.wait_seconds = wait_seconds

    def run(self, prompts):
        print("\n" + "=" * 60)
        print("[Runway Browser Orchestrator] STARTED")
        print("=" * 60)

        provider = RunwayBrowserProvider()
        provider.start()

        download_provider = RunwayDownloadProvider()
        download_provider.browser = provider.browser
        download_provider.page = provider.page

        downloaded_files = []

        try:
            provider.prepare_gen45_page()

            for index, prompt in enumerate(prompts, start=1):
                print("\n" + "=" * 60)
                print(f"[Runway Browser] CLIP {index}")
                print("=" * 60)

                before_sources = self.get_video_sources(provider.page)

                provider.fill_prompt(prompt)
                provider.apply_default_settings()
                provider.click_generate()

                new_video_url = self.wait_for_new_video_url(
                    page=provider.page,
                    before_sources=before_sources,
                    max_wait_seconds=700,
                )

                if not new_video_url:
                    raise RuntimeError("[Runway Browser] No new generated video detected.")

                file_path = download_provider.download_video_url(
                    video_url=new_video_url,
                    filename_prefix=f"runway_clip_{index}",
                )

                downloaded_files.append(file_path)

            print("[Runway Browser Orchestrator] DONE")
            return downloaded_files

        except Exception as e:
            print("\n[Runway Browser Orchestrator] ERROR")
            print(e)
            print("[DEBUG] Browser will stay open. Send screenshot + terminal log.")
            time.sleep(999999)

    def get_video_sources(self, page):
        try:
            return page.evaluate(
                """
                () => Array.from(document.querySelectorAll("video"))
                    .map(v => v.currentSrc || v.src || "")
                    .filter(Boolean)
                """
            )
        except Exception:
            return []

    def wait_for_new_video_url(self, page, before_sources, max_wait_seconds=700):
        print("[Runway Browser] Waiting for NEW generated video URL...")

        before_set = set(before_sources)
        start = time.time()
        last_seen = []

        while time.time() - start < max_wait_seconds:
            current_sources = self.get_video_sources(page)

            new_sources = [
                src for src in current_sources
                if src and src not in before_set
            ]

            if current_sources != last_seen:
                print(
                    f"[Runway Browser] Current videos: {len(current_sources)} | "
                    f"New: {len(new_sources)}"
                )
                last_seen = current_sources

            if new_sources:
                newest = new_sources[-1]
                print("[Runway Browser] New video URL detected:")
                print(newest)
                return newest

            time.sleep(10)

        return None