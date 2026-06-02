"""
Phase 11H-1a — ElevenLabs preflight probe (no audio generation, no live TTS).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VOICE
from content_brain.providers.provider_capability_registry import (
    CAPABILITY_NARRATION,
    ProviderCapabilityRegistry,
)
from providers.elevenlabs_config import ElevenLabsConfigResolver

PREFLIGHT_VERSION = "11h1a_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

STATUS_READY = "ready"
STATUS_FAILED = "failed"

CODE_CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
CODE_PROVIDER_DISABLED = "PROVIDER_DISABLED"
CODE_PROVIDER_NOT_IMPLEMENTED = "PROVIDER_NOT_IMPLEMENTED"
CODE_CAPABILITY_UNSUPPORTED = "CAPABILITY_RUNTIME_UNSUPPORTED"
CODE_NARRATION_SKIPPED = "NARRATION_SKIPPED"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


@dataclass
class ElevenLabsPreflightResult:
    status: str
    provider: str
    code: str | None = None
    message: str = ""
    ready: bool = False
    checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_summary: dict[str, Any] = field(default_factory=dict)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflight_version": PREFLIGHT_VERSION,
            "status": self.status,
            "provider": self.provider,
            "ready": self.ready,
            "code": self.code,
            "message": self.message,
            "checks": list(self.checks),
            "warnings": list(self.warnings),
            "config_summary": dict(self.config_summary),
            "checked_at": self.checked_at,
        }


def _check(check_id: str, passed: bool, message: str = "") -> dict[str, Any]:
    return {"id": check_id, "passed": passed, "message": message}


class ElevenLabsPreflight:
    """Probe-only preflight for ElevenLabs voice routing."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
        self.config_resolver = ElevenLabsConfigResolver(self.project_root)

    def run(
        self,
        session: dict[str, Any] | None = None,
        *,
        narration_skipped: bool = False,
    ) -> ElevenLabsPreflightResult:
        session = session or {}
        checked_at = _now()
        checks: list[dict[str, Any]] = []
        warnings: list[str] = []

        config = self.config_resolver.resolve(session)
        config_summary = config.to_summary()
        checks.append(
            _check(
                "PROVIDER_ENABLED",
                config.enabled_in_registry,
                "ElevenLabs enabled in provider registry" if config.enabled_in_registry else "ElevenLabs disabled in registry",
            )
        )
        if not config.enabled_in_registry:
            return ElevenLabsPreflightResult(
                status=STATUS_FAILED,
                provider="elevenlabs",
                code=CODE_PROVIDER_DISABLED,
                message="ElevenLabs is disabled in provider registry.",
                ready=False,
                checks=checks,
                config_summary=config_summary,
                checked_at=checked_at,
            )

        registry = ProviderCapabilityRegistry.load(self.project_root)
        supports_narration = registry.supports("elevenlabs", CAPABILITY_NARRATION)
        checks.append(
            _check(
                "CAPABILITY_NARRATION",
                supports_narration,
                "ElevenLabs supports narration capability" if supports_narration else "Narration capability not supported",
            )
        )
        if not supports_narration:
            return ElevenLabsPreflightResult(
                status=STATUS_FAILED,
                provider="elevenlabs",
                code=CODE_CAPABILITY_UNSUPPORTED,
                message="ElevenLabs does not support narration in capability registry.",
                ready=False,
                checks=checks,
                config_summary=config_summary,
                checked_at=checked_at,
            )

        checks.append(
            _check(
                "API_KEY_PRESENT",
                config.has_api_key,
                f"API key env {config.api_key_env} present" if config.has_api_key else f"Missing environment variable: {config.api_key_env}",
            )
        )
        if not config.has_api_key:
            return ElevenLabsPreflightResult(
                status=STATUS_FAILED,
                provider="elevenlabs",
                code=CODE_CREDENTIALS_MISSING,
                message=f"Missing environment variable: {config.api_key_env}",
                ready=False,
                checks=checks,
                config_summary=config_summary,
                checked_at=checked_at,
            )

        checks.append(
            _check(
                "VOICE_ID_RESOLVED",
                bool(config.voice_id),
                f"Voice ID resolved: {config.voice_id[:8]}..." if config.voice_id else "Voice ID missing",
            )
        )

        if narration_skipped:
            warnings.append("Narration adapter returned skipped — no narration segments in brief.")
            checks.append(_check("NARRATION_AVAILABLE", False, "No narration segments available"))
            return ElevenLabsPreflightResult(
                status=STATUS_FAILED,
                provider="elevenlabs",
                code=CODE_NARRATION_SKIPPED,
                message="No narration text available in session brief.",
                ready=False,
                checks=checks,
                warnings=warnings,
                config_summary=config_summary,
                checked_at=checked_at,
            )

        checks.append(_check("PROVIDER_CATEGORY", True, f"Category: {CATEGORY_VOICE}"))
        checks.append(_check("LIVE_TTS_DISABLED", True, "11H-1a preflight only — no live TTS call"))

        return ElevenLabsPreflightResult(
            status=STATUS_READY,
            provider="elevenlabs",
            code=None,
            message="ElevenLabs preflight ready (probe only, no TTS executed).",
            ready=True,
            checks=checks,
            warnings=warnings,
            config_summary=config_summary,
            checked_at=checked_at,
        )


__all__ = [
    "PREFLIGHT_VERSION",
    "STATUS_READY",
    "STATUS_FAILED",
    "CODE_CREDENTIALS_MISSING",
    "ElevenLabsPreflightResult",
    "ElevenLabsPreflight",
]
