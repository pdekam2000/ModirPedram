"""
Phase 11H-1g — voice approval write operations (approve/reject/expire/reset).

Mutates only voice_generation.approval metadata and audit logs.
Never imports or calls ElevenLabsVoiceProvider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import uuid

from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.voice_approval_action_policy import (
    ACTION_APPROVE,
    ACTION_EXPIRE,
    ACTION_REJECT,
    ACTION_RESET,
    evaluate_voice_approval_action,
)
from content_brain.execution.voice_approval_guard import (
    BLOCK_APPROVAL_EXPIRED,
    BLOCK_VOICE_APPROVAL_REJECTED,
    DEFAULT_APPROVAL_TTL_HOURS,
    GATE_VERSION,
    STATE_APPROVED,
    STATE_EXPIRED,
    STATE_REJECTED,
    TIMESTAMP_FORMAT,
    build_voice_approval_operations_mirror,
    can_run_live_voice_tts,
    evaluate_voice_approval_gate,
)
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run

ENGINE_VERSION = "11h1g_v1"
AUDIT_MAX_EVENTS = 50
DEFAULT_TTL_MINUTES = int(DEFAULT_APPROVAL_TTL_HOURS * 60)
MIN_TTL_MINUTES = 15
MAX_TTL_MINUTES = 24 * 60
CATEGORY_NAME = "voice_generation"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_voice_approval_audit_event_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"voice_appr_evt_{stamp}_{uuid.uuid4().hex[:6]}"


def _default_reason(action: str) -> str:
    defaults = {
        ACTION_APPROVE: "Voice generation approved for live TTS (metadata only).",
        ACTION_REJECT: "Voice generation rejected by operator.",
        ACTION_EXPIRE: "Voice approval expired by operator.",
        ACTION_RESET: "Voice approval reset by operator.",
    }
    return defaults.get(action, "Voice approval action.")


@dataclass
class VoiceApprovalActionResult:
    success: bool
    session_id: str
    action: str
    message: str = ""
    code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    voice_slot: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    panel_excerpt: dict[str, Any] | None = None
    audit_event: dict[str, Any] | None = None
    tts_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "session_id": self.session_id,
            "action": self.action,
            "message": self.message,
            "tts_executed": self.tts_executed,
        }
        if not self.success:
            payload["code"] = self.code
            if self.reject_reasons:
                payload["reject_reasons"] = self.reject_reasons
        if self.voice_slot is not None:
            payload["voice_slot"] = self.voice_slot
        if self.guard_result is not None:
            payload["guard_result"] = self.guard_result
        if self.panel_excerpt is not None:
            payload["panel_excerpt"] = self.panel_excerpt
        if self.audit_event is not None:
            payload["audit_event"] = self.audit_event
        return payload


class VoiceApprovalOperationsEngine:
    """Apply voice approval write actions — metadata and audit only."""

    def __init__(self, store: ExecutionSessionStore, *, project_root: str | Path | None = None):
        self.store = store
        self.project_root = project_root or store.project_root

    def approve(
        self,
        session_id: str,
        *,
        request_live_tts: bool,
        reason: str = "",
        approved_by: str = "local_user",
        ttl_minutes: int | None = None,
    ) -> VoiceApprovalActionResult:
        return self._run(
            session_id,
            ACTION_APPROVE,
            actor=approved_by,
            reason=reason,
            request_live_tts=request_live_tts,
            ttl_minutes=ttl_minutes,
        )

    def reject(
        self,
        session_id: str,
        *,
        reason: str = "",
        rejected_by: str = "local_user",
    ) -> VoiceApprovalActionResult:
        return self._run(session_id, ACTION_REJECT, actor=rejected_by, reason=reason)

    def expire(
        self,
        session_id: str,
        *,
        reason: str = "",
        expired_by: str = "local_user",
    ) -> VoiceApprovalActionResult:
        return self._run(session_id, ACTION_EXPIRE, actor=expired_by, reason=reason)

    def reset_approval(
        self,
        session_id: str,
        *,
        reason: str = "",
        reset_by: str = "local_user",
        clear_live_tts_request: bool = False,
    ) -> VoiceApprovalActionResult:
        return self._run(
            session_id,
            ACTION_RESET,
            actor=reset_by,
            reason=reason,
            clear_live_tts_request=clear_live_tts_request,
        )

    def _run(
        self,
        session_id: str,
        action: str,
        *,
        actor: str,
        reason: str = "",
        request_live_tts: bool = False,
        ttl_minutes: int | None = None,
        clear_live_tts_request: bool = False,
    ) -> VoiceApprovalActionResult:
        session = self.store.load_session(session_id)
        runtime, voice_slot, previous_state = self._prepare_voice_context(session)
        video_before = self._video_slot_snapshot(session)

        policy = evaluate_voice_approval_action(
            session,
            voice_slot,
            action,
            request_live_tts=request_live_tts if action == ACTION_APPROVE else bool(voice_slot.get("live_tts_requested")),
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
                live_tts_eligible=False,
                voice_slot=voice_slot,
            )
            self.store.save_session(session, overwrite=True)
            return VoiceApprovalActionResult(
                success=False,
                session_id=session_id,
                action=action,
                message=policy.message,
                code=policy.code,
                reject_reasons=policy.reject_reasons,
                voice_slot=voice_slot,
                guard_result=can_run_live_voice_tts(voice_slot, session, project_root=self.project_root).to_dict(),
                panel_excerpt=self._panel_excerpt(voice_slot, runtime),
                audit_event=audit,
                tts_executed=False,
            )

        if action == ACTION_APPROVE:
            voice_slot = self._mutate_approve(
                voice_slot,
                session,
                actor=actor,
                reason=reason,
                ttl_minutes=ttl_minutes,
            )
        elif action == ACTION_REJECT:
            voice_slot = self._mutate_reject(voice_slot, session, reason=reason)
        elif action == ACTION_EXPIRE:
            voice_slot = self._mutate_expire(voice_slot, session, reason=reason)
        elif action == ACTION_RESET:
            voice_slot = self._mutate_reset(
                voice_slot,
                session,
                clear_live_tts_request=clear_live_tts_request,
            )

        runtime = self._persist_voice_slot(session, runtime, voice_slot)
        new_state = str(_dict(voice_slot.get("approval")).get("approval_state") or previous_state)
        guard = can_run_live_voice_tts(voice_slot, session, project_root=self.project_root)
        approval = _dict(voice_slot.get("approval"))
        live_eligible = bool(approval.get("live_tts_eligible"))

        audit = self._append_audit(
            session,
            runtime,
            action=action,
            actor=actor,
            reason=reason or _default_reason(action),
            previous_state=previous_state,
            new_state=new_state,
            allowed=True,
            blocked_reasons=list(approval.get("live_tts_blocked_reasons") or []),
            live_tts_eligible=live_eligible,
            voice_slot=voice_slot,
        )

        session["execution_runtime"] = runtime
        session["updated_at"] = _now_utc()
        self.store.save_session(session, overwrite=True)

        video_after = self._video_slot_snapshot(session)
        if not self._video_slot_preserved(video_before, video_after):
            raise RuntimeError("Video generation slot critical fields were mutated — aborting.")

        return VoiceApprovalActionResult(
            success=True,
            session_id=session_id,
            action=action,
            message=f"Voice approval {action} completed (metadata only — no TTS executed).",
            voice_slot=voice_slot,
            guard_result=guard.to_dict(),
            panel_excerpt=self._panel_excerpt(voice_slot, runtime),
            audit_event=audit,
            tts_executed=False,
        )

    def _prepare_voice_context(
        self,
        session: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        runtime = dict(_dict(session.get("execution_runtime")))
        runtime = ensure_multi_category_shell(runtime)
        runtime = apply_voice_preflight_dry_run(session, runtime, project_root=self.project_root)
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
        previous_state = str(_dict(voice_slot.get("approval")).get("approval_state") or "not_required")
        session["execution_runtime"] = runtime
        return runtime, voice_slot, previous_state

    def _persist_voice_slot(
        self,
        session: dict[str, Any],
        runtime: dict[str, Any],
        voice_slot: dict[str, Any],
    ) -> dict[str, Any]:
        category_runtime = dict(_dict(runtime.get("category_runtime")))
        video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
        category_runtime[CATEGORY_VOICE] = voice_slot
        category_runtime[CATEGORY_VIDEO] = video_slot
        runtime["category_runtime"] = category_runtime

        evaluated_at = _now_utc()
        operations = dict(_dict(runtime.get("operations")))
        operations["voice_approval_gate"] = build_voice_approval_operations_mirror(
            voice_slot,
            live_tts_requested=bool(voice_slot.get("live_tts_requested")),
            evaluated_at=evaluated_at,
        )
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return runtime

    def _mutate_approve(
        self,
        voice_slot: dict[str, Any],
        session: dict[str, Any],
        *,
        actor: str,
        reason: str,
        ttl_minutes: int | None,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        slot["live_tts_requested"] = True
        ttl = DEFAULT_TTL_MINUTES if ttl_minutes is None else int(ttl_minutes)
        ttl = max(MIN_TTL_MINUTES, min(MAX_TTL_MINUTES, ttl))
        now_local = datetime.now()
        approved_at = now_local.strftime(TIMESTAMP_FORMAT)
        expires_at = (now_local + timedelta(minutes=ttl)).strftime(TIMESTAMP_FORMAT)

        gate_preview = evaluate_voice_approval_gate(
            slot,
            session,
            live_tts_requested=True,
            project_root=self.project_root,
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
        slot["approval"] = evaluate_voice_approval_gate(
            slot,
            session,
            live_tts_requested=True,
            project_root=self.project_root,
        )
        guard = can_run_live_voice_tts(slot, session, project_root=self.project_root)
        slot["approval"]["live_tts_eligible"] = guard.allowed
        slot["approval"]["live_tts_blocked_reasons"] = guard.block_codes if guard.blocked else []
        return slot

    def _mutate_reject(
        self,
        voice_slot: dict[str, Any],
        session: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        gate_preview = evaluate_voice_approval_gate(
            slot,
            session,
            live_tts_requested=bool(slot.get("live_tts_requested")),
            project_root=self.project_root,
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
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_VOICE_APPROVAL_REJECTED],
            }
        )
        slot["approval"] = approval
        return slot

    def _mutate_expire(
        self,
        voice_slot: dict[str, Any],
        session: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        gate_preview = evaluate_voice_approval_gate(
            slot,
            session,
            live_tts_requested=bool(slot.get("live_tts_requested")),
            project_root=self.project_root,
        )
        approval = dict(gate_preview)
        approval.update(
            {
                "approval_state": STATE_EXPIRED,
                "approval_expires_at": datetime.now().strftime(TIMESTAMP_FORMAT),
                "approval_reason": reason or _default_reason(ACTION_EXPIRE),
                "live_tts_eligible": False,
                "live_tts_blocked_reasons": [BLOCK_APPROVAL_EXPIRED],
            }
        )
        slot["approval"] = approval
        return slot

    def _mutate_reset(
        self,
        voice_slot: dict[str, Any],
        session: dict[str, Any],
        *,
        clear_live_tts_request: bool,
    ) -> dict[str, Any]:
        slot = dict(voice_slot)
        if clear_live_tts_request:
            slot["live_tts_requested"] = False
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
        slot["approval"] = evaluate_voice_approval_gate(
            slot,
            session,
            live_tts_requested=bool(slot.get("live_tts_requested")),
            project_root=self.project_root,
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
        live_tts_eligible: bool,
        voice_slot: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = ExecutionSessionStore.extract_session_id(session)
        approval = _dict(voice_slot.get("approval"))
        event = {
            "event_id": generate_voice_approval_audit_event_id(),
            "event_type": action,
            "session_id": session_id,
            "category": CATEGORY_NAME,
            "actor": actor or "local_user",
            "reason": reason,
            "timestamp": _now_utc(),
            "previous_state": previous_state,
            "new_state": new_state,
            "blocked_reasons": list(blocked_reasons),
            "live_tts_eligible": live_tts_eligible,
            "tts_executed": False,
            "allowed": allowed,
            "metadata": {
                "engine_version": ENGINE_VERSION,
                "gate_version": GATE_VERSION,
                "provider": voice_slot.get("provider"),
                "estimated_character_count": approval.get("estimated_character_count"),
                "estimated_segment_count": approval.get("estimated_segment_count"),
                "estimated_voice_cost": approval.get("estimated_voice_cost"),
                "live_tts_requested": bool(voice_slot.get("live_tts_requested")),
            },
        }
        operations = dict(_dict(runtime.get("operations")))
        audit_log = list(operations.get("voice_approval_audit") or [])
        audit_log.append(event)
        if len(audit_log) > AUDIT_MAX_EVENTS:
            audit_log = audit_log[-AUDIT_MAX_EVENTS:]
        operations["voice_approval_audit"] = audit_log
        runtime["operations"] = operations
        session["execution_runtime"] = runtime
        return event

    @staticmethod
    def _video_slot_snapshot(session: dict[str, Any]) -> dict[str, Any]:
        runtime = _dict(session.get("execution_runtime"))
        return dict(_dict(_dict(runtime.get("category_runtime")).get(CATEGORY_VIDEO)))

    @staticmethod
    def _video_slot_preserved(before: dict[str, Any], after: dict[str, Any]) -> bool:
        keys = ("state", "provider", "started_at", "completed_at")
        return all(before.get(key) == after.get(key) for key in keys)

    @staticmethod
    def _panel_excerpt(voice_slot: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
        approval = _dict(voice_slot.get("approval"))
        operations = _dict(runtime.get("operations"))
        return {
            "voice_generation_status": voice_slot.get("status"),
            "voice_generation_executed": voice_slot.get("executed"),
            "voice_approval_gate": operations.get("voice_approval_gate"),
            "approval_state": approval.get("approval_state"),
            "live_tts_eligible": approval.get("live_tts_eligible"),
        }


__all__ = [
    "ENGINE_VERSION",
    "VoiceApprovalOperationsEngine",
    "VoiceApprovalActionResult",
    "generate_voice_approval_audit_event_id",
]
