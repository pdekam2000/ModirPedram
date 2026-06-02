"""
Runway browser orchestrator — Phase 11E-c hardened.

Bounded waits, cancel checkpoints, structured errors, cleanup on failure.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from providers.runway_api_errors import RunwayCancelledError, RunwayProviderError
from providers.runway_output_url_classifier import (
    RUNWAY_REAL_OUTPUT_NOT_DETECTED,
    build_rejected_candidate_entry,
    is_real_runway_output_url,
    runway_output_rejection_reason,
)
from providers.runway_artifact_utils import (
    mark_clip_results_partial,
    partial_artifact_bundle,
)
from content_brain.execution.runway_perf_timestamps import (
    STAGE_DOWNLOAD_COMPLETE,
    STAGE_DOWNLOAD_START,
    STAGE_URL_DETECTED,
    maybe_mark_video_visible_in_ui,
    try_mark_perf_stage,
)
from providers.runway_browser_support import (
    BROWSER_PROVIDER_VERSION,
    CancelCheck,
    browser_max_wait_seconds,
    browser_poll_interval,
    check_cancel,
    wrap_browser_error,
)


class RunwayBrowserOrchestrator:
    def __init__(
        self,
        wait_seconds: int | None = None,
        *,
        cancel_check: CancelCheck | None = None,
        browser_provider_cls=None,
        download_provider_cls=None,
        runway_obs=None,
    ):
        self.wait_seconds = wait_seconds if wait_seconds is not None else browser_max_wait_seconds()
        self._cancel_check = cancel_check
        self._browser_provider_cls = browser_provider_cls
        self._download_provider_cls = download_provider_cls
        self._runway_obs = runway_obs
        self.clip_results: list[dict[str, Any]] = []
        self.partial_paths: list[str] = []

    def run(self, prompts, *, cancel_check: CancelCheck | None = None):
        effective_cancel = cancel_check or self._cancel_check
        browser_cls = self._browser_provider_cls
        if browser_cls is None:
            from providers.runway_browser_provider import RunwayBrowserProvider

            browser_cls = RunwayBrowserProvider
        download_cls = self._download_provider_cls
        if download_cls is None:
            from providers.runway_download_provider import RunwayDownloadProvider

            download_cls = RunwayDownloadProvider

        print("\n" + "=" * 60)
        print("[Runway Browser Orchestrator] STARTED")
        print(f"[Runway Browser Orchestrator] Version: {BROWSER_PROVIDER_VERSION}")
        print("=" * 60)

        provider = None
        download_provider = None
        downloaded_files: list[str] = []
        self.clip_results = []
        self.partial_paths = []

        obs = self._runway_obs
        try:
            check_cancel(effective_cancel, "before_browser_launch", partial_paths=downloaded_files)

            if obs is not None:
                obs.set_step("browser_connecting")

            provider = browser_cls(cancel_check=effective_cancel, runway_obs=obs)
            provider.start()

            if obs is not None:
                obs.set_step("browser_connected")
                obs.record_controlled_page(provider.page, provider.browser)

            download_provider = download_cls(cancel_check=effective_cancel)
            download_provider.browser = provider.browser
            download_provider.page = provider.page

            if obs is not None:
                obs.set_step("preparing_gen45_page")
            provider.prepare_gen45_page()

            for index, prompt in enumerate(prompts, start=1):
                clip_obs = obs.with_clip(index) if obs is not None and hasattr(obs, "with_clip") else obs
                check_cancel(effective_cancel, "between_clips", partial_paths=downloaded_files)

                print("\n" + "=" * 60)
                print(f"[Runway Browser] CLIP {index}")
                print("=" * 60)

                before_sources = self.get_video_sources(provider.page)

                check_cancel(effective_cancel, "before_prompt_submit", partial_paths=downloaded_files)
                if clip_obs is not None:
                    clip_obs.set_step("filling_prompt")
                    provider._runway_obs = clip_obs
                provider.prepare_clip_for_generate(prompt)
                provider.click_generate()
                if clip_obs is not None:
                    clip_obs.set_step("generate_clicked")

                check_cancel(effective_cancel, "before_generation_wait", partial_paths=downloaded_files)
                new_video_url = self.wait_for_generated_video_url(
                    page=provider.page,
                    before_sources=before_sources,
                    clip_index=index,
                    max_wait_seconds=self.wait_seconds,
                    cancel_check=effective_cancel,
                    partial_paths=downloaded_files,
                    runway_obs=clip_obs,
                )

                if clip_obs is not None:
                    clip_obs.set_step("video_url_detected")

                check_cancel(effective_cancel, "before_download", partial_paths=downloaded_files)
                if clip_obs is not None:
                    clip_obs.set_step("download_started")
                try_mark_perf_stage(clip_obs, STAGE_DOWNLOAD_START)
                download_meta = download_provider.download_video_url(
                    video_url=new_video_url,
                    filename_prefix=f"runway_clip_{index}",
                    clip_index=index,
                )
                if clip_obs is not None:
                    clip_obs.set_step("download_completed")
                try_mark_perf_stage(clip_obs, STAGE_DOWNLOAD_COMPLETE)
                if clip_obs is not None and hasattr(clip_obs, "record_perf_report"):
                    clip_obs.record_perf_report()
                check_cancel(effective_cancel, "after_download", partial_paths=downloaded_files)

                file_path = download_meta["file_path"]
                downloaded_files.append(file_path)
                self.partial_paths.append(file_path)
                self.clip_results.append(download_meta)

            print("[Runway Browser Orchestrator] DONE")
            return downloaded_files

        except RunwayCancelledError as exc:
            if obs is not None:
                obs.mark_failed("cancelled")
            self._attach_partial_artifacts(downloaded_files, exc)
            raise
        except RunwayProviderError as exc:
            if obs is not None:
                obs.mark_failed(str(exc))
            self._attach_partial_artifacts(downloaded_files, exc)
            raise
        except Exception as exc:
            if obs is not None:
                obs.mark_failed(str(exc))
            self.partial_paths = list(downloaded_files)
            wrapped = wrap_browser_error(exc, details={"partial_paths": list(downloaded_files)})
            self._attach_partial_artifacts(downloaded_files, wrapped)
            raise wrapped from exc
        finally:
            self._cleanup(provider, download_provider)

    def _attach_partial_artifacts(self, downloaded_files: list[str], exc: RunwayProviderError) -> None:
        self.partial_paths = list(downloaded_files)
        self.clip_results = mark_clip_results_partial(self.clip_results)
        exc.details.update(partial_artifact_bundle(self.clip_results, self.partial_paths))

    def _cleanup(self, provider, download_provider) -> None:
        for label, item in (("browser", provider), ("download", download_provider)):
            if item is None:
                continue
            try:
                close = getattr(item, "close", None)
                if callable(close):
                    close()
            except Exception as cleanup_error:
                print(f"[Runway Browser Orchestrator] Cleanup warning ({label}): {cleanup_error}")

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
            if "log in" in lower or "sign in" in lower:
                return "LOGIN_REQUIRED"
            if "session expired" in lower:
                return "SESSION_EXPIRED"
            if "in queue" in lower or "your generation is in queue" in lower:
                return "IN_QUEUE"
            if "generating" in lower:
                return "GENERATING"
            if "error" in lower and "generation" in lower:
                return "GENERATION_ERROR"
            if "downloaded" in lower or "download" in lower:
                return "READY_OR_HISTORY"
            return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def _body_text_summary(self, page, *, max_len: int = 400) -> str:
        try:
            text = page.evaluate("() => document.body.innerText || ''") or ""
            collapsed = " ".join(str(text).split())
            return collapsed[:max_len]
        except Exception:
            return ""

    def _try_screenshot_path(self, page, clip_index: int) -> str | None:
        screenshot = getattr(page, "screenshot", None)
        if not callable(screenshot):
            return None
        try:
            out_dir = Path("downloads") / "runway_debug"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"clip_{clip_index}_{int(time.time())}.png"
            screenshot(path=str(path), full_page=True)
            return str(path.resolve())
        except Exception:
            return None

    def _append_rejected_candidate(
        self,
        rejected: list[dict[str, Any]],
        seen: set[tuple[str, str, str]],
        url: str,
        reason: str,
        *,
        source: str,
    ) -> None:
        key = (url, reason, source)
        if key in seen:
            return
        seen.add(key)
        rejected.append(build_rejected_candidate_entry(url, reason, source=source))

    def _accept_output_url(
        self,
        url: str,
        *,
        before_set: set[str],
        downloaded_set: set[str],
        rejected: list[dict[str, Any]],
        seen_rejected: set[tuple[str, str, str]],
        source: str,
    ) -> str | None:
        normalized = str(url or "").strip()
        if not normalized:
            return None
        if normalized in downloaded_set:
            self._append_rejected_candidate(
                rejected,
                seen_rejected,
                normalized,
                "already_downloaded",
                source=source,
            )
            return None
        if normalized in before_set:
            self._append_rejected_candidate(
                rejected,
                seen_rejected,
                normalized,
                "present_before_generate",
                source=source,
            )
            return None
        reason = runway_output_rejection_reason(normalized)
        if reason:
            self._append_rejected_candidate(
                rejected,
                seen_rejected,
                normalized,
                reason,
                source=source,
            )
            return None
        return normalized

    def _build_output_detection_failure_debug(
        self,
        page,
        *,
        before_sources: list[str],
        last_sources: list[str],
        visible_infos: list[dict[str, Any]],
        rejected_candidates: list[dict[str, Any]],
        page_state: str,
        clip_index: int,
    ) -> dict[str, Any]:
        return {
            "clip_index": clip_index,
            "page_state": page_state,
            "before_sources": list(before_sources or [])[:32],
            "last_video_sources": list(last_sources or [])[:32],
            "visible_videos": list(visible_infos or [])[:16],
            "rejected_candidates": list(rejected_candidates or [])[:64],
            "body_text_summary": self._body_text_summary(page),
            "screenshot_path": self._try_screenshot_path(page, clip_index),
        }

    def _persist_output_detection_failure(self, runway_obs, debug: dict[str, Any]) -> None:
        if runway_obs is None:
            return
        if hasattr(runway_obs, "record_output_detection_failure"):
            runway_obs.record_output_detection_failure(debug)
        elif hasattr(runway_obs, "_persist"):
            runway_obs._persist(
                {
                    "output_detection_failure": debug,
                    "step": "output_detection_failed",
                }
            )

    def wait_for_generated_video_url(
        self,
        page,
        before_sources,
        clip_index,
        already_downloaded_urls=None,
        max_wait_seconds=None,
        *,
        cancel_check: CancelCheck | None = None,
        partial_paths: list[str] | None = None,
        runway_obs=None,
    ):
        max_wait = max_wait_seconds if max_wait_seconds is not None else self.wait_seconds
        poll_every = browser_poll_interval()

        effective_obs = runway_obs if runway_obs is not None else self._runway_obs
        if effective_obs is not None:
            effective_obs.set_step("waiting_for_generation")
            if hasattr(effective_obs, "log_wait_started"):
                effective_obs.log_wait_started(max_wait_seconds=max_wait)

        print(f"[Runway Browser] Waiting for real generated video URL (max {max_wait}s)...")

        before_set = set(before_sources or [])
        downloaded_set = set(already_downloaded_urls or [])
        start = time.monotonic()
        last_sources: list[str] = []
        stable_candidate = None
        stable_count = 0
        rejected_candidates: list[dict[str, Any]] = []
        seen_rejected: set[tuple[str, str, str]] = set()
        last_page_state = "UNKNOWN"
        last_visible_infos: list[dict[str, Any]] = []
        video_visible_marked = [False]

        while time.monotonic() - start < max_wait:
            check_cancel(cancel_check, "generation_wait", partial_paths=partial_paths)

            page_state = self.get_page_generation_state(page)
            last_page_state = page_state
            if page_state in {"LOGIN_REQUIRED", "SESSION_EXPIRED"}:
                raise RunwayProviderError(
                    f"[Runway Browser] Session unavailable ({page_state})",
                    code="BROWSER_SESSION_INVALID",
                    details={"clip_index": clip_index, "page_state": page_state},
                )
            if page_state == "GENERATION_ERROR":
                raise RunwayProviderError(
                    "[Runway Browser] Provider page reported generation error",
                    code="PROVIDER_TASK_FAILED",
                    details={"clip_index": clip_index, "page_state": page_state},
                )

            current_sources = self.get_video_sources(page)
            visible_infos = self.get_visible_video_sources_with_info(page)
            last_visible_infos = visible_infos
            new_sources = [src for src in current_sources if src and src not in before_set]

            maybe_mark_video_visible_in_ui(
                effective_obs,
                marked=video_visible_marked,
                before_set=before_set,
                current_sources=current_sources,
                visible_infos=visible_infos,
                is_real_url=is_real_runway_output_url,
            )

            if current_sources != last_sources:
                elapsed = int(time.monotonic() - start)
                real_new = [src for src in new_sources if is_real_runway_output_url(src)]
                print(
                    f"[Runway Browser] State: {page_state} | "
                    f"Current videos: {len(current_sources)} | "
                    f"Visible videos: {len(visible_infos)} | "
                    f"New: {len(new_sources)} (real: {len(real_new)}) | elapsed={elapsed}s"
                )
                last_sources = current_sources

            for src in new_sources:
                accepted = self._accept_output_url(
                    src,
                    before_set=before_set,
                    downloaded_set=downloaded_set,
                    rejected=rejected_candidates,
                    seen_rejected=seen_rejected,
                    source="new_source",
                )
                if accepted:
                    print("[Runway Browser] New real video URL detected:")
                    print(accepted)
                    try_mark_perf_stage(effective_obs, STAGE_URL_DETECTED)
                    return accepted

            if page_state not in ["IN_QUEUE", "GENERATING"] and visible_infos:
                visible_infos_sorted = sorted(
                    visible_infos,
                    key=lambda item: item.get("top", 0),
                    reverse=True,
                )
                candidate = visible_infos_sorted[0].get("src")
                if candidate:
                    accepted = self._accept_output_url(
                        candidate,
                        before_set=before_set,
                        downloaded_set=downloaded_set,
                        rejected=rejected_candidates,
                        seen_rejected=seen_rejected,
                        source="fallback_visible",
                    )
                    if not accepted:
                        stable_candidate = None
                        stable_count = 0
                    elif accepted == stable_candidate:
                        stable_count += 1
                        print(
                            f"[Runway Browser] Real fallback candidate stable {stable_count}/3"
                        )
                        if stable_count >= 3:
                            print("[Runway Browser] Using stable real visible video URL:")
                            print(accepted)
                            try_mark_perf_stage(effective_obs, STAGE_URL_DETECTED)
                            return accepted
                    else:
                        stable_candidate = accepted
                        stable_count = 1

            remaining = max_wait - (time.monotonic() - start)
            if remaining <= 0:
                break
            time.sleep(min(poll_every, remaining))

        debug = self._build_output_detection_failure_debug(
            page,
            before_sources=list(before_sources or []),
            last_sources=last_sources,
            visible_infos=last_visible_infos,
            rejected_candidates=rejected_candidates,
            page_state=last_page_state,
            clip_index=clip_index,
        )
        self._persist_output_detection_failure(effective_obs, debug)

        timeout_code = (
            RUNWAY_REAL_OUTPUT_NOT_DETECTED
            if rejected_candidates or last_sources
            else "PROVIDER_TIMEOUT"
        )
        message = (
            f"[Runway Browser] Real Runway output not detected (clip {clip_index})"
            if timeout_code == RUNWAY_REAL_OUTPUT_NOT_DETECTED
            else f"[Runway Browser] Timeout waiting for generated video URL (clip {clip_index})"
        )
        print(f"[RUNWAY_OUTPUT_DETECTION_FAILED] code={timeout_code} clip={clip_index}")
        raise RunwayProviderError(
            message,
            code=timeout_code,
            details={
                "clip_index": clip_index,
                "max_wait_seconds": max_wait,
                **debug,
            },
        )

    def wait_for_new_video_url(self, page, before_sources, max_wait_seconds=700):
        return self.wait_for_generated_video_url(
            page=page,
            before_sources=before_sources,
            clip_index=0,
            max_wait_seconds=max_wait_seconds,
        )
