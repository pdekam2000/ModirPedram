"""
Phase 12J-C2A-OBS — Runway browser execution observability.

Persists step + controlled-tab metadata to session operations/category runtime.
No credentials, cookies, localStorage, or account-sensitive payloads.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.runway_perf_timestamps import (
    STAGE_DOWNLOAD_COMPLETE,
    STAGE_DOWNLOAD_START,
    STAGE_GENERATE_CLICK,
    STAGE_URL_DETECTED,
    STAGE_VIDEO_VISIBLE,
    build_perf_report,
    format_perf_report_lines,
    mark_stage,
)
from content_brain.execution.session_store import ExecutionSessionStore

RUNWAY_BROWSER_STEPS = (
    "browser_connecting",
    "browser_connected",
    "page_selected",
    "preparing_gen45_page",
    "selecting_video_mode",
    "selecting_gen45_model",
    "clicking_try_it_now",
    "try_it_now_clicked",
    "waiting_for_generate_editor",
    "generate_editor_ready",
    "setting_duration_10s",
    "prompt_box_ready",
    "ready_for_generate",
    "filling_prompt",
    "generate_clicked",
    "waiting_for_generation",
    "video_url_detected",
    "download_started",
    "download_completed",
    "failed",
)

_MAX_OPEN_PAGES = 24
_MAX_TITLE_LEN = 200
_MAX_FAILURE_MSG = 240


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme and not parsed.netloc:
        return text[:512]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))[:512]


def _safe_title(title: str) -> str:
    return str(title or "").strip()[:_MAX_TITLE_LEN]


def _is_runway_url(url: str) -> bool:
    host = (urlparse(_safe_url(url)).netloc or "").lower()
    return "runwayml.com" in host


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


class RunwayBrowserObservability:
    """Session-backed Runway browser step + tab observability (no-op without store/session)."""

    def __init__(
        self,
        store: ExecutionSessionStore | None,
        session_id: str | None,
        *,
        clip_index: int | None = None,
    ) -> None:
        self._store = store
        self._session_id = str(session_id or "").strip() or None
        self._clip_index = clip_index
        self._enabled = bool(self._store and self._session_id)
        self._perf_marks: dict[str, float] = {}
        self._perf_wall_anchor: float | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_step(self, step: str, *, detail: str | None = None) -> None:
        normalized = str(step or "").strip()
        if normalized not in RUNWAY_BROWSER_STEPS:
            return
        print(f"[RUNWAY_STEP] step={normalized} session={self._session_id or '-'}")
        payload: dict[str, Any] = {
            "step": normalized,
            "step_updated_at": _now_iso(),
        }
        if detail:
            payload["step_detail"] = str(detail)[:_MAX_FAILURE_MSG]
        if self._clip_index is not None:
            payload["clip_index"] = self._clip_index
        self._persist(payload)

    def mark_failed(self, message: str | None = None) -> None:
        detail = str(message or "runway_browser_failed")[:_MAX_FAILURE_MSG]
        print(f"[RUNWAY_STEP] step=failed session={self._session_id or '-'} detail={detail}")
        payload: dict[str, Any] = {
            "step": "failed",
            "step_updated_at": _now_iso(),
            "failure_message": detail,
        }
        if self._clip_index is not None:
            payload["clip_index"] = self._clip_index
        self._persist(payload)

    def log_prompt_typing_start(self) -> None:
        print(f"[RUNWAY_PROMPT_TYPING_START] session={self._session_id or '-'}")

    def log_generate_clicked(self) -> None:
        self.mark_perf_stage(STAGE_GENERATE_CLICK)
        print(f"[RUNWAY_GENERATE_CLICKED] session={self._session_id or '-'}")

    def mark_perf_stage(self, stage: str) -> None:
        """Phase PERF-A — monotonic timestamp for a pipeline stage (first mark wins)."""
        if not mark_stage(self._perf_marks, stage):
            return
        if stage == STAGE_GENERATE_CLICK and self._perf_wall_anchor is None:
            self._perf_wall_anchor = time.time()
        print(
            f"[RUNWAY_PERF] stage={stage} clip={self._clip_index or '-'} "
            f"session={self._session_id or '-'}"
        )

    def record_perf_report(self) -> dict[str, Any]:
        """Persist and print PERF-A durations for the current clip."""
        report = build_perf_report(
            self._perf_marks,
            clip_index=self._clip_index,
            wall_clock_anchor=self._perf_wall_anchor,
        )
        for line in format_perf_report_lines(report):
            print(f"[RUNWAY_PERF] {line}")

        payload: dict[str, Any] = {"perf_report_updated_at": _now_iso()}
        if self._clip_index is not None:
            clips_perf = self._merge_clip_perf_report(report)
            payload["perf_clips"] = clips_perf
        payload["last_perf_report"] = report
        self._persist(payload)
        return report

    def _merge_clip_perf_report(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._enabled or self._store is None or not self._session_id:
            return [{"clip_index": self._clip_index, "perf_timestamps": report}]
        try:
            session = self._store.load_session(self._session_id)
        except FileNotFoundError:
            return [{"clip_index": self._clip_index, "perf_timestamps": report}]
        runtime = dict(_dict(session.get("execution_runtime")))
        operations = dict(_dict(runtime.get("operations")))
        existing_obs = dict(_dict(operations.get("runway_browser_obs")))
        clips_perf = list(existing_obs.get("perf_clips") or [])
        clip_idx = int(self._clip_index or 0)
        updated = False
        for i, entry in enumerate(clips_perf):
            if int(entry.get("clip_index") or 0) == clip_idx:
                clips_perf[i] = {"clip_index": clip_idx, "perf_timestamps": report}
                updated = True
                break
        if not updated:
            clips_perf.append({"clip_index": clip_idx, "perf_timestamps": report})
        return clips_perf

    def log_wait_started(self, *, max_wait_seconds: int | None = None) -> None:
        suffix = f" max_wait={max_wait_seconds}s" if max_wait_seconds is not None else ""
        print(f"[RUNWAY_WAIT_STARTED] session={self._session_id or '-'}{suffix}")

    def record_output_detection_failure(self, debug: dict[str, Any]) -> None:
        """Phase 12J-E1 — persist placeholder rejection / wait failure context."""
        payload: dict[str, Any] = {
            "output_detection_failed_at": _now_iso(),
            "output_detection_failure": dict(debug or {}),
            "step": "output_detection_failed",
        }
        if self._clip_index is not None:
            payload["clip_index"] = self._clip_index
        rejected = list((debug or {}).get("rejected_candidates") or [])
        print(
            f"[RUNWAY_OUTPUT_DETECTION_FAILED] session={self._session_id or '-'} "
            f"rejected={len(rejected)} page_state={(debug or {}).get('page_state')}"
        )
        self._persist(payload)

    def record_clip_prep(
        self,
        *,
        prompt_expected_length: int | None = None,
        prompt_actual_length: int | None = None,
        prompt_verified: bool | None = None,
        ratio_verified: bool | None = None,
        duration_verified: bool | None = None,
        ratio_selected_before_generate: bool | None = None,
        duration_selected_before_generate: bool | None = None,
        prompt_still_verified_before_generate: bool | None = None,
        ui_stabilized_after_ratio: bool | None = None,
    ) -> None:
        """Phase 12J-E0/E2 — per-clip prompt-first prep metrics (session-safe, no prompt text)."""
        payload: dict[str, Any] = {"clip_prep_updated_at": _now_iso()}
        if self._clip_index is not None:
            payload["clip_index"] = self._clip_index
        if prompt_expected_length is not None:
            payload["prompt_expected_length"] = int(prompt_expected_length)
        if prompt_actual_length is not None:
            payload["prompt_actual_length"] = int(prompt_actual_length)
        if prompt_verified is not None:
            payload["prompt_verified"] = bool(prompt_verified)
        if ratio_verified is not None:
            payload["ratio_verified"] = bool(ratio_verified)
        if duration_verified is not None:
            payload["duration_verified"] = bool(duration_verified)
        if ratio_selected_before_generate is not None:
            payload["ratio_selected_before_generate"] = bool(ratio_selected_before_generate)
        if duration_selected_before_generate is not None:
            payload["duration_selected_before_generate"] = bool(duration_selected_before_generate)
        if prompt_still_verified_before_generate is not None:
            payload["prompt_still_verified_before_generate"] = bool(
                prompt_still_verified_before_generate
            )
        if ui_stabilized_after_ratio is not None:
            payload["ui_stabilized_after_ratio"] = bool(ui_stabilized_after_ratio)
        self._persist(payload)

    def record_controlled_page(self, page: Any, browser_manager: Any | None = None) -> None:
        if page is None:
            return
        page_index = 0
        page_url = _safe_url(getattr(page, "url", "") or "")
        try:
            page_title = _safe_title(page.title())
        except Exception:
            page_title = ""

        open_pages = self._collect_open_pages(browser_manager, controlled_page=page)
        for entry in open_pages:
            if entry.get("controlled"):
                page_index = int(entry.get("index") or 0)
                break

        print(
            f"[RUNWAY_PAGE_SELECTED] index={page_index} "
            f"url={page_url} title={page_title!r} runway={_is_runway_url(page_url)}"
        )

        self.set_step("page_selected")
        self._persist(
            {
                "controlled_page": {
                    "page_index": page_index,
                    "page_url": page_url,
                    "page_title": page_title,
                    "is_runway_url": _is_runway_url(page_url),
                },
                "open_pages": open_pages,
            }
        )

    def _collect_open_pages(
        self,
        browser_manager: Any | None,
        *,
        controlled_page: Any,
    ) -> list[dict[str, Any]]:
        pages_out: list[dict[str, Any]] = []
        controlled_id = id(controlled_page) if controlled_page is not None else None

        browser = getattr(browser_manager, "browser", None) if browser_manager else None
        contexts = []
        if browser is not None:
            try:
                contexts = list(browser.contexts or [])
            except Exception:
                contexts = []
        elif browser_manager is not None:
            ctx = getattr(browser_manager, "context", None)
            if ctx is not None:
                contexts = [ctx]

        global_index = 0
        for context in contexts:
            try:
                pages = list(context.pages or [])
            except Exception:
                pages = []
            for page in pages:
                if global_index >= _MAX_OPEN_PAGES:
                    break
                try:
                    raw_url = getattr(page, "url", "") or ""
                except Exception:
                    raw_url = ""
                safe_url = _safe_url(raw_url)
                try:
                    title = _safe_title(page.title())
                except Exception:
                    title = ""
                pages_out.append(
                    {
                        "index": global_index,
                        "page_url": safe_url,
                        "page_title": title,
                        "is_runway_url": _is_runway_url(safe_url),
                        "controlled": controlled_id is not None and id(page) == controlled_id,
                    }
                )
                global_index += 1

        if not pages_out and controlled_page is not None:
            try:
                raw_url = getattr(controlled_page, "url", "") or ""
            except Exception:
                raw_url = ""
            pages_out.append(
                {
                    "index": 0,
                    "page_url": _safe_url(raw_url),
                    "page_title": _safe_title(
                        controlled_page.title() if hasattr(controlled_page, "title") else ""
                    ),
                    "is_runway_url": _is_runway_url(raw_url),
                    "controlled": True,
                }
            )
        return pages_out

    def _persist(self, patch: dict[str, Any]) -> None:
        if not self._enabled or self._store is None or not self._session_id:
            return
        try:
            session = self._store.load_session(self._session_id)
        except FileNotFoundError:
            return

        runtime = dict(_dict(session.get("execution_runtime")))
        operations = dict(_dict(runtime.get("operations")))
        existing = dict(_dict(operations.get("runway_browser_obs")))
        merged = {**existing, **patch, "observability_version": "12j_c2a_obs_v1"}
        operations["runway_browser_obs"] = merged
        runtime["operations"] = operations

        category_runtime = dict(_dict(runtime.get("category_runtime")))
        video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        video_slot["runway_browser_obs"] = merged
        category_runtime[CATEGORY_VIDEO] = video_slot
        runtime["category_runtime"] = category_runtime

        session["execution_runtime"] = runtime
        session["updated_at"] = _now_iso()
        self._store.save_session(session, overwrite=True)

    def with_clip(self, clip_index: int) -> RunwayBrowserObservability:
        return RunwayBrowserObservability(
            self._store,
            self._session_id,
            clip_index=clip_index,
        )


def build_runway_browser_observability(
    store: ExecutionSessionStore | None,
    session_id: str | None,
    *,
    provider: str | None = None,
) -> RunwayBrowserObservability | None:
    normalized = str(provider or "").strip().lower()
    if normalized != "runway_browser":
        return None
    if not store or not str(session_id or "").strip():
        return None
    return RunwayBrowserObservability(store, session_id)


def extract_runway_browser_obs_from_session(session: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict(session.get("execution_runtime"))
    operations = _dict(runtime.get("operations"))
    obs = _dict(operations.get("runway_browser_obs"))
    if not obs:
        category_runtime = _dict(runtime.get("category_runtime"))
        video_slot = _dict(category_runtime.get(CATEGORY_VIDEO))
        obs = _dict(video_slot.get("runway_browser_obs"))

    video_slot = _dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO))
    video_state = str(video_slot.get("state") or runtime.get("state") or "").strip() or None

    controlled = _dict(obs.get("controlled_page"))
    return {
        "runway_browser_obs": obs,
        "video_runtime": {
            "state": video_state,
            "provider": video_slot.get("provider"),
            "runway_step": obs.get("step"),
            "controlled_tab_url": controlled.get("page_url"),
            "controlled_tab_title": controlled.get("page_title"),
            "is_runway_url": controlled.get("is_runway_url"),
            "open_pages": list(obs.get("open_pages") or []),
        },
    }
