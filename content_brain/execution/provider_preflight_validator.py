"""
Phase 10J-b — mode-aware provider preflight before RUNNING / router call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
from typing import Any

from content_brain.execution.api_connectivity_probe import run_api_probes
from content_brain.execution.browser_connectivity_probe import run_browser_probes
from content_brain.execution.operations_policy import OperationsPolicy
from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.provider_mode_catalog import EXECUTION_MODE_API, EXECUTION_MODE_BROWSER
from content_brain.execution.provider_mode_router import ProviderModeRouter
from content_brain.execution.runway_prompt_composer import apply_runway_prompt_composer_to_session
from content_brain.execution.runway_prompt_composer_config import enable_runway_prompt_composer
from content_brain.execution.session_prompt_adapter import SessionPromptAdapter
from content_brain.execution.session_store import ExecutionSessionStore

PREFLIGHT_VERSION = "10j_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

CHECK_REJECT_CODES: dict[str, str] = {
    "PROVIDER_FAMILY_RESOLVED": "INVALID_PROVIDER",
    "EXECUTION_MODE_SUPPORTED": "EXECUTION_MODE_UNSUPPORTED",
    "ROUTER_KEY_RESOLVED": "PROVIDER_NOT_IMPLEMENTED",
    "ROUTER_IMPLEMENTED": "PROVIDER_NOT_IMPLEMENTED",
    "REGISTRY_ENTRY": "PROVIDER_REGISTRY_MISSING",
    "PROMPT_BUNDLE": "PROMPT_ADAPTER_FAILED",
    "CLIP_COUNT_CAP": "CLIP_COUNT_MISMATCH",
    "ARTIFACT_DIR_WRITABLE": "ARTIFACT_DIR_NOT_WRITABLE",
    "DISPATCH_ATTEMPTS": "RETRY_EXHAUSTED",
    "BROWSER_AVAILABLE": "BROWSER_UNAVAILABLE",
    "BROWSER_PROFILE": "BROWSER_PROFILE_MISSING",
    "BROWSER_SESSION_VALID": "BROWSER_SESSION_INVALID",
    "BROWSER_AUTOMATION_READY": "BROWSER_AUTOMATION_NOT_READY",
    "DOWNLOAD_PATH_READY": "DOWNLOAD_PATH_NOT_WRITABLE",
    "BROWSER_CONCURRENCY": "BROWSER_CONCURRENCY_LIMIT",
    "API_KEY_PRESENT": "CREDENTIALS_MISSING",
    "API_ENDPOINT_CONFIGURED": "API_ENDPOINT_NOT_CONFIGURED",
    "API_CONNECTIVITY_PROBE": "API_CONNECTIVITY_FAILED",
    "API_POLLING_SUPPORTED": "API_POLLING_NOT_SUPPORTED",
    "RUNWAY_API_KEY_MISSING": "CREDENTIALS_MISSING",
    "RUNWAY_API_DISABLED": "PROVIDER_DISABLED",
    "RUNWAY_BROWSER_DISABLED": "PROVIDER_DISABLED",
    "RUNWAY_API_BASE_URL_MISSING": "API_ENDPOINT_NOT_CONFIGURED",
    "RUNWAY_API_BASE_URL_INVALID": "API_ENDPOINT_NOT_CONFIGURED",
    "RUNWAY_CAPABILITY_UNSUPPORTED": "CAPABILITY_RUNTIME_UNSUPPORTED",
    "RUNWAY_CAPABILITY_RUNTIME_GAP": "CAPABILITY_RUNTIME_UNSUPPORTED",
    "RUNWAY_I2V_DRIFT": "CAPABILITY_RUNTIME_UNSUPPORTED",
    "RUNWAY_BROWSER_PROBE": "BROWSER_UNAVAILABLE",
    "RUNWAY_MODE_UNSUPPORTED": "EXECUTION_MODE_UNSUPPORTED",
    "HAILUO_API_NOT_IMPLEMENTED": "PROVIDER_NOT_IMPLEMENTED",
    "HAILUO_API_PLANNED": "PROVIDER_NOT_IMPLEMENTED",
    "HAILUO_API_KEY_MISSING": "CREDENTIALS_MISSING",
    "HAILUO_API_BASE_URL_INVALID": "API_ENDPOINT_NOT_CONFIGURED",
    "HAILUO_BROWSER_DISABLED": "PROVIDER_DISABLED",
    "HAILUO_BROWSER_PROBE": "BROWSER_UNAVAILABLE",
    "HAILUO_CAPABILITY_UNSUPPORTED": "CAPABILITY_RUNTIME_UNSUPPORTED",
    "HAILUO_CAPABILITY_RUNTIME_GAP": "CAPABILITY_RUNTIME_UNSUPPORTED",
    "HAILUO_I2V_DRIFT": "CAPABILITY_RUNTIME_UNSUPPORTED",
    "HAILUO_MODE_UNSUPPORTED": "EXECUTION_MODE_UNSUPPORTED",
    "MINIMAX_API_STUB": "PROVIDER_NOT_IMPLEMENTED",
    "MINIMAX_API_NOT_IMPLEMENTED": "PROVIDER_NOT_IMPLEMENTED",
    "MINIMAX_API_DISABLED": "PROVIDER_DISABLED",
    "MINIMAX_API_KEY_MISSING": "CREDENTIALS_MISSING",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _check(check_id: str, passed: bool, message: str = "") -> dict[str, Any]:
    return {"id": check_id, "passed": passed, "message": message}


@dataclass
class PreflightResult:
    passed: bool
    checked_at: str
    provider_family: str | None = None
    provider_execution_mode: str | None = None
    provider_resolved: str | None = None
    learning_key: str | None = None
    mode_resolution: dict[str, Any] | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    runway_preflight: dict[str, Any] | None = None
    hailuo_preflight: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "passed": self.passed,
            "checked_at": self.checked_at,
            "preflight_version": PREFLIGHT_VERSION,
            "provider_family": self.provider_family,
            "provider_execution_mode": self.provider_execution_mode,
            "provider_resolved": self.provider_resolved,
            "learning_key": self.learning_key,
            "mode_resolution": self.mode_resolution,
            "checks": self.checks,
            "reject_code": self.reject_code,
            "reject_reasons": self.reject_reasons,
        }
        if self.runway_preflight is not None:
            payload["runway_preflight"] = self.runway_preflight
        if self.hailuo_preflight is not None:
            payload["hailuo_preflight"] = self.hailuo_preflight
        return payload


class ProviderPreflightValidator:
    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        mode_router: ProviderModeRouter | None = None,
        project_root: str | Path | None = None,
    ):
        self.store = store
        self.project_root = Path(project_root or store.project_root).resolve()
        self.mode_router = mode_router or ProviderModeRouter(project_root=self.project_root)
        self.adapter = SessionPromptAdapter()

    def validate(
        self,
        session: dict[str, Any],
        policy: OperationsPolicy | None = None,
        *,
        execution_mode_override: str | None = None,
        skip_browser_probes: bool = False,
        skip_api_connectivity: bool = False,
        active_browser_jobs: int | None = None,
    ) -> PreflightResult:
        policy = policy or OperationsPolicy()
        checks: list[dict[str, Any]] = []
        checked_at = _now()

        resolution = self.mode_router.resolve(session, execution_mode_override=execution_mode_override)
        if not resolution:
            family_hint = _dict(_dict(session.get("provider_selection")).get("category_selections"))
            checks.append(
                _check(
                    "PROVIDER_FAMILY_RESOLVED",
                    False,
                    f"Could not resolve provider family/mode for session (provider={session.get('provider')}).",
                )
            )
            return self._fail(checks, checked_at)

        checks.append(
            _check(
                "PROVIDER_FAMILY_RESOLVED",
                True,
                f"Family resolved: {resolution.provider_family}",
            )
        )
        checks.append(
            _check(
                "EXECUTION_MODE_SUPPORTED",
                resolution.provider_execution_mode in self.mode_router.catalog.supported_modes(resolution.provider_family),
                f"Mode: {resolution.provider_execution_mode}",
            )
        )
        checks.append(
            _check(
                "ROUTER_KEY_RESOLVED",
                bool(resolution.router_key),
                f"Router key: {resolution.router_key}",
            )
        )

        implemented, impl_msg = self.mode_router.router_implementation_status(resolution)
        checks.append(_check("ROUTER_IMPLEMENTED", implemented, impl_msg or "Router implemented"))
        if not implemented:
            return self._finalize(checks, checked_at, resolution, fail_early=True)

        registry_entry = self._lookup_registry(resolution.router_key)
        checks.append(
            _check(
                "REGISTRY_ENTRY",
                registry_entry is not None,
                f"Registry entry for {resolution.router_key}" if registry_entry else f"Missing registry: {resolution.router_key}",
            )
        )

        bundle_error = self._probe_prompt_bundle(session, resolution.router_key, policy)
        if bundle_error:
            checks.append(_check("PROMPT_BUNDLE", False, bundle_error))
        else:
            checks.append(_check("PROMPT_BUNDLE", True, "Prompt adapter dry-run OK"))

        clip_error = self._probe_clip_cap(session, policy)
        if clip_error:
            checks.append(_check("CLIP_COUNT_CAP", False, clip_error))
        else:
            checks.append(_check("CLIP_COUNT_CAP", True, "Clip count within cap"))

        artifact_ok, artifact_msg = self._probe_artifact_dir(session)
        checks.append(_check("ARTIFACT_DIR_WRITABLE", artifact_ok, artifact_msg))

        attempts_ok, attempts_msg = self._probe_dispatch_attempts(session, policy)
        checks.append(_check("DISPATCH_ATTEMPTS", attempts_ok, attempts_msg))

        if resolution.provider_execution_mode == EXECUTION_MODE_BROWSER:
            mode_checks, mode_fail = self._run_browser_checks(
                resolution,
                policy,
                skip_browser_probes=skip_browser_probes,
                active_browser_jobs=active_browser_jobs,
            )
            checks.extend(mode_checks)
            if mode_fail:
                return self._finalize(checks, checked_at, resolution, fail_early=True)

        if resolution.provider_execution_mode == EXECUTION_MODE_API:
            mode_checks, mode_fail = self._run_api_checks(
                resolution,
                skip_connectivity=skip_api_connectivity,
            )
            checks.extend(mode_checks)
            if mode_fail:
                return self._finalize(checks, checked_at, resolution, fail_early=True)

        runway_preflight_block: dict[str, Any] | None = None
        if resolution.provider_family == "runway":
            runway_preflight_block, runway_checks, runway_fail = self._run_runway_checks(
                session,
                resolution,
                skip_browser_probes=skip_browser_probes,
            )
            checks.extend(runway_checks)
            if runway_fail:
                return self._finalize(
                    checks,
                    checked_at,
                    resolution,
                    fail_early=True,
                    runway_preflight=runway_preflight_block,
                )

        hailuo_preflight_block: dict[str, Any] | None = None
        if resolution.provider_family in {"hailuo", "minimax"}:
            hailuo_preflight_block, hailuo_checks, hailuo_fail = self._run_hailuo_checks(
                session,
                resolution,
                skip_browser_probes=skip_browser_probes,
            )
            checks.extend(hailuo_checks)
            if hailuo_fail:
                return self._finalize(
                    checks,
                    checked_at,
                    resolution,
                    fail_early=True,
                    runway_preflight=runway_preflight_block,
                    hailuo_preflight=hailuo_preflight_block,
                )

        return self._finalize(
            checks,
            checked_at,
            resolution,
            fail_early=False,
            runway_preflight=runway_preflight_block,
            hailuo_preflight=hailuo_preflight_block,
        )

    def _run_browser_checks(
        self,
        resolution: Any,
        policy: OperationsPolicy,
        *,
        skip_browser_probes: bool,
        active_browser_jobs: int | None,
    ) -> tuple[list[dict[str, Any]], bool]:
        checks: list[dict[str, Any]] = []
        if skip_browser_probes:
            checks.append(_check("BROWSER_AVAILABLE", True, "Browser probes skipped (test mode)"))
            return checks, False

        entry = self.mode_router.catalog.get_family(resolution.provider_family) or {}
        browser_config = _dict(entry.get("browser_config"))
        probe = run_browser_probes(browser_config, project_root=self.project_root)
        checks.extend(probe.checks)

        active = active_browser_jobs if active_browser_jobs is not None else self._count_active_browser_jobs()
        concurrency_ok = active < policy.max_concurrent_browser_jobs
        checks.append(
            _check(
                "BROWSER_CONCURRENCY",
                concurrency_ok,
                f"Active browser jobs: {active} (max {policy.max_concurrent_browser_jobs})",
            )
        )
        if not probe.passed or not concurrency_ok:
            return checks, True
        return checks, False

    def _run_api_checks(
        self,
        resolution: Any,
        *,
        skip_connectivity: bool,
    ) -> tuple[list[dict[str, Any]], bool]:
        entry = self.mode_router.catalog.get_family(resolution.provider_family) or {}
        api_config = _dict(entry.get("api_config"))
        probe = run_api_probes(api_config, skip_connectivity=skip_connectivity)
        return probe.checks, not probe.passed

    def _run_runway_checks(
        self,
        session: dict[str, Any],
        resolution: Any,
        *,
        skip_browser_probes: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        from content_brain.execution.runway_preflight import RunwayPreflightEngine

        runway = RunwayPreflightEngine(self.project_root).evaluate(
            session,
            mode=resolution.provider_execution_mode,
            provider_id=resolution.router_key,
            skip_browser_probes=skip_browser_probes,
        )
        block = runway.to_dict()
        runway_checks: list[dict[str, Any]] = []
        for issue in runway.blocking_issues:
            check_id = str(issue.get("check_id") or issue.get("code") or "RUNWAY_PREFLIGHT")
            message = str(issue.get("message") or check_id)
            runway_checks.append(_check(check_id, False, message))
        return block, runway_checks, not runway.ready

    def _run_hailuo_checks(
        self,
        session: dict[str, Any],
        resolution: Any,
        *,
        skip_browser_probes: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        from content_brain.execution.hailuo_preflight import HailuoPreflightEngine

        hailuo = HailuoPreflightEngine(self.project_root).evaluate(
            session,
            mode=resolution.provider_execution_mode,
            provider_id=resolution.router_key,
            skip_browser_probes=skip_browser_probes,
        )
        block = hailuo.to_dict()
        hailuo_checks: list[dict[str, Any]] = []
        for issue in hailuo.blocking_issues:
            check_id = str(issue.get("check_id") or issue.get("code") or "HAILUO_PREFLIGHT")
            message = str(issue.get("message") or check_id)
            hailuo_checks.append(_check(check_id, False, message))
        return block, hailuo_checks, not hailuo.ready

    def _lookup_registry(self, router_key: str) -> dict[str, Any] | None:
        try:
            from core.provider_registry_engine import ProviderRegistryEngine

            engine = ProviderRegistryEngine()
            return engine.get_provider_info("video", router_key)
        except Exception:
            return None

    def _probe_prompt_bundle(
        self,
        session: dict[str, Any],
        router_key: str,
        policy: OperationsPolicy,
    ) -> str | None:
        try:
            if enable_runway_prompt_composer(session):
                session = apply_runway_prompt_composer_to_session(session)
            bundle = self.adapter.build(session, router_key)
            if bundle.clip_count > policy.max_clips_cap:
                return f"Clip count {bundle.clip_count} exceeds cap {policy.max_clips_cap}"
        except ValueError as exc:
            return str(exc)
        except Exception as exc:
            return f"PROMPT_ADAPTER_FAILED: {exc}"
        return None

    def _probe_clip_cap(self, session: dict[str, Any], policy: OperationsPolicy) -> str | None:
        brief = _dict(session.get("brief_snapshot"))
        format_plan = _dict(brief.get("video_format_plan"))
        simulation = _dict(session.get("simulation_report"))
        try:
            target = int(format_plan.get("clip_count") or simulation.get("estimated_clip_count") or 0)
        except (TypeError, ValueError):
            target = 0
        if target and target > policy.max_clips_cap:
            return f"Target clip_count {target} exceeds cap {policy.max_clips_cap}"
        return None

    def _probe_artifact_dir(self, session: dict[str, Any]) -> tuple[bool, str]:
        session_id = ExecutionSessionStore.extract_session_id(session)
        try:
            path = self.store.artifact_dir(session_id, CATEGORY_VIDEO)
            probe = path / ".preflight_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True, f"Artifact dir writable: {path}"
        except OSError as exc:
            return False, str(exc)

    def _probe_dispatch_attempts(self, session: dict[str, Any], policy: OperationsPolicy) -> tuple[bool, str]:
        runtime = _dict(session.get("execution_runtime"))
        retry = _dict(runtime.get("retry"))
        used = int(retry.get("dispatch_attempts_used") or 0)
        if used >= policy.max_dispatch_attempts:
            return False, f"Dispatch attempts exhausted ({used}/{policy.max_dispatch_attempts})"
        return True, f"Dispatch attempts OK ({used}/{policy.max_dispatch_attempts})"

    def _count_active_browser_jobs(self) -> int:
        index_path = self.project_root / "storage" / "content_brain" / "execution" / "runtime" / "active_jobs.json"
        if not index_path.exists():
            return 0
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return 0
        count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            mode = str(item.get("provider_execution_mode") or "").lower()
            if mode == EXECUTION_MODE_BROWSER:
                count += 1
        return count

    def _fail(self, checks: list[dict[str, Any]], checked_at: str) -> PreflightResult:
        reject_code, reasons = self._reject_from_checks(checks)
        return PreflightResult(
            passed=False,
            checked_at=checked_at,
            checks=checks,
            reject_code=reject_code,
            reject_reasons=reasons,
        )

    def _finalize(
        self,
        checks: list[dict[str, Any]],
        checked_at: str,
        resolution: Any,
        *,
        fail_early: bool,
        runway_preflight: dict[str, Any] | None = None,
        hailuo_preflight: dict[str, Any] | None = None,
    ) -> PreflightResult:
        failed = [item for item in checks if not item.get("passed")]
        passed = not failed
        reject_code = None
        reasons: list[str] = []
        if failed:
            reject_code, reasons = self._reject_from_checks(checks)
        return PreflightResult(
            passed=passed,
            checked_at=checked_at,
            provider_family=resolution.provider_family,
            provider_execution_mode=resolution.provider_execution_mode,
            provider_resolved=resolution.router_key,
            learning_key=resolution.learning_key,
            mode_resolution=resolution.to_dict(),
            checks=checks,
            reject_code=reject_code,
            reject_reasons=reasons,
            runway_preflight=runway_preflight,
            hailuo_preflight=hailuo_preflight,
        )

    def _reject_from_checks(self, checks: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
        reasons: list[str] = []
        reject_code = "PREFLIGHT_FAILED"
        for item in checks:
            if item.get("passed"):
                continue
            check_id = str(item.get("id") or "")
            message = str(item.get("message") or check_id)
            reasons.append(message)
            reject_code = CHECK_REJECT_CODES.get(check_id, reject_code)
            break
        return reject_code, reasons


__all__ = [
    "PREFLIGHT_VERSION",
    "PreflightResult",
    "ProviderPreflightValidator",
]
