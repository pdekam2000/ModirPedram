"""
Phase RUNWAY-STARTER-TO-VIDEO-H.5 — Runway live smoke approval runtime (view + approval surface).

Thread-safe bridge between RunwayLiveSmokeRunner callbacks and Runtime Studio UI.
Does not modify approval guard, semi-auto engine, or provider execution.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

APPROVAL_RUNTIME_VERSION = "runway_live_smoke_h5_ui_v2_gate_safety"

GATE_IDLE = "idle"
GATE_APPROVAL = "approval"
GATE_MANUAL_HOLD = "manual_hold"
GATE_CANCELLED = "cancelled"
GATE_COMPLETED = "completed"

RUN_STATUS_IDLE = "idle"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_WAITING_APPROVAL = "waiting_approval"
RUN_STATUS_WAITING_IMAGE_READY = "waiting_image_ready"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class RunwayApprovalHistoryEntry:
    event: str
    step_id: str = ""
    control_key: str = ""
    label: str = ""
    granted: bool | None = None
    operator: str = ""
    timestamp: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "step_id": self.step_id,
            "control_key": self.control_key,
            "label": self.label,
            "granted": self.granted,
            "operator": self.operator,
            "timestamp": self.timestamp,
            "detail": self.detail,
        }


@dataclass
class RunwayLiveSmokeApprovalSnapshot:
    runtime_version: str = APPROVAL_RUNTIME_VERSION
    run_status: str = RUN_STATUS_IDLE
    gate_type: str = GATE_IDLE
    waiting: bool = False
    current_step_id: str = ""
    current_control_key: str = ""
    current_label: str = ""
    current_action: str = ""
    ui_connected: bool = False
    fallback_to_terminal: bool = True
    project_id: str = ""
    operator: str = "operator"
    approval_history: list[dict[str, Any]] = field(default_factory=list)
    runtime_logs: list[str] = field(default_factory=list)
    run_ok: bool | None = None
    stopped_reason: str = ""
    cancelled: bool = False
    gate_ready: bool = False
    gate_enabled: bool = False
    gate_reason: str = ""
    expected_step_id: str = ""
    early_approval_rejections_count: int = 0
    approval_gate_safety_enabled: bool = True
    execution_mode: str = ""
    last_auto_action: str = ""
    next_auto_action: str = ""
    auto_validation_state: str = ""
    auto_execution_timeline: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_version": self.runtime_version,
            "run_status": self.run_status,
            "gate_type": self.gate_type,
            "waiting": self.waiting,
            "current_step_id": self.current_step_id,
            "current_control_key": self.current_control_key,
            "current_label": self.current_label,
            "current_action": self.current_action,
            "ui_connected": self.ui_connected,
            "fallback_to_terminal": self.fallback_to_terminal,
            "project_id": self.project_id,
            "operator": self.operator,
            "approval_history": list(self.approval_history),
            "runtime_logs": list(self.runtime_logs),
            "run_ok": self.run_ok,
            "stopped_reason": self.stopped_reason,
            "cancelled": self.cancelled,
            "gate_ready": self.gate_ready,
            "gate_enabled": self.gate_enabled,
            "gate_reason": self.gate_reason,
            "expected_step_id": self.expected_step_id,
            "early_approval_rejections_count": self.early_approval_rejections_count,
            "approval_gate_safety_enabled": self.approval_gate_safety_enabled,
            "execution_mode": self.execution_mode,
            "last_auto_action": self.last_auto_action,
            "next_auto_action": self.next_auto_action,
            "auto_validation_state": self.auto_validation_state,
            "auto_execution_timeline": list(self.auto_execution_timeline),
        }


TerminalApprovalFn = Callable[[str, str, str], bool]
TerminalManualAckFn = Callable[[str, str], bool]


class RunwayLiveSmokeApprovalRuntime:
    """Approval surface for Phase H live smoke — engine callbacks block until UI/terminal acts."""

    def __init__(
        self,
        *,
        operator: str = "operator",
        project_id: str = "live_smoke_h",
        fallback_to_terminal: bool = True,
        terminal_approval: TerminalApprovalFn | None = None,
        terminal_manual_ack: TerminalManualAckFn | None = None,
        ui_poll_seconds: float = 0.15,
    ) -> None:
        self.operator = str(operator or "operator")
        self.project_id = str(project_id or "live_smoke_h")
        self.fallback_to_terminal = bool(fallback_to_terminal)
        self.ui_poll_seconds = max(0.05, float(ui_poll_seconds))
        self._terminal_approval = terminal_approval
        self._terminal_manual_ack = terminal_manual_ack

        self._lock = threading.RLock()
        self._response_event = threading.Event()
        self._response_value: bool | None = None
        self._ui_connected = False
        self._cancelled = False
        self._gate_type = GATE_IDLE
        self._waiting = False
        self._run_status = RUN_STATUS_IDLE
        self._current_step_id = ""
        self._current_control_key = ""
        self._current_label = ""
        self._current_action = ""
        self._approval_history: list[RunwayApprovalHistoryEntry] = []
        self._runtime_logs: list[str] = []
        self._run_ok: bool | None = None
        self._stopped_reason = ""
        self._gate_ready = False
        self._gate_enabled = False
        self._gate_reason = ""
        self._expected_step_id = ""
        self._early_approval_rejections_count = 0
        self._approval_gate_safety_enabled = True
        self._execution_mode = ""
        self._last_auto_action = ""
        self._next_auto_action = ""
        self._auto_validation_state = ""
        self._auto_execution_timeline: list[dict[str, Any]] = []

    def set_execution_timeline(
        self,
        *,
        execution_mode: str = "",
        current_step_id: str = "",
        last_action: str = "",
        next_action: str = "",
        validation_state: str = "",
        timeline: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._lock:
            if execution_mode:
                self._execution_mode = str(execution_mode)
            if current_step_id:
                self._current_step_id = str(current_step_id)
            if last_action:
                self._last_auto_action = str(last_action)
            if next_action:
                self._next_auto_action = str(next_action)
            if validation_state:
                self._auto_validation_state = str(validation_state)
            if timeline is not None:
                self._auto_execution_timeline = list(timeline)

    def set_gate_readiness(
        self,
        *,
        ready: bool,
        enabled: bool,
        reason: str = "",
        step_id: str = "",
        control_key: str = "",
    ) -> None:
        with self._lock:
            self._gate_ready = bool(ready)
            self._gate_enabled = bool(enabled)
            self._gate_reason = str(reason or "")
            if step_id:
                self._expected_step_id = str(step_id)
            if control_key:
                self._current_control_key = str(control_key)

    def mark_ui_connected(self, connected: bool = True) -> None:
        with self._lock:
            self._ui_connected = bool(connected)
            if connected:
                self._log("Runtime Studio UI connected")
            else:
                self._log("Runtime Studio UI disconnected")

    def set_run_status(self, status: str, *, detail: str = "") -> None:
        with self._lock:
            self._run_status = status
            if detail:
                self._log(detail)

    def mark_run_finished(
        self,
        *,
        ok: bool,
        stopped_reason: str = "",
        current_step_id: str = "",
        last_action: str = "",
        next_action: str = "",
        validation_state: str = "",
        timeline: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._lock:
            self._run_ok = ok
            self._stopped_reason = stopped_reason
            self._run_status = RUN_STATUS_COMPLETED if ok else RUN_STATUS_FAILED
            self._waiting = False
            self._gate_type = GATE_COMPLETED if ok else GATE_IDLE
            if timeline is not None:
                self._auto_execution_timeline = list(timeline)
            if current_step_id:
                self._current_step_id = str(current_step_id)
            else:
                self._current_step_id = ""
            self._current_control_key = ""
            self._current_label = ""
            self._current_action = ""
            if last_action:
                self._last_auto_action = str(last_action)
            if next_action:
                self._next_auto_action = str(next_action)
            if validation_state:
                self._auto_validation_state = str(validation_state)
            elif ok:
                self._auto_validation_state = "pass"
            else:
                self._auto_validation_state = "fail"
            self._log(f"Run finished: {'PASS' if ok else 'FAIL'} {stopped_reason}".strip())

    def snapshot(self) -> RunwayLiveSmokeApprovalSnapshot:
        with self._lock:
            return RunwayLiveSmokeApprovalSnapshot(
                run_status=self._run_status,
                gate_type=self._gate_type,
                waiting=self._waiting,
                current_step_id=self._current_step_id,
                current_control_key=self._current_control_key,
                current_label=self._current_label,
                current_action=self._current_action,
                ui_connected=self._ui_connected,
                fallback_to_terminal=self.fallback_to_terminal,
                project_id=self.project_id,
                operator=self.operator,
                approval_history=[item.to_dict() for item in self._approval_history],
                runtime_logs=list(self._runtime_logs),
                run_ok=self._run_ok,
                stopped_reason=self._stopped_reason,
                cancelled=self._cancelled,
                gate_ready=self._gate_ready,
                gate_enabled=self._gate_enabled,
                gate_reason=self._gate_reason,
                expected_step_id=self._expected_step_id,
                early_approval_rejections_count=self._early_approval_rejections_count,
                approval_gate_safety_enabled=self._approval_gate_safety_enabled,
                execution_mode=self._execution_mode,
                last_auto_action=self._last_auto_action,
                next_auto_action=self._next_auto_action,
                auto_validation_state=self._auto_validation_state,
                auto_execution_timeline=list(self._auto_execution_timeline),
            )

    def approval_callback(self, control_key: str, step_id: str, label: str) -> bool:
        return self._wait_for_gate_response(
            gate_type=GATE_APPROVAL,
            run_status=RUN_STATUS_WAITING_APPROVAL,
            step_id=step_id,
            control_key=control_key,
            label=label,
            action="",
            history_event="approval_requested",
            ui_success_log="UI approved gate",
            terminal_fn=lambda: self._call_terminal_approval(control_key, step_id, label),
        )

    def manual_ack_callback(self, step_id: str, action: str) -> bool:
        return self._wait_for_gate_response(
            gate_type=GATE_MANUAL_HOLD,
            run_status=RUN_STATUS_WAITING_IMAGE_READY,
            step_id=step_id,
            control_key="",
            label="image ready",
            action=action,
            history_event="manual_hold_requested",
            ui_success_log="UI confirmed image ready",
            terminal_fn=lambda: self._call_terminal_manual_ack(step_id, action),
        )

    def submit_approve(self, *, operator: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self._cancelled:
                return self._action_result(False, "run already cancelled")
            if not self._waiting or self._gate_type != GATE_APPROVAL:
                return self._reject_early_approval("not waiting for approval")
            if self._approval_gate_safety_enabled and not self._gate_enabled:
                return self._reject_early_approval(
                    self._gate_reason or "gate not enabled — completion not verified"
                )
            self._response_value = True
            self._record_history(
                "approval_granted",
                step_id=self._current_step_id,
                control_key=self._current_control_key,
                label=self._current_label,
                granted=True,
                operator=operator or self.operator,
                detail="UI Approve",
            )
            self._log(f"Approve clicked for {self._current_control_key}")
            self._clear_waiting()
            self._response_event.set()
            return self._action_result(True, "approved")

    def submit_image_ready(self, *, operator: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self._cancelled:
                return self._action_result(False, "run already cancelled")
            if not self._waiting or self._gate_type != GATE_MANUAL_HOLD:
                return self._action_result(False, "not waiting for image ready")
            self._response_value = True
            self._record_history(
                "manual_hold_acknowledged",
                step_id=self._current_step_id,
                label="image ready",
                granted=True,
                operator=operator or self.operator,
                detail="UI Image Ready",
            )
            self._log("Image Ready clicked")
            self._clear_waiting()
            self._response_event.set()
            return self._action_result(True, "image_ready")

    def submit_cancel(self, *, operator: str | None = None, reason: str = "operator_cancel") -> dict[str, Any]:
        with self._lock:
            self._cancelled = True
            self._gate_type = GATE_CANCELLED
            self._run_status = RUN_STATUS_CANCELLED
            self._response_value = False
            self._record_history(
                "run_cancelled",
                step_id=self._current_step_id,
                control_key=self._current_control_key,
                label=self._current_label,
                granted=False,
                operator=operator or self.operator,
                detail=reason,
            )
            self._log(f"Cancel Run clicked ({reason})")
            self._clear_waiting()
            self._response_event.set()
            return self._action_result(True, "cancelled")

    def _wait_for_gate_response(
        self,
        *,
        gate_type: str,
        run_status: str,
        step_id: str,
        control_key: str,
        label: str,
        action: str,
        history_event: str,
        ui_success_log: str,
        terminal_fn: Callable[[], bool],
    ) -> bool:
        with self._lock:
            if self._cancelled:
                return False
            self._gate_type = gate_type
            self._waiting = True
            self._run_status = run_status
            self._current_step_id = step_id
            self._current_control_key = control_key
            self._current_label = label
            self._current_action = action
            self._expected_step_id = step_id
            self._response_event.clear()
            self._response_value = None
            self._record_history(
                history_event,
                step_id=step_id,
                control_key=control_key,
                label=label,
                detail=action or label,
            )
            if gate_type == GATE_APPROVAL:
                self._log(f"Waiting approval: {control_key} ({step_id})")
            else:
                self._log(f"Waiting image ready: {step_id}")

        granted = self._await_response(terminal_fn=terminal_fn)
        with self._lock:
            if granted:
                self._log(ui_success_log if self._ui_connected else "Terminal gate acknowledged")
            elif self._cancelled:
                self._log("Gate cancelled by operator")
            else:
                self._log("Gate denied or cancelled")
            if self._run_status not in {RUN_STATUS_CANCELLED, RUN_STATUS_FAILED, RUN_STATUS_COMPLETED}:
                self._run_status = RUN_STATUS_RUNNING
            return granted

    def _await_response(self, *, terminal_fn: Callable[[], bool]) -> bool:
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            with self._lock:
                if self._ui_connected:
                    break
            time.sleep(self.ui_poll_seconds)

        with self._lock:
            use_ui = self._ui_connected and not self._cancelled

        if use_ui:
            while True:
                if self._response_event.wait(timeout=self.ui_poll_seconds):
                    with self._lock:
                        return bool(self._response_value)
                with self._lock:
                    if self._cancelled:
                        return False

        if self.fallback_to_terminal:
            self._log("Falling back to terminal approval input")
            return bool(terminal_fn())

        with self._lock:
            self._cancelled = True
            self._run_status = RUN_STATUS_CANCELLED
        return False

    def _call_terminal_approval(self, control_key: str, step_id: str, label: str) -> bool:
        if self._terminal_approval is None:
            from content_brain.execution.runway_live_smoke_test import default_interactive_approval

            return default_interactive_approval(control_key, step_id, label)
        return self._terminal_approval(control_key, step_id, label)

    def _call_terminal_manual_ack(self, step_id: str, action: str) -> bool:
        if self._terminal_manual_ack is None:
            from content_brain.execution.runway_live_smoke_test import default_interactive_manual_ack

            return default_interactive_manual_ack(step_id, action)
        return self._terminal_manual_ack(step_id, action)

    def _clear_waiting(self) -> None:
        self._waiting = False
        self._gate_type = GATE_IDLE
        self._current_step_id = ""
        self._current_control_key = ""
        self._current_label = ""
        self._current_action = ""
        self._gate_ready = False
        self._gate_enabled = False
        self._gate_reason = ""
        self._expected_step_id = ""

    def _reject_early_approval(self, detail: str) -> dict[str, Any]:
        self._early_approval_rejections_count += 1
        self._record_history(
            "rejected_early_approval",
            step_id=self._current_step_id,
            control_key=self._current_control_key,
            label=self._current_label,
            granted=False,
            detail=detail,
        )
        self._log(f"Early approval rejected: {detail}")
        return self._action_result(False, detail)

    def _record_history(
        self,
        event: str,
        *,
        step_id: str = "",
        control_key: str = "",
        label: str = "",
        granted: bool | None = None,
        operator: str = "",
        detail: str = "",
    ) -> None:
        self._approval_history.append(
            RunwayApprovalHistoryEntry(
                event=event,
                step_id=step_id,
                control_key=control_key,
                label=label,
                granted=granted,
                operator=operator or self.operator,
                timestamp=_now(),
                detail=detail,
            )
        )

    def _log(self, message: str) -> None:
        line = f"[{_now()}] {message}"
        self._runtime_logs.append(line)
        if len(self._runtime_logs) > 500:
            self._runtime_logs = self._runtime_logs[-500:]

    def _action_result(self, ok: bool, message: str) -> dict[str, Any]:
        return {"ok": ok, "message": message, "snapshot": self.snapshot().to_dict()}


def build_ui_approval_callbacks(
    runtime: RunwayLiveSmokeApprovalRuntime,
) -> tuple[TerminalApprovalFn, TerminalManualAckFn]:
    return runtime.approval_callback, runtime.manual_ack_callback


__all__ = [
    "APPROVAL_RUNTIME_VERSION",
    "GATE_APPROVAL",
    "GATE_CANCELLED",
    "GATE_COMPLETED",
    "GATE_IDLE",
    "GATE_MANUAL_HOLD",
    "RUN_STATUS_CANCELLED",
    "RUN_STATUS_COMPLETED",
    "RUN_STATUS_FAILED",
    "RUN_STATUS_IDLE",
    "RUN_STATUS_RUNNING",
    "RUN_STATUS_WAITING_APPROVAL",
    "RUN_STATUS_WAITING_IMAGE_READY",
    "RunwayApprovalHistoryEntry",
    "RunwayLiveSmokeApprovalRuntime",
    "RunwayLiveSmokeApprovalSnapshot",
    "build_ui_approval_callbacks",
]
