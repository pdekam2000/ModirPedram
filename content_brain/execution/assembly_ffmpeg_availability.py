"""
Phase 11J-19 — FFmpeg binary availability check (version probe only).

Locates the ffmpeg binary and runs ``ffmpeg -version``. Never performs media processing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROBE_TIMEOUT_SECONDS = 15


@dataclass
class FFmpegAvailabilityResult:
    available: bool
    ffmpeg_path: str | None = None
    version_line: str | None = None
    error: str | None = None
    checked_env_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": bool(self.available),
            "ffmpeg_path": self.ffmpeg_path,
            "version_line": self.version_line,
            "error": self.error,
            "checked_env_keys": list(self.checked_env_keys),
        }


def resolve_ffmpeg_binary() -> str | None:
    """Return absolute path to ffmpeg if discoverable, else None."""
    env_path = os.getenv("FFMPEG_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return str(Path(env_path).resolve())
    which = shutil.which("ffmpeg")
    if which:
        return str(Path(which).resolve())
    which_exe = shutil.which("ffmpeg.exe")
    if which_exe:
        return str(Path(which_exe).resolve())
    return None


def check_ffmpeg_availability(*, timeout_seconds: int = PROBE_TIMEOUT_SECONDS) -> FFmpegAvailabilityResult:
    """
    Probe ffmpeg availability via ``ffmpeg -version``.

    Does not decode, encode, or write media files.
    """
    checked: list[str] = []
    if os.getenv("FFMPEG_PATH"):
        checked.append("FFMPEG_PATH")
    checked.append("PATH")

    binary = resolve_ffmpeg_binary()
    if not binary:
        return FFmpegAvailabilityResult(
            available=False,
            ffmpeg_path=None,
            error="FFmpeg binary not found on PATH or FFMPEG_PATH.",
            checked_env_keys=checked,
        )

    try:
        proc = subprocess.run(
            [binary, "-version"],
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return FFmpegAvailabilityResult(
            available=False,
            ffmpeg_path=binary,
            error="FFmpeg version probe timed out.",
            checked_env_keys=checked,
        )
    except OSError as exc:
        return FFmpegAvailabilityResult(
            available=False,
            ffmpeg_path=binary,
            error=str(exc),
            checked_env_keys=checked,
        )

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    combined = stdout or stderr
    version_line = combined.splitlines()[0] if combined else None

    if proc.returncode != 0 or not version_line:
        return FFmpegAvailabilityResult(
            available=False,
            ffmpeg_path=binary,
            version_line=version_line,
            error=f"ffmpeg -version failed (exit {proc.returncode}).",
            checked_env_keys=checked,
        )

    return FFmpegAvailabilityResult(
        available=True,
        ffmpeg_path=binary,
        version_line=version_line,
        checked_env_keys=checked,
    )


__all__ = [
    "FFmpegAvailabilityResult",
    "PROBE_TIMEOUT_SECONDS",
    "check_ffmpeg_availability",
    "resolve_ffmpeg_binary",
]
