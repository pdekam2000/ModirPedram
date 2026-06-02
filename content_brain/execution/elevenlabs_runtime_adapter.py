"""
Phase 11H-2c — ElevenLabs runtime adapter (Content Brain live HTTP site).

Single approved import site for ElevenLabs TTS HTTP in content_brain/execution/.
Real HTTP is disabled unless allow_real_http=True (not approved in 11H-2c).
Tests must inject a mock http_client — no network in CI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol

from content_brain.execution.voice_live_tts_safety_caps import (
    BACKOFF_BASE_SECONDS,
    MAX_RETRY_ATTEMPTS,
    TIMEOUT_SECONDS,
)
from providers.elevenlabs_config import ElevenLabsConfigSnapshot

PROVIDER_ID = "elevenlabs"
PROVIDER_MODE_LIVE = "live_elevenlabs"
ADAPTER_VERSION = "11h2c_v1"

ELEVENLABS_TTS_BASE = "https://api.elevenlabs.io/v1/text-to-speech"

CODE_ELEVENLABS_KEY_MISSING = "ELEVENLABS_KEY_MISSING"
CODE_ELEVENLABS_RATE_LIMIT = "ELEVENLABS_RATE_LIMIT"
CODE_ELEVENLABS_TIMEOUT = "ELEVENLABS_TIMEOUT"
CODE_ELEVENLABS_HTTP_ERROR = "ELEVENLABS_HTTP_ERROR"
CODE_ELEVENLABS_EMPTY_AUDIO = "ELEVENLABS_EMPTY_AUDIO"
CODE_ELEVENLABS_CANCELLED = "ELEVENLABS_CANCELLED"

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_FAKE_MP3_PREFIX = bytes([0xFF, 0xFB, 0x90, 0x00])


class HttpResponse(Protocol):
    status_code: int
    content: bytes
    headers: dict[str, str] | Any


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> HttpResponse: ...


@dataclass
class ElevenLabsSegmentResult:
    success: bool
    output_path: str
    segment_index: int
    character_count: int
    size_bytes: int = 0
    text_hash: str = ""
    voice_id: str = ""
    model_id: str = ""
    output_format: str = ""
    http_status: int | None = None
    latency_ms: int | None = None
    request_id: str | None = None
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    retried: bool = False
    retry_count: int = 0
    real_provider_called: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "segment_index": self.segment_index,
            "character_count": self.character_count,
            "size_bytes": self.size_bytes,
            "text_hash": self.text_hash,
            "voice_id": self.voice_id,
            "model_id": self.model_id,
            "output_format": self.output_format,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
            "retried": self.retried,
            "retry_count": self.retry_count,
            "real_provider_called": self.real_provider_called,
            "provider": PROVIDER_ID,
            "provider_mode": PROVIDER_MODE_LIVE,
        }


class RequestsHttpClient:
    """Default HTTP client — only used when allow_real_http=True (11H-2d+)."""

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> HttpResponse:
        import requests

        return requests.post(url, headers=headers, json=json, timeout=timeout)


def _extract_request_id(headers: Any) -> str | None:
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    for key in ("x-request-id", "request-id", "X-Request-Id"):
        value = getter(key)
        if value:
            return str(value)
    return None


def _map_http_status(status_code: int) -> str:
    if status_code == 429:
        return CODE_ELEVENLABS_RATE_LIMIT
    if status_code in (401, 403):
        return CODE_ELEVENLABS_KEY_MISSING
    return CODE_ELEVENLABS_HTTP_ERROR


def build_live_manifest_extras(
    config: ElevenLabsConfigSnapshot,
    *,
    total_retry_count: int = 0,
    adapter_version: str = ADAPTER_VERSION,
    request_id: str | None = None,
    use_smoke_profile: bool = True,
) -> dict[str, Any]:
    """Manifest fields for live ElevenLabs runs."""
    if use_smoke_profile:
        from content_brain.execution.voice_live_tts_smoke_profile import smoke_caps_snapshot

        caps = smoke_caps_snapshot()
    else:
        from content_brain.execution.voice_live_tts_safety_caps import safety_caps_snapshot

        caps = safety_caps_snapshot()

    extras: dict[str, Any] = {
        "provider": PROVIDER_ID,
        "provider_mode": PROVIDER_MODE_LIVE,
        "voice_id": config.voice_id,
        "model_id": config.model_id,
        "output_format": config.output_format,
        "real_provider_called": True,
        "retry_count": total_retry_count,
        "adapter_version": adapter_version,
        "safety_caps": caps,
    }
    if request_id:
        extras["request_id"] = request_id
    return extras


class ElevenLabsRuntimeAdapter:
    """
    Hardened ElevenLabs TTS adapter for Content Brain runtime.

    Never logs or exposes api_key. Inject http_client for tests.
    """

    def __init__(
        self,
        *,
        config: ElevenLabsConfigSnapshot,
        api_key: str,
        timeout_seconds: int = TIMEOUT_SECONDS,
        max_retry_attempts: int = MAX_RETRY_ATTEMPTS,
        cancel_check: Callable[[], bool] | None = None,
        http_client: HttpClient | None = None,
        allow_real_http: bool = False,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        key = str(api_key or "").strip()
        if not key:
            raise ValueError(CODE_ELEVENLABS_KEY_MISSING)

        if http_client is None:
            if not allow_real_http:
                raise RuntimeError(
                    "Real ElevenLabs HTTP is disabled — inject http_client for tests "
                    "or set allow_real_http=True (11H-2d+ only)."
                )
            http_client = RequestsHttpClient()

        self.config = config
        self._api_key = key
        self.timeout_seconds = int(timeout_seconds)
        self.max_retry_attempts = int(max_retry_attempts)
        self.cancel_check = cancel_check
        self._http = http_client
        self._sleep = sleep_fn or time.sleep

    def synthesize_segment(
        self,
        text: str,
        output_path: str | Path,
        *,
        segment_index: int,
        text_hash: str = "",
    ) -> ElevenLabsSegmentResult:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        resolved_hash = text_hash or f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"
        character_count = len(text)

        if self.cancel_check and self.cancel_check():
            return ElevenLabsSegmentResult(
                success=False,
                output_path=str(path),
                segment_index=segment_index,
                character_count=character_count,
                text_hash=resolved_hash,
                voice_id=self.config.voice_id,
                model_id=self.config.model_id,
                output_format=self.config.output_format,
                reject_code=CODE_ELEVENLABS_CANCELLED,
                reject_reasons=["Cooperative cancellation requested."],
                real_provider_called=False,
            )

        url = (
            f"{ELEVENLABS_TTS_BASE}/{self.config.voice_id}"
            f"?output_format={self.config.output_format}"
        )
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.85,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        }

        attempt = 0
        retried = False
        last_code = CODE_ELEVENLABS_HTTP_ERROR
        last_reasons = ["ElevenLabs request failed."]

        while attempt < self.max_retry_attempts:
            if self.cancel_check and self.cancel_check():
                return ElevenLabsSegmentResult(
                    success=False,
                    output_path=str(path),
                    segment_index=segment_index,
                    character_count=character_count,
                    text_hash=resolved_hash,
                    voice_id=self.config.voice_id,
                    model_id=self.config.model_id,
                    output_format=self.config.output_format,
                    reject_code=CODE_ELEVENLABS_CANCELLED,
                    reject_reasons=["Cooperative cancellation requested."],
                    retry_count=attempt,
                    retried=retried,
                    real_provider_called=False,
                )

            attempt += 1
            started = time.monotonic()
            try:
                response = self._http.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=float(self.timeout_seconds),
                )
            except Exception as exc:
                exc_name = type(exc).__name__.lower()
                is_timeout = "timeout" in exc_name or isinstance(exc, TimeoutError)
                last_code = CODE_ELEVENLABS_TIMEOUT if is_timeout else CODE_ELEVENLABS_HTTP_ERROR
                last_reasons = [
                    "ElevenLabs request timed out."
                    if is_timeout
                    else f"Network error: {type(exc).__name__}"
                ]
                if attempt < self.max_retry_attempts and is_timeout:
                    retried = True
                    self._sleep(BACKOFF_BASE_SECONDS * attempt)
                    continue
                return ElevenLabsSegmentResult(
                    success=False,
                    output_path=str(path),
                    segment_index=segment_index,
                    character_count=character_count,
                    text_hash=resolved_hash,
                    voice_id=self.config.voice_id,
                    model_id=self.config.model_id,
                    output_format=self.config.output_format,
                    reject_code=last_code,
                    reject_reasons=last_reasons,
                    retry_count=attempt,
                    retried=retried,
                    real_provider_called=True,
                )

            latency_ms = int((time.monotonic() - started) * 1000)
            status = int(getattr(response, "status_code", 0) or 0)
            request_id = _extract_request_id(getattr(response, "headers", {}))

            if status == 200:
                content = bytes(getattr(response, "content", b"") or b"")
                if len(content) == 0:
                    return ElevenLabsSegmentResult(
                        success=False,
                        output_path=str(path),
                        segment_index=segment_index,
                        character_count=character_count,
                        text_hash=resolved_hash,
                        voice_id=self.config.voice_id,
                        model_id=self.config.model_id,
                        output_format=self.config.output_format,
                        http_status=status,
                        latency_ms=latency_ms,
                        request_id=request_id,
                        reject_code=CODE_ELEVENLABS_EMPTY_AUDIO,
                        reject_reasons=["ElevenLabs returned empty audio body."],
                        retry_count=attempt - 1,
                        retried=retried,
                        real_provider_called=True,
                    )
                path.write_bytes(content)
                return ElevenLabsSegmentResult(
                    success=True,
                    output_path=str(path.resolve()),
                    segment_index=segment_index,
                    character_count=character_count,
                    size_bytes=path.stat().st_size,
                    text_hash=resolved_hash,
                    voice_id=self.config.voice_id,
                    model_id=self.config.model_id,
                    output_format=self.config.output_format,
                    http_status=status,
                    latency_ms=latency_ms,
                    request_id=request_id,
                    retry_count=max(0, attempt - 1),
                    retried=retried,
                    real_provider_called=True,
                )

            last_code = _map_http_status(status)
            last_reasons = [f"ElevenLabs HTTP {status}"]

            if status in RETRYABLE_STATUS and attempt < self.max_retry_attempts:
                retried = True
                self._sleep(BACKOFF_BASE_SECONDS * attempt)
                continue

            return ElevenLabsSegmentResult(
                success=False,
                output_path=str(path),
                segment_index=segment_index,
                character_count=character_count,
                text_hash=resolved_hash,
                voice_id=self.config.voice_id,
                model_id=self.config.model_id,
                output_format=self.config.output_format,
                http_status=status,
                latency_ms=latency_ms,
                request_id=request_id,
                reject_code=last_code,
                reject_reasons=last_reasons,
                retry_count=attempt,
                retried=retried,
                real_provider_called=True,
            )

        return ElevenLabsSegmentResult(
            success=False,
            output_path=str(path),
            segment_index=segment_index,
            character_count=character_count,
            text_hash=resolved_hash,
            voice_id=self.config.voice_id,
            model_id=self.config.model_id,
            output_format=self.config.output_format,
            reject_code=last_code,
            reject_reasons=last_reasons,
            retry_count=attempt,
            retried=retried,
            real_provider_called=True,
        )


__all__ = [
    "ADAPTER_VERSION",
    "PROVIDER_ID",
    "PROVIDER_MODE_LIVE",
    "CODE_ELEVENLABS_KEY_MISSING",
    "CODE_ELEVENLABS_RATE_LIMIT",
    "CODE_ELEVENLABS_TIMEOUT",
    "CODE_ELEVENLABS_HTTP_ERROR",
    "CODE_ELEVENLABS_EMPTY_AUDIO",
    "CODE_ELEVENLABS_CANCELLED",
    "ElevenLabsSegmentResult",
    "ElevenLabsRuntimeAdapter",
    "RequestsHttpClient",
    "HttpClient",
    "build_live_manifest_extras",
]
