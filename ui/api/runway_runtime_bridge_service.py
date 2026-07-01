"""Runway Runtime Bridge service — AI Content Factory Phase I / Kling entry (Phase 5A/5B)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.browser_launcher import launch_controlled_chrome, resolve_runway_browser_config
from content_brain.execution.browser_connectivity_probe import run_browser_probes
from content_brain.execution.kling_frame_continuity_runtime import run_kling_frame_continuity_chain
from content_brain.execution.kling_starter_frame_generator import kling_frame_run_dir
from content_brain.execution.runway_live_smoke_test import (
    browser_probe_is_ok,
    browser_probe_message,
    run_live_smoke_test,
)
from content_brain.execution.runway_runtime_bridge_adapter import (
    BRIDGE_ADAPTER_VERSION,
    PROVIDER_KLING,
    SUPPORTED_PROVIDER,
    RunwayRuntimeBridgeValidationError,
    RunwayRuntimeGenerateContext,
    build_generate_context,
)

BRIDGE_SERVICE_VERSION = "runway_runtime_bridge_service_v2"
BRIDGE_OPERATOR = "ai_content_factory"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
EXECUTION_MODE_FULL_AUTO = "FULL_AUTO"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _acf_auto_approve(_control_key: str, _step_id: str, _label: str) -> bool:
    return True


def _acf_auto_ack(_step_id: str, _action: str) -> bool:
    return True


@dataclass
class BridgeRunRecord:
    run_id: str
    project_id: str
    provider: str
    model: str
    aspect_ratio: str
    clip_count: int
    duration_seconds: int
    status: str = STATUS_RUNNING
    started_at: str = ""
    finished_at: str = ""
    thread: threading.Thread | None = None
    report: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _map_kling_worker_report(
    *,
    clip_results: list[dict[str, Any]],
    generation_report: dict[str, Any],
    download_report: dict[str, Any],
    final_video: str,
    continuity_chain: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    downloaded: list[str] = []
    clips_completed = 0
    for item in clip_results:
        clip_index = int(item.get("clip_index") or 0)
        clip_video = run_dir / "clips" / f"c{clip_index}" / "video.mp4"
        output_path = str(item.get("clip_output_path") or item.get("download_path") or "").strip()
        if clip_video.is_file():
            resolved = str(clip_video.resolve())
            downloaded.append(resolved)
            clips_completed += 1
        elif output_path and Path(output_path).is_file():
            downloaded.append(str(Path(output_path).resolve()))
            clips_completed += 1
        elif item.get("ok"):
            clips_completed += 1

    if final_video:
        final_resolved = str(Path(final_video).resolve())
        if final_resolved not in downloaded:
            downloaded.append(final_resolved)

    chain_complete = bool(generation_report.get("chain_complete"))
    ok = chain_complete or (bool(final_video) and generation_report.get("status") == "completed")
    errors: list[str] = []
    if not ok:
        stop_reason = str(generation_report.get("stop_reason") or "").strip()
        if stop_reason:
            errors.append(stop_reason)
        precondition = str(generation_report.get("precondition_message") or "").strip()
        if precondition:
            errors.append(precondition)
        for item in clip_results:
            if item.get("ok"):
                continue
            for err in list(item.get("errors") or []):
                text = str(err).strip()
                if text:
                    errors.append(text)
            stopped = str(item.get("stopped_reason") or item.get("failure_reason") or "").strip()
            if stopped:
                errors.append(stopped)

    return {
        "ok": ok,
        "provider": PROVIDER_KLING,
        "status": generation_report.get("status"),
        "clips_completed": clips_completed,
        "downloaded_file_paths": downloaded,
        "download_dir": str(run_dir.resolve()),
        "generation_report": generation_report,
        "download_report": download_report,
        "continuity_chain": continuity_chain,
        "clip_results": clip_results,
        "final_video_path": final_video,
        "errors": errors,
        "chain_complete": chain_complete,
    }


class RunwayRuntimeBridgeService:
    """Isolated bridge runs keyed by run_id (does not use live-smoke singleton)."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root).resolve()
        self._lock = threading.RLock()
        self._runs: dict[str, BridgeRunRecord] = {}

    def start_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            context = build_generate_context(
                project_id=str(payload.get("project_id") or ""),
                provider=str(payload.get("provider") or ""),
                model=str(payload.get("model") or ""),
                aspect_ratio=str(payload.get("aspect_ratio") or ""),
                duration_seconds=int(payload.get("duration_seconds") or 0),
                prompt_package=dict(payload.get("prompt_package") or {}),
            )
        except RunwayRuntimeBridgeValidationError as exc:
            return {
                "ok": False,
                "message": str(exc),
                "error_code": exc.code,
                "status": STATUS_FAILED,
            }

        with self._lock:
            existing = self._runs.get(context.run_id)
            if existing is not None and existing.thread is not None and existing.thread.is_alive():
                return {
                    "ok": False,
                    "run_id": context.run_id,
                    "message": f"run_id already active: {context.run_id}",
                    "error_code": "run_id_active",
                    "status": STATUS_RUNNING,
                }

        browser_error = self._ensure_browser_ready()
        if browser_error:
            return {
                "ok": False,
                "run_id": context.run_id,
                "project_id": context.project_id,
                "message": browser_error,
                "error_code": "browser_unavailable",
                "status": STATUS_FAILED,
            }

        record = BridgeRunRecord(
            run_id=context.run_id,
            project_id=context.project_id,
            provider=context.provider,
            model=context.model,
            aspect_ratio=context.aspect_ratio,
            clip_count=context.clip_count,
            duration_seconds=context.duration_seconds,
            status=STATUS_RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        def _worker() -> None:
            try:
                if context.provider == PROVIDER_KLING:
                    payload_out = self._run_kling_chain(context)
                else:
                    report = run_live_smoke_test(
                        context.story_idea,
                        project_id=context.run_id,
                        operator=BRIDGE_OPERATOR,
                        simulate=False,
                        clip_count=context.clip_count,
                        execution_mode=EXECUTION_MODE_FULL_AUTO,
                        e2e_result=context.e2e_result,
                        approval_callback=_acf_auto_approve,
                        manual_ack_callback=_acf_auto_ack,
                    )
                    payload_out = report.to_dict()
            except Exception as exc:
                payload_out = {"ok": False, "errors": [str(exc)], "stopped_reason": str(exc)}

            with self._lock:
                active = self._runs.get(context.run_id)
                if active is None:
                    return
                active.report = dict(payload_out)
                active.errors = [str(item) for item in list(payload_out.get("errors") or [])]
                active.status = STATUS_COMPLETED if bool(payload_out.get("ok")) else STATUS_FAILED
                active.finished_at = datetime.now(timezone.utc).isoformat()

        thread = threading.Thread(
            target=_worker,
            name=f"runway-runtime-bridge-{context.run_id}",
            daemon=True,
        )
        record.thread = thread

        with self._lock:
            self._runs[context.run_id] = record

        thread.start()
        return self._running_response(context)

    def _run_kling_chain(self, context: RunwayRuntimeGenerateContext) -> dict[str, Any]:
        if context.kling_plan is None:
            raise ValueError("kling_plan is required for Kling bridge runs")

        run_dir = kling_frame_run_dir(self._project_root, context.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        clip_results, generation_report, download_report, final_video, _, continuity_chain = (
            run_kling_frame_continuity_chain(
                project_root=self._project_root,
                run_id=context.run_id,
                run_dir=run_dir,
                plan=context.kling_plan,
                approved_by=BRIDGE_OPERATOR,
                confirm_credit_spend=True,
                starter_frame_path=None,
                cdp_url=DEFAULT_CDP_URL,
                payload={
                    "approve_all_clips": True,
                    "aspect_ratio": context.aspect_ratio,
                },
            )
        )
        return _map_kling_worker_report(
            clip_results=list(clip_results),
            generation_report=dict(generation_report),
            download_report=dict(download_report),
            final_video=str(final_video or ""),
            continuity_chain=dict(continuity_chain),
            run_dir=run_dir,
        )

    def get_status(self, run_id: str) -> dict[str, Any]:
        key = str(run_id or "").strip()
        if not key:
            return {"ok": False, "message": "run_id is required", "error_code": "missing_run_id"}

        with self._lock:
            record = self._runs.get(key)
            if record is None:
                return {"ok": False, "run_id": key, "message": "run not found", "error_code": "not_found"}

            active = record.thread is not None and record.thread.is_alive()
            report = dict(record.report) if record.report else None
            status = STATUS_RUNNING if active else record.status

        downloaded = list(report.get("downloaded_file_paths") or []) if report else []
        clips_completed = int(report.get("clips_completed") or 0) if report else 0
        if record.provider == SUPPORTED_PROVIDER and report:
            clips_completed = int(report.get("clips_completed") or clips_completed)

        return {
            "ok": True,
            "run_id": record.run_id,
            "project_id": record.project_id,
            "provider": record.provider,
            "model": record.model or None,
            "status": status,
            "active": active,
            "clip_count": record.clip_count,
            "aspect_ratio": record.aspect_ratio,
            "clips_completed": clips_completed,
            "downloaded_file_paths": downloaded,
            "download_dir": str(report.get("download_dir") or "") if report else "",
            "report": report if not active else None,
            "errors": list(record.errors),
        }

    def _ensure_browser_ready(self) -> str | None:
        browser_config = resolve_runway_browser_config(self._project_root)
        probe = run_browser_probes(
            browser_config,
            project_root=self._project_root,
            require_playwright_attach=True,
        )
        if browser_probe_is_ok(probe):
            return None

        launch = launch_controlled_chrome(self._project_root)
        if not bool(launch.get("success")) and not bool(launch.get("cdp_reachable")):
            detail = str(launch.get("message") or "Chrome launch failed")
            return f"browser launch failed: {detail}"

        probe = run_browser_probes(
            browser_config,
            project_root=self._project_root,
            require_playwright_attach=True,
        )
        if browser_probe_is_ok(probe):
            return None
        return browser_probe_message(probe) or "browser probe failed after launch"

    @staticmethod
    def _running_response(context: RunwayRuntimeGenerateContext) -> dict[str, Any]:
        return {
            "ok": True,
            "run_id": context.run_id,
            "project_id": context.project_id,
            "provider": context.provider,
            "model": context.model or None,
            "status": STATUS_RUNNING,
            "clip_count": context.clip_count,
            "aspect_ratio": context.aspect_ratio,
            "poll_url": f"/runway/runtime/status/{context.run_id}",
            "bridge_version": BRIDGE_SERVICE_VERSION,
            "adapter_version": BRIDGE_ADAPTER_VERSION,
        }


__all__ = [
    "BRIDGE_SERVICE_VERSION",
    "RunwayRuntimeBridgeService",
]
