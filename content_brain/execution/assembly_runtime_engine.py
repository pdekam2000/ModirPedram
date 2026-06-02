"""
Phase 11J-19 — Assembly runtime execution engine.

Orchestrates the assembly dry-run and gated real-execution lifecycle:

* builds an ``AssemblyPlan`` via ``AssemblyPlanBuilder`` (read-only),
* applies ``evaluate_assembly_run_request`` (eligibility policy),
* invokes ``AssemblyFFmpegExecutor`` in dry-run or gated real mode,
* mutates **only** the ``assembly_generation`` slot.

Dry-run: never invokes FFmpeg, never creates output files.
Real run: only when all policy gates pass and ``real_execution_allowed`` is set.
"""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.assembly_approval_guard import (
    AssemblyRunRequestContext,
    evaluate_assembly_approval_gate,
)
from content_brain.execution.assembly_ffmpeg_executor import (
    AssemblyFFmpegExecutor,
    EXECUTOR_VERSION,
    STATUS_COMPLETED as EXEC_STATUS_COMPLETED,
    STATUS_DRY_RUN,
)
from content_brain.execution.assembly_models import AssemblyPlan
from content_brain.execution.assembly_plan_builder import AssemblyPlanBuilder
from content_brain.execution.assembly_run_action_policy import (
    ACTION_RUN_REAL,
    evaluate_assembly_run_request,
)
from content_brain.execution.category_runtime_compat import (
    ASSEMBLY_PROVIDER,
    ensure_multi_category_shell,
    sync_assembly_category_aliases,
)
from content_brain.execution.operations_cancel import is_cancellation_requested
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY,
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore

ENGINE_VERSION = "11j19_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_RUNNING = "running"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def generate_assembly_run_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"assembly_run_{stamp}_{uuid.uuid4().hex[:6]}"


@dataclass
class AssemblyRuntimeRunResult:
    success: bool
    session_id: str
    status: str
    message: str = ""
    code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    assembly_slot: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    validation_status: str = "FAILED"
    assembly_mode: str | None = None
    subtitle_mode: str | None = None
    planned_steps: list[dict[str, Any]] = field(default_factory=list)
    expected_output: str | None = None
    input_summary: dict[str, int] = field(default_factory=dict)
    output_created: bool = False
    real_assembly_executed: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    video_mutated: bool = False
    voice_mutated: bool = False
    subtitle_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "session_id": self.session_id,
            "status": self.status,
            "message": self.message,
            "validation_status": self.validation_status,
            "assembly_mode": self.assembly_mode,
            "subtitle_mode": self.subtitle_mode,
            "planned_steps": list(self.planned_steps),
            "expected_output": self.expected_output,
            "input_summary": dict(self.input_summary),
            "output_created": bool(self.output_created),
            "real_assembly_executed": bool(self.real_assembly_executed),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "video_mutated": bool(self.video_mutated),
            "voice_mutated": bool(self.voice_mutated),
            "subtitle_mutated": bool(self.subtitle_mutated),
        }
        if not self.success:
            payload["code"] = self.code
            if self.reject_reasons:
                payload["reject_reasons"] = list(self.reject_reasons)
        if self.assembly_slot is not None:
            payload["assembly_slot"] = self.assembly_slot
        if self.guard_result is not None:
            payload["guard_result"] = self.guard_result
        return payload


class AssemblyRuntimeEngine:
    """Execute the assembly dry-run lifecycle for a session (no FFmpeg)."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        project_root: str | Path | None = None,
    ) -> None:
        self.store = store
        self.project_root = Path(project_root or store.project_root).resolve()
        self.builder = AssemblyPlanBuilder(self.project_root)
        self.executor = AssemblyFFmpegExecutor(dry_run=True)
        self._session_locks: dict[str, threading.Lock] = {}
        self._lock_guard = threading.Lock()

    def _session_lock(self, session_id: str) -> threading.Lock:
        with self._lock_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            return self._session_locks[session_id]

    def run(
        self,
        session_id: str,
        *,
        dry_run: bool = True,
        confirm_real_assembly: bool = False,
        overwrite: bool = False,
        timeout_seconds: int = 120,
        triggered_by: str = "operator",
        reason: str = "",
        max_output_bytes: int | None = None,
    ) -> AssemblyRuntimeRunResult:
        with self._session_lock(session_id):
            return self._run_locked(
                session_id,
                dry_run=dry_run,
                confirm_real_assembly=confirm_real_assembly,
                overwrite=overwrite,
                timeout_seconds=timeout_seconds,
                triggered_by=triggered_by,
                reason=reason,
                max_output_bytes=max_output_bytes,
            )

    # ------------------------------------------------------------------ #

    def _run_locked(
        self,
        session_id: str,
        *,
        dry_run: bool,
        confirm_real_assembly: bool,
        overwrite: bool,
        timeout_seconds: int,
        triggered_by: str,
        reason: str,
        max_output_bytes: int | None = None,
    ) -> AssemblyRuntimeRunResult:
        session = self.store.load_session(session_id)

        runtime = ensure_multi_category_shell(dict(_dict(session.get("execution_runtime"))))
        session["execution_runtime"] = runtime

        # Snapshot upstream slots AFTER shell normalization so any mutation
        # we detect is attributable to this run (the builder is read-only).
        video_before = self._slot_snapshot(runtime, CATEGORY_VIDEO)
        voice_before = self._slot_snapshot(runtime, CATEGORY_VOICE)
        subtitle_before = self._slot_snapshot(runtime, CATEGORY_SUBTITLE_GENERATION)

        assembly_slot = self._read_assembly_slot(runtime)

        plan = self.builder.build(session)

        policy = evaluate_assembly_run_request(
            session,
            assembly_slot,
            plan,
            session_id=session_id,
            dry_run=dry_run,
            confirm_real_assembly=confirm_real_assembly,
            overwrite=overwrite,
            timeout_seconds=timeout_seconds,
            triggered_by=triggered_by,
            project_root=str(self.project_root),
        )
        if not policy.allowed:
            assembly_slot = self._set_failed(
                assembly_slot,
                code=policy.code,
                reasons=policy.reject_reasons,
                plan=plan,
            )
            assembly_slot = self._refresh_approval_gate(
                assembly_slot, session=session, plan=plan, dry_run=dry_run
            )
            runtime = self._persist_assembly_slot(session, runtime, assembly_slot)
            self.store.save_session(session, overwrite=True)
            return self._result(
                success=False,
                session_id=session_id,
                status=STATUS_REJECTED,
                message=policy.message,
                code=policy.code,
                reject_reasons=policy.reject_reasons,
                assembly_slot=assembly_slot,
                guard_result=policy.guard_result,
                plan=plan,
                runtime=runtime,
                video_before=video_before,
                voice_before=voice_before,
                subtitle_before=subtitle_before,
            )

        run_id = generate_assembly_run_id()
        started_at = _now()
        is_real_run = policy.action == ACTION_RUN_REAL and dry_run is False
        assembly_slot = self._set_running(
            assembly_slot,
            run_id=run_id,
            triggered_by=triggered_by,
            overwrite=overwrite,
            timeout_seconds=timeout_seconds,
            started_at=started_at,
            dry_run=not is_real_run,
            reason=reason,
        )
        runtime = self._persist_assembly_slot(session, runtime, assembly_slot)
        self.store.save_session(session, overwrite=True)

        if is_cancellation_requested(session):
            assembly_slot = self._set_failed(
                assembly_slot,
                code="ASSEMBLY_CANCELLED",
                reasons=["Cancellation requested before assembly dry-run."],
                plan=plan,
                status=STATUS_CANCELLED,
            )
            runtime = self._persist_assembly_slot(session, runtime, assembly_slot)
            self.store.save_session(session, overwrite=True)
            return self._result(
                success=False,
                session_id=session_id,
                status=STATUS_CANCELLED,
                message="Assembly dry-run cancelled.",
                code="ASSEMBLY_CANCELLED",
                reject_reasons=["Cancellation requested before assembly dry-run."],
                assembly_slot=assembly_slot,
                guard_result=policy.guard_result,
                plan=plan,
                runtime=runtime,
                video_before=video_before,
                voice_before=voice_before,
                subtitle_before=subtitle_before,
            )

        exec_result = self.executor.execute(
            plan,
            cancel_check=lambda: is_cancellation_requested(session),
            overwrite=overwrite,
            timeout_seconds=timeout_seconds,
            dry_run=not is_real_run,
            real_execution_allowed=is_real_run and policy.allowed,
            max_output_bytes=max_output_bytes,
        )

        completed_at = _now()
        if is_real_run:
            success = exec_result.status == EXEC_STATUS_COMPLETED and not exec_result.errors
        else:
            success = exec_result.status == STATUS_DRY_RUN and not exec_result.errors

        assembly_slot = self._set_completed(
            assembly_slot,
            exec_result=exec_result,
            plan=plan,
            started_at=started_at,
            completed_at=completed_at,
            success=success,
            is_real_run=is_real_run,
        )
        assembly_slot = self._refresh_approval_gate(
            assembly_slot,
            session=session,
            plan=plan,
            dry_run=not is_real_run,
            real_assembly_requested=bool(assembly_slot.get("real_assembly_requested")),
        )
        runtime = self._persist_assembly_slot(
            session,
            runtime,
            assembly_slot,
            reason=reason,
            triggered_by=triggered_by,
            is_real_run=is_real_run,
            exec_result=exec_result,
        )
        self.store.save_session(session, overwrite=True)

        if is_real_run:
            message = "Real assembly completed." if success else "Real assembly failed."
        else:
            message = "Assembly dry-run completed." if success else "Assembly dry-run failed."

        return self._result(
            success=success,
            session_id=session_id,
            status=STATUS_COMPLETED if success else STATUS_FAILED,
            message=message,
            code=None if success else self._first_error_code(exec_result),
            reject_reasons=[] if success else self._error_messages(exec_result),
            assembly_slot=assembly_slot,
            guard_result=policy.guard_result,
            plan=plan,
            runtime=runtime,
            video_before=video_before,
            voice_before=voice_before,
            subtitle_before=subtitle_before,
            exec_result=exec_result,
            is_real_run=is_real_run,
        )

    # ------------------------------------------------------------------ #
    # Approval gate (read-only, 11J-12)
    # ------------------------------------------------------------------ #

    def _refresh_approval_gate(
        self,
        assembly_slot: dict[str, Any],
        *,
        session: dict[str, Any],
        plan: Any,
        dry_run: bool,
        real_assembly_requested: bool = False,
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        slot["approval"] = evaluate_assembly_approval_gate(
            slot,
            plan if isinstance(plan, AssemblyPlan) else None,
            AssemblyRunRequestContext(
                dry_run=dry_run,
                real_assembly_requested=real_assembly_requested
                or bool(slot.get("real_assembly_requested")),
            ),
            session=session,
            project_root=self.project_root,
        )
        return slot

    # ------------------------------------------------------------------ #
    # Slot helpers (assembly_generation only)
    # ------------------------------------------------------------------ #

    def _read_assembly_slot(self, runtime: dict[str, Any]) -> dict[str, Any]:
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        sync_assembly_category_aliases(category_runtime)
        slot = (
            category_runtime.get(CATEGORY_ASSEMBLY_GENERATION)
            or category_runtime.get(CATEGORY_ASSEMBLY)
        )
        return dict(_dict(slot))

    def _slot_snapshot(self, runtime: dict[str, Any], category: str) -> dict[str, Any]:
        category_runtime = _dict(runtime.get("category_runtime"))
        return deepcopy(_dict(category_runtime.get(category)))

    def _persist_assembly_slot(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        assembly_slot: dict[str, Any],
        *,
        reason: str = "",
        triggered_by: str = "operator",
        is_real_run: bool = False,
        exec_result: Any | None = None,
    ) -> dict[str, Any]:
        category_runtime = dict(_dict(runtime.get("category_runtime")))

        # Preserve upstream slots verbatim.
        video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
        subtitle_slot = dict(_dict(category_runtime.get(CATEGORY_SUBTITLE_GENERATION)))

        category_runtime[CATEGORY_ASSEMBLY_GENERATION] = assembly_slot
        category_runtime[CATEGORY_ASSEMBLY] = assembly_slot
        category_runtime[CATEGORY_VIDEO] = video_slot
        category_runtime[CATEGORY_VOICE] = voice_slot
        category_runtime[CATEGORY_SUBTITLE_GENERATION] = subtitle_slot
        runtime["category_runtime"] = category_runtime

        operations = dict(_dict(runtime.get("operations")))
        assembly_exec = dict(_dict(operations.get("assembly_execution")))
        assembly_exec.update(
            {
                "engine_version": ENGINE_VERSION,
                "executor_version": EXECUTOR_VERSION,
                "last_status": assembly_slot.get("status"),
                "last_run_id": _dict(assembly_slot.get("assembly_run")).get("run_id"),
                "assembly_executed": bool(assembly_slot.get("executed")),
                "real_assembly_executed": bool(assembly_slot.get("real_assembly_executed")),
                "output_created": bool(assembly_slot.get("output_created")),
                "triggered_by": triggered_by,
                "reason": reason or assembly_exec.get("reason"),
            }
        )
        if exec_result is not None:
            assembly_exec["output_size_bytes"] = getattr(exec_result, "output_size", None)
            assembly_exec["execution_time_seconds"] = getattr(
                exec_result, "execution_time_seconds", None
            )
            assembly_exec["manifest_path"] = getattr(exec_result, "manifest_path", None)
        if is_real_run:
            assembly_exec["last_real_run_at"] = assembly_slot.get("completed_at")
        operations["assembly_execution"] = assembly_exec
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return runtime

    def _set_running(
        self,
        assembly_slot: dict[str, Any],
        *,
        run_id: str,
        triggered_by: str,
        overwrite: bool,
        timeout_seconds: int,
        started_at: str,
        dry_run: bool = True,
        reason: str = "",
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        slot["status"] = STATUS_RUNNING
        slot["provider"] = ASSEMBLY_PROVIDER
        slot["executed"] = False
        slot["dry_run"] = bool(dry_run)
        slot["real_assembly_executed"] = False
        slot["output_created"] = False
        slot["error"] = None
        slot["started_at"] = started_at
        slot["updated_at"] = started_at
        slot["assembly_run"] = {
            "run_id": run_id,
            "triggered_by": triggered_by,
            "reason": reason,
            "overwrite": bool(overwrite),
            "timeout_seconds": int(timeout_seconds),
            "dry_run": bool(dry_run),
            "started_at": started_at,
        }
        return slot

    def _set_completed(
        self,
        assembly_slot: dict[str, Any],
        *,
        exec_result: Any,
        plan: Any,
        started_at: str,
        completed_at: str,
        success: bool,
        is_real_run: bool = False,
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        slot["status"] = STATUS_COMPLETED if success else STATUS_FAILED
        slot["provider"] = ASSEMBLY_PROVIDER
        slot["validation_status"] = exec_result.validation_status or getattr(
            plan, "validation_status", None
        )
        slot["assembly_mode"] = getattr(plan, "assembly_mode", None)
        slot["subtitle_mode"] = getattr(plan, "subtitle_mode", None)
        slot["expected_output"] = exec_result.expected_output
        slot["planned_steps"] = list(exec_result.planned_steps)
        slot["input_summary"] = dict(exec_result.input_counts)
        slot["output_summary"] = {
            "expected_output": exec_result.expected_output,
            "output_file": exec_result.output_file,
            "output_created": bool(exec_result.output_created),
            "output_size": exec_result.output_size,
            "manifest_path": getattr(exec_result, "manifest_path", None),
        }
        slot["warnings"] = list(exec_result.warnings)
        slot["errors"] = list(exec_result.errors)
        slot["error"] = self._first_error_code(exec_result) if exec_result.errors else None
        slot["executed"] = bool(success and is_real_run)
        slot["dry_run"] = not is_real_run
        if not is_real_run and success:
            slot["dry_run_completed"] = True
        slot["real_assembly_executed"] = bool(success and is_real_run and exec_result.real_assembly_executed)
        slot["output_created"] = bool(success and exec_result.output_created)
        slot["completed_at"] = completed_at
        slot["updated_at"] = completed_at
        slot["execution_time_seconds"] = exec_result.execution_time_seconds

        run = dict(_dict(slot.get("assembly_run")))
        run["completed_at"] = completed_at
        run["status"] = slot["status"]
        run["dry_run"] = not is_real_run
        slot["assembly_run"] = run
        return slot

    def _set_failed(
        self,
        assembly_slot: dict[str, Any],
        *,
        code: str | None,
        reasons: list[str],
        plan: Any,
        status: str = STATUS_FAILED,
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        slot["status"] = status
        slot["provider"] = ASSEMBLY_PROVIDER
        slot["validation_status"] = getattr(plan, "validation_status", None) or slot.get(
            "validation_status"
        )
        slot["executed"] = False
        slot["dry_run"] = True
        slot["real_assembly_executed"] = False
        slot["output_created"] = False
        slot["error"] = code
        slot["reject_reasons"] = list(reasons)
        slot["updated_at"] = _now()
        return slot

    # ------------------------------------------------------------------ #
    # Result assembly + mutation detection
    # ------------------------------------------------------------------ #

    def _result(
        self,
        *,
        success: bool,
        session_id: str,
        status: str,
        message: str,
        code: str | None,
        reject_reasons: list[str],
        assembly_slot: dict[str, Any],
        guard_result: dict[str, Any] | None,
        plan: Any,
        runtime: dict[str, Any],
        video_before: dict[str, Any],
        voice_before: dict[str, Any],
        subtitle_before: dict[str, Any],
        exec_result: Any | None = None,
        is_real_run: bool = False,
    ) -> AssemblyRuntimeRunResult:
        video_after = self._slot_snapshot(runtime, CATEGORY_VIDEO)
        voice_after = self._slot_snapshot(runtime, CATEGORY_VOICE)
        subtitle_after = self._slot_snapshot(runtime, CATEGORY_SUBTITLE_GENERATION)

        planned_steps: list[dict[str, Any]] = []
        expected_output = getattr(plan, "expected_output", None)
        input_summary: dict[str, int] = {}
        warnings: list[str] = list(getattr(plan, "warnings", []) or [])
        errors: list[dict[str, Any]] = []
        if exec_result is not None:
            planned_steps = list(exec_result.planned_steps)
            expected_output = exec_result.expected_output or expected_output
            input_summary = dict(exec_result.input_counts)
            warnings = list(exec_result.warnings)
            errors = list(exec_result.errors)

        output_created = False
        real_assembly_executed = False
        if exec_result is not None:
            output_created = bool(exec_result.output_created)
            real_assembly_executed = bool(exec_result.real_assembly_executed)

        return AssemblyRuntimeRunResult(
            success=success,
            session_id=session_id,
            status=status,
            message=message,
            code=code,
            reject_reasons=list(reject_reasons),
            assembly_slot=assembly_slot,
            guard_result=guard_result,
            validation_status=getattr(plan, "validation_status", None) or "FAILED",
            assembly_mode=getattr(plan, "assembly_mode", None),
            subtitle_mode=getattr(plan, "subtitle_mode", None),
            planned_steps=planned_steps,
            expected_output=expected_output,
            input_summary=input_summary,
            output_created=output_created,
            real_assembly_executed=real_assembly_executed,
            warnings=warnings,
            errors=errors,
            video_mutated=video_after != video_before,
            voice_mutated=voice_after != voice_before,
            subtitle_mutated=subtitle_after != subtitle_before,
        )

    @staticmethod
    def _first_error_code(exec_result: Any) -> str | None:
        errors = exec_result.get("errors") if isinstance(exec_result, dict) else getattr(
            exec_result, "errors", None
        )
        for err in errors or []:
            if isinstance(err, dict) and err.get("code"):
                return str(err["code"])
        return None

    @staticmethod
    def _error_messages(exec_result: Any) -> list[str]:
        messages: list[str] = []
        for err in getattr(exec_result, "errors", None) or []:
            if isinstance(err, dict):
                messages.append(str(err.get("message") or err.get("code") or "assembly error"))
        return messages


__all__ = [
    "ENGINE_VERSION",
    "AssemblyRuntimeRunResult",
    "AssemblyRuntimeEngine",
    "generate_assembly_run_id",
]
