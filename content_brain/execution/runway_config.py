"""
Phase 11E-a — unified Runway config resolution from registry, mode catalog, and env.

Read-only; does not mutate config files or call Runway API.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_brain.execution.provider_mode_catalog import (
    EXECUTION_MODE_API,
    EXECUTION_MODE_BROWSER,
    ProviderModeCatalog,
)
from content_brain.providers.provider_capability_registry import normalize_provider_id

CONFIG_VERSION = "11e_a_v1"

RUNWAY_FAMILY = "runway"
RUNWAY_API_ROUTER_KEY = "runway"
RUNWAY_BROWSER_ROUTER_KEY = "runway_browser"
RUNWAY_API_ALIASES = frozenset({"runway", "runway_api"})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_valid_api_base_url(url: str | None) -> bool:
    if not url or not str(url).strip():
        return False
    parsed = urlparse(str(url).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_runway_provider_id(provider_id: str | None) -> str:
    canonical = normalize_provider_id(str(provider_id or "").strip().lower())
    if canonical in RUNWAY_API_ALIASES:
        return RUNWAY_API_ROUTER_KEY
    return canonical


@dataclass(frozen=True)
class RunwayConfigSnapshot:
    config_version: str
    provider_family: str
    active_video_provider: str
    preferred_mode: str
    api_router_key: str
    browser_router_key: str
    api_key_env: str
    api_key_present: bool
    api_base_url: str | None
    api_base_url_source: str
    api_base_url_valid: bool
    api_enabled_in_registry: bool
    browser_enabled_in_registry: bool
    endpoint_env: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "provider_family": self.provider_family,
            "active_video_provider": self.active_video_provider,
            "preferred_mode": self.preferred_mode,
            "api_router_key": self.api_router_key,
            "browser_router_key": self.browser_router_key,
            "api_key_env": self.api_key_env,
            "api_key_present": self.api_key_present,
            "api_base_url": self.api_base_url,
            "api_base_url_source": self.api_base_url_source,
            "api_base_url_valid": self.api_base_url_valid,
            "api_enabled_in_registry": self.api_enabled_in_registry,
            "browser_enabled_in_registry": self.browser_enabled_in_registry,
            "endpoint_env": self.endpoint_env,
        }


class RunwayConfigResolver:
    """Resolve Runway settings from provider_registry, mode catalog, active_providers, and env."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or ".").resolve()
        self.config_dir = self.project_root / "config"
        self.mode_catalog = ProviderModeCatalog.load(self.project_root)

    def resolve(self) -> RunwayConfigSnapshot:
        family_entry = self.mode_catalog.get_family(RUNWAY_FAMILY) or {}
        api_config = _dict(family_entry.get("api_config"))

        api_key_env = str(api_config.get("api_key_env") or "RUNWAY_API_KEY")
        endpoint_env = str(api_config.get("endpoint_env") or "RUNWAY_API_BASE_URL")
        default_endpoint = str(api_config.get("default_endpoint") or "").strip()

        env_endpoint = os.getenv(endpoint_env, "").strip()
        if env_endpoint:
            api_base_url = env_endpoint.rstrip("/")
            api_base_url_source = endpoint_env
        elif default_endpoint:
            api_base_url = default_endpoint.rstrip("/")
            api_base_url_source = "catalog.default_endpoint"
        else:
            api_base_url = None
            api_base_url_source = "unset"

        api_key_present = bool(os.getenv(api_key_env, "").strip())

        active_video = self._load_active_video_provider()
        api_registry = self._registry_entry(RUNWAY_API_ROUTER_KEY)
        browser_registry = self._registry_entry(RUNWAY_BROWSER_ROUTER_KEY)

        return RunwayConfigSnapshot(
            config_version=CONFIG_VERSION,
            provider_family=RUNWAY_FAMILY,
            active_video_provider=active_video,
            preferred_mode=self.mode_catalog.get_preferred_mode(RUNWAY_FAMILY),
            api_router_key=RUNWAY_API_ROUTER_KEY,
            browser_router_key=RUNWAY_BROWSER_ROUTER_KEY,
            api_key_env=api_key_env,
            api_key_present=api_key_present,
            api_base_url=api_base_url,
            api_base_url_source=api_base_url_source,
            api_base_url_valid=is_valid_api_base_url(api_base_url),
            api_enabled_in_registry=bool(_dict(api_registry).get("enabled", False)),
            browser_enabled_in_registry=bool(_dict(browser_registry).get("enabled", True)),
            endpoint_env=endpoint_env,
        )

    def _load_active_video_provider(self) -> str:
        active_path = self.config_dir / "active_providers.json"
        if not active_path.exists():
            return RUNWAY_BROWSER_ROUTER_KEY
        try:
            data = json.loads(active_path.read_text(encoding="utf-8"))
            return normalize_runway_provider_id(str(data.get("video") or RUNWAY_BROWSER_ROUTER_KEY))
        except Exception:
            return RUNWAY_BROWSER_ROUTER_KEY

    def _registry_entry(self, name: str) -> dict[str, Any] | None:
        registry_path = self.config_dir / "provider_registry.json"
        if not registry_path.exists():
            return None
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        for entry in data.get("video") or []:
            if isinstance(entry, dict) and str(entry.get("name", "")).lower() == name.lower():
                return entry
        return None

    def router_key_for_mode(self, mode: str) -> str:
        key = self.mode_catalog.router_key(RUNWAY_FAMILY, mode)
        return key or (
            RUNWAY_BROWSER_ROUTER_KEY
            if str(mode).lower() == EXECUTION_MODE_BROWSER
            else RUNWAY_API_ROUTER_KEY
        )


__all__ = [
    "CONFIG_VERSION",
    "RUNWAY_FAMILY",
    "RUNWAY_API_ROUTER_KEY",
    "RUNWAY_BROWSER_ROUTER_KEY",
    "RUNWAY_API_ALIASES",
    "RunwayConfigSnapshot",
    "RunwayConfigResolver",
    "is_valid_api_base_url",
    "normalize_runway_provider_id",
]
