"""
Topic Universe Agent — facade for title bank generation.

Delegates to execution-layer builder + studio orchestrator.
"""

from __future__ import annotations

from content_brain.execution.topic_universe_builder import (
    BUILDER_VERSION,
    DEFAULT_TITLE_TARGET,
    TitleBankEntry,
    TitleBankResult,
    TopicScopeResult,
    build_title_bank,
    deduplicate_title_entries,
    detect_topic_scope,
    normalize_title,
    title_passes_topic_authority,
)
from content_brain.execution.topic_universe_studio import (
    DEFAULT_EXPORT_DIR,
    TopicUniverseInput,
    TopicUniverseRunResult,
    TopicUniverseStudio,
    run_topic_universe_studio,
)

AGENT_VERSION = "topic_universe_agent_v1"


class TopicUniverseAgent:
    """Agent entry point for SEO title bank generation."""

    VERSION = AGENT_VERSION

    def __init__(self, *, studio: TopicUniverseStudio | None = None) -> None:
        self.studio = studio or TopicUniverseStudio()

    def run(self, payload: TopicUniverseInput | dict) -> TopicUniverseRunResult:
        return self.studio.run(payload)

    @staticmethod
    def detect_scope(topic: str, *, language_code: str | None = None) -> TopicScopeResult:
        return detect_topic_scope(topic, language_code=language_code)


def run_topic_universe_agent(**kwargs) -> dict:
    return run_topic_universe_studio(**kwargs)


__all__ = [
    "AGENT_VERSION",
    "TopicUniverseAgent",
    "run_topic_universe_agent",
    "build_title_bank",
    "detect_topic_scope",
]
