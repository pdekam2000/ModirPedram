"""
Topic Universe / SEO Title Bank builder for Content Brain.

Expands broad categories into many specific, deduplicated, SEO-ready video titles.
Detects broad vs specific topics and applies user topic authority.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from hashlib import md5
from typing import Any

from content_brain.execution.content_brain_topic_authority import extract_topic_domain
from content_brain.execution.content_brain_topic_locale import detect_language_code, extract_topic_anchor_tokens
from content_brain.execution.content_brain_topic_strategy import (
    INSTRUCTIONAL_INTENT_MARKERS,
    classify_topic,
)

BUILDER_VERSION = "topic_universe_builder_v1"
DEFAULT_TITLE_TARGET = 100
MAX_SUBTOPIC_SHARE = 8
NEAR_DUPLICATE_THRESHOLD = 0.82

LISTICLE_NUMBERS = (3, 5, 7, 9)

INTENT_LABELS = (
    "how_to",
    "listicle",
    "mistake_fix",
    "myth_busting",
    "technique",
    "gear_guide",
    "challenge",
    "explainer",
)

FISHING_SPECIES: tuple[str, ...] = (
    "zander",
    "pike",
    "carp",
    "bass",
    "trout",
    "salmon",
    "walleye",
    "perch",
)

BAD_GENERIC_PATTERNS = (
    r"^best {topic}$",
    r"^{topic} tips$",
    r"^how to {topic}$",
    r"^{topic} method$",
    r"^fishing tips$",
    r"^best fishing$",
)

FISHING_SUBCATEGORY_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "subtopic": "beginner fishing tips",
        "templates": (
            "{n} Fishing Mistakes Beginners Make Without Realizing",
            "The First {n} Things Every New Angler Should Learn",
            "Why Beginners Lose Fish Before They Even Hook Them",
            "What Nobody Tells You Before Your First Fishing Trip",
            "Stop Doing This on Your First Cast",
            "The Beginner Fishing Checklist Pros Still Use",
        ),
        "intent": "listicle",
        "difficulty": "beginner",
    },
    {
        "subtopic": "lure fishing",
        "templates": (
            "The Best Lure Color for Murky Water Fishing",
            "Why Fish Ignore Your Lure in Clear Water",
            "How to Make Soft Plastics Look Alive Underwater",
            "The Biggest Mistake When Using Soft Plastic Lures",
            "Which Lure Works When Nothing Else Does",
            "How to Choose the Right Lure for the Conditions",
        ),
        "intent": "technique",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "zander fishing",
        "templates": (
            "How to Catch Zander in Shallow Water at Night",
            "How to Catch Zander When the Water Gets Cold",
            "The Zander Retrieve Rhythm Most Anglers Miss",
            "Why Zander Follow Your Lure But Never Bite",
            "Best Depth to Target Zander in a New Lake",
            "The Lure Type That Triggers More Zander Strikes",
        ),
        "intent": "how_to",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "carp fishing",
        "templates": (
            "How to Find Carp in a Lake You Have Never Fished",
            "The Bait Choice That Gets Carp Feeding Faster",
            "Why Your Carp Rig Keeps Failing at the Margin",
            "How to Read Carp Signs Before You Cast",
            "The Simple Carp Setup That Works in Tough Conditions",
            "What Changes When Carp Go Deep in Summer",
        ),
        "intent": "how_to",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "pike fishing",
        "templates": (
            "How to Target Pike Without Spooking Shallow Fish",
            "The Retrieve Speed That Triggers Aggressive Pike",
            "Why Pike Follow and Turn Away at the Last Second",
            "Best Wire Leader Mistakes Pike Anglers Make",
            "How to Fish Weed Edges for Hidden Pike",
            "The Lure Profile Pike Cannot Ignore in Cold Water",
        ),
        "intent": "technique",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "bass fishing",
        "templates": (
            "How to Catch Bass When the Bite Goes Quiet",
            "The Cover Pattern Bass Use on Small Lakes",
            "Why Your Bass Lure Gets Short Strikes",
            "How to Fish Drop-Offs for Suspended Bass",
            "The Topwater Window Bass Anglers Should Not Miss",
            "What Bass Do When Water Temperature Drops Fast",
        ),
        "intent": "how_to",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "night fishing",
        "templates": (
            "How to Catch More Fish After Dark Without Guesswork",
            "The Night Fishing Setup That Keeps You Hooked Up",
            "Why Night Bites Feel Different and How to Adapt",
            "How to Find Safe Spots for Night Fishing",
            "The Sound and Light Mistakes Night Anglers Make",
            "What to Change in Retrieve Speed After Sunset",
        ),
        "intent": "how_to",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "winter fishing",
        "templates": (
            "How to Catch Fish When the Water Gets Ice Cold",
            "The Slow Presentation Trick for Winter Predators",
            "Why Winter Fish Hold Deeper Than You Think",
            "How to Keep Your Line Alive in Freezing Conditions",
            "The Winter Lure Size Rule Most Anglers Break",
            "What to Do When Bites Disappear in Cold Fronts",
        ),
        "intent": "technique",
        "difficulty": "advanced",
    },
    {
        "subtopic": "fishing knots",
        "templates": (
            "The Simple Knot Every Beginner Angler Should Learn",
            "Why Your Fishing Line Keeps Breaking at the Knot",
            "How to Tie a Strong Knot in 10 Seconds",
            "The Knot Pros Use for Slippery Braid",
            "Stop Losing Fish to Weak Knots",
            "Which Knot to Use for Lure Changes Fast",
        ),
        "intent": "how_to",
        "difficulty": "beginner",
    },
    {
        "subtopic": "fishing gear",
        "templates": (
            "The Only Fishing Gear Upgrades Worth Buying First",
            "How to Build a Minimal Tackle Box That Actually Works",
            "Why Expensive Rods Do Not Fix Bad Technique",
            "The Gear Mistake That Ruins Your First Season",
            "What to Pack for a One-Day Fishing Trip",
            "How to Match Rod Power to Your Target Species",
        ),
        "intent": "gear_guide",
        "difficulty": "beginner",
    },
    {
        "subtopic": "fishing mistakes",
        "templates": (
            "The Hook-Set Mistake That Costs You Fish Every Trip",
            "Why You Keep Missing Bites Without Knowing It",
            "How to Stop Scaring Fish Before Your First Cast",
            "The Casting Error That Kills Your Accuracy",
            "What Anglers Do Wrong at the Landing Net",
            "Why Your Spot Looks Good But Produces Nothing",
        ),
        "intent": "mistake_fix",
        "difficulty": "beginner",
    },
    {
        "subtopic": "casting technique",
        "templates": (
            "How to Set the Hook Properly Every Time",
            "The Casting Fix That Doubles Your Accuracy",
            "Why Your Lure Lands Too Loud and Spooks Fish",
            "How to Cast Under Overhangs Without Snagging",
            "The Roll Cast Trick for Tight Bank Fishing",
            "What Your Backcast Is Doing Wrong",
        ),
        "intent": "technique",
        "difficulty": "beginner",
    },
    {
        "subtopic": "bait selection",
        "templates": (
            "How to Pick Bait When Fish Are Being Picky",
            "Why Live Bait Outfishes Everything Some Days",
            "The Bait Switch That Saves a Slow Session",
            "How to Match Bait Size to What Fish Are Eating",
            "What Bait Color Means in Stained Water",
            "When to Downsize Bait and Actually Get Bites",
        ),
        "intent": "explainer",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "depth strategy",
        "templates": (
            "How to Fish Deep Water Without Losing Your Lure",
            "The Depth Rule That Finds Fish Faster on New Lakes",
            "Why Fish Move Shallow Then Vanish Again",
            "How to Count Down Lures to the Right Depth",
            "What Thermocline Means for Your Next Trip",
            "How to Adjust Depth When the Bite Stops",
        ),
        "intent": "technique",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "river fishing",
        "templates": (
            "How to Read River Current for Better Casts",
            "The Seam Pattern Where River Predators Wait",
            "Why River Fish Hold Behind Small Obstacles",
            "How to Fish Fast River Flow Without Snags",
            "What Changes When River Levels Rise Overnight",
            "The Wading Mistake That Ruins River Spots",
        ),
        "intent": "how_to",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "lake fishing",
        "templates": (
            "How to Find Fish Fast in a New Lake",
            "The Structure Map Every Lake Angler Should Scan First",
            "Why Lake Fish Move Shallow at Dawn",
            "How to Work a Point When Nothing Is Biting",
            "What Wind Direction Does to Lake Bites",
            "The Boat-Free Strategy for Bank Fishing Big Lakes",
        ),
        "intent": "how_to",
        "difficulty": "beginner",
    },
    {
        "subtopic": "sea fishing",
        "templates": (
            "How to Read Tide Timing for Better Sea Fishing",
            "The Ground Bait Trick for Consistent Sea Bites",
            "Why Sea Fish Turn Off Without Warning",
            "How to Fish Rocky Marks Safely from Shore",
            "What Rig Change Saves a Slow Sea Session",
            "The Cast Distance Myth in Saltwater Fishing",
        ),
        "intent": "how_to",
        "difficulty": "advanced",
    },
    {
        "subtopic": "catch and cook",
        "templates": (
            "How to Clean and Cook Your Catch on a Camp Stove",
            "The Simple Shore Lunch Every Angler Should Try Once",
            "Why Fresh Catch Tastes Better With This One Step",
            "How to Fillet a Fish Without Wasting Meat",
            "The Minimal Spice Kit for Fishing Trips",
            "What Not to Do When Cooking Over an Open Fire",
        ),
        "intent": "explainer",
        "difficulty": "beginner",
    },
    {
        "subtopic": "fishing myths",
        "templates": (
            "The Biggest Fishing Myth That Still Fools Beginners",
            "Why Bright Lures Do Not Always Mean More Bites",
            "The Moon Phase Myth Anglers Still Believe",
            "Do Fish Really Stop Biting After Rain?",
            "Why More Scent Is Not Always Better",
            "The Line Visibility Myth Explained in 30 Seconds",
        ),
        "intent": "myth_busting",
        "difficulty": "beginner",
    },
    {
        "subtopic": "fishing challenges",
        "templates": (
            "Can You Catch a Fish With Only One Lure All Day?",
            "The 30-Minute Challenge to Find Active Fish",
            "Try This Lure-Only Bank Fishing Challenge",
            "One Rod One Reel Fishing Challenge Rules",
            "Can You Beat This Cold-Water Bite Challenge?",
            "The No-Bait Challenge That Tests Your Skill",
        ),
        "intent": "challenge",
        "difficulty": "intermediate",
    },
)

GENERIC_SUBCATEGORY_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "subtopic": "beginner basics",
        "templates": (
            "{n} {topic} Mistakes Beginners Make Without Realizing",
            "The First {n} Things to Learn About {topic}",
            "What Nobody Tells You Before Starting {topic}",
            "Stop Doing This When You Try {topic}",
        ),
        "intent": "listicle",
        "difficulty": "beginner",
    },
    {
        "subtopic": "how-to guides",
        "templates": (
            "How to Master {topic} Step by Step",
            "The Simple {topic} Method That Actually Works",
            "How to Get Better at {topic} Fast",
            "Why Your {topic} Results Keep Failing",
        ),
        "intent": "how_to",
        "difficulty": "beginner",
    },
    {
        "subtopic": "common mistakes",
        "templates": (
            "The Biggest {topic} Mistake Almost Everyone Makes",
            "Why {topic} Feels Harder Than It Should",
            "What to Fix First in Your {topic} Routine",
            "The {topic} Error That Wastes the Most Time",
        ),
        "intent": "mistake_fix",
        "difficulty": "beginner",
    },
    {
        "subtopic": "gear and tools",
        "templates": (
            "The Only {topic} Tools Worth Buying First",
            "How to Build a Minimal {topic} Setup",
            "Why Expensive {topic} Gear Does Not Fix Bad Technique",
            "What Pros Pack for {topic} Every Time",
        ),
        "intent": "gear_guide",
        "difficulty": "intermediate",
    },
    {
        "subtopic": "advanced techniques",
        "templates": (
            "The Advanced {topic} Trick Most People Skip",
            "How to Level Up Your {topic} Technique",
            "What Changes When You Take {topic} Seriously",
            "The {topic} Strategy Experts Use Under Pressure",
        ),
        "intent": "technique",
        "difficulty": "advanced",
    },
    {
        "subtopic": "myths debunked",
        "templates": (
            "The Biggest {topic} Myth Still Believed Today",
            "Does {topic} Really Work Like Everyone Says?",
            "Why Popular {topic} Advice Is Wrong",
            "The {topic} Rule You Should Stop Following",
        ),
        "intent": "myth_busting",
        "difficulty": "beginner",
    },
    {
        "subtopic": "quick wins",
        "templates": (
            "Try This {topic} Hack Before Your Next Attempt",
            "The 30-Second {topic} Tip That Saves Time",
            "One Change That Improves {topic} Immediately",
            "The Fastest Way to See Results in {topic}",
        ),
        "intent": "explainer",
        "difficulty": "beginner",
    },
    {
        "subtopic": "challenges",
        "templates": (
            "Can You Master {topic} in One Day?",
            "The {topic} Challenge Nobody Talks About",
            "Try This {topic} Test and See Your Level",
            "One-Week {topic} Improvement Challenge",
        ),
        "intent": "challenge",
        "difficulty": "intermediate",
    },
)


@dataclass
class TopicScopeResult:
    topic: str
    scope: str
    token_count: int
    instructional_intent: bool
    domain: str
    anchor_tokens: tuple[str, ...]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "scope": self.scope,
            "token_count": self.token_count,
            "instructional_intent": self.instructional_intent,
            "domain": self.domain,
            "anchor_tokens": list(self.anchor_tokens),
            "reasoning": self.reasoning,
        }


@dataclass
class TitleBankEntry:
    title_id: str
    title: str
    subtopic: str
    category: str
    intent: str
    difficulty: str
    estimated_viral_potential: float
    educational_value: float
    trend_score: float
    source_provider: str
    keywords: list[str]
    suggested_duration: int
    suggested_clip_count: int
    content_strategy: str
    duplicate_status: str = "unique"
    normalized_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title_id": self.title_id,
            "title": self.title,
            "subtopic": self.subtopic,
            "category": self.category,
            "intent": self.intent,
            "difficulty": self.difficulty,
            "estimated_viral_potential": round(self.estimated_viral_potential, 4),
            "educational_value": round(self.educational_value, 4),
            "trend_score": round(self.trend_score, 4),
            "source_provider": self.source_provider,
            "keywords": list(self.keywords),
            "suggested_duration": self.suggested_duration,
            "suggested_clip_count": self.suggested_clip_count,
            "content_strategy": self.content_strategy,
            "duplicate_status": self.duplicate_status,
            "normalized_title": self.normalized_title,
        }


@dataclass
class TitleBankResult:
    run_id: str
    topic: str
    scope: TopicScopeResult
    mode: str
    trend_mode: str
    title_target: int
    titles: list[TitleBankEntry]
    deduplication: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    builder_version: str = BUILDER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "topic": self.topic,
            "scope": self.scope.to_dict(),
            "mode": self.mode,
            "trend_mode": self.trend_mode,
            "title_target": self.title_target,
            "title_count": len(self.titles),
            "titles": [item.to_dict() for item in self.titles],
            "deduplication": self.deduplication,
            "notes": list(self.notes),
            "builder_version": self.builder_version,
        }


def detect_topic_scope(topic: str, *, language_code: str | None = None) -> TopicScopeResult:
    cleaned = _normalize_display(topic)
    lowered = cleaned.lower()
    tokens = extract_topic_anchor_tokens(cleaned, limit=8)
    raw_word_count = len(cleaned.split())
    token_count = len(tokens) or raw_word_count
    instructional = _has_instructional_intent(lowered)
    domain = extract_topic_domain(cleaned) or "general"
    lang = language_code or detect_language_code(cleaned)

    if instructional and raw_word_count >= 3:
        return TopicScopeResult(
            topic=cleaned,
            scope="specific",
            token_count=token_count,
            instructional_intent=True,
            domain=domain,
            anchor_tokens=tuple(tokens),
            reasoning="Instructional phrasing with enough detail for one video plan.",
        )

    if instructional and raw_word_count >= 2 and domain != "general":
        return TopicScopeResult(
            topic=cleaned,
            scope="specific",
            token_count=token_count,
            instructional_intent=True,
            domain=domain,
            anchor_tokens=tuple(tokens),
            reasoning="Instructional domain topic reads as one focused video plan.",
        )

    if token_count <= 2 and not instructional:
        if domain == "fishing" and any(species in lowered for species in FISHING_SPECIES):
            return TopicScopeResult(
                topic=cleaned,
                scope="semi_specific",
                token_count=token_count,
                instructional_intent=False,
                domain=domain,
                anchor_tokens=tuple(tokens),
                reasoning="Species-focused fishing niche — generate narrowed title bank.",
            )
        return TopicScopeResult(
            topic=cleaned,
            scope="broad",
            token_count=token_count,
            instructional_intent=False,
            domain=domain,
            anchor_tokens=tuple(tokens),
            reasoning="Short category/niche input — expand into title bank.",
        )

    if token_count >= 4:
        return TopicScopeResult(
            topic=cleaned,
            scope="specific",
            token_count=token_count,
            instructional_intent=instructional,
            domain=domain,
            anchor_tokens=tuple(tokens),
            reasoning="Multi-token topic reads as a single video idea.",
        )

    if domain != "general" and token_count == 3:
        return TopicScopeResult(
            topic=cleaned,
            scope="semi_specific",
            token_count=token_count,
            instructional_intent=instructional,
            domain=domain,
            anchor_tokens=tuple(tokens),
            reasoning="Focused sub-niche — generate narrowed title bank.",
        )

    del lang
    return TopicScopeResult(
        topic=cleaned,
        scope="broad" if token_count <= 2 else "semi_specific",
        token_count=token_count,
        instructional_intent=instructional,
        domain=domain,
        anchor_tokens=tuple(tokens),
        reasoning="Default scope classification for title bank expansion.",
    )


def build_title_bank(
    *,
    topic: str,
    language_code: str | None = None,
    platform: str = "youtube_shorts",
    audience_level: str = "general",
    niche_style: str = "general",
    title_target: int = DEFAULT_TITLE_TARGET,
    use_live_trends: bool = True,
    suggested_duration: int | None = None,
    trend_opportunities: list[dict[str, Any]] | None = None,
    trend_mode: str | None = None,
) -> TitleBankResult:
    cleaned_topic = _normalize_display(topic)
    scope = detect_topic_scope(cleaned_topic, language_code=language_code)
    run_id = f"topic_universe_{uuid.uuid4().hex[:12]}"
    duration = int(suggested_duration or 30)
    clip_count = max(1, duration // 10)

    if scope.scope == "specific":
        entry = _build_specific_video_entry(
            cleaned_topic,
            scope=scope,
            platform=platform,
            duration=duration,
            clip_count=clip_count,
        )
        return TitleBankResult(
            run_id=run_id,
            topic=cleaned_topic,
            scope=scope,
            mode="specific_video_plan",
            trend_mode=trend_mode or "not_applicable",
            title_target=1,
            titles=[entry],
            deduplication={"removed_exact": 0, "removed_near": 0, "removed_subtopic_cap": 0},
            notes=["Specific topic detected — generated one detailed video plan instead of title bank."],
        )

    live_mode = trend_mode or ("live" if trend_opportunities else "fallback_seed_expansion")
    if use_live_trends and trend_opportunities:
        live_mode = trend_mode or "live"

    raw_entries = _expand_seed_titles(
        topic=cleaned_topic,
        scope=scope,
        audience_level=audience_level,
        platform=platform,
        duration=duration,
        clip_count=clip_count,
        title_target=max(title_target, 100),
    )
    if trend_opportunities:
        raw_entries.extend(
            _titles_from_trends(
                cleaned_topic,
                scope=scope,
                trends=trend_opportunities,
                duration=duration,
                clip_count=clip_count,
            )
        )

    deduped, dedup_stats = deduplicate_title_entries(raw_entries, title_target=title_target)
    notes: list[str] = []
    if len(deduped) < title_target:
        notes.append(
            f"Generated {len(deduped)} unique titles (target {title_target}). "
            "Increase seed diversity or enable live trend providers for more."
        )
    if live_mode == "fallback_seed_expansion":
        notes.append("trend_mode=fallback_seed_expansion — live trend APIs were not used.")

    return TitleBankResult(
        run_id=run_id,
        topic=cleaned_topic,
        scope=scope,
        mode="title_bank",
        trend_mode=live_mode,
        title_target=title_target,
        titles=deduped,
        deduplication=dedup_stats,
        notes=notes,
    )


def deduplicate_title_entries(
    entries: list[TitleBankEntry],
    *,
    title_target: int,
) -> tuple[list[TitleBankEntry], dict[str, Any]]:
    kept: list[TitleBankEntry] = []
    seen_exact: set[str] = set()
    seen_skeletons: dict[str, int] = {}
    subtopic_counts: dict[str, int] = {}
    removed_exact = 0
    removed_near = 0
    removed_subtopic_cap = 0

    for entry in entries:
        normalized = normalize_title(entry.title)
        if not normalized or _is_bad_generic_title(normalized, entry.category):
            removed_exact += 1
            continue
        if normalized in seen_exact:
            entry.duplicate_status = "exact_duplicate"
            removed_exact += 1
            continue

        skeleton = _title_skeleton(entry.title)
        if seen_skeletons.get(skeleton, 0) >= 2:
            entry.duplicate_status = "template_repeat"
            removed_near += 1
            continue

        if any(_near_duplicate(normalized, normalize_title(existing.title)) for existing in kept):
            entry.duplicate_status = "near_duplicate"
            removed_near += 1
            continue

        subtopic_key = entry.subtopic.lower()
        if subtopic_counts.get(subtopic_key, 0) >= MAX_SUBTOPIC_SHARE:
            entry.duplicate_status = "subtopic_cap"
            removed_subtopic_cap += 1
            continue

        entry.normalized_title = normalized
        entry.duplicate_status = "unique"
        kept.append(entry)
        seen_exact.add(normalized)
        seen_skeletons[skeleton] = seen_skeletons.get(skeleton, 0) + 1
        subtopic_counts[subtopic_key] = subtopic_counts.get(subtopic_key, 0) + 1
        if len(kept) >= title_target:
            break

    return kept, {
        "removed_exact": removed_exact,
        "removed_near": removed_near,
        "removed_subtopic_cap": removed_subtopic_cap,
        "kept": len(kept),
        "requested": title_target,
    }


def normalize_title(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return " ".join(lowered.split())


def title_passes_topic_authority(title: str, topic: str, scope: TopicScopeResult) -> bool:
    normalized_title = normalize_title(title)
    if scope.scope == "specific":
        return all(token in normalized_title for token in scope.anchor_tokens[:2] if len(token) > 2)

    if scope.scope == "semi_specific" and scope.domain == "fishing":
        species = next((item for item in FISHING_SPECIES if item in " ".join(scope.anchor_tokens).lower()), "")
        if species and species not in normalized_title:
            return False

    domain = scope.domain
    if domain == "fishing":
        fishing_terms = (
            "fish",
            "fishing",
            "angler",
            "lure",
            "cast",
            "hook",
            "bait",
            "rod",
            "reel",
            "zander",
            "pike",
            "carp",
            "bass",
            "trout",
        )
        return any(term in normalized_title for term in fishing_terms)

    anchor = scope.anchor_tokens or extract_topic_anchor_tokens(topic, limit=2)
    if not anchor:
        anchor = (normalize_title(topic),)
    return any(token in normalized_title for token in anchor if len(token) > 2)


def _expand_seed_titles(
    *,
    topic: str,
    scope: TopicScopeResult,
    audience_level: str,
    platform: str,
    duration: int,
    clip_count: int,
    title_target: int,
) -> list[TitleBankEntry]:
    seeds = _resolve_seed_pack(scope)
    entries: list[TitleBankEntry] = []
    number_cycle = list(LISTICLE_NUMBERS)
    number_index = 0
    topic_label = _topic_label(topic, scope)

    for seed in seeds:
        subtopic = str(seed["subtopic"])
        intent = str(seed.get("intent") or "explainer")
        difficulty = str(seed.get("difficulty") or audience_level or "beginner")
        templates = list(seed.get("templates") or ())
        for template in templates:
            number = number_cycle[number_index % len(number_cycle)]
            number_index += 1
            rendered = _render_template(template, topic=topic_label, n=number, anchor=topic_label)
            if not title_passes_topic_authority(rendered, topic, scope):
                continue
            if _is_bad_generic_title(normalize_title(rendered), scope.domain):
                continue
            classification = classify_topic(rendered, language_code=detect_language_code(topic))
            entries.append(
                _make_entry(
                    title=rendered,
                    subtopic=subtopic,
                    category=scope.domain,
                    intent=intent,
                    difficulty=difficulty,
                    platform=platform,
                    duration=duration,
                    clip_count=clip_count,
                    content_strategy=classification.content_strategy,
                    source_provider="seed_expansion",
                    trend_score=0.42,
                )
            )
            if len(entries) >= title_target * 2:
                return entries
    return entries


def _titles_from_trends(
    topic: str,
    *,
    scope: TopicScopeResult,
    trends: list[dict[str, Any]],
    duration: int,
    clip_count: int,
) -> list[TitleBankEntry]:
    entries: list[TitleBankEntry] = []
    for item in trends:
        trend_title = _normalize_display(str(item.get("trend") or item.get("topic") or ""))
        if not trend_title:
            continue
        rendered = _normalize_display(f"{trend_title}: what shorts creators should know")
        if not title_passes_topic_authority(rendered, topic, scope):
            continue
        score = float(item.get("score") or item.get("overall_trend_score") or 0.55)
        provider = str(item.get("source") or item.get("provider_id") or "trend_discovery")
        classification = classify_topic(rendered)
        entries.append(
            _make_entry(
                title=rendered,
                subtopic="trending angles",
                category=scope.domain,
                intent="explainer",
                difficulty="intermediate",
                platform="youtube_shorts",
                duration=duration,
                clip_count=clip_count,
                content_strategy=classification.content_strategy,
                source_provider=provider,
                trend_score=min(1.0, score),
            )
        )
    return entries


def _build_specific_video_entry(
    topic: str,
    *,
    scope: TopicScopeResult,
    platform: str,
    duration: int,
    clip_count: int,
) -> TitleBankEntry:
    classification = classify_topic(topic)
    seo_title = _normalize_display(topic.title() if topic.islower() else topic)
    if not seo_title[0].isupper():
        seo_title = seo_title[:1].upper() + seo_title[1:]
    return _make_entry(
        title=seo_title,
        subtopic=scope.domain,
        category=scope.domain,
        intent="how_to" if scope.instructional_intent else "explainer",
        difficulty="intermediate",
        platform=platform,
        duration=duration,
        clip_count=clip_count,
        content_strategy=classification.content_strategy,
        source_provider="specific_topic_plan",
        trend_score=0.5,
        educational_value=0.9,
        viral_potential=0.55,
    )


def _make_entry(
    *,
    title: str,
    subtopic: str,
    category: str,
    intent: str,
    difficulty: str,
    platform: str,
    duration: int,
    clip_count: int,
    content_strategy: str,
    source_provider: str,
    trend_score: float,
    educational_value: float | None = None,
    viral_potential: float | None = None,
) -> TitleBankEntry:
    del platform
    keywords = list(dict.fromkeys(normalize_title(title).split()))[:8]
    title_id = f"title_{md5(normalize_title(title).encode('utf-8')).hexdigest()[:10]}"
    edu = educational_value
    if edu is None:
        edu = 0.82 if intent in {"how_to", "technique", "mistake_fix"} else 0.62
    viral = viral_potential
    if viral is None:
        viral = min(1.0, 0.45 + trend_score * 0.35 + (0.1 if intent in {"listicle", "challenge", "myth_busting"} else 0.0))
    return TitleBankEntry(
        title_id=title_id,
        title=title,
        subtopic=subtopic,
        category=category,
        intent=intent,
        difficulty=difficulty,
        estimated_viral_potential=viral,
        educational_value=edu,
        trend_score=trend_score,
        source_provider=source_provider,
        keywords=keywords,
        suggested_duration=duration,
        suggested_clip_count=clip_count,
        content_strategy=content_strategy,
    )


def _resolve_seed_pack(scope: TopicScopeResult) -> tuple[dict[str, Any], ...]:
    if scope.domain == "fishing":
        if scope.scope == "semi_specific":
            anchors = " ".join(scope.anchor_tokens).lower()
            species = next((item for item in FISHING_SPECIES if item in anchors), "")
            if species:
                filtered = [
                    item
                    for item in FISHING_SUBCATEGORY_SEEDS
                    if species in str(item["subtopic"]).lower() or species in " ".join(item.get("templates") or ()).lower()
                ]
                if filtered:
                    return tuple(filtered)
        return FISHING_SUBCATEGORY_SEEDS

    generic = []
    for seed in GENERIC_SUBCATEGORY_SEEDS:
        generic.append(dict(seed))
    return tuple(generic)


def _render_template(template: str, *, topic: str, n: int, anchor: str) -> str:
    text = template.format(topic=topic, anchor=anchor, n=n)
    return _normalize_display(text)


def _topic_label(topic: str, scope: TopicScopeResult) -> str:
    if scope.scope == "broad":
        return topic.strip()
    if scope.anchor_tokens:
        return " ".join(scope.anchor_tokens[:3])
    return topic.strip()


def _title_skeleton(title: str) -> str:
    skeleton = normalize_title(title)
    skeleton = re.sub(r"\b\d+\b", "{n}", skeleton)
    skeleton = re.sub(r"\b(zander|pike|carp|bass|trout|fish|fishing)\b", "{fish}", skeleton)
    return skeleton


def _near_duplicate(left: str, right: str) -> bool:
    left_words = set(left.split())
    right_words = set(right.split())
    if not left_words or not right_words:
        return False
    overlap = len(left_words & right_words)
    union = len(left_words | right_words)
    return (overlap / union) >= NEAR_DUPLICATE_THRESHOLD


def _is_bad_generic_title(normalized: str, category: str) -> bool:
    if len(normalized.split()) < 4:
        return True
    topic_token = category if category != "general" else "topic"
    for pattern in BAD_GENERIC_PATTERNS:
        if re.fullmatch(pattern.format(topic=re.escape(topic_token)), normalized):
            return True
    banned = (f"best {topic_token}", f"{topic_token} tips", f"how to {topic_token}", f"{topic_token} method")
    return normalized in banned


def _has_instructional_intent(text: str) -> bool:
    return any(marker in text for marker in INSTRUCTIONAL_INTENT_MARKERS)


def _normalize_display(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


__all__ = [
    "BUILDER_VERSION",
    "DEFAULT_TITLE_TARGET",
    "TitleBankEntry",
    "TitleBankResult",
    "TopicScopeResult",
    "build_title_bank",
    "deduplicate_title_entries",
    "detect_topic_scope",
    "normalize_title",
    "title_passes_topic_authority",
]
