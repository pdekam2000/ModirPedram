"""
Phase 11E-a — Runway-specific preflight checks (config, capability drift, mode readiness).

Does not call Runway API or run browser automation by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.browser_connectivity_probe import run_browser_probes
from content_brain.execution.provider_mode_catalog import EXECUTION_MODE_API, EXECUTION_MODE_BROWSER
from content_brain.execution.provider_categories import CATEGORY_VIDEO
from content_brain.execution.runway_config import (
    RUNWAY_API_ROUTER_KEY,
    RUNWAY_BROWSER_ROUTER_KEY,
    RUNWAY_FAMILY,
    RunwayConfigResolver,
)
from content_brain.providers.provider_capability_registry import (
    CAPABILITY_IMAGE_TO_VIDEO,
    CAPABILITY_TEXT_TO_VIDEO,
    ProviderCapabilityRegistry,
    normalize_provider_id,
)

PREFLIGHT_VERSION = "11e_a_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Runtime-supported capabilities for Runway (11E-a scope — I2V excluded).
RUNWAY_RUNTIME_SUPPORTED_CAPABILITIES: frozenset[str] = frozenset({
    CAPABILITY_TEXT_TO_VIDEO,
    "asset_download",
})

I2V_DRIFT_NOTE = (
    "11A declares image_to_video for Runway but runtime does not implement it yet (Phase 11E-a)."
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
class RunwayPreflightResult:
    ready: bool
    mode: str
    provider_id: str
    blocking_issues: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    capability_supported: bool = False
    runtime_supported: bool = False
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
            "blocking_issues": list(self.blocking_issues),
            "warnings": list(self.warnings),
            "capability_supported": self.capability_supported,
            "runtime_supported": self.runtime_supported,
            "requested_capability": self.requested_capability,
            "checked_at": self.checked_at,
            "config_snapshot": dict(self.config_snapshot),
            "i2v_drift_detected": self.i2v_drift_detected,
            "i2v_drift_note": I2V_DRIFT_NOTE if self.i2v_drift_detected else None,
        }


class RunwayPreflightEngine:
    """Structured Runway preflight — metadata and local probes only."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        capability_registry: ProviderCapabilityRegistry | None = None,
        config_resolver: RunwayConfigResolver | None = None,
    ):
        self.project_root = Path(project_root or ".").resolve()
        self.capabilities = capability_registry or ProviderCapabilityRegistry.load(self.project_root)
        self.config = config_resolver or RunwayConfigResolver(self.project_root)

    def evaluate(
        self,
        session: dict[str, Any] | None = None,
        *,
        mode: str | None = None,
        provider_id: str | None = None,
        capability: str | None = None,
        skip_browser_probes: bool = True,
    ) -> RunwayPreflightResult:
        snapshot = self.config.resolve()
        session = session or {}

        category_selections = _dict(_dict(session.get("provider_selection")).get("category_selections"))
        video_sel = _dict(category_selections.get(CATEGORY_VIDEO))
        resolved_mode = str(
            mode
            or video_sel.get("execution_mode")
            or category_selections.get("execution_mode")
            or snapshot.preferred_mode
        ).lower()
        if resolved_mode not in {EXECUTION_MODE_API, EXECUTION_MODE_BROWSER}:
            resolved_mode = snapshot.preferred_mode

        resolved_provider = normalize_provider_id(
            provider_id
            or self.config.router_key_for_mode(resolved_mode)
            or snapshot.active_video_provider
        )
        requested = str(capability or infer_requested_capability(session)).strip().lower()

        blocking: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        registry_cap_supported = self.capabilities.supports(resolved_provider, requested)
        runtime_cap_supported = requested in RUNWAY_RUNTIME_SUPPORTED_CAPABILITIES

        i2v_declared = self.capabilities.supports(resolved_provider, CAPABILITY_IMAGE_TO_VIDEO)
        i2v_runtime = CAPABILITY_IMAGE_TO_VIDEO in RUNWAY_RUNTIME_SUPPORTED_CAPABILITIES
        i2v_drift = i2v_declared and not i2v_runtime

        if i2v_drift:
            drift_warning = _issue(
                "CAPABILITY_RUNTIME_UNSUPPORTED",
                I2V_DRIFT_NOTE,
                check_id="RUNWAY_I2V_DRIFT",
            )
            if requested == CAPABILITY_IMAGE_TO_VIDEO:
                blocking.append(drift_warning)
            else:
                warnings.append(drift_warning)

        if not registry_cap_supported:
            blocking.append(
                _issue(
                    "CAPABILITY_RUNTIME_UNSUPPORTED",
                    f"Capability {requested!r} not declared for provider {resolved_provider}.",
                    check_id="RUNWAY_CAPABILITY_UNSUPPORTED",
                )
            )
        elif not runtime_cap_supported:
            blocking.append(
                _issue(
                    "CAPABILITY_RUNTIME_UNSUPPORTED",
                    f"Capability {requested!r} declared in 11A but not runtime-supported for Runway.",
                    check_id="RUNWAY_CAPABILITY_RUNTIME_GAP",
                )
            )

        if resolved_mode == EXECUTION_MODE_API:
            self._evaluate_api_mode(snapshot, blocking, warnings)
        elif resolved_mode == EXECUTION_MODE_BROWSER:
            self._evaluate_browser_mode(snapshot, blocking, warnings, skip_browser_probes=skip_browser_probes)
        else:
            blocking.append(
                _issue(
                    "EXECUTION_MODE_UNSUPPORTED",
                    f"Unsupported Runway mode: {resolved_mode}",
                    check_id="RUNWAY_MODE_UNSUPPORTED",
                )
            )

        if (
            resolved_provider == RUNWAY_BROWSER_ROUTER_KEY
            and not snapshot.browser_enabled_in_registry
        ):
            blocking.append(
                _issue(
                    "PROVIDER_DISABLED",
                    "Runway browser provider is disabled in provider_registry.json.",
                    check_id="RUNWAY_BROWSER_DISABLED",
                )
            )

        ready = len(blocking) == 0
        return RunwayPreflightResult(
            ready=ready,
            mode=resolved_mode,
            provider_id=resolved_provider,
            blocking_issues=blocking,
            warnings=warnings,
            capability_supported=registry_cap_supported,
            runtime_supported=runtime_cap_supported and registry_cap_supported,
            requested_capability=requested,
            checked_at=_now(),
            config_snapshot=snapshot.to_dict(),
            i2v_drift_detected=i2v_drift,
        )

    def _evaluate_api_mode(
        self,
        snapshot: Any,
        blocking: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> None:
        if not snapshot.api_enabled_in_registry:
            blocking.append(
                _issue(
                    "PROVIDER_DISABLED",
                    "Runway API mode is disabled in provider_registry.json (enabled=false).",
                    check_id="RUNWAY_API_DISABLED",
                )
            )

        if not snapshot.api_key_present:
            blocking.append(
                _issue(
                    "CREDENTIALS_MISSING",
                    f"Missing {snapshot.api_key_env} for Runway API mode.",
                    check_id="RUNWAY_API_KEY_MISSING",
                )
            )

        if not snapshot.api_base_url:
            blocking.append(
                _issue(
                    "API_ENDPOINT_NOT_CONFIGURED",
                    "Runway API base URL is not configured.",
                    check_id="RUNWAY_API_BASE_URL_MISSING",
                )
            )
        elif not snapshot.api_base_url_valid:
            blocking.append(
                _issue(
                    "API_ENDPOINT_NOT_CONFIGURED",
                    f"Invalid Runway API base URL from {snapshot.api_base_url_source}: {snapshot.api_base_url!r}",
                    check_id="RUNWAY_API_BASE_URL_INVALID",
                )
            )
        elif snapshot.api_base_url_source.startswith("catalog."):
            warnings.append(
                _issue(
                    "API_ENDPOINT_NOT_CONFIGURED",
                    f"Using catalog default endpoint ({snapshot.api_base_url}); set {snapshot.endpoint_env} to override.",
                    check_id="RUNWAY_API_BASE_URL_DEFAULT",
                )
            )

        if snapshot.active_video_provider == RUNWAY_API_ROUTER_KEY and not snapshot.api_enabled_in_registry:
            warnings.append(
                _issue(
                    "PROVIDER_DISABLED",
                    "Active video provider points to Runway API but API is disabled in registry.",
                    check_id="RUNWAY_ACTIVE_API_DISABLED",
                )
            )

    def _evaluate_browser_mode(
        self,
        snapshot: Any,
        blocking: list[dict[str, str]],
        warnings: list[dict[str, str]],
        *,
        skip_browser_probes: bool,
    ) -> None:
        if snapshot.active_video_provider not in {RUNWAY_BROWSER_ROUTER_KEY, RUNWAY_FAMILY}:
            if normalize_provider_id(snapshot.active_video_provider) == RUNWAY_API_ROUTER_KEY:
                warnings.append(
                    _issue(
                        "PROVIDER_DISABLED",
                        "Active default is Runway API; operator policy keeps browser as runtime authority.",
                        check_id="RUNWAY_ACTIVE_NOT_BROWSER",
                    )
                )

        if skip_browser_probes:
            warnings.append(
                _issue(
                    "BROWSER_UNAVAILABLE",
                    "Browser probes skipped (test/offline mode).",
                    check_id="RUNWAY_BROWSER_PROBES_SKIPPED",
                )
            )
            return

        family_entry = self.config.mode_catalog.get_family(RUNWAY_FAMILY) or {}
        browser_config = _dict(family_entry.get("browser_config"))
        probe = run_browser_probes(browser_config, project_root=self.project_root)
        if not probe.passed:
            code = probe.reject_code or "BROWSER_UNAVAILABLE"
            blocking.append(
                _issue(
                    code,
                    probe.message or "Browser preflight failed.",
                    check_id="RUNWAY_BROWSER_PROBE",
                )
            )


__all__ = [
    "PREFLIGHT_VERSION",
    "I2V_DRIFT_NOTE",
    "RUNWAY_RUNTIME_SUPPORTED_CAPABILITIES",
    "RunwayPreflightResult",
    "RunwayPreflightEngine",
    "infer_requested_capability",
]
