"""
Runway Story Brief Builder — content layer before Runway Prompt Builder.

Expands a short topic or raw idea into a structured RunwayStoryBrief with
character, setting, conflict, visual hook, emotional arc, and clip beats.

Rule-based only — no browser, no Runway, no credits, no LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_setting_builder import build_topic_setting
from content_brain.execution.content_brain_topic_authority import (
    extract_topic_domain,
    extract_topic_facets,
)
from content_brain.execution.content_brain_topic_locale import (
    detect_language_code,
    extract_topic_anchor_tokens,
    pick_title_anchor,
)
from content_brain.execution.content_brain_topic_story_detail import TopicStoryDetail, build_topic_story_detail
from content_brain.execution.domain_knowledge_layer import get_domain_profile

BUILDER_VERSION = "runway_story_brief_v3"
DEFAULT_PLATFORM = "youtube_shorts"
DEFAULT_NICHE_STYLE = "cinematic"
DEFAULT_MOOD = "tense hopeful"
DEFAULT_CLIP_COUNT = 3
CLIP_DURATION_SECONDS = 10


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _sentences(text: str) -> list[str]:
    raw = _normalize(text)
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+", raw)
    return [p.strip() for p in parts if p.strip()]


@dataclass(frozen=True)
class StoryBriefAnchors:
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

PLATFORM_PRESETS: dict[str, dict[str, str]] = {
    "youtube_shorts": {
        "aspect_label": "vertical 9:16 YouTube Shorts",
        "pacing": "hook in first second, payoff before loop point",
        "audience": "mobile-first scroll-stopping viewer",
    },
    "tiktok": {
        "aspect_label": "vertical 9:16 TikTok",
        "pacing": "immediate visual hook, micro-escalation every 2 seconds",
        "audience": "fast-scroll discovery viewer",
    },
    "instagram_reels": {
        "aspect_label": "vertical 9:16 Instagram Reels",
        "pacing": "aesthetic-first hook with emotional beat clarity",
        "audience": "visual-first social viewer",
    },
    "runway": {
        "aspect_label": "vertical 9:16",
        "pacing": "cinematic continuity across chained clips",
        "audience": "generative video continuity workflow",
    },
}

NICHE_STYLE_PRESETS: dict[str, dict[str, str]] = {
    "cinematic": {
        "visual_style": "cinematic realistic",
        "camera": "35mm anamorphic lens personality with natural edge falloff",
        "lighting": "motivated cinematic key with volumetric atmosphere",
        "palette": "teal and amber cinematic color grade",
    },
    "cyberpunk": {
        "visual_style": "cinematic cyberpunk neo-noir",
        "camera": "wide anamorphic with neon edge bloom",
        "lighting": "rain-soaked reflective neon practicals and volumetric fog",
        "palette": "teal, magenta, and amber neon color grade",
    },
    "documentary": {
        "visual_style": "premium documentary realism",
        "camera": "handheld-inspired stability with observational framing",
        "lighting": "natural motivated available light with soft contrast",
        "palette": "neutral documentary color grade with selective warmth",
    },
    "mystery": {
        "visual_style": "dark atmospheric mystery",
        "camera": "slow push-ins with shallow depth of field",
        "lighting": "low-key motivated practicals with cold undertones",
        "palette": "desaturated blue-green mystery grade",
    },
    "general": {
        "visual_style": "cinematic realistic",
        "camera": "35mm cinematic lens with stable vertical framing",
        "lighting": "cinematic motivated lighting with stable key direction",
        "palette": "cohesive cinematic color grade",
    },
}

MOOD_TENSION_MAP: dict[str, tuple[str, str]] = {
    "tense": ("rising pressure against an unseen deadline", "anxiety tightening into resolve"),
    "hopeful": ("fragile optimism pushing through adversity", "quiet hope expanding into determination"),
    "melancholic": ("loss held in stillness before motion returns", "sorrow yielding to acceptance"),
    "epic": ("scale of environment dwarfing a single decisive choice", "awe building into committed action"),
    "mysterious": ("an unexplained detail demanding closer inspection", "curiosity deepening into revelation"),
    "tense hopeful": ("danger and possibility coexisting in the same frame", "fear converting into forward motion"),
    "emotional": ("personal stakes tied directly to the viewer's curiosity", "connection deepening into conviction"),
}

DOMAIN_STORY_PRESETS: dict[str, dict[str, dict[str, str]]] = {
    "fishing": {
        "en": {
            "character": "an experienced angler focused on technique",
            "setting": "a misty lakeside at dawn with still water and reeds",
            "wardrobe": "weatherproof jacket and fishing vest with visible lure kit",
            "hook_detail": "a precise lure presentation at the water edge",
        },
        "fa": {
            "character": "یک ماهیگیر حرفه‌ای که روی تکنیک تمرکز دارد",
            "setting": "دریاچه‌ای آرام در سپیده‌دم با مه روی آب",
            "wardrobe": "کاپشن ضدآب و جلیقه ماهیگیری با قلاب‌های مشخص",
            "hook_detail": "ارائه دقیق قلاب در لبه آب",
        },
    },
}

CLIP_BEAT_TEMPLATES: dict[str, dict[int, tuple[str, str, str]]] = {
    "en": {
        1: (
            "{character} opens with {topic} in {setting} — {hook_detail}; camera pushes in on hands and tackle while location stays locked.",
            "{character} introduces {topic} at {setting}; first decisive cast or setup draws immediate attention.",
            "{character} reveals the opening clue for {topic}; alert posture, water and light react to the moment.",
        ),
        2: (
            "{character} escalates {topic} with purposeful movement through {setting}; tension rises as technique becomes visible.",
            "Continuous action around {topic} in {setting}; camera tracks the subject while {conflict} intensifies.",
            "{character} tests the core method behind {topic}; ripples, line tension, or gear detail sharpen the stakes.",
        ),
        3: (
            "{character} lands the payoff for {topic} in {setting} — {ending_beat}; camera settles on the result with emotional clarity.",
            "Final reveal for {topic}: {ending_beat}; same character, location, and wardrobe remain continuous.",
            "{character} closes {topic} with a frame-ready end pose that pays off the method and mood.",
        ),
    },
    "fa": {
        1: (
            "{character} با {topic} در {setting} شروع می‌کند — {hook_detail}; دوربین روی دست‌ها و وسایل ماهیگیری نزدیک می‌شود.",
            "{character} {topic} را در {setting} معرفی می‌کند؛ اولین پرتاب یا آماده‌سازی توجه را جلب می‌کند.",
        ),
        2: (
            "{character} {topic} را در {setting} با حرکت هدفمند پیش می‌برد؛ فشار داستان با دیده شدن تکنیک بیشتر می‌شود.",
            "حرکت پیوسته حول {topic} در {setting}; دوربین سوژه را دنبال می‌کند و {conflict} شدت می‌گیرد.",
        ),
        3: (
            "{character} payoff مربوط به {topic} را در {setting} می‌گیرد — {ending_beat}; دوربین روی نتیجه می‌ایستد.",
            " reveal نهایی برای {topic}: {ending_beat}; همان شخصیت، مکان و لباس حفظ می‌شود.",
        ),
    },
}


@dataclass(frozen=True)
class StoryBriefInput:
    topic: str
    target_platform: str = DEFAULT_PLATFORM
    niche_style: str = DEFAULT_NICHE_STYLE
    mood: str = DEFAULT_MOOD
    clip_count: int = DEFAULT_CLIP_COUNT
    duration_seconds: int = CLIP_DURATION_SECONDS
    character: str = ""
    setting: str = ""
    wardrobe: str = ""
    seo_title: str = ""
    related_trends: tuple[str, ...] = ()
    language_code: str = ""
    content_strategy: str = ""
    strategy_clip_beats: tuple[str, ...] = ()
    strategy_conflict: str = ""
    strategy_visual_hook: str = ""
    strategy_niche_style: str = ""
    strategy_effective_mood: str = ""
    topic_category: str = ""
    openai_enrichment: dict[str, Any] | None = None
    cross_domain_fusion: dict[str, Any] | None = None


@dataclass
class RunwayStoryBrief:
    title: str
    logline: str
    subject: str
    main_character: str
    environment: str
    setting: str
    conflict: str
    conflict_tension: str
    stakes: str
    emotional_arc: str
    visual_hook: str
    opening_hook: str
    escalation: str
    payoff: str
    ending_beat: str
    style_direction: str
    continuity_anchors: StoryBriefAnchors
    clip_beats: list[str]
    scene_progression: list[str]
    source_topic: str = ""
    target_platform: str = DEFAULT_PLATFORM
    niche_style: str = DEFAULT_NICHE_STYLE
    mood: str = DEFAULT_MOOD
    clip_count: int = DEFAULT_CLIP_COUNT
    duration_seconds: int = CLIP_DURATION_SECONDS
    builder_version: str = BUILDER_VERSION
    warnings: list[str] = field(default_factory=list)
    topic_story_detail: dict[str, Any] = field(default_factory=dict)
    domain_concepts: list[str] = field(default_factory=list)
    content_strategy: str = ""
    cross_domain_fusion: dict[str, Any] = field(default_factory=dict)
    concept_distribution: dict[str, Any] = field(default_factory=dict)
    clip_assigned_concepts: dict[int, list[str]] = field(default_factory=dict)
    topic_label: str = ""
    topic_label_quality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "logline": self.logline,
            "subject": self.subject,
            "main_character": self.main_character,
            "environment": self.environment,
            "setting": self.setting,
            "conflict": self.conflict,
            "conflict_tension": self.conflict_tension,
            "stakes": self.stakes,
            "emotional_arc": self.emotional_arc,
            "visual_hook": self.visual_hook,
            "opening_hook": self.opening_hook,
            "escalation": self.escalation,
            "payoff": self.payoff,
            "ending_beat": self.ending_beat,
            "style_direction": self.style_direction,
            "continuity_anchors": self.continuity_anchors.to_dict(),
            "clip_beats": list(self.clip_beats),
            "scene_progression": list(self.scene_progression),
            "source_topic": self.source_topic,
            "target_platform": self.target_platform,
            "niche_style": self.niche_style,
            "mood": self.mood,
            "clip_count": self.clip_count,
            "duration_seconds": self.duration_seconds,
            "builder_version": self.builder_version,
            "warnings": list(self.warnings),
            "topic_story_detail": dict(self.topic_story_detail),
            "domain_concepts": list(self.domain_concepts),
            "content_strategy": self.content_strategy,
            "cross_domain_fusion": dict(self.cross_domain_fusion),
            "concept_distribution": dict(self.concept_distribution),
            "clip_assigned_concepts": {
                str(index): list(values) for index, values in self.clip_assigned_concepts.items()
            },
            "topic_label": self.topic_label,
            "topic_label_quality_score": round(self.topic_label_quality_score, 4),
        }

    def rich_story_text(self) -> str:
        """Combined narrative seed for downstream prompt expansion."""
        beats = " ".join(
            f"Clip {index + 1}: {beat}."
            for index, beat in enumerate(self.clip_beats)
        )
        return _normalize(
            f"{self.logline} Subject: {self.subject}. "
            f"Character: {self.main_character}. Environment: {self.environment}. "
            f"Conflict: {self.conflict}. Stakes: {self.stakes}. "
            f"Opening hook: {self.opening_hook}. Escalation: {self.escalation}. "
            f"Visual hook: {self.visual_hook}. Emotional arc: {self.emotional_arc}. "
            f"Payoff: {self.payoff}. {beats}"
        )


class RunwayStoryBriefBuilder:
    """Rule-based story brief expansion for Runway continuity workflows."""

    def build(self, spec: StoryBriefInput | dict[str, Any] | str) -> RunwayStoryBrief:
        payload = self._coerce_input(spec)
        topic = _normalize(payload.topic)
        if not topic:
            raise ValueError("topic is required")
        if payload.clip_count < 1:
            raise ValueError("clip_count must be >= 1")

        platform_key = self._normalize_key(payload.target_platform, PLATFORM_PRESETS, "runway")
        niche_key = self._normalize_key(
            payload.strategy_niche_style or payload.niche_style,
            NICHE_STYLE_PRESETS,
            "general",
        )
        platform = PLATFORM_PRESETS[platform_key]
        niche = NICHE_STYLE_PRESETS[niche_key]
        mood_key = self._normalize_mood(payload.strategy_effective_mood or payload.mood)
        language_code = str(payload.language_code or detect_language_code(topic)).strip().lower() or "en"
        topic_category = _normalize(payload.topic_category) or extract_topic_domain(topic) or ""
        domain = topic_category or extract_topic_domain(topic)
        domain_preset = (DOMAIN_STORY_PRESETS.get(domain) or {}).get(language_code) or (
            DOMAIN_STORY_PRESETS.get(domain) or {}
        ).get("en", {})
        strategy_beats = [_normalize(b) for b in payload.strategy_clip_beats if _normalize(b)]

        explicit_beats = strategy_beats or self._parse_explicit_clip_beats(topic)
        sentences = _sentences(topic)
        lead = sentences[0] if sentences else topic

        domain_profile = get_domain_profile(
            topic,
            topic_category=topic_category or domain or "",
            openai_enrichment=payload.openai_enrichment,
        )
        topic_detail = build_topic_story_detail(
            topic,
            topic_category=topic_category or domain or "",
            content_strategy=payload.content_strategy,
            language_code=language_code,
            openai_enrichment=payload.openai_enrichment,
        )
        topic_detail_payload = self._finalize_topic_story_detail(
            topic_detail.to_dict(),
            topic=topic,
            domain_profile=domain_profile,
            openai_enrichment=payload.openai_enrichment,
        )
        setting_result = build_topic_setting(
            topic,
            explicit_setting=payload.setting,
            topic_detail=topic_detail,
            domain_profile=domain_profile,
            topic_category=topic_category or domain or "",
            content_strategy=payload.content_strategy,
        )
        main_character = _normalize(payload.character)
        if not main_character:
            from content_brain.execution.content_brain_character_builder import build_character

            character_result = build_character(
                topic,
                explicit_character=(payload.openai_enrichment or {}).get("domain_role", ""),
                topic_category=topic_category or domain or "",
                language_code=language_code,
            )
            main_character = character_result.character
        elif (
            topic_detail.source in {"topic_pack", "openai_classification"}
            or payload.content_strategy
            in {
                "narrative_mystery",
                "documentary",
                "historical_investigation",
                "business_case_study",
            }
        ):
            from content_brain.execution.content_brain_character_builder import build_character

            character_result = build_character(
                topic,
                explicit_character=payload.character or (payload.openai_enrichment or {}).get("domain_role", ""),
                topic_category=topic_category or domain or "",
                language_code=language_code,
            )
            main_character = character_result.character
        elif payload.openai_enrichment and payload.openai_enrichment.get("domain_role"):
            main_character = _normalize(str(payload.openai_enrichment.get("domain_role")))
        setting = setting_result.setting
        wardrobe = _normalize(payload.wardrobe) or domain_preset.get("wardrobe") or self._infer_wardrobe(topic)
        conflict, emotional_arc = self._infer_conflict_and_arc(
            topic,
            mood_key,
            language_code,
            topic_detail=topic_detail,
        )
        if payload.strategy_conflict:
            conflict = _normalize(payload.strategy_conflict)
        fusion_payload = dict(payload.cross_domain_fusion or {})
        if fusion_payload.get("multi_domain"):
            if fusion_payload.get("fused_conflict"):
                conflict = _normalize(str(fusion_payload.get("fused_conflict")))
            if fusion_payload.get("fused_character"):
                main_character = _normalize(str(fusion_payload.get("fused_character")))
            if fusion_payload.get("fused_setting"):
                setting = _normalize(str(fusion_payload.get("fused_setting")))
            fusion_concepts: list[str] = []
            from content_brain.execution.content_brain_cross_domain_fusion import balance_fusion_domain_concepts

            balanced = balance_fusion_domain_concepts(
                fusion_payload.get("domain_concepts_by_domain") or {},
                max_total=12,
            )
            if balanced:
                fusion_concepts = balanced
            else:
                for concepts in (fusion_payload.get("domain_concepts_by_domain") or {}).values():
                    fusion_concepts.extend(str(item) for item in concepts or [])
            if fusion_concepts:
                from content_brain.execution.domain_knowledge_layer import filter_prompt_entity_concepts

                merged = filter_prompt_entity_concepts(
                    fusion_concepts + list(topic_detail_payload.get("entities") or []),
                    topic=topic,
                )
                topic_detail_payload["entities"] = merged[:12]
                topic_detail_payload["objects"] = merged[:6]
                topic_detail_payload["domain_concepts"] = merged[:12]
                topic_detail_payload["source"] = "cross_domain_fusion"
            if fusion_payload.get("fused_clip_structure"):
                strategy_beats = [
                    _normalize(str(item))
                    for item in fusion_payload.get("fused_clip_structure") or []
                    if _normalize(str(item))
                ]
        if payload.content_strategy.startswith("instructional") or payload.content_strategy.endswith("_fishing"):
            emotional_arc = (
                "آموزش از آماده‌سازی تا نتیجه عملی"
                if language_code == "fa"
                else "instructional arc from setup through technique to proven result"
            )
        hook_detail = domain_preset.get("hook_detail") or self._build_visual_hook(
            topic,
            main_character,
            setting,
            niche,
            topic_detail=topic_detail,
        )
        visual_hook = _normalize(payload.strategy_visual_hook) or (
            hook_detail if domain_preset else self._build_visual_hook(
                topic,
                main_character,
                setting,
                niche,
                topic_detail=topic_detail,
            )
        )
        ending_beat = self._build_ending_beat(
            topic,
            main_character,
            explicit_beats,
            payload.clip_count,
            language_code,
            content_strategy=payload.content_strategy,
        )
        logline = self._build_logline(
            topic=topic,
            seo_title=_normalize(payload.seo_title),
            main_character=main_character,
            setting=setting,
            conflict=conflict,
            visual_hook=visual_hook,
            language_code=language_code,
            content_strategy=payload.content_strategy,
            topic_detail=topic_detail,
            cross_domain_fusion=fusion_payload,
        )
        title = _normalize(payload.seo_title) or self._build_title(main_character, setting, conflict, topic)
        style_direction = self._build_style_direction(
            niche=niche,
            platform=platform,
            mood=mood_key,
            niche_key=niche_key,
        )
        if payload.content_strategy.startswith("instructional") or payload.content_strategy in {
            "recipe_tutorial",
            "educational_tech",
            "educational_lifestyle",
        }:
            style_direction = _normalize(
                f"{niche['visual_style']} instructional demo for {platform['aspect_label']}. "
                f"Purpose: teach {topic} step by step with clear hands-on detail. "
                f"Camera: {niche['camera']}. Lighting: {niche['lighting']}."
            )
        if strategy_beats:
            clip_beats = strategy_beats[: payload.clip_count]
        elif topic_detail.narrative_beats and payload.content_strategy in {
            "narrative_mystery",
            "documentary",
            "horror_storytelling",
            "historical_investigation",
            "business_case_study",
        }:
            clip_beats = self._build_topic_detail_beats(
                topic_detail=topic_detail,
                main_character=main_character,
                setting=setting,
                clip_count=payload.clip_count,
            )
        else:
            clip_beats = self._resolve_clip_beats(
                topic=topic,
                explicit_beats=explicit_beats,
                sentences=sentences,
                main_character=main_character,
                setting=setting,
                conflict=conflict,
                ending_beat=ending_beat,
                clip_count=payload.clip_count,
                language_code=language_code,
                hook_detail=hook_detail if isinstance(hook_detail, str) else str(visual_hook),
                related_trends=list(payload.related_trends or ()),
            )
        anchors = StoryBriefAnchors(
            character=main_character,
            location=setting,
            lighting=niche["lighting"],
            camera=niche["camera"],
            palette=niche["palette"],
            wardrobe=wardrobe,
        )

        subject = str(topic_detail_payload.get("subject") or topic_detail.subject or main_character)
        from content_brain.execution.content_brain_topic_authority import (
            extract_topic_facets,
            is_generic_subject_replacement,
        )

        topic_subject, _, _ = extract_topic_facets(topic)
        if is_generic_subject_replacement(subject) or is_generic_subject_replacement(main_character):
            if topic_subject:
                subject = topic_subject
        if is_generic_subject_replacement(main_character) and not is_generic_subject_replacement(subject):
            main_character = subject
        if "boxing" in topic.lower() and "box" not in subject.lower():
            subject = "young boxer training for championship"
            if is_generic_subject_replacement(main_character):
                main_character = "a dedicated young boxer"
        stakes = self._build_stakes(conflict, topic, language_code)
        opening_hook = self._build_opening_hook(visual_hook, topic, main_character, setting)
        escalation = clip_beats[1] if len(clip_beats) >= 2 else self._build_escalation(conflict, topic, language_code)
        payoff = ending_beat
        scene_progression = list(clip_beats)

        brief = RunwayStoryBrief(
            title=title,
            logline=logline,
            subject=subject,
            main_character=main_character,
            environment=setting,
            setting=setting,
            conflict=conflict,
            conflict_tension=conflict,
            stakes=stakes,
            visual_hook=visual_hook,
            opening_hook=opening_hook,
            escalation=escalation,
            emotional_arc=emotional_arc,
            payoff=payoff,
            ending_beat=ending_beat,
            style_direction=style_direction,
            continuity_anchors=anchors,
            clip_beats=clip_beats,
            scene_progression=scene_progression,
            source_topic=topic,
            target_platform=platform_key,
            niche_style=niche_key,
            mood=mood_key,
            clip_count=payload.clip_count,
            duration_seconds=payload.duration_seconds,
            topic_story_detail=topic_detail_payload,
            domain_concepts=list(topic_detail_payload.get("domain_concepts") or []),
            content_strategy=payload.content_strategy,
            cross_domain_fusion=fusion_payload,
        )
        brief.warnings.extend(validate_story_brief(brief))
        return brief

    @staticmethod
    def _finalize_topic_story_detail(
        topic_detail: dict[str, Any],
        *,
        topic: str,
        domain_profile: Any,
        openai_enrichment: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from content_brain.execution.domain_knowledge_layer import filter_prompt_entity_concepts

        payload = dict(topic_detail or {})
        enrichment_concepts = filter_prompt_entity_concepts(
            list((openai_enrichment or {}).get("domain_concepts") or []),
            topic=topic,
        )
        profile_concepts = filter_prompt_entity_concepts(list(domain_profile.concepts[:12]), topic=topic)
        existing_entities = filter_prompt_entity_concepts(list(payload.get("entities") or []), topic=topic)
        merged_entities = list(dict.fromkeys(enrichment_concepts + profile_concepts + existing_entities))[:10]
        merged_objects = list(
            dict.fromkeys(
                filter_prompt_entity_concepts(list(payload.get("objects") or []), topic=topic)
                + profile_concepts[:4]
            )
        )[:6]
        merged_facts = list(dict.fromkeys(list(payload.get("facts") or [])))[:6]
        payload["entities"] = merged_entities
        payload["objects"] = merged_objects or merged_entities[:4]
        payload["facts"] = merged_facts
        payload["domain_concepts"] = merged_entities
        return payload

    def _coerce_input(self, spec: StoryBriefInput | dict[str, Any] | str) -> StoryBriefInput:
        if isinstance(spec, StoryBriefInput):
            return spec
        if isinstance(spec, str):
            return StoryBriefInput(topic=spec)
        return StoryBriefInput(
            topic=str(spec.get("topic") or spec.get("story_idea") or spec.get("idea") or ""),
            target_platform=str(spec.get("target_platform") or spec.get("platform") or DEFAULT_PLATFORM),
            niche_style=str(spec.get("niche_style") or spec.get("niche") or spec.get("channel_style") or DEFAULT_NICHE_STYLE),
            mood=str(spec.get("mood") or DEFAULT_MOOD),
            clip_count=int(spec.get("clip_count") or DEFAULT_CLIP_COUNT),
            duration_seconds=int(spec.get("duration_seconds") or spec.get("duration") or CLIP_DURATION_SECONDS),
            character=str(spec.get("character") or spec.get("main_character") or ""),
            setting=str(spec.get("setting") or ""),
            wardrobe=str(spec.get("wardrobe") or ""),
            seo_title=str(spec.get("seo_title") or spec.get("title") or ""),
            related_trends=tuple(str(item) for item in (spec.get("related_trends") or []) if str(item).strip()),
            language_code=str(spec.get("language_code") or spec.get("language") or ""),
            content_strategy=str(spec.get("content_strategy") or ""),
            strategy_clip_beats=tuple(str(item) for item in (spec.get("strategy_clip_beats") or []) if str(item).strip()),
            strategy_conflict=str(spec.get("strategy_conflict") or ""),
            strategy_visual_hook=str(spec.get("strategy_visual_hook") or ""),
            strategy_niche_style=str(spec.get("strategy_niche_style") or ""),
            strategy_effective_mood=str(spec.get("strategy_effective_mood") or ""),
        )

    @staticmethod
    def _normalize_key(value: str, presets: dict[str, dict[str, str]], fallback: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
        if cleaned in presets:
            return cleaned
        aliases = {
            "shorts": "youtube_shorts",
            "youtube": "youtube_shorts",
            "reels": "instagram_reels",
            "instagram": "instagram_reels",
            "neo_noir": "cyberpunk",
            "sci_fi": "cinematic",
        }
        return aliases.get(cleaned, fallback)

    @staticmethod
    def _normalize_mood(value: str) -> str:
        cleaned = _normalize(value).lower()
        if cleaned in MOOD_TENSION_MAP:
            return cleaned
        for key in MOOD_TENSION_MAP:
            if key in cleaned:
                return key
        return DEFAULT_MOOD.replace(" ", "_") if " " not in DEFAULT_MOOD else DEFAULT_MOOD

    @staticmethod
    def _parse_explicit_clip_beats(topic: str) -> list[str]:
        beats: list[str] = []
        for match in re.finditer(r"(?i)clip\s*(\d+)\s*:\s*([^.!?]+[.!?]?)", topic):
            beats.append(_normalize(match.group(2)))
        return beats

    def _infer_character(self, lead: str, topic: str, *, topic_category: str = "", language_code: str = "en") -> str:
        from content_brain.execution.content_brain_character_builder import build_character

        result = build_character(
            topic,
            topic_category=topic_category,
            language_code=language_code,
        )
        return result.character

    def _infer_setting(self, topic: str, domain: str = "") -> str:
        patterns = (
            r"\b(on|in|inside|within|above|beneath|at)\s+(?:a|an|the)\s+([^.!?]{4,90})",
            r"\b(city|street|room|platform|forest|desert|ocean|rooftop|alley|studio|kitchen|lab|station|cradle|tower)\b[^.!?]{0,50}",
        )
        for pattern in patterns:
            match = re.search(pattern, topic, re.I)
            if match:
                if match.lastindex and match.lastindex >= 2:
                    return _normalize(match.group(2))
                return _normalize(match.group(0))
        if re.search(r"\b(neon|cyberpunk|futuristic|rain)\b", topic, re.I):
            return "a rain-soaked futuristic platform above a glowing neon metropolis at night"
        if domain == "fishing" or re.search(r"\b(fish|zander|pike|lake|river|lure|angler)\b", topic, re.I):
            return "a quiet lakeside fishing spot with mist, reeds, and readable water texture"
        return "a single continuous environment with strong depth and readable vertical framing"

    def _infer_wardrobe(self, topic: str) -> str:
        match = re.search(r"\b(wearing|dressed in|in a)\s+([^.!?]{4,60})", topic, re.I)
        if match:
            return _normalize(match.group(2))
        if re.search(r"\bastronaut\b", topic, re.I):
            return "weathered EVA suit with scuffed helmet visor"
        return ""

    def _infer_conflict_and_arc(
        self,
        topic: str,
        mood_key: str,
        language_code: str = "en",
        *,
        topic_detail: TopicStoryDetail | None = None,
    ) -> tuple[str, str]:
        conflict, arc = MOOD_TENSION_MAP.get(mood_key, MOOD_TENSION_MAP[DEFAULT_MOOD])
        if topic_detail and topic_detail.facts:
            subject = topic_detail.subject
            conflict = _normalize(
                f"What conflicting evidence still surrounds {subject}? {conflict}"
            )
        if re.search(r"\b(rain|storm|danger|chase|deadline|abandoned|lost|alone|snow|freez)\b", topic, re.I):
            conflict = _normalize(
                f"{conflict}; environmental pressure intensifies around the subject"
            )
        anchors = extract_topic_anchor_tokens(topic, limit=2)
        if anchors and not (topic_detail and topic_detail.source == "topic_pack"):
            anchor_text = " ".join(anchors[:2])
            if language_code == "fa":
                conflict = _normalize(f"فشار داستان حول {anchor_text} و {conflict}")
            else:
                conflict = _normalize(f"stakes centered on {anchor_text}; {conflict}")
        return conflict, arc

    def _build_visual_hook(
        self,
        topic: str,
        main_character: str,
        setting: str,
        niche: dict[str, str],
        *,
        topic_detail: TopicStoryDetail | None = None,
    ) -> str:
        if topic_detail and topic_detail.objects:
            obj = topic_detail.objects[0]
            return (
                f"Opening visual hook: {main_character} examines {obj} in {setting}, "
                f"with one unexplained detail about {topic_detail.subject} visible in frame."
            )
        if re.search(r"\b(neon|rain|visor|reflection|glow|fog)\b", topic, re.I):
            return (
                f"Extreme readability hero frame: {main_character} framed against {setting}, "
                "with a single unmistakable visual detail that stops the scroll in under one second."
            )
        return (
            f"Opening visual hook: {main_character} isolated in {setting}, "
            f"{niche['lighting']}, with one sharp focal detail that anchors the entire sequence."
        )

    def _build_ending_beat(
        self,
        topic: str,
        main_character: str,
        explicit_beats: list[str],
        clip_count: int,
        language_code: str = "en",
        content_strategy: str = "",
    ) -> str:
        if explicit_beats and len(explicit_beats) >= clip_count:
            return explicit_beats[clip_count - 1]
        if content_strategy == "instructional_fishing" or "fishing" in content_strategy:
            if language_code == "fa":
                return (
                    f"{main_character} ماهی را land می‌کند و درس اصلی {topic} را "
                    "در یک جمله آموزشی جمع‌بندی می‌کند."
                )
            return (
                f"{main_character} lands the fish and delivers the key takeaway of {topic}: "
                "hook-set timing, lure choice, and depth strategy that made the bite happen."
            )
        if language_code == "fa":
            return (
                f"{main_character} با یک حرکت قطعی داستان {topic} را می‌بندد "
                "در حالی که مکان و لباس برای تداوم ثابت می‌مانند."
            )
        if re.search(r"\b(hand|touch|cradle|launch|door|choice|reveal|catch|hook|lure)\b", topic, re.I):
            return (
                f"{main_character} completes one decisive physical action that closes the emotional question "
                "while keeping the same location and wardrobe locked for continuity."
            )
        return (
            f"{main_character} holds a final stillness that pays off the tension without changing location, "
            "creating a frame-ready end pose for the last clip."
        )

    def _build_logline(
        self,
        *,
        topic: str,
        seo_title: str,
        main_character: str,
        setting: str,
        conflict: str,
        visual_hook: str,
        language_code: str = "en",
        content_strategy: str = "",
        topic_detail: TopicStoryDetail | None = None,
        cross_domain_fusion: dict[str, Any] | None = None,
    ) -> str:
        fusion_payload = dict(cross_domain_fusion or {})
        instructional = content_strategy.startswith("instructional") or content_strategy in {
            "recipe_tutorial",
            "educational_tech",
            "educational_lifestyle",
        }
        if topic_detail and topic_detail.source == "topic_pack" and not instructional:
            fact = topic_detail.facts[0] if topic_detail.facts else topic_detail.subject
            entity = topic_detail.entities[0] if topic_detail.entities else topic_detail.subject
            return _normalize(
                f"{main_character} investigates {topic_detail.subject} in {setting}. "
                f"{fact} Focus: {entity}. Central tension: {conflict}."
            )
        if seo_title:
            if language_code == "fa":
                lead = f"آموزش {topic}: {seo_title}." if instructional else f"{main_character} در {setting}. {seo_title}."
                return _normalize(f"{lead} هدف: {conflict}.")
        if instructional:
            topic_label = pick_title_anchor(topic) if len(topic.split()) > 4 else topic
            return _normalize(
                f"{main_character} teaches {topic_label}. {seo_title}. "
                f"Goal: demonstrate the method clearly. Central question: {conflict}."
            )
        if content_strategy == "scientific_explanation" and fusion_payload.get("multi_domain"):
            from content_brain.execution.content_brain_cross_domain_fusion import balance_fusion_domain_concepts

            concept_clause = ", ".join(
                balance_fusion_domain_concepts(
                    fusion_payload.get("domain_concepts_by_domain") or {},
                    max_total=6,
                )[:6]
            )
            focus = str(fusion_payload.get("story_focus") or topic.rstrip("?"))
            return _normalize(
                f"{main_character} in {setting} investigates {topic.rstrip('?')}, "
                f"combining {focus} through {concept_clause or 'cross-domain evidence'}. "
                f"{seo_title}. Central tension: {conflict}."
            )
        if content_strategy == "scientific_explanation":
            return _normalize(
                f"{main_character} in {setting} explains the science behind {topic.rstrip('?')} "
                f"because concentration, molecules, skin chemistry, and note longevity provide the mechanism and evidence. "
                f"{seo_title}. Central tension: {conflict}."
            )
        if content_strategy in {"future_analysis", "business_debate", "technology_forecast"} and fusion_payload.get("story_focus"):
            return _normalize(
                f"{main_character} in {setting} tests {fusion_payload.get('strategic_angle') or topic.rstrip('?')}, "
                f"combining {fusion_payload.get('story_focus')} with future forecast, trend evidence, automation impact, "
                f"and a 2030 outcome prediction. {seo_title}. Central tension: {conflict}."
            )
        if seo_title:
            return _normalize(
                f"{main_character} in {setting}. {seo_title}. Central tension: {conflict}."
            )
        if len(topic) > 180 and _sentences(topic):
            return _normalize(
                f"{main_character} in {setting}. {_sentences(topic)[0]} "
                f"Central tension: {conflict}."
            )
        return _normalize(
            f"{main_character} in {setting}. {visual_hook} Central tension: {conflict}."
        )

    @staticmethod
    def _build_title(main_character: str, setting: str, conflict: str, topic: str = "") -> str:
        if topic and len(topic) <= 72:
            return _normalize(topic)
        subject = main_character[:48].strip()
        place = setting.split(",")[0][:40].strip() or "One Continuous Scene"
        tension_word = conflict.split(",")[0].split(";")[0][:32].strip() or "Rising Stakes"
        return _normalize(f"{subject} — {place} — {tension_word}")

    @staticmethod
    def _build_stakes(conflict: str, topic: str, language_code: str = "en") -> str:
        if language_code == "fa":
            return _normalize(f"اگر {topic} شکست بخورد، {conflict.split(';')[0]}")
        return _normalize(f"If the central question fails, {conflict.split(';')[0]} — viewer must feel the cost immediately.")

    @staticmethod
    def _build_opening_hook(visual_hook: str, topic: str, character: str, setting: str) -> str:
        if visual_hook:
            return _normalize(visual_hook)
        return _normalize(f"First-second hook: {character} in {setting} reveals why {topic} matters now.")

    @staticmethod
    def _build_escalation(conflict: str, topic: str, language_code: str = "en") -> str:
        if language_code == "fa":
            return _normalize(f"فشار داستان درباره {topic} بالا می‌رود — {conflict}")
        return _normalize(f"Midpoint escalation: pressure around {topic} intensifies — {conflict}")

    @staticmethod
    def _build_style_direction(
        *,
        niche: dict[str, str],
        platform: dict[str, str],
        mood: str,
        niche_key: str,
    ) -> str:
        return _normalize(
            f"{niche['visual_style']} for {platform['aspect_label']}. "
            f"Mood: {mood}. Pacing: {platform['pacing']}. "
            f"Palette: {niche['palette']}. Camera: {niche['camera']}. "
            f"Audience: {platform['audience']}."
        )

    def _resolve_clip_beats(
        self,
        *,
        topic: str,
        explicit_beats: list[str],
        sentences: list[str],
        main_character: str,
        setting: str,
        conflict: str,
        ending_beat: str,
        clip_count: int,
        language_code: str = "en",
        hook_detail: str = "",
        related_trends: list[str] | None = None,
    ) -> list[str]:
        if explicit_beats and len(explicit_beats) >= clip_count:
            return explicit_beats[:clip_count]

        localized = CLIP_BEAT_TEMPLATES.get(language_code) or CLIP_BEAT_TEMPLATES["en"]
        trend_note = ""
        if related_trends:
            trend_note = related_trends[0]

        beats: list[str] = []
        for index in range(1, clip_count + 1):
            if len(sentences) >= clip_count and index <= len(sentences):
                beats.append(sentences[index - 1])
                continue
            phase = min(index, 3)
            templates = localized.get(phase) or CLIP_BEAT_TEMPLATES["en"][phase]
            template = templates[(index - 1) % len(templates)]
            beats.append(
                _normalize(
                    template.format(
                        character=main_character,
                        setting=setting,
                        conflict=conflict,
                        ending_beat=ending_beat,
                        topic=topic,
                        hook_detail=hook_detail or topic,
                        trend=trend_note,
                    )
                )
            )
        return beats[:clip_count]

    @staticmethod
    def _build_topic_detail_beats(
        *,
        topic_detail: TopicStoryDetail,
        main_character: str,
        setting: str,
        clip_count: int,
    ) -> list[str]:
        beats = list(topic_detail.narrative_beats)
        if len(beats) >= clip_count:
            return [_normalize(beat) for beat in beats[:clip_count]]
        while len(beats) < clip_count:
            index = len(beats)
            obj = topic_detail.objects[index % len(topic_detail.objects)] if topic_detail.objects else topic_detail.subject
            beats.append(
                _normalize(
                    f"{main_character} continues investigating {topic_detail.subject} in {setting}, "
                    f"focusing on {obj}."
                )
            )
        return beats[:clip_count]


def validate_story_brief(brief: RunwayStoryBrief) -> list[str]:
    warnings: list[str] = []
    required = {
        "title": brief.title,
        "logline": brief.logline,
        "subject": brief.subject,
        "main_character": brief.main_character,
        "environment": brief.environment,
        "conflict": brief.conflict,
        "stakes": brief.stakes,
        "visual_hook": brief.visual_hook,
        "opening_hook": brief.opening_hook,
        "escalation": brief.escalation,
        "payoff": brief.payoff,
        "ending_beat": brief.ending_beat,
        "style_direction": brief.style_direction,
    }
    for key, value in required.items():
        if not _normalize(str(value)):
            warnings.append(f"missing or empty field: {key}")
    if len(brief.clip_beats) < brief.clip_count:
        warnings.append(
            f"clip_beats count ({len(brief.clip_beats)}) below clip_count ({brief.clip_count})"
        )
    if any(not _normalize(beat) for beat in brief.clip_beats):
        warnings.append("one or more clip beats are empty")
    if len(brief.logline) < 80:
        warnings.append(f"logline may be too short for rich prompts ({len(brief.logline)} chars)")
    return warnings


def build_runway_story_brief(
    topic: str,
    *,
    target_platform: str = DEFAULT_PLATFORM,
    niche_style: str = DEFAULT_NICHE_STYLE,
    mood: str = DEFAULT_MOOD,
    clip_count: int = DEFAULT_CLIP_COUNT,
    duration_seconds: int = CLIP_DURATION_SECONDS,
    **kwargs: Any,
) -> RunwayStoryBrief:
    """Convenience wrapper."""
    builder = RunwayStoryBriefBuilder()
    return builder.build(
        StoryBriefInput(
            topic=topic,
            target_platform=target_platform,
            niche_style=niche_style,
            mood=mood,
            clip_count=clip_count,
            duration_seconds=duration_seconds,
            character=str(kwargs.get("character") or kwargs.get("main_character") or ""),
            setting=str(kwargs.get("setting") or ""),
            wardrobe=str(kwargs.get("wardrobe") or ""),
        )
    )


__all__ = [
    "BUILDER_VERSION",
    "DEFAULT_MOOD",
    "DEFAULT_NICHE_STYLE",
    "DEFAULT_PLATFORM",
    "RunwayStoryBrief",
    "RunwayStoryBriefBuilder",
    "StoryBriefAnchors",
    "StoryBriefInput",
    "build_runway_story_brief",
    "validate_story_brief",
]
