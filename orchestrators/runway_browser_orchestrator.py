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

                new_video_url = self.wait_for_generated_video_url(
                    page=provider.page,
                    before_sources=before_sources,
                    clip_index=index,
                    already_downloaded_urls=downloaded_files,
                    max_wait_seconds=900,
                )

                if not new_video_url:
                    raise RuntimeError(
                        "[Runway Browser] No generated video URL detected."
                    )

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

    def get_visible_video_sources_with_info(self, page):
        try:
            return page.evaluate(
                """
                () => Array.from(document.querySelectorAll("video"))
                    .map((v, index) => {
                        const rect = v.getBoundingClientRect();
                        return {
                            index,
                            src: v.currentSrc || v.src || "",
                            width: rect.width || 0,
                            height: rect.height || 0,
                            top: rect.top || 0,
                            left: rect.left || 0,
                            visible: !!(
                                (v.currentSrc || v.src) &&
                                rect.width > 80 &&
                                rect.height > 80
                            )
                        };
                    })
                    .filter(item => item.src && item.visible)
                """
            )
        except Exception:
            return []

    def get_page_generation_state(self, page):
        try:
            text = page.evaluate(
                """
                () => document.body.innerText || ""
                """
            )

            lower = text.lower()

            if "in queue" in lower:
                return "IN_QUEUE"

            if "generating" in lower:
                return "GENERATING"

            if "your generation is in queue" in lower:
                return "IN_QUEUE"

            if "downloaded" in lower or "download" in lower:
                return "READY_OR_HISTORY"

            return "UNKNOWN"

        except Exception:
            return "UNKNOWN"

    def wait_for_generated_video_url(
        self,
        page,
        before_sources,
        clip_index,
        already_downloaded_urls=None,
        max_wait_seconds=900,
    ):
        print("[Runway Browser] Waiting for generated video URL...")

        before_set = set(before_sources or [])
        already_downloaded_urls = set(already_downloaded_urls or [])

        start = time.time()
        last_sources = []
        stable_candidate = None
        stable_count = 0

        while time.time() - start < max_wait_seconds:
            current_sources = self.get_video_sources(page)
            visible_infos = self.get_visible_video_sources_with_info(page)
            page_state = self.get_page_generation_state(page)

            new_sources = [
                src for src in current_sources
                if src and src not in before_set
            ]

            if current_sources != last_sources:
                print(
                    f"[Runway Browser] State: {page_state} | "
                    f"Current videos: {len(current_sources)} | "
                    f"Visible videos: {len(visible_infos)} | "
                    f"New: {len(new_sources)}"
                )
                last_sources = current_sources

            if new_sources:
                newest = new_sources[-1]
                print("[Runway Browser] New video URL detected:")
                print(newest)
                return newest

            # Fallback:
            # Sometimes Runway updates/reuses existing video elements,
            # so no brand-new src appears. In that case, after the page is
            # no longer clearly queued/generating, use the newest visible video.
            if page_state not in ["IN_QUEUE", "GENERATING"] and visible_infos:
                visible_infos_sorted = sorted(
                    visible_infos,
                    key=lambda item: item.get("top", 0),
                    reverse=True,
                )

                candidate = visible_infos_sorted[0].get("src")

                if candidate:
                    if candidate == stable_candidate:
                        stable_count += 1
                    else:
                        stable_candidate = candidate
                        stable_count = 1

                    print(
                        f"[Runway Browser] Fallback candidate stable "
                        f"{stable_count}/3"
                    )

                    if stable_count >= 3:
                        print("[Runway Browser] Using latest visible video URL:")
                        print(candidate)
                        return candidate

            time.sleep(10)

        print("[Runway Browser] Timeout waiting for video URL.")
        return None

    # Backward compatibility
    def wait_for_new_video_url(self, page, before_sources, max_wait_seconds=700):
        return self.wait_for_generated_video_url(
            page=page,
            before_sources=before_sources,
            clip_index=0,
            max_wait_seconds=max_wait_seconds,
        )