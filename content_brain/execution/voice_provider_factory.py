"""
Phase 11H-2c — voice TTS provider factory (dependency injection prep).

Live execution path is not wired to /voice/run in 11H-2c.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from content_brain.execution.elevenlabs_runtime_adapter import (
    ElevenLabsRuntimeAdapter,
    HttpClient,
)
from content_brain.execution.mock_voice_tts_provider import MockVoiceTtsProvider
from content_brain.execution.voice_live_tts_action_policy import (
    PROVIDER_MODE_LIVE,
    PROVIDER_MODE_MOCK,
)
from providers.elevenlabs_config import ElevenLabsConfigResolver

ProviderLike = MockVoiceTtsProvider | ElevenLabsRuntimeAdapter


def build_mock_voice_provider(
    *,
    cancel_check: Callable[[], bool] | None = None,
    fail_on_segment: int | None = None,
) -> MockVoiceTtsProvider:
    return MockVoiceTtsProvider(cancel_check=cancel_check, fail_on_segment=fail_on_segment)


def build_elevenlabs_runtime_adapter(
    session: dict[str, Any],
    *,
    project_root: str | Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    http_client: HttpClient | None = None,
    allow_real_http: bool = False,
    timeout_seconds: int | None = None,
    max_retry_attempts: int | None = None,
) -> ElevenLabsRuntimeAdapter:
    """Build live adapter — requires http_client unless allow_real_http=True."""
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    config = ElevenLabsConfigResolver(root).resolve(session)
    api_key = os.getenv(config.api_key_env, "").strip()
    kwargs: dict[str, Any] = {
        "config": config,
        "api_key": api_key,
        "cancel_check": cancel_check,
        "http_client": http_client,
        "allow_real_http": allow_real_http,
    }
    if timeout_seconds is not None:
        kwargs["timeout_seconds"] = timeout_seconds
    if max_retry_attempts is not None:
        kwargs["max_retry_attempts"] = max_retry_attempts
    return ElevenLabsRuntimeAdapter(**kwargs)


def build_voice_tts_provider(
    provider_mode: str,
    session: dict[str, Any],
    *,
    project_root: str | Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    http_client: HttpClient | None = None,
    fail_on_segment: int | None = None,
    allow_real_http: bool = False,
    timeout_seconds: int | None = None,
    max_retry_attempts: int | None = None,
) -> ProviderLike:
    mode = str(provider_mode or PROVIDER_MODE_MOCK).lower()
    if mode == PROVIDER_MODE_LIVE:
        return build_elevenlabs_runtime_adapter(
            session,
            project_root=project_root,
            cancel_check=cancel_check,
            http_client=http_client,
            allow_real_http=allow_real_http,
            timeout_seconds=timeout_seconds,
            max_retry_attempts=max_retry_attempts,
        )
    return build_mock_voice_provider(cancel_check=cancel_check, fail_on_segment=fail_on_segment)


__all__ = [
    "build_mock_voice_provider",
    "build_elevenlabs_runtime_adapter",
    "build_voice_tts_provider",
]
