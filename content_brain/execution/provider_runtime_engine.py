"""
Phase 10I — provider runtime dispatch for DEQUEUED sessions (video_generation only).

Reuses VideoProviderRouter and existing orchestrators. No Suno/music execution in 10I.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import shutil
import uuid
from typing import Any

from content_brain.execution.category_runtime_compat import ensure_multi_category_shell
from content_brain.execution.voice_preflight_runtime_slot import apply_voice_preflight_dry_run
from content_brain.execution.provider_categories import (
    CATEGORY_VIDEO,
    MEDIA_CATEGORIES,
    PROVIDER_CATEGORIES,
    REGISTRY_TO_RUNTIME_CATEGORY,
    default_artifacts_by_category,
    default_category_runtime_slots,
    normalize_provider_key,
)
from content_brain.execution.artifact_validation_engine import (
    ArtifactValidationEngine,
    build_artifact_failure,
)
from content_brain.execution.operations_cancel import (
    CANCEL_REJECT_CODE,
    PHASE_CANCELLATION_ACKNOWLEDGED,
    clip_counts_from_runtime,
    get_cancel_metadata,
    is_cancellation_requested,
)
from content_brain.execution.provider_cancel_wiring import (
    build_runtime_cancel_check,
    extract_cancel_partial_artifacts,
)
from content_brain.execution.hailuo_failover_advisory import build_hailuo_failover_advisory
from content_brain.execution.runway_failover_advisory import (
    OUTCOME_CANCELLED as ADVISORY_OUTCOME_CANCELLED,
    OUTCOME_FAILED as ADVISORY_OUTCOME_FAILED,
    attach_failover_advisory_to_operations,
    build_runway_failover_advisory,
)
from content_brain.execution.queue_integrity_validator import QueueIntegrityValidator
from content_brain.execution.runway_prompt_composer import apply_runway_prompt_composer_to_session
from content_brain.execution.runway_prompt_composer_config import enable_runway_prompt_composer
from content_brain.execution.session_prompt_adapter import SessionPromptAdapter
from content_brain.execution.session_store import ExecutionSessionStore
from providers.runway_api_errors import RunwayCancelledError
from providers.hailuo_api_errors import HailuoCancelledError

ENGINE_NAME = "ProviderRuntimeEngine"
ENGINE_VERSION = "10i_v1"
POLICY_VERSION = "10i_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATE_DEQUEUED = "DEQUEUED"
STATE_DISPATCHED = "DISPATCHED"
STATE_RUNNING = "RUNNING"
STATE_COMPLETED = "COMPLETED"
STATE_FAILED = "FAILED"
STATE_CANCELLED = "CANCELLED"
FAILURE_CODE_OPERATIONS_CANCELLED = "OPERATIONS_CANCELLED"

ROUTER_SUPPORTED = {
    "hailuo",
    "hailuo_browser",
    "runway_browser",
    "runway",
    "runway_api",
    "minimax_api",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _first(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def generate_dispatch_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"disp_{stamp}_{uuid.uuid4().hex[:6]}"


def generate_audit_event_id() -> str:
    return f"pevt_{uuid.uuid4().hex[:12]}"


@dataclass
class RuntimePolicy:
    policy_id: str = "default_local"
    policy_version: str = POLICY_VERSION
    provider_category: str = CATEGORY_VIDEO
    require_queue_fingerprint: bool = True
    require_readiness: bool = True
    skip_provider_execution: bool = False
    max_clips_cap: int = 30

    def snapshot(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "provider_category": self.provider_category,
            "require_queue_fingerprint": self.require_queue_fingerprint,
            "require_readiness": self.require_readiness,
            "skip_provider_execution": self.skip_provider_execution,
            "max_clips_cap": self.max_clips_cap,
            "supported_categories_10i": [CATEGORY_VIDEO],
            "supported_categories_11g_shell": list(MEDIA_CATEGORIES),
            "future_categories": [c for c in PROVIDER_CATEGORIES if c != CATEGORY_VIDEO],
        }


@dataclass
class DispatchResult:
    success: bool
    session: dict[str, Any] | None = None
    execution_runtime: dict[str, Any] | None = None
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)


def resolve_video_provider(session: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (normalized_provider, reject_code)."""
    provider_selection = _dict(session.get("provider_selection"))
    category_selections = _dict(provider_selection.get("category_selections"))
    video_sel = _dict(category_selections.get(CATEGORY_VIDEO))

    raw = _first(
        video_sel.get("provider"),
        provider_selection.get("primary_provider"),
        session.get("provider"),
    )
    if not raw:
        return None, "INVALID_PROVIDER"

    normalized = normalize_provider_key(raw)
    if normalized not in ROUTER_SUPPORTED:
        return normalized, "PROVIDER_UNSUPPORTED"
    return normalized, None


def lookup_registry_entry(provider: str) -> dict[str, Any] | None:
    try:
        from core.provider_registry_engine import ProviderRegistryEngine

        registry = ProviderRegistryEngine()
        catalog = registry.load_registry()
        for entry in catalog.get("video") or []:
            if isinstance(entry, dict) and str(entry.get("name", "")).lower() == provider:
                return entry
        for alias, target in {"runway_api": "runway", "hailuo": "hailuo_browser"}.items():
            if provider == alias:
                for entry in catalog.get("video") or []:
                    if isinstance(entry, dict) and str(entry.get("name", "")).lower() == target:
                        return entry
    except Exception:
        return None
    return None


class ProviderRuntimeEngine:
    """Dispatch DEQUEUED sessions to existing video provider infrastructure."""

    def __init__(self, store: ExecutionSessionStore):
        self.store = store
        self.integrity = QueueIntegrityValidator()
        self.adapter = SessionPromptAdapter()

    def validate_dispatch_eligibility(
        self,
        session: dict[str, Any],
        policy: RuntimePolicy | None = None,
    ) -> tuple[bool, list[str], str | None]:
        policy = policy or RuntimePolicy()
        if policy.provider_category != CATEGORY_VIDEO:
            return False, [f"Category {policy.provider_category} not supported in 10I."], "CATEGORY_NOT_SUPPORTED"

        integrity = self.integrity.validate(
            session,
            require_queue_fingerprint=policy.require_queue_fingerprint,
            require_readiness=policy.require_readiness,
        )
        if not integrity.passed:
            return False, integrity.failures or integrity.warnings, integrity.reject_code

        provider, code = resolve_video_provider(session)
        if not provider or code:
            reasons = [f"Provider resolution failed: {code or 'unknown'}."]
            return False, reasons, code or "INVALID_PROVIDER"

        return True, integrity.warnings, None

    def dispatch(
        self,
        session: dict[str, Any],
        *,
        actor: str = "system",
        policy: RuntimePolicy | None = None,
        dispatch_id: str | None = None,
    ) -> DispatchResult:
        policy = policy or RuntimePolicy()
        session = dict(session)
        ok, reasons, code = self.validate_dispatch_eligibility(session, policy)
        if not ok:
            session = self._mark_failed(session, code or "DISPATCH_REJECTED", reasons, actor, policy)
            self.store.save_session(session, overwrite=True)
            return DispatchResult(False, session=session, execution_runtime=session.get("execution_runtime"), reject_code=code, reject_reasons=reasons)

        provider, provider_code = resolve_video_provider(session)
        if not provider or provider_code:
            session = self._mark_failed(session, provider_code or "INVALID_PROVIDER", reasons, actor, policy)
            self.store.save_session(session, overwrite=True)
            return DispatchResult(False, session=session, reject_code=provider_code, reject_reasons=reasons)

        try:
            if enable_runway_prompt_composer(session):
                session = apply_runway_prompt_composer_to_session(session)
                self.store.save_session(session, overwrite=True)
            bundle = self.adapter.build(session, provider)
        except ValueError as exc:
            message = str(exc)
            if "COMPOSER_" in message:
                fail_code = "PROMPT_COMPOSER_FAILED"
            else:
                fail_code = "CLIP_COUNT_MISMATCH" if "CLIP_COUNT_MISMATCH" in message else "PROMPT_ADAPTER_FAILED"
            session = self._mark_failed(session, fail_code, [message], actor, policy)
            self.store.save_session(session, overwrite=True)
            return DispatchResult(False, session=session, reject_code=fail_code, reject_reasons=[message])

        if bundle.clip_count > policy.max_clips_cap:
            session = self._mark_failed(
                session,
                "CLIP_COUNT_MISMATCH",
                [f"Clip count {bundle.clip_count} exceeds cap {policy.max_clips_cap}."],
                actor,
                policy,
            )
            self.store.save_session(session, overwrite=True)
            return DispatchResult(False, session=session, reject_code="CLIP_COUNT_MISMATCH", reject_reasons=[f"Too many clips: {bundle.clip_count}"])

        timestamp = _now()
        dispatch_id = dispatch_id or generate_dispatch_id()
        session_id = ExecutionSessionStore.extract_session_id(session)
        artifact_root = self.store.artifact_dir(session_id, CATEGORY_VIDEO)
        registry_entry = lookup_registry_entry(provider) or {}
        preserved_operations = _dict(_dict(session.get("execution_runtime")).get("operations"))

        category_runtime = default_category_runtime_slots()
        artifacts_by_category = default_artifacts_by_category()
        execution_runtime: dict[str, Any] = {
            "runtime_version": ENGINE_VERSION,
            "provider_category": CATEGORY_VIDEO,
            "dispatch_id": dispatch_id,
            "dispatch_uuid": str(uuid.uuid4()),
            "provider_resolved": provider,
            "provider_mode": registry_entry.get("mode") or "unknown",
            "state": STATE_DISPATCHED,
            "dispatched_at": timestamp,
            "running_at": None,
            "completed_at": None,
            "artifact_root": str(artifact_root),
            "prompt_bundle": bundle.to_dict(),
            "category_runtime": category_runtime,
            "artifacts_by_category": artifacts_by_category,
            "failure": None,
            "retry": {
                "max_dispatch_attempts": 1,
                "dispatch_attempts_used": 1,
                "requeue_required_for_retry": True,
            },
            "provider_provenance": {
                "engine": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
                "policy_version": policy.policy_version,
                "evaluated_at": timestamp,
                "provider_category": CATEGORY_VIDEO,
                "provider_resolved": provider,
                "registry_category": REGISTRY_TO_RUNTIME_CATEGORY.get("video", "video"),
                "registry_entry": registry_entry or None,
                "future_categories_registered": [
                    c for c in PROVIDER_CATEGORIES if c != CATEGORY_VIDEO
                ],
                "policy_snapshot": policy.snapshot(),
            },
        }
        if preserved_operations:
            execution_runtime["operations"] = preserved_operations

        execution_runtime = ensure_multi_category_shell(execution_runtime)
        execution_runtime = apply_voice_preflight_dry_run(
            session,
            execution_runtime,
            project_root=self.store.project_root,
        )
        category_runtime = _dict(execution_runtime.get("category_runtime"))
        session["execution_runtime"] = execution_runtime
        session["state"] = STATE_DISPATCHED
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10i_v1"
        self._append_state_history(session, STATE_DISPATCHED, timestamp, f"provider runtime: dispatched ({provider}, clips={bundle.clip_count})")
        self._audit(session, "DISPATCHED", actor, dispatch_id, {"provider": provider, "provider_category": CATEGORY_VIDEO, "clip_count": bundle.clip_count})

        bundle_path = artifact_root / "prompt_bundle.json"
        bundle_path.write_text(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        running_ts = _now()
        execution_runtime["state"] = STATE_RUNNING
        execution_runtime["running_at"] = running_ts
        category_runtime[CATEGORY_VIDEO]["state"] = STATE_RUNNING
        category_runtime[CATEGORY_VIDEO]["provider"] = provider
        category_runtime[CATEGORY_VIDEO]["started_at"] = running_ts
        session["state"] = STATE_RUNNING
        session["updated_at"] = running_ts
        self._append_state_history(session, STATE_RUNNING, running_ts, f"provider runtime: running ({provider})")
        self._audit(session, "RUNNING", actor, dispatch_id, {"provider": provider, "provider_category": CATEGORY_VIDEO})
        self.store.save_session(session, overwrite=True)

        if self._cancellation_requested(session_id):
            session = self._mark_cooperative_cancelled(
                session,
                actor=actor,
                dispatch_id=dispatch_id,
                execution_runtime=execution_runtime,
                partial_clip_paths=[],
            )
            self.store.save_session(session, overwrite=True)
            return DispatchResult(
                False,
                session=session,
                execution_runtime=session.get("execution_runtime"),
                reject_code=CANCEL_REJECT_CODE,
                reject_reasons=[get_cancel_metadata(session).get("cancel_reason") or "Operator cancelled"],
            )

        try:
            clip_paths = self._execute_clips(
                bundle.prompts,
                provider,
                artifact_root,
                policy,
                session_id=session_id,
            )
            if self._cancellation_requested(session_id):
                session = self.store.load_session(session_id)
                runtime = _dict(session.get("execution_runtime"))
                session = self._mark_cooperative_cancelled(
                    session,
                    actor=actor,
                    dispatch_id=dispatch_id,
                    execution_runtime=runtime or execution_runtime,
                    partial_clip_paths=clip_paths,
                )
                self.store.save_session(session, overwrite=True)
                return DispatchResult(
                    False,
                    session=session,
                    execution_runtime=session.get("execution_runtime"),
                    reject_code=CANCEL_REJECT_CODE,
                    reject_reasons=[get_cancel_metadata(session).get("cancel_reason") or "Operator cancelled"],
                )

            video_artifacts = self._build_video_artifacts(clip_paths, provider, bundle)

            if self._cancellation_requested(session_id):
                execution_runtime["artifacts_by_category"] = {CATEGORY_VIDEO: video_artifacts}
                session["execution_runtime"] = execution_runtime
                session = self._mark_cooperative_cancelled(
                    session,
                    actor=actor,
                    dispatch_id=dispatch_id,
                    execution_runtime=execution_runtime,
                    partial_clip_paths=clip_paths,
                )
                self.store.save_session(session, overwrite=True)
                return DispatchResult(
                    False,
                    session=session,
                    execution_runtime=session.get("execution_runtime"),
                    reject_code=CANCEL_REJECT_CODE,
                    reject_reasons=[get_cancel_metadata(session).get("cancel_reason") or "Operator cancelled"],
                )

            preserved_operations = _dict(execution_runtime.get("operations"))
            policy_snapshot = _dict(preserved_operations.get("policy_snapshot"))
            min_artifact_bytes = int(policy_snapshot.get("min_artifact_bytes") or 100_000)
            provider_execution = self._provider_execution_context(preserved_operations, provider)
            validation = ArtifactValidationEngine().validate(
                video_artifacts,
                clip_target=bundle.clip_count,
                min_artifact_bytes=min_artifact_bytes,
                dry_run=policy.skip_provider_execution,
                provider_execution=provider_execution,
            )
            video_artifacts = validation.enriched_artifacts
            artifacts_by_category[CATEGORY_VIDEO] = video_artifacts
            execution_runtime["artifacts_by_category"] = artifacts_by_category
            operations_block = dict(preserved_operations)
            operations_block["validation"] = validation.to_operations_block()
            execution_runtime["operations"] = operations_block

            if not validation.passed:
                category_runtime[CATEGORY_VIDEO]["artifact_count"] = validation.clip_valid
                execution_runtime["category_runtime"] = category_runtime
                session["execution_runtime"] = execution_runtime
                session = self._mark_artifact_validation_failed(
                    session,
                    validation,
                    actor,
                    policy,
                    dispatch_id=dispatch_id,
                    partial_runtime=execution_runtime,
                )
                self.store.save_session(session, overwrite=True)
                return DispatchResult(
                    False,
                    session=session,
                    execution_runtime=session.get("execution_runtime"),
                    reject_code=validation.reject_code,
                    reject_reasons=validation.reject_reasons,
                )

            self._audit(
                session,
                "ARTIFACT_VALIDATED",
                actor,
                dispatch_id,
                {
                    "clip_count": validation.clip_valid,
                    "clip_target": validation.clip_target,
                    "provider_category": CATEGORY_VIDEO,
                },
            )

            if self._cancellation_requested(session_id):
                session = self.store.load_session(session_id)
                runtime = _dict(session.get("execution_runtime"))
                session = self._mark_cooperative_cancelled(
                    session,
                    actor=actor,
                    dispatch_id=dispatch_id,
                    execution_runtime=runtime or execution_runtime,
                    partial_clip_paths=clip_paths,
                )
                self.store.save_session(session, overwrite=True)
                return DispatchResult(
                    False,
                    session=session,
                    execution_runtime=session.get("execution_runtime"),
                    reject_code=CANCEL_REJECT_CODE,
                    reject_reasons=[get_cancel_metadata(session).get("cancel_reason") or "Operator cancelled"],
                )

            completed_ts = _now()
            execution_runtime["state"] = STATE_COMPLETED
            execution_runtime["completed_at"] = completed_ts
            category_runtime[CATEGORY_VIDEO]["state"] = STATE_COMPLETED
            category_runtime[CATEGORY_VIDEO]["completed_at"] = completed_ts
            category_runtime[CATEGORY_VIDEO]["artifact_count"] = len(video_artifacts)
            artifacts_by_category[CATEGORY_VIDEO] = video_artifacts
            session["state"] = STATE_COMPLETED
            session["updated_at"] = completed_ts
            self._append_state_history(session, STATE_COMPLETED, completed_ts, f"provider runtime: completed ({len(video_artifacts)} clips)")
            self._audit(session, "COMPLETED", actor, dispatch_id, {"clip_count": len(video_artifacts), "provider_category": CATEGORY_VIDEO})
            self.store.save_session(session, overwrite=True)
            refreshed = self.store.load_session(session_id)
            return DispatchResult(True, session=refreshed, execution_runtime=refreshed.get("execution_runtime"))

        except (RunwayCancelledError, HailuoCancelledError) as exc:
            partial_paths, clip_results = extract_cancel_partial_artifacts(exc)
            session = self.store.load_session(session_id)
            session = self._mark_cooperative_cancelled(
                session,
                actor=actor,
                dispatch_id=dispatch_id,
                execution_runtime=execution_runtime,
                partial_clip_paths=partial_paths,
                clip_results=clip_results,
                failure_code=FAILURE_CODE_OPERATIONS_CANCELLED,
                cancel_reason=str(exc) or get_cancel_metadata(session).get("cancel_reason") or "Operator cancelled",
            )
            self.store.save_session(session, overwrite=True)
            return DispatchResult(
                False,
                session=session,
                execution_runtime=session.get("execution_runtime"),
                reject_code=CANCEL_REJECT_CODE,
                reject_reasons=[get_cancel_metadata(session).get("cancel_reason") or str(exc) or "Operator cancelled"],
            )
        except Exception as exc:
            fail_msg = str(exc)
            session = self._mark_failed(
                session,
                "PROVIDER_RUNTIME_ERROR",
                [fail_msg],
                actor,
                policy,
                dispatch_id=dispatch_id,
                partial_runtime=execution_runtime,
            )
            self.store.save_session(session, overwrite=True)
            return DispatchResult(False, session=session, execution_runtime=session.get("execution_runtime"), reject_code="PROVIDER_RUNTIME_ERROR", reject_reasons=[fail_msg])

    def dispatch_by_id(
        self,
        session_id: str,
        *,
        actor: str = "system",
        policy: RuntimePolicy | None = None,
        dispatch_id: str | None = None,
    ) -> DispatchResult:
        session = self.store.load_session(session_id)
        return self.dispatch(session, actor=actor, policy=policy, dispatch_id=dispatch_id)

    def _execute_clips(
        self,
        prompts: list[str],
        provider: str,
        artifact_root: Path,
        policy: RuntimePolicy,
        *,
        session_id: str | None = None,
    ) -> list[str]:
        if policy.skip_provider_execution:
            paths: list[str] = []
            for index in range(1, len(prompts) + 1):
                if session_id and self._cancellation_requested(session_id):
                    break
                marker = artifact_root / f"clip_{index:02d}.mock"
                marker.write_text(
                    f"mock artifact — provider execution skipped ({provider})\n",
                    encoding="utf-8",
                )
                paths.append(str(marker))
            return paths

        from content_brain.execution.runway_browser_observability import (
            build_runway_browser_observability,
        )
        from core.video_provider_router import VideoProviderRouter

        cancel_check = build_runtime_cancel_check(self.store, session_id) if session_id else None
        runway_obs = build_runway_browser_observability(self.store, session_id, provider=provider)

        router = VideoProviderRouter()
        try:
            raw_paths = router.generate_clips(
                prompts,
                provider_override=provider,
                cancel_check=cancel_check,
                runway_obs=runway_obs,
            )
        except (RunwayCancelledError, HailuoCancelledError) as exc:
            partial_paths, _clip_results = extract_cancel_partial_artifacts(exc)
            canonical = self._canonicalize_clip_paths(partial_paths, artifact_root)
            if canonical:
                details = {
                    **(_dict(getattr(exc, "details", None))),
                    "partial_paths": canonical,
                    "clip_results": _clip_results,
                }
                if isinstance(exc, HailuoCancelledError):
                    raise HailuoCancelledError(
                        str(exc),
                        partial_paths=canonical,
                        clip_results=_clip_results,
                        phase=getattr(exc, "phase", "provider_execution"),
                        details=details,
                    ) from exc
                raise RunwayCancelledError(
                    str(exc),
                    partial_paths=canonical,
                    phase=getattr(exc, "phase", "provider_execution"),
                    details=details,
                ) from exc
            raise

        canonical = self._canonicalize_clip_paths(list(raw_paths or []), artifact_root)
        if not canonical:
            raise RuntimeError("Provider returned no clip paths.")
        return canonical

    def _canonicalize_clip_paths(self, raw_paths: list[str], artifact_root: Path) -> list[str]:
        canonical: list[str] = []
        for index, src in enumerate(raw_paths or [], start=1):
            if not src:
                continue
            src_path = Path(str(src))
            dest = artifact_root / f"clip_{index:02d}{src_path.suffix or '.mp4'}"
            if src_path.resolve() == dest.resolve():
                canonical.append(str(dest))
                continue
            if src_path.exists():
                shutil.copy2(src_path, dest)
                canonical.append(str(dest))
            else:
                canonical.append(str(src_path))
        return canonical

    def _build_video_artifacts(
        self,
        clip_paths: list[str],
        provider: str,
        bundle: Any,
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for index, path in enumerate(clip_paths, start=1):
            meta = {}
            if index - 1 < len(bundle.clip_metadata):
                meta = dict(bundle.clip_metadata[index - 1])
            artifacts.append(
                {
                    "artifact_id": f"art_{uuid.uuid4().hex[:12]}",
                    "provider_category": CATEGORY_VIDEO,
                    "artifact_type": "video_clip",
                    "provider": provider,
                    "file_path": path,
                    "clip_number": meta.get("clip_number", index),
                    "metadata": meta,
                }
            )
        return artifacts

    def _cancellation_requested(self, session_id: str) -> bool:
        try:
            session = self.store.load_session(session_id)
        except FileNotFoundError:
            return False
        return is_cancellation_requested(session)

    @staticmethod
    def _clip_result_metadata_key(provider: str) -> str:
        normalized = normalize_provider_key(str(provider or ""))
        if normalized in {"hailuo", "hailuo_browser"}:
            return "hailuo_clip_result"
        return "runway_clip_result"

    def _mark_cooperative_cancelled(
        self,
        session: dict[str, Any],
        *,
        actor: str,
        dispatch_id: str,
        execution_runtime: dict[str, Any],
        partial_clip_paths: list[str] | None,
        clip_results: list[dict[str, Any]] | None = None,
        failure_code: str | None = None,
        cancel_reason: str | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        session = dict(session)
        runtime = dict(_dict(execution_runtime))
        cancel_meta = get_cancel_metadata(session)
        resolved_reason = cancel_reason or str(cancel_meta.get("cancel_reason") or "Operator cancelled")
        resolved_failure_code = failure_code or CANCEL_REJECT_CODE

        if partial_clip_paths:
            provider = str(runtime.get("provider_resolved") or session.get("provider") or "")
            bundle_data = _dict(runtime.get("prompt_bundle"))

            class _MiniBundle:
                clip_metadata = bundle_data.get("clip_metadata") or []

            video_artifacts = self._build_video_artifacts(partial_clip_paths, provider, _MiniBundle())
            if clip_results:
                clip_meta_key = self._clip_result_metadata_key(provider)
                for index, artifact in enumerate(video_artifacts):
                    if index < len(clip_results):
                        meta = dict(artifact.get("metadata") or {})
                        meta[clip_meta_key] = clip_results[index]
                        artifact["metadata"] = meta
            artifacts_by_category = dict(_dict(runtime.get("artifacts_by_category")))
            artifacts_by_category[CATEGORY_VIDEO] = video_artifacts
            runtime["artifacts_by_category"] = artifacts_by_category
            category_runtime = dict(_dict(runtime.get("category_runtime")))
            video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))
            video_slot["artifact_count"] = len(video_artifacts)
            video_slot["state"] = STATE_CANCELLED
            category_runtime[CATEGORY_VIDEO] = video_slot
            runtime["category_runtime"] = category_runtime
            runtime["provider_clip_results"] = list(clip_results or [])

        completed_count, skipped_count = clip_counts_from_runtime(runtime, clip_target=None)
        runtime["state"] = STATE_CANCELLED
        runtime["cancelled_at"] = timestamp
        runtime["failure"] = {
            "code": resolved_failure_code,
            "message": resolved_reason,
            "category": "OPERATIONS",
            "failed_at": timestamp,
        }

        operations = dict(_dict(runtime.get("operations")))
        worker = dict(_dict(operations.get("worker")))
        worker["phase"] = PHASE_CANCELLATION_ACKNOWLEDGED
        worker["thread_alive"] = False
        worker["stale"] = False
        worker["stale_reason"] = None
        worker["cancelled_at"] = timestamp
        operations["worker"] = worker
        operations["cancellation"] = {
            "acknowledged_at": timestamp,
            "cancel_reason": resolved_reason,
            "cancelled_by": cancel_meta.get("cancelled_by"),
            "completed_clip_count": completed_count,
            "skipped_clip_count": skipped_count,
            "partial_artifacts_preserved": bool(partial_clip_paths),
            "partial_paths": list(partial_clip_paths or []),
            "clip_results": list(clip_results or []),
        }
        runtime["operations"] = operations
        runtime = self._attach_failover_advisory(
            session,
            runtime,
            outcome=ADVISORY_OUTCOME_CANCELLED,
            failure_code=resolved_failure_code,
            failure_message=resolved_reason,
        )
        operations = dict(_dict(runtime.get("operations")))
        session["execution_runtime"] = runtime
        session["state"] = STATE_CANCELLED
        session["updated_at"] = timestamp

        control = dict(_dict(session.get("operations_control")))
        control["cancelled_at"] = timestamp
        control["cancel_acknowledged"] = True
        session["operations_control"] = control

        self._append_state_history(session, STATE_CANCELLED, timestamp, f"cooperative cancel: {resolved_reason}")
        self._audit(
            session,
            "CANCELLATION_ACKNOWLEDGED",
            actor,
            dispatch_id,
            operations.get("cancellation") or {},
        )
        self._audit(
            session,
            "WORKER_CANCELLED",
            actor,
            dispatch_id,
            {
                "completed_clip_count": completed_count,
                "skipped_clip_count": skipped_count,
            },
        )
        return session

    def _attach_failover_advisory(
        self,
        session: dict[str, Any],
        execution_runtime: dict[str, Any],
        *,
        outcome: str,
        failure_code: str | None,
        failure_message: str | None = None,
    ) -> dict[str, Any]:
        advisory = build_runway_failover_advisory(
            session=session,
            execution_runtime=execution_runtime,
            outcome=outcome,
            failure_code=failure_code,
            failure_message=failure_message,
            project_root=self.store.project_root,
        )
        if advisory is None:
            advisory = build_hailuo_failover_advisory(
                session=session,
                execution_runtime=execution_runtime,
                outcome=outcome,
                failure_code=failure_code,
                failure_message=failure_message,
                project_root=self.store.project_root,
            )
        return attach_failover_advisory_to_operations(execution_runtime, advisory)

    @staticmethod
    def _provider_execution_context(operations: dict[str, Any], provider: str) -> dict[str, Any]:
        return {
            "provider_name": operations.get("provider_family") or provider,
            "provider_category": CATEGORY_VIDEO,
            "execution_mode": operations.get("provider_execution_mode"),
            "learning_key": operations.get("learning_key"),
            "router_key": operations.get("router_key") or provider,
        }

    def _mark_artifact_validation_failed(
        self,
        session: dict[str, Any],
        validation: Any,
        actor: str,
        policy: RuntimePolicy,
        *,
        dispatch_id: str,
        partial_runtime: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = _now()
        code = validation.reject_code or "ARTIFACT_VALIDATION_FAILED"
        reasons = validation.reject_reasons or [code]
        execution_runtime = dict(partial_runtime)
        execution_runtime["state"] = STATE_FAILED
        execution_runtime["failure"] = build_artifact_failure(
            validation,
            dispatch_id=dispatch_id,
            failed_at=timestamp,
        )
        execution_runtime = self._attach_failover_advisory(
            session,
            execution_runtime,
            outcome=ADVISORY_OUTCOME_FAILED,
            failure_code=code,
            failure_message="; ".join(reasons) if reasons else code,
        )
        session["execution_runtime"] = execution_runtime
        session["state"] = STATE_FAILED
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10j_v1"
        self._append_state_history(
            session,
            STATE_FAILED,
            timestamp,
            f"artifact validation failed: {code} ({validation.clip_valid}/{validation.clip_target or validation.clip_count} valid)",
        )
        self._audit(
            session,
            "ARTIFACT_VALIDATION_FAILED",
            actor,
            dispatch_id,
            {
                "code": code,
                "reasons": reasons,
                "clip_valid": validation.clip_valid,
                "clip_target": validation.clip_target,
                "invalid_clips": validation.invalid_clips,
                "provider_category": CATEGORY_VIDEO,
            },
        )
        self._audit(
            session,
            "FAILED",
            actor,
            dispatch_id,
            {"code": code, "reasons": reasons, "provider_category": CATEGORY_VIDEO},
        )
        return session

    def _mark_failed(
        self,
        session: dict[str, Any],
        code: str,
        reasons: list[str],
        actor: str,
        policy: RuntimePolicy,
        *,
        dispatch_id: str | None = None,
        partial_runtime: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        dispatch_id = dispatch_id or generate_dispatch_id()
        execution_runtime = partial_runtime or _dict(session.get("execution_runtime"))
        if not execution_runtime:
            execution_runtime = {
                "runtime_version": ENGINE_VERSION,
                "provider_category": CATEGORY_VIDEO,
                "dispatch_id": dispatch_id,
                "category_runtime": default_category_runtime_slots(),
                "artifacts_by_category": default_artifacts_by_category(),
            }
        execution_runtime["state"] = STATE_FAILED
        execution_runtime["failure"] = {
            "code": code,
            "message": "; ".join(reasons) if reasons else code,
            "failed_at": timestamp,
        }
        execution_runtime = self._attach_failover_advisory(
            session,
            execution_runtime,
            outcome=ADVISORY_OUTCOME_FAILED,
            failure_code=code,
            failure_message="; ".join(reasons) if reasons else code,
        )
        session["execution_runtime"] = execution_runtime
        session["state"] = STATE_FAILED
        session["updated_at"] = timestamp
        session["session_schema_version"] = "10i_v1"
        self._append_state_history(session, STATE_FAILED, timestamp, f"provider runtime failed: {code}")
        event_type = "DISPATCH_REJECTED" if code in {"NOT_DEQUEUED", "STALE_QUEUE_FINGERPRINT", "READINESS_DRIFT", "INVALID_PROVIDER", "PROVIDER_UNSUPPORTED", "PROMPT_ADAPTER_FAILED", "CLIP_COUNT_MISMATCH", "CATEGORY_NOT_SUPPORTED"} else "FAILED"
        self._audit(session, event_type, actor, dispatch_id, {"code": code, "reasons": reasons, "provider_category": CATEGORY_VIDEO})
        return session

    def _append_state_history(self, session: dict[str, Any], state: str, timestamp: str, reason: str) -> None:
        history = list(session.get("state_history") or [])
        history.append({"at": timestamp, "state": state, "reason": reason})
        session["state_history"] = history

    def _audit(
        self,
        session: dict[str, Any],
        event_type: str,
        actor: str,
        dispatch_id: str,
        details: dict[str, Any],
    ) -> None:
        event = {
            "event_id": generate_audit_event_id(),
            "event_type": event_type,
            "at": _now(),
            "dispatch_id": dispatch_id,
            "actor": actor,
            "details": details,
        }
        audit_log = list(session.get("provider_audit_log") or [])
        audit_log.append(event)
        session["provider_audit_log"] = audit_log
        self.store.append_global_provider_audit(
            {
                **event,
                "execution_session_id": ExecutionSessionStore.extract_session_id(session),
                "session_uuid": session.get("session_uuid"),
            }
        )


__all__ = [
    "ProviderRuntimeEngine",
    "RuntimePolicy",
    "DispatchResult",
    "resolve_video_provider",
    "STATE_DISPATCHED",
    "STATE_RUNNING",
    "STATE_COMPLETED",
    "STATE_FAILED",
    "STATE_CANCELLED",
]
