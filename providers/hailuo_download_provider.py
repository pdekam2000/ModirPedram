"""
Hailuo download provider — Phase 11F-c artifact continuity.

Shares browser session with generator; normalized clip_results; no silent failures.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from content_brain.execution.hailuo_config import HAILUO_BROWSER_ROUTER_KEY
from providers.hailuo_api_errors import HailuoProviderError
from providers.hailuo_artifact_utils import (
    MODE_BROWSER,
    build_job_id,
    finalize_download_artifact,
    is_valid_source_url,
)
from providers.hailuo_browser_support import (
    CancelCheck,
    browser_assets_settle_seconds,
    browser_step_timeout_ms,
    check_cancel,
    wrap_browser_error,
)


class HailuoDownloadProvider:
    def __init__(self, *, cancel_check: CancelCheck | None = None, output_dir: str | Path | None = None):
        self._cancel_check = cancel_check
        self.browser = None
        self.page = None
        self.output_dir = Path(output_dir or "downloads")
        self.clip_results: list[dict] = []

    def open_assets(self):
        print("[DownloadProvider] Opening assets...")
        check_cancel(self._cancel_check, "before_download_navigate")
        try:
            self.browser.goto("https://hailuoai.video/mine")
            settle = browser_assets_settle_seconds()
            if settle > 0:
                time.sleep(settle)
        except Exception as exc:
            raise wrap_browser_error(exc, details={"phase": "open_assets"}) from exc

    def open_video_for_clip(self, *, clip_index: int | None = None) -> bool:
        """Select assets-page video; prefers index 0 (latest) with clip_index bounds."""
        print("[DownloadProvider] Opening video for clip...")
        check_cancel(self._cancel_check, "before_download_select")
        try:
            videos = self.page.locator("video")
            count = videos.count()
            print(f"[DownloadProvider] Video count: {count}")
            if count == 0:
                return False
            pick = 0
            if clip_index is not None and clip_index > 0:
                pick = min(clip_index - 1, count - 1)
            videos.nth(pick).click(timeout=browser_step_timeout_ms(), force=True)
            time.sleep(min(5.0, browser_assets_settle_seconds()))
            print("[DownloadProvider] Detail page opened:")
            print(self.page.url)
            return True
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="BROWSER_AUTOMATION_NOT_READY",
                details={"phase": "open_video_for_clip", "clip_index": clip_index},
            ) from exc

    def open_latest_video_by_video_element(self, *, clip_index: int | None = None) -> bool:
        return self.open_video_for_clip(clip_index=clip_index)

    def extract_and_save_video(self, *, clip_index: int | None = None) -> dict:
        print("[DownloadProvider] Extracting video from page...")
        check_cancel(self._cancel_check, "download_stream")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = self.page.evaluate(
                """
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
                """
            )

            if not result.get("ok"):
                message = result.get("error") or "Video extraction failed"
                raise HailuoProviderError(
                    f"[Hailuo Download] {message}",
                    code="DOWNLOAD_FAILED",
                    details={"clip_index": clip_index, "phase": "extract"},
                )

            source_url = str(result.get("url") or "")
            if not is_valid_source_url(source_url):
                raise HailuoProviderError(
                    f"Invalid Hailuo download source URL: {source_url!r}",
                    code="DOWNLOAD_FAILED",
                    details={"clip_index": clip_index, "source_url": source_url, "phase": "validate_source"},
                )

            video_data = base64.b64decode(result["data"])
            job_id = build_job_id(clip_index=clip_index)
            filename = f"{job_id}_{int(time.time())}.mp4"
            save_path = self.output_dir / filename
            with save_path.open("wb") as handle:
                handle.write(video_data)

            print("[DownloadProvider] Saved video:")
            print(save_path)

            artifact = finalize_download_artifact(
                save_path,
                mode=MODE_BROWSER,
                provider_id=HAILUO_BROWSER_ROUTER_KEY,
                clip_index=clip_index,
                task_id=job_id,
                source_url=source_url,
                metadata={"mime": result.get("mime"), "hailuo_job_id": job_id},
            )
            self.clip_results.append(artifact)
            check_cancel(self._cancel_check, "after_download")
            return artifact

        except HailuoProviderError:
            raise
        except Exception as exc:
            raise wrap_browser_error(
                exc,
                default_code="DOWNLOAD_FAILED",
                details={"clip_index": clip_index, "phase": "extract"},
            ) from exc

    def close(self):
        if self.browser is not None:
            self.browser.close()
