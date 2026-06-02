"""
Phase 11A — provider capability registry.

Declarative source of truth for what each provider can do.
Sits beside ProviderModeCatalog and ProviderRegistryEngine; does not replace them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from content_brain.execution.provider_categories import (
    CATEGORY_IMAGE,
    CATEGORY_MUSIC,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
    normalize_provider_key,
)

REGISTRY_VERSION = "11a_v1"

# --- Capability identifiers ---

CAPABILITY_TEXT_TO_VIDEO = "text_to_video"
CAPABILITY_IMAGE_TO_VIDEO = "image_to_video"
CAPABILITY_TEXT_TO_IMAGE = "text_to_image"
CAPABILITY_IMAGE_GENERATION = "image_generation"
CAPABILITY_NARRATION = "narration"
CAPABILITY_VOICE_CLONE = "voice_clone"
CAPABILITY_MUSIC_GENERATION = "music_generation"
CAPABILITY_SUBTITLE_GENERATION = "subtitle_generation"
CAPABILITY_ASSET_DOWNLOAD = "asset_download"
CAPABILITY_ASSET_UPLOAD = "asset_upload"

ALL_CAPABILITIES: tuple[str, ...] = (
    CAPABILITY_TEXT_TO_VIDEO,
    CAPABILITY_IMAGE_TO_VIDEO,
    CAPABILITY_TEXT_TO_IMAGE,
    CAPABILITY_IMAGE_GENERATION,
    CAPABILITY_NARRATION,
    CAPABILITY_VOICE_CLONE,
    CAPABILITY_MUSIC_GENERATION,
    CAPABILITY_SUBTITLE_GENERATION,
    CAPABILITY_ASSET_DOWNLOAD,
    CAPABILITY_ASSET_UPLOAD,
)

# Resolve common aliases to canonical provider_id keys in this registry.
_PROVIDER_ID_ALIASES: dict[str, str] = {
    "hailuo": "hailuo_browser",
    "runway_api": "runway",
    "runway": "runway",
    "runway_browser": "runway_browser",
    "hailuo_browser": "hailuo_browser",
    "hailuo_api": "hailuo_api",
    "minimax_api": "minimax_api",
    "elevenlabs": "elevenlabs",
    "openai_tts": "openai_tts",
    "suno": "suno",
    "luma": "luma",
    "kling": "kling",
    "generic_image": "generic_image",
}


def normalize_provider_id(provider_id: str) -> str:
    key = normalize_provider_key(str(provider_id or "").strip().lower())
    return _PROVIDER_ID_ALIASES.get(key, key)


def _caps(*items: str) -> tuple[str, ...]:
    return tuple(items)


_DEFAULT_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "provider_id": "hailuo_browser",
        "provider_name": "Hailuo Browser",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(
            CAPABILITY_TEXT_TO_VIDEO,
            CAPABILITY_IMAGE_TO_VIDEO,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": True,
        "supports_api_mode": False,
        "supports_async_jobs": False,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
    {
        "provider_id": "hailuo_api",
        "provider_name": "Hailuo API",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(
            CAPABILITY_TEXT_TO_VIDEO,
            CAPABILITY_IMAGE_TO_VIDEO,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
    {
        "provider_id": "runway_browser",
        "provider_name": "Runway Browser",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(
            CAPABILITY_TEXT_TO_VIDEO,
            CAPABILITY_IMAGE_TO_VIDEO,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": True,
        "supports_api_mode": False,
        "supports_async_jobs": False,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
    {
        "provider_id": "runway",
        "provider_name": "Runway API",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(
            CAPABILITY_TEXT_TO_VIDEO,
            CAPABILITY_IMAGE_TO_VIDEO,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
    {
        "provider_id": "minimax_api",
        "provider_name": "MiniMax API",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(CAPABILITY_TEXT_TO_VIDEO, CAPABILITY_ASSET_DOWNLOAD),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": False,
    },
    {
        "provider_id": "luma",
        "provider_name": "Luma AI",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(CAPABILITY_TEXT_TO_VIDEO, CAPABILITY_ASSET_DOWNLOAD),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": False,
    },
    {
        "provider_id": "kling",
        "provider_name": "Kling AI",
        "category": CATEGORY_VIDEO,
        "capabilities": _caps(
            CAPABILITY_TEXT_TO_VIDEO,
            CAPABILITY_IMAGE_TO_VIDEO,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": False,
    },
    {
        "provider_id": "elevenlabs",
        "provider_name": "ElevenLabs",
        "category": CATEGORY_VOICE,
        "capabilities": _caps(
            CAPABILITY_NARRATION,
            CAPABILITY_VOICE_CLONE,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": False,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
    {
        "provider_id": "openai_tts",
        "provider_name": "OpenAI TTS",
        "category": CATEGORY_VOICE,
        "capabilities": _caps(CAPABILITY_NARRATION, CAPABILITY_ASSET_DOWNLOAD),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": False,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
    {
        "provider_id": "suno",
        "provider_name": "Suno AI",
        "category": CATEGORY_MUSIC,
        "capabilities": _caps(
            CAPABILITY_MUSIC_GENERATION,
            CAPABILITY_ASSET_DOWNLOAD,
        ),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": False,
    },
    {
        "provider_id": "generic_image",
        "provider_name": "Generic Image Provider",
        "category": CATEGORY_IMAGE,
        "capabilities": _caps(
            CAPABILITY_TEXT_TO_IMAGE,
            CAPABILITY_IMAGE_GENERATION,
            CAPABILITY_ASSET_DOWNLOAD,
            CAPABILITY_ASSET_UPLOAD,
        ),
        "supports_browser_mode": False,
        "supports_api_mode": True,
        "supports_async_jobs": True,
        "supports_webhooks": False,
        "supports_cost_estimation": True,
    },
)


@dataclass(frozen=True)
class ProviderCapabilityRecord:
    provider_id: str
    provider_name: str
    category: str
    capabilities: tuple[str, ...]
    supports_browser_mode: bool
    supports_api_mode: bool
    supports_async_jobs: bool
    supports_webhooks: bool
    supports_cost_estimation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "category": self.category,
            "capabilities": list(self.capabilities),
            "supports_browser_mode": self.supports_browser_mode,
            "supports_api_mode": self.supports_api_mode,
            "supports_async_jobs": self.supports_async_jobs,
            "supports_webhooks": self.supports_webhooks,
            "supports_cost_estimation": self.supports_cost_estimation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderCapabilityRecord:
        raw_caps = data.get("capabilities") or []
        if isinstance(raw_caps, str):
            raw_caps = [raw_caps]
        capabilities = tuple(
            str(item).strip().lower()
            for item in raw_caps
            if str(item).strip()
        )
        unknown = [cap for cap in capabilities if cap not in ALL_CAPABILITIES]
        if unknown:
            raise ValueError(f"Unknown capabilities for {data.get('provider_id')}: {unknown}")

        provider_id = normalize_provider_id(str(data.get("provider_id") or ""))
        if not provider_id:
            raise ValueError("provider_id is required")

        return cls(
            provider_id=provider_id,
            provider_name=str(data.get("provider_name") or provider_id),
            category=str(data.get("category") or "").strip(),
            capabilities=capabilities,
            supports_browser_mode=bool(data.get("supports_browser_mode")),
            supports_api_mode=bool(data.get("supports_api_mode")),
            supports_async_jobs=bool(data.get("supports_async_jobs")),
            supports_webhooks=bool(data.get("supports_webhooks")),
            supports_cost_estimation=bool(data.get("supports_cost_estimation")),
        )


class ProviderCapabilityRegistry:
    """Lookup registry for provider capabilities — read-only after load."""

    def __init__(self, providers: Iterable[ProviderCapabilityRecord]):
        self._providers: dict[str, ProviderCapabilityRecord] = {}
        self._by_capability: dict[str, list[str]] = {cap: [] for cap in ALL_CAPABILITIES}

        for record in providers:
            if record.provider_id in self._providers:
                raise ValueError(f"Duplicate provider_id: {record.provider_id}")
            self._providers[record.provider_id] = record
            for capability in record.capabilities:
                self._by_capability.setdefault(capability, []).append(record.provider_id)

        for capability in self._by_capability:
            self._by_capability[capability] = sorted(set(self._by_capability[capability]))

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> ProviderCapabilityRegistry:
        providers = [ProviderCapabilityRecord.from_dict(item) for item in _DEFAULT_PROVIDERS]

        if project_root is not None:
            override_path = Path(project_root).resolve() / "config" / "provider_capability_registry.json"
            if override_path.exists():
                payload = json.loads(override_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    extra = payload.get("providers") or payload.get("provider_overrides") or []
                    if isinstance(extra, list):
                        by_id = {record.provider_id: record for record in providers}
                        for item in extra:
                            if isinstance(item, dict):
                                record = ProviderCapabilityRecord.from_dict(item)
                                by_id[record.provider_id] = record
                        providers = list(by_id.values())

        return cls(providers)

    @classmethod
    def default(cls) -> ProviderCapabilityRegistry:
        return cls.load()

    def list_provider_ids(self) -> list[str]:
        return sorted(self._providers.keys())

    def list_providers(self) -> list[ProviderCapabilityRecord]:
        return [self._providers[key] for key in self.list_provider_ids()]

    def get_provider(self, provider_id: str) -> ProviderCapabilityRecord | None:
        key = normalize_provider_id(provider_id)
        return self._providers.get(key)

    def list_capabilities(self, provider_id: str) -> list[str]:
        record = self.get_provider(provider_id)
        if record is None:
            return []
        return list(record.capabilities)

    def providers_for_capability(self, capability: str) -> list[str]:
        cap = str(capability or "").strip().lower()
        if cap not in ALL_CAPABILITIES:
            return []
        return list(self._by_capability.get(cap, []))

    def supports(self, provider_id: str, capability: str) -> bool:
        cap = str(capability or "").strip().lower()
        if cap not in ALL_CAPABILITIES:
            return False
        return cap in self.list_capabilities(provider_id)

    def capability_coverage(self) -> dict[str, list[str]]:
        return {cap: list(self._by_capability.get(cap, [])) for cap in ALL_CAPABILITIES}

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": REGISTRY_VERSION,
            "capabilities": list(ALL_CAPABILITIES),
            "providers": [record.to_dict() for record in self.list_providers()],
        }

    def legacy_registry_coverage(self, project_root: str | Path | None = None) -> dict[str, Any]:
        """
        Read-only cross-check against legacy ProviderRegistryEngine names.
        Does not modify legacy registry.
        """
        from core.provider_registry_engine import ProviderRegistryEngine

        engine = ProviderRegistryEngine()
        legacy = engine.load_registry()
        missing: list[str] = []
        mapped: list[str] = []

        for category, entries in legacy.items():
            if category in {"trend", "trend_enrichment", "llm"}:
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "").strip().lower()
                if not name:
                    continue
                canonical = normalize_provider_id(name)
                if self.get_provider(canonical) or self.get_provider(name):
                    mapped.append(f"{category}:{name}")
                else:
                    missing.append(f"{category}:{name}")

        mode_catalog_families: list[str] = []
        try:
            from content_brain.execution.provider_mode_catalog import ProviderModeCatalog

            catalog = ProviderModeCatalog.load(project_root)
            for family in catalog.families():
                resolution = catalog.resolve(family)
                if resolution and self.get_provider(resolution.router_key):
                    mode_catalog_families.append(family)
        except Exception:
            mode_catalog_families = []

        return {
            "legacy_mapped": mapped,
            "legacy_missing": missing,
            "mode_catalog_families_mapped": mode_catalog_families,
        }


__all__ = [
    "REGISTRY_VERSION",
    "ALL_CAPABILITIES",
    "CAPABILITY_TEXT_TO_VIDEO",
    "CAPABILITY_IMAGE_TO_VIDEO",
    "CAPABILITY_TEXT_TO_IMAGE",
    "CAPABILITY_IMAGE_GENERATION",
    "CAPABILITY_NARRATION",
    "CAPABILITY_VOICE_CLONE",
    "CAPABILITY_MUSIC_GENERATION",
    "CAPABILITY_SUBTITLE_GENERATION",
    "CAPABILITY_ASSET_DOWNLOAD",
    "CAPABILITY_ASSET_UPLOAD",
    "ProviderCapabilityRecord",
    "ProviderCapabilityRegistry",
    "normalize_provider_id",
]
