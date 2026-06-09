"""
Phase RUNWAY-STARTER-TO-VIDEO-F — Runway continuity prompt builder.

Converts a story/video idea into starter_image_prompt + clip_prompts[] for the
Image → Use to Video → multi-clip continuity workflow.

Prompt generation only — no browser, Generate, Download, or credits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.runway_continuity_dry_run import build_continuity_plan
from content_brain.execution.runway_continuity_models import RunwayContinuityPlan

try:
    from content_brain.execution.runway_story_brief_builder import (
        RunwayStoryBrief,
        build_runway_story_brief,
    )
except ImportError:  # pragma: no cover
    RunwayStoryBrief = Any  # type: ignore[misc, assignment]
    build_runway_story_brief = None  # type: ignore[assignment]

BUILDER_VERSION = "runway_starter_to_video_f_v4"
NARRATIVE_PROMPT_WEIGHT = 0.7
CONTINUITY_PROMPT_WEIGHT = 0.3

SCIENTIFIC_EXPLANATION_CLIP_FRAMES: dict[int, str] = {
    1: (
        "Scientific explanation opening: pose the why question with visible evidence, "
        "mechanism stakes, and concentration context."
    ),
    2: (
        "Mechanism beat: explain the science because molecular volatility, skin chemistry, "
        "note evaporation, and fixatives drive longevity and projection."
    ),
    3: (
        "Takeaway beat: translate the evidence into a clear conclusion about concentration, "
        "longevity, and lasting power on skin."
    ),
}

SCIENTIFIC_EXPLANATION_CROSS_DOMAIN_CLIP_FRAMES: dict[int, str] = {
    1: (
        "Scientific cross-domain opening: pose the core question with one surprising visual hook "
        "and immediate stakes — do not preview every domain yet."
    ),
    2: (
        "Mechanism beat: explain how the process works with cause-and-effect evidence "
        "grounded in this clip's assigned concepts only."
    ),
    3: (
        "Takeaway beat: deliver the outcome verdict and business or human impact "
        "using this clip's assigned concepts only."
    ),
}

CROSS_DOMAIN_FUSION_CLIP_FRAMES: dict[int, str] = {
    1: (
        "Future analysis opening: frame the market claim, trend forecast, and 2030 opportunity with visible evidence."
    ),
    2: (
        "Evidence beat: compare automation impact, prediction models, consumer adoption signals, and cross-domain mechanism detail."
    ),
    3: (
        "Verdict beat: deliver the likely outcome, business impact, and what still requires human judgment."
    ),
}

RUNWAY_PROMPT_MAX_CHARS = 5000
STARTER_IMAGE_MAX_CHARS = RUNWAY_PROMPT_MAX_CHARS
STARTER_IMAGE_SOFT_MIN = 1800
CLIP_PROMPT_SOFT_MIN = 2500
CLIP_PROMPT_SOFT_MAX = RUNWAY_PROMPT_MAX_CHARS
CLIP_PROMPT_HARD_MAX = RUNWAY_PROMPT_MAX_CHARS
CLIP_DURATION_SECONDS = 10
DEFAULT_CLIP_COUNT = 3

DEFAULT_ASPECT_LABEL = "vertical 9:16"
DEFAULT_VISUAL_STYLE = "cinematic realistic"
DEFAULT_IMAGE_QUALITY_LABEL = "2K photoreal detail"

FORBIDDEN_VISUAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\bsubtitles?\b",
        r"\bcaptions?\b",
        r"\bwatermarks?\b",
        r"\blogo[s]?\b",
        r"\blower third[s]?\b",
        r"\btext overlay[s]?\b",
        r"\bon-?screen text\b",
        r"\bbrand mark[s]?\b",
        r"\btitle card[s]?\b",
        r"\bui overlay[s]?\b",
    )
)

MOTION_VERBS_BY_PHASE: dict[str, tuple[str, ...]] = {
    "open": (
        "begins with a slow discovery push-in",
        "opens on alert head-turn and environmental reaction",
        "starts with medium-wide push-in as the subject notices the first clue",
        "initiates a controlled dolly forward toward the narrative hook",
    ),
    "middle": (
        "continues with purposeful tracking movement through the space",
        "maintains fluid lateral camera tracking during escalation",
        "progresses through a single continuous forward action beat",
        "advances the action with rising environmental pressure without cutting away",
    ),
    "close": (
        "resolves into a reveal-focused hero moment",
        "settles into a payoff end-frame for continuity handoff",
        "eases into a final micro-motion reveal-ready pose",
        "concludes with a smooth deceleration toward the decisive payoff frame",
    ),
}

CLIP_NARRATIVE_ROLES: dict[int, dict[str, str]] = {
    1: {
        "role": "discovery",
        "camera": "medium-wide push-in; subject shifts from stillness to alerted attention",
        "environment": "introduce first environmental story beat (rain shift, distant lights, particles)",
        "emotion": "curiosity and unease awaken",
    },
    2: {
        "role": "escalation",
        "camera": "lateral tracking shot following motivated forward movement",
        "environment": "weather, lighting, or background motion intensifies while location stays fixed",
        "emotion": "pressure and urgency rise",
    },
    3: {
        "role": "payoff",
        "camera": "push to hero close or crane down to reveal object/consequence",
        "environment": "environment frames the reveal detail without changing world location",
        "emotion": "emotional consequence lands in a frame-ready end pose",
    },
}

CAMERA_CONTINUITY_LIBRARY: tuple[str, ...] = (
    "35mm anamorphic lens personality with natural edge falloff",
    "shallow depth of field keeping background softly readable",
    "handheld-inspired stability without chaotic shake",
    "motivated rack focus only when action demands it",
    "vertical framing with intentional headroom for Shorts composition",
)

LIGHTING_CONTINUITY_LIBRARY: tuple[str, ...] = (
    "consistent motivated key light direction across the sequence",
    "practical sources remain fixed in world space",
    "volumetric atmosphere density unchanged between beats",
    "skin and material specular response stays coherent",
    "no sudden exposure jumps or white balance shifts",
)

ENVIRONMENT_MICRO_MOTION: tuple[str, ...] = (
    "background extras or particles move subtly in parallax",
    "ambient particulate catches the same light angle throughout",
    "practical lights flicker minimally within realistic bounds",
    "fabric, hair, or surface micro-movement reacts to the same air current",
    "distant city or nature elements drift slowly for depth",
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _sentences(text: str) -> list[str]:
    raw = _normalize(text)
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+", raw)
    return [p.strip() for p in parts if p.strip()]


def _truncate_words(text: str, max_chars: int) -> str:
    normalized = _normalize(text)
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[: max_chars + 1].rsplit(" ", 1)[0].strip()
    if clipped.endswith((".", "!", "?")):
        return clipped
    return clipped.rstrip(",;:") + "."


def _contains_forbidden_visual(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in FORBIDDEN_VISUAL_PATTERNS:
        for match in pattern.finditer(text):
            start = match.start()
            prefix = text[max(0, start - 8):start].lower()
            if re.search(r"\b(no|without|avoid|exclude)\s*$", prefix):
                continue
            hits.append(pattern.pattern)
            break
    return hits


def _strip_forbidden_visual(text: str) -> str:
    cleaned = _normalize(text)
    for pattern in FORBIDDEN_VISUAL_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return _normalize(re.sub(r"\s+([,.;])", r"\1", cleaned))


def _clip_phase(index: int, total: int) -> str:
    if total <= 1:
        return "close"
    if index == 1:
        return "open"
    if index == total:
        return "close"
    return "middle"


@dataclass(frozen=True)
class ContinuityAnchors:
    character: str
    location: str
    lighting: str
    camera: str
    palette: str
    wardrobe: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "character": self.character,
            "location": self.location,
            "lighting": self.lighting,
            "camera": self.camera,
            "palette": self.palette,
            "wardrobe": self.wardrobe,
        }

    def lock_line(self) -> str:
        wardrobe = f", same wardrobe ({self.wardrobe})" if self.wardrobe else ", same wardrobe"
        return (
            f"Continuity lock: same character ({self.character}){wardrobe}, "
            f"same location ({self.location}), same lighting ({self.lighting}), "
            f"same camera language ({self.camera}), same palette ({self.palette}). "
            f"No scene jump. No unrelated location change."
        )


@dataclass
class RunwayContinuityPromptBundle:
    project_id: str
    story_idea: str
    clip_count: int
    starter_image_prompt: str
    clip_prompts: list[str]
    continuity_anchors: ContinuityAnchors
    warnings: list[str] = field(default_factory=list)
    char_stats: dict[str, Any] = field(default_factory=dict)
    builder_version: str = BUILDER_VERSION
    story_brief: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "project_id": self.project_id,
            "story_idea": self.story_idea,
            "clip_count": self.clip_count,
            "starter_image_prompt": self.starter_image_prompt,
            "clip_prompts": list(self.clip_prompts),
            "continuity_anchors": self.continuity_anchors.to_dict(),
            "warnings": list(self.warnings),
            "char_stats": dict(self.char_stats),
            "builder_version": self.builder_version,
        }
        if self.story_brief is not None and hasattr(self.story_brief, "to_dict"):
            payload["story_brief"] = self.story_brief.to_dict()
        return payload

    def to_continuity_plan(self, **plan_kwargs: Any) -> RunwayContinuityPlan:
        return build_continuity_plan(
            project_id=self.project_id,
            starter_image_prompt=self.starter_image_prompt,
            clip_prompts=self.clip_prompts,
            **plan_kwargs,
        )


@dataclass
class PromptBuilderInput:
    story_idea: str
    project_id: str = "continuity_project"
    clip_count: int = DEFAULT_CLIP_COUNT
    character: str = ""
    location: str = ""
    lighting: str = ""
    camera: str = ""
    palette: str = ""
    wardrobe: str = ""
    director_shots: list[dict[str, Any]] | None = None
    visual_style: str = DEFAULT_VISUAL_STYLE
    aspect_label: str = DEFAULT_ASPECT_LABEL
    story_brief: Any | None = None
    auto_story_brief: bool = False
    target_platform: str = "youtube_shorts"
    niche_style: str = "cinematic"
    mood: str = "tense hopeful"


class RunwayPromptBuilder:
    """Rule-based continuity prompt builder for starter-to-video workflow."""

    def build(self, spec: PromptBuilderInput | dict[str, Any] | str) -> RunwayContinuityPromptBundle:
        if isinstance(spec, str):
            payload = PromptBuilderInput(story_idea=spec)
        elif isinstance(spec, dict):
            payload = PromptBuilderInput(
                story_idea=str(spec.get("story_idea") or spec.get("idea") or ""),
                project_id=str(spec.get("project_id") or "continuity_project"),
                clip_count=int(spec.get("clip_count") or DEFAULT_CLIP_COUNT),
                character=str(spec.get("character") or ""),
                location=str(spec.get("location") or ""),
                lighting=str(spec.get("lighting") or ""),
                camera=str(spec.get("camera") or ""),
                palette=str(spec.get("palette") or ""),
                wardrobe=str(spec.get("wardrobe") or ""),
                director_shots=list(spec.get("director_shots") or []) or None,
                visual_style=str(spec.get("visual_style") or DEFAULT_VISUAL_STYLE),
                aspect_label=str(spec.get("aspect_label") or DEFAULT_ASPECT_LABEL),
                story_brief=spec.get("story_brief"),
                auto_story_brief=bool(spec.get("auto_story_brief", False)),
                target_platform=str(spec.get("target_platform") or spec.get("platform") or "youtube_shorts"),
                niche_style=str(spec.get("niche_style") or spec.get("niche") or "cinematic"),
                mood=str(spec.get("mood") or "tense hopeful"),
            )
        else:
            payload = spec

        story = _normalize(payload.story_idea)
        if not story:
            raise ValueError("story_idea is required")
        if payload.clip_count < 1:
            raise ValueError("clip_count must be >= 1")

        story_brief = payload.story_brief
        if story_brief is None and payload.auto_story_brief and build_runway_story_brief is not None:
            story_brief = build_runway_story_brief(
                story,
                target_platform=payload.target_platform,
                niche_style=payload.niche_style,
                mood=payload.mood,
                clip_count=payload.clip_count,
                character=payload.character,
                setting=payload.location,
                wardrobe=payload.wardrobe,
            )

        if story_brief is not None:
            story = story_brief.rich_story_text() if hasattr(story_brief, "rich_story_text") else story
            if not payload.character and hasattr(story_brief, "main_character"):
                payload.character = str(story_brief.main_character or payload.character)
            if not payload.location and hasattr(story_brief, "setting"):
                payload.location = str(story_brief.setting or payload.location)
            if not payload.wardrobe and hasattr(story_brief, "continuity_anchors"):
                anchors_obj = story_brief.continuity_anchors
                payload.wardrobe = str(getattr(anchors_obj, "wardrobe", "") or payload.wardrobe)
            if hasattr(story_brief, "style_direction") and story_brief.style_direction:
                niche_style = str(getattr(story_brief, "niche_style", "") or payload.niche_style)
                if niche_style == "cyberpunk":
                    payload.visual_style = "cinematic cyberpunk neo-noir"
                elif not payload.visual_style or payload.visual_style == DEFAULT_VISUAL_STYLE:
                    payload.visual_style = DEFAULT_VISUAL_STYLE

        warnings: list[str] = []
        forbidden_hits = _contains_forbidden_visual(story)
        if forbidden_hits:
            warnings.append(
                "story_idea contained forbidden visual terms; sanitized in output "
                f"({len(forbidden_hits)} patterns)"
            )
            story = _strip_forbidden_visual(story)

        anchors = self._resolve_anchors(story, payload, story_brief)
        beats = self._resolve_beats(story, payload, story_brief)
        starter = self._build_starter_image_prompt(
            story=story,
            anchors=anchors,
            visual_style=payload.visual_style,
            aspect_label=payload.aspect_label,
            story_brief=story_brief,
        )
        clips = [
            self._build_clip_prompt(
                clip_index=index,
                beat=beats[index - 1],
                anchors=anchors,
                clip_count=payload.clip_count,
                visual_style=payload.visual_style,
                aspect_label=payload.aspect_label,
                director_shot=self._director_shot(payload, index),
                story_brief=story_brief,
            )
            for index in range(1, payload.clip_count + 1)
        ]

        bundle = RunwayContinuityPromptBundle(
            project_id=payload.project_id,
            story_idea=story,
            clip_count=payload.clip_count,
            starter_image_prompt=starter,
            clip_prompts=clips,
            continuity_anchors=anchors,
            warnings=warnings,
            story_brief=story_brief,
        )
        bundle.warnings.extend(validate_prompt_bundle(bundle))
        bundle.char_stats = _char_stats(bundle)
        return bundle

    def _director_shot(self, payload: PromptBuilderInput, clip_index: int) -> dict[str, Any]:
        if not payload.director_shots:
            return {}
        for shot in payload.director_shots:
            if int(shot.get("clip_number") or 0) == clip_index:
                return shot
        if len(payload.director_shots) >= clip_index:
            shot = payload.director_shots[clip_index - 1]
            return shot if isinstance(shot, dict) else {}
        return {}

    def _resolve_anchors(
        self,
        story: str,
        payload: PromptBuilderInput,
        story_brief: Any | None = None,
    ) -> ContinuityAnchors:
        if story_brief is not None and hasattr(story_brief, "continuity_anchors"):
            brief_anchors = story_brief.continuity_anchors
            return ContinuityAnchors(
                character=_normalize(getattr(brief_anchors, "character", "") or payload.character),
                location=_normalize(getattr(brief_anchors, "location", "") or payload.location),
                lighting=_normalize(getattr(brief_anchors, "lighting", "") or payload.lighting),
                camera=_normalize(getattr(brief_anchors, "camera", "") or payload.camera),
                palette=_normalize(getattr(brief_anchors, "palette", "") or payload.palette),
                wardrobe=_normalize(getattr(brief_anchors, "wardrobe", "") or payload.wardrobe),
            )
        sentences = _sentences(story)
        lead = sentences[0] if sentences else story

        character = _normalize(payload.character) or self._infer_character(lead, story)
        location = _normalize(payload.location) or self._infer_location(story)
        lighting = _normalize(payload.lighting) or self._infer_lighting(story)
        camera = _normalize(payload.camera) or CAMERA_CONTINUITY_LIBRARY[0]
        palette = _normalize(payload.palette) or self._infer_palette(story)
        wardrobe = _normalize(payload.wardrobe) or self._infer_wardrobe(story)

        return ContinuityAnchors(
            character=character,
            location=location,
            lighting=lighting,
            camera=camera,
            palette=palette,
            wardrobe=wardrobe,
        )

    def _infer_character(self, lead: str, story: str) -> str:
        patterns = (
            r"\b(a|an|the)\s+([a-zA-Z][\w\s-]{2,40}?)\s+(standing|walking|sitting|looking|running|holding)",
            r"\b(portrait of|close-up of|hero)\s+([a-zA-Z][\w\s-]{2,40})",
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(who|stands|walks|runs)",
        )
        for pattern in patterns:
            match = re.search(pattern, lead, re.I)
            if match:
                group = match.group(match.lastindex or 1)
                return _normalize(group)
        tokens = [t for t in re.findall(r"[A-Za-z']+", story) if len(t) > 3][:6]
        if tokens:
            return " ".join(tokens[:4])
        return "primary subject in focus"

    def _infer_location(self, story: str) -> str:
        location_patterns = (
            r"\b(on|in|inside|within|above|beneath|at)\s+(?:a|an|the)\s+([^.!?]{4,80})",
            r"\b(city|street|room|platform|forest|desert|ocean|rooftop|alley|studio|kitchen|lab)\b[^.!?]{0,40}",
        )
        for pattern in location_patterns:
            match = re.search(pattern, story, re.I)
            if match:
                if match.lastindex and match.lastindex >= 2:
                    return _normalize(match.group(2))
                return _normalize(match.group(0))
        return "single continuous environment established in the story"

    def _infer_lighting(self, story: str) -> str:
        cues = (
            "neon",
            "moonlight",
            "sunset",
            "golden hour",
            "overcast",
            "volumetric",
            "practical",
            "low-key",
            "high contrast",
            "soft diffused",
            "rain-soaked reflective",
        )
        lowered = story.lower()
        found = [cue for cue in cues if cue in lowered]
        if found:
            return ", ".join(found[:3]) + " motivated lighting"
        return "cinematic motivated lighting with stable key direction"

    def _infer_palette(self, story: str) -> str:
        colors = re.findall(
            r"\b(teal|orange|amber|cyan|magenta|gold|silver|crimson|emerald|violet|monochrome|pastel)\b",
            story,
            re.I,
        )
        if colors:
            return ", ".join(dict.fromkeys(c.lower() for c in colors[:4])) + " color grade"
        return "cohesive cinematic color grade"

    def _infer_wardrobe(self, story: str) -> str:
        match = re.search(
            r"\b(wearing|dressed in|in a)\s+([^.!?]{4,60})",
            story,
            re.I,
        )
        if match:
            return _normalize(match.group(2))
        return ""

    def _resolve_beats(
        self,
        story: str,
        payload: PromptBuilderInput,
        story_brief: Any | None = None,
    ) -> list[str]:
        if story_brief is not None and getattr(story_brief, "clip_beats", None):
            beats = [_normalize(str(beat)) for beat in story_brief.clip_beats if _normalize(str(beat))]
            if len(beats) >= payload.clip_count:
                return beats[: payload.clip_count]
        if payload.director_shots:
            beats: list[str] = []
            for index in range(1, payload.clip_count + 1):
                shot = self._director_shot(payload, index)
                parts = [
                    _normalize(shot.get("prompt") or ""),
                    _normalize(shot.get("action") or ""),
                    _normalize(shot.get("motion") or ""),
                ]
                beat = _normalize(". ".join(p for p in parts if p))
                beats.append(beat or story)
            return beats[: payload.clip_count]

        sentences = _sentences(story)
        if not sentences:
            sentences = [story]
        beats = []
        for index in range(payload.clip_count):
            if len(sentences) >= payload.clip_count:
                beats.append(sentences[index])
            else:
                beats.append(sentences[min(index, len(sentences) - 1)])
        return beats

    def _build_starter_image_prompt(
        self,
        *,
        story: str,
        anchors: ContinuityAnchors,
        visual_style: str,
        aspect_label: str,
        story_brief: Any | None = None,
    ) -> str:
        lead = _sentences(story)[0] if _sentences(story) else story
        if story_brief is not None:
            lead = _normalize(getattr(story_brief, "logline", "") or lead)
        body = (
            f"{visual_style} {aspect_label} hero starter frame. "
            f"Static hold composition for reference image generation. "
            f"Subject: {anchors.character}. Environment: {anchors.location}. "
            f"Lighting: {anchors.lighting}. Camera: {anchors.camera}. "
            f"Palette: {anchors.palette}. "
            f"Scene essence: {lead}. "
        )
        if story_brief is not None:
            hook = _normalize(getattr(story_brief, "visual_hook", ""))
            conflict = _normalize(getattr(story_brief, "conflict_tension", ""))
            style = _normalize(getattr(story_brief, "style_direction", ""))
            topic_detail = dict(getattr(story_brief, "topic_story_detail", {}) or {})
            if topic_detail:
                narrative = _topic_narrative_block(topic_detail)
                if narrative:
                    body += f"Topic narrative: {narrative}. "
            if hook:
                body += f"Visual hook: {hook}. "
            if conflict:
                body += f"Tension: {conflict}. "
            if style:
                body += f"Style direction: {style}. "
        body += (
            f"Frame the subject for vertical Shorts with clear silhouette readability. "
            f"Ultra-detailed textures, realistic materials, natural skin and fabric response. "
            f"No motion blur priority — this is a still hero frame that seeds clip 1. "
            f"No text, no subtitles, no logos, no watermarks, no UI overlays."
        )
        if anchors.wardrobe:
            body += f" Wardrobe locked: {anchors.wardrobe}."
        if story_brief is not None:
            beats = list(getattr(story_brief, "clip_beats", []) or [])
            for beat in beats[:3]:
                cleaned = _normalize(str(beat))
                if cleaned:
                    body += f" Story beat reference: {cleaned}. "
        body = self._expand_starter_to_soft_target(_strip_forbidden_visual(body))
        return _truncate_words(body, STARTER_IMAGE_MAX_CHARS)

    def _expand_starter_to_soft_target(self, prompt: str) -> str:
        expanded = _normalize(prompt)
        filler_index = 0
        libraries = [
            CAMERA_CONTINUITY_LIBRARY,
            LIGHTING_CONTINUITY_LIBRARY,
            ENVIRONMENT_MICRO_MOTION,
        ]
        while len(expanded) < STARTER_IMAGE_SOFT_MIN:
            lib = libraries[filler_index % len(libraries)]
            snippet = lib[filler_index % len(lib)]
            expanded = _normalize(
                f"{expanded} Reference detail: {snippet}. "
                "Maintain photoreal texture, material fidelity, and vertical framing readability."
            )
            filler_index += 1
            if filler_index > 28:
                break
        return expanded

    def _build_clip_prompt(
        self,
        *,
        clip_index: int,
        beat: str,
        anchors: ContinuityAnchors,
        clip_count: int,
        visual_style: str,
        aspect_label: str,
        director_shot: dict[str, Any],
        story_brief: Any | None = None,
    ) -> str:
        phase = _clip_phase(clip_index, clip_count)
        motion_seed = MOTION_VERBS_BY_PHASE[phase][(clip_index - 1) % len(MOTION_VERBS_BY_PHASE[phase])]

        director_camera = _normalize(director_shot.get("camera_shot") or director_shot.get("camera") or "")
        director_move = _normalize(director_shot.get("camera_movement") or "")
        director_action = _normalize(director_shot.get("action") or "")
        director_light = _normalize(director_shot.get("lighting") or "")
        continuity_notes = _normalize(director_shot.get("continuity_notes") or "")
        topic_detail = {}
        domain_concepts: list[str] = []
        content_strategy = ""
        fusion_multi_domain = False
        clip_assigned: dict[int, list[str]] = {}
        clip_scoped = False
        if story_brief is not None:
            topic_detail = dict(getattr(story_brief, "topic_story_detail", {}) or {})
            clip_assigned_raw = dict(getattr(story_brief, "clip_assigned_concepts", {}) or {})
            for key, values in clip_assigned_raw.items():
                try:
                    clip_assigned[int(key)] = list(values or [])
                except (TypeError, ValueError):
                    continue
            domain_concepts = list(getattr(story_brief, "domain_concepts", []) or topic_detail.get("domain_concepts") or [])
            fusion_payload = dict(getattr(story_brief, "cross_domain_fusion", {}) or {})
            fusion_multi_domain = bool(fusion_payload.get("multi_domain"))
            if clip_assigned.get(clip_index):
                domain_concepts = list(clip_assigned[clip_index])
            elif fusion_multi_domain:
                from content_brain.execution.content_brain_cross_domain_fusion import balance_fusion_domain_concepts

                domain_concepts = balance_fusion_domain_concepts(
                    fusion_payload.get("domain_concepts_by_domain") or {},
                    max_total=12,
                ) or domain_concepts
            content_strategy = str(getattr(story_brief, "content_strategy", "") or "")
            clip_scoped = bool(clip_assigned.get(clip_index))
            topic_detail = _resolve_prompt_topic_detail(
                topic_detail,
                domain_concepts=domain_concepts,
                clip_scoped=clip_scoped,
            )

        if topic_detail:
            return self._build_topic_weighted_clip_prompt(
                clip_index=clip_index,
                beat=beat,
                anchors=anchors,
                clip_count=clip_count,
                visual_style=visual_style,
                aspect_label=aspect_label,
                director_shot=director_shot,
                topic_detail=topic_detail,
                content_strategy=content_strategy,
                fusion_multi_domain=fusion_multi_domain,
                clip_concepts=list(domain_concepts),
                clip_scoped=clip_scoped,
            )

        core_sections: list[str] = [
            anchors.lock_line(),
            (
                f"Clip {clip_index} of {clip_count}. "
                f"Exactly {CLIP_DURATION_SECONDS} seconds of continuous on-screen motion and action. "
                f"{visual_style} {aspect_label}."
            ),
        ]

        if topic_detail:
            narrative = _topic_narrative_block(topic_detail)
            if narrative:
                core_sections.append(f"Topic-specific story detail: {narrative}.")

        if clip_index == 1:
            core_sections.append(
                "Opens from the approved starter reference image via Use to Video — "
                "preserve identity, wardrobe, and environment from the hero frame."
            )
        else:
            core_sections.append(
                "Seamless continuation from the previous clip last frame via Use Frame — "
                "do not reset location or character identity."
            )

        action_line = director_action or beat
        core_sections.append(
            f"Primary action beat: {action_line}. "
            f"Camera motion: {motion_seed}"
            + (f"; {director_move}" if director_move else "")
            + (f". Shot type: {director_camera}" if director_camera else ".")
        )

        if clip_count >= 3 and clip_index in CLIP_NARRATIVE_ROLES:
            role = CLIP_NARRATIVE_ROLES[clip_index]
            core_sections.append(
                f"Narrative role ({role['role']}): emotional beat — {role['emotion']}. "
                f"Camera progression: {role['camera']}. "
                f"Environmental progression: {role['environment']}. "
                "Preserve the same character, location, and wardrobe — change story energy, not world identity."
            )

        core_sections.append(
            "Motion design for the full 10 seconds: "
            "second 0-2 establish continuity and micro-movement; "
            "second 2-7 execute the main motivated action without cuts; "
            "second 7-10 decelerate into a stable end pose suitable for frame handoff."
        )

        continuity_depth = 1 if topic_detail else 3
        core_sections.append(
            "Cinematography continuity: "
            + "; ".join(CAMERA_CONTINUITY_LIBRARY[:continuity_depth])
            + "."
        )
        core_sections.append(
            "Lighting continuity: "
            + (director_light + ". " if director_light else "")
            + "; ".join(LIGHTING_CONTINUITY_LIBRARY[:continuity_depth])
            + "."
        )
        if not topic_detail:
            core_sections.append(
                "Environment continuity: "
                + "; ".join(ENVIRONMENT_MICRO_MOTION[:continuity_depth])
                + "."
            )

        if continuity_notes:
            core_sections.append(f"Director continuity note: {continuity_notes}.")

        if clip_index < clip_count:
            core_sections.append(
                "End frame must remain in the same spatial layout to enable Use Frame for the next clip."
            )
        else:
            core_sections.append(
                "Final clip resolves action but keeps the same world — no epilogue scene change."
            )

        strict_suffix = (
            "Strict negatives: no text, no subtitles, no captions, no logos, no watermarks, "
            "no title cards, no scene jump, no unrelated new characters entering frame."
        )

        core = _strip_forbidden_visual(" ".join(core_sections))
        core = self._expand_to_soft_target(
            core,
            clip_index=clip_index,
            anchors=anchors,
            topic_detail=topic_detail,
        )
        prompt = _normalize(f"{core} {strict_suffix}")
        return _truncate_preserving_suffix(prompt, strict_suffix, CLIP_PROMPT_HARD_MAX)

    def _build_topic_weighted_clip_prompt(
        self,
        *,
        clip_index: int,
        beat: str,
        anchors: ContinuityAnchors,
        clip_count: int,
        visual_style: str,
        aspect_label: str,
        director_shot: dict[str, Any],
        topic_detail: dict[str, Any],
        content_strategy: str = "",
        fusion_multi_domain: bool = False,
        clip_concepts: list[str] | None = None,
        clip_scoped: bool = False,
    ) -> str:
        director_action = _normalize(director_shot.get("action") or "")
        if clip_scoped and clip_concepts:
            role = _clip_phase(clip_index, clip_count)
            focus = "; ".join(filter_prompt_section_values(list(clip_concepts))[:3])
            action_line = f"{role.title()} — focus on {focus}."
        else:
            action_line = director_action or beat
        narrative_block = _build_topic_narrative_prompt_block(
            topic_detail,
            beat=action_line,
            anchors=anchors,
            clip_index=clip_index,
            clip_count=clip_count,
            content_strategy=content_strategy,
            fusion_multi_domain=fusion_multi_domain,
            clip_concepts=list(clip_concepts or []),
            clip_scoped=clip_scoped,
        )
        continuity_block = _build_compact_continuity_block(
            anchors=anchors,
            clip_index=clip_index,
            clip_count=clip_count,
            visual_style=visual_style,
            aspect_label=aspect_label,
        )
        strict_suffix = (
            "Strict negatives: no text, no subtitles, no captions, no logos, no watermarks, "
            "no title cards, no scene jump, no unrelated new characters entering frame."
        )
        narrative_target = int(CLIP_PROMPT_SOFT_MIN * NARRATIVE_PROMPT_WEIGHT)
        continuity_target = int(CLIP_PROMPT_SOFT_MIN * CONTINUITY_PROMPT_WEIGHT)
        narrative_block = self._expand_topic_narrative_block(
            narrative_block,
            topic_detail=topic_detail,
            target_chars=narrative_target,
            clip_scoped=clip_scoped,
        )
        continuity_block = _truncate_words(continuity_block, max(400, continuity_target + 120))
        core = _strip_forbidden_visual(f"{narrative_block} {continuity_block}")
        prompt = _normalize(f"{core} {strict_suffix}")
        return _truncate_preserving_suffix(prompt, strict_suffix, CLIP_PROMPT_HARD_MAX)

    def _expand_topic_narrative_block(
        self,
        prompt: str,
        *,
        topic_detail: dict[str, Any],
        target_chars: int,
        clip_scoped: bool = False,
    ) -> str:
        expanded = _normalize(prompt)
        fillers = _topic_narrative_fillers(topic_detail, include_beats=not clip_scoped)
        filler_index = 0
        while len(expanded) < target_chars and fillers:
            snippet = fillers[filler_index % len(fillers)]
            expanded = _normalize(f"{expanded} Historical detail: {snippet}.")
            filler_index += 1
            if filler_index > 20:
                break
        return expanded

    def _expand_to_soft_target(
        self,
        prompt: str,
        *,
        clip_index: int,
        anchors: ContinuityAnchors,
        topic_detail: dict[str, Any] | None = None,
    ) -> str:
        expanded = _normalize(prompt)
        filler_index = 0
        topic_fillers = _topic_narrative_fillers(topic_detail or {})
        libraries: list[list[str]] = [
            topic_fillers,
            CAMERA_CONTINUITY_LIBRARY,
            LIGHTING_CONTINUITY_LIBRARY,
            ENVIRONMENT_MICRO_MOTION,
        ]
        while len(expanded) < CLIP_PROMPT_SOFT_MIN:
            lib = libraries[filler_index % len(libraries)]
            if not lib:
                filler_index += 1
                if filler_index > 24:
                    break
                continue
            snippet = lib[(clip_index + filler_index) % len(lib)]
            if lib is topic_fillers:
                expanded = _normalize(f"{expanded} Story detail: {snippet}.")
            else:
                expanded = _normalize(f"{expanded} Additional continuity detail: {snippet}.")
            filler_index += 1
            if filler_index > 24:
                break
        if len(expanded) > CLIP_PROMPT_SOFT_MAX:
            expanded = _truncate_words(expanded, CLIP_PROMPT_SOFT_MAX)
        return expanded


def _resolve_prompt_topic_detail(
    topic_detail: dict[str, Any],
    *,
    domain_concepts: list[str] | None = None,
    clip_scoped: bool = False,
) -> dict[str, Any]:
    from content_brain.execution.domain_knowledge_layer import filter_prompt_entity_concepts

    payload = dict(topic_detail or {})
    topic = str(payload.get("topic") or "")
    clip_concepts = filter_prompt_entity_concepts(list(domain_concepts or []), topic=topic)
    if clip_scoped and clip_concepts:
        scoped_entities = list(dict.fromkeys(item for item in clip_concepts if item))[:6]
        payload["entities"] = scoped_entities
        payload["objects"] = scoped_entities[:4]
        payload["facts"] = []
        payload["domain_concepts"] = scoped_entities
        return payload

    prioritized = list(clip_concepts)
    prioritized.extend(
        filter_prompt_entity_concepts(list(payload.get("entities") or []), topic=topic)
    )
    prioritized.extend(
        filter_prompt_entity_concepts(list(payload.get("objects") or []), topic=topic)
    )
    prioritized.extend(
        filter_prompt_entity_concepts(list(payload.get("facts") or []), topic=topic)
    )
    merged_entities = list(dict.fromkeys(item for item in prioritized if item))[:10]
    merged_objects = list(
        dict.fromkeys(
            filter_prompt_entity_concepts(list(payload.get("objects") or []), topic=topic)
            + merged_entities[:4]
        )
    )[:6]
    merged_facts = [
        fact
        for fact in filter_prompt_entity_concepts(list(payload.get("facts") or []), topic=topic)
        if fact
    ][:6]
    payload["entities"] = merged_entities
    payload["objects"] = merged_objects or merged_entities[:4]
    payload["facts"] = merged_facts
    payload["domain_concepts"] = merged_entities
    return payload


def _contains_generic_prompt_entities(text: str) -> list[str]:
    from content_brain.execution.domain_knowledge_layer import PROMPT_ENTITY_STOPWORDS

    lowered = str(text or "").lower()
    hits: list[str] = []
    for label, pattern in (
        ("Key entities", r"key entities:\s*([^\.]+)"),
        ("Visible objects", r"visible objects:\s*([^\.]+)"),
        ("Historical facts", r"historical facts:\s*([^\.]+)"),
        ("Historical details", r"historical detail:\s*([^\.]+)"),
    ):
        match = re.search(pattern, lowered)
        if not match:
            continue
        segment = match.group(1)
        for token in re.split(r"[;,]", segment):
            cleaned = token.strip()
            if cleaned in PROMPT_ENTITY_STOPWORDS or cleaned in {"method", "technique", "stuff", "thing"}:
                hits.append(f"{label}:{cleaned}")
    return hits


def _build_topic_narrative_prompt_block(
    topic_detail: dict[str, Any],
    *,
    beat: str,
    anchors: ContinuityAnchors,
    clip_index: int,
    clip_count: int,
    content_strategy: str = "",
    fusion_multi_domain: bool = False,
    clip_concepts: list[str] | None = None,
    clip_scoped: bool = False,
) -> str:
    subject = str(topic_detail.get("subject") or "").strip()
    sections = [
        f"Clip {clip_index} of {clip_count}. Topic-first narrative sequence about {subject or 'the case'}.",
        f"Primary story beat: {beat}.",
        f"Subject identity: {anchors.character}. Location: {anchors.location}.",
    ]
    scoped_concepts = filter_prompt_section_values(list(clip_concepts or []))
    if str(content_strategy or "").strip().lower() == "scientific_explanation":
        frame_source = (
            SCIENTIFIC_EXPLANATION_CROSS_DOMAIN_CLIP_FRAMES
            if fusion_multi_domain
            else SCIENTIFIC_EXPLANATION_CLIP_FRAMES
        )
        frame = frame_source.get(
            clip_index,
            frame_source.get(
                3,
                "Scientific explanation beat with mechanism, evidence, and because-driven cause detail.",
            ),
        )
        sections.append(frame)
    elif str(content_strategy or "").strip().lower() in {
        "future_analysis",
        "business_debate",
        "technology_forecast",
    }:
        frame = CROSS_DOMAIN_FUSION_CLIP_FRAMES.get(
            clip_index,
            CROSS_DOMAIN_FUSION_CLIP_FRAMES.get(
                3,
                "Cross-domain future analysis beat with trend forecast, evidence, and business outcome detail.",
            ),
        )
        sections.append(frame)
    if scoped_concepts:
        sections.append(f"Clip focus concepts: {'; '.join(scoped_concepts[:4])}.")
    if not clip_scoped:
        narrative = _topic_narrative_block(topic_detail)
        if narrative:
            sections.append(f"Topic facts and evidence: {narrative}.")
    for key, label in (
        ("facts", "Historical facts"),
        ("entities", "Key entities"),
        ("objects", "Visible objects"),
        ("settings", "Setting details"),
    ):
        values = filter_prompt_section_values(list(topic_detail.get(key) or []))
        if values:
            sections.append(f"{label}: {'; '.join(str(item) for item in values[:3])}.")
    beats = list(topic_detail.get("narrative_beats") or [])
    if beats and clip_index <= len(beats) and not clip_scoped:
        sections.append(f"Narrative progression: {beats[clip_index - 1]}.")
    return _normalize(" ".join(sections))


def _build_compact_continuity_block(
    *,
    anchors: ContinuityAnchors,
    clip_index: int,
    clip_count: int,
    visual_style: str,
    aspect_label: str,
) -> str:
    handoff = (
        "Opens from approved starter reference via Use to Video."
        if clip_index == 1
        else "Continues from previous clip last frame via Use Frame."
    )
    return _normalize(
        f"{handoff} {visual_style} {aspect_label}. "
        f"{anchors.lock_line()} "
        "Maintain same character, wardrobe, and location. "
        "Single continuous 10-second motivated action with stable end pose for frame handoff."
    )


def _topic_narrative_block(topic_detail: dict[str, Any]) -> str:
    parts: list[str] = []
    subject = str(topic_detail.get("subject") or "").strip()
    if subject:
        parts.append(f"subject {subject}")
    for key in ("facts", "entities", "settings", "objects"):
        values = filter_prompt_section_values(list(topic_detail.get(key) or []))
        for item in values[:2]:
            cleaned = _normalize(str(item))
            if cleaned:
                parts.append(cleaned)
    return "; ".join(parts[:6])


def filter_prompt_section_values(values: list[str]) -> list[str]:
    from content_brain.execution.domain_knowledge_layer import filter_prompt_entity_concepts

    topic = ""
    return filter_prompt_entity_concepts(values, topic=topic)


def _topic_narrative_fillers(topic_detail: dict[str, Any], *, include_beats: bool = True) -> list[str]:
    fillers: list[str] = []
    for key in ("facts", "entities", "objects", "settings"):
        for item in filter_prompt_section_values(list(topic_detail.get(key) or []))[:4]:
            cleaned = _normalize(str(item))
            if cleaned:
                fillers.append(cleaned)
    if include_beats:
        beats = list(topic_detail.get("narrative_beats") or [])
        fillers.extend(_normalize(str(beat)) for beat in beats[:2] if _normalize(str(beat)))
    return fillers


def _truncate_preserving_suffix(text: str, suffix: str, max_chars: int) -> str:
    normalized = _normalize(text)
    suffix_n = _normalize(suffix)
    if len(normalized) <= max_chars:
        return normalized
    if not suffix_n or not normalized.endswith(suffix_n):
        return _truncate_words(normalized, max_chars)
    core = normalized[: -len(suffix_n)].strip()
    budget = max(200, max_chars - len(suffix_n) - 1)
    return _normalize(f"{_truncate_words(core, budget)} {suffix_n}")


def _char_stats(bundle: RunwayContinuityPromptBundle) -> dict[str, Any]:
    clip_lengths = [len(p) for p in bundle.clip_prompts]
    return {
        "runway_prompt_max_chars": RUNWAY_PROMPT_MAX_CHARS,
        "starter_image_chars": len(bundle.starter_image_prompt),
        "starter_image_max": STARTER_IMAGE_MAX_CHARS,
        "clip_prompt_chars": clip_lengths,
        "clip_prompt_min": min(clip_lengths) if clip_lengths else 0,
        "clip_prompt_max": max(clip_lengths) if clip_lengths else 0,
        "clip_prompt_hard_max": CLIP_PROMPT_HARD_MAX,
    }


SCIENTIFIC_EXPLANATION_PROMPT_SPECIFICITY_MIN = 0.70


def validate_prompt_entity_gates(
    bundle: RunwayContinuityPromptBundle,
    *,
    content_strategy: str = "",
    prompt_specificity_score: float | None = None,
) -> list[str]:
    """Return hard validation failures for prompt entity quality gates."""
    failures: list[str] = []
    strategy = str(content_strategy or "").strip().lower()
    if strategy == "scientific_explanation" and prompt_specificity_score is not None:
        if float(prompt_specificity_score) < SCIENTIFIC_EXPLANATION_PROMPT_SPECIFICITY_MIN:
            failures.append(
                f"prompt_specificity_score<{SCIENTIFIC_EXPLANATION_PROMPT_SPECIFICITY_MIN}: "
                f"{float(prompt_specificity_score):.4f}"
            )
    for index, prompt in enumerate(bundle.clip_prompts, start=1):
        generic_hits = _contains_generic_prompt_entities(prompt)
        if generic_hits:
            failures.append(f"clip {index} generic prompt entities: {', '.join(generic_hits[:4])}")
    return failures


def validate_prompt_bundle(bundle: RunwayContinuityPromptBundle) -> list[str]:
    """Return warnings (non-fatal quality notes). Empty list means within all targets."""
    warnings: list[str] = []

    if len(bundle.starter_image_prompt) > STARTER_IMAGE_MAX_CHARS:
        warnings.append(
            f"starter_image_prompt exceeds max ({len(bundle.starter_image_prompt)} > {STARTER_IMAGE_MAX_CHARS})"
        )

    if _contains_forbidden_visual(bundle.starter_image_prompt):
        warnings.append("starter_image_prompt contains forbidden visual terms")

    for index, prompt in enumerate(bundle.clip_prompts, start=1):
        length = len(prompt)
        if length > CLIP_PROMPT_HARD_MAX:
            warnings.append(f"clip {index} exceeds hard max ({length} > {CLIP_PROMPT_HARD_MAX})")
        if length < CLIP_PROMPT_SOFT_MIN:
            warnings.append(
                f"clip {index} below soft min ({length} < {CLIP_PROMPT_SOFT_MIN})"
            )
        elif length > CLIP_PROMPT_SOFT_MAX:
            warnings.append(
                f"clip {index} above soft max ({length} > {CLIP_PROMPT_SOFT_MAX})"
            )
        if _contains_forbidden_visual(prompt):
            warnings.append(f"clip {index} contains forbidden visual terms")
        generic_hits = _contains_generic_prompt_entities(prompt)
        if generic_hits:
            warnings.append(f"clip {index} contains generic prompt entities: {', '.join(generic_hits[:3])}")
        if "10 second" not in prompt.lower() and "10 seconds" not in prompt.lower():
            warnings.append(f"clip {index} missing explicit 10-second motion language")
        if "no scene jump" not in prompt.lower():
            warnings.append(f"clip {index} missing no-scene-jump guard")
        if "continuity lock" not in prompt.lower():
            warnings.append(f"clip {index} missing continuity lock language")

    return warnings


def build_continuity_prompts(
    story_idea: str,
    *,
    project_id: str = "continuity_project",
    clip_count: int = DEFAULT_CLIP_COUNT,
    auto_story_brief: bool = True,
    target_platform: str = "youtube_shorts",
    niche_style: str = "cinematic",
    mood: str = "tense hopeful",
    story_brief: Any | None = None,
    **kwargs: Any,
) -> RunwayContinuityPromptBundle:
    """Convenience wrapper."""
    builder = RunwayPromptBuilder()
    return builder.build(
        PromptBuilderInput(
            story_idea=story_idea,
            project_id=project_id,
            clip_count=clip_count,
            auto_story_brief=auto_story_brief,
            target_platform=target_platform,
            niche_style=niche_style,
            mood=mood,
            story_brief=story_brief,
            **kwargs,
        )
    )


def build_continuity_prompts_from_brief(
    story_brief: RunwayStoryBrief,
    *,
    project_id: str = "continuity_project",
    **kwargs: Any,
) -> RunwayContinuityPromptBundle:
    """Build continuity prompts directly from a prepared RunwayStoryBrief."""
    source = getattr(story_brief, "source_topic", "") or getattr(story_brief, "logline", "")
    return build_continuity_prompts(
        str(source),
        project_id=project_id,
        clip_count=int(getattr(story_brief, "clip_count", DEFAULT_CLIP_COUNT) or DEFAULT_CLIP_COUNT),
        story_brief=story_brief,
        auto_story_brief=False,
        target_platform=str(getattr(story_brief, "target_platform", "youtube_shorts")),
        niche_style=str(getattr(story_brief, "niche_style", "cinematic")),
        mood=str(getattr(story_brief, "mood", "tense hopeful")),
        **kwargs,
    )


__all__ = [
    "BUILDER_VERSION",
    "CLIP_DURATION_SECONDS",
    "CLIP_PROMPT_HARD_MAX",
    "CLIP_PROMPT_SOFT_MAX",
    "CLIP_PROMPT_SOFT_MIN",
    "ContinuityAnchors",
    "PromptBuilderInput",
    "RunwayContinuityPromptBundle",
    "RunwayPromptBuilder",
    "RUNWAY_PROMPT_MAX_CHARS",
    "STARTER_IMAGE_MAX_CHARS",
    "build_continuity_prompts",
    "build_continuity_prompts_from_brief",
    "validate_prompt_bundle",
    "validate_prompt_entity_gates",
]
