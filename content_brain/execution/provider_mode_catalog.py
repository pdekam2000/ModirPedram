"""
Phase 10J-a — dual execution mode catalog for video provider families.

Browser vs API routing keys and learning keys; config-overridable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VIDEO, normalize_provider_key

CATALOG_VERSION = "10j_v1"
EXECUTION_MODE_BROWSER = "browser"
EXECUTION_MODE_API = "api"
EXECUTION_MODES = (EXECUTION_MODE_BROWSER, EXECUTION_MODE_API)

COST_BASIS_SUBSCRIPTION = "subscription"
COST_BASIS_USAGE_API = "usage_api"
COST_BASIS_UNKNOWN = "unknown"

_DEFAULT_CATALOG: dict[str, dict[str, Any]] = {
    "runway": {
        "display_name": "Runway",
        "supported_modes": [EXECUTION_MODE_API, EXECUTION_MODE_BROWSER],
        "preferred_mode": EXECUTION_MODE_BROWSER,
        "router_keys": {
            EXECUTION_MODE_BROWSER: "runway_browser",
            EXECUTION_MODE_API: "runway",
        },
        "learning_keys": {
            EXECUTION_MODE_BROWSER: "runway_browser",
            EXECUTION_MODE_API: "runway_api",
        },
        "cost_basis_by_mode": {
            EXECUTION_MODE_BROWSER: COST_BASIS_SUBSCRIPTION,
            EXECUTION_MODE_API: COST_BASIS_USAGE_API,
        },
        "api_config": {
            "api_key_env": "RUNWAY_API_KEY",
            "endpoint_env": "RUNWAY_API_BASE_URL",
            "default_endpoint": "https://api.dev.runwayml.com/v1",
            "polling_supported": True,
        },
        "browser_config": {
            "cdp_url": "http://127.0.0.1:9222",
            "profile_path": "storage/real_chrome_profile",
            "download_dir": "downloads/runway",
        },
    },
    "hailuo": {
        "display_name": "Hailuo",
        "supported_modes": [EXECUTION_MODE_API, EXECUTION_MODE_BROWSER],
        "preferred_mode": EXECUTION_MODE_BROWSER,
        "router_keys": {
            EXECUTION_MODE_BROWSER: "hailuo_browser",
            EXECUTION_MODE_API: "hailuo_api",
        },
        "learning_keys": {
            EXECUTION_MODE_BROWSER: "hailuo_browser",
            EXECUTION_MODE_API: "hailuo_api",
        },
        "cost_basis_by_mode": {
            EXECUTION_MODE_BROWSER: COST_BASIS_SUBSCRIPTION,
            EXECUTION_MODE_API: COST_BASIS_USAGE_API,
        },
        "api_config": {
            "api_key_env": "HAILUO_API_KEY",
            "polling_supported": False,
            "implementation_status": "planned",
        },
        "browser_config": {
            "cdp_url": "http://127.0.0.1:9222",
            "profile_path": "storage/real_chrome_profile",
            "download_dir": "downloads",
        },
    },
    "minimax": {
        "display_name": "MiniMax",
        "supported_modes": [EXECUTION_MODE_API],
        "preferred_mode": EXECUTION_MODE_API,
        "router_keys": {EXECUTION_MODE_API: "minimax_api"},
        "learning_keys": {EXECUTION_MODE_API: "minimax_api"},
        "cost_basis_by_mode": {EXECUTION_MODE_API: COST_BASIS_USAGE_API},
        "api_config": {
            "api_key_env": "MINIMAX_API_KEY",
            "polling_supported": False,
            "implementation_status": "stub",
        },
    },
}

_ROUTER_KEY_TO_FAMILY: dict[str, str] = {}
for _family, _entry in _DEFAULT_CATALOG.items():
    for _mode, _router_key in (_entry.get("router_keys") or {}).items():
        _ROUTER_KEY_TO_FAMILY[str(_router_key).lower()] = _family


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ModeResolution:
    provider_family: str
    provider_execution_mode: str
    router_key: str
    learning_key: str
    adapter: str
    display_name: str
    cost_basis: str
    provider_category: str = CATEGORY_VIDEO

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_family": self.provider_family,
            "provider_execution_mode": self.provider_execution_mode,
            "router_key": self.router_key,
            "learning_key": self.learning_key,
            "adapter": self.adapter,
            "display_name": self.display_name,
            "cost_basis": self.cost_basis,
            "provider_category": self.provider_category,
        }


class ProviderModeCatalog:
    def __init__(self, catalog: dict[str, dict[str, Any]] | None = None):
        self._catalog = catalog if catalog is not None else dict(_DEFAULT_CATALOG)

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> ProviderModeCatalog:
        catalog = dict(_DEFAULT_CATALOG)
        if project_root is not None:
            override_path = Path(project_root).resolve() / "config" / "provider_mode_catalog.json"
            if override_path.exists():
                with override_path.open("r", encoding="utf-8") as handle:
                    override = json.load(handle)
                if isinstance(override, dict):
                    for family, entry in override.items():
                        if isinstance(entry, dict):
                            base = dict(catalog.get(family) or {})
                            base.update(entry)
                            catalog[family] = base
        return cls(catalog)

    def families(self) -> list[str]:
        return sorted(self._catalog.keys())

    def get_family(self, provider_family: str) -> dict[str, Any] | None:
        key = str(provider_family or "").strip().lower()
        entry = self._catalog.get(key)
        return dict(entry) if isinstance(entry, dict) else None

    def get_preferred_mode(self, provider_family: str) -> str:
        entry = self.get_family(provider_family) or {}
        mode = str(entry.get("preferred_mode") or EXECUTION_MODE_BROWSER).strip().lower()
        return mode if mode in EXECUTION_MODES else EXECUTION_MODE_BROWSER

    def supported_modes(self, provider_family: str) -> list[str]:
        entry = self.get_family(provider_family) or {}
        modes = entry.get("supported_modes") or []
        if not isinstance(modes, list):
            return []
        return [str(item).lower() for item in modes if str(item).lower() in EXECUTION_MODES]

    def router_key(self, provider_family: str, provider_execution_mode: str) -> str | None:
        entry = self.get_family(provider_family) or {}
        keys = _dict(entry.get("router_keys"))
        return keys.get(str(provider_execution_mode).lower())

    def learning_key(self, provider_family: str, provider_execution_mode: str) -> str | None:
        entry = self.get_family(provider_family) or {}
        keys = _dict(entry.get("learning_keys"))
        return keys.get(str(provider_execution_mode).lower())

    def cost_basis(self, provider_family: str, provider_execution_mode: str) -> str:
        entry = self.get_family(provider_family) or {}
        by_mode = _dict(entry.get("cost_basis_by_mode"))
        return str(
            by_mode.get(str(provider_execution_mode).lower()) or COST_BASIS_UNKNOWN
        )

    def infer_family_from_router_key(self, router_key: str) -> str | None:
        normalized = normalize_provider_key(router_key)
        if normalized in _ROUTER_KEY_TO_FAMILY:
            return _ROUTER_KEY_TO_FAMILY[normalized]
        if normalized.endswith("_browser"):
            return normalized.replace("_browser", "")
        if normalized.endswith("_api"):
            return normalized.replace("_api", "")
        return normalized or None

    def infer_mode_from_router_key(self, router_key: str) -> str | None:
        normalized = normalize_provider_key(router_key)
        if normalized.endswith("_browser") or normalized == "hailuo_browser" or normalized == "runway_browser":
            return EXECUTION_MODE_BROWSER
        if normalized in {"runway", "runway_api", "minimax_api", "hailuo_api"}:
            return EXECUTION_MODE_API
        entry_family = self.infer_family_from_router_key(normalized)
        if not entry_family:
            return None
        for mode in self.supported_modes(entry_family):
            if self.router_key(entry_family, mode) == normalized:
                return mode
        return self.get_preferred_mode(entry_family)

    def resolve(
        self,
        provider_family: str,
        provider_execution_mode: str | None = None,
    ) -> ModeResolution | None:
        family = str(provider_family or "").strip().lower()
        entry = self.get_family(family)
        if not entry:
            return None

        mode = str(provider_execution_mode or entry.get("preferred_mode") or EXECUTION_MODE_BROWSER).lower()
        if mode not in self.supported_modes(family):
            return None

        router = self.router_key(family, mode)
        learning = self.learning_key(family, mode)
        if not router or not learning:
            return None

        return ModeResolution(
            provider_family=family,
            provider_execution_mode=mode,
            router_key=router,
            learning_key=learning,
            adapter=mode,
            display_name=str(entry.get("display_name") or family),
            cost_basis=self.cost_basis(family, mode),
        )

    def resolve_from_session(
        self,
        session: dict[str, Any],
        *,
        execution_mode_override: str | None = None,
    ) -> ModeResolution | None:
        provider_selection = _dict(session.get("provider_selection"))
        category_selections = _dict(provider_selection.get("category_selections"))
        video_sel = _dict(category_selections.get(CATEGORY_VIDEO))

        raw_provider = (
            video_sel.get("provider")
            or provider_selection.get("primary_provider")
            or session.get("provider")
            or ""
        )
        normalized = normalize_provider_key(str(raw_provider))

        family = (
            str(video_sel.get("provider_family") or provider_selection.get("provider_family") or "").lower()
            or self.infer_family_from_router_key(normalized)
            or normalized.replace("_browser", "").replace("_api", "")
        )

        mode = (
            execution_mode_override
            or video_sel.get("execution_mode")
            or provider_selection.get("execution_mode")
            or self.infer_mode_from_router_key(normalized)
            or self.get_preferred_mode(family)
        )
        return self.resolve(family, str(mode).lower())


def default_catalog() -> ProviderModeCatalog:
    return ProviderModeCatalog.load()


__all__ = [
    "CATALOG_VERSION",
    "EXECUTION_MODE_BROWSER",
    "EXECUTION_MODE_API",
    "EXECUTION_MODES",
    "COST_BASIS_SUBSCRIPTION",
    "COST_BASIS_USAGE_API",
    "ModeResolution",
    "ProviderModeCatalog",
    "default_catalog",
]
