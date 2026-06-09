"""
Setting Builder V3 — real-world, topic-oriented settings (not runtime prompt-engine language).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from content_brain.execution.content_brain_topic_story_detail import (
    TopicStoryDetail,
    _is_generic_runtime_setting,
    build_topic_story_detail,
)
from content_brain.execution.domain_knowledge_layer import DomainKnowledgeProfile, get_domain_profile

BUILDER_VERSION = "setting_builder_v3"

GENERIC_SETTING_FALLBACK = (
    "a single continuous environment with strong depth and readable vertical framing"
)


@dataclass
class SettingBuildResult:
    setting: str
    setting_candidates: tuple[str, ...]
    source: str
    is_topic_specific: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "setting": self.setting,
            "setting_candidates": list(self.setting_candidates),
            "source": self.source,
            "is_topic_specific": self.is_topic_specific,
            "builder_version": BUILDER_VERSION,
        }


def build_topic_setting(
    topic: str,
    *,
    explicit_setting: str = "",
    topic_detail: TopicStoryDetail | None = None,
    domain_profile: DomainKnowledgeProfile | None = None,
    topic_category: str = "",
    content_strategy: str = "",
) -> SettingBuildResult:
    explicit = re.sub(r"\s+", " ", str(explicit_setting or "").strip())
    if explicit and not _is_generic_runtime_setting(explicit):
        return SettingBuildResult(
            setting=explicit,
            setting_candidates=(explicit,),
            source="user_explicit",
            is_topic_specific=True,
        )

    detail = topic_detail or build_topic_story_detail(
        topic,
        topic_category=topic_category,
        content_strategy=content_strategy,
    )
    profile = domain_profile or get_domain_profile(topic, topic_category=topic_category)

    candidates: list[str] = []
    candidates.extend(item for item in detail.settings if item and not _is_generic_runtime_setting(item))
    if profile.setting_en and not _is_generic_runtime_setting(profile.setting_en):
        candidates.append(profile.setting_en)

    topic_setting = _extract_setting_from_topic_text(topic)
    if topic_setting:
        candidates.append(topic_setting)

    candidates = list(dict.fromkeys(item for item in candidates if item))
    if candidates:
        primary = _compose_setting_phrase(candidates[:3])
        return SettingBuildResult(
            setting=primary,
            setting_candidates=tuple(candidates),
            source="topic_pack" if detail.source == "topic_pack" else "topic_story_detail",
            is_topic_specific=True,
        )

    fallback = profile.setting_en or GENERIC_SETTING_FALLBACK
    return SettingBuildResult(
        setting=fallback,
        setting_candidates=(fallback,),
        source="domain_fallback",
        is_topic_specific=bool(profile.setting_en and not _is_generic_runtime_setting(profile.setting_en)),
    )


def _extract_setting_from_topic_text(topic: str) -> str:
    match = re.search(
        r"\b(?:on|in|inside|within|above|beneath|at)\s+(?:a|an|the)\s+([^.!?]{4,90})",
        str(topic or ""),
        re.I,
    )
    if match:
        phrase = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        if phrase and not _is_generic_runtime_setting(phrase):
            return phrase
    return ""


def _compose_setting_phrase(candidates: list[str]) -> str:
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 2:
        return f"{candidates[0]}, {candidates[1]}"
    return f"{candidates[0]}, {candidates[1]}, {candidates[2]}"


__all__ = [
    "BUILDER_VERSION",
    "SettingBuildResult",
    "build_topic_setting",
    "GENERIC_SETTING_FALLBACK",
]
