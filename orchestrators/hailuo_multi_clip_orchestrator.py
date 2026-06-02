"""
Hailuo multi-clip orchestrator — Phase 11F-b hardened.

Single browser session per run, bounded polling, cancel checkpoints, clip_results[].
"""

from __future__ import annotations

import time
from typing import Any

from providers.hailuo_api_errors import HailuoCancelledError, HailuoProviderError
from providers.hailuo_artifact_utils import (
    clip_result_paths,
    mark_clip_results_partial,
    partial_artifact_bundle,
)
from providers.hailuo_browser_support import (
    BROWSER_PROVIDER_VERSION,
    CancelCheck,
    browser_max_wait_seconds,
    browser_poll_interval,
    check_cancel,
    wrap_browser_error,
)

# Session reuse: one CDP attach per orchestrator.run(); generator and downloader share browser/page.
SESSION_REUSE_MODE = "single_session_per_run"


class HailuoMultiClipOrchestrator:
    def __init__(
        self,
        wait_seconds: int | None = None,
        *,
        cancel_check: CancelCheck | None = None,
        browser_provider_cls=None,
        download_provider_cls=None,
    ):
        self.wait_seconds = wait_seconds if wait_seconds is not None else browser_max_wait_seconds()
        self._cancel_check = cancel_check
        self._browser_provider_cls = browser_provider_cls
        self._download_provider_cls = download_provider_cls
        self.clip_results: list[dict[str, Any]] = []
        self.partial_paths: list[str] = []

    def run(self, prompts, *, cancel_check: CancelCheck | None = None):
        effective_cancel = cancel_check or self._cancel_check
        browser_cls = self._browser_provider_cls
        if browser_cls is None:
            from providers.hailuo_browser_provider import HailuoBrowserProvider

            browser_cls = HailuoBrowserProvider
        download_cls = self._download_provider_cls
        if download_cls is None:
            from providers.hailuo_download_provider import HailuoDownloadProvider

            download_cls = HailuoDownloadProvider

        print("\n" + "=" * 60)
        print("[Hailuo Orchestrator] STARTED")
        print(f"[Hailuo Orchestrator] Version: {BROWSER_PROVIDER_VERSION}")
        print(f"[Hailuo Orchestrator] Session reuse: {SESSION_REUSE_MODE}")
        print("=" * 60)

        generator = None
        downloader = None
        downloaded_files: list[str] = []
        self.clip_results = []
        self.partial_paths = []

        try:
            check_cancel(
                effective_cancel,
                "before_browser_launch",
                partial_paths=downloaded_files,
                clip_results=self.clip_results,
            )

            generator = browser_cls(cancel_check=effective_cancel)
            generator.start()

            downloader = download_cls(cancel_check=effective_cancel)
            downloader.browser = generator.browser
            downloader.page = generator.page

            for index, prompt in enumerate(prompts, start=1):
                check_cancel(
                    effective_cancel,
                    "between_clips",
                    partial_paths=downloaded_files,
                    clip_results=self.clip_results,
                )

                print("\n" + "=" * 60)
                print(f"GENERATING CLIP {index}/{len(prompts)}")
                print("=" * 60)
                print(prompt)

                before_sources = self._get_video_sources(generator.page)

                generator.open_hailuo()
                check_cancel(
                    effective_cancel,
                    "before_prompt_submit",
                    partial_paths=downloaded_files,
                    clip_results=self.clip_results,
                )
                generator.fill_prompt(prompt)
                generator.click_create()

                check_cancel(
                    effective_cancel,
                    "before_generation_wait",
                    partial_paths=downloaded_files,
                    clip_results=self.clip_results,
                )
                self._wait_for_generation(
                    generator.page,
                    before_sources=before_sources,
                    clip_index=index,
                    cancel_check=effective_cancel,
                    partial_paths=downloaded_files,
                )

                check_cancel(
                    effective_cancel,
                    "before_download",
                    partial_paths=downloaded_files,
                    clip_results=self.clip_results,
                )
                downloader.open_assets()
                if not downloader.open_video_for_clip(clip_index=index):
                    raise HailuoProviderError(
                        "[Hailuo Download] No video elements found on assets page",
                        code="DOWNLOAD_FAILED",
                        details={"clip_index": index, "phase": "select_video"},
                    )

                download_meta = downloader.extract_and_save_video(clip_index=index)
                file_path = require_download_path(download_meta, clip_index=index)
                downloaded_files.append(file_path)
                self.partial_paths.append(file_path)
                self.clip_results.append(download_meta)

                print(f"[Orchestrator] Clip {index} saved:")
                print(file_path)

            print("[Hailuo Orchestrator] DONE")
            clip_result_paths(self.clip_results)
            return downloaded_files

        except HailuoCancelledError as exc:
            self._attach_partial_artifacts(downloaded_files, exc)
            raise
        except HailuoProviderError as exc:
            self._attach_partial_artifacts(downloaded_files, exc)
            raise
        except Exception as exc:
            wrapped = wrap_browser_error(exc, details={"partial_paths": list(downloaded_files)})
            self._attach_partial_artifacts(downloaded_files, wrapped)
            raise wrapped from exc
        finally:
            self._cleanup(generator, downloader)

    def _wait_for_generation(
        self,
        page,
        *,
        before_sources: list[str],
        clip_index: int,
        cancel_check: CancelCheck | None,
        partial_paths: list[str],
    ) -> None:
        max_wait = self.wait_seconds
        poll_every = browser_poll_interval()
        before_set = set(before_sources or [])
        start = time.monotonic()
        last_count = -1

        print(f"[Hailuo Orchestrator] Polling for generation complete (max {max_wait}s)...")

        while time.monotonic() - start < max_wait:
            check_cancel(
                cancel_check,
                "generation_wait",
                partial_paths=partial_paths,
                clip_results=self.clip_results,
            )

            page_state = self._get_page_generation_state(page)
            if page_state in {"LOGIN_REQUIRED", "SESSION_EXPIRED"}:
                raise HailuoProviderError(
                    f"[Hailuo] Session unavailable ({page_state})",
                    code="BROWSER_SESSION_INVALID",
                    details={"clip_index": clip_index, "page_state": page_state},
                )
            if page_state == "GENERATION_ERROR":
                raise HailuoProviderError(
                    "[Hailuo] Provider page reported generation error",
                    code="PROVIDER_TASK_FAILED",
                    details={"clip_index": clip_index, "page_state": page_state},
                )

            current_sources = self._get_video_sources(page)
            new_sources = [src for src in current_sources if src and src not in before_set]
            if len(current_sources) != last_count:
                elapsed = int(time.monotonic() - start)
                print(
                    f"[Hailuo Orchestrator] State={page_state} videos={len(current_sources)} "
                    f"new={len(new_sources)} elapsed={elapsed}s"
                )
                last_count = len(current_sources)

            if new_sources or page_state in {"READY", "READY_OR_HISTORY"}:
                print("[Hailuo Orchestrator] Generation appears complete.")
                return

            if page_state in {"GENERATING", "IN_QUEUE", "UNKNOWN"}:
                remaining = max_wait - (time.monotonic() - start)
                if remaining <= 0:
                    break
                time.sleep(min(poll_every, remaining))
                continue

            remaining = max_wait - (time.monotonic() - start)
            if remaining <= 0:
                break
            time.sleep(min(poll_every, remaining))

        raise HailuoProviderError(
            f"[Hailuo Orchestrator] Timeout waiting for generation (clip {clip_index})",
            code="PROVIDER_TIMEOUT",
            details={"clip_index": clip_index, "max_wait_seconds": max_wait},
        )

    def _get_video_sources(self, page) -> list[str]:
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

    def _get_page_generation_state(self, page) -> str:
        try:
            text = (page.evaluate("() => document.body.innerText || ''") or "").lower()
        except Exception:
            return "UNKNOWN"
        if "log in" in text or "sign in" in text:
            return "LOGIN_REQUIRED"
        if "session expired" in text:
            return "SESSION_EXPIRED"
        if "generating" in text or "in queue" in text:
            return "GENERATING"
        if "error" in text and "generation" in text:
            return "GENERATION_ERROR"
        if "download" in text or "mine" in text:
            return "READY_OR_HISTORY"
        if self._get_video_sources(page):
            return "READY"
        return "UNKNOWN"

    def _attach_partial_artifacts(self, downloaded_files: list[str], exc: HailuoProviderError) -> None:
        self.partial_paths = list(downloaded_files)
        self.clip_results = mark_clip_results_partial(self.clip_results)
        bundle = partial_artifact_bundle(self.clip_results, self.partial_paths)
        exc.details.update(bundle)
        exc.details["artifact_preserved"] = True
        if isinstance(exc, HailuoCancelledError):
            exc.partial_paths = list(self.partial_paths)
            exc.clip_results = list(self.clip_results)

    def _cleanup(self, generator, downloader) -> None:
        # Close once via generator; downloader shares browser — do not double-disconnect.
        if generator is not None:
            try:
                generator.close()
            except Exception as cleanup_error:
                print(f"[Hailuo Orchestrator] Cleanup warning: {cleanup_error}")
        elif downloader is not None:
            try:
                downloader.close()
            except Exception as cleanup_error:
                print(f"[Hailuo Orchestrator] Cleanup warning: {cleanup_error}")


def require_download_path(record: dict[str, Any], *, clip_index: int | None = None) -> str:
    path = record.get("file_path")
    if not path:
        raise HailuoProviderError(
            "Download returned artifact without file_path",
            code="ARTIFACT_NULL_PATH",
            details={"clip_index": clip_index, "artifact_preserved": False},
        )
    return str(path)
