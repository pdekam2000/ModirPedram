"""
Story Intelligence Engine — Phase 9A foundation.

Turns a selected content idea + existing StoryBlueprint into a cinematic
story plan with scene-level direction and provider-neutral director shots.

No persistent memory in 9A. No video provider changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import md5
import json
import re
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    DirectorShot,
    HookPackage,
    StoryBlueprint,
    TrendSignal,
)

try:
    from content_brain.engines.video_format_planner import VideoFormatPlan
except ImportError:
    VideoFormatPlan = Any  # type: ignore[misc, assignment]

try:
    from content_brain.engines.story_memory_engine import StoryMemoryEngine
except ImportError:  # pragma: no cover - optional Phase 9B layer
    StoryMemoryEngine = None  # type: ignore[assignment,misc]

from content_brain.engines.topic_class_grammar_engine import TopicClassGrammarEngine

ENGINE_VERSION = "story_intelligence_v1"

BEAT_ROLES = [
    "HOOK_BEAT",
    "CONTEXT_BEAT",
    "ESCALATION_BEAT",
    "PATTERN_BREAK",
    "PAYOFF_BEAT",
    "LOOP_SEED",
]

BEAT_ROLE_LABELS = {
    "HOOK_BEAT": "hook",
    "CONTEXT_BEAT": "context",
    "ESCALATION_BEAT": "escalation",
    "PATTERN_BREAK": "pattern_break",
    "PAYOFF_BEAT": "payoff",
    "LOOP_SEED": "loop_seed",
}

EMOTIONAL_TARGETS = {
    "HOOK_BEAT": ("curiosity", 0.88),
    "CONTEXT_BEAT": ("grounding", 0.55),
    "ESCALATION_BEAT": ("tension", 0.78),
    "PATTERN_BREAK": ("surprise", 0.82),
    "PAYOFF_BEAT": ("payoff", 0.92),
    "LOOP_SEED": ("open_loop", 0.70),
}

GENERIC_VISUAL_PATTERNS = [
    "person looking shocked",
    "person shocked",
    "dark room",
    "walking alone",
    "generic b-roll",
    "cinematic b-roll",
    "slow motion walk",
    "talking head",
    "random footage",
]

NICHE_VISUAL_LEXICON: dict[str, list[str]] = {
    "football": [
        "broadcast replay monitor",
        "VAR review screen",
        "referee earpiece close-up",
        "stadium line-mark freeze frame",
        "touchline fourth official board",
    ],
    "dark_mystery": [
        "blueprint floor plan with missing room",
        "cold draft under door gap",
        "flickering hallway sconce",
        "architectural anomaly in wall panel",
        "hum vibration on metal door handle",
    ],
    "storytelling": [
        "documentary evidence board",
        "timestamped archival still",
        "annotated map detail",
        "witness note margin highlight",
        "contradicting frame comparison",
    ],
    "general": [
        "topic-specific object in sharp focus",
        "evidence detail macro shot",
        "contrasting before/after frame",
        "annotated screen capture",
        "environmental texture tied to claim",
    ],
}


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return [token for token in cleaned.split() if len(token) >= 3]


def _topic_anchor_tokens(topic: str, limit: int = 6) -> list[str]:
    stop = {"the", "and", "for", "that", "this", "with", "from", "why", "how", "what"}
    tokens = [t for t in _tokenize(topic) if t not in stop]
    return tokens[:limit] if tokens else ["topic"]


def _fingerprint(text: str, length: int = 12) -> str:
    return md5(text.encode("utf-8")).hexdigest()[:length]


@dataclass
class NarrativeContext:
    profile: dict[str, Any]
    topic: str
    hook: str
    hook_class: str
    niche: str
    niche_label: str
    story_mode: str
    reveal_type: str
    loop_seed: str
    sensory_anchor: str
    topic_tokens: list[str] = field(default_factory=list)
    semantic_clusters: list[str] = field(default_factory=list)


class NarrativeStrategyEngine:
    """Derive narrative premise and story framing from topic + hook + profile."""

    def build(self, context: NarrativeContext) -> dict[str, Any]:
        anchor = " ".join(context.topic_tokens[:3])
        premise = (
            f"A {context.niche_label} story about {context.topic} "
            f"that proves {anchor} is the detail everyone missed."
        )
        narrative_question = f"What does {anchor} reveal about {context.topic}?"
        stakes = (
            f"If viewers ignore {anchor}, they misread the entire {context.niche_label} angle."
        )
        visual_language = self._resolve_visual_language(context)

        return {
            "narrative_premise": premise,
            "narrative_question": narrative_question,
            "stakes_statement": stakes,
            "story_mode": context.story_mode,
            "hook_class": context.hook_class,
            "niche_visual_language": visual_language,
        }

    def _resolve_visual_language(self, context: NarrativeContext) -> list[str]:
        niche = context.niche
        base = list(NICHE_VISUAL_LEXICON.get(niche, NICHE_VISUAL_LEXICON["general"]))
        profile_style = str(context.profile.get("visual_style", "")).strip()
        if profile_style:
            base.insert(0, profile_style)
        for cluster in context.semantic_clusters[:3]:
            if cluster and cluster not in base:
                base.append(cluster)
        for token in context.topic_tokens[:4]:
            token_visual = f"{token}-specific evidence frame"
            if token_visual not in base:
                base.append(token_visual)
        return base[:8]


class EmotionalArcEngine:
    """Build beat-by-beat emotional arc with causal escalation."""

    def build(
        self,
        beats: list[dict[str, Any]],
        context: NarrativeContext,
    ) -> list[dict[str, Any]]:
        arc: list[dict[str, Any]] = []
        prior_emotion = "neutral"
        prior_intensity = 0.0

        for index, beat in enumerate(beats):
            beat_id = beat["beat_id"]
            emotion, intensity = EMOTIONAL_TARGETS.get(
                beat_id,
                ("tension", 0.65),
            )
            cause = self._build_cause(beat_id, context, prior_emotion)
            arc.append(
                {
                    "beat_id": beat_id,
                    "emotion_target": emotion,
                    "intensity": round(intensity, 2),
                    "cause": cause,
                    "prior_beat_emotion": prior_emotion,
                    "release_or_tension": "tension" if intensity >= prior_intensity else "release",
                    "connects_to_next": beats[index + 1]["beat_id"] if index + 1 < len(beats) else "",
                }
            )
            prior_emotion = emotion
            prior_intensity = intensity

        return arc

    def _build_cause(
        self,
        beat_id: str,
        context: NarrativeContext,
        prior_emotion: str,
    ) -> str:
        anchor = context.topic_tokens[0] if context.topic_tokens else "detail"
        causes = {
            "HOOK_BEAT": f"Hook promises a hidden {anchor} in {context.topic}.",
            "CONTEXT_BEAT": f"After curiosity from {prior_emotion}, viewer needs grounding on {anchor}.",
            "ESCALATION_BEAT": f"Stakes rise when {anchor} contradicts the obvious reading.",
            "PATTERN_BREAK": f"Perspective shifts because {context.reveal_type.replace('_', ' ')} reframes {anchor}.",
            "PAYOFF_BEAT": f"Payoff delivers the answer the hook implied about {anchor}.",
            "LOOP_SEED": f"One unanswered {anchor} detail seeds the next episode.",
        }
        return causes.get(beat_id, f"Advances emotional line from {prior_emotion}.")


class SceneProgressionEngine:
    """Build scene plan where every scene advances story."""

    def build(
        self,
        beats: list[dict[str, Any]],
        context: NarrativeContext,
        clip_count: int,
        clip_duration: int,
    ) -> list[dict[str, Any]]:
        selected = self._select_beats_for_clips(beats, clip_count)
        scenes: list[dict[str, Any]] = []

        for index, beat in enumerate(selected):
            beat_id = beat["beat_id"]
            role = BEAT_ROLE_LABELS.get(beat_id, "progression")
            start_s = int(beat.get("start_second", index * clip_duration))
            end_s = int(beat.get("end_second", start_s + clip_duration))
            prev_id = selected[index - 1]["beat_id"] if index > 0 else ""
            next_id = selected[index + 1]["beat_id"] if index + 1 < len(selected) else ""

            scenes.append(
                {
                    "scene_id": f"scene_{index + 1:02d}",
                    "beat_id": beat_id,
                    "beat_role": role,
                    "start_second": start_s,
                    "end_second": end_s,
                    "duration_seconds": max(1, end_s - start_s),
                    "narrative_purpose": self._narrative_purpose(beat_id, context),
                    "connects_from": prev_id,
                    "connects_to": next_id,
                    "story_advance": self._story_advance(beat_id),
                }
            )

        return scenes

    def _select_beats_for_clips(
        self,
        beats: list[dict[str, Any]],
        clip_count: int,
    ) -> list[dict[str, Any]]:
        if not beats:
            return []
        if len(beats) <= clip_count:
            return beats

        priority = ["HOOK_BEAT", "ESCALATION_BEAT", "PAYOFF_BEAT", "LOOP_SEED"]
        selected: list[dict[str, Any]] = []
        beat_map = {beat["beat_id"]: beat for beat in beats}

        for beat_id in priority:
            if beat_id in beat_map and len(selected) < clip_count:
                selected.append(beat_map[beat_id])

        for beat in beats:
            if beat not in selected and len(selected) < clip_count:
                selected.append(beat)

        return selected[:clip_count]

    def _narrative_purpose(self, beat_id: str, context: NarrativeContext) -> str:
        anchor = context.topic_tokens[0] if context.topic_tokens else "detail"
        purposes = {
            "HOOK_BEAT": f"Interrupt with a concrete {anchor} the audience has not examined.",
            "CONTEXT_BEAT": f"Establish why {anchor} matters inside {context.topic}.",
            "ESCALATION_BEAT": f"Raise stakes by showing {anchor} conflicts with the public narrative.",
            "PATTERN_BREAK": f"Shift frame so {context.reveal_type.replace('_', ' ')} recontextualizes {anchor}.",
            "PAYOFF_BEAT": f"Deliver the decisive {anchor} evidence the hook promised.",
            "LOOP_SEED": f"Leave one {anchor} question open to drive comments or part two.",
        }
        return purposes.get(beat_id, f"Advance story through {anchor}.")

    def _story_advance(self, beat_id: str) -> str:
        advances = {
            "HOOK_BEAT": "new_information",
            "CONTEXT_BEAT": "stakes_definition",
            "ESCALATION_BEAT": "stakes_increase",
            "PATTERN_BREAK": "perspective_shift",
            "PAYOFF_BEAT": "answer_delivery",
            "LOOP_SEED": "open_question",
        }
        return advances.get(beat_id, "narrative_progression")


class VisualOriginalityEngine:
    """Topic-specific visuals; block generic AI filler patterns."""

    def __init__(self, *, grammar_engine: TopicClassGrammarEngine | None = None) -> None:
        self._grammar_engine = grammar_engine or TopicClassGrammarEngine()

    def enrich_scenes(
        self,
        scenes: list[dict[str, Any]],
        context: NarrativeContext,
        visual_language: list[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        notes: list[str] = []
        enriched: list[dict[str, Any]] = []
        self._grammar_engine.beat_grammar_used = []
        self._grammar_engine.resolve_topic_class(
            context.topic,
            context.niche,
            context.profile,
        )

        for index, scene in enumerate(scenes):
            visual = self._build_visual(scene, context, visual_language, index)
            notes.append(
                f"{scene['scene_id']}: topic_class={self._grammar_engine.resolved_topic_class} "
                f"lexicon '{visual_language[index % len(visual_language)]}' beat={scene.get('beat_id')}."
            )
            enriched.append({**scene, **visual})

        return enriched, notes

    def get_visual_grammar_metadata(self) -> dict[str, Any]:
        return self._grammar_engine.metadata().to_dict()

    def _build_visual(
        self,
        scene: dict[str, Any],
        context: NarrativeContext,
        visual_language: list[str],
        index: int,
    ) -> dict[str, Any]:
        lexicon = visual_language[index % len(visual_language)]
        anchor = context.topic_tokens[index % len(context.topic_tokens)] if context.topic_tokens else "subject"
        beat_id = scene["beat_id"]
        emotion, intensity = EMOTIONAL_TARGETS.get(beat_id, ("tension", 0.7))

        grammar_visual = self._grammar_engine.apply_beat_grammar(
            beat_id,
            anchor=anchor,
            topic=context.topic,
            niche_label=context.niche_label,
            scene_role=str(scene.get("beat_role") or "progression"),
            fallback_lexicon=lexicon,
        )
        lighting_mood = self._lighting_for_beat(beat_id, context.niche)
        voiceover_intent = self._vo_intent(beat_id, context)
        mood = grammar_visual.get("pacing") or emotion

        return {
            "visual_description": grammar_visual["visual_description"],
            "emotional_target": emotion,
            "emotional_intensity": intensity,
            "camera_direction": grammar_visual["camera_direction"],
            "lighting_mood": lighting_mood,
            "motion_direction": grammar_visual["motion_direction"],
            "voiceover_intent": voiceover_intent,
            "subject": grammar_visual["subject"],
            "environment": grammar_visual["environment"],
            "action": grammar_visual["action"],
            "mood": mood,
            "framing_style": grammar_visual.get("framing", ""),
            "reveal_style": grammar_visual.get("reveal_style", ""),
            "escalation_style": grammar_visual.get("escalation_style", ""),
            "payoff_style": grammar_visual.get("payoff_style", ""),
            "topic_class": self._grammar_engine.resolved_topic_class,
        }

    def _camera_for_beat(self, beat_id: str) -> str:
        cell = self._grammar_engine.get_grammar(
            self._grammar_engine.resolved_topic_class,
            beat_id,
        )
        return cell.get("camera", "Purposeful medium shot")

    def _lighting_for_beat(self, beat_id: str, niche: str) -> str:
        if niche in {"dark_mystery", "storytelling"}:
            base = "Low-key with motivated practical light source"
        elif niche == "football":
            base = "Broadcast monitor glow mixed with stadium spill light"
        else:
            base = "Natural motivated light with clear subject separation"
        accents = {
            "HOOK_BEAT": " — high contrast accent on focal detail",
            "PAYOFF_BEAT": " — crisp highlight on reveal object",
            "LOOP_SEED": " — falloff into shadow on unresolved edge",
        }
        return base + accents.get(beat_id, "")

    def _motion_for_beat(self, beat_id: str) -> str:
        cell = self._grammar_engine.get_grammar(
            self._grammar_engine.resolved_topic_class,
            beat_id,
        )
        return cell.get("motion", "Deliberate camera move supporting beat purpose")

    def _vo_intent(self, beat_id: str, context: NarrativeContext) -> str:
        intents = {
            "HOOK_BEAT": f"State the overlooked {context.topic_tokens[0]} claim without explaining yet.",
            "CONTEXT_BEAT": f"Ground why {context.topic_tokens[0]} changes interpretation.",
            "ESCALATION_BEAT": "Increase urgency; introduce contradiction.",
            "PATTERN_BREAK": f"Signal the {context.reveal_type.replace('_', ' ')} reframe.",
            "PAYOFF_BEAT": "Deliver the answer with concrete specificity.",
            "LOOP_SEED": f"Pose one unanswered question about {context.topic_tokens[0]}.",
        }
        return intents.get(beat_id, "Advance narration with concrete detail.")

    def _action_for_beat(self, beat_id: str, anchor: str) -> str:
        cell = self._grammar_engine.get_grammar(
            self._grammar_engine.resolved_topic_class,
            beat_id,
        )
        return self._grammar_engine.format_action(
            cell.get("action", "Show {anchor} with narrative purpose"),
            anchor=anchor,
            topic=anchor,
            niche_label="setting",
        )


class AntiGenericSceneEngine:
    """Detect and flag generic AI visual patterns."""

    def audit(
        self,
        scenes: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str], float]:
        notes: list[str] = []
        risk_hits = 0
        audited: list[dict[str, Any]] = []

        seen_subjects: set[str] = set()

        for scene in scenes:
            combined = " ".join(
                [
                    scene.get("visual_description", ""),
                    scene.get("subject", ""),
                    scene.get("action", ""),
                    scene.get("environment", ""),
                ]
            ).lower()

            hits = [pattern for pattern in GENERIC_VISUAL_PATTERNS if pattern in combined]
            subject_key = scene.get("subject", "").lower().strip()
            repeated_subject = subject_key in seen_subjects and subject_key
            if subject_key:
                seen_subjects.add(subject_key)

            reason_parts: list[str] = []
            if hits:
                risk_hits += 1
                reason_parts.append(f"avoided generic patterns: {', '.join(hits)}")
            else:
                reason_parts.append("no generic trope keywords detected")

            if repeated_subject:
                risk_hits += 1
                reason_parts.append("varied subject from prior scene")

            if scene.get("narrative_purpose"):
                reason_parts.append("scene has explicit narrative purpose")
            else:
                risk_hits += 1
                reason_parts.append("WARNING: missing narrative purpose")

            anti_generic_reason = "; ".join(reason_parts)
            notes.append(f"{scene['scene_id']}: {anti_generic_reason}")

            audited.append({**scene, "anti_generic_reason": anti_generic_reason})

        repeated_risk = round(min(1.0, risk_hits / max(len(scenes), 1)), 3)
        return audited, notes, repeated_risk


class CinematicBeatEngine:
    """Assemble cinematic progression and director shots from scenes."""

    def build_progression(
        self,
        scenes: list[dict[str, Any]],
        emotional_arc: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        arc_map = {item["beat_id"]: item for item in emotional_arc}
        progression: list[dict[str, Any]] = []

        for scene in scenes:
            arc = arc_map.get(scene["beat_id"], {})
            progression.append(
                {
                    "scene_id": scene["scene_id"],
                    "beat_id": scene["beat_id"],
                    "escalation_step": arc.get("intensity", 0.5),
                    "camera": scene.get("camera_direction", ""),
                    "lighting": scene.get("lighting_mood", ""),
                    "motion": scene.get("motion_direction", ""),
                    "emotional_target": scene.get("emotional_target", ""),
                    "narrative_link": (
                        f"{scene.get('connects_from', 'start')} → "
                        f"{scene['beat_id']} → {scene.get('connects_to', 'end')}"
                    ),
                }
            )

        return progression

    def build_director_shots(
        self,
        scenes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        shots: list[dict[str, Any]] = []

        for index, scene in enumerate(scenes):
            prompt_intent = (
                f"{scene.get('visual_description', '')}. "
                f"Subject: {scene.get('subject', '')}. "
                f"Action: {scene.get('action', '')}. "
                f"Mood: {scene.get('mood', '')}."
            ).strip()

            shots.append(
                {
                    "shot_id": f"shot_{index + 1:02d}",
                    "scene_id": scene["scene_id"],
                    "clip_number": index + 1,
                    "duration_seconds": scene.get("duration_seconds", 5),
                    "prompt_intent": prompt_intent,
                    "camera": scene.get("camera_direction", ""),
                    "lighting": scene.get("lighting_mood", ""),
                    "subject": scene.get("subject", ""),
                    "environment": scene.get("environment", ""),
                    "action": scene.get("action", ""),
                    "mood": scene.get("mood", ""),
                    "continuity_notes": (
                        f"Follows {scene.get('connects_from') or 'opening'}; "
                        f"sets up {scene.get('connects_to') or 'close'}."
                    ),
                }
            )

        return shots

    def to_schema_director_shots(
        self,
        director_shots: list[dict[str, Any]],
    ) -> list[DirectorShot]:
        schema_shots: list[DirectorShot] = []

        for shot in director_shots:
            camera = shot.get("camera", "Medium shot")
            camera_parts = camera.split(",", 1)
            camera_shot = camera_parts[0].strip()
            camera_movement = (
                camera_parts[1].strip() if len(camera_parts) > 1 else "Static hold"
            )

            schema_shots.append(
                DirectorShot(
                    clip_number=int(shot.get("clip_number", 1)),
                    duration_seconds=max(1, int(shot.get("duration_seconds", 5))),
                    prompt=shot.get("prompt_intent", ""),
                    camera_shot=camera_shot[:120],
                    camera_movement=camera_movement[:120],
                    lighting=str(shot.get("lighting", "Motivated natural light"))[:120],
                    pacing=str(shot.get("mood", "balanced")),
                    continuity_notes=str(shot.get("continuity_notes", ""))[:240],
                )
            )

        return schema_shots


class StoryIntelligenceEngine:
    """
    Enhance an existing StoryBlueprint with cinematic scene planning.

    Usage:
        engine = StoryIntelligenceEngine()
        result = engine.enhance(profile, trend, hooks, story_blueprint, format_plan)
    """

    def __init__(self, memory_engine: Any | None = None) -> None:
        self.narrative_engine = NarrativeStrategyEngine()
        self.emotional_engine = EmotionalArcEngine()
        self.scene_engine = SceneProgressionEngine()
        self.visual_engine = VisualOriginalityEngine()
        self.anti_generic_engine = AntiGenericSceneEngine()
        self.cinematic_engine = CinematicBeatEngine()
        if memory_engine is not None:
            self.memory_engine = memory_engine
        elif StoryMemoryEngine is not None:
            self.memory_engine = StoryMemoryEngine()
        else:
            self.memory_engine = None

    def enhance(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
        video_format_plan: VideoFormatPlan | None = None,
        channel_id: str = "",
    ) -> dict[str, Any]:
        context = self._build_context(profile, trend_signal, hook_package, story_blueprint)
        beats = self._beats_from_blueprint(story_blueprint)

        clip_count = (
            video_format_plan.clip_count
            if video_format_plan is not None
            else len(beats)
        )
        clip_duration = (
            video_format_plan.clip_duration_seconds
            if video_format_plan is not None
            else max(1, story_blueprint.total_duration_seconds // max(len(beats), 1))
        )

        narrative = self.narrative_engine.build(context)
        emotional_arc = self.emotional_engine.build(beats, context)
        scene_plan = self.scene_engine.build(beats, context, clip_count, clip_duration)
        scene_plan, visual_notes = self.visual_engine.enrich_scenes(
            scene_plan,
            context,
            narrative["niche_visual_language"],
        )
        visual_grammar_metadata = self.visual_engine.get_visual_grammar_metadata()
        scene_plan, anti_generic_notes, repeated_risk_score = self.anti_generic_engine.audit(
            scene_plan
        )

        cinematic_progression = self.cinematic_engine.build_progression(
            scene_plan,
            emotional_arc,
        )
        director_shots = self.cinematic_engine.build_director_shots(scene_plan)
        schema_director_shots = self.cinematic_engine.to_schema_director_shots(director_shots)

        story_beats = self._build_story_beats(beats, emotional_arc)
        twist_or_reveal = {
            "reveal_type": context.reveal_type,
            "loop_seed": context.loop_seed,
            "payoff_scene_id": scene_plan[-2]["scene_id"] if len(scene_plan) >= 2 else "",
            "twist_mechanism": f"{context.reveal_type.replace('_', ' ')} reframes {context.topic_tokens[0]}",
        }

        story_signature = _fingerprint(
            f"{context.topic}|{context.hook}|{context.story_mode}|{len(scene_plan)}"
        )
        scene_fingerprints = [
            _fingerprint(
                f"{scene['scene_id']}|{scene.get('visual_description', '')}|{scene.get('subject', '')}"
            )
            for scene in scene_plan
        ]
        visual_fingerprints = [
            _fingerprint(scene.get("visual_description", ""))
            for scene in scene_plan
        ]

        quality = self._score_quality(
            scene_plan,
            emotional_arc,
            visual_notes,
            anti_generic_notes,
            repeated_risk_score,
        )

        story_blueprint_payload = {
            "narrative_premise": narrative["narrative_premise"],
            "emotional_arc": emotional_arc,
            "story_beats": story_beats,
            "cinematic_progression": cinematic_progression,
            "twist_or_reveal": twist_or_reveal,
            "scene_plan": scene_plan,
            "visual_originality_notes": visual_notes,
            "anti_repetition_notes": anti_generic_notes,
            "director_shots": director_shots,
            "story_quality_score": quality,
        }

        payload = {
            "engine_version": ENGINE_VERSION,
            "story_blueprint": story_blueprint_payload,
            "schema_director_shots": [shot.to_dict() for shot in schema_director_shots],
            "story_signature": story_signature,
            "scene_fingerprints": scene_fingerprints,
            "visual_fingerprints": visual_fingerprints,
            "repeated_risk_score": repeated_risk_score,
            "visual_grammar_metadata": visual_grammar_metadata,
            "explainability": {
                "narrative_question": narrative["narrative_question"],
                "stakes_statement": narrative["stakes_statement"],
                "niche_visual_language": narrative["niche_visual_language"],
                "scene_count": len(scene_plan),
                "clip_count": clip_count,
                "topic_class": visual_grammar_metadata.get("topic_class"),
                "topic_class_resolution": visual_grammar_metadata.get("resolution_source"),
                "grammar_version": visual_grammar_metadata.get("grammar_version"),
            },
        }

        if self.memory_engine is not None:
            try:
                memory_result = self.memory_engine.compare(
                    payload,
                    profile,
                    channel_id=channel_id,
                )
                payload["memory"] = memory_result.to_dict()
                payload["repeated_risk_score"] = memory_result.repeated_risk_score
            except Exception:
                pass

        return payload

    def _build_context(
        self,
        profile: dict[str, Any],
        trend_signal: TrendSignal,
        hook_package: HookPackage,
        story_blueprint: StoryBlueprint,
    ) -> NarrativeContext:
        topic = trend_signal.topic.strip()
        hook = hook_package.best_hook_text.strip()
        if not hook and hook_package.variants:
            hook = hook_package.variants[0].text

        hook_class = hook_package.hook_class
        hook_class_value = hook_class.value if hook_class else "unknown"
        if hook_class is None and hook_package.variants:
            hook_class_value = hook_package.variants[0].hook_class.value

        niche = str(profile.get("niche", "general"))
        niche_label = str(profile.get("niche_label", niche.replace("_", " ").title()))
        semantic = profile.get("semantic_universe", {})
        clusters = semantic.get("clusters", []) if isinstance(semantic, dict) else []
        cluster_names = [
            str(cluster.get("name", cluster.get("label", "")))
            for cluster in clusters
            if isinstance(cluster, dict)
        ]

        return NarrativeContext(
            profile=profile,
            topic=topic,
            hook=hook,
            hook_class=hook_class_value,
            niche=niche,
            niche_label=niche_label,
            story_mode=story_blueprint.story_mode.value,
            reveal_type=story_blueprint.reveal_type,
            loop_seed=story_blueprint.loop_seed,
            sensory_anchor=story_blueprint.sensory_anchor,
            topic_tokens=_topic_anchor_tokens(topic),
            semantic_clusters=[name for name in cluster_names if name],
        )

    def _beats_from_blueprint(self, story_blueprint: StoryBlueprint) -> list[dict[str, Any]]:
        beats: list[dict[str, Any]] = []
        for beat in story_blueprint.beats:
            beats.append(
                {
                    "beat_id": beat.beat_id,
                    "act": beat.act,
                    "start_second": beat.start_second,
                    "end_second": beat.end_second,
                    "description": beat.description,
                    "retention_mechanic": beat.retention_mechanic,
                }
            )
        return beats

    def _build_story_beats(
        self,
        beats: list[dict[str, Any]],
        emotional_arc: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        arc_map = {item["beat_id"]: item for item in emotional_arc}
        result: list[dict[str, Any]] = []

        for beat in beats:
            arc = arc_map.get(beat["beat_id"], {})
            result.append(
                {
                    "beat_id": beat["beat_id"],
                    "act": beat["act"],
                    "start_second": beat["start_second"],
                    "end_second": beat["end_second"],
                    "emotional_target": arc.get("emotion_target", ""),
                    "intensity": arc.get("intensity", 0.0),
                    "retention_mechanic": beat.get("retention_mechanic", ""),
                    "description": beat.get("description", ""),
                }
            )

        return result

    def _score_quality(
        self,
        scenes: list[dict[str, Any]],
        emotional_arc: list[dict[str, Any]],
        visual_notes: list[str],
        anti_generic_notes: list[str],
        repeated_risk_score: float,
    ) -> dict[str, Any]:
        if not scenes:
            return {
                "composite": 0.0,
                "originality_score": 0.0,
                "cinematic_score": 0.0,
                "emotional_tension_score": 0.0,
                "visual_diversity_score": 0.0,
                "scene_necessity_score": 0.0,
            }

        has_purpose = sum(1 for scene in scenes if scene.get("narrative_purpose"))
        scene_necessity = round(100.0 * has_purpose / len(scenes), 1)

        subjects = {scene.get("subject", "") for scene in scenes}
        visual_diversity = round(min(100.0, 60.0 + len(subjects) * 8.0), 1)

        intensities = [item.get("intensity", 0.0) for item in emotional_arc]
        if len(intensities) >= 2:
            escalation = intensities[-2] - intensities[0]
            emotional_tension = round(min(100.0, 50.0 + escalation * 80.0), 1)
        else:
            emotional_tension = 55.0

        generic_warnings = sum(
            1 for note in anti_generic_notes if "WARNING" in note
        )
        originality = round(max(0.0, 92.0 - generic_warnings * 15.0 - repeated_risk_score * 20.0), 1)

        cinematic_fields = sum(
            1
            for scene in scenes
            if scene.get("camera_direction") and scene.get("lighting_mood")
        )
        cinematic = round(100.0 * cinematic_fields / len(scenes), 1)

        composite = round(
            originality * 0.25
            + cinematic * 0.20
            + emotional_tension * 0.20
            + visual_diversity * 0.15
            + scene_necessity * 0.20,
            1,
        )

        return {
            "composite": composite,
            "originality_score": originality,
            "cinematic_score": cinematic,
            "emotional_tension_score": emotional_tension,
            "visual_diversity_score": visual_diversity,
            "scene_necessity_score": scene_necessity,
            "visual_note_count": len(visual_notes),
        }


def _run_smoke_test() -> None:
    from content_brain.engines.story_architecture_engine import StoryArchitectureEngine
    from content_brain.engines.video_format_planner import VideoFormatPlanner
    from content_brain.profiles.profile_loader import ProfileLoader
    from content_brain.schemas.content_brief import Platform

    loader = ProfileLoader()
    profile = loader.resolve(niche="football")
    trend = TrendSignal(
        topic="VAR offside line decision in the 89th minute changed the result",
        velocity=82.0,
        saturation=30.0,
        virality_score=80.0,
        platform=Platform.TIKTOK,
        source="smoke_test",
    )

    from content_brain.engines.hook_engineering_engine import HookEngineeringEngine

    hook_engine = HookEngineeringEngine()
    hook_package = hook_engine.generate_hook_package(
        profile=profile,
        topic=trend.topic,
        platforms=[Platform.TIKTOK],
    )

    story_engine = StoryArchitectureEngine()
    story_blueprint = story_engine.build_blueprint(profile, trend, hook_package)

    format_planner = VideoFormatPlanner()
    format_plan = format_planner.plan(
        profile=profile,
        platform=Platform.TIKTOK,
        user_duration_seconds=30,
        provider_name="hailuo",
    )

    engine = StoryIntelligenceEngine()
    result = engine.enhance(
        profile=profile,
        trend_signal=trend,
        hook_package=hook_package,
        story_blueprint=story_blueprint,
        video_format_plan=format_plan,
    )

    blueprint = result["story_blueprint"]
    print("\n" + "=" * 72)
    print("STORY INTELLIGENCE ENGINE SMOKE TEST")
    print("=" * 72)
    print("ENGINE:", result["engine_version"])
    print("STORY SIGNATURE:", result["story_signature"])
    print("REPEATED RISK:", result["repeated_risk_score"])
    print("\nNARRATIVE PREMISE:")
    print(blueprint["narrative_premise"])
    print("\nQUALITY SCORE:")
    print(json.dumps(blueprint["story_quality_score"], indent=2))
    print("\nSCENE PLAN (first 2):")
    for scene in blueprint["scene_plan"][:2]:
        print(json.dumps(scene, indent=2))
    print("\nDIRECTOR SHOTS (first 2):")
    for shot in blueprint["director_shots"][:2]:
        print(json.dumps(shot, indent=2))
    print("\nSCHEMA DIRECTOR SHOTS VALID:",
          all(DirectorShot.from_dict(item).validate().is_valid
              for item in result["schema_director_shots"]))
    print("SCENE COUNT:", len(blueprint["scene_plan"]))
    print("COMPOSITE SCORE:", blueprint["story_quality_score"]["composite"])


if __name__ == "__main__":
    _run_smoke_test()
