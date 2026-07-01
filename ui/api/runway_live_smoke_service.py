"""Runway live smoke approval runtime API service (Phase H.5) — UI surface only."""

from __future__ import annotations

import threading
from typing import Any

from content_brain.execution.content_brain_live_smoke_handoff import (
    get_registered_e2e_result,
    preview_live_smoke_handoff,
)
from content_brain.execution.runway_live_smoke_approval_runtime import (
    APPROVAL_RUNTIME_VERSION,
    RUN_STATUS_RUNNING,
    RunwayLiveSmokeApprovalRuntime,
    build_ui_approval_callbacks,
)
from content_brain.execution.runway_live_smoke_test import run_live_smoke_test

API_VERSION = "0.1.0"


class RunwayLiveSmokeRuntimeService:
    """Single active live smoke run with shared approval runtime bridge."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runtime: RunwayLiveSmokeApprovalRuntime | None = None
        self._thread: threading.Thread | None = None
        self._last_report: dict[str, Any] | None = None

    def start_run(
        self,
        *,
        story_idea: str,
        project_id: str = "live_smoke_h",
        operator: str = "operator",
        simulate: bool = False,
        clip_count: int = 1,
        execution_mode: str = "FULL_AUTO",
        e2e_result: dict[str, Any] | None = None,
        strict_topic_authority: bool = False,
        auto_director: bool = False,
        auto_prompt_critic: bool = False,
    ) -> dict[str, Any]:
        story = str(story_idea or "").strip()
        if not story:
            return self._error("story_idea is required")

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._error("a live smoke run is already active")

            runtime = RunwayLiveSmokeApprovalRuntime(
                operator=operator,
                project_id=project_id,
                fallback_to_terminal=False,
            )
            runtime.mark_ui_connected(True)
            runtime.set_run_status(RUN_STATUS_RUNNING, detail="Live smoke run started from Runtime Studio UI")
            approval_cb, manual_cb = build_ui_approval_callbacks(runtime)
            self._runtime = runtime
            self._last_report = None

            def _worker() -> None:
                try:
                    resolved_e2e = e2e_result if e2e_result is not None else get_registered_e2e_result()
                    report = run_live_smoke_test(
                        story,
                        project_id=project_id,
                        operator=operator,
                        simulate=simulate,
                        clip_count=clip_count,
                        execution_mode=execution_mode,
                        approval_callback=approval_cb,
                        manual_ack_callback=manual_cb,
                        approval_runtime=runtime,
                        e2e_result=resolved_e2e,
                        strict_topic_authority=strict_topic_authority,
                        auto_director=auto_director,
                        auto_prompt_critic=auto_prompt_critic,
                    )
                    payload = report.to_dict()
                except Exception as exc:
                    payload = {"ok": False, "errors": [str(exc)], "stopped_reason": str(exc)}
                with self._lock:
                    self._last_report = payload
                    if self._runtime is not None:
                        self._runtime.mark_run_finished(
                            ok=bool(payload.get("ok")),
                            stopped_reason=str(payload.get("stopped_reason") or ""),
                            current_step_id=str(payload.get("current_step_id") or ""),
                            last_action=str(payload.get("last_auto_action") or ""),
                            next_action=str(
                                payload.get("next_auto_action")
                                or ("completed" if payload.get("ok") else "failed")
                            ),
                            validation_state=str(
                                payload.get("auto_validation_state")
                                or ("pass" if payload.get("ok") else "fail")
                            ),
                            timeline=list(payload.get("auto_execution_timeline") or []),
                        )

            thread = threading.Thread(target=_worker, name="runway-live-smoke-ui", daemon=True)
            self._thread = thread
            thread.start()

            handoff_preview = preview_live_smoke_handoff(
                story_idea=story,
                clip_count=clip_count,
                e2e_result=e2e_result,
                strict_topic_authority=strict_topic_authority,
                auto_director=auto_director,
                auto_prompt_critic=auto_prompt_critic,
            ).to_dict()

            return {
                "ok": True,
                "api_version": API_VERSION,
                "approval_runtime_version": APPROVAL_RUNTIME_VERSION,
                "project_id": project_id,
                "simulate": simulate,
                "clip_count": clip_count,
                "handoff_preview": handoff_preview,
                "snapshot": runtime.snapshot().to_dict(),
            }

    def handoff_preview(
        self,
        *,
        story_idea: str = "",
        clip_count: int = 3,
    ) -> dict[str, Any]:
        preview = preview_live_smoke_handoff(
            story_idea=str(story_idea or "").strip(),
            clip_count=max(1, int(clip_count)),
        )
        return {
            "ok": True,
            "api_version": API_VERSION,
            "handoff_preview": preview.to_dict(),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            runtime = self._runtime
            active = runtime is not None and (self._thread is not None and self._thread.is_alive())
            return {
                "ok": True,
                "api_version": API_VERSION,
                "active": active,
                "snapshot": runtime.snapshot().to_dict() if runtime else None,
                "report": (
                    dict(self._last_report)
                    if self._last_report and not active
                    else None
                ),
            }

    def connect_ui(self) -> dict[str, Any]:
        with self._lock:
            if self._runtime is None:
                return self._error("no active live smoke run")
            self._runtime.mark_ui_connected(True)
            return {"ok": True, "snapshot": self._runtime.snapshot().to_dict()}

    def approve(self, *, operator: str = "operator") -> dict[str, Any]:
        with self._lock:
            if self._runtime is None:
                return self._error("no active live smoke run")
            return self._runtime.submit_approve(operator=operator)

    def image_ready(self, *, operator: str = "operator") -> dict[str, Any]:
        with self._lock:
            if self._runtime is None:
                return self._error("no active live smoke run")
            return self._runtime.submit_image_ready(operator=operator)

    def cancel(self, *, operator: str = "operator", reason: str = "ui_cancel") -> dict[str, Any]:
        with self._lock:
            if self._runtime is None:
                return self._error("no active live smoke run")
            return self._runtime.submit_cancel(operator=operator, reason=reason)

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"ok": False, "message": message, "api_version": API_VERSION}
