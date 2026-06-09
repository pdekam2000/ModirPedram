"""
Title + Thumbnail Engine V1 for the Viral Content Brain.

Generates CTR-focused packaging concepts after the decision gate.
Rule-based only in V1 (no LLM, no external APIs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    HookPackage,
    Platform,
    StoryBlueprint,
    TrendSignal,
)

try:
    from content_brain.engines.content_decision_engine import (
        ContentDecision,
        DecisionPackage,
    )
except ImportError as exc:  # pragma: no cover - defensive fallback
    raise ImportError(
        "TitleThumbnailEngine requires content_brain.engines.content_decision_engine."
    ) from exc

CLICKBAIT_SPAM_TERMS = {
    "you won't believe",
    "shocking",
    "insane",
    "gone wrong",
    "100%",
    "free money",
}

TITLE_NOUN_STOPWORDS = {
    "concrete",
    "specific",
    "story",
    "detail",
    "sensory",
    "anchor",
    "topic",
    "about",
    "this",
    "that",
    "with",
    "from",
    "your",
    "what",
    "when",
    "where",
    "everyone",
    "nobody",
    "actually",
    "really",
    "tied",
    "frame",
    "one",
}

DEFAULT_TITLE_MAX_CHARACTERS = 80


@dataclass
class ThumbnailConcept:
    concept_id: str
    focal_subject: str
    visual_prompt: str
    tension_element: str
    composition_note: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "focal_subject": self.focal_subject,
            "visual_prompt": self.visual_prompt,
            "tension_element": self.tension_element,
            "composition_note": self.composition_note,
            "score": round(self.score, 2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThumbnailConcept:
        return cls(
            concept_id=str(data.get("concept_id", "")),
            focal_subject=str(data.get("focal_subject", "")),
            visual_prompt=str(data.get("visual_prompt", "")),
            tension_element=str(data.get("tension_element", "")),
            composition_note=str(data.get("composition_note", "")),
            score=float(data.get("score", 0.0)),
        )


@dataclass
class TitleThumbnailPackage:
    titles: list[str] = field(default_factory=list)
    thumbnail_concepts: list[dict[str, Any]] = field(default_factory=list)
    thumbnail_text_options: list[str] = field(default_factory=list)
    ctr_hooks: list[str] = field(default_factory=list)
    curiosity_gaps: list[str] = field(default_factory=list)
    emotional_triggers: list[str] = field(default_factory=list)
    packaging_style: str = ""
    platform_optimized: dict[str, Any] = field(default_factory=dict)
    recommended_title: str = ""
    recommended_thumbnail_concept: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "titles": list(self.titles),
            "thumbnail_concepts": list(self.thumbnail_concepts),
            "thumbnail_text_options": list(self.thumbnail_text_options),
            "ctr_hooks": list(self.ctr_hooks),
            "curiosity_gaps": list(self.curiosity_gaps),
            "emotional_triggers": list(self.emotional_triggers),
            "packaging_style": self.packaging_style,
            "platform_optimized": dict(self.platform_optimized),
            "recommended_title": self.recommended_title,
            "recommended_thumbnail_concept": dict(self.recommended_thumbnail_concept),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TitleThumbnailPackage:
        if not isinstance(data, dict):
            raise ValueError("TitleThumbnailPackage.from_dict() expects a dict.")

        return cls(
            titles=list(data.get("titles", [])),
            thumbnail_concepts=list(data.get("thumbnail_concepts", [])),
            thumbnail_text_options=list(data.get("thumbnail_text_options", [])),
            ctr_hooks=list(data.get("ctr_hooks", [])),
            curiosity_gaps=list(data.get("curiosity_gaps", [])),
            emotional_triggers=list(data.get("emotional_triggers", [])),
            packaging_style=str(data.get("packaging_style", "")),
            platform_optimized=dict(data.get("platform_optimized", {})),
            recommended_title=str(data.get("recommended_title", "")),
            recommended_thumbnail_concept=dict(data.get("recommended_thumbnail_concept", {})),
            warnings=list(data.get("warnings", [])),
        )


@dataclass
class TitleThumbnailResult:
    package: TitleThumbnailPackage
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package.to_dict(),
            "reasoning": self.reasoning,
        }


class TitleThumbnailEngine:
    """
    Generate CTR-focused title and thumbnail packaging for an approved brief.

    Usage:
        engine = TitleThumbnailEngine()
        result = engine.generate(
            profile=profile,
            decision_package=decision_package,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
            trend_signal=trend_signal,
            platform=Platform.TIKTOK,
        )
    """

    THUMBNAIL_TEXT_MAX_WORDS = 6

    def generate(
        self,
        profile: dict[str, Any],
        decision_package: DecisionPackage,
        story_blueprint: StoryBlueprint,
        hook_package: HookPackage,
        trend_signal: TrendSignal,
        platform: Platform | str = Platform.TIKTOK,
    ) -> TitleThumbnailResult:
        resolved_platform = self._resolve_platform(platform)
        context = self._build_context(
            profile=profile,
            decision_package=decision_package,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
            trend_signal=trend_signal,
            platform=resolved_platform,
        )

        if decision_package.decision == ContentDecision.REJECT:
            package = self._build_rejected_package(context)
            return TitleThumbnailResult(
                package=package,
                reasoning="Packaging skipped because the brief was rejected.",
            )

        titles = self._generate_titles(context)
        thumbnail_concepts = self._generate_thumbnail_concepts(context)
        thumbnail_text_options = self._generate_thumbnail_text_options(context)
        ctr_hooks = self._generate_ctr_hooks(context)
        curiosity_gaps = self._generate_curiosity_gaps(context)
        emotional_triggers = self._generate_emotional_triggers(context)
        warnings = self._generate_warnings(context, titles, thumbnail_concepts)

        recommended_title = self._select_recommended_title(titles, context)
        recommended_concept = self._select_recommended_concept(thumbnail_concepts)

        package = TitleThumbnailPackage(
            titles=titles,
            thumbnail_concepts=[concept.to_dict() for concept in thumbnail_concepts],
            thumbnail_text_options=thumbnail_text_options,
            ctr_hooks=ctr_hooks,
            curiosity_gaps=curiosity_gaps,
            emotional_triggers=emotional_triggers,
            packaging_style=context["packaging_style"],
            platform_optimized=context["platform_optimized"],
            recommended_title=recommended_title,
            recommended_thumbnail_concept=(
                recommended_concept.to_dict() if recommended_concept else {}
            ),
            warnings=warnings,
        )

        reasoning = (
            f"Generated {len(titles)} titles and {len(thumbnail_concepts)} thumbnail concepts "
            f"for {context['niche']} on {resolved_platform.value} "
            f"with decision {decision_package.decision.value}."
        )
        return TitleThumbnailResult(package=package, reasoning=reasoning)

    def generate_package(
        self,
        profile: dict[str, Any],
        decision_package: DecisionPackage,
        story_blueprint: StoryBlueprint,
        hook_package: HookPackage,
        trend_signal: TrendSignal,
        platform: Platform | str = Platform.TIKTOK,
    ) -> TitleThumbnailPackage:
        return self.generate(
            profile=profile,
            decision_package=decision_package,
            story_blueprint=story_blueprint,
            hook_package=hook_package,
            trend_signal=trend_signal,
            platform=platform,
        ).package

    def _build_context(
        self,
        profile: dict[str, Any],
        decision_package: DecisionPackage,
        story_blueprint: StoryBlueprint,
        hook_package: HookPackage,
        trend_signal: TrendSignal,
        platform: Platform,
    ) -> dict[str, Any]:
        niche = str(profile.get("niche", "general"))
        niche_label = str(profile.get("niche_label", niche.replace("_", " ").title()))
        hook_text = hook_package.best_hook_text.strip()
        if not hook_text and hook_package.variants:
            hook_text = hook_package.variants[0].text

        packaging_rules = profile.get("seo_and_packaging", {})
        title_rules = packaging_rules.get("title_rules", {})
        thumbnail_rules = packaging_rules.get("thumbnail_psychology", {})
        platform_rules = profile.get("platform_rules", {}).get(platform.value, {})
        visual_dna = profile.get("visual_dna", {})

        concrete_noun = self._extract_concrete_noun(
            topic=trend_signal.topic,
            sensory_anchor=story_blueprint.sensory_anchor,
            hook_text=hook_text,
        )
        tension_phrase = self._extract_tension_phrase(
            hook_text=hook_text,
            reveal_type=story_blueprint.reveal_type,
            loop_seed=story_blueprint.loop_seed,
        )

        return {
            "profile": profile,
            "decision_package": decision_package,
            "story_blueprint": story_blueprint,
            "hook_package": hook_package,
            "trend_signal": trend_signal,
            "platform": platform,
            "niche": niche,
            "niche_label": niche_label,
            "topic": trend_signal.topic.strip(),
            "hook_text": hook_text,
            "loop_seed": story_blueprint.loop_seed.strip(),
            "reveal_type": story_blueprint.reveal_type.strip(),
            "sensory_anchor": story_blueprint.sensory_anchor.strip(),
            "concrete_noun": concrete_noun,
            "tension_phrase": tension_phrase,
            "title_rules": title_rules,
            "thumbnail_rules": thumbnail_rules,
            "platform_rules": platform_rules,
            "visual_dna": visual_dna,
            "packaging_style": self._resolve_packaging_style(profile, platform_rules),
            "platform_optimized": self._build_platform_optimized(
                platform,
                platform_rules,
                title_rules,
            ),
            "emotional_vector": dict(trend_signal.emotional_vector),
        }

    def _build_rejected_package(self, context: dict[str, Any]) -> TitleThumbnailPackage:
        return TitleThumbnailPackage(
            packaging_style=context["packaging_style"],
            platform_optimized=context["platform_optimized"],
            warnings=[
                "Packaging skipped: brief decision is REJECT.",
                "Resolve upstream scoring or uniqueness issues before generating titles.",
            ],
        )

    def _generate_titles(self, context: dict[str, Any]) -> list[str]:
        topic = context["topic"]
        noun = context["concrete_noun"]
        tension = context["tension_phrase"]
        hook_text = context["hook_text"]
        loop_seed = context["loop_seed"]
        platform = context["platform"]
        title_rules = context["title_rules"]
        max_chars = int(title_rules.get("max_characters", DEFAULT_TITLE_MAX_CHARACTERS))

        candidates = [
            self._trim_to_chars(topic, max_chars),
            f"{topic} — {tension.lower()}",
            f"{noun}: {tension}",
            self._trim_to_chars(hook_text.rstrip("."), max_chars),
            f"Why {noun} changes this story",
        ]

        if not self._topic_mentions_niche(context):
            candidates.append(
                f"The {noun} moment nobody finished explaining"
            )

        if loop_seed:
            candidates.append(self._trim_to_chars(loop_seed.rstrip("?") + "?", max_chars))

        if platform == Platform.YOUTUBE_SHORTS:
            candidates.append(
                self._trim_to_chars(
                    f"{noun} and the {context['reveal_type'].replace('_', ' ')}",
                    max_chars,
                )
            )
        elif platform == Platform.TIKTOK:
            candidates.append(self._trim_to_chars(f"POV: {tension}", max_chars))
        elif platform == Platform.INSTAGRAM_REELS:
            candidates.append(self._trim_to_chars(f"{noun} / {tension}", max_chars))

        for pattern in title_rules.get("preferred_patterns", []):
            rendered = self._render_title_pattern(pattern, context)
            if rendered:
                candidates.append(self._trim_to_chars(rendered, max_chars))

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            cleaned = re.sub(r"\s+", " ", candidate).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)

        scored = sorted(
            deduped,
            key=lambda title: self._score_title(title, context),
            reverse=True,
        )
        return scored[:6]

    def _generate_thumbnail_concepts(self, context: dict[str, Any]) -> list[ThumbnailConcept]:
        noun = context["concrete_noun"]
        anchor = context["sensory_anchor"] or noun
        hook_text = context["hook_text"]
        reveal_type = context["reveal_type"]
        visual_dna = context["visual_dna"]
        thumbnail_rules = context["thumbnail_rules"]

        palette = ", ".join(visual_dna.get("color_palette", [])[:3]) or "high-contrast mobile palette"
        camera_language = visual_dna.get("camera_language", {})
        if isinstance(camera_language, list):
            camera = camera_language[0] if camera_language else "close subject framing"
        elif isinstance(camera_language, dict):
            camera = camera_language.get("default_shot", "close subject framing")
        else:
            camera = "close subject framing"
        lighting = visual_dna.get("lighting_style") or visual_dna.get("lighting", "readable contrast on mobile")
        if isinstance(lighting, list):
            lighting = lighting[0] if lighting else "readable contrast on mobile"
        elif not isinstance(lighting, str):
            lighting = "readable contrast on mobile"
        must_show = ", ".join(thumbnail_rules.get("must_show", [])) or "clear focal subject"

        concepts = [
            ThumbnailConcept(
                concept_id="thumb_focal_tension",
                focal_subject=anchor,
                visual_prompt=(
                    f"{camera}; {lighting}; palette {palette}; "
                    f"focal subject {anchor}; incomplete detail visible but payoff hidden."
                ),
                tension_element=f"Hide the full {reveal_type.replace('_', ' ')} behind framing or shadow.",
                composition_note=f"Must show: {must_show}.",
            ),
            ThumbnailConcept(
                concept_id="thumb_object_interrupt",
                focal_subject=noun,
                visual_prompt=(
                    f"Single object-led frame featuring {noun}; "
                    f"mobile-readable contrast; motion or wrong detail in frame 0."
                ),
                tension_element="One precise wrong detail without revealing the final answer.",
                composition_note="Use object focus before context is explained.",
            ),
            ThumbnailConcept(
                concept_id="thumb_hook_overlay",
                focal_subject=hook_text[:48] or anchor,
                visual_prompt=(
                    f"Cover frame with {anchor} in background and bold overlay text zone; "
                    f"{lighting}; avoid full payoff reveal."
                ),
                tension_element="Text implies a missing piece the viewer must watch to resolve.",
                composition_note=context["platform_rules"].get(
                    "title_style",
                    "cover frame carries the hook",
                ),
            ),
        ]

        if context["loop_seed"]:
            concepts.append(
                ThumbnailConcept(
                    concept_id="thumb_loop_seed",
                    focal_subject=context["loop_seed"][:60],
                    visual_prompt=(
                        f"Unresolved question visual using {anchor}; "
                        f"leave one unanswered element on screen."
                    ),
                    tension_element=context["loop_seed"],
                    composition_note="Invite comments or rewatch without closing the loop.",
                )
            )

        for concept in concepts:
            concept.score = self._score_thumbnail_concept(concept, context)

        concepts.sort(key=lambda item: item.score, reverse=True)
        return concepts[:4]

    def _generate_thumbnail_text_options(self, context: dict[str, Any]) -> list[str]:
        noun = context["concrete_noun"]
        tension = context["tension_phrase"]
        hook_text = context["hook_text"]

        options = [
            self._short_thumbnail_text(noun.upper()),
            self._short_thumbnail_text(tension.upper()),
            self._short_thumbnail_text(hook_text),
            self._short_thumbnail_text(f"THE {noun.upper()}"),
            self._short_thumbnail_text(f"{noun.upper()}?!"),
        ]

        if context["loop_seed"]:
            options.append(self._short_thumbnail_text(context["loop_seed"]))

        deduped: list[str] = []
        seen: set[str] = set()
        for option in options:
            cleaned = re.sub(r"\s+", " ", option).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                deduped.append(cleaned)
        return deduped[:5]

    def _generate_ctr_hooks(self, context: dict[str, Any]) -> list[str]:
        hook_text = context["hook_text"]
        hooks = [
            hook_text,
            f"Stop scrolling — {context['concrete_noun']} is the part everyone missed.",
            (
                f"You saw the clip about {context['concrete_noun']}. "
                f"You didn't see {context['tension_phrase'].lower()}."
            ),
        ]

        if context["decision_package"].decision == ContentDecision.REVISE:
            hooks.append("Revised angle: same topic, sharper opening promise.")

        deduped: list[str] = []
        seen: set[str] = set()
        for hook in hooks:
            cleaned = hook.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                deduped.append(cleaned)
        return deduped[:4]

    def _generate_curiosity_gaps(self, context: dict[str, Any]) -> list[str]:
        gaps = [
            f"What actually caused {context['concrete_noun']}?",
            f"Why {context['tension_phrase'].lower()}?",
        ]
        if context["loop_seed"]:
            gaps.append(context["loop_seed"])
        if context["reveal_type"]:
            gaps.append(
                f"The {context['reveal_type'].replace('_', ' ')} is shown partially, not fully."
            )
        return gaps[:4]

    def _generate_emotional_triggers(self, context: dict[str, Any]) -> list[str]:
        triggers: list[str] = []
        for name, weight in sorted(
            context["emotional_vector"].items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            if weight >= 0.5:
                triggers.append(f"{name} ({weight:.2f})")

        if not triggers:
            triggers.extend(["curiosity", "tension"])

        if context["story_blueprint"].story_mode.value:
            triggers.append(context["story_blueprint"].story_mode.value.replace("_", " "))

        deduped: list[str] = []
        seen: set[str] = set()
        for trigger in triggers:
            key = trigger.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(trigger)
        return deduped[:5]

    def _generate_warnings(
        self,
        context: dict[str, Any],
        titles: list[str],
        concepts: list[ThumbnailConcept],
    ) -> list[str]:
        warnings: list[str] = []
        decision = context["decision_package"].decision

        if decision == ContentDecision.REGENERATE:
            warnings.append("Brief requires regeneration; packaging is provisional.")
        elif decision == ContentDecision.REVISE:
            targets = ", ".join(context["decision_package"].revision_targets) or "unspecified targets"
            warnings.append(f"Brief is under revision; revisit packaging after fixing: {targets}.")

        if not context["sensory_anchor"]:
            warnings.append("Missing sensory anchor; thumbnail focal subject may feel generic.")

        max_chars = int(context["title_rules"].get("max_characters", DEFAULT_TITLE_MAX_CHARACTERS))
        for title in titles:
            if len(title) > max_chars:
                warnings.append(
                    f"Title exceeds max length ({len(title)}>{max_chars}): {title[:40]}..."
                )
                break

        for title in titles:
            lower = title.lower()
            if any(term in lower for term in CLICKBAIT_SPAM_TERMS):
                warnings.append("One title pattern resembles spammy clickbait; review before publish.")
                break

        if concepts and concepts[0].score < 60:
            warnings.append("Top thumbnail concept scored low; consider a stronger focal subject.")

        must_avoid = context["thumbnail_rules"].get("must_avoid", [])
        if any("payoff reveal" in item.lower() for item in must_avoid):
            warnings.append("Do not reveal the full payoff in the thumbnail frame.")

        return warnings

    def _select_recommended_title(self, titles: list[str], context: dict[str, Any]) -> str:
        if not titles:
            return context["topic"]
        return titles[0]

    def _select_recommended_concept(
        self,
        concepts: list[ThumbnailConcept],
    ) -> Optional[ThumbnailConcept]:
        return concepts[0] if concepts else None

    def _score_title(self, title: str, context: dict[str, Any]) -> float:
        score = 50.0
        lower = title.lower()
        max_chars = int(context["title_rules"].get("max_characters", DEFAULT_TITLE_MAX_CHARACTERS))
        topic = context["topic"].lower()
        topic_tokens = [
            token
            for token in re.split(r"\s+", topic)
            if len(token.strip(".,!?;:'\"")) >= 4
        ]

        if topic and topic in lower:
            score += 18.0
        elif any(token in lower for token in topic_tokens[:4]):
            score += 12.0

        if context["concrete_noun"].lower() in lower:
            score += 15.0
        if "?" in title:
            score += 8.0
        if len(title) <= max_chars:
            score += 10.0
        else:
            score -= 20.0
        if any(term in lower for term in CLICKBAIT_SPAM_TERMS):
            score -= 25.0
        if title == context["hook_text"]:
            score += 5.0
        if context["platform"].value == "youtube_shorts" and context["concrete_noun"].lower() in lower:
            score += 6.0

        niche_label = context["niche_label"].lower()
        if niche_label and niche_label in lower and not self._topic_mentions_niche(context):
            score -= 12.0

        return round(score, 2)

    def _topic_mentions_niche(self, context: dict[str, Any]) -> bool:
        topic = context["topic"].lower()
        niche = context["niche"].lower().replace("_", " ")
        niche_label = context["niche_label"].lower()

        if niche and niche in topic:
            return True
        if niche_label and niche_label in topic:
            return True

        label_tokens = [
            token
            for token in re.split(r"\s+", niche_label)
            if len(token) >= 4
        ]
        return any(token in topic for token in label_tokens)

    def _score_thumbnail_concept(
        self,
        concept: ThumbnailConcept,
        context: dict[str, Any],
    ) -> float:
        score = 55.0
        anchor = context["sensory_anchor"].lower()
        if anchor and anchor in concept.visual_prompt.lower():
            score += 12.0
        if context["concrete_noun"].lower() in concept.focal_subject.lower():
            score += 10.0
        if "payoff hidden" in concept.visual_prompt.lower() or "without revealing" in concept.tension_element.lower():
            score += 8.0
        if concept.concept_id == "thumb_hook_overlay" and context["platform"] == Platform.INSTAGRAM_REELS:
            score += 6.0
        return round(min(100.0, score), 2)

    def _render_title_pattern(self, pattern: str, context: dict[str, Any]) -> str:
        replacements = {
            "[specific subject]": context["concrete_noun"],
            "[specific object/place]": context["concrete_noun"],
            "[result or tension]": context["tension_phrase"],
            "[niche problem]": f"{context['concrete_noun']} problem",
            "[promise]": f"what happened to {context['concrete_noun']}",
            "[before state]": f"before {context['concrete_noun']}",
            "[after state]": context["tension_phrase"],
            "[time]": "this moment",
            "[personal threat]": context["tension_phrase"],
            "[relationship role]": "viewer",
            "[missing/ changed detail]": context["tension_phrase"],
            "[wrong detail]": context["tension_phrase"],
        }
        rendered = pattern
        for key, value in replacements.items():
            rendered = rendered.replace(key, value)
        if "[" in rendered and "]" in rendered:
            return ""
        return rendered

    def _extract_concrete_noun(
        self,
        topic: str,
        sensory_anchor: str,
        hook_text: str,
    ) -> str:
        for source in (topic, sensory_anchor, hook_text, topic):
            tokens = [
                token.strip(".,!?;:'\"")
                for token in re.split(r"\s+", source)
                if len(token.strip(".,!?;:'\"")) >= 4
                and token.strip(".,!?;:'\"").lower() not in TITLE_NOUN_STOPWORDS
            ]
            if tokens:
                return max(tokens, key=len)
        anchors = [
            token
            for token in re.findall(r"[\w\u0600-\u06FF]+", topic, flags=re.UNICODE)
            if len(token) >= 3 and token.lower() not in TITLE_NOUN_STOPWORDS
        ]
        if anchors:
            return max(anchors, key=len)
        return "story"

    def _extract_tension_phrase(
        self,
        hook_text: str,
        reveal_type: str,
        loop_seed: str,
    ) -> str:
        if loop_seed:
            return loop_seed.rstrip("?")
        if hook_text:
            parts = re.split(r"[.!?]", hook_text)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
            return hook_text.strip()
        return reveal_type.replace("_", " ")

    def _resolve_packaging_style(
        self,
        profile: dict[str, Any],
        platform_rules: dict[str, Any],
    ) -> str:
        tone = profile.get("tone_rules", {}).get("primary_tone", "native short-form")
        title_style = platform_rules.get("title_style", "curiosity-first packaging")
        return f"{tone}; {title_style}"

    def _build_platform_optimized(
        self,
        platform: Platform,
        platform_rules: dict[str, Any],
        title_rules: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "platform": platform.value,
            "display_name": platform_rules.get("display_name", platform.value),
            "title_style": platform_rules.get("title_style", ""),
            "caption_style": platform_rules.get("caption_style", ""),
            "cta_style": platform_rules.get("cta_style", ""),
            "title_max_characters": int(title_rules.get("max_characters", DEFAULT_TITLE_MAX_CHARACTERS)),
            "hook_window_seconds": platform_rules.get("hook_window_seconds"),
            "hashtag_count": platform_rules.get("hashtag_count", {}),
        }

    def _short_thumbnail_text(self, text: str) -> str:
        words = re.sub(r"\s+", " ", text).strip().split()
        if not words:
            return ""
        shortened = " ".join(words[: self.THUMBNAIL_TEXT_MAX_WORDS])
        return shortened.upper()

    def _trim_to_chars(self, text: str, max_chars: int) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 1].rstrip() + "..."

    def _resolve_platform(self, platform: Platform | str) -> Platform:
        if isinstance(platform, Platform):
            return platform
        return Platform(str(platform))


__all__ = [
    "ThumbnailConcept",
    "TitleThumbnailEngine",
    "TitleThumbnailPackage",
    "TitleThumbnailResult",
]


if __name__ == "__main__":
    import json
    import tempfile
    from pathlib import Path

    from content_brain.engines.content_decision_engine import DecisionPackage
    from content_brain.orchestrators.content_brief_orchestrator import (
        ContentBriefOrchestrator,
        ContentBriefRunRequest,
    )
    from content_brain.schemas.content_brief import Platform

    engine = TitleThumbnailEngine()

    cases = [
        ContentBriefRunRequest(
            niche="football",
            topic="the replay angle nobody checked",
            platform=Platform.TIKTOK,
            user_duration_seconds=30,
            provider_name="hailuo",
            provider_clip_duration_seconds=6,
            record_uniqueness_on_success=False,
        ),
        ContentBriefRunRequest(
            niche="perfume",
            topic="the airport scent everyone asked about",
            platform=Platform.INSTAGRAM_REELS,
            user_duration_seconds=30,
            provider_name="hailuo",
            provider_clip_duration_seconds=8,
            record_uniqueness_on_success=False,
        ),
        ContentBriefRunRequest(
            niche="dark_mystery",
            topic="the room missing from the blueprint",
            platform=Platform.YOUTUBE_SHORTS,
            user_duration_seconds=45,
            provider_name="runway",
            provider_clip_duration_seconds=10,
            record_uniqueness_on_success=False,
        ),
    ]

    last_brief = None
    with tempfile.TemporaryDirectory() as tmp_dir:
        orchestrator = ContentBriefOrchestrator(
            project_root=".",
            memory_path=Path(tmp_dir) / "content_history.json",
        )

        for request in cases:
            brief = orchestrator.run(request)
            last_brief = brief
            packaging = engine.generate(
                profile=brief.profile,
                decision_package=brief.decision_package,
                story_blueprint=brief.story_blueprint,
                hook_package=brief.hook_package,
                trend_signal=brief.trend_signal,
                platform=request.platform,
            )

            payload = packaging.package.to_dict()
            roundtrip = TitleThumbnailPackage.from_dict(payload)

            print("\n" + "=" * 72)
            print(
                f"{request.niche.upper()} | decision={brief.decision_package.decision.value} | "
                f"titles={len(payload['titles'])} | concepts={len(payload['thumbnail_concepts'])}"
            )
            print("RECOMMENDED TITLE:", payload["recommended_title"])
            print(
                "RECOMMENDED CONCEPT:",
                payload["recommended_thumbnail_concept"].get("concept_id", "none"),
            )
            print("CTR HOOKS:", " | ".join(payload["ctr_hooks"][:2]))
            print("WARNINGS:", "; ".join(payload["warnings"]) or "none")
            print("JSON OK:", json.dumps(payload)[:140] + "...")
            print("ROUNDTRIP:", roundtrip.recommended_title[:48])

    print("\n" + "=" * 72)
    print("REJECTED BRIEF PACKAGING CHECK")
    if last_brief is not None:
        rejected = engine.generate_package(
            profile={"niche": "general", "seo_and_packaging": {}, "platform_rules": {}},
            decision_package=DecisionPackage(
                decision=ContentDecision.REJECT,
                confidence=0.9,
                reasons=["Composite score too low."],
                production_ready=False,
            ),
            story_blueprint=last_brief.story_blueprint,
            hook_package=last_brief.hook_package,
            trend_signal=last_brief.trend_signal,
        )
        print("WARNINGS:", "; ".join(rejected.warnings))
