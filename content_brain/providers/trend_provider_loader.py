"""
Config-driven loader for Content Brain trend provider registration.

Reads active trend sources from ProviderRegistryEngine and registers
runtime provider instances into RealTrendProviderRegistry.
No API calls. No credential exposure.
"""

from __future__ import annotations

import importlib
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from content_brain.providers.real_trend_provider import RealTrendProviderRegistry

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover - defensive import
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]


FUTURE_PLUGIN_SPECS: dict[str, tuple[str, str]] = {
    "dataforseo": (
        "content_brain.providers.dataforseo_trend_provider",
        "DataForSEOTrendProvider",
    ),
    "serpapi": (
        "content_brain.providers.serpapi_trend_provider",
        "SerpAPITrendProvider",
    ),
    "dataforseo_youtube": (
        "content_brain.providers.dataforseo_youtube_trend_provider",
        "DataForSEOYouTubeTrendProvider",
    ),
}


class TrendProviderConfigLoader:
    """Build a RealTrendProviderRegistry from config/active_providers.json."""

    def __init__(
        self,
        registry_engine: Any | None = None,
    ):
        self.registry_engine = registry_engine

    def build_registry(self) -> "RealTrendProviderRegistry":
        from content_brain.providers.real_trend_provider import (
            MockTrendProvider,
            RealTrendProviderRegistry,
        )

        registry = RealTrendProviderRegistry()
        registered_count = 0

        try:
            ready_sources = self._get_ready_trend_sources()
        except Exception:
            ready_sources = []

        for provider_id in ready_sources:
            provider = self._instantiate_provider(provider_id)
            if provider is None:
                continue
            registry.register(provider)
            registered_count += 1

        if registered_count == 0:
            registry.register(MockTrendProvider())

        return registry

    def _get_engine(self) -> Any:
        if self.registry_engine is not None:
            return self.registry_engine
        if ProviderRegistryEngine is None:
            raise RuntimeError("ProviderRegistryEngine is unavailable.")
        return ProviderRegistryEngine()

    def _get_ready_trend_sources(self) -> list[str]:
        engine = self._get_engine()
        active_ready = engine.get_ready_trend_sources()
        live_active = [item for item in active_ready if item != "mock_trend_provider"]
        if live_active:
            return active_ready
        credential_ready = engine.get_credential_ready_trend_sources()
        if credential_ready:
            return credential_ready
        return active_ready

    def _instantiate_provider(
        self,
        provider_id: str,
    ) -> Any | None:
        if provider_id == "mock_trend_provider":
            from content_brain.providers.real_trend_provider import MockTrendProvider

            return MockTrendProvider()

        if provider_id in FUTURE_PLUGIN_SPECS:
            return self._try_load_future_plugin(provider_id)

        return None

    def _try_load_future_plugin(
        self,
        provider_id: str,
    ) -> Any | None:
        spec = FUTURE_PLUGIN_SPECS.get(provider_id)
        if spec is None:
            return None

        module_name, class_name = spec

        try:
            module = importlib.import_module(module_name)
            provider_cls = getattr(module, class_name)
        except (ImportError, AttributeError, ModuleNotFoundError):
            return None

        try:
            return provider_cls()
        except Exception:
            return None


__all__ = [
    "FUTURE_PLUGIN_SPECS",
    "TrendProviderConfigLoader",
]
