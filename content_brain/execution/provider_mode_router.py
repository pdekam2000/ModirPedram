"""
Phase 10J-b — resolve provider family + execution mode to router keys and adapters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.execution_adapters import ExecutionAdapter, adapter_for_resolution
from content_brain.execution.provider_mode_catalog import (
    EXECUTION_MODE_API,
    EXECUTION_MODE_BROWSER,
    ModeResolution,
    ProviderModeCatalog,
)

VIDEO_ROUTER_KEYS_IMPLEMENTED = frozenset(
    {
        "hailuo",
        "hailuo_browser",
        "runway_browser",
        "runway",
        "runway_api",
        "minimax_api",
    }
)


class ProviderModeRouter:
    """Compatibility shim: session + mode → router_key + adapter (no router edits)."""

    def __init__(
        self,
        catalog: ProviderModeCatalog | None = None,
        project_root: str | Path | None = None,
    ):
        self.project_root = Path(project_root).resolve() if project_root else None
        self.catalog = catalog or ProviderModeCatalog.load(self.project_root)

    def resolve(
        self,
        session: dict[str, Any],
        *,
        execution_mode_override: str | None = None,
    ) -> ModeResolution | None:
        return self.catalog.resolve_from_session(
            session,
            execution_mode_override=execution_mode_override,
        )

    def select_adapter(self, resolution: ModeResolution) -> ExecutionAdapter:
        return adapter_for_resolution(resolution)

    def execute(self, resolution: ModeResolution, prompts: list[str]) -> list[str | None]:
        adapter = self.select_adapter(resolution)
        return adapter.execute(prompts, resolution.router_key)

    @staticmethod
    def is_router_key_implemented(router_key: str) -> bool:
        return str(router_key or "").strip().lower() in VIDEO_ROUTER_KEYS_IMPLEMENTED

    def router_implementation_status(
        self,
        resolution: ModeResolution,
    ) -> tuple[bool, str | None]:
        router_key = resolution.router_key
        if not self.is_router_key_implemented(router_key):
            return False, f"Router key not implemented: {router_key}"

        entry = self.catalog.get_family(resolution.provider_family) or {}
        if resolution.provider_execution_mode == EXECUTION_MODE_API:
            api_config = entry.get("api_config") or {}
            status = str(api_config.get("implementation_status") or "").strip().lower()
            if status in {"planned", "stub"}:
                return False, f"API mode implementation status: {status}"
        return True, None


__all__ = [
    "ProviderModeRouter",
    "VIDEO_ROUTER_KEYS_IMPLEMENTED",
    "EXECUTION_MODE_BROWSER",
    "EXECUTION_MODE_API",
]
