"""
Session → provider-ready prompts adapter (Phase 10I, video_generation category).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any

from content_brain.execution.provider_categories import CATEGORY_VIDEO, normalize_provider_key

ENGINE_NAME = "SessionPromptAdapter"
ENGINE_VERSION = "10i_v1"
COMPOSER_VERSION_12J_C = "12j_c_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
RUNWAY_MAX_PROMPT_CHARS = 950


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


@dataclass
class PromptBundle:
    adapter_version: str
    adapter_source: str
    provider_category: str
    clip_count: int
    target_clip_count: int
    provider_hint: str
    prompts: list[str]
    clip_metadata: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_version": self.adapter_version,
            "adapter_source": self.adapter_source,
            "provider_category": self.provider_category,
            "clip_count": self.clip_count,
            "target_clip_count": self.target_clip_count,
            "provider_hint": self.provider_hint,
            "prompts": self.prompts,
            "clip_metadata": self.clip_metadata,
            "metadata": self.metadata,
        }


class SessionPromptAdapter:
    """Map brief_snapshot director shots to VideoProviderRouter prompt strings."""

    def build(self, session: dict[str, Any], provider: str) -> PromptBundle:
        brief = _dict(session.get("brief_snapshot"))
        format_plan = _dict(brief.get("video_format_plan"))
        simulation = _dict(session.get("simulation_report"))

        target = int(
            format_plan.get("clip_count")
            or simulation.get("estimated_clip_count")
            or 0
        )

        shots, source = self._resolve_shots(brief)
        if not shots:
            raise ValueError("PROMPT_ADAPTER_FAILED: no director shots found in brief_snapshot.")

        run_context = _dict(brief.get("run_context"))
        composed_by_clip = self._composed_clip_index(run_context)
        composer_active = run_context.get("runway_composer_version") == COMPOSER_VERSION_12J_C

        provider_key = normalize_provider_key(provider)
        prompts: list[str] = []
        clip_metadata: list[dict[str, Any]] = []
        warnings: list[str] = []
        pre_truncation_prompts: list[str] = []
        prompt_lineage: list[dict[str, Any]] = []
        quality_warnings: list[str] = []

        for shot in sorted(shots, key=lambda item: int(item.get("clip_number") or 0)):
            clip_number = int(shot.get("clip_number") or len(prompts) + 1)
            pre_prompt = self._compose_prompt(shot, source, provider_key, truncate=False)
            pre_truncation_prompts.append(pre_prompt)
            prompt = pre_prompt
            if provider_key in {"runway", "runway_browser"} and len(prompt) > RUNWAY_MAX_PROMPT_CHARS:
                if composer_active:
                    prompt = self._truncate_runway_with_priority(prompt)
                else:
                    prompt = prompt[:RUNWAY_MAX_PROMPT_CHARS].rsplit(" ", 1)[0].strip()

            prompts.append(prompt)
            composed = composed_by_clip.get(clip_number) or {}
            lineage = _dict(composed.get("lineage")) if composed else {}
            quality = _dict(composed.get("quality_score")) if composed else {}
            if quality and not quality.get("pass"):
                quality_warnings.append(
                    f"clip {clip_number}: {', '.join(quality.get('failure_reasons') or [])}"
                )
            if lineage and len(prompt) < len(pre_prompt):
                lineage = dict(lineage)
                lineage["truncation_applied_by"] = "adapter"

            clip_metadata.append(
                {
                    "clip_number": clip_number,
                    "duration_seconds": shot.get("duration_seconds"),
                    "beat_id": shot.get("beat_id"),
                    "source_shot_id": shot.get("shot_id"),
                    "prompt_hash": f"sha256:{sha256(prompt.encode('utf-8')).hexdigest()}",
                    "lineage": lineage or None,
                    "quality_score": quality or None,
                }
            )
            if lineage:
                prompt_lineage.append({"clip_number": clip_number, **lineage})

        if target and len(prompts) > target:
            warnings.append(f"Trimmed prompts from {len(prompts)} to target clip_count {target}.")
            prompts = prompts[:target]
            clip_metadata = clip_metadata[:target]

        if target and len(prompts) < target:
            raise ValueError(
                f"CLIP_COUNT_MISMATCH: {len(prompts)} prompts for target clip_count {target}."
            )

        if not prompts:
            raise ValueError("PROMPT_ADAPTER_FAILED: empty prompt list after adaptation.")

        metadata: dict[str, Any] = {
            "adapter_provenance": {
                "engine": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
                "evaluated_at": _now(),
            },
            "sources_used": [source, "video_format_plan", "brief_snapshot"],
            "warnings": warnings,
        }
        if composer_active:
            metadata["runway_composer_version"] = COMPOSER_VERSION_12J_C
            metadata["pre_truncation_prompts"] = pre_truncation_prompts
            metadata["prompt_lineage"] = prompt_lineage
            if quality_warnings:
                metadata["quality_warnings"] = quality_warnings

        return PromptBundle(
            adapter_version=ENGINE_VERSION,
            adapter_source=source,
            provider_category=CATEGORY_VIDEO,
            clip_count=len(prompts),
            target_clip_count=target or len(prompts),
            provider_hint=provider_key,
            prompts=prompts,
            clip_metadata=clip_metadata,
            metadata=metadata,
        )

    @staticmethod
    def _composed_clip_index(run_context: dict[str, Any]) -> dict[int, dict[str, Any]]:
        clips = run_context.get("runway_composed_clips")
        if not isinstance(clips, list):
            return {}
        indexed: dict[int, dict[str, Any]] = {}
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            clip_index = int(clip.get("clip_index") or 0)
            if clip_index:
                indexed[clip_index] = clip
        return indexed

    @staticmethod
    def _truncate_runway_with_priority(text: str, max_chars: int = RUNWAY_MAX_PROMPT_CHARS) -> str:
        """Drop lower-priority trailing sections before continuity tail."""
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= max_chars:
            return normalized

        sentences = [part.strip() for part in normalized.split(". ") if part.strip()]
        if not sentences:
            return normalized[:max_chars].rsplit(" ", 1)[0].strip()

        continuity = ""
        if sentences:
            last = sentences[-1]
            if any(
                marker in last.lower()
                for marker in ("continuity", "clip 2 opens", "opens with", "sets up", "follows")
            ):
                continuity = last
                sentences = sentences[:-1]

        drop_keywords = (
            "hero frame",
            "payoff object",
            "thumbnail",
            "palette",
            "composition note",
            "topic-specific object",
            "evidence detail macro",
        )
        while sentences and len(". ".join(sentences) + (f". {continuity}" if continuity else "")) > max_chars:
            drop_index = -1
            for index in range(len(sentences) - 1, -1, -1):
                lowered = sentences[index].lower()
                if any(keyword in lowered for keyword in drop_keywords):
                    drop_index = index
                    break
            if drop_index >= 0:
                sentences.pop(drop_index)
            else:
                sentences.pop()

        rebuilt = ". ".join(sentences)
        if continuity:
            rebuilt = f"{rebuilt}. {continuity}" if rebuilt else continuity
        if len(rebuilt) <= max_chars:
            return rebuilt.strip()
        return rebuilt[:max_chars].rsplit(" ", 1)[0].strip()

    def _resolve_shots(self, brief: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        run_context = _dict(brief.get("run_context"))
        story_intelligence = _dict(run_context.get("story_intelligence"))
        schema_shots = story_intelligence.get("schema_director_shots")
        if isinstance(schema_shots, list) and schema_shots:
            return [s for s in schema_shots if isinstance(s, dict)], "schema_director_shots"

        blueprint = _dict(story_intelligence.get("story_blueprint"))
        director_shots = blueprint.get("director_shots")
        if isinstance(director_shots, list) and director_shots:
            normalized = []
            for index, shot in enumerate(director_shots, start=1):
                if not isinstance(shot, dict):
                    continue
                normalized.append(
                    {
                        "clip_number": shot.get("clip_number", index),
                        "duration_seconds": shot.get("duration_seconds"),
                        "prompt": shot.get("prompt_intent") or shot.get("prompt") or "",
                        "camera_shot": shot.get("camera") or shot.get("camera_shot") or "",
                        "camera_movement": shot.get("camera_movement") or "",
                        "lighting": shot.get("lighting") or "",
                        "pacing": shot.get("mood") or shot.get("pacing") or "",
                        "continuity_notes": shot.get("continuity_notes") or "",
                        "shot_id": shot.get("shot_id"),
                    }
                )
            if normalized:
                return normalized, "story_intelligence.director_shots"

        story_blueprint = _dict(brief.get("story_blueprint"))
        beats = story_blueprint.get("beats")
        if isinstance(beats, list) and beats:
            fallback = []
            for index, beat in enumerate(beats, start=1):
                if not isinstance(beat, dict):
                    continue
                description = str(beat.get("description") or beat.get("beat_id") or "")
                if not description.strip():
                    continue
                fallback.append(
                    {
                        "clip_number": index,
                        "duration_seconds": None,
                        "prompt": description,
                        "camera_shot": "",
                        "camera_movement": "",
                        "lighting": "",
                        "pacing": str(beat.get("emotional_tone") or ""),
                        "continuity_notes": "",
                        "beat_id": beat.get("beat_id"),
                    }
                )
            if fallback:
                return fallback, "story_blueprint.beats_fallback"

        return [], "none"

    def _compose_prompt(
        self,
        shot: dict[str, Any],
        source: str,
        provider: str,
        *,
        truncate: bool = True,
    ) -> str:
        base_prompt = str(shot.get("prompt") or "").strip()
        has_camera = "camera:" in base_prompt.lower()

        if source == "story_intelligence.director_shots":
            parts = [base_prompt]
            if not has_camera:
                parts.extend(
                    [
                        f"Camera: {shot.get('camera_shot') or '—'}.",
                        f"Subject: {shot.get('subject') or '—'}.",
                        f"Action: {shot.get('action') or '—'}.",
                        f"Mood: {shot.get('pacing') or '—'}.",
                        f"Environment: {shot.get('environment') or '—'}.",
                    ]
                )
            if shot.get("continuity_notes") and "continuity:" not in base_prompt.lower():
                parts.append(f"Continuity: {shot['continuity_notes']}.")
            text = " ".join(part for part in parts if part and part != "—.")
        else:
            parts = [base_prompt]
            if not has_camera:
                parts.extend(
                    [
                        f"Camera: {shot.get('camera_shot') or '—'}.",
                        f"Movement: {shot.get('camera_movement') or '—'}.",
                        f"Lighting: {shot.get('lighting') or '—'}.",
                        f"Pacing: {shot.get('pacing') or '—'}.",
                    ]
                )
            if shot.get("continuity_notes") and "continuity:" not in base_prompt.lower():
                parts.append(f"Continuity: {shot['continuity_notes']}.")
            text = " ".join(part for part in parts if part and part not in {"—.", "—"})

        text = " ".join(text.split())
        if (
            truncate
            and provider in {"runway", "runway_browser"}
            and len(text) > RUNWAY_MAX_PROMPT_CHARS
        ):
            text = text[:RUNWAY_MAX_PROMPT_CHARS].rsplit(" ", 1)[0].strip()
        return text


__all__ = ["SessionPromptAdapter", "PromptBundle"]
