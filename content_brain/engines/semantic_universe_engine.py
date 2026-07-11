"""
Semantic Universe Engine V1 for the Viral Content Brain.

Expands a niche or channel identity into a semantic universe for topic generation.
Rule-based only in V1 (no LLM, no external APIs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Optional

from content_brain.schemas.semantic_universe import (
    ENGINE_VERSION,
    SemanticCluster,
    SemanticUniverse,
    SemanticUniverseRequest,
    generate_universe_id,
)


KNOWN_DOMAINS = (
    "football",
    "perfume",
    "education",
    "horror",
    "dark_mystery",
)

FORBIDDEN_SEED_PATTERNS = (
    r"\bbreakout topic\b",
    r"\baudience debate\b",
    r"\bcreator angle\b",
    r"^[\w_]+ breakout topic$",
    r"^[\w_]+ audience debate$",
    r"^[\w_]+ creator angle$",
)

SEED_TEMPLATES = (
    "{concept}",
    "{concept} in a high-stakes moment",
    "why {concept} is dividing viewers right now",
    "the {concept} moment nobody rewinds the same way",
    "what changed after {concept}",
)

GENERIC_CLUSTER_BLUEPRINTS = (
    ("subject_core", "Core Subject", "core"),
    ("audience_interest", "Audience Interest", "audience"),
    ("tension_points", "Tension Points", "conflict"),
    ("discovery_angles", "Discovery Angles", "discovery"),
)


@dataclass
class DomainPack:
    domain: str
    clusters: list[SemanticCluster]
    emotional_angles: list[str] = field(default_factory=list)
    audience_angles: list[str] = field(default_factory=list)
    conflict_angles: list[str] = field(default_factory=list)
    trend_angles: list[str] = field(default_factory=list)


class SemanticUniverseEngine:
    """
    Build a semantic universe from niche and channel identity inputs.

    Usage:
        engine = SemanticUniverseEngine()
        universe = engine.build(
            SemanticUniverseRequest(
                main_niche="football VAR controversy",
                audience="Football fans who debate referee calls",
                tone="documentary_style",
            )
        )
    """

    DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
        "football": (
            "football",
            "soccer",
            "var",
            "referee",
            "penalty",
            "premier league",
            "matchday",
            "stadium",
            "uefa",
        ),
        "perfume": (
            "perfume",
            "fragrance",
            "scent",
            "cologne",
            "notes",
            "dupe",
            "niche perfumery",
        ),
        "education": (
            "education",
            "study",
            "exam",
            "student",
            "learning",
            "school",
            "cram",
            "tutorial",
        ),
        "horror": (
            "horror",
            "scary",
            "creepy",
            "dread",
            "haunted",
            "paranormal",
        ),
        "dark_mystery": (
            "dark mystery",
            "mystery",
            "psychological",
            "disturbing",
            "found footage",
            "missing person",
            "wrong house",
        ),
    }

    DOMAIN_PACKS: dict[str, DomainPack] = {}

    def __init__(self) -> None:
        if not self.DOMAIN_PACKS:
            self.DOMAIN_PACKS = _build_domain_packs()

    def build(self, request: SemanticUniverseRequest | dict[str, Any]) -> SemanticUniverse:
        if isinstance(request, dict):
            request = SemanticUniverseRequest.from_dict(request)

        request.validate()
        main_niche = request.main_niche.strip()
        domain = self._detect_domain(main_niche)
        pack = self.DOMAIN_PACKS.get(domain, self._build_generic_pack(main_niche))

        clusters = [_clone_cluster(cluster) for cluster in pack.clusters]
        clusters = self._apply_sub_niche_focus(clusters, request.sub_niche.strip())
        clusters = self._apply_context_bias(clusters, request)

        emotional_angles = _dedupe_preserve_order(
            pack.emotional_angles + self._tone_emotional_angles(request.tone)
        )
        audience_angles = _dedupe_preserve_order(
            pack.audience_angles + self._audience_emotional_angles(request.audience)
        )
        conflict_angles = _dedupe_preserve_order(pack.conflict_angles)
        trend_angles = _dedupe_preserve_order(
            pack.trend_angles + self._visual_trend_angles(request.visual_style)
        )

        topic_seed_pool = self._build_topic_seed_pool(
            clusters=clusters,
            emotional_angles=emotional_angles,
            audience_angles=audience_angles,
            conflict_angles=conflict_angles,
            trend_angles=trend_angles,
            main_niche=main_niche,
            sub_niche=request.sub_niche.strip(),
        )

        niche_slug = _normalize_slug(main_niche)
        universe = SemanticUniverse(
            universe_id=generate_universe_id(main_niche),
            source_niche=main_niche,
            niche_slug=niche_slug,
            domain=domain,
            semantic_clusters=clusters,
            topic_seed_pool=topic_seed_pool,
            emotional_angles=emotional_angles,
            audience_angles=audience_angles,
            conflict_angles=conflict_angles,
            trend_angles=trend_angles,
            engine_version=ENGINE_VERSION,
            metadata={
                "sub_niche": request.sub_niche.strip(),
                "audience": request.audience.strip(),
                "tone": request.tone.strip(),
                "visual_style": request.visual_style.strip(),
                "expansion_strategy": domain if domain in KNOWN_DOMAINS else "generic_decomposition",
                "cluster_count": len(clusters),
                "seed_count": len(topic_seed_pool),
            },
        )
        return universe

    def build_to_dict(self, request: SemanticUniverseRequest | dict[str, Any]) -> dict[str, Any]:
        return self.build(request).to_dict()

    def _detect_domain(self, main_niche: str) -> str:
        lowered = main_niche.lower()
        tokens = set(_tokenize(main_niche))

        if any(keyword in lowered for keyword in self.DOMAIN_KEYWORDS["dark_mystery"]):
            if any(keyword in lowered for keyword in ("horror", "scary", "creepy", "haunted")):
                return "horror"
            return "dark_mystery"

        scores: dict[str, int] = {}
        for domain in KNOWN_DOMAINS:
            if domain == "dark_mystery":
                continue
            keywords = self.DOMAIN_KEYWORDS.get(domain, ())
            score = sum(1 for keyword in keywords if keyword in lowered or keyword in tokens)
            if score:
                scores[domain] = score

        if not scores:
            return "custom"

        return max(scores, key=scores.get)

    def _build_generic_pack(self, main_niche: str) -> DomainPack:
        tokens = [
            token
            for token in _tokenize(main_niche)
            if len(token) >= 3 and token not in GENERIC_STOP_WORDS
        ]
        if not tokens:
            tokens = ["topic"]

        subject = " ".join(tokens[:3])
        clusters: list[SemanticCluster] = []

        core_concepts = [
            f"common mistakes around {tokens[0]}",
            f"underrated angle in {subject}",
            f"before-and-after shift in {subject}",
            f"the detail most people skip in {subject}",
        ]
        audience_concepts = [
            f"what newcomers get wrong about {subject}",
            f"what experienced people notice first in {subject}",
            f"comment-section debates around {subject}",
        ]
        tension_concepts = [
            f"the tradeoff nobody mentions in {subject}",
            f"the hidden cost of choosing {tokens[0]}",
            f"when {subject} stops working",
        ]
        discovery_concepts = [
            f"unexpected use case for {tokens[0]}",
            f"small change that improves {subject}",
            f"pattern emerging around {subject}",
        ]

        cluster_concepts = {
            "subject_core": core_concepts,
            "audience_interest": audience_concepts,
            "tension_points": tension_concepts,
            "discovery_angles": discovery_concepts,
        }

        for cluster_id, label, _kind in GENERIC_CLUSTER_BLUEPRINTS:
            clusters.append(
                SemanticCluster(
                    cluster_id=cluster_id,
                    label=label,
                    concepts=cluster_concepts[cluster_id],
                )
            )

        return DomainPack(
            domain="custom",
            clusters=clusters,
            emotional_angles=["curiosity", "surprise", "skepticism", "relief", "urgency"],
            audience_angles=[
                "first-time viewers",
                "repeat scrollers",
                "comment-driven follow-ups",
                "save-for-later researchers",
            ],
            conflict_angles=[
                f"beginner vs expert views on {subject}",
                f"popular advice vs real results in {subject}",
                f"expectation vs outcome in {subject}",
            ],
            trend_angles=[
                f"this week's most debated {tokens[0]} angle",
                f"the format gaining traction around {subject}",
                f"the question people keep asking about {subject}",
            ],
        )

    def _apply_sub_niche_focus(
        self,
        clusters: list[SemanticCluster],
        sub_niche: str,
    ) -> list[SemanticCluster]:
        if not sub_niche:
            return clusters

        focused = SemanticCluster(
            cluster_id="sub_niche_focus",
            label="Sub-Niche Focus",
            concepts=[sub_niche, f"local angle on {sub_niche}", f"recent spike in {sub_niche}"],
        )
        return [focused] + clusters

    def _apply_context_bias(
        self,
        clusters: list[SemanticCluster],
        request: SemanticUniverseRequest,
    ) -> list[SemanticCluster]:
        tone = request.tone.strip().lower()
        visual = request.visual_style.strip().lower()
        audience = request.audience.strip().lower()
        biased: list[SemanticCluster] = []

        for cluster in clusters:
            concepts = list(cluster.concepts)
            if tone:
                concepts.extend(_tone_cluster_concepts(tone, cluster.cluster_id))
            if visual:
                concepts.extend(_visual_cluster_concepts(visual, cluster.cluster_id))
            if audience:
                concepts.extend(_audience_cluster_concepts(audience, cluster.cluster_id))
            biased.append(
                SemanticCluster(
                    cluster_id=cluster.cluster_id,
                    label=cluster.label,
                    concepts=_dedupe_preserve_order(concepts),
                )
            )

        return biased

    def _tone_emotional_angles(self, tone: str) -> list[str]:
        lowered = tone.lower()
        if "documentary" in lowered:
            return ["investigative tension", "measured disbelief", "evidence-led urgency"]
        if "luxury" in lowered or "brand" in lowered:
            return ["desire", "refinement", "status curiosity"]
        if "educational" in lowered or "clean" in lowered:
            return ["clarity", "confidence", "relief"]
        if "cinematic" in lowered or "mystery" in lowered:
            return ["dread", "suspense", "unease"]
        return []

    def _audience_emotional_angles(self, audience: str) -> list[str]:
        lowered = audience.lower()
        angles: list[str] = []
        if "fan" in lowered or "debate" in lowered:
            angles.append("partisan intensity")
        if "student" in lowered or "exam" in lowered:
            angles.append("deadline pressure")
        if "enthusiast" in lowered or "collector" in lowered:
            angles.append("comparison obsession")
        if "scroll" in lowered or "comment" in lowered:
            angles.append("thread-chasing curiosity")
        return angles

    def _visual_trend_angles(self, visual_style: str) -> list[str]:
        lowered = visual_style.lower()
        angles: list[str] = []
        if "replay" in lowered or "broadcast" in lowered:
            angles.append("the replay angle everyone rewinds")
        if "close-up" in lowered or "product" in lowered:
            angles.append("the close-up detail driving saves")
        if "whiteboard" in lowered or "text" in lowered:
            angles.append("the on-screen explanation getting shared")
        if "found footage" in lowered or "grain" in lowered:
            angles.append("the frame that feels too real to fake")
        return angles

    def _build_topic_seed_pool(
        self,
        clusters: list[SemanticCluster],
        emotional_angles: list[str],
        audience_angles: list[str],
        conflict_angles: list[str],
        trend_angles: list[str],
        main_niche: str,
        sub_niche: str,
    ) -> list[str]:
        seeds: list[str] = []
        ordered_clusters = [c for c in clusters if c.cluster_id != "sub_niche_focus"]
        ordered_clusters.extend(c for c in clusters if c.cluster_id == "sub_niche_focus")

        for cluster in ordered_clusters:
            for concept in cluster.concepts[:3]:
                cleaned = concept.strip()
                if not cleaned:
                    continue
                for template in SEED_TEMPLATES[:2]:
                    seed = template.format(concept=cleaned).strip()
                    if seed:
                        seeds.append(seed)

        if sub_niche:
            seeds.append(f"fresh angle on {sub_niche}")
            seeds.append(f"what changed in {sub_niche} this week")

        for angle in emotional_angles[:3]:
            seeds.append(f"{angle} framing around a pivotal moment")
        for angle in audience_angles[:3]:
            seeds.append(f"what {angle} are arguing about this week")
        for angle in conflict_angles[:3]:
            seeds.append(f"{angle} under pressure")
        for angle in trend_angles[:3]:
            seeds.append(angle)

        seeds = _dedupe_preserve_order(seeds)
        seeds = [
            seed
            for seed in seeds
            if not _is_forbidden_seed(seed, main_niche)
            and not _seed_repeats_full_niche(seed, main_niche)
        ]
        return seeds[:24]


GENERIC_STOP_WORDS = {
    "micro",
    "niche",
    "general",
    "content",
    "channel",
    "short",
    "form",
    "video",
    "creator",
    "daily",
}


def _build_domain_packs() -> dict[str, DomainPack]:
    football = DomainPack(
        domain="football",
        clusters=[
            SemanticCluster(
                cluster_id="match_decisions",
                label="Match Decisions",
                concepts=[
                    "late match decisions",
                    "controversial penalties",
                    "offside line disputes",
                    "added time drama",
                    "VAR review delays",
                ],
            ),
            SemanticCluster(
                cluster_id="human_drama",
                label="Human Drama",
                concepts=[
                    "referee pressure",
                    "fan reactions",
                    "coach interviews",
                    "emotional match endings",
                    "player confrontations",
                ],
            ),
            SemanticCluster(
                cluster_id="football_ecosystem",
                label="Football Ecosystem",
                concepts=[
                    "UEFA politics",
                    "transfer chaos",
                    "tactical failures",
                    "stadium incidents",
                    "derby week tension",
                ],
            ),
        ],
        emotional_angles=["outrage", "disbelief", "relief", "tension", "vindication"],
        audience_angles=["debate threads", "replay obsessives", "team loyalty stress"],
        conflict_angles=["referee vs fans", "coach vs media", "rule vs emotion"],
        trend_angles=[
            "this week's most debated call",
            "the angle everyone rewinds",
            "the clip splitting rival fan bases",
        ],
    )

    perfume = DomainPack(
        domain="perfume",
        clusters=[
            SemanticCluster(
                cluster_id="scent_experience",
                label="Scent Experience",
                concepts=[
                    "skin chemistry shifts",
                    "longevity on fabric vs skin",
                    "office-safe layering",
                    "first spray vs dry-down",
                ],
            ),
            SemanticCluster(
                cluster_id="buying_context",
                label="Buying Context",
                concepts=[
                    "airport duty-free testing",
                    "blind buy regrets",
                    "sample size vs full bottle",
                    "seasonal scent rotation",
                ],
            ),
            SemanticCluster(
                cluster_id="community_debate",
                label="Community Debate",
                concepts=[
                    "niche dupes",
                    "overhyped releases",
                    "signature scent fatigue",
                    "compliment magnets vs quiet wearers",
                ],
            ),
        ],
        emotional_angles=["desire", "surprise", "skepticism", "confidence"],
        audience_angles=["fragrance collectors", "dupe hunters", "skin chemistry testers"],
        conflict_angles=["hype vs performance", "price vs quality", "nature vs synthetic"],
        trend_angles=[
            "the scent everyone asked about this week",
            "the dry-down comparison getting saves",
            "the airport test format gaining traction",
        ],
    )

    education = DomainPack(
        domain="education",
        clusters=[
            SemanticCluster(
                cluster_id="study_systems",
                label="Study Systems",
                concepts=[
                    "exam cram frameworks",
                    "visual memory tricks",
                    "active recall routines",
                    "note-to-retention pipelines",
                ],
            ),
            SemanticCluster(
                cluster_id="mistake_patterns",
                label="Mistake Patterns",
                concepts=[
                    "common mistake corrections",
                    "concept gaps before exam day",
                    "time management failures",
                    "practice question traps",
                ],
            ),
            SemanticCluster(
                cluster_id="motivation_pressure",
                label="Motivation Pressure",
                concepts=[
                    "deadline panic loops",
                    "burnout recovery sprints",
                    "focus reset rituals",
                    "last-week revision plans",
                ],
            ),
        ],
        emotional_angles=["urgency", "relief", "confidence", "anxiety", "clarity"],
        audience_angles=["exam crammers", "visual learners", "last-minute revisers"],
        conflict_angles=["speed vs retention", "shortcuts vs mastery", "confidence vs reality"],
        trend_angles=[
            "the study format students are saving",
            "the revision mistake trending in comments",
            "the 10-minute framework getting reposts",
        ],
    )

    horror = DomainPack(
        domain="horror",
        clusters=[
            SemanticCluster(
                cluster_id="fear_mechanics",
                label="Fear Mechanics",
                concepts=[
                    "jump-scare timing",
                    "sound design dread",
                    "silence before the reveal",
                    "uncanny familiar spaces",
                ],
            ),
            SemanticCluster(
                cluster_id="story_fear",
                label="Story Fear",
                concepts=[
                    "wrong place wrong time",
                    "the rule that gets broken",
                    "the friend who disappears first",
                    "the recording that should not exist",
                ],
            ),
            SemanticCluster(
                cluster_id="audience_reaction",
                label="Audience Reaction",
                concepts=[
                    "watch-alone vs watch-with-friends",
                    "rewind-the-scare behavior",
                    "comment-section fear tests",
                    "sleep-loss confessions",
                ],
            ),
        ],
        emotional_angles=["dread", "shock", "unease", "panic", "disbelief"],
        audience_angles=["horror binge scrollers", "jump-scare seekers", "lore hunters"],
        conflict_angles=["safety vs curiosity", "belief vs denial", "group fear vs solo fear"],
        trend_angles=[
            "the scare clip people refuse to finish",
            "the sound cue viewers keep mentioning",
            "the ending that broke comment sections",
        ],
    )

    dark_mystery = DomainPack(
        domain="dark_mystery",
        clusters=[
            SemanticCluster(
                cluster_id="narrative_mystery",
                label="Narrative Mystery",
                concepts=[
                    "found-footage pacing tricks",
                    "one-room psychological dread",
                    "open-loop cliffhanger endings",
                    "missing timeline details",
                ],
            ),
            SemanticCluster(
                cluster_id="environmental_dread",
                label="Environmental Dread",
                concepts=[
                    "the room not on the blueprint",
                    "ambient sound design hooks",
                    "lighting that feels slightly wrong",
                    "objects moved between cuts",
                ],
            ),
            SemanticCluster(
                cluster_id="audience_engagement",
                label="Audience Engagement",
                concepts=[
                    "comment-section theory threads",
                    "frame-by-frame breakdowns",
                    "part-two demand loops",
                    "unsolved detail obsession",
                ],
            ),
        ],
        emotional_angles=["dread", "curiosity", "paranoia", "suspense", "disorientation"],
        audience_angles=["theory builders", "frame hunters", "slow-burn viewers"],
        conflict_angles=["what you saw vs what happened", "memory vs evidence", "trust vs fear"],
        trend_angles=[
            "the detail viewers rewound three times",
            "the ending that launched a theory thread",
            "the clip that feels too coherent to fake",
        ],
    )

    return {
        "football": football,
        "perfume": perfume,
        "education": education,
        "horror": horror,
        "dark_mystery": dark_mystery,
    }


def _clone_cluster(cluster: SemanticCluster) -> SemanticCluster:
    return SemanticCluster(
        cluster_id=cluster.cluster_id,
        label=cluster.label,
        concepts=list(cluster.concepts),
    )


def _tone_cluster_concepts(tone: str, cluster_id: str) -> list[str]:
    if "documentary" in tone:
        if cluster_id in {"match_decisions", "human_drama", "subject_core"}:
            return ["timeline reconstruction", "evidence-led breakdown"]
    if "luxury" in tone or "brand" in tone:
        if cluster_id in {"scent_experience", "buying_context"}:
            return ["premium presentation angle", "status-signaling detail"]
    if "educational" in tone:
        return ["step-by-step clarity angle", "common misconception reset"]
    if "cinematic" in tone or "mystery" in tone:
        return ["slow reveal framing", "atmospheric setup detail"]
    return []


def _visual_cluster_concepts(visual_style: str, cluster_id: str) -> list[str]:
    if "replay" in visual_style or "broadcast" in visual_style:
        return ["broadcast replay framing", "stadium close-up tension"]
    if "close-up" in visual_style or "product" in visual_style:
        return ["macro detail reveal", "texture-first comparison"]
    if "whiteboard" in visual_style or "desk" in visual_style:
        return ["on-screen framework reveal", "annotated walkthrough"]
    if "found footage" in visual_style or "grain" in visual_style:
        return ["handheld authenticity cue", "imperfect lighting beat"]
    return []


def _audience_cluster_concepts(audience: str, cluster_id: str) -> list[str]:
    if "debate" in audience or "fan" in audience:
        return ["rival fan base split", "post-match argument thread"]
    if "student" in audience or "exam" in audience:
        return ["deadline-week pressure point", "grade-saving shortcut test"]
    if "enthusiast" in audience or "collector" in audience:
        return ["comparison-table obsession", "expert vs beginner gap"]
    return []


def _normalize_slug(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s\-_]", "", cleaned)
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    return cleaned[:48].strip("_") or "general"


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return [token for token in cleaned.split() if token]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", item.strip())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _is_forbidden_seed(seed: str, main_niche: str) -> bool:
    lowered = seed.lower()
    for pattern in FORBIDDEN_SEED_PATTERNS:
        if re.search(pattern, lowered):
            return True
    slug = _normalize_slug(main_niche)
    if slug and slug in lowered and "breakout" in lowered:
        return True
    return False


def _seed_repeats_full_niche(seed: str, main_niche: str) -> bool:
    seed_lower = seed.lower().strip()
    niche_lower = main_niche.lower().strip()
    if not niche_lower:
        return False
    if seed_lower == niche_lower:
        return True
    if len(niche_lower) >= 12 and niche_lower in seed_lower and len(seed_lower) <= len(niche_lower) + 6:
        return True
    return False


__all__ = [
    "KNOWN_DOMAINS",
    "SemanticUniverseEngine",
]


if __name__ == "__main__":
    engine = SemanticUniverseEngine()

    cases = [
        SemanticUniverseRequest(
            main_niche="football VAR controversy",
            sub_niche="Premier League replay decisions",
            audience="Football fans who debate referee calls and replay angles",
            tone="documentary_style",
            visual_style="broadcast replay frames, stadium close-ups",
        ),
        SemanticUniverseRequest(
            main_niche="perfume niche reviews",
            sub_niche="airport duty-free scent testing",
            audience="Fragrance enthusiasts comparing dupes and skin chemistry",
            tone="luxury_brand",
            visual_style="clean product close-ups, skin swatches",
        ),
        SemanticUniverseRequest(
            main_niche="AI education",
            audience="Students looking for fast, practical study systems",
            tone="educational_clean",
            visual_style="whiteboard overlays, readable text on mobile",
        ),
        SemanticUniverseRequest(
            main_niche="dark mystery storytelling",
            audience="Viewers who comment frame-by-frame theories",
            tone="cinematic_professional",
            visual_style="found footage grain, low-light interiors",
        ),
        SemanticUniverseRequest(
            main_niche="urban beekeeping micro-niche",
            audience="City hobbyists and ecology scrollers",
            tone="informative_warm",
            visual_style="rooftop close-ups, handheld natural light",
        ),
    ]

    print("SEMANTIC UNIVERSE ENGINE V1 - SMOKE TEST")
    print("=" * 72)

    for index, request in enumerate(cases, start=1):
        universe = engine.build(request)
        payload = universe.to_dict()
        roundtrip = SemanticUniverse.from_dict(payload)

        print(f"\n[{index}] {request.main_niche}")
        print("  DOMAIN:", universe.domain)
        print("  UNIVERSE ID:", universe.universe_id)
        print("  CLUSTERS:", len(universe.semantic_clusters))
        print("  SEED POOL:", len(universe.topic_seed_pool))
        print("  SAMPLE SEEDS:")
        for seed in universe.topic_seed_pool[:5]:
            print(f"    - {seed}")
        print("  EMOTIONAL:", ", ".join(universe.emotional_angles[:4]))
        print("  CONFLICT:", ", ".join(universe.conflict_angles[:3]))
        print("  ROUNDTRIP OK:", roundtrip.source_niche == universe.source_niche)
        print("  JSON OK:", json.dumps(payload, ensure_ascii=False)[:120] + "...")

        forbidden_hits = [
            seed
            for seed in universe.topic_seed_pool
            if _is_forbidden_seed(seed, request.main_niche)
        ]
        niche_echo_hits = [
            seed
            for seed in universe.topic_seed_pool
            if seed.lower().strip() == request.main_niche.lower().strip()
        ]
        print("  FORBIDDEN SEED HITS:", len(forbidden_hits))
        print("  FULL-NICHE ECHO HITS:", len(niche_echo_hits))

    print("\n" + "=" * 72)
    print("FOOTBALL VAR UNIVERSE CHECK")
    football = engine.build(cases[0])
    expected_fragments = (
        "referee pressure",
        "late match decisions",
        "fan reactions",
        "controversial penalties",
        "coach interviews",
        "UEFA politics",
        "transfer chaos",
        "tactical failures",
        "stadium incidents",
    )
    pool_text = " | ".join(football.topic_seed_pool).lower()
    hits = [fragment for fragment in expected_fragments if fragment in pool_text]
    print("EXPECTED FRAGMENT HITS:", len(hits), "/", len(expected_fragments))
    for fragment in hits:
        print(f"  OK {fragment}")
    missing = [fragment for fragment in expected_fragments if fragment not in pool_text]
    for fragment in missing:
        print(f"  MISSING {fragment}")

    print("\nDETERMINISM CHECK")
    first = engine.build(cases[0]).to_dict()
    second = engine.build(cases[0]).to_dict()
    first.pop("generated_at", None)
    second.pop("generated_at", None)
    print("DETERMINISTIC (excluding timestamp):", first == second)
