from pathlib import Path
import time
from typing import Any

from providers.runway_api_errors import RunwayProviderError
from providers.runway_artifact_utils import (
    CAPABILITY_TEXT_TO_VIDEO,
    MODE_BROWSER,
    RUNWAY_BROWSER_ROUTER_KEY,
    finalize_download_artifact,
)
from providers.runway_browser_support import (
    BROWSER_PROVIDER_VERSION,
    CancelCheck,
    check_cancel,
    wrap_browser_error,
)


class RunwayDownloadProvider:

    def __init__(self, *, cancel_check: CancelCheck | None = None, output_dir: str | Path | None = None):
        self.browser = None
        self.page = None
        self._cancel_check = cancel_check
        self.output_dir = Path(output_dir or Path("downloads") / "runway")

    def start(self):
        raise NotImplementedError("RunwayDownloadProvider.start is unused; orchestrator shares browser session.")

    def download_video_url(
        self,
        video_url,
        filename_prefix="runway_clip",
        *,
        clip_index: int | None = None,
    ) -> dict[str, Any]:
        print("[Runway Download] Downloading exact video URL...")
        print(video_url)

        check_cancel(self._cancel_check, "before_download")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{filename_prefix}_{int(time.time())}.mp4"
        save_path = self.output_dir / filename

        try:
            response = self._http_get(video_url)
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="DOWNLOAD_FAILED",
                details={"video_url": video_url, "clip_index": clip_index},
            ) from exc

        if response.status_code != 200:
            raise RunwayProviderError(
                f"[Runway Download] Download failed: {response.status_code} {response.text}",
                code="DOWNLOAD_FAILED",
                http_status=response.status_code,
                details={"video_url": video_url, "clip_index": clip_index},
            )

        total_bytes = 0
        with open(save_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                check_cancel(self._cancel_check, "download_stream")
                if chunk:
                    handle.write(chunk)
                    total_bytes += len(chunk)

        print("[Runway Download] Saved video:")
        print(save_path)
        print("[Runway Download] Downloaded bytes:")
        print(total_bytes)

        check_cancel(self._cancel_check, "after_download")

        return finalize_download_artifact(
            save_path,
            mode=MODE_BROWSER,
            provider_id=RUNWAY_BROWSER_ROUTER_KEY,
            capability=CAPABILITY_TEXT_TO_VIDEO,
            clip_index=clip_index,
            source_url=video_url,
            metadata={"provider_version": BROWSER_PROVIDER_VERSION},
        )

    def _http_get(self, url: str):
        try:
            import requests as requests_lib
        except ImportError as exc:
            raise RunwayProviderError(
                "requests package is not installed",
                code="DOWNLOAD_FAILED",
            ) from exc
        return requests_lib.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=300,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "video/mp4,*/*",
            },
        )

    def close(self):
        if self.browser is None:
            return
        try:
            self.browser.close()
        except Exception as exc:
            print(f"[Runway Download] Disconnect warning: {exc}")
