"""
Generic Hook Engineering Engine for the Viral Content Brain.

Generates and scores hook variants from any resolved ProfileLoader profile.
Returns schema-compatible HookPackage objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional

from content_brain.schemas.content_brief import (
    HookClass,
    HookPackage,
    HookVariant,
    Platform,
)


@dataclass
class HookScoreBreakdown:
    curiosity_gap: float = 0.0
    emotional_spike: float = 0.0
    specificity: float = 0.0
    niche_fit: float = 0.0
    platform_fit: float = 0.0
    non_generic_score: float = 0.0
    composite: float = 0.0

    def to_emotional_vector(self) -> dict[str, float]:
        return {
            "curiosity_gap": round(self.curiosity_gap, 2),
            "emotional_spike": round(self.emotional_spike, 2),
            "niche_fit": round(self.niche_fit, 2),
            "platform_fit": round(self.platform_fit, 2),
            "non_generic_score": round(self.non_generic_score, 2),
            "composite": round(self.composite, 2),
        }


@dataclass
class HookCandidate:
    variant_id: str
    hook_class: HookClass
    text: str
    scores: HookScoreBreakdown
    reasoning: str
    platform_fit: dict[str, float] = field(default_factory=dict)
    rejected: bool = False
    rejection_reason: str = ""

    def to_hook_variant(self) -> HookVariant:
        return HookVariant(
            variant_id=self.variant_id,
            hook_class=self.hook_class,
            text=self.text,
            curiosity_gap_score=self.scores.curiosity_gap,
            interrupt_power=self.scores.emotional_spike,
            specificity_score=self.scores.specificity,
            emotional_vector=self.scores.to_emotional_vector(),
        )


@dataclass
class HookGenerationResult:
    package: HookPackage
    candidates: list[HookCandidate]
    rejected_candidates: list[HookCandidate]

    def get_analysis(self, variant_id: str) -> Optional[HookCandidate]:
        for candidate in self.candidates + self.rejected_candidates:
            if candidate.variant_id == variant_id:
                return candidate
        return None


class HookEngineeringEngine:
    """
    Profile-driven hook generator and scorer.

    Usage:
        engine = HookEngineeringEngine()
        result = engine.generate(profile, topic="...", platforms=[Platform.TIKTOK])
        package = result.package
    """

    COMPOSITE_WEIGHTS = {
        "curiosity_gap": 0.22,
        "emotional_spike": 0.18,
        "specificity": 0.18,
        "niche_fit": 0.18,
        "platform_fit": 0.12,
        "non_generic_score": 0.12,
    }

    VAGUE_WORDS = {
        "something",
        "someone",
        "anything",
        "everything",
        "very",
        "really",
        "stuff",
        "things",
        "interesting",
        "amazing",
        "incredible",
    }

    URGENCY_WORDS = {
        "tonight",
        "today",
        "now",
        "before",
        "stop",
        "never",
        "always",
        "secret",
        "hidden",
        "wrong",
    }

    OPEN_LOOP_MARKERS = {
        "but",
        "until",
        "except",
        "what",
        "why",
        "how",
        "who",
        "?",
        "…",
    }

    GLOBAL_SAFETY_BANNED = [
        "guaranteed cure",
        "guaranteed to work",
        "100% guaranteed",
        "doctors hate",
        "miracle cure",
        "instant cure",
        "you will die if",
        "kill yourself",
        "harm yourself",
        "stop taking your medication",
        "ignore your doctor",
        "fake news proof",
        "election was stolen proof",
        "classified leak proof",
    ]

    GLOBAL_CLICKBAIT_LIES = [
        "you won't believe",
        "shocked the world",
        "what happened next",
        "this one trick",
        "they don't want you to know",
        "banned video",
        "forbidden technique",
    ]

    TEMPLATE_BANK: dict[HookClass, list[str]] = {
        HookClass.VIOLATION: [
            "{topic} broke the one rule every {niche_label} audience assumed was fixed.",
            "Everyone in {niche_label} does this first — {topic} proves that habit fails.",
            "This {niche_label} moment looks normal until {detail} violates the setup.",
        ],
        HookClass.INCOMPLETE_TRUTH: [
            "Everyone saw {detail}. Nobody checked {missing_detail}.",
            "{topic} looked solved on the surface — the second detail changes everything.",
            "The clip shows {detail}, but it cuts before {missing_detail}.",
        ],
        HookClass.PERSONAL_THREAT: [
            "If you care about {niche_label}, check this before your next {routine}.",
            "This {niche_label} mistake is common — {topic} shows why it catches people off guard.",
            "You might be doing this in {niche_label} already — {topic} is the warning sign.",
        ],
        HookClass.MORAL_DISCOMFORT: [
            "{topic} worked — and that is exactly why it feels wrong in {niche_label}.",
            "The {niche_label} choice looked smart until {detail} exposed the cost.",
            "They won in {niche_label} by doing {detail}, and the result is hard to defend.",
        ],
        HookClass.FALSE_SAFETY: [
            "Everything about {topic} looked fine until {detail} appeared in frame.",
            "It started as a normal {niche_label} routine — then {detail} broke the pattern.",
            "The setup feels safe for {niche_label} viewers until one small detail turns.",
        ],
        HookClass.OPEN_LOOP_SEED: [
            "{topic} ends with one question nobody in {niche_label} can ignore.",
            "Watch {detail} closely — the last second of {topic} does not match the opening.",
            "{topic} starts with an answer, then removes the one detail that makes it true.",
        ],
    }

    NICHE_DETAIL_HINTS: dict[str, dict[str, str]] = {
        "football": {
            "detail": "the replay angle in the 89th minute",
            "missing_detail": "the offside line on the wide camera",
            "routine": "matchday watch",
        },
        "perfume": {
            "detail": "the dry-down note after twenty minutes",
            "missing_detail": "how the scent shifts on skin versus paper",
            "routine": "scent test",
        },
        "music": {
            "detail": "the bridge before the final chorus",
            "missing_detail": "the muted layer under the hook",
            "routine": "release listen",
        },
        "education": {
            "detail": "the one step students skip in the solution",
            "missing_detail": "the assumption hidden in the question",
            "routine": "study session",
        },
        "selfcare": {
            "detail": "the ingredient order in step two",
            "missing_detail": "what happens after ten minutes on skin",
            "routine": "night routine",
        },
        "comedy": {
            "detail": "the pause before the punchline",
            "missing_detail": "the setup line everyone misremembers",
            "routine": "bit rehearsal",
        },
        "news": {
            "detail": "the timestamp on the first report",
            "missing_detail": "the correction posted three hours later",
            "routine": "headline scan",
        },
        "dark_mystery": {
            "detail": "the hallway light flickering once",
            "missing_detail": "the door that opens the wrong way",
            "routine": "night watch",
        },
        "horror": {
            "detail": "the hallway light flickering once",
            "missing_detail": "the door that opens the wrong way",
            "routine": "night watch",
        },
    }

    def generate(
        self,
        profile: dict[str, Any],
        topic: str,
        platforms: Optional[list[Platform | str]] = None,
        max_variants: Optional[int] = None,
    ) -> HookGenerationResult:
        context = self._build_context(profile, topic, platforms)
        enabled_classes = self._enabled_hook_classes(profile)

        candidates: list[HookCandidate] = []
        rejected: list[HookCandidate] = []

        for index, hook_class in enumerate(enabled_classes, start=1):
            texts = self._generate_texts_for_class(hook_class, context)
            for sub_index, text in enumerate(texts, start=1):
                variant_id = f"hook_{index}_{hook_class.value}_{sub_index}"
                candidate = self._evaluate_candidate(
                    variant_id=variant_id,
                    hook_class=hook_class,
                    text=text,
                    context=context,
                    profile=profile,
                )
                if candidate.rejected:
                    rejected.append(candidate)
                else:
                    candidates.append(candidate)

        candidates.sort(key=lambda item: item.scores.composite, reverse=True)

        minimums = profile.get("hook_rules", {}).get("minimum_scores", {})
        min_composite = float(minimums.get("composite_hook_score", 65))
        passing = [
            candidate
            for candidate in candidates
            if candidate.scores.composite >= min_composite
        ]

        if not passing:
            passing = candidates[: max(1, min(3, len(candidates)))]

        if max_variants is not None:
            passing = passing[:max_variants]
        else:
            passing = passing[: max(3, min(len(passing), len(enabled_classes)))]

        package = self._build_package(passing, profile)
        return HookGenerationResult(
            package=package,
            candidates=passing,
            rejected_candidates=rejected,
        )

    def generate_hook_package(
        self,
        profile: dict[str, Any],
        topic: str,
        platforms: Optional[list[Platform | str]] = None,
        max_variants: Optional[int] = None,
    ) -> HookPackage:
        return self.generate(
            profile=profile,
            topic=topic,
            platforms=platforms,
            max_variants=max_variants,
        ).package

    def _build_context(
        self,
        profile: dict[str, Any],
        topic: str,
        platforms: Optional[list[Platform | str]],
    ) -> dict[str, Any]:
        niche = str(profile.get("niche", "general"))
        niche_label = str(profile.get("niche_label", niche.replace("_", " ").title()))
        language = profile.get("language_rules", {}).get("output_language", "English")

        resolved_platforms = self._resolve_platforms(profile, platforms)
        hints = self.NICHE_DETAIL_HINTS.get(niche, {})
        topic_clean = topic.strip() or f"a {niche_label} moment worth stopping for"

        return {
            "profile": profile,
            "topic": topic_clean,
            "niche": niche,
            "niche_label": niche_label,
            "language": language,
            "platforms": resolved_platforms,
            "detail": hints.get("detail", f"one concrete {niche_label.lower()} detail"),
            "missing_detail": hints.get(
                "missing_detail",
                f"the part most {niche_label.lower()} viewers skip",
            ),
            "routine": hints.get("routine", "session"),
            "tone_targets": profile.get("tone_rules", {}).get("emotional_targets", []),
            "must_include_one_of": profile.get("hook_rules", {}).get(
                "must_include_one_of",
                [],
            ),
        }

    def _enabled_hook_classes(self, profile: dict[str, Any]) -> list[HookClass]:
        hook_rules = profile.get("hook_rules", {})
        enabled = hook_rules.get("enabled_hook_classes", [])
        classes: list[HookClass] = []

        for value in enabled:
            try:
                classes.append(HookClass(value))
            except ValueError:
                continue

        if classes:
            return classes

        return list(HookClass)

    def _generate_texts_for_class(
        self,
        hook_class: HookClass,
        context: dict[str, Any],
    ) -> list[str]:
        templates = self.TEMPLATE_BANK.get(hook_class, [])
        if not templates:
            return []

        rendered: list[str] = []
        for template in templates[:2]:
            text = template.format(
                topic=context["topic"],
                niche_label=context["niche_label"],
                detail=context["detail"],
                missing_detail=context["missing_detail"],
                routine=context["routine"],
            )
            rendered.append(self._normalize_text(text, context))

        return rendered

    def _normalize_text(self, text: str, context: dict[str, Any]) -> str:
        cleaned = re.sub(r"\s+", " ", text.strip())
        max_words = int(
            context["profile"]
            .get("hook_rules", {})
            .get("hook_length", {})
            .get("max_words", 22)
        )
        words = cleaned.split()
        if len(words) > max_words:
            cleaned = " ".join(words[:max_words])
            if not cleaned.endswith((".", "?", "…")):
                cleaned += "…"
        return cleaned

    def _evaluate_candidate(
        self,
        variant_id: str,
        hook_class: HookClass,
        text: str,
        context: dict[str, Any],
        profile: dict[str, Any],
    ) -> HookCandidate:
        safety = self._safety_check(text, profile)
        if not safety["passed"]:
            return HookCandidate(
                variant_id=variant_id,
                hook_class=hook_class,
                text=text,
                scores=HookScoreBreakdown(),
                reasoning=safety["reason"],
                rejected=True,
                rejection_reason=safety["reason"],
            )

        scores = self._score_hook(text, hook_class, context, profile)
        platform_fit = self._score_platform_fit_map(text, context)

        reasoning = self._build_reasoning(
            hook_class=hook_class,
            text=text,
            scores=scores,
            platform_fit=platform_fit,
            context=context,
        )

        return HookCandidate(
            variant_id=variant_id,
            hook_class=hook_class,
            text=text,
            scores=scores,
            reasoning=reasoning,
            platform_fit=platform_fit,
        )

    def _score_hook(
        self,
        text: str,
        hook_class: HookClass,
        context: dict[str, Any],
        profile: dict[str, Any],
    ) -> HookScoreBreakdown:
        breakdown = HookScoreBreakdown(
            curiosity_gap=self._score_curiosity_gap(text, hook_class),
            emotional_spike=self._score_emotional_spike(text, context),
            specificity=self._score_specificity(text, context),
            niche_fit=self._score_niche_fit(text, context),
            platform_fit=self._score_platform_fit_average(text, context),
            non_generic_score=self._score_non_generic(text, profile),
        )
        breakdown.composite = self._composite_score(breakdown)
        return breakdown

    def _composite_score(self, breakdown: HookScoreBreakdown) -> float:
        total = 0.0
        for key, weight in self.COMPOSITE_WEIGHTS.items():
            total += getattr(breakdown, key) * weight
        return round(min(100.0, max(0.0, total)), 2)

    def _score_curiosity_gap(self, text: str, hook_class: HookClass) -> float:
        score = 55.0
        lower = text.lower()

        if "?" in text:
            score += 12.0
        if any(marker in lower for marker in self.OPEN_LOOP_MARKERS):
            score += 8.0
        if "—" in text or "..." in text or "…" in text:
            score += 5.0

        class_bonus = {
            HookClass.INCOMPLETE_TRUTH: 12.0,
            HookClass.OPEN_LOOP_SEED: 14.0,
            HookClass.VIOLATION: 8.0,
            HookClass.FALSE_SAFETY: 6.0,
            HookClass.PERSONAL_THREAT: 5.0,
            HookClass.MORAL_DISCOMFORT: 4.0,
        }
        score += class_bonus.get(hook_class, 0.0)
        return round(min(100.0, score), 2)

    def _score_emotional_spike(self, text: str, context: dict[str, Any]) -> float:
        score = 50.0
        lower = text.lower()

        if re.search(r"\byou\b|\byour\b", lower):
            score += 10.0
        if any(word in lower for word in self.URGENCY_WORDS):
            score += 8.0

        for target in context.get("tone_targets", []):
            token = str(target).lower()
            if token and token in lower:
                score += 4.0

        if "wrong" in lower or "warning" in lower or "ignore" in lower:
            score += 6.0

        return round(min(100.0, score), 2)

    def _score_specificity(self, text: str, context: dict[str, Any]) -> float:
        score = 45.0
        words = text.split()
        lower_words = [word.lower().strip(".,!?;:") for word in words]

        if re.search(r"\b\d+\b", text):
            score += 12.0
        if any(word[:1].isupper() for word in words[1:]):
            score += 8.0

        topic_tokens = set(re.findall(r"[a-zA-Z']+", context["topic"].lower()))
        overlap = topic_tokens.intersection(set(lower_words))
        score += min(15.0, len(overlap) * 5.0)

        vague_hits = sum(1 for word in lower_words if word in self.VAGUE_WORDS)
        score -= vague_hits * 6.0

        if self._includes_required_anchor(text, context):
            score += 10.0

        return round(min(100.0, max(0.0, score)), 2)

    def _score_niche_fit(self, text: str, context: dict[str, Any]) -> float:
        score = 52.0
        lower = text.lower()
        niche_label = context["niche_label"].lower()
        niche = context["niche"].lower()

        if niche_label and niche_label in lower:
            score += 18.0
        elif niche != "general" and niche in lower:
            score += 12.0

        if self._includes_required_anchor(text, context):
            score += 12.0
        elif context.get("must_include_one_of"):
            score += 4.0

        tone_must = context["profile"].get("tone_rules", {}).get("must_include", [])
        tone_hits = sum(
            1
            for rule in tone_must
            if any(token in lower for token in re.findall(r"[a-zA-Z']+", rule.lower())[:3])
        )
        score += min(10.0, tone_hits * 3.0)

        return round(min(100.0, score), 2)

    def _score_platform_fit_average(self, text: str, context: dict[str, Any]) -> float:
        fit_map = self._score_platform_fit_map(text, context)
        if not fit_map:
            return 60.0
        return round(sum(fit_map.values()) / len(fit_map), 2)

    def _score_platform_fit_map(
        self,
        text: str,
        context: dict[str, Any],
    ) -> dict[str, float]:
        profile = context["profile"]
        platform_rules = profile.get("platform_rules", {})
        word_count = len(text.split())
        fit: dict[str, float] = {}

        for platform in context["platforms"]:
            platform_key = platform.value if isinstance(platform, Platform) else str(platform)
            rules = platform_rules.get(platform_key, {})
            score = 70.0

            hook_window = float(rules.get("hook_window_seconds", 2.0))
            if word_count <= 18:
                score += 8.0
            if word_count <= 14 and hook_window <= 1.5:
                score += 8.0
            if word_count > 22:
                score -= 12.0

            caption_style = str(rules.get("caption_style", "")).lower()
            if "cryptic" in caption_style and ("?" in text or "…" in text):
                score += 4.0
            if "searchable" in caption_style and any(ch.isdigit() for ch in text):
                score += 4.0
            if "minimal" in caption_style and word_count <= 16:
                score += 4.0

            pacing_note = str(rules.get("pacing_note", "")).lower()
            if "frame 0" in pacing_note and word_count <= 18:
                score += 3.0

            fit[platform_key] = round(min(100.0, max(0.0, score)), 2)

        return fit

    def _score_non_generic(self, text: str, profile: dict[str, Any]) -> float:
        score = 78.0
        lower = text.lower()
        banned = profile.get("banned_generic_patterns", {})

        for phrase in banned.get("banned_phrases", []):
            if phrase.lower() in lower:
                score -= 25.0

        for pattern in banned.get("ai_tell_patterns", []):
            tokens = re.findall(r"[a-zA-Z']+", pattern.lower())[:4]
            if tokens and all(token in lower for token in tokens[:2]):
                score -= 10.0

        for phrase in self.GLOBAL_CLICKBAIT_LIES:
            if phrase in lower:
                score -= 20.0

        originality_signals = banned.get("required_originality_signals", [])
        if originality_signals:
            hits = 0
            if _contains_concrete_detail(lower):
                hits += 1
            if re.search(r"\b\d+\b", text):
                hits += 1
            if len(text.split()) >= 10:
                hits += 1
            score += min(12.0, hits * 4.0)

        return round(min(100.0, max(0.0, score)), 2)

    def _safety_check(self, text: str, profile: dict[str, Any]) -> dict[str, Any]:
        lower = text.lower()

        for phrase in self.GLOBAL_SAFETY_BANNED:
            if phrase in lower:
                return {
                    "passed": False,
                    "reason": f"Blocked dangerous or misleading hook language: '{phrase}'.",
                }

        for phrase in profile.get("banned_generic_patterns", {}).get("banned_phrases", []):
            if phrase.lower() in lower:
                return {
                    "passed": False,
                    "reason": f"Blocked banned generic phrase: '{phrase}'.",
                }

        for phrase in self.GLOBAL_CLICKBAIT_LIES:
            if phrase in lower:
                return {
                    "passed": False,
                    "reason": f"Blocked clickbait lie pattern: '{phrase}'.",
                }

        if self._looks_like_false_medical_claim(lower):
            return {
                "passed": False,
                "reason": "Blocked potential medical misinformation hook.",
            }

        return {"passed": True, "reason": ""}

    def _looks_like_false_medical_claim(self, lower_text: str) -> bool:
        medical_terms = ("cure", "treat", "diagnose", "medicine", "doctor", "cancer", "diabetes")
        claim_terms = ("guaranteed", "instant", "100%", "always works", "replace your")
        has_medical = any(term in lower_text for term in medical_terms)
        has_claim = any(term in lower_text for term in claim_terms)
        return has_medical and has_claim

    def _includes_required_anchor(self, text: str, context: dict[str, Any]) -> bool:
        lower = text.lower()
        anchors = context.get("must_include_one_of", [])

        anchor_patterns = {
            "specific time": r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?\b|\b\d+\s*(minute|hour|second|day|week|month|year)s?\b",
            "specific object": r"\b(note|door|clip|photo|video|recording|screen|replay|scent|track|step|ball|goal|lesson|product|bottle)\b",
            "specific place detail": r"\b(room|hallway|field|stage|classroom|store|kitchen|studio|corridor|pitch|channel)\b",
            "specific relationship": r"\b(mother|father|brother|sister|coach|teacher|friend|neighbor|partner|teammate|fan)\b",
            "specific result": r"\b(result|score|grade|outcome|transformation|before|after|proof|evidence)\b",
            "specific sound": r"\b(whisper|knock|echo|silence|hum|ring|voice|sound|beat|note)\b",
        }

        for anchor in anchors:
            pattern = anchor_patterns.get(anchor.lower())
            if pattern and re.search(pattern, lower):
                return True

        return False

    def _build_reasoning(
        self,
        hook_class: HookClass,
        text: str,
        scores: HookScoreBreakdown,
        platform_fit: dict[str, float],
        context: dict[str, Any],
    ) -> str:
        top_platform = max(platform_fit, key=platform_fit.get) if platform_fit else "general"
        return (
            f"{hook_class.value} hook for {context['niche_label']} using topic '{context['topic']}'. "
            f"Strongest dimensions: curiosity {scores.curiosity_gap}, specificity {scores.specificity}, "
            f"niche fit {scores.niche_fit}. Best platform fit: {top_platform} "
            f"({platform_fit.get(top_platform, scores.platform_fit)})."
        )

    def _build_package(
        self,
        candidates: list[HookCandidate],
        profile: dict[str, Any],
    ) -> HookPackage:
        del profile
        if not candidates:
            return HookPackage(variants=[], composite_score=0.0)

        variants = [candidate.to_hook_variant() for candidate in candidates]
        best = candidates[0]

        return HookPackage(
            variants=variants,
            selected_variant_id=best.variant_id,
            best_hook_text=best.text,
            hook_class=best.hook_class,
            composite_score=best.scores.composite,
        )

    def _resolve_platforms(
        self,
        profile: dict[str, Any],
        platforms: Optional[list[Platform | str]],
    ) -> list[Platform]:
        if platforms:
            resolved: list[Platform] = []
            for item in platforms:
                if isinstance(item, Platform):
                    resolved.append(item)
                else:
                    resolved.append(Platform(str(item)))
            return resolved

        resolved = []
        for value in profile.get("target_platforms", []):
            try:
                resolved.append(Platform(value))
            except ValueError:
                continue
        return resolved or [Platform.TIKTOK]


def _contains_concrete_detail(lower_text: str) -> bool:
    return bool(
        re.search(
            r"\b(replay|minute|second|step|note|scent|bridge|lesson|field|door|clip|score|grade)\b",
            lower_text,
        )
    )


__all__ = [
    "HookCandidate",
    "HookEngineeringEngine",
    "HookGenerationResult",
    "HookScoreBreakdown",
]


if __name__ == "__main__":
    from content_brain.profiles.profile_loader import ProfileLoader

    loader = ProfileLoader()
    engine = HookEngineeringEngine()

    samples = [
        ("football", "The referee checked the monitor twice before the final whistle"),
        ("perfume", "This vanilla note disappears after ten minutes on skin"),
        ("dark_mystery", "The apartment had one extra room on the lease but not on the blueprint"),
    ]

    for niche, topic in samples:
        profile = loader.resolve(niche=niche)
        result = engine.generate(profile, topic=topic)
        best = result.candidates[0] if result.candidates else None

        print("\n" + "=" * 72)
        print(f"NICHE: {niche}")
        print(f"TOPIC: {topic}")
        print(f"VARIANTS: {len(result.package.variants)} | REJECTED: {len(result.rejected_candidates)}")

        if best:
            print(f"BEST: {best.text}")
            print(f"CLASS: {best.hook_class.value} | SCORE: {best.scores.composite}")
            print(f"REASON: {best.reasoning}")
            print(f"PLATFORM FIT: {best.platform_fit}")

        print("VALID:", result.package.validate().is_valid)
