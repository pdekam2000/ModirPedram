"""Canonical subprocess exit codes for pwmap.py and runway_agent.py."""

from __future__ import annotations

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_SESSION_NOT_READY = 2

EXIT_CODE_MEANINGS: dict[int, str] = {
    EXIT_OK: "Success — generation completed.",
    EXIT_RUNTIME_ERROR: (
        "Runtime error — clip generation failed, Google Chrome could not launch, "
        "Playwright is missing, or an unexpected agent error occurred."
    ),
    EXIT_SESSION_NOT_READY: (
        "Session/browser not ready — no saved Runway session at "
        "project_brain/sessions/runway_session.json, Runway login expired, "
        "or invalid CLI arguments (argparse also uses exit code 2)."
    ),
}


def exit_code_message(code: int) -> str:
    return EXIT_CODE_MEANINGS.get(int(code), f"Unknown exit code {code}")


__all__ = [
    "EXIT_CODE_MEANINGS",
    "EXIT_OK",
    "EXIT_RUNTIME_ERROR",
    "EXIT_SESSION_NOT_READY",
    "exit_code_message",
]
