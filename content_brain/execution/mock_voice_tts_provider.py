"""
Phase 11H-2a — mock voice TTS provider (no network, no ElevenLabs API).

Generates deterministic non-empty fake MP3 files for validation and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

PROVIDER_ID = "mock_elevenlabs"
PROVIDER_MODE = "mock"

# Minimal MP3 frame header bytes (not playable audio — sufficient for size/extension checks).
_FAKE_MP3_PREFIX = bytes([0xFF, 0xFB, 0x90, 0x00])


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class MockVoiceSegmentResult:
    success: bool
    output_path: str
    segment_index: int
    character_count: int
    size_bytes: int = 0
    text_hash: str = ""
    reject_code: str | None = None
    reject_reasons: list[str] = field(default_factory=list)
    retried: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "segment_index": self.segment_index,
            "character_count": self.character_count,
            "size_bytes": self.size_bytes,
            "text_hash": self.text_hash,
            "reject_code": self.reject_code,
            "reject_reasons": list(self.reject_reasons),
            "retried": self.retried,
            "provider": PROVIDER_ID,
            "provider_mode": PROVIDER_MODE,
            "real_provider_called": False,
        }


class MockVoiceTtsProvider:
    """Write deterministic fake MP3 artifacts — never calls external APIs."""

    def __init__(
        self,
        *,
        fail_on_segment: int | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ):
        self.fail_on_segment = fail_on_segment
        self.cancel_check = cancel_check

    def synthesize_segment(
        self,
        text: str,
        output_path: str | Path,
        *,
        segment_index: int,
        text_hash: str = "",
    ) -> MockVoiceSegmentResult:
        if self.cancel_check and self.cancel_check():
            return MockVoiceSegmentResult(
                success=False,
                output_path=str(output_path),
                segment_index=segment_index,
                character_count=len(text),
                text_hash=text_hash,
                reject_code="CANCELLED",
                reject_reasons=["Cooperative cancellation requested."],
            )

        if self.fail_on_segment is not None and segment_index == self.fail_on_segment:
            return MockVoiceSegmentResult(
                success=False,
                output_path=str(output_path),
                segment_index=segment_index,
                character_count=len(text),
                text_hash=text_hash,
                reject_code="PROVIDER_ERROR",
                reject_reasons=[f"Simulated provider failure on segment {segment_index}."],
            )

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256(f"{segment_index}:{text}".encode("utf-8")).digest()
        payload = _FAKE_MP3_PREFIX + digest + b"\x00" * 64
        path.write_bytes(payload)

        resolved_hash = text_hash or f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"
        return MockVoiceSegmentResult(
            success=True,
            output_path=str(path.resolve()),
            segment_index=segment_index,
            character_count=len(text),
            size_bytes=path.stat().st_size,
            text_hash=resolved_hash,
        )


__all__ = [
    "PROVIDER_ID",
    "PROVIDER_MODE",
    "MockVoiceSegmentResult",
    "MockVoiceTtsProvider",
]
