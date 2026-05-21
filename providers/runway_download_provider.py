from automation.browser_manager import BrowserManager
from pathlib import Path
import time
import requests


class RunwayDownloadProvider:

    def __init__(self):
        self.browser = BrowserManager()
        self.page = None

    def start(self):
        self.page = self.browser.launch()

    def download_video_url(
        self,
        video_url,
        filename_prefix="runway_clip",
    ):
        print("[Runway Download] Downloading exact video URL...")
        print(video_url)

        output_dir = Path("downloads") / "runway"
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{filename_prefix}_{int(time.time())}.mp4"
        save_path = output_dir / filename

        response = requests.get(
            video_url,
            stream=True,
            allow_redirects=True,
            timeout=300,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "video/mp4,*/*",
            },
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"[Runway Download] Download failed: "
                f"{response.status_code} {response.text}"
            )

        total_bytes = 0

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)

        final_size = save_path.stat().st_size

        print("[Runway Download] Saved video:")
        print(save_path)
        print("[Runway Download] Downloaded bytes:")
        print(total_bytes)
        print("[Runway Download] Final file size:")
        print(final_size)

        if final_size < 100_000:
            raise RuntimeError(
                f"[Runway Download] File too small, probably invalid: {final_size}"
            )

        return str(save_path)

    def close(self):
        self.browser.close()