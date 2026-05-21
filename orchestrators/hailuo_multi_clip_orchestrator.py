from providers.hailuo_browser_provider import HailuoBrowserProvider
from providers.hailuo_download_provider import HailuoDownloadProvider
import time


class HailuoMultiClipOrchestrator:
    def __init__(self, wait_seconds=150):
        self.wait_seconds = wait_seconds

    def generate_clip(self, prompt: str):
        generator = HailuoBrowserProvider()

        try:
            generator.start()
            generator.open_hailuo()
            generator.fill_prompt(prompt)
            time.sleep(1)
            generator.click_create()

            print(f"\n[Orchestrator] Waiting {self.wait_seconds} seconds...")
            time.sleep(self.wait_seconds)

        finally:
            generator.close()

    def download_latest_clip(self):
        downloader = HailuoDownloadProvider()

        try:
            downloader.start()
            downloader.open_assets()

            opened = downloader.open_latest_video_by_video_element()

            if not opened:
                return None

            return downloader.extract_and_save_video()

        finally:
            downloader.close()

    def run(self, prompts):
        downloaded_files = []

        for index, prompt in enumerate(prompts, start=1):
            print("\n" + "=" * 60)
            print(f"GENERATING CLIP {index}/{len(prompts)}")
            print("=" * 60)

            print(prompt)

            self.generate_clip(prompt)

            file_path = self.download_latest_clip()

            downloaded_files.append(file_path)

            print(f"[Orchestrator] Clip {index} saved:")
            print(file_path)

        return downloaded_files