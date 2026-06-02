"""
Phase 11H-2c — ElevenLabs runtime safety caps (live mode — not enabled in 11H-2c).
"""

from __future__ import annotations

MAX_SEGMENTS_PER_RUN = 20
MAX_CHARACTERS_PER_RUN = 5000
MAX_RETRY_ATTEMPTS = 3
TIMEOUT_SECONDS = 120
MAX_ESTIMATED_COST_USD = 5.0
MIN_ARTIFACT_BYTES = 1
BACKOFF_BASE_SECONDS = 2.0

SAFETY_CAPS_VERSION = "11h2c_v1"


def safety_caps_snapshot() -> dict[str, float | int]:
    return {
        "max_segments_per_run": MAX_SEGMENTS_PER_RUN,
        "max_characters_per_run": MAX_CHARACTERS_PER_RUN,
        "max_retry_attempts": MAX_RETRY_ATTEMPTS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_estimated_cost_usd": MAX_ESTIMATED_COST_USD,
        "min_artifact_bytes": MIN_ARTIFACT_BYTES,
    }


__all__ = [
    "SAFETY_CAPS_VERSION",
    "MAX_SEGMENTS_PER_RUN",
    "MAX_CHARACTERS_PER_RUN",
    "MAX_RETRY_ATTEMPTS",
    "TIMEOUT_SECONDS",
    "MAX_ESTIMATED_COST_USD",
    "MIN_ARTIFACT_BYTES",
    "BACKOFF_BASE_SECONDS",
    "safety_caps_snapshot",
]
