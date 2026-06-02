"""
Phase 11F-a — Hailuo / MiniMax preflight checks (config, capability drift, mode readiness).

Does not call Hailuo/MiniMax API or run browser automation by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.browser_connectivity_probe import run_browser_probes
from content_brain.execution.hailuo_config import (
    HAILUO_API_ROUTER_KEY,
    HAILUO_BROWSER_ROUTER_KEY,
    HAILUO_FAMILY,
    MINIMAX_API_ROUTER_KEY,
    MINIMAX_FAMILY,
    HailuoConfigResolver,
    infer_provider_family,
    normalize_hailuo_provider_id,
)
from content_brain.execution.provider_mode_catalog import EXECUTION_MODE_API, EXECUTION_MODE_BROWSER
from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.provider_mode_router import ProviderModeRouter
from content_brain.providers.provider_capability_registry import (
    CAPABILITY_IMAGE_TO_VIDEO,
    CAPABILITY_TEXT_TO_VIDEO,
    ProviderCapabilityRegistry,
)

PREFLIGHT_VERSION = "11f_a_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

HAILUO_RUNTIME_SUPPORTED_CAPABILITIES: frozenset[str] = frozenset({
    CAPABILITY_TEXT_TO_VIDEO,
    "asset_download",
})

I2V_DRIFT_NOTE = (
    "11A declares image_to_video for Hailuo but runtime does not implement it yet (Phase 11F-a)."
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _issue(code: str, message: str, *, check_id: str | None = None) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "check_id": check_id or code,
    }


def infer_requested_capability(session: dict[str, Any] | None) -> str:
    session = session or {}
    brief = _dict(session.get("brief_snapshot"))
    format_plan = _dict(brief.get("video_format_plan"))
    explicit = (
        format_plan.get("capability")
        or format_plan.get("generation_capability")
        or _dict(session.get("provider_selection")).get("capability")
    )
    if explicit:
        return str(explicit).strip().lower()

    format_type = str(format_plan.get("format_type") or "").lower()
    if "image_to_video" in format_type or "i2v" in format_type:
        return CAPABILITY_IMAGE_TO_VIDEO
    return CAPABILITY_TEXT_TO_VIDEO


@dataclass
class HailuoPreflightResult:
    ready: bool
    mode: str
    provider_id: str
    provider_family: str
    blocking_issues: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    capability_supported: bool = False
    runtime_supported: bool = False
    api_implemented: bool = False
    browser_available: bool | None = None
    requested_capability: str = CAPABILITY_TEXT_TO_VIDEO
    checked_at: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    i2v_drift_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflight_version": PREFLIGHT_VERSION,
            "ready": self.ready,
            "mode": self.mode,
            "provider_id": self.provider_id,
            "provider_family": self.provider_family,
            "blocking_issues": list(self.blocking_issues),
            "warnings": list(self.warnings),
            "capability_supported": self.capability_supported,
            "runtime_supported": self.runtime_supported,
            "api_implemented": self.api_implemented,
            "browser_available": self.browser_available,
            "requested_capability": self.requested_capability,
            "checked_at": self.checked_at,
            "config_snapshot": dict(self.config_snapshot),
            "i2v_drift_detected": self.i2v_drift_detected,
            "i2v_drift_note": I2V_DRIFT_NOTE if self.i2v_drift_detected else None,
        }


class HailuoPreflightEngine:
    """Structured Hailuo/MiniMax preflight — metadata and local probes only."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        capability_registry: ProviderCapabilityRegistry | None = None,
        config_resolver: HailuoConfigResolver | None = None,
        mode_router: ProviderModeRouter | None = None,
    ):
        self.project_root = Path(project_root or ".").resolve()
        self.capabilities = capability_registry or ProviderCapabilityRegistry.load(self.project_root)
        self.config = config_resolver or HailuoConfigResolver(self.project_root)
        self.mode_router = mode_router or ProviderModeRouter(project_root=self.project_root)

    def evaluate(
        self,
        session: dict[str, Any] | None = None,
        *,
        mode: str | None = None,
        provider_id: str | None = None,
        capability: str | None = None,
        skip_browser_probes: bool = True,
    ) -> HailuoPreflightResult:
        snapshot = self.config.resolve()
        session = session or {}

        category_selections = _dict(_dict(session.get("provider_selection")).get("category_selections"))
        video_sel = _dict(category_selections.get(CATEGORY_VIDEO))

        raw_provider = (
            provider_id
            or video_sel.get("provider")
            or session.get("provider")
            or snapshot.hailuo_browser_router_key
        )
        resolved_provider = normalize_hailuo_provider_id(str(raw_provider))
        provider_family = infer_provider_family(resolved_provider) or HAILUO_FAMILY

        resolved_mode = str(
            mode
            or video_sel.get("execution_mode")
            or category_selections.get("execution_mode")
            or (
                snapshot.minimax_preferred_mode
                if provider_family == MINIMAX_FAMILY
                else snapshot.hailuo_preferred_mode
            )
        ).lower()
        if resolved_mode not in {EXECUTION_MODE_API, EXECUTION_MODE_BROWSER}:
            resolved_mode = (
                EXECUTION_MODE_API
                if provider_family == MINIMAX_FAMILY
                else snapshot.hailuo_preferred_mode
            )

        if provider_family == MINIMAX_FAMILY:
            resolved_provider = MINIMAX_API_ROUTER_KEY
            resolved_mode = EXECUTION_MODE_API

        requested = str(capability or infer_requested_capability(session)).strip().lower()

        blocking: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        browser_available: bool | None = None
        api_implemented = False

        registry_cap_supported = self.capabilities.supports(resolved_provider, requested)
        runtime_cap_supported = requested in HAILUO_RUNTIME_SUPPORTED_CAPABILITIES

        i2v_declared = self.capabilities.supports(resolved_provider, CAPABILITY_IMAGE_TO_VIDEO)
        i2v_runtime = CAPABILITY_IMAGE_TO_VIDEO in HAILUO_RUNTIME_SUPPORTED_CAPABILITIES
        i2v_drift = i2v_declared and not i2v_runtime

        if i2v_drift:
            drift_issue = _issue(
                "CAPABILITY_RUNTIME_UNSUPPORTED",
                I2V_DRIFT_NOTE,
                check_id="HAILUO_I2V_DRIFT",
            )
            if requested == CAPABILITY_IMAGE_TO_VIDEO:
                blocking.append(drift_issue)
            else:
                warnings.append(drift_issue)

        if not registry_cap_supported:
            blocking.append(
                _issue(
                    "CAPABILITY_RUNTIME_UNSUPPORTED",
                    f"Capability {requested!r} not declared for provider {resolved_provider}.",
                    check_id="HAILUO_CAPABILITY_UNSUPPORTED",
                )
            )
        elif provider_family == HAILUO_FAMILY and not runtime_cap_supported:
            blocking.append(
                _issue(
                    "CAPABILITY_RUNTIME_UNSUPPORTED",
                    f"Capability {requested!r} declared in 11A but not runtime-supported for Hailuo.",
                    check_id="HAILUO_CAPABILITY_RUNTIME_GAP",
                )
            )

        if provider_family == MINIMAX_FAMILY:
            api_implemented = snapshot.minimax_api_implemented
            self._evaluate_minimax_api(snapshot, blocking, warnings)
        elif resolved_mode == EXECUTION_MODE_API:
            api_implemented = snapshot.hailuo_api_implemented
            self._evaluate_hailuo_api_mode(snapshot, blocking, warnings)
        elif resolved_mode == EXECUTION_MODE_BROWSER:
            api_implemented = False
            browser_available = self._evaluate_hailuo_browser_mode(
                snapshot,
                blocking,
                warnings,
                skip_browser_probes=skip_browser_probes,
            )
        else:
            blocking.append(
                _issue(
                    "EXECUTION_MODE_UNSUPPORTED",
                    f"Unsupported Hailuo mode: {resolved_mode}",
                    check_id="HAILUO_MODE_UNSUPPORTED",
                )
            )

        if (
            provider_family == HAILUO_FAMILY
            and resolved_provider == HAILUO_BROWSER_ROUTER_KEY
            and not snapshot.hailuo_browser_enabled_in_registry
        ):
            blocking.append(
                _issue(
                    "PROVIDER_DISABLED",
                    "Hailuo browser provider is disabled in provider_registry.json.",
                    check_id="HAILUO_BROWSER_DISABLED",
                )
            )

        if not snapshot.active_default_is_runway:
            warnings.append(
                _issue(
                    "PROVIDER_DISABLED",
                    f"Active default video provider is {snapshot.active_video_provider!r}; "
                    "operator policy keeps runway_browser as system default authority.",
                    check_id="HAILUO_ACTIVE_DEFAULT_DRIFT",
                )
            )

        ready = len(blocking) == 0
        return HailuoPreflightResult(
            ready=ready,
            mode=resolved_mode,
            provider_id=resolved_provider,
            provider_family=provider_family,
            blocking_issues=blocking,
            warnings=warnings,
            capability_supported=registry_cap_supported,
            runtime_supported=runtime_cap_supported and registry_cap_supported,
            api_implemented=api_implemented,
            browser_available=browser_available,
            requested_capability=requested,
            checked_at=_now(),
            config_snapshot=snapshot.to_dict(),
            i2v_drift_detected=i2v_drift,
        )

    def _evaluate_hailuo_api_mode(
        self,
        snapshot: Any,
        blocking: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> None:
        blocking.append(
            _issue(
                "PROVIDER_NOT_IMPLEMENTED",
                "Hailuo API mode is metadata-only; no provider implementation exists (Phase 11F-a).",
                check_id="HAILUO_API_NOT_IMPLEMENTED",
            )
        )

        if snapshot.hailuo_api_implementation_status == "planned":
            warnings.append(
                _issue(
                    "PROVIDER_NOT_IMPLEMENTED",
                    f"Hailuo API implementation_status={snapshot.hailuo_api_implementation_status!r} in mode catalog.",
                    check_id="HAILUO_API_PLANNED",
                )
            )

        if not snapshot.hailuo_api_in_registry:
            warnings.append(
                _issue(
                    "PROVIDER_REGISTRY_MISSING",
                    "hailuo_api has no entry in provider_registry.json.",
                    check_id="HAILUO_API_REGISTRY_MISSING",
                )
            )

        if not snapshot.hailuo_api_key_present:
            blocking.append(
                _issue(
                    "CREDENTIALS_MISSING",
                    f"Missing {snapshot.hailuo_api_key_env} for Hailuo API mode.",
                    check_id="HAILUO_API_KEY_MISSING",
                )
            )

        if snapshot.hailuo_api_base_url and not snapshot.hailuo_api_base_url_valid:
            blocking.append(
                _issue(
                    "API_ENDPOINT_NOT_CONFIGURED",
                    f"Invalid Hailuo API base URL from {snapshot.hailuo_api_base_url_source}.",
                    check_id="HAILUO_API_BASE_URL_INVALID",
                )
            )

    def _evaluate_minimax_api(
        self,
        snapshot: Any,
        blocking: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> None:
        if snapshot.minimax_api_implementation_status == "stub":
            blocking.append(
                _issue(
                    "PROVIDER_NOT_IMPLEMENTED",
                    "MiniMax API mode is a stub; provider raises NotImplementedError at runtime.",
                    check_id="MINIMAX_API_STUB",
                )
            )
            warnings.append(
                _issue(
                    "PROVIDER_NOT_IMPLEMENTED",
                    f"MiniMax implementation_status={snapshot.minimax_api_implementation_status!r}.",
                    check_id="MINIMAX_API_STUB_STATUS",
                )
            )
        elif not snapshot.minimax_api_implemented:
            blocking.append(
                _issue(
                    "PROVIDER_NOT_IMPLEMENTED",
                    "MiniMax API mode is not implemented.",
                    check_id="MINIMAX_API_NOT_IMPLEMENTED",
                )
            )

        if not snapshot.minimax_api_enabled_in_registry:
            blocking.append(
                _issue(
                    "PROVIDER_DISABLED",
                    "MiniMax API provider is disabled in provider_registry.json.",
                    check_id="MINIMAX_API_DISABLED",
                )
            )

        if not snapshot.minimax_api_key_present:
            blocking.append(
                _issue(
                    "CREDENTIALS_MISSING",
                    f"Missing {snapshot.minimax_api_key_env} for MiniMax API mode.",
                    check_id="MINIMAX_API_KEY_MISSING",
                )
            )

    def _evaluate_hailuo_browser_mode(
        self,
        snapshot: Any,
        blocking: list[dict[str, str]],
        warnings: list[dict[str, str]],
        *,
        skip_browser_probes: bool,
    ) -> bool | None:
        if skip_browser_probes:
            warnings.append(
                _issue(
                    "BROWSER_UNAVAILABLE",
                    "Browser probes skipped (test/offline mode).",
                    check_id="HAILUO_BROWSER_PROBES_SKIPPED",
                )
            )
            return None

        family_entry = self.config.mode_catalog.get_family(HAILUO_FAMILY) or {}
        browser_config = _dict(family_entry.get("browser_config"))
        probe = run_browser_probes(browser_config, project_root=self.project_root)
        if not probe.passed:
            code = probe.reject_code or "BROWSER_UNAVAILABLE"
            blocking.append(
                _issue(
                    code,
                    probe.message or "Browser preflight failed.",
                    check_id="HAILUO_BROWSER_PROBE",
                )
            )
            return False
        return True


__all__ = [
    "PREFLIGHT_VERSION",
    "I2V_DRIFT_NOTE",
    "HAILUO_RUNTIME_SUPPORTED_CAPABILITIES",
    "HailuoPreflightResult",
    "HailuoPreflightEngine",
    "infer_requested_capability",
]
