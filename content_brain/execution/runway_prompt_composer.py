"""
Phase 12J-C — RunwayPromptComposer: merge Content Brain visual fields into clip prompts.

Design lock: project_brain/PHASE_12J_C_RUNWAY_PROMPT_COMPOSER_DESIGN_LOCK.md
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from content_brain.engines.story_intelligence_engine import NICHE_VISUAL_LEXICON

ENGINE_NAME = "RunwayPromptComposer"
COMPOSER_VERSION = "12j_c_v1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
MERGE_PASS = "prose_v1"

PRECEDENCE_ORDER = [
    "retention",
    "architecture",
    "director_shots",
    "thumbnail",
    "lexicon_fallback",
]

PRIMARY_BEATS_BY_CLIP_COUNT: dict[int, list[dict[str, list[str]]]] = {
    1: [{"primary": "HOOK_BEAT", "folded": ["CONTEXT_BEAT", "ESCALATION_BEAT", "PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"]}],
    2: [
        {"primary": "HOOK_BEAT", "folded": ["CONTEXT_BEAT"]},
        {"primary": "ESCALATION_BEAT", "folded": ["PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"]},
    ],
    3: [
        {"primary": "HOOK_BEAT", "folded": ["CONTEXT_BEAT"]},
        {"primary": "ESCALATION_BEAT", "folded": ["PATTERN_BREAK"]},
        {"primary": "PAYOFF_BEAT", "folded": ["LOOP_SEED"]},
    ],
}

FOLDED_PAYOFF_BEATS = frozenset({"PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"})

GENERIC_PATTERNS = [
    re.compile(r"topic-specific object in sharp focus", re.I),
    re.compile(r"evidence detail macro shot", re.I),
    re.compile(r"generic stock footage", re.I),
    re.compile(r"evidence element", re.I),
    re.compile(r"\{topic\}", re.I),
]

STOCK_PHRASES = (
    "generic stock footage",
    "not generic stock",
    "specific to",
)

CLIP_NOTE_RE = re.compile(r"CLIP:\s*(\d+)\s*\[([0-9.]+)-([0-9.]+)\]", re.I)
STORY_BEAT_RE = re.compile(r"STORY:\s*([A-Z_]+)", re.I)

VISUAL_DIMENSION_KEYWORDS = {
    "subject": ("subject", "focal", "portrait", "close-up", "macro"),
    "action": ("action", "reveal", "motion", "contrast", "enters", "shift"),
    "environment": ("environment", "setting", "background", "location"),
    "camera": ("camera", "shot", "push-in", "macro", "angle", "frame"),
    "lighting": ("lighting", "light", "shadow", "contrast", "motivated"),
    "motion": ("motion", "movement", "push", "rack", "pan"),
    "mood": ("mood", "tension", "curiosity", "surprise", "tone"),
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _parse_pipe_segments(note: str) -> dict[str, str]:
    segments: dict[str, str] = {}
    for part in str(note or "").split("|"):
        piece = part.strip()
        if ":" not in piece:
            continue
        key, value = piece.split(":", 1)
        segments[key.strip().upper()] = value.strip()
    return segments


def _parse_description_visual(description: str) -> str:
    for segment in str(description or "").split("|"):
        piece = segment.strip()
        if piece.upper().startswith("VISUAL:"):
            return piece.split(":", 1)[1].strip()
    return ""


def _clip_index_from_retention(segments: dict[str, str], clip_duration: float) -> int:
    clip_tag = segments.get("CLIP", "")
    match = CLIP_NOTE_RE.search(clip_tag)
    if match:
        return int(match.group(1)) + 1
    try:
        start = float(segments.get("START", "0") or 0)
    except ValueError:
        start = 0.0
    if clip_duration <= 0:
        clip_duration = 10.0
    return int(start // clip_duration) + 1


def _topic_from_brief(brief: dict[str, Any]) -> str:
    run_context = _dict(brief.get("run_context"))
    topic = _normalize_text(run_context.get("topic") or run_context.get("user_topic") or "")
    if topic:
        return topic
    trend = _dict(brief.get("trend_signal"))
    return _normalize_text(trend.get("topic") or "")


def _niche_from_brief(brief: dict[str, Any]) -> str:
    profile = _dict(brief.get("profile"))
    run_context = _dict(brief.get("run_context"))
    return _normalize_text(profile.get("niche") or run_context.get("niche") or "general") or "general"


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    stop = {"the", "and", "for", "that", "this", "with", "from", "why", "how", "what", "not", "are"}
    return [t for t in cleaned.split() if len(t) >= 3 and t not in stop]


def _is_generic(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return True
    for pattern in GENERIC_PATTERNS:
        if pattern.search(normalized):
            return True
    tokens = _tokenize(normalized)
    if len(tokens) < 2:
        return True
    if not any(len(t) >= 4 for t in tokens[:8]):
        return True
    return False


def _concrete_subject(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized or _is_generic(normalized):
        return False
    tokens = _tokenize(normalized)
    return len(tokens) >= 2


def _specificity_heuristic(text: str, topic: str) -> float:
    normalized = _normalize_text(text)
    if not normalized:
        return 0.0
    topic_tokens = _tokenize(topic)
    words = _tokenize(normalized)
    overlap = sum(1 for t in topic_tokens if t in words)
    length_bonus = min(0.3, len(words) / 40.0)
    return min(1.0, 0.2 + overlap * 0.15 + length_bonus)


def _compress(text: str, max_chars: int = 120) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rsplit(" ", 1)[0] + "..."


def _augment(base: str, overlay: str) -> str:
    base_n = _normalize_text(base)
    overlay_n = _normalize_text(overlay)
    if not overlay_n:
        return base_n
    if not base_n:
        return overlay_n
    if _is_generic(base_n) and not _is_generic(overlay_n):
        return overlay_n
    if _concrete_subject(overlay_n) and not _concrete_subject(base_n):
        return f"{overlay_n}. {base_n}"
    if len(overlay_n) > len(base_n) * 1.5 and _specificity_heuristic(overlay_n, "") > _specificity_heuristic(base_n, ""):
        return f"{overlay_n}. {_compress(base_n)}"
    return f"{base_n}. {overlay_n}"


def _merge_layers(layers: list[str]) -> str:
    body = ""
    for layer in layers:
        layer_n = _normalize_text(layer)
        if not layer_n:
            continue
        body = layer_n if not body else _augment(body, layer_n)
    return body


def _merge_prose_v1(
    *,
    clip_index: int,
    retention_visual: str,
    architecture_visual: str,
    director_visual: str,
    thumbnail_visual: str,
    lexicon_visual: str,
    hook_visual_seed: str,
    payoff_compressed: str,
    continuity_tail: str,
    lineage: dict[str, Any],
) -> str:
    sections: list[str] = []
    if clip_index == 1 and hook_visual_seed:
        sections.append(hook_visual_seed)

    if payoff_compressed:
        sections.append(payoff_compressed)

    body = _merge_layers([retention_visual, architecture_visual, director_visual, thumbnail_visual])
    if not body and lexicon_visual:
        body = lexicon_visual
        lineage["lexicon_fallback_used"] = True

    if not body:
        raise ValueError(f"COMPOSER_EMPTY_PROMPT: clip_index={clip_index}")

    if clip_index == 1 and hook_visual_seed:
        sections.append(body)
    else:
        sections.insert(0, body)

    if continuity_tail:
        sections.append(continuity_tail)

    return ". ".join(_normalize_text(part) for part in sections if part)


def _shannon_entropy(text: str) -> float:
    letters = [c.lower() for c in text if c.isalpha()]
    if not letters:
        return 0.0
    counts = Counter(letters)
    total = len(letters)
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy


def _quality_score(prompt: str, topic: str, hook_seed: str, sensory_anchor: str | None) -> dict[str, Any]:
    genericity = 0.0
    for pattern in GENERIC_PATTERNS:
        if pattern.search(prompt):
            genericity += 0.4
    if "topic" in prompt.lower().split() and topic.lower() not in prompt.lower():
        genericity += 0.15
    for phrase in STOCK_PHRASES:
        if phrase in prompt.lower():
            genericity += 0.1
    genericity = min(1.0, genericity)

    topic_present = 0.35 if topic and topic.lower() in prompt.lower() else 0.0
    nouns = min(0.25, len(_tokenize(prompt)) / 16.0)
    hook_overlap = 0.2 if hook_seed and any(t in prompt.lower() for t in _tokenize(hook_seed)[:4]) else 0.0
    anchor_overlap = (
        0.2
        if sensory_anchor and _normalize_text(sensory_anchor).lower() in prompt.lower()
        else 0.0
    )
    specificity_score = min(1.0, topic_present + nouns + hook_overlap + anchor_overlap)

    lowered = prompt.lower()
    dimensions = sum(
        1
        for keywords in VISUAL_DIMENSION_KEYWORDS.values()
        if any(keyword in lowered for keyword in keywords)
    )
    visual_richness_score = min(1.0, dimensions / 7.0)

    entropy = _shannon_entropy(prompt)
    prompt_entropy_score = min(1.0, entropy / 4.5)

    composite_score = min(
        1.0,
        0.30 * specificity_score
        + 0.30 * visual_richness_score
        + 0.25 * prompt_entropy_score
        + 0.15 * (1.0 - genericity),
    )

    failure_reasons: list[str] = []
    if genericity > 0.35:
        failure_reasons.append("HIGH_GENERICITY")
    if specificity_score < 0.55:
        failure_reasons.append("LOW_SPECIFICITY")
    if visual_richness_score < 0.50:
        failure_reasons.append("LOW_VISUAL_RICHNESS")
    if prompt_entropy_score < 0.40:
        failure_reasons.append("LOW_ENTROPY")

    audit_flags: list[str] = []
    if genericity > 0.35:
        audit_flags.append("HIGH_GENERICITY")
    if prompt_entropy_score < 0.35:
        audit_flags.append("LOW_ENTROPY")
    if genericity > 0.35 and specificity_score < 0.4:
        audit_flags.append("LEXICON_ONLY")

    return {
        "genericity_score": round(genericity, 4),
        "specificity_score": round(specificity_score, 4),
        "visual_richness_score": round(visual_richness_score, 4),
        "prompt_entropy_score": round(prompt_entropy_score, 4),
        "composite_score": round(composite_score, 4),
        "pass": not failure_reasons,
        "failure_reasons": failure_reasons,
        "audit_flags": audit_flags,
    }


def _lexicon_fallback(niche: str, beat_id: str, topic: str) -> str:
    phrases = list(NICHE_VISUAL_LEXICON.get(niche, NICHE_VISUAL_LEXICON["general"]))
    if not phrases:
        return ""
    index = abs(hash(beat_id)) % len(phrases)
    phrase = phrases[index]
    topic_token = _tokenize(topic)[0] if _tokenize(topic) else "subject"
    return f"{phrase} featuring {topic_token} during {beat_id.lower().replace('_beat', '')}."


def _beat_visual_from_blueprint(beats_by_id: dict[str, dict[str, Any]], beat_id: str) -> str:
    beat = beats_by_id.get(beat_id) or {}
    return _parse_description_visual(str(beat.get("description") or ""))


def _collapse_map(clip_count: int) -> list[dict[str, list[str]]]:
    if clip_count in PRIMARY_BEATS_BY_CLIP_COUNT:
        return PRIMARY_BEATS_BY_CLIP_COUNT[clip_count]
    if clip_count <= 0:
        return []
    mapping: list[dict[str, list[str]]] = []
    for index in range(clip_count):
        if index == 0:
            mapping.append({"primary": "HOOK_BEAT", "folded": ["CONTEXT_BEAT"]})
        elif index == clip_count - 1:
            mapping.append({"primary": "ESCALATION_BEAT", "folded": ["PATTERN_BREAK", "PAYOFF_BEAT", "LOOP_SEED"]})
        else:
            mapping.append({"primary": "ESCALATION_BEAT", "folded": ["PATTERN_BREAK"]})
    return mapping


class RunwayPromptComposer:
    """Compose clip-aligned Runway prompts from brief_snapshot fields."""

    def compose(self, brief: dict[str, Any]) -> dict[str, Any]:
        brief = _dict(brief)
        format_plan = _dict(brief.get("video_format_plan"))
        clip_count = int(format_plan.get("clip_count") or 0)
        if clip_count <= 0:
            raise ValueError("COMPOSER_CLIP_COUNT_MISMATCH: video_format_plan.clip_count missing.")

        clip_duration = float(format_plan.get("clip_duration_seconds") or 10.0)
        topic = _topic_from_brief(brief)
        niche = _niche_from_brief(brief)

        story_blueprint = _dict(brief.get("story_blueprint"))
        beats = story_blueprint.get("beats") if isinstance(story_blueprint.get("beats"), list) else []
        beats_by_id = {str(b.get("beat_id")): b for b in beats if isinstance(b, dict) and b.get("beat_id")}

        run_context = _dict(brief.get("run_context"))
        story_intelligence = _dict(run_context.get("story_intelligence"))
        schema_shots = story_intelligence.get("schema_director_shots")
        if not isinstance(schema_shots, list) or not schema_shots:
            raise ValueError("COMPOSER_FAILED: schema_director_shots missing.")

        shots_by_clip = {
            int(_dict(s).get("clip_number") or index): _dict(s)
            for index, s in enumerate(schema_shots, start=1)
            if isinstance(s, dict)
        }

        hook_package = _dict(brief.get("hook_package"))
        hook_text = _normalize_text(hook_package.get("best_hook_text") or "")
        hook_class = hook_package.get("hook_class")

        retention_map = _dict(brief.get("retention_map"))
        retention_beats = retention_map.get("beats") if isinstance(retention_map.get("beats"), list) else []

        title_pkg = _dict(brief.get("title_thumbnail_package"))
        recommended_thumb = _dict(title_pkg.get("recommended_thumbnail_concept"))
        thumb_concepts = title_pkg.get("thumbnail_concepts") if isinstance(title_pkg.get("thumbnail_concepts"), list) else []

        emotional_curve = story_blueprint.get("emotional_curve")
        if not isinstance(emotional_curve, list):
            emotional_curve = []

        sensory_anchor = _normalize_text(story_blueprint.get("sensory_anchor") or "") or None

        retention_by_clip: dict[int, list[dict[str, Any]]] = {index: [] for index in range(1, clip_count + 1)}
        for beat_index, block in enumerate(retention_beats):
            if not isinstance(block, dict):
                continue
            segments = _parse_pipe_segments(str(block.get("implementation_note") or ""))
            visual = segments.get("VISUAL", "")
            if not visual:
                continue
            clip_index = _clip_index_from_retention(segments, clip_duration)
            if clip_index < 1 or clip_index > clip_count:
                continue
            story_match = STORY_BEAT_RE.search(str(block.get("implementation_note") or ""))
            story_beat_id = story_match.group(1) if story_match else ""
            retention_by_clip[clip_index].append(
                {
                    "block_label": str(block.get("block_label") or ""),
                    "story_beat_id": story_beat_id,
                    "visual_clause": visual,
                    "clip_tag": segments.get("CLIP", ""),
                    "intensity": float(segments.get("INTENSITY") or 0.0) if segments.get("INTENSITY") else 0.0,
                    "source_path": f"retention_map.beats[{beat_index}].implementation_note",
                }
            )

        collapse = _collapse_map(clip_count)
        if len(collapse) != clip_count:
            raise ValueError("COMPOSER_CLIP_COUNT_MISMATCH: collapse map does not match clip_count.")

        composed_clips: list[dict[str, Any]] = []

        for clip_index, collapse_entry in enumerate(collapse, start=1):
            primary_beat = collapse_entry["primary"]
            folded_beats = list(collapse_entry.get("folded") or [])
            shot = shots_by_clip.get(clip_index) or {}

            retention_blocks = retention_by_clip.get(clip_index, [])
            retention_visuals = [b["visual_clause"] for b in retention_blocks if b.get("visual_clause")]
            retention_primary = _merge_layers(retention_visuals)

            arch_hints: list[dict[str, Any]] = []
            arch_visuals: list[str] = []
            for beat_id in [primary_beat, *folded_beats]:
                visual_line = _beat_visual_from_blueprint(beats_by_id, beat_id)
                if visual_line:
                    arch_visuals.append(visual_line)
                    arch_hints.append(
                        {
                            "beat_id": beat_id,
                            "visual_prompt_hint": visual_line,
                            "description_visual_line": visual_line,
                            "source_path": f"story_blueprint.beats[{beat_id}]",
                        }
                    )
            architecture_primary = _merge_layers(arch_visuals)

            director_visual = _normalize_text(shot.get("prompt") or "")

            thumb_payload: dict[str, Any]
            if clip_index == 1:
                thumb_payload = {
                    "applies": True,
                    "concept_id": recommended_thumb.get("concept_id"),
                    "focal_subject": _normalize_text(recommended_thumb.get("focal_subject") or ""),
                    "visual_prompt": _normalize_text(recommended_thumb.get("visual_prompt") or ""),
                    "tension_element": _normalize_text(recommended_thumb.get("tension_element") or ""),
                    "composition_note": _normalize_text(recommended_thumb.get("composition_note") or ""),
                    "role": "hero_frame",
                    "source_paths": ["title_thumbnail_package.recommended_thumbnail_concept"],
                }
            elif clip_index == clip_count:
                payoff_concept = next(
                    (c for c in thumb_concepts if isinstance(c, dict) and "payoff" in str(c.get("concept_id", "")).lower()),
                    recommended_thumb,
                )
                thumb_payload = {
                    "applies": True,
                    "concept_id": _dict(payoff_concept).get("concept_id"),
                    "focal_subject": _normalize_text(_dict(payoff_concept).get("focal_subject") or ""),
                    "visual_prompt": _normalize_text(_dict(payoff_concept).get("visual_prompt") or ""),
                    "tension_element": _normalize_text(_dict(payoff_concept).get("tension_element") or ""),
                    "composition_note": _normalize_text(_dict(payoff_concept).get("composition_note") or ""),
                    "role": "payoff_object",
                    "source_paths": ["title_thumbnail_package"],
                }
            else:
                thumb_payload = {
                    "applies": False,
                    "concept_id": None,
                    "focal_subject": "",
                    "visual_prompt": "",
                    "tension_element": "",
                    "composition_note": "",
                    "role": "none",
                    "source_paths": [],
                }

            thumbnail_visual = ""
            if thumb_payload.get("applies"):
                thumb_parts = [
                    thumb_payload.get("visual_prompt"),
                    thumb_payload.get("focal_subject"),
                ]
                thumbnail_visual = _merge_layers([p for p in thumb_parts if p])

            payoff_applies = clip_index == clip_count and any(b in FOLDED_PAYOFF_BEATS for b in folded_beats)
            pattern_break_visual = _beat_visual_from_blueprint(beats_by_id, "PATTERN_BREAK")
            payoff_visual = _beat_visual_from_blueprint(beats_by_id, "PAYOFF_BEAT")
            loop_seed_visual = _beat_visual_from_blueprint(beats_by_id, "LOOP_SEED")
            if not pattern_break_visual:
                pattern_break_visual = next(
                    (
                        b["visual_clause"]
                        for b in retention_blocks
                        if "PATTERN" in str(b.get("story_beat_id", ""))
                    ),
                    "",
                )
            if not payoff_visual:
                payoff_visual = next(
                    (b["visual_clause"] for b in retention_blocks if "PAYOFF" in str(b.get("story_beat_id", ""))),
                    "",
                )
            if not loop_seed_visual:
                loop_seed_visual = _beat_visual_from_blueprint(beats_by_id, "LOOP_SEED")

            payoff_parts = [pattern_break_visual, payoff_visual, loop_seed_visual]
            compressed_clause = " then ".join(_normalize_text(p) for p in payoff_parts if p)

            hook_payload = {
                "applies": clip_index == 1,
                "beat_ids": ["HOOK_BEAT"] if clip_index == 1 else [],
                "best_hook_text_excerpt": hook_text[:120],
                "hook_class": hook_class,
                "visual_seed": "",
                "specificity_score": round(_specificity_heuristic(hook_text, topic), 4),
                "source_paths": ["hook_package.best_hook_text"] if clip_index == 1 else [],
            }
            if clip_index == 1 and hook_text:
                anchor = _tokenize(topic)[:1]
                anchor_text = anchor[0] if anchor else "subject"
                hook_payload["visual_seed"] = _compress(
                    f"Open on {anchor_text}: {_compress(hook_text, 80)}",
                    120,
                )

            continuity_in = _normalize_text(shot.get("continuity_notes") or "") if clip_index > 1 else ""
            continuity_out = _normalize_text(shot.get("continuity_notes") or "")
            between_clip = ""
            for block in retention_blocks:
                visual = str(block.get("visual_clause") or "")
                if "clip 2 opens" in visual.lower() or "opens with" in visual.lower():
                    between_clip = visual
                    break
            if not between_clip and clip_index > 1:
                for blocks in retention_by_clip.get(clip_index, []):
                    note_visual = str(blocks.get("visual_clause") or "")
                    if "opens" in note_visual.lower():
                        between_clip = note_visual
                        break

            continuity_payload = {
                "continuity_in": continuity_in,
                "continuity_out": continuity_out,
                "director_notes": continuity_out,
                "retention_clip_notes": [b.get("clip_tag") or "" for b in retention_blocks if b.get("clip_tag")],
                "between_clip_directive": between_clip or None,
                "source_paths": [
                    f"schema_director_shots[{clip_index - 1}].continuity_notes",
                    "retention_map",
                ],
            }

            curve_slice = emotional_curve[: clip_index + 1] if emotional_curve else []
            beat_ids_for_arc = [primary_beat, *folded_beats]
            tones: list[str] = []
            for beat_id in beat_ids_for_arc:
                beat = beats_by_id.get(beat_id) or {}
                tone = str(beat.get("emotional_tone") or "")
                if tone:
                    tones.append(tone.split("(")[0].strip())

            emotional_arc = {
                "clip_index": clip_index,
                "beat_ids": beat_ids_for_arc,
                "intensity_start": float(curve_slice[0]) if curve_slice else 0.0,
                "intensity_peak": float(max(curve_slice)) if curve_slice else 0.0,
                "intensity_end": float(curve_slice[-1]) if curve_slice else 0.0,
                "tones": tones[:4],
                "curve_sample": [float(v) for v in curve_slice[:6]],
                "source_path": "story_blueprint.emotional_curve",
            }

            lineage: dict[str, Any] = {
                "composer_version": COMPOSER_VERSION,
                "clip_index": clip_index,
                "merge_pass": MERGE_PASS,
                "precedence_applied": list(PRECEDENCE_ORDER),
                "beat_collapse": {
                    "primary_beats": [primary_beat],
                    "folded_beats": folded_beats,
                    "clip_count": clip_count,
                },
                "sources_used": [],
                "director_shot_id": shot.get("shot_id"),
                "lexicon_fallback_used": False,
                "truncation_applied_by": "none",
            }

            lexicon_visual = ""
            provisional = _merge_layers([retention_primary, architecture_primary, director_visual, thumbnail_visual])
            if _is_generic(provisional):
                lexicon_visual = _lexicon_fallback(niche, primary_beat, topic)
                lineage["sources_used"].append(
                    {
                        "path": "NICHE_VISUAL_LEXICON",
                        "field": "fallback",
                        "weight": 0.1,
                        "used_in": "composed_prompt",
                    }
                )

            continuity_tail = between_clip or continuity_out
            composed_prompt = _merge_prose_v1(
                clip_index=clip_index,
                retention_visual=retention_primary,
                architecture_visual=architecture_primary,
                director_visual=director_visual,
                thumbnail_visual=thumbnail_visual,
                lexicon_visual=lexicon_visual,
                hook_visual_seed=str(hook_payload.get("visual_seed") or ""),
                payoff_compressed=compressed_clause if payoff_applies else "",
                continuity_tail=continuity_tail,
                lineage=lineage,
            )

            for layer_name, layer_text, used_in in (
                ("retention", retention_primary, "retention_payload.primary_visual"),
                ("architecture", architecture_primary, "architecture_payload.primary_visual"),
                ("director_shots", director_visual, "director_shots.prompt"),
                ("thumbnail", thumbnail_visual, "thumbnail_payload"),
            ):
                if layer_text:
                    lineage["sources_used"].append(
                        {
                            "path": layer_name,
                            "field": "visual",
                            "weight": 1.0 - PRECEDENCE_ORDER.index(layer_name) * 0.1,
                            "used_in": used_in,
                        }
                    )

            quality = _quality_score(
                composed_prompt,
                topic,
                str(hook_payload.get("visual_seed") or ""),
                sensory_anchor,
            )

            window_start = (clip_index - 1) * clip_duration
            window_end = clip_index * clip_duration

            composed_clips.append(
                {
                    "clip_index": clip_index,
                    "hook_payload": hook_payload,
                    "retention_payload": {
                        "clip_window_seconds": [window_start, window_end],
                        "blocks": retention_blocks,
                        "primary_visual": retention_primary,
                    },
                    "architecture_payload": {
                        "primary_beat_id": primary_beat,
                        "secondary_beat_ids": folded_beats,
                        "visual_hints": arch_hints,
                        "sensory_anchor": sensory_anchor,
                        "primary_visual": architecture_primary,
                    },
                    "thumbnail_payload": thumb_payload,
                    "continuity_payload": continuity_payload,
                    "emotional_arc": emotional_arc,
                    "payoff_payload": {
                        "applies": payoff_applies,
                        "folded_beat_ids": [b for b in folded_beats if b in FOLDED_PAYOFF_BEATS],
                        "pattern_break_visual": pattern_break_visual,
                        "payoff_visual": payoff_visual,
                        "loop_seed_visual": loop_seed_visual,
                        "compressed_clause": compressed_clause if payoff_applies else "",
                        "source_paths": [
                            "story_blueprint.beats",
                            "retention_map.beats",
                        ],
                    },
                    "composed_prompt": composed_prompt,
                    "lineage": lineage,
                    "quality_score": quality,
                    "director_format": {
                        "camera_shot": shot.get("camera_shot") or "",
                        "camera_movement": shot.get("camera_movement") or "",
                        "lighting": shot.get("lighting") or "",
                        "pacing": shot.get("pacing") or "",
                        "continuity_notes": continuity_out,
                    },
                }
            )

        updated_shots = []
        for index, shot in enumerate(schema_shots):
            if not isinstance(shot, dict):
                continue
            shot_copy = dict(shot)
            clip_number = int(shot_copy.get("clip_number") or index + 1)
            match = next((c for c in composed_clips if c.get("clip_index") == clip_number), None)
            if match:
                shot_copy["prompt"] = match["composed_prompt"]
                fmt = match.get("director_format") or {}
                for key in ("camera_shot", "camera_movement", "lighting", "pacing", "continuity_notes"):
                    if fmt.get(key):
                        shot_copy[key] = fmt[key]
                shot_copy["lineage_version"] = COMPOSER_VERSION
            updated_shots.append(shot_copy)

        story_intelligence["schema_director_shots"] = updated_shots
        run_context["story_intelligence"] = story_intelligence
        run_context["runway_composer_version"] = COMPOSER_VERSION
        run_context["runway_composed_clips"] = composed_clips
        run_context["runway_composed_at"] = _now()
        brief["run_context"] = run_context

        return {
            "runway_composer_version": COMPOSER_VERSION,
            "composed_at": run_context["runway_composed_at"],
            "topic": topic,
            "clip_count": clip_count,
            "clips": composed_clips,
            "brief_snapshot": brief,
        }


def _already_composed(brief: dict[str, Any]) -> bool:
    run_context = _dict(brief.get("run_context"))
    if run_context.get("runway_composer_version") != COMPOSER_VERSION:
        return False
    clips = run_context.get("runway_composed_clips")
    if not isinstance(clips, list) or not clips:
        return False
    return all(
        isinstance(c, dict)
        and _dict(c.get("lineage")).get("merge_pass") == MERGE_PASS
        and _normalize_text(c.get("composed_prompt") or "")
        for c in clips
    )


def apply_runway_prompt_composer_to_session(session: dict[str, Any]) -> dict[str, Any]:
    """Mutate session brief_snapshot with composed clips when composer is enabled."""
    from content_brain.execution.runway_prompt_composer_config import enable_runway_prompt_composer

    session = dict(session)
    if not enable_runway_prompt_composer(session):
        return session

    brief = _dict(session.get("brief_snapshot"))
    if not brief:
        return session

    if _already_composed(brief):
        return session

    result = RunwayPromptComposer().compose(brief)
    session["brief_snapshot"] = result["brief_snapshot"]
    return session


__all__ = [
    "RunwayPromptComposer",
    "apply_runway_prompt_composer_to_session",
    "COMPOSER_VERSION",
    "ENGINE_NAME",
]
