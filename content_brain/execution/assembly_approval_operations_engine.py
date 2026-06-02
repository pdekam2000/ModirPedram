"""
Phase 11J-14 — assembly approval write operations (approve/reject/expire/reset).

Mutates only assembly_generation.approval metadata and audit logs.
Never imports or calls FFmpeg / AssemblyFFmpegExecutor real execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import uuid

from content_brain.execution.assembly_approval_action_policy import (
    ACTION_APPROVE,
    ACTION_EXPIRE,
    ACTION_REJECT,
    ACTION_RESET,
    evaluate_assembly_approval_action,
)
from content_brain.execution.assembly_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_APPROVAL_REJECTED,
    GATE_VERSION,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_REJECTED,
    TIMESTAMP_FORMAT,
    AssemblyRunRequestContext,
    can_run_real_assembly,
    evaluate_assembly_approval_gate,
)
from content_brain.execution.assembly_plan_builder import AssemblyPlanBuilder
from content_brain.execution.assembly_preflight_runtime_slot import apply_assembly_preflight_dry_run
from content_brain.execution.category_runtime_compat import (
    ensure_multi_category_shell,
    sync_assembly_category_aliases,
)
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY_GENERATION,
    CATEGORY_SUBTITLE_GENERATION,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
)
from content_brain.execution.session_store import ExecutionSessionStore

ENGINE_VERSION = "11j14_v1"
AUDIT_MAX_EVENTS = 50
DEFAULT_TTL_MINUTES = 30
MIN_TTL_MINUTES = 15
MAX_TTL_MINUTES = 24 * 60
CATEGORY_NAME = "assembly_generation"

AUDIT_EVENT_TYPES = {
    ACTION_APPROVE: "assembly_approval_approved",
    ACTION_REJECT: "assembly_approval_rejected",
    ACTION_EXPIRE: "assembly_approval_expired",
    ACTION_RESET: "assembly_approval_reset",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_assembly_approval_audit_event_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"asm_appr_evt_{stamp}_{uuid.uuid4().hex[:6]}"


def _default_reason(action: str) -> str:
    defaults = {
        ACTION_APPROVE: "Assembly approved for real execution (metadata only).",
        ACTION_REJECT: "Assembly rejected by operator.",
        ACTION_EXPIRE: "Assembly approval expired by operator.",
        ACTION_RESET: "Assembly approval reset by operator.",
    }
    return defaults.get(action, "Assembly approval action.")


def build_assembly_approval_operations_mirror(
    assembly_slot: dict[str, Any],
    *,
    real_assembly_requested: bool,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    approval = _dict(assembly_slot.get("approval"))
    return {
        "gate_version": GATE_VERSION,
        "evaluated_at": evaluated_at,
        "approval_required": approval.get("approval_required"),
        "approval_state": approval.get("approval_state"),
        "real_assembly_requested": real_assembly_requested,
        "assembly_eligible": approval.get("assembly_eligible"),
        "blocked_reasons": list(approval.get("assembly_blocked_reasons") or []),
    }


@dataclass
class AssemblyApprovalActionResult:
    success: bool
    session_id: str
    action: str
    message: str = ""
    code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    assembly_slot: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    panel_excerpt: dict[str, Any] | None = None
    audit_event: dict[str, Any] | None = None
    real_assembly_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "session_id": self.session_id,
            "action": self.action,
            "message": self.message,
            "real_assembly_executed": self.real_assembly_executed,
        }
        if not self.success:
            payload["code"] = self.code
            if self.reject_reasons:
                payload["reject_reasons"] = self.reject_reasons
        if self.assembly_slot is not None:
            payload["assembly_slot"] = self.assembly_slot
        if self.guard_result is not None:
            payload["guard_result"] = self.guard_result
        if self.panel_excerpt is not None:
            payload["panel_excerpt"] = self.panel_excerpt
        if self.audit_event is not None:
            payload["audit_event"] = self.audit_event
        return payload


class AssemblyApprovalOperationsEngine:
    """Apply assembly approval write actions — metadata and audit only."""

    def __init__(self, store: ExecutionSessionStore, *, project_root: str | Path | None = None):
        self.store = store
        self.project_root = project_root or store.project_root
        self.builder = AssemblyPlanBuilder(self.project_root)

    def approve(
        self,
        session_id: str,
        *,
        request_real_assembly: bool,
        reason: str = "",
        approved_by: str = "local_user",
        ttl_minutes: int | None = None,
    ) -> AssemblyApprovalActionResult:
        return self._run(
            session_id,
            ACTION_APPROVE,
            actor=approved_by,
            reason=reason,
            request_real_assembly=request_real_assembly,
            ttl_minutes=ttl_minutes,
        )

    def reject(
        self,
        session_id: str,
        *,
        reason: str = "",
        rejected_by: str = "local_user",
    ) -> AssemblyApprovalActionResult:
        return self._run(session_id, ACTION_REJECT, actor=rejected_by, reason=reason)

    def expire(
        self,
        session_id: str,
        *,
        reason: str = "",
        expired_by: str = "local_user",
    ) -> AssemblyApprovalActionResult:
        return self._run(session_id, ACTION_EXPIRE, actor=expired_by, reason=reason)

    def reset_approval(
        self,
        session_id: str,
        *,
        reason: str = "",
        reset_by: str = "local_user",
    ) -> AssemblyApprovalActionResult:
        return self._run(session_id, ACTION_RESET, actor=reset_by, reason=reason)

    def _run(
        self,
        session_id: str,
        action: str,
        *,
        actor: str,
        reason: str = "",
        request_real_assembly: bool = False,
        ttl_minutes: int | None = None,
    ) -> AssemblyApprovalActionResult:
        session = self.store.load_session(session_id)
        upstream_before = self._upstream_slots_snapshot(session)
        runtime, assembly_slot, plan, previous_state = self._prepare_assembly_context(session)

        policy = evaluate_assembly_approval_action(
            session,
            assembly_slot,
            plan,
            action,
            request_real_assembly=request_real_assembly if action == ACTION_APPROVE else bool(
                assembly_slot.get("real_assembly_requested")
            ),
            runtime=runtime,
        )
        if not policy.allowed:
            audit = self._append_audit(
                session,
                runtime,
                action=action,
                actor=actor,
                reason=reason or _default_reason(action),
                previous_state=previous_state,
                new_state=previous_state,
                allowed=False,
                blocked_reasons=policy.reject_reasons,
                assembly_eligible=False,
                assembly_slot=assembly_slot,
            )
            self.store.save_session(session, overwrite=True)
            request_ctx = AssemblyRunRequestContext(
                dry_run=False,
                real_assembly_requested=bool(assembly_slot.get("real_assembly_requested")),
            )
            return AssemblyApprovalActionResult(
                success=False,
                session_id=session_id,
                action=action,
                message=policy.message,
                code=policy.code,
                reject_reasons=policy.reject_reasons,
                assembly_slot=assembly_slot,
                guard_result=can_run_real_assembly(
                    assembly_slot, plan, request_ctx, session=session, project_root=self.project_root
                ).to_dict(),
                panel_excerpt=self._panel_excerpt(assembly_slot, runtime),
                audit_event=audit,
                real_assembly_executed=False,
            )

        if action == ACTION_APPROVE:
            assembly_slot = self._mutate_approve(
                assembly_slot,
                session,
                plan,
                actor=actor,
                reason=reason,
                request_real_assembly=request_real_assembly,
                ttl_minutes=ttl_minutes,
            )
        elif action == ACTION_REJECT:
            assembly_slot = self._mutate_reject(assembly_slot, session, plan, reason=reason)
        elif action == ACTION_EXPIRE:
            assembly_slot = self._mutate_expire(assembly_slot, session, plan, reason=reason)
        elif action == ACTION_RESET:
            assembly_slot = self._mutate_reset(assembly_slot, session, plan)

        runtime = self._persist_assembly_slot(session, runtime, assembly_slot)
        new_state = str(_dict(assembly_slot.get("approval")).get("approval_state") or previous_state)
        request_ctx = AssemblyRunRequestContext(
            dry_run=False,
            real_assembly_requested=bool(assembly_slot.get("real_assembly_requested")),
        )
        guard = can_run_real_assembly(
            assembly_slot, plan, request_ctx, session=session, project_root=self.project_root
        )
        approval = _dict(assembly_slot.get("approval"))
        assembly_eligible = bool(approval.get("assembly_eligible"))

        audit = self._append_audit(
            session,
            runtime,
            action=action,
            actor=actor,
            reason=reason or _default_reason(action),
            previous_state=previous_state,
            new_state=new_state,
            allowed=True,
            blocked_reasons=list(approval.get("assembly_blocked_reasons") or []),
            assembly_eligible=assembly_eligible,
            assembly_slot=assembly_slot,
        )

        session["execution_runtime"] = runtime
        session["updated_at"] = _now_utc()
        self.store.save_session(session, overwrite=True)

        upstream_after = self._upstream_slots_snapshot(session)
        if not self._upstream_slots_preserved(upstream_before, upstream_after):
            raise RuntimeError("Upstream media slots were mutated — aborting.")

        return AssemblyApprovalActionResult(
            success=True,
            session_id=session_id,
            action=action,
            message=f"Assembly approval {action} completed (metadata only — no FFmpeg executed).",
            assembly_slot=assembly_slot,
            guard_result=guard.to_dict(),
            panel_excerpt=self._panel_excerpt(assembly_slot, runtime),
            audit_event=audit,
            real_assembly_executed=False,
        )

    def _prepare_assembly_context(
        self,
        session: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], Any, str]:
        runtime = dict(_dict(session.get("execution_runtime")))
        runtime = ensure_multi_category_shell(runtime)
        runtime = apply_assembly_preflight_dry_run(session, runtime)
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        sync_assembly_category_aliases(category_runtime)
        assembly_slot = dict(_dict(category_runtime.get(CATEGORY_ASSEMBLY_GENERATION)))
        previous_state = str(_dict(assembly_slot.get("approval")).get("approval_state") or "not_required")
        session["execution_runtime"] = runtime
        plan = self.builder.build(session)
        return runtime, assembly_slot, plan, previous_state

    def _persist_assembly_slot(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        assembly_slot: dict[str, Any],
    ) -> dict[str, Any]:
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
        subtitle_slot = dict(_dict(category_runtime.get(CATEGORY_SUBTITLE_GENERATION)))
        category_runtime[CATEGORY_ASSEMBLY_GENERATION] = assembly_slot
        category_runtime[CATEGORY_VIDEO] = video_slot
        category_runtime[CATEGORY_VOICE] = voice_slot
        category_runtime[CATEGORY_SUBTITLE_GENERATION] = subtitle_slot
        sync_assembly_category_aliases(category_runtime)
        runtime["category_runtime"] = category_runtime

        evaluated_at = _now_utc()
        operations = dict(_dict(runtime.get("operations")))
        operations["assembly_approval_gate"] = build_assembly_approval_operations_mirror(
            assembly_slot,
            real_assembly_requested=bool(assembly_slot.get("real_assembly_requested")),
            evaluated_at=evaluated_at,
        )
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return runtime

    def _request_context(self, assembly_slot: dict[str, Any]) -> AssemblyRunRequestContext:
        return AssemblyRunRequestContext(
            dry_run=False,
            real_assembly_requested=bool(assembly_slot.get("real_assembly_requested")),
        )

    def _mutate_approve(
        self,
        assembly_slot: dict[str, Any],
        session: dict[str, Any],
        plan: Any,
        *,
        actor: str,
        reason: str,
        request_real_assembly: bool,
        ttl_minutes: int | None,
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        if request_real_assembly:
            slot["real_assembly_requested"] = True
        ttl = DEFAULT_TTL_MINUTES if ttl_minutes is None else int(ttl_minutes)
        ttl = max(MIN_TTL_MINUTES, min(MAX_TTL_MINUTES, ttl))
        now_local = datetime.now()
        approved_at = now_local.strftime(TIMESTAMP_FORMAT)
        expires_at = (now_local + timedelta(minutes=ttl)).strftime(TIMESTAMP_FORMAT)

        request_ctx = self._request_context(slot)
        gate_preview = evaluate_assembly_approval_gate(
            slot, plan, request_ctx, session=session, project_root=self.project_root
        )
        approval = dict(gate_preview)
        approval.update(
            {
                "gate_version": GATE_VERSION,
                "approval_required": True,
                "approval_state": STATE_APPROVED,
                "approved_by": actor or "local_user",
                "approved_at": approved_at,
                "approval_reason": reason or _default_reason(ACTION_APPROVE),
                "approval_expires_at": expires_at,
            }
        )
        slot["approval"] = approval
        slot["approval"] = evaluate_assembly_approval_gate(
            slot, plan, request_ctx, session=session, project_root=self.project_root
        )
        slot["approval"]["approval_state"] = STATE_APPROVED
        slot["approval"]["approved_by"] = actor or "local_user"
        slot["approval"]["approved_at"] = approved_at
        slot["approval"]["approval_reason"] = reason or _default_reason(ACTION_APPROVE)
        slot["approval"]["approval_expires_at"] = expires_at
        guard = can_run_real_assembly(slot, plan, request_ctx, session=session, project_root=self.project_root)
        slot["approval"]["assembly_eligible"] = guard.assembly_eligible
        slot["approval"]["assembly_blocked_reasons"] = guard.block_codes if guard.blocked else []
        return slot

    def _mutate_reject(
        self,
        assembly_slot: dict[str, Any],
        session: dict[str, Any],
        plan: Any,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        request_ctx = self._request_context(slot)
        gate_preview = evaluate_assembly_approval_gate(
            slot, plan, request_ctx, session=session, project_root=self.project_root
        )
        approval = dict(gate_preview)
        approval.update(
            {
                "approval_required": True,
                "approval_state": STATE_REJECTED,
                "approved_by": None,
                "approved_at": None,
                "approval_expires_at": None,
                "approval_reason": reason or _default_reason(ACTION_REJECT),
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_APPROVAL_REJECTED],
            }
        )
        slot["approval"] = approval
        return slot

    def _mutate_expire(
        self,
        assembly_slot: dict[str, Any],
        session: dict[str, Any],
        plan: Any,
        *,
        reason: str,
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        request_ctx = self._request_context(slot)
        gate_preview = evaluate_assembly_approval_gate(
            slot, plan, request_ctx, session=session, project_root=self.project_root
        )
        approval = dict(gate_preview)
        approval.update(
            {
                "approval_state": STATE_EXPIRED,
                "approval_expires_at": datetime.now().strftime(TIMESTAMP_FORMAT),
                "approval_reason": reason or _default_reason(ACTION_EXPIRE),
                "assembly_eligible": False,
                "assembly_blocked_reasons": [BLOCK_APPROVAL_EXPIRED],
            }
        )
        slot["approval"] = approval
        return slot

    def _mutate_reset(
        self,
        assembly_slot: dict[str, Any],
        session: dict[str, Any],
        plan: Any,
    ) -> dict[str, Any]:
        slot = dict(assembly_slot)
        existing = dict(_dict(slot.get("approval")))
        existing.update(
            {
                "approved_by": None,
                "approved_at": None,
                "approval_reason": None,
                "approval_expires_at": None,
            }
        )
        slot["approval"] = existing
        request_ctx = self._request_context(slot)
        slot["approval"] = evaluate_assembly_approval_gate(
            slot, plan, request_ctx, session=session, project_root=self.project_root
        )
        return slot

    def _append_audit(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        *,
        action: str,
        actor: str,
        reason: str,
        previous_state: str,
        new_state: str,
        allowed: bool,
        blocked_reasons: list[str],
        assembly_eligible: bool,
        assembly_slot: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = ExecutionSessionStore.extract_session_id(session)
        approval = _dict(assembly_slot.get("approval"))
        event = {
            "event_id": generate_assembly_approval_audit_event_id(),
            "event_type": AUDIT_EVENT_TYPES.get(action, action),
            "session_id": session_id,
            "category": CATEGORY_NAME,
            "actor": actor or "local_user",
            "reason": reason,
            "timestamp": _now_utc(),
            "previous_state": previous_state,
            "new_state": new_state,
            "blocked_reasons": list(blocked_reasons),
            "assembly_eligible": assembly_eligible,
            "real_assembly_executed": False,
            "allowed": allowed,
            "metadata": {
                "engine_version": ENGINE_VERSION,
                "gate_version": GATE_VERSION,
                "validation_status": assembly_slot.get("validation_status"),
                "expected_output": assembly_slot.get("expected_output"),
                "real_assembly_requested": bool(assembly_slot.get("real_assembly_requested")),
            },
        }
        operations = dict(_dict(runtime.get("operations")))
        audit_log = list(operations.get("assembly_approval_audit") or [])
        audit_log.append(event)
        if len(audit_log) > AUDIT_MAX_EVENTS:
            audit_log = audit_log[-AUDIT_MAX_EVENTS:]
        operations["assembly_approval_audit"] = audit_log
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return event

    @staticmethod
    def _upstream_slots_snapshot(session: dict[str, Any]) -> dict[str, Any]:
        runtime = _dict(session.get("execution_runtime"))
        category_runtime = _dict(runtime.get("category_runtime"))
        return {
            CATEGORY_VIDEO: dict(_dict(category_runtime.get(CATEGORY_VIDEO))),
            CATEGORY_VOICE: dict(_dict(category_runtime.get(CATEGORY_VOICE))),
            CATEGORY_SUBTITLE_GENERATION: dict(_dict(category_runtime.get(CATEGORY_SUBTITLE_GENERATION))),
        }

    @staticmethod
    def _upstream_slots_preserved(before: dict[str, Any], after: dict[str, Any]) -> bool:
        keys = ("state", "provider", "status", "started_at", "completed_at")
        for category in before:
            before_slot = _dict(before.get(category))
            after_slot = _dict(after.get(category))
            if not all(before_slot.get(key) == after_slot.get(key) for key in keys):
                return False
        return True

    @staticmethod
    def _panel_excerpt(assembly_slot: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
        approval = _dict(assembly_slot.get("approval"))
        operations = _dict(runtime.get("operations"))
        return {
            "assembly_generation_status": assembly_slot.get("status"),
            "assembly_generation_executed": assembly_slot.get("executed"),
            "assembly_approval_gate": operations.get("assembly_approval_gate"),
            "approval_state": approval.get("approval_state"),
            "assembly_eligible": approval.get("assembly_eligible"),
            "blocked_reasons": list(approval.get("assembly_blocked_reasons") or []),
        }


__all__ = [
    "ENGINE_VERSION",
    "AssemblyApprovalOperationsEngine",
    "AssemblyApprovalActionResult",
    "generate_assembly_approval_audit_event_id",
    "build_assembly_approval_operations_mirror",
]
