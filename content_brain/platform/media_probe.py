"""Lightweight ffprobe helpers for delivery quality checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

DURATION_TOLERANCE_SECONDS = 0.5
DURATION_LOSS_RATIO_FAIL = 0.05


def probe_duration_seconds(path: str | Path) -> float | None:
    target = Path(path)
    if not target.is_file() or target.stat().st_size <= 0:
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def probe_has_audio_stream(path: str | Path) -> bool:
    target = Path(path)
    if not target.is_file():
        return False
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "audio" in (proc.stdout or "")


def probe_mean_volume_db(path: str | Path) -> float | None:
    target = Path(path)
    if not target.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(target),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    import re

    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", proc.stderr or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def duration_preserved(
    *,
    assembled_seconds: float | None,
    deliverable_seconds: float | None,
    tolerance: float = DURATION_TOLERANCE_SECONDS,
) -> bool:
    if assembled_seconds is None or deliverable_seconds is None:
        return False
    if assembled_seconds <= 0:
        return deliverable_seconds <= tolerance
    return deliverable_seconds >= assembled_seconds - tolerance


def duration_loss_ratio(
    *,
    assembled_seconds: float | None,
    deliverable_seconds: float | None,
) -> float | None:
    if assembled_seconds is None or deliverable_seconds is None or assembled_seconds <= 0:
        return None
    loss = max(0.0, assembled_seconds - deliverable_seconds)
    return loss / assembled_seconds


__all__ = [
    "DURATION_LOSS_RATIO_FAIL",
    "DURATION_TOLERANCE_SECONDS",
    "duration_loss_ratio",
    "duration_preserved",
    "probe_duration_seconds",
    "probe_has_audio_stream",
    "probe_mean_volume_db",
]
