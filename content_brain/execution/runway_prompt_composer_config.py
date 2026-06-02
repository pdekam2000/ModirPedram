"""
Phase 12J-C — RunwayPromptComposer feature flag (default off).
"""

from __future__ import annotations

import os
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def enable_runway_prompt_composer(session: dict[str, Any] | None = None) -> bool:
    """
    Return True when the composer path is active.

    Precedence:
    1. brief_snapshot.run_context.enable_runway_prompt_composer (explicit bool)
    2. session.enable_runway_prompt_composer (explicit bool)
    3. MODIR_ENABLE_RUNWAY_PROMPT_COMPOSER env (true/1/yes)
    Default: False
    """
    if session is not None:
        if session.get("enable_runway_prompt_composer") is True:
            return True
        if session.get("enable_runway_prompt_composer") is False:
            return False

        brief = _dict(session.get("brief_snapshot"))
        run_context = _dict(brief.get("run_context"))
        if run_context.get("enable_runway_prompt_composer") is True:
            return True
        if run_context.get("enable_runway_prompt_composer") is False:
            return False

    env = os.getenv("MODIR_ENABLE_RUNWAY_PROMPT_COMPOSER", "").strip().lower()
    return env in {"true", "1", "yes", "on"}


__all__ = ["enable_runway_prompt_composer"]
