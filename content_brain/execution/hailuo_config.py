"""
Phase 11F-a — unified Hailuo / MiniMax config resolution from registry, mode catalog, and env.

Read-only; does not mutate config files or call Hailuo/MiniMax API.
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

CONFIG_VERSION = "11f_a_v1"

HAILUO_FAMILY = "hailuo"
MINIMAX_FAMILY = "minimax"

HAILUO_BROWSER_ROUTER_KEY = "hailuo_browser"
HAILUO_API_ROUTER_KEY = "hailuo_api"
MINIMAX_API_ROUTER_KEY = "minimax_api"

HAILUO_BROWSER_ALIASES = frozenset({"hailuo", "hailuo_browser"})
HAILUO_API_ALIASES = frozenset({"hailuo_api"})
MINIMAX_API_ALIASES = frozenset({"minimax_api"})

DEFAULT_ACTIVE_VIDEO_PROVIDER = "runway_browser"

HAILUO_API_KEY_ENV = "HAILUO_API_KEY"
MINIMAX_API_KEY_ENV = "MINIMAX_API_KEY"
HAILUO_API_BASE_URL_ENV = "HAILUO_API_BASE_URL"
MINIMAX_API_BASE_URL_ENV = "MINIMAX_API_BASE_URL"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_valid_api_base_url(url: str | None) -> bool:
    if not url or not str(url).strip():
        return False
    parsed = urlparse(str(url).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_hailuo_provider_id(provider_id: str | None) -> str:
    canonical = normalize_provider_id(str(provider_id or "").strip().lower())
    if canonical in HAILUO_BROWSER_ALIASES:
        return HAILUO_BROWSER_ROUTER_KEY
    if canonical in HAILUO_API_ALIASES:
        return HAILUO_API_ROUTER_KEY
    if canonical in MINIMAX_API_ALIASES:
        return MINIMAX_API_ROUTER_KEY
    return canonical


def infer_provider_family(provider_id: str | None) -> str | None:
    normalized = normalize_hailuo_provider_id(provider_id)
    if normalized == MINIMAX_API_ROUTER_KEY:
        return MINIMAX_FAMILY
    if normalized in {HAILUO_BROWSER_ROUTER_KEY, HAILUO_API_ROUTER_KEY}:
        return HAILUO_FAMILY
    if normalized == "hailuo":
        return HAILUO_FAMILY
    return None


@dataclass(frozen=True)
class HailuoConfigSnapshot:
    config_version: str
    active_video_provider: str
    active_default_is_runway: bool
    hailuo_family: str
    minimax_family: str
    hailuo_browser_router_key: str
    hailuo_api_router_key: str
    minimax_api_router_key: str
    hailuo_preferred_mode: str
    minimax_preferred_mode: str
    hailuo_browser_enabled_in_registry: bool
    hailuo_api_in_registry: bool
    minimax_api_enabled_in_registry: bool
    hailuo_api_implementation_status: str
    minimax_api_implementation_status: str
    hailuo_api_implemented: bool
    minimax_api_implemented: bool
    hailuo_api_key_env: str
    minimax_api_key_env: str
    hailuo_api_key_present: bool
    minimax_api_key_present: bool
    hailuo_api_base_url: str | None
    minimax_api_base_url: str | None
    hailuo_api_base_url_source: str
    minimax_api_base_url_source: str
    hailuo_api_base_url_valid: bool
    minimax_api_base_url_valid: bool
    hailuo_api_base_url_env: str
    minimax_api_base_url_env: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "active_video_provider": self.active_video_provider,
            "active_default_is_runway": self.active_default_is_runway,
            "hailuo_family": self.hailuo_family,
            "minimax_family": self.minimax_family,
            "hailuo_browser_router_key": self.hailuo_browser_router_key,
            "hailuo_api_router_key": self.hailuo_api_router_key,
            "minimax_api_router_key": self.minimax_api_router_key,
            "hailuo_preferred_mode": self.hailuo_preferred_mode,
            "minimax_preferred_mode": self.minimax_preferred_mode,
            "hailuo_browser_enabled_in_registry": self.hailuo_browser_enabled_in_registry,
            "hailuo_api_in_registry": self.hailuo_api_in_registry,
            "minimax_api_enabled_in_registry": self.minimax_api_enabled_in_registry,
            "hailuo_api_implementation_status": self.hailuo_api_implementation_status,
            "minimax_api_implementation_status": self.minimax_api_implementation_status,
            "hailuo_api_implemented": self.hailuo_api_implemented,
            "minimax_api_implemented": self.minimax_api_implemented,
            "hailuo_api_key_env": self.hailuo_api_key_env,
            "minimax_api_key_env": self.minimax_api_key_env,
            "hailuo_api_key_present": self.hailuo_api_key_present,
            "minimax_api_key_present": self.minimax_api_key_present,
            "hailuo_api_base_url": self.hailuo_api_base_url,
            "minimax_api_base_url": self.minimax_api_base_url,
            "hailuo_api_base_url_source": self.hailuo_api_base_url_source,
            "minimax_api_base_url_source": self.minimax_api_base_url_source,
            "hailuo_api_base_url_valid": self.hailuo_api_base_url_valid,
            "minimax_api_base_url_valid": self.minimax_api_base_url_valid,
            "hailuo_api_base_url_env": self.hailuo_api_base_url_env,
            "minimax_api_base_url_env": self.minimax_api_base_url_env,
        }


class HailuoConfigResolver:
    """Resolve Hailuo/MiniMax settings from provider_registry, mode catalog, active_providers, and env."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or ".").resolve()
        self.config_dir = self.project_root / "config"
        self.mode_catalog = ProviderModeCatalog.load(self.project_root)

    def resolve(self) -> HailuoConfigSnapshot:
        hailuo_entry = self.mode_catalog.get_family(HAILUO_FAMILY) or {}
        minimax_entry = self.mode_catalog.get_family(MINIMAX_FAMILY) or {}
        hailuo_api_config = _dict(hailuo_entry.get("api_config"))
        minimax_api_config = _dict(minimax_entry.get("api_config"))

        hailuo_api_key_env = str(hailuo_api_config.get("api_key_env") or HAILUO_API_KEY_ENV)
        minimax_api_key_env = str(minimax_api_config.get("api_key_env") or MINIMAX_API_KEY_ENV)
        hailuo_endpoint_env = str(hailuo_api_config.get("endpoint_env") or HAILUO_API_BASE_URL_ENV)
        minimax_endpoint_env = str(minimax_api_config.get("endpoint_env") or MINIMAX_API_BASE_URL_ENV)

        hailuo_api_base_url, hailuo_url_source = self._resolve_api_base_url(
            hailuo_endpoint_env,
            str(hailuo_api_config.get("default_endpoint") or "").strip(),
        )
        minimax_api_base_url, minimax_url_source = self._resolve_api_base_url(
            minimax_endpoint_env,
            str(minimax_api_config.get("default_endpoint") or "").strip(),
        )

        hailuo_impl_status = str(hailuo_api_config.get("implementation_status") or "planned").strip().lower()
        minimax_impl_status = str(minimax_api_config.get("implementation_status") or "stub").strip().lower()

        active_video = self._load_active_video_provider()
        browser_registry = self._registry_entry(HAILUO_BROWSER_ROUTER_KEY)
        minimax_registry = self._registry_entry(MINIMAX_API_ROUTER_KEY)

        return HailuoConfigSnapshot(
            config_version=CONFIG_VERSION,
            active_video_provider=active_video,
            active_default_is_runway=active_video == DEFAULT_ACTIVE_VIDEO_PROVIDER,
            hailuo_family=HAILUO_FAMILY,
            minimax_family=MINIMAX_FAMILY,
            hailuo_browser_router_key=HAILUO_BROWSER_ROUTER_KEY,
            hailuo_api_router_key=HAILUO_API_ROUTER_KEY,
            minimax_api_router_key=MINIMAX_API_ROUTER_KEY,
            hailuo_preferred_mode=self.mode_catalog.get_preferred_mode(HAILUO_FAMILY),
            minimax_preferred_mode=self.mode_catalog.get_preferred_mode(MINIMAX_FAMILY),
            hailuo_browser_enabled_in_registry=bool(_dict(browser_registry).get("enabled", False)),
            hailuo_api_in_registry=self._registry_entry(HAILUO_API_ROUTER_KEY) is not None,
            minimax_api_enabled_in_registry=bool(_dict(minimax_registry).get("enabled", False)),
            hailuo_api_implementation_status=hailuo_impl_status,
            minimax_api_implementation_status=minimax_impl_status,
            hailuo_api_implemented=hailuo_impl_status == "implemented",
            minimax_api_implemented=minimax_impl_status == "implemented",
            hailuo_api_key_env=hailuo_api_key_env,
            minimax_api_key_env=minimax_api_key_env,
            hailuo_api_key_present=bool(os.getenv(hailuo_api_key_env, "").strip()),
            minimax_api_key_present=bool(os.getenv(minimax_api_key_env, "").strip()),
            hailuo_api_base_url=hailuo_api_base_url,
            minimax_api_base_url=minimax_api_base_url,
            hailuo_api_base_url_source=hailuo_url_source,
            minimax_api_base_url_source=minimax_url_source,
            hailuo_api_base_url_valid=is_valid_api_base_url(hailuo_api_base_url),
            minimax_api_base_url_valid=is_valid_api_base_url(minimax_api_base_url),
            hailuo_api_base_url_env=hailuo_endpoint_env,
            minimax_api_base_url_env=minimax_endpoint_env,
        )

    def router_key_for_mode(self, family: str, mode: str) -> str:
        key = self.mode_catalog.router_key(family, mode)
        if key:
            return key
        if str(family).lower() == MINIMAX_FAMILY:
            return MINIMAX_API_ROUTER_KEY
        if str(mode).lower() == EXECUTION_MODE_BROWSER:
            return HAILUO_BROWSER_ROUTER_KEY
        return HAILUO_API_ROUTER_KEY

    def _resolve_api_base_url(
        self,
        endpoint_env: str,
        default_endpoint: str,
    ) -> tuple[str | None, str]:
        env_endpoint = os.getenv(endpoint_env, "").strip()
        if env_endpoint:
            return env_endpoint.rstrip("/"), endpoint_env
        if default_endpoint:
            return default_endpoint.rstrip("/"), "catalog.default_endpoint"
        return None, "unset"

    def _load_active_video_provider(self) -> str:
        active_path = self.config_dir / "active_providers.json"
        if not active_path.exists():
            return DEFAULT_ACTIVE_VIDEO_PROVIDER
        try:
            data = json.loads(active_path.read_text(encoding="utf-8"))
            return normalize_hailuo_provider_id(str(data.get("video") or DEFAULT_ACTIVE_VIDEO_PROVIDER))
        except Exception:
            return DEFAULT_ACTIVE_VIDEO_PROVIDER

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


__all__ = [
    "CONFIG_VERSION",
    "HAILUO_FAMILY",
    "MINIMAX_FAMILY",
    "HAILUO_BROWSER_ROUTER_KEY",
    "HAILUO_API_ROUTER_KEY",
    "MINIMAX_API_ROUTER_KEY",
    "DEFAULT_ACTIVE_VIDEO_PROVIDER",
    "HailuoConfigSnapshot",
    "HailuoConfigResolver",
    "infer_provider_family",
    "is_valid_api_base_url",
    "normalize_hailuo_provider_id",
]
