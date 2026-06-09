"""
Content Brain V8.3 → Runway Live Smoke handoff layer.

Loads cleaned prompts from prompt_cleanup output (not raw prompt_generation).
Priority: in-memory E2E result → latest.runway_prompts.txt → latest.json → fallback builder.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.content_brain_e2e_micro_test_studio import DEFAULT_EXPORT_DIR
from content_brain.execution.runway_prompt_builder import (
    ContinuityAnchors,
    RunwayContinuityPromptBundle,
    build_continuity_prompts,
)

HANDOFF_VERSION = "content_brain_live_smoke_handoff_v1_1"
STARTER_PROMPT_PREVIEW_CHARS = 280
STORY_SUMMARY_MAX_CHARS = 400
PROMPT_SOURCE_CONTENT_BRAIN = "CONTENT_BRAIN_V83"
PROMPT_SOURCE_FALLBACK = "FALLBACK_CONTINUITY_BUILDER"

ROOT = Path(__file__).resolve().parents[2]

_REGISTERED_E2E_RESULT: dict[str, Any] | None = None

_CHAR_COUNT_SUFFIX = r"(?:\n\s*\[[^\]]*chars\])"

_STARTER_SECTION = re.compile(
    rf"=== STARTER IMAGE PROMPT ===\s*\n(.*?)(?:{_CHAR_COUNT_SUFFIX}|(?:\n=== CLIP)|\Z)",
    re.DOTALL,
)
_CLIP_SECTION = re.compile(
    rf"=== CLIP (\d+) VIDEO PROMPT ===\s*\n(.*?)(?:{_CHAR_COUNT_SUFFIX}|(?:\n=== CLIP)|\Z)",
    re.DOTALL,
)
_RUN_ID_LINE = re.compile(r"^Run ID:\s*(.+)$", re.MULTILINE)


def register_e2e_result(result: dict[str, Any] | None) -> None:
    """Register the latest Content Brain E2E run for Live Smoke priority-1 loading."""
    global _REGISTERED_E2E_RESULT
    _REGISTERED_E2E_RESULT = dict(result) if isinstance(result, dict) else None


def get_registered_e2e_result() -> dict[str, Any] | None:
    if _REGISTERED_E2E_RESULT is None:
        return None
    return dict(_REGISTERED_E2E_RESULT)


def clear_registered_e2e_result() -> None:
    global _REGISTERED_E2E_RESULT
    _REGISTERED_E2E_RESULT = None


@dataclass
class LiveSmokeHandoffMeta:
    prompt_source: str = PROMPT_SOURCE_FALLBACK
    content_brain_run_id: str = ""
    prompt_cleanup_used: bool = False
    prompt_noise_score: float = 0.0
    prompt_efficiency_score: float = 0.0
    loaded_from: str = "fallback_continuity_builder"
    topic_label: str = ""
    content_brain_topic: str = ""
    seo_title: str = ""
    story_summary: str = ""
    starter_prompt_preview: str = ""
    handoff_version: str = HANDOFF_VERSION
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_source": self.prompt_source,
            "content_brain_run_id": self.content_brain_run_id,
            "prompt_cleanup_used": self.prompt_cleanup_used,
            "prompt_noise_score": self.prompt_noise_score,
            "prompt_efficiency_score": self.prompt_efficiency_score,
            "loaded_from": self.loaded_from,
            "topic_label": self.topic_label,
            "content_brain_topic": self.content_brain_topic,
            "seo_title": self.seo_title,
            "story_summary": self.story_summary,
            "starter_prompt_preview": self.starter_prompt_preview,
            "handoff_version": self.handoff_version,
            "warnings": list(self.warnings),
        }


@dataclass
class _CleanedPromptPayload:
    starter_image_prompt: str
    clip_prompts: list[str]
    run_id: str
    prompt_cleanup_used: bool
    prompt_noise_score: float
    prompt_efficiency_score: float
    topic_label: str
    content_brain_topic: str
    seo_title: str
    story_summary: str
    starter_prompt_preview: str
    continuity_anchors: dict[str, str]
    loaded_from: str
    warnings: list[str] = field(default_factory=list)


def _unwrap_e2e_result(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    nested = payload.get("result")
    if isinstance(nested, dict) and nested.get("steps") is not None:
        return nested
    if payload.get("steps") is not None:
        return payload
    return None


def _step_payload(result: dict[str, Any], step_key: str) -> dict[str, Any]:
    step = next(
        (item for item in result.get("steps") or [] if isinstance(item, dict) and item.get("step_key") == step_key),
        None,
    )
    if not isinstance(step, dict):
        return {}
    return dict(step.get("payload") or {})


def _truncate_preview(text: str, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _extract_topic_label_from_result(result: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
    concept = _step_payload(result, "concept_distribution")
    topic_label_value = concept.get("topic_label")
    if isinstance(topic_label_value, dict):
        label = str(topic_label_value.get("topic_label") or topic_label_value.get("label") or "").strip()
        if label:
            return label
    elif isinstance(topic_label_value, str) and topic_label_value.strip():
        return topic_label_value.strip()

    audit = dict(result.get("quality_audit") or {})
    label = str(audit.get("topic_label") or "").strip()
    if label:
        return label

    if payload:
        label = str(payload.get("topic_label") or "").strip()
        if label and label != str(payload.get("topic") or "").strip():
            return label

    export_meta = dict(result.get("export") or {})
    label = str(export_meta.get("topic_label") or "").strip()
    if label:
        return label

    return str((result.get("input") or {}).get("topic") or "").strip()


def _extract_e2e_story_context(result: dict[str, Any]) -> dict[str, str]:
    content_brain_topic = str((result.get("input") or {}).get("topic") or "").strip()
    topic_label = _extract_topic_label_from_result(result)

    seo_payload = _step_payload(result, "seo_title")
    seo_title = str(
        seo_payload.get("seo_title")
        or seo_payload.get("selected_seo_title")
        or ""
    ).strip()

    story_payload = _step_payload(result, "story_generation")
    story = dict(story_payload.get("story") or {})
    if not seo_title:
        seo_title = str(story.get("title") or "").strip()

    logline = str(story.get("logline") or "").strip()
    clip_beats = [str(item).strip() for item in (story.get("clip_beats") or []) if str(item).strip()]
    if logline:
        story_summary = _truncate_preview(logline, STORY_SUMMARY_MAX_CHARS)
    elif clip_beats:
        story_summary = _truncate_preview(" · ".join(clip_beats[:3]), STORY_SUMMARY_MAX_CHARS)
    else:
        story_summary = _truncate_preview(
            str(story.get("title") or topic_label or content_brain_topic),
            STORY_SUMMARY_MAX_CHARS,
        )

    return {
        "content_brain_topic": content_brain_topic,
        "topic_label": topic_label,
        "seo_title": seo_title,
        "story_summary": story_summary,
    }


def _starter_prompt_preview(starter_image_prompt: str) -> str:
    return _truncate_preview(starter_image_prompt, STARTER_PROMPT_PREVIEW_CHARS)


def _find_prompt_cleanup_step(steps: list[Any]) -> dict[str, Any] | None:
    cleanup = next((step for step in steps if isinstance(step, dict) and step.get("step_key") == "prompt_cleanup"), None)
    if cleanup:
        return dict(cleanup.get("payload") or {})
    generation = next(
        (step for step in steps if isinstance(step, dict) and step.get("step_key") == "prompt_generation"),
        None,
    )
    if generation:
        return dict(generation.get("payload") or {})
    return None


def _extract_topic_label(result: dict[str, Any], payload: dict[str, Any]) -> str:
    label = _extract_topic_label_from_result(result, payload)
    if label:
        return label
    return str(payload.get("topic") or (result.get("input") or {}).get("topic") or "").strip()


def _metrics_from_result(result: dict[str, Any], payload: dict[str, Any]) -> tuple[float, float]:
    noise = payload.get("prompt_noise_score")
    efficiency = payload.get("prompt_efficiency_score")
    audit = dict(result.get("quality_audit") or {})
    if noise is None:
        noise = audit.get("prompt_noise_score")
    if efficiency is None:
        efficiency = audit.get("prompt_efficiency_score")
    return float(noise or 0.0), float(efficiency or 0.0)


def _clip_prompt_strings(payload: dict[str, Any]) -> list[str]:
    clips = payload.get("clip_prompts") or []
    ordered: list[tuple[int, str]] = []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        index = int(clip.get("clip_index") or 0)
        prompt = str(clip.get("video_prompt") or "").strip()
        if prompt:
            ordered.append((index, prompt))
    ordered.sort(key=lambda item: item[0])
    return [prompt for _, prompt in ordered]


def _payload_from_e2e_result(result: dict[str, Any], *, loaded_from: str) -> _CleanedPromptPayload | None:
    steps = list(result.get("steps") or [])
    payload = _find_prompt_cleanup_step(steps)
    if not payload:
        return None
    starter = str(payload.get("starter_image_prompt") or "").strip()
    clip_prompts = _clip_prompt_strings(payload)
    if not starter or not clip_prompts:
        return None
    noise, efficiency = _metrics_from_result(result, payload)
    anchors = dict(payload.get("continuity_anchors") or {})
    context = _extract_e2e_story_context(result)
    warnings: list[str] = []
    if payload.get("step_key") != "prompt_cleanup" and loaded_from.endswith("json"):
        warnings.append("prompt_cleanup step missing; used prompt_generation payload")
    return _CleanedPromptPayload(
        starter_image_prompt=starter,
        clip_prompts=clip_prompts,
        run_id=str(result.get("run_id") or "").strip(),
        prompt_cleanup_used=bool(payload.get("cleanup_applied", loaded_from != "prompt_generation")),
        prompt_noise_score=noise,
        prompt_efficiency_score=efficiency,
        topic_label=context["topic_label"] or _extract_topic_label(result, payload),
        content_brain_topic=context["content_brain_topic"],
        seo_title=context["seo_title"],
        story_summary=context["story_summary"],
        starter_prompt_preview=_starter_prompt_preview(starter),
        continuity_anchors=anchors,
        loaded_from=loaded_from,
        warnings=warnings,
    )


def _load_from_e2e_candidates(
    *,
    e2e_result: dict[str, Any] | None,
    story_idea: str,
) -> _CleanedPromptPayload | None:
    candidates: list[tuple[str, dict[str, Any] | None]] = [
        ("e2e_result", _unwrap_e2e_result(e2e_result)),
        ("registered_e2e_result", get_registered_e2e_result()),
    ]
    normalized_story = _normalize_topic(story_idea)
    for source_name, candidate in candidates:
        if not candidate:
            continue
        loaded = _payload_from_e2e_result(candidate, loaded_from=source_name)
        if loaded is None:
            continue
        topic = _normalize_topic(loaded.topic_label or str((candidate.get("input") or {}).get("topic") or ""))
        if normalized_story and topic and normalized_story != topic:
            loaded.warnings.append(f"story_idea differs from E2E topic ({source_name})")
        return loaded
    return None


def _load_from_runway_prompts_txt(path: Path, *, metrics_result: dict[str, Any] | None = None) -> _CleanedPromptPayload | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    starter_match = _STARTER_SECTION.search(text)
    if not starter_match:
        return None
    starter = starter_match.group(1).strip()
    clip_prompts = [body.strip() for _, body in sorted(_CLIP_SECTION.findall(text), key=lambda item: int(item[0]))]
    if not starter or not clip_prompts:
        return None
    run_id = ""
    run_match = _RUN_ID_LINE.search(text)
    if run_match:
        run_id = run_match.group(1).strip()
    noise = 0.0
    efficiency = 0.0
    cleanup_used = True
    anchors: dict[str, str] = {}
    topic_label = ""
    content_brain_topic = ""
    seo_title = ""
    story_summary = ""
    warnings: list[str] = []
    if metrics_result:
        payload = _payload_from_e2e_result(metrics_result, loaded_from="latest_json_for_metrics")
        if payload:
            noise = payload.prompt_noise_score
            efficiency = payload.prompt_efficiency_score
            cleanup_used = payload.prompt_cleanup_used
            anchors = dict(payload.continuity_anchors)
            topic_label = payload.topic_label
            content_brain_topic = payload.content_brain_topic
            seo_title = payload.seo_title
            story_summary = payload.story_summary
            if run_id and payload.run_id and run_id != payload.run_id:
                warnings.append("runway_prompts.txt run_id differs from latest.json")
            if not run_id:
                run_id = payload.run_id
    return _CleanedPromptPayload(
        starter_image_prompt=starter,
        clip_prompts=clip_prompts,
        run_id=run_id,
        prompt_cleanup_used=cleanup_used,
        prompt_noise_score=noise,
        prompt_efficiency_score=efficiency,
        topic_label=topic_label,
        content_brain_topic=content_brain_topic,
        seo_title=seo_title,
        story_summary=story_summary,
        starter_prompt_preview=_starter_prompt_preview(starter),
        continuity_anchors=anchors,
        loaded_from="latest.runway_prompts.txt",
        warnings=warnings,
    )


def _load_from_latest_json(path: Path) -> _CleanedPromptPayload | None:
    if not path.is_file():
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(result, dict):
        return None
    return _payload_from_e2e_result(result, loaded_from="latest.json")


def _normalize_topic(value: str) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _anchors_from_payload(payload: _CleanedPromptPayload) -> ContinuityAnchors | None:
    raw = payload.continuity_anchors
    if not raw:
        return None
    character = str(raw.get("character") or "").strip()
    location = str(raw.get("location") or "").strip()
    if not character and not location:
        return None
    return ContinuityAnchors(
        character=character or "subject",
        location=location or "primary location",
        lighting=str(raw.get("lighting") or "consistent motivated lighting").strip(),
        camera=str(raw.get("camera") or "stable cinematic framing").strip(),
        palette=str(raw.get("palette") or "consistent palette").strip(),
        wardrobe=str(raw.get("wardrobe") or "").strip(),
    )


def _build_scaffold_bundle(
    *,
    story_idea: str,
    project_id: str,
    clip_count: int,
    niche_style: str,
    mood: str,
) -> RunwayContinuityPromptBundle:
    return build_continuity_prompts(
        story_idea,
        project_id=project_id,
        clip_count=clip_count,
        niche_style=niche_style,
        mood=mood,
    )


def _bundle_from_cleaned_payload(
    payload: _CleanedPromptPayload,
    *,
    story_idea: str,
    project_id: str,
    clip_count: int,
    niche_style: str,
    mood: str,
) -> RunwayContinuityPromptBundle:
    effective_story = str(payload.content_brain_topic or story_idea or "").strip()
    scaffold = _build_scaffold_bundle(
        story_idea=effective_story,
        project_id=project_id,
        clip_count=clip_count,
        niche_style=niche_style,
        mood=mood,
    )
    anchors = _anchors_from_payload(payload) or scaffold.continuity_anchors
    clip_prompts = list(payload.clip_prompts[:clip_count])
    while len(clip_prompts) < clip_count:
        index = len(clip_prompts)
        if index < len(scaffold.clip_prompts):
            clip_prompts.append(scaffold.clip_prompts[index])
        else:
            break
    warnings = list(scaffold.warnings)
    warnings.extend(payload.warnings)
    if len(payload.clip_prompts) < clip_count:
        warnings.append(f"handoff provided {len(payload.clip_prompts)} clips; padded to {clip_count}")
    return RunwayContinuityPromptBundle(
        project_id=project_id,
        story_idea=effective_story,
        clip_count=clip_count,
        starter_image_prompt=payload.starter_image_prompt,
        clip_prompts=clip_prompts,
        continuity_anchors=anchors,
        warnings=warnings,
        char_stats={
            "starter_image_prompt_chars": len(payload.starter_image_prompt),
            "clip_prompt_chars": [len(item) for item in clip_prompts],
            "source": payload.loaded_from,
        },
        builder_version=f"{HANDOFF_VERSION}+{scaffold.builder_version}",
        story_brief=scaffold.story_brief,
    )


def preview_live_smoke_handoff(
    *,
    story_idea: str = "",
    clip_count: int = 3,
    e2e_result: dict[str, Any] | None = None,
    export_dir: Path | str | None = None,
    project_root: Path | str | None = None,
) -> LiveSmokeHandoffMeta:
    """Resolve handoff metadata without building the full prompt bundle."""
    _, meta = resolve_live_smoke_prompts(
        story_idea=story_idea,
        project_id="preview",
        clip_count=clip_count,
        e2e_result=e2e_result,
        export_dir=export_dir,
        project_root=project_root,
    )
    return meta


def resolve_live_smoke_prompts(
    *,
    story_idea: str,
    project_id: str,
    clip_count: int = 3,
    e2e_result: dict[str, Any] | None = None,
    export_dir: Path | str | None = None,
    project_root: Path | str | None = None,
    niche_style: str | None = None,
    mood: str | None = None,
) -> tuple[RunwayContinuityPromptBundle, LiveSmokeHandoffMeta]:
    """
    Resolve Live Smoke prompts with Content Brain V8.3 handoff priority.

    Returns (prompt_bundle, handoff_meta).
    """
    root = Path(project_root) if project_root else ROOT
    if export_dir:
        export_path = Path(export_dir)
    elif project_root:
        export_path = root / "project_brain" / "content_brain_test_results"
    else:
        export_path = DEFAULT_EXPORT_DIR
    resolved_niche = niche_style or ("cyberpunk" if clip_count > 1 else "cinematic")
    resolved_mood = mood or "tense hopeful"
    clip_total = max(1, int(clip_count))

    cleaned: _CleanedPromptPayload | None = _load_from_e2e_candidates(
        e2e_result=e2e_result,
        story_idea=story_idea,
    )
    latest_json_path = export_path / "latest.json"
    latest_txt_path = export_path / "latest.runway_prompts.txt"
    metrics_result: dict[str, Any] | None = None
    if latest_json_path.is_file():
        try:
            metrics_result = json.loads(latest_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metrics_result = None

    if cleaned is None and latest_txt_path.is_file():
        cleaned = _load_from_runway_prompts_txt(latest_txt_path, metrics_result=metrics_result)

    if cleaned is None:
        cleaned = _load_from_latest_json(latest_json_path)

    if cleaned is not None:
        bundle = _bundle_from_cleaned_payload(
            cleaned,
            story_idea=story_idea,
            project_id=project_id,
            clip_count=clip_total,
            niche_style=resolved_niche,
            mood=resolved_mood,
        )
        meta = LiveSmokeHandoffMeta(
            prompt_source=PROMPT_SOURCE_CONTENT_BRAIN,
            content_brain_run_id=cleaned.run_id,
            prompt_cleanup_used=cleaned.prompt_cleanup_used,
            prompt_noise_score=cleaned.prompt_noise_score,
            prompt_efficiency_score=cleaned.prompt_efficiency_score,
            loaded_from=cleaned.loaded_from,
            topic_label=cleaned.topic_label,
            content_brain_topic=cleaned.content_brain_topic,
            seo_title=cleaned.seo_title,
            story_summary=cleaned.story_summary,
            starter_prompt_preview=cleaned.starter_prompt_preview,
            warnings=list(cleaned.warnings),
        )
        return bundle, meta

    bundle = _build_scaffold_bundle(
        story_idea=story_idea,
        project_id=project_id,
        clip_count=clip_total,
        niche_style=resolved_niche,
        mood=resolved_mood,
    )
    meta = LiveSmokeHandoffMeta(
        prompt_source=PROMPT_SOURCE_FALLBACK,
        loaded_from="fallback_continuity_builder",
        warnings=["Content Brain handoff unavailable; using build_continuity_prompts()"],
    )
    return bundle, meta


__all__ = [
    "HANDOFF_VERSION",
    "LiveSmokeHandoffMeta",
    "PROMPT_SOURCE_CONTENT_BRAIN",
    "PROMPT_SOURCE_FALLBACK",
    "clear_registered_e2e_result",
    "get_registered_e2e_result",
    "preview_live_smoke_handoff",
    "register_e2e_result",
    "resolve_live_smoke_prompts",
]
