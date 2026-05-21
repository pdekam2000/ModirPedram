from automation.browser_manager import BrowserManager
from pathlib import Path
import base64
import time


class HailuoDownloadProvider:
    def __init__(self):
        self.browser = BrowserManager()
        self.page = None

    def start(self):
        self.page = self.browser.launch()

    def open_assets(self):
        print("[DownloadProvider] Opening assets...")
        self.browser.goto("https://hailuoai.video/mine")
        time.sleep(10)

    def open_latest_video_by_video_element(self):
        print("[DownloadProvider] Opening latest video...")

        videos = self.page.locator("video")
        count = videos.count()
        print(f"[DownloadProvider] Video count: {count}")

        if count == 0:
            return False

        videos.nth(0).click(timeout=10000, force=True)
        time.sleep(5)

        print("[DownloadProvider] Detail page opened:")
        print(self.page.url)
        return True

    def extract_and_save_video(self):
        print("[DownloadProvider] Extracting video from page...")

        output_dir = Path("downloads")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = self.page.evaluate("""
                async () => {
                    const video = document.querySelector("video");
                    if (!video) {
                        return { ok: false, error: "No video element found" };
                    }

                    const url = video.currentSrc || video.src;
                    if (!url) {
                        return { ok: false, error: "No video src/currentSrc found" };
                    }

                    const response = await fetch(url);
                    const blob = await response.blob();
                    const buffer = await blob.arrayBuffer();

                    let binary = "";
                    const bytes = new Uint8Array(buffer);
                    const chunkSize = 0x8000;

                    for (let i = 0; i < bytes.length; i += chunkSize) {
                        const chunk = bytes.subarray(i, i + chunkSize);
                        binary += String.fromCharCode.apply(null, chunk);
                    }

                    return {
                        ok: true,
                        url: url,
                        mime: blob.type,
                        data: btoa(binary)
                    };
                }
            """)

            if not result.get("ok"):
                print("[DownloadProvider] Extract failed:")
                print(result.get("error"))
                return None

            video_data = base64.b64decode(result["data"])

            filename = f"hailuo_clip_{int(time.time())}.mp4"
            save_path = output_dir / filename

            with open(save_path, "wb") as f:
                f.write(video_data)

            print("[DownloadProvider] Saved video:")
            print(save_path)
            print("[DownloadProvider] MIME:")
            print(result.get("mime"))
            print("[DownloadProvider] Source URL:")
            print(result.get("url"))

            return str(save_path)

        except Exception as e:
            print("[DownloadProvider] ERROR extracting video:")
            print(e)
            return None

    def close(self):
        self.browser.close()