"""
Runway execution modes for Live Smoke and future autonomous production runs.

MANUAL — legacy operator approval gates.
SEMI_AUTO — auto image-ready + auto generate with safety validators; download manual.
FULL_AUTO — no operator approvals; validated automatic progression (default for Live Smoke).
"""

from __future__ import annotations

EXECUTION_MODE_MANUAL = "MANUAL"
EXECUTION_MODE_SEMI_AUTO = "SEMI_AUTO"
EXECUTION_MODE_FULL_AUTO = "FULL_AUTO"
DEFAULT_LIVE_SMOKE_EXECUTION_MODE = EXECUTION_MODE_FULL_AUTO

SUPPORTED_EXECUTION_MODES = (
    EXECUTION_MODE_MANUAL,
    EXECUTION_MODE_SEMI_AUTO,
    EXECUTION_MODE_FULL_AUTO,
)


def normalize_execution_mode(value: str | None) -> str:
    cleaned = str(value or DEFAULT_LIVE_SMOKE_EXECUTION_MODE).strip().upper()
    if cleaned in SUPPORTED_EXECUTION_MODES:
        return cleaned
    return DEFAULT_LIVE_SMOKE_EXECUTION_MODE


def requires_operator_approval(
    execution_mode: str,
    control_key: str,
) -> bool:
    mode = normalize_execution_mode(execution_mode)
    if mode == EXECUTION_MODE_MANUAL:
        return True
    if mode == EXECUTION_MODE_FULL_AUTO:
        return False
    # SEMI_AUTO — keep download approval manual; generate/image handled by auto validators.
    if control_key == "download_mp4_button":
        return True
    return False


def requires_manual_image_ready_hold(execution_mode: str) -> bool:
    return normalize_execution_mode(execution_mode) == EXECUTION_MODE_MANUAL


__all__ = [
    "DEFAULT_LIVE_SMOKE_EXECUTION_MODE",
    "EXECUTION_MODE_FULL_AUTO",
    "EXECUTION_MODE_MANUAL",
    "EXECUTION_MODE_SEMI_AUTO",
    "normalize_execution_mode",
    "requires_manual_image_ready_hold",
    "requires_operator_approval",
]
