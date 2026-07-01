"""pwmap agent — per-clip and subprocess timeout policy for long multi-clip runs."""

from __future__ import annotations

import os

CLIP_TIMEOUT_BY_COUNT: dict[int, int] = {
    1: 900,
    2: 1200,
    3: 1500,
    4: 1800,
}
FINALIZATION_BUFFER_SECONDS = 900
MAX_CLIP_COUNT = 6


def clip_count_from_job(job: dict) -> int:
    prompts = job.get("prompts")
    if isinstance(prompts, list) and prompts:
        return max(1, min(MAX_CLIP_COUNT, len(prompts)))
    if str(job.get("prompt") or "").strip():
        return 1
    return 1


def resolve_clip_timeout_seconds(clip_count: int) -> int:
    """Per-clip --timeout for pwmap runway_agent.py."""
    env_value = str(os.environ.get("PWMAP_CLIP_TIMEOUT_SECONDS") or "").strip()
    if env_value:
        return max(60, int(env_value))
    count = max(1, min(MAX_CLIP_COUNT, int(clip_count)))
    if count in CLIP_TIMEOUT_BY_COUNT:
        return CLIP_TIMEOUT_BY_COUNT[count]
    return CLIP_TIMEOUT_BY_COUNT[4] + (count - 4) * 300


def resolve_subprocess_timeout_seconds(
    clip_count: int,
    *,
    clip_timeout_seconds: int | None = None,
) -> int:
    """ModirAgentOS subprocess.run timeout — must exceed pwmap total wait budget."""
    env_value = str(os.environ.get("PWMAP_SUBPROCESS_TIMEOUT_SECONDS") or "").strip()
    if env_value:
        return max(60, int(env_value))
    per_clip = int(clip_timeout_seconds or resolve_clip_timeout_seconds(clip_count))
    count = max(1, min(MAX_CLIP_COUNT, int(clip_count)))
    return (per_clip * count) + FINALIZATION_BUFFER_SECONDS


__all__ = [
    "CLIP_TIMEOUT_BY_COUNT",
    "FINALIZATION_BUFFER_SECONDS",
    "clip_count_from_job",
    "resolve_clip_timeout_seconds",
    "resolve_subprocess_timeout_seconds",
]
