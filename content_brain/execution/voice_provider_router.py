"""
Phase 11H-1a — voice-only provider router (route selection + dry-run only, no live TTS).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VOICE, normalize_provider_key
from content_brain.execution.session_narration_adapter import NarrationBundle, SessionNarrationAdapter
from providers.elevenlabs_preflight import ElevenLabsPreflight

ENGINE_NAME = "VoiceProviderRouter"
ENGINE_VERSION = "11h1a_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

ROUTER_SUPPORTED = frozenset({"elevenlabs", "openai_tts", "minimax_tts"})
IMPLEMENTED_PROVIDERS = frozenset({"elevenlabs"})
STUB_PROVIDERS = frozenset({"openai_tts", "minimax_tts"})

REJECT_INVALID_PROVIDER = "INVALID_PROVIDER"
REJECT_PROVIDER_UNSUPPORTED = "PROVIDER_UNSUPPORTED"
REJECT_PROVIDER_NOT_IMPLEMENTED = "PROVIDER_NOT_IMPLEMENTED"
REJECT_NARRATION_SKIPPED = "NARRATION_SKIPPED"


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


@dataclass
class VoiceRouterResult:
    success: bool
    provider: str
    provider_category: str = CATEGORY_VOICE
    executed: bool = False
    dry_run: bool = True
    route_selected: bool = False
    segment_count: int = 0
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    preflight: dict[str, Any] | None = None
    mock_artifacts: list[dict[str, Any]] = field(default_factory=list)
    narration_bundle: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "provider": self.provider,
            "provider_category": self.provider_category,
            "executed": self.executed,
            "dry_run": self.dry_run,
            "route_selected": self.route_selected,
            "segment_count": self.segment_count,
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
            "preflight": self.preflight,
            "mock_artifacts": list(self.mock_artifacts),
            "narration_bundle": self.narration_bundle,
            "metadata": dict(self.metadata),
        }


class VoiceProviderRouter:
    """Voice-only router — 11H-1a selects routes and returns dry-run results only."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
        self.narration_adapter = SessionNarrationAdapter()
        self.elevenlabs_preflight = ElevenLabsPreflight(self.project_root)

    @classmethod
    def list_supported_providers(cls) -> list[str]:
        return sorted(ROUTER_SUPPORTED)

    def resolve_voice_provider(self, session: dict[str, Any]) -> tuple[str | None, str | None]:
        provider_selection = _dict(session.get("provider_selection"))
        category_selections = _dict(provider_selection.get("category_selections"))
        voice_sel = _dict(category_selections.get(CATEGORY_VOICE))

        raw = _first(
            voice_sel.get("provider"),
            provider_selection.get("primary_provider"),
            session.get("provider"),
        )
        if not raw:
            return None, REJECT_INVALID_PROVIDER

        normalized = normalize_provider_key(raw)
        if normalized not in ROUTER_SUPPORTED:
            return normalized, REJECT_PROVIDER_UNSUPPORTED
        return normalized, None

    def route(
        self,
        session: dict[str, Any],
        *,
        provider_override: str | None = None,
        artifact_root: str | Path | None = None,
        dry_run: bool = True,
    ) -> VoiceRouterResult:
        """
        Select voice provider route and return structured dry-run result.

        Never calls ElevenLabsVoiceProvider.generate_voice or any live TTS API.
        """
        provider, reject_code = self.resolve_voice_provider(session)
        if provider_override:
            candidate = normalize_provider_key(provider_override)
            if candidate not in ROUTER_SUPPORTED:
                return VoiceRouterResult(
                    success=False,
                    provider=candidate,
                    reject_code=REJECT_PROVIDER_UNSUPPORTED,
                    reject_reasons=[f"Unsupported voice provider: {candidate}"],
                    metadata={"router_version": ENGINE_VERSION},
                )
            provider = candidate

        if reject_code and not provider_override:
            return VoiceRouterResult(
                success=False,
                provider=provider or "",
                reject_code=reject_code,
                reject_reasons=[reject_code],
                metadata={"router_version": ENGINE_VERSION},
            )

        assert provider is not None
        bundle = self.narration_adapter.build(session)

        if provider in STUB_PROVIDERS:
            return VoiceRouterResult(
                success=False,
                provider=provider,
                route_selected=True,
                dry_run=True,
                executed=False,
                segment_count=bundle.segment_count,
                reject_code=REJECT_PROVIDER_NOT_IMPLEMENTED,
                reject_reasons=[f"Voice provider {provider} is registered as stub only in 11H-1a."],
                narration_bundle=bundle.to_dict(),
                metadata={
                    "router_version": ENGINE_VERSION,
                    "implementation_status": "stub",
                },
            )

        if bundle.skipped:
            return VoiceRouterResult(
                success=False,
                provider=provider,
                route_selected=True,
                dry_run=True,
                executed=False,
                segment_count=0,
                reject_code=REJECT_NARRATION_SKIPPED,
                reject_reasons=list(bundle.warnings) or ["No narration segments in brief."],
                narration_bundle=bundle.to_dict(),
                metadata={"router_version": ENGINE_VERSION, "status": "skipped"},
            )

        preflight = self.elevenlabs_preflight.run(session, narration_skipped=False)
        preflight_dict = preflight.to_dict()

        if not preflight.ready:
            return VoiceRouterResult(
                success=False,
                provider=provider,
                route_selected=True,
                dry_run=True,
                executed=False,
                segment_count=bundle.segment_count,
                reject_code=preflight.code,
                reject_reasons=[preflight.message],
                preflight=preflight_dict,
                narration_bundle=bundle.to_dict(),
                metadata={"router_version": ENGINE_VERSION},
            )

        root = Path(artifact_root) if artifact_root else self.project_root / "storage" / "content_brain" / "execution" / "artifacts" / "dry_run_voice"
        mock_artifacts = self._build_mock_artifacts(bundle, provider, root)

        return VoiceRouterResult(
            success=True,
            provider=provider,
            route_selected=True,
            dry_run=dry_run,
            executed=False,
            segment_count=bundle.segment_count,
            preflight=preflight_dict,
            mock_artifacts=mock_artifacts,
            narration_bundle=bundle.to_dict(),
            metadata={
                "router_version": ENGINE_VERSION,
                "engine": ENGINE_NAME,
                "evaluated_at": _now(),
                "live_tts": False,
            },
        )

    def _build_mock_artifacts(
        self,
        bundle: NarrationBundle,
        provider: str,
        artifact_root: Path,
    ) -> list[dict[str, Any]]:
        """Create dry-run artifact metadata only — writes tiny .mock files, not real audio."""
        artifact_root.mkdir(parents=True, exist_ok=True)
        artifacts: list[dict[str, Any]] = []
        for segment in bundle.segments:
            filename = f"segment_{segment.segment_index:02d}.mock"
            path = artifact_root / filename
            path.write_text(f"dry_run_voice:{provider}:{segment.text_hash}\n", encoding="utf-8")
            artifacts.append(
                {
                    "artifact_id": f"art_voice_{segment.segment_index:02d}",
                    "provider_category": CATEGORY_VOICE,
                    "artifact_type": "narration_audio",
                    "provider": provider,
                    "file_path": str(path),
                    "segment_index": segment.segment_index,
                    "clip_number": segment.clip_number,
                    "metadata": {
                        "text_hash": segment.text_hash,
                        "dry_run": True,
                        "live_tts": False,
                    },
                }
            )
        return artifacts


__all__ = [
    "VoiceProviderRouter",
    "VoiceRouterResult",
    "ROUTER_SUPPORTED",
    "IMPLEMENTED_PROVIDERS",
    "STUB_PROVIDERS",
]
