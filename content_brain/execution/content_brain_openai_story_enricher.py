"""
Optional OpenAI story enrichment for Content Brain Test Studio.

Polishes rule-based story briefs into audience-friendly narratives while
preserving topic, SEO title, clip count, and output language.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

try:
    from core.provider_registry_engine import ProviderRegistryEngine
except ImportError:  # pragma: no cover
    ProviderRegistryEngine = None  # type: ignore[misc, assignment]

ENRICHMENT_ID = "openai_story_enricher"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_OUTPUT_TOKENS = 2200
REQUEST_TIMEOUT_SECONDS = 60.0

REQUIRED_STORY_KEYS = (
    "title",
    "logline",
    "main_character",
    "setting",
    "conflict_tension",
    "visual_hook",
    "emotional_arc",
    "ending_beat",
    "clip_beats",
)

DRY_RUN_RESPONSE: dict[str, Any] = {
    "title": "",
    "logline": "",
    "main_character": "",
    "setting": "",
    "conflict_tension": "",
    "visual_hook": "",
    "emotional_arc": "",
    "ending_beat": "",
    "clip_beats": [],
}


@dataclass
class StoryEnrichmentResult:
    applied: bool = False
    provider: str = ENRICHMENT_ID
    model: str = ""
    story: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "provider": self.provider,
            "model": self.model,
            "story": dict(self.story),
            "notes": list(self.notes),
        }


class OpenAIStoryEnricher:
    """Optional LLM polish layer for RunwayStoryBrief payloads."""

    def __init__(
        self,
        *,
        registry_engine: Any | None = None,
        model: str | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.registry_engine = registry_engine
        self.model = (model or os.getenv("OPENAI_STORY_MODEL") or DEFAULT_MODEL).strip()
        self.dry_run = (
            dry_run
            if dry_run is not None
            else os.getenv("OPENAI_STORY_ENRICH_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        )
        self._api_key = ""
        self.enabled = self._resolve_enabled_state() or self.dry_run
        self._client: Any | None = None

    def enrich(
        self,
        *,
        topic: str,
        seo_title: str,
        language_code: str,
        mood: str,
        platform: str,
        clip_count: int,
        clip_duration_seconds: int,
        related_trends: list[str] | None,
        base_story: dict[str, Any],
        content_strategy: str = "",
        strategy_purpose: str = "",
        forbidden_filler: list[str] | None = None,
    ) -> StoryEnrichmentResult:
        if not self.enabled:
            return StoryEnrichmentResult(notes=["openai_story_enricher_disabled"])

        payload = _build_request_payload(
            topic=topic,
            seo_title=seo_title,
            language_code=language_code,
            mood=mood,
            platform=platform,
            clip_count=clip_count,
            clip_duration_seconds=clip_duration_seconds,
            related_trends=related_trends or [],
            base_story=base_story,
            content_strategy=content_strategy,
            strategy_purpose=strategy_purpose,
            forbidden_filler=forbidden_filler or [],
        )

        if self.dry_run:
            response_data = _build_dry_run_story(base_story, seo_title, clip_count)
            notes = ["dry_run_story_enrichment"]
        else:
            if not self._api_key or OpenAI is None:
                return StoryEnrichmentResult(notes=["openai_client_unavailable"])
            response_data = self._call_openai(payload)
            if not response_data:
                return StoryEnrichmentResult(notes=["openai_story_enrichment_failed"])
            notes = ["openai_story_enrichment_applied"]

        if not _validate_story_payload(response_data, clip_count):
            return StoryEnrichmentResult(notes=["openai_story_enrichment_invalid"])

        merged = dict(base_story)
        merged.update({key: response_data[key] for key in REQUIRED_STORY_KEYS})
        merged["openai_enriched"] = True
        merged["builder_version"] = str(base_story.get("builder_version") or "") + "+openai_story"

        if not _topic_preserved(topic, merged):
            return StoryEnrichmentResult(notes=["openai_story_rejected_topic_drift"])

        if not _strategy_preserved(content_strategy, merged, forbidden_filler or []):
            return StoryEnrichmentResult(notes=["openai_story_rejected_strategy_drift"])

        from content_brain.execution.content_brain_language_authority import audit_language_authority

        language_audit = audit_language_authority(
            topic=topic,
            expected_language_code=language_code,
            seo_title=seo_title,
            story_payload=merged,
        )
        if not language_audit.passed:
            return StoryEnrichmentResult(notes=["openai_story_rejected_language_drift"])

        return StoryEnrichmentResult(
            applied=True,
            model=self.model,
            story=merged,
            notes=notes,
        )

    def _get_registry_engine(self) -> Any:
        if self.registry_engine is not None:
            return self.registry_engine
        if ProviderRegistryEngine is None:
            raise RuntimeError("ProviderRegistryEngine is unavailable.")
        return ProviderRegistryEngine()

    def _resolve_enabled_state(self) -> bool:
        try:
            engine = self._get_registry_engine()
        except Exception:
            return bool(str(os.getenv("OPENAI_API_KEY") or "").strip())

        for category, provider in (("llm", "openai"), (ProviderRegistryEngine.TREND_ENRICHMENT_CATEGORY, "openai_trend_enricher")):
            if engine.credentials_ready(category, provider):
                creds = engine.get_provider_credentials(category, provider)
                api_key = creds.get("OPENAI_API_KEY", "").strip()
                if api_key:
                    self._api_key = api_key
                    return True

        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if api_key:
            self._api_key = api_key
            return True
        return False

    def _call_openai(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client
        if client is None:
            client = OpenAI(api_key=self._api_key, timeout=REQUEST_TIMEOUT_SECONDS)
            self._client = client

        system_prompt = (
            "You write short-form vertical video story briefs for YouTube Shorts and social platforms. "
            "Return JSON only. Preserve the user's topic meaning. "
            "Write ALL text in the requested language_code.\n\n"
            "TITLE RULES (for the title field):\n"
            "- SEO optimized for YouTube Shorts\n"
            "- Must contain a power word: Shocking, Secret, Never, Finally, Insane, Unbelievable, Hidden, or Revealed\n"
            "- Must be under 60 characters\n"
            "- Must create a curiosity gap — viewer must click to know the answer\n"
            "- Example: \"The Shocking Truth About Ocean Depths 🌊\"\n\n"
            "STORY RULES:\n"
            "- Hook in first 3 seconds must make viewer UNABLE to scroll\n"
            "- Use openers like \"Did you know...\", \"Most people don't know...\", or \"Scientists just discovered...\"\n"
            "- Every sentence must make viewer want to see the next one\n"
            "- End with a cliffhanger or surprising twist\n"
            "- CTA at end: \"Follow for daily mind-blowing facts\"\n"
            "- Language: conversational English, 8th grade reading level\n"
            "- Tone: amazed, urgent, slightly dramatic\n\n"
            "AUDIENCE: English speaking, 18-35 years old, curious about science/nature/space/animals\n\n"
            "clip_beats must contain exactly clip_count items; each beat is one 10-second clip direction. "
            "Follow content_strategy and strategy_purpose from the user payload. "
            "For instructional/educational strategies: teach step-by-step; no generic cinematic filler. "
            "Do not invent unrelated genres or drift away from the topic."
        )
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.55,
                max_tokens=MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception:
            return {}

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


def maybe_enrich_story_brief(
    brief: Any,
    *,
    topic: str,
    seo_title: str,
    language_code: str,
    mood: str,
    platform: str,
    related_trends: list[str] | None = None,
    content_strategy: str = "",
    strategy_purpose: str = "",
    forbidden_filler: list[str] | None = None,
) -> tuple[Any, StoryEnrichmentResult]:
    """Apply optional OpenAI enrichment to a RunwayStoryBrief instance."""
    base_story = brief.to_dict() if hasattr(brief, "to_dict") else dict(brief)
    enricher = OpenAIStoryEnricher()
    result = enricher.enrich(
        topic=topic,
        seo_title=seo_title,
        language_code=language_code,
        mood=mood,
        platform=platform,
        clip_count=int(getattr(brief, "clip_count", len(base_story.get("clip_beats") or [])) or 3),
        clip_duration_seconds=int(getattr(brief, "duration_seconds", 10) or 10),
        related_trends=related_trends,
        base_story=base_story,
        content_strategy=content_strategy,
        strategy_purpose=strategy_purpose,
        forbidden_filler=forbidden_filler,
    )
    if not result.applied:
        return brief, result

    for key in REQUIRED_STORY_KEYS:
        if key in result.story and hasattr(brief, key):
            setattr(brief, key, result.story[key])
    return brief, result


def _build_request_payload(
    *,
    topic: str,
    seo_title: str,
    language_code: str,
    mood: str,
    platform: str,
    clip_count: int,
    clip_duration_seconds: int,
    related_trends: list[str],
    base_story: dict[str, Any],
    content_strategy: str = "",
    strategy_purpose: str = "",
    forbidden_filler: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "seo_title": seo_title,
        "language_code": language_code,
        "mood": mood,
        "platform": platform,
        "clip_count": clip_count,
        "clip_duration_seconds": clip_duration_seconds,
        "related_trends": related_trends[:5],
        "content_strategy": content_strategy,
        "strategy_purpose": strategy_purpose,
        "forbidden_filler": list(forbidden_filler or []),
        "base_story": {key: base_story.get(key) for key in REQUIRED_STORY_KEYS},
        "required_keys": list(REQUIRED_STORY_KEYS),
        "title_rules": {
            "max_chars": 60,
            "power_words": [
                "Shocking", "Secret", "Never", "Finally", "Insane",
                "Unbelievable", "Hidden", "Revealed",
            ],
            "curiosity_gap_required": True,
            "example": "The Shocking Truth About Ocean Depths 🌊",
        },
        "story_rules": {
            "hook_seconds": 3,
            "openers": ["Did you know...", "Most people don't know...", "Scientists just discovered..."],
            "cta": "Follow for daily mind-blowing facts",
            "reading_level": "8th grade",
            "tone": "amazed, urgent, slightly dramatic",
            "audience": "English 18-35, science/nature/space/animals curiosity",
        },
    }


def _build_dry_run_story(base_story: dict[str, Any], seo_title: str, clip_count: int) -> dict[str, Any]:
    story = {key: base_story.get(key) for key in REQUIRED_STORY_KEYS}
    if seo_title:
        story["title"] = seo_title
    beats = list(story.get("clip_beats") or [])
    if len(beats) < clip_count:
        beats.extend([f"Clip {index + 1} beat for {seo_title or base_story.get('source_topic', 'topic')}" for index in range(len(beats), clip_count)])
    story["clip_beats"] = beats[:clip_count]
    return story


def _validate_story_payload(payload: dict[str, Any], clip_count: int) -> bool:
    for key in REQUIRED_STORY_KEYS:
        if key not in payload:
            return False
    beats = payload.get("clip_beats")
    if not isinstance(beats, list) or len(beats) != clip_count:
        return False
    return all(str(item).strip() for item in beats)


def _topic_preserved(topic: str, story: dict[str, Any]) -> bool:
    from content_brain.execution.content_brain_topic_authority import audit_story_brief_preservation

    audit = audit_story_brief_preservation(topic, story)
    return float(audit.topic_preservation_score) >= 0.34


def _strategy_preserved(
    content_strategy: str,
    story: dict[str, Any],
    forbidden_filler: list[str],
) -> bool:
    if not content_strategy or content_strategy == "cinematic_narrative":
        return True
    if not content_strategy.startswith("instructional") and "instructional" not in content_strategy:
        if content_strategy not in {
            "recipe_tutorial",
            "educational_tech",
            "documentary",
            "journalistic",
            "educational_lifestyle",
        }:
            return True
    corpus = " ".join(
        [
            str(story.get("logline") or ""),
            str(story.get("conflict_tension") or ""),
            str(story.get("visual_hook") or ""),
            str(story.get("ending_beat") or ""),
            " ".join(str(b) for b in story.get("clip_beats") or []),
        ]
    ).lower()
    if any(phrase in corpus for phrase in forbidden_filler):
        return False
    if content_strategy == "instructional_fishing":
        technique_terms = ("lure", "cast", "hook", "depth", "strike", "technique", "retrieve", "tackle")
        hits = sum(1 for term in technique_terms if term in corpus)
        return hits >= 2
    return True


__all__ = [
    "OpenAIStoryEnricher",
    "StoryEnrichmentResult",
    "maybe_enrich_story_brief",
]
