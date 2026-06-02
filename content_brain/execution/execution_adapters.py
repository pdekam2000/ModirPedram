"""
Phase 10J-b — thin browser/API adapters delegating to VideoProviderRouter (unchanged).
"""

from __future__ import annotations

from typing import Protocol

from content_brain.execution.provider_mode_catalog import (
    EXECUTION_MODE_API,
    EXECUTION_MODE_BROWSER,
    ModeResolution,
)


class ExecutionAdapter(Protocol):
    def execute(self, prompts: list[str], router_key: str) -> list[str | None]: ...


class BrowserExecutionAdapter:
    """Browser mode — delegates to existing router/orchestrators."""

    def execute(self, prompts: list[str], router_key: str) -> list[str | None]:
        from core.video_provider_router import VideoProviderRouter

        router = VideoProviderRouter()
        return router.generate_clips(prompts, provider_override=router_key)


class ApiExecutionAdapter:
    """API mode — same router entrypoint; preflight differs, router unchanged."""

    def execute(self, prompts: list[str], router_key: str) -> list[str | None]:
        from core.video_provider_router import VideoProviderRouter

        router = VideoProviderRouter()
        return router.generate_clips(prompts, provider_override=router_key)


def adapter_for_mode(provider_execution_mode: str) -> ExecutionAdapter:
    mode = str(provider_execution_mode or "").strip().lower()
    if mode == EXECUTION_MODE_BROWSER:
        return BrowserExecutionAdapter()
    if mode == EXECUTION_MODE_API:
        return ApiExecutionAdapter()
    raise ValueError(f"Unsupported provider_execution_mode: {provider_execution_mode}")


def adapter_for_resolution(resolution: ModeResolution) -> ExecutionAdapter:
    return adapter_for_mode(resolution.provider_execution_mode)


def execute_prompts(resolution: ModeResolution, prompts: list[str]) -> list[str | None]:
    adapter = adapter_for_resolution(resolution)
    return adapter.execute(prompts, resolution.router_key)


__all__ = [
    "ExecutionAdapter",
    "BrowserExecutionAdapter",
    "ApiExecutionAdapter",
    "adapter_for_mode",
    "adapter_for_resolution",
    "execute_prompts",
]
