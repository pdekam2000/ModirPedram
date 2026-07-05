"""Channel topic → fresh story ideation with anti-repetition memory."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.runway_story_brief_builder import (
    RunwayStoryBrief,
    StoryBriefAnchors,
    build_runway_story_brief,
)
from content_brain.execution.instagram_skincare_recipes import (
    INSTAGRAM_RECIPE_CTA,
    INSTAGRAM_RECIPE_POOL,
    INSTAGRAM_RECIPE_SETTINGS,
    format_ingredients_list,
    recipe_memory_key,
)
from content_brain.execution.youtube_science_channel import (
    PRESENTER_DIRECTIVE,
    SCIENCE_CTA_POOL,
    SCIENCE_ENDING_POOL,
    SCIENCE_FACT_POOL,
    SCIENCE_SETTING_POOL,
    SCIENCE_VISUAL_HOOK_POOL,
    TOPIC_SUMMARY,
    is_science_youtube_platform,
)

IDEATION_VERSION = "channel_story_ideation_v5_instagram_recipes"
MEMORY_RELATIVE_PATH = Path("data") / "story_memory" / "channel_story_history.jsonl"
DEFAULT_CHANNEL_TOPIC = TOPIC_SUMMARY

LOGLINE_SIMILARITY_REJECT = 0.72
PROMPT_SIMILARITY_REJECT = 0.78
MAX_IDEATION_ATTEMPTS = 16
ARCHETYPE_STREAK_REJECT = 3

DIVERSITY_SAFE_VARIETY = "safe_variety"
DIVERSITY_HIGH_VARIETY = "high_variety"
DIVERSITY_EPISODIC_SERIES = "episodic_series"
DEFAULT_DIVERSITY_MODE = DIVERSITY_SAFE_VARIETY

STOPWORDS = frozenset(
    {
        "the",
        "and",
        "with",
        "from",
        "that",
        "this",
        "into",
        "their",
        "about",
        "through",
        "while",
        "where",
        "when",
        "story",
        "stories",
        "funny",
        "video",
        "real",
        "life",
    }
)

SETTING_POOL_SAFE: tuple[dict[str, str], ...] = (
    {"setting": "living room with a couch and coffee table", "object": "startled house cat", "archetype": "pet owner"},
    {"setting": "suburban backyard during a barbecue", "object": "overconfident golden retriever", "archetype": "dog dad"},
    {"setting": "kitchen counter at snack time", "object": "sneaky raccoon on camera", "archetype": "homeowner"},
    {"setting": "dog park on a sunny afternoon", "object": "tiny dog with big attitude", "archetype": "dog walker"},
    {"setting": "office break room with open snacks", "object": "bold office squirrel at the window", "archetype": "employee"},
    {"setting": "apartment balcony with bird feeder", "object": "dramatic parrot reaction", "archetype": "bird lover"},
    {"setting": "driveway security camera view", "object": "goat that refuses to move", "archetype": "homeowner"},
    {"setting": "vet waiting room with nervous pets", "object": "dramatic husky meltdown", "archetype": "pet parent"},
)

SETTING_POOL_HIGH: tuple[dict[str, str], ...] = SETTING_POOL_SAFE + (
    {"setting": "birthday party living room", "object": "cake-stealing dog", "archetype": "party host"},
    {"setting": "supermarket pet aisle", "object": "talkative African grey parrot", "archetype": "shopper"},
    {"setting": "baby monitor nursery view", "object": "protective cat guarding crib", "archetype": "new parent"},
    {"setting": "pool deck on a hot day", "object": "dog afraid of water", "archetype": "pool owner"},
)

CONFLICT_POOL: tuple[str, ...] = (
    "everyone expects a calm moment until the animal does the exact opposite",
    "the setup looks normal until one hilarious fail changes everything",
    "the owner tries to stay serious but the pet ruins the plan instantly",
    "a tiny mistake snowballs into the funniest unexpected chain reaction",
    "the camera catches a plot twist nobody saw coming",
    "the animal's reaction is so over-the-top it becomes instantly viral",
)

VISUAL_HOOK_POOL: tuple[str, ...] = (
    "security camera catches the exact second everything goes wrong",
    "slow-motion shows the fail in perfect comedic timing",
    "split-screen compares expectation versus hilarious reality",
    "close-up on the pet's shocked face right before the twist",
    "wide shot reveals the absurd situation in one punchline frame",
)

ENDING_POOL: tuple[str, ...] = (
    "the punchline lands with a freeze-frame and disbelief laughter",
    "the owner gives up and joins the chaos for a perfect ending",
    "the final reaction shot becomes the meme moment viewers replay",
    "one last unexpected beat delivers the twist and instant shareability",
)

INSTAGRAM_PRESENTER = (
    "friendly female skincare educator — bright, clean, approachable, demonstrates recipes on camera"
)


def _is_beauty_platform(target_platform: str, channel_topic: str) -> bool:
    """Instagram-only lane — never infer beauty from shared channel_topic text."""
    platform_key = str(target_platform or "").strip().lower()
    return platform_key in {"instagram_reels", "instagram"}


def _is_science_platform(target_platform: str, channel_topic: str) -> bool:
    return is_science_youtube_platform(target_platform, channel_topic)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", _normalize(text).lower())
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def token_jaccard_similarity(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def story_memory_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / MEMORY_RELATIVE_PATH


def load_story_memory(project_root: str | Path, *, limit: int = 5000) -> list[dict[str, Any]]:
    path = story_memory_path(project_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    except OSError:
        return []
    if limit <= 0:
        return rows
    return rows[-max(1, int(limit)) :]


def append_story_memory(project_root: str | Path, entry: dict[str, Any]) -> Path:
    path = story_memory_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(entry)
    row.setdefault("timestamp", _now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _story_hash(idea: "ChannelStoryIdea") -> str:
    digest = hashlib.sha256(
        f"{idea.title}|{idea.logline}|{idea.setting}|{idea.main_character}|{idea.conflict}".encode("utf-8")
    )
    return digest.hexdigest()


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def _extract_archetype(character: str) -> str:
    lowered = _normalize(character).lower()
    for token in (
        "owner",
        "parent",
        "walker",
        "host",
        "shopper",
        "employee",
        "presenter",
        "creator",
    ):
        if token in lowered:
            return token
    return lowered.split(" ", 1)[0] if lowered else "unknown"


def _used_recipe_names_from_history(history: list[dict[str, Any]]) -> set[str]:
    used: set[str] = set()
    for row in history:
        recipe_name = _normalize(str(row.get("recipe_name") or ""))
        if recipe_name:
            used.add(recipe_name.lower())
        title = _normalize(str(row.get("title") or ""))
        if title:
            used.add(title.lower())
        for tag in row.get("novelty_tags") or []:
            token = str(tag or "").strip()
            if token.lower().startswith("recipe:"):
                used.add(token.split(":", 1)[1].strip().lower())
    return used


def _select_instagram_recipe(*, used_recipes: set[str], attempt: int) -> dict[str, Any]:
    available = [
        dict(recipe)
        for recipe in INSTAGRAM_RECIPE_POOL
        if recipe["recipe_name"].strip().lower() not in used_recipes
    ]
    pool = available or [dict(recipe) for recipe in INSTAGRAM_RECIPE_POOL]
    index = (secrets.randbelow(len(pool)) + attempt) % len(pool)
    return pool[index]


def _banned_terms_from_history(history: list[dict[str, Any]]) -> list[str]:
    banned: list[str] = []
    for row in history[-12:]:
        for key in ("title", "setting", "main_character", "visual_hook", "conflict"):
            value = _normalize(str(row.get(key) or ""))
            if value:
                banned.extend(list(_tokens(value))[:6])
        for tag in row.get("novelty_tags") or []:
            if tag:
                banned.append(str(tag))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in banned:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:40]


@dataclass
class ChannelStoryIdea:
    unique_story_id: str
    title: str
    logline: str
    main_character: str
    setting: str
    conflict: str
    visual_hook: str
    emotional_hook: str
    twist_or_reveal: str
    ending_beat: str
    novelty_tags: list[str] = field(default_factory=list)
    banned_similarity_terms: list[str] = field(default_factory=list)
    continuity_anchors: dict[str, str] = field(default_factory=dict)
    clip_beat_outline: list[str] = field(default_factory=list)
    channel_topic: str = ""
    niche: str = ""
    diversity_mode: str = DEFAULT_DIVERSITY_MODE
    story_hash: str = ""
    prompt_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    def rich_story_text(self) -> str:
        beats = " ".join(f"Clip {index + 1}: {beat}." for index, beat in enumerate(self.clip_beat_outline))
        return _normalize(
            f"{self.logline} Character: {self.main_character}. Setting: {self.setting}. "
            f"Conflict: {self.conflict}. Visual hook: {self.visual_hook}. "
            f"Emotional hook: {self.emotional_hook}. Twist: {self.twist_or_reveal}. "
            f"Ending: {self.ending_beat}. {beats}"
        )


def _clip_beats_for_idea(
    idea: ChannelStoryIdea,
    clip_count: int,
    *,
    beauty_mode: bool = False,
    science_mode: bool = False,
) -> list[str]:
    if clip_count == 2:
        return _two_clip_story_beats(idea, beauty_mode=beauty_mode, science_mode=science_mode)
    if science_mode:
        beats = [
            f"Open with hook (0-2s): {idea.visual_hook}",
            f"Setup (2-8s): {idea.conflict}",
            f"Visual explanation (8-22s): {idea.twist_or_reveal} with cinematic scientific visuals",
            f"Twist/payoff + CTA (22-30s): {idea.ending_beat}",
        ]
    elif beauty_mode:
        beats = [
            f"Show exact ingredients on camera — {idea.conflict}",
            f"Mix the recipe live in {idea.setting} while presenter explains quantities",
            f"Apply treatment on camera — {idea.twist_or_reveal}",
            f"Reveal result and close with {idea.ending_beat}",
        ]
    else:
        beats = [
            f"Open with {idea.visual_hook.lower()} while setting up the funny moment in {idea.setting}",
            f"Build toward {idea.conflict.lower()} featuring {idea.main_character}",
            f"Hit {idea.twist_or_reveal.lower()} with perfect comedic timing",
            f"Close with {idea.ending_beat.lower()} and a shareable punchline",
        ]
    if clip_count <= 1:
        return [beats[0]]
    return beats[:clip_count]


def _two_clip_story_beats(
    idea: ChannelStoryIdea,
    *,
    beauty_mode: bool = False,
    science_mode: bool = False,
) -> list[str]:
    """30s / 2×15s: Hook+Setup (3+10+2s) then Payoff+Ending (8+4+3s)."""
    if science_mode:
        clip1 = (
            "Clip 1 (15s) Hook+Setup: Open with impossible hook (0-2s) — "
            f"{idea.visual_hook}. "
            f"Presenter setup (2-8s) — {idea.main_character} explains {idea.conflict}. "
            "Begin visual explanation (8-15s) — holographic/scientific visuals integrate dynamically. "
            "End on curiosity gap — setup COMPLETE."
        )
        clip2 = (
            "Clip 2 (15s) Payoff+Twist+CTA: Continue visual explanation (8s) — "
            f"{idea.twist_or_reveal}. "
            f"Deliver strangest payoff (4s) — {idea.emotional_hook}. "
            f"HARD ENDING (3s) — {idea.ending_beat}. "
            "NEVER end mid-sentence. Viewer rewarded for watching to the end."
        )
    elif beauty_mode:
        clip1 = (
            "Clip 1 (15s) Ingredients + Mix: Presenter says "
            f'\"Today I\'m making {idea.title}. You need {idea.conflict}.\" '
            f"Show exact quantities, close-ups of each ingredient, and mix live in {idea.setting}. "
            "Setup COMPLETE — mixture ready to apply."
        )
        clip2 = (
            "Clip 2 (15s) Apply + Result: Apply treatment to face/skin on camera (8s). "
            f"Reveal visible result — {idea.twist_or_reveal} (4s). "
            f'HARD ENDING (3s): Presenter says \"{INSTAGRAM_RECIPE_CTA}\". '
            "Viewer knows the recipe and sees the payoff."
        )
    else:
        clip1 = (
            "Clip 1 (15s) Hook+Setup: Open with arresting visual (3s) — "
            f"{idea.visual_hook.lower()} in {idea.setting}. "
            f"Build the situation (10s) — {idea.main_character} and {idea.conflict.lower()} fully established. "
            "End on clear tension (2s) — anticipation held, setup COMPLETE."
        )
        clip2 = (
            "Clip 2 (15s) Payoff+Clear Ending: Deliver the funny moment fully (8s) — "
            f"{idea.twist_or_reveal.lower()}. "
            f"Show character reactions (4s) — {idea.main_character} laughing, shocked, or losing it. "
            f"HARD ENDING (3s) — freeze frame, laugh, or clear resolution: {idea.ending_beat.lower()}. "
            "NEVER end mid-action or mid-sentence. Viewer feels satisfied and complete."
        )
    return [clip1, clip2]


def _build_beauty_candidate(
    *,
    channel_topic: str,
    niche: str,
    style: str,
    mood: str,
    clip_count: int,
    diversity_mode: str,
    banned_terms: list[str],
    used_recipes: set[str],
    attempt: int,
) -> ChannelStoryIdea:
    recipe = _select_instagram_recipe(used_recipes=used_recipes, attempt=attempt)
    setting = INSTAGRAM_RECIPE_SETTINGS[
        (secrets.randbelow(len(INSTAGRAM_RECIPE_SETTINGS)) + attempt) % len(INSTAGRAM_RECIPE_SETTINGS)
    ]
    recipe_name = str(recipe["recipe_name"])
    ingredients = list(recipe.get("ingredients") or [])
    ingredients_text = format_ingredients_list(ingredients)
    skin_benefit = str(recipe.get("skin_benefit") or "healthy glow")
    season = str(recipe.get("season") or "all year")
    occasion = str(recipe.get("occasion") or "daily")
    category = str(recipe.get("category") or "face masks")

    character = INSTAGRAM_PRESENTER
    title = recipe_name
    logline = (
        f"In {setting}, the presenter teaches {recipe_name} — {ingredients_text}. "
        f"Benefits: {skin_benefit}. Season: {season}. Occasion: {occasion}."
    )
    conflict = ingredients_text
    visual_hook = f"macro close-ups of {ingredients_text} measured on a clean tray"
    emotional_hook = f"{mood or 'helpful confidence'} as the recipe comes together step by step"
    twist = f"visible {skin_benefit} result after on-camera application"
    ending = f"{INSTAGRAM_RECIPE_CTA} — {skin_benefit} result reveal"
    tags = [
        recipe_memory_key(recipe_name),
        category,
        season,
        occasion,
        style or "bright aesthetic",
        diversity_mode,
    ]

    idea = ChannelStoryIdea(
        unique_story_id=f"story_{hashlib.sha256(f'{recipe_name}:{attempt}'.encode()).hexdigest()[:12]}",
        title=title,
        logline=logline,
        main_character=character,
        setting=setting,
        conflict=conflict,
        visual_hook=visual_hook,
        emotional_hook=emotional_hook,
        twist_or_reveal=twist,
        ending_beat=ending,
        novelty_tags=tags,
        banned_similarity_terms=list(banned_terms),
        continuity_anchors={
            "character": character,
            "location": setting,
            "lighting": "bright clean daylight with soft highlights on ingredients and skin",
            "camera": "macro ingredient close-ups, overhead mixing shots, face application close-ups",
            "palette": "clean whites, warm wood, soft greens, fresh natural tones",
            "wardrobe": "clean casual top or robe suited to kitchen/bathroom recipe demo",
        },
        clip_beat_outline=[],
        channel_topic=channel_topic,
        niche=category,
        diversity_mode=diversity_mode,
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count, beauty_mode=True)
    idea.story_hash = _story_hash(idea)
    idea.prompt_hash = _prompt_hash(idea.rich_story_text())
    return idea


def _build_science_candidate(
    *,
    channel_topic: str,
    niche: str,
    style: str,
    mood: str,
    clip_count: int,
    diversity_mode: str,
    banned_terms: list[str],
    attempt: int,
) -> ChannelStoryIdea:
    setting_pool = SCIENCE_SETTING_POOL
    fact_pool = SCIENCE_FACT_POOL
    seed = secrets.randbelow(len(fact_pool))
    fact = dict(fact_pool[(seed + attempt) % len(fact_pool)])
    setting_bundle = dict(setting_pool[(seed + attempt) % len(setting_pool)])
    visual_hook = SCIENCE_VISUAL_HOOK_POOL[(seed + attempt * 2) % len(SCIENCE_VISUAL_HOOK_POOL)]
    ending = SCIENCE_ENDING_POOL[(seed + attempt * 3) % len(SCIENCE_ENDING_POOL)]
    cta = SCIENCE_CTA_POOL[(seed + attempt) % len(SCIENCE_CTA_POOL)]

    setting = setting_bundle["setting"]
    pillar = fact.get("pillar") or setting_bundle.get("pillar") or "Science facts"
    sci_visual = setting_bundle.get("visual") or "cinematic scientific visualization"
    topic_label = _normalize(channel_topic) or _normalize(niche) or "Science That Feels Impossible"

    character = (
        "recurring female science presenter — confident, intelligent, elegant modern documentary host "
        f"({PRESENTER_DIRECTIVE[:120]}...)"
    )
    hook = fact["hook"]
    title = fact["title"]
    setup = fact["setup"]
    mechanism = fact["mechanism"]
    twist = fact["twist"]

    logline = (
        f'Hook: "{hook}" In {setting}, {character} explains: {setup} '
        f"Mechanism: {mechanism} Payoff: {twist}"
    )
    conflict = f"{setup} {mechanism}"
    emotional_hook = mood or "intellectual wonder and disbelief"
    twist_reveal = twist
    ending_beat = f"{ending} {cta}"
    tags = [pillar, setting.split(" ", 1)[0], "science", style or "cinematic documentary", diversity_mode]

    idea = ChannelStoryIdea(
        unique_story_id=f"story_{hashlib.sha256(f'{channel_topic}:{attempt}:{seed}'.encode()).hexdigest()[:12]}",
        title=title,
        logline=logline,
        main_character=character,
        setting=setting,
        conflict=conflict,
        visual_hook=f'{hook} — {visual_hook} with {sci_visual}',
        emotional_hook=emotional_hook,
        twist_or_reveal=twist_reveal,
        ending_beat=ending_beat,
        novelty_tags=tags,
        banned_similarity_terms=list(banned_terms),
        continuity_anchors={
            "character": character,
            "location": setting,
            "lighting": "dramatic cinematic rim light, high contrast, premium documentary depth",
            "camera": "slow push-ins, orbit moves, presenter integrated with holographic visuals",
            "palette": "deep blues, silver highlights, clean whites, subtle magenta accents",
            "wardrobe": "stylish modern science presenter — sleek blazer, elegant minimal jewelry, futuristic journalist look",
        },
        clip_beat_outline=[],
        channel_topic=channel_topic,
        niche=niche or "Science That Feels Impossible",
        diversity_mode=diversity_mode,
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count, science_mode=True)
    idea.story_hash = _story_hash(idea)
    idea.prompt_hash = _prompt_hash(idea.rich_story_text())
    return idea


def _build_candidate(
    *,
    channel_topic: str,
    niche: str,
    style: str,
    mood: str,
    clip_count: int,
    diversity_mode: str,
    banned_terms: list[str],
    attempt: int,
    target_platform: str = "youtube_shorts",
    used_recipes: set[str] | None = None,
) -> ChannelStoryIdea:
    if _is_science_platform(target_platform, channel_topic):
        return _build_science_candidate(
            channel_topic=channel_topic,
            niche=niche,
            style=style,
            mood=mood,
            clip_count=clip_count,
            diversity_mode=diversity_mode,
            banned_terms=banned_terms,
            attempt=attempt,
        )
    if _is_beauty_platform(target_platform, channel_topic):
        return _build_beauty_candidate(
            channel_topic=channel_topic,
            niche=niche,
            style=style,
            mood=mood,
            clip_count=clip_count,
            diversity_mode=diversity_mode,
            banned_terms=banned_terms,
            used_recipes=used_recipes or set(),
            attempt=attempt,
        )
    pool = SETTING_POOL_HIGH if diversity_mode == DIVERSITY_HIGH_VARIETY else SETTING_POOL_SAFE
    if diversity_mode == DIVERSITY_EPISODIC_SERIES:
        pool = SETTING_POOL_SAFE

    seed = secrets.randbelow(len(pool))
    bundle = dict(pool[(seed + attempt) % len(pool)])
    conflict = CONFLICT_POOL[(seed + attempt) % len(CONFLICT_POOL)]
    visual_hook = VISUAL_HOOK_POOL[(seed + attempt * 2) % len(VISUAL_HOOK_POOL)]
    ending = ENDING_POOL[(seed + attempt * 3) % len(ENDING_POOL)]

    archetype = bundle.get("archetype") or "content creator"
    setting = bundle["setting"]
    obj = bundle.get("object") or "unexpected animal moment"
    topic_label = _normalize(channel_topic) or _normalize(niche) or DEFAULT_CHANNEL_TOPIC
    character = f"a {archetype} filming {obj} for {topic_label}"
    if diversity_mode == DIVERSITY_EPISODIC_SERIES:
        character = f"the returning {archetype} capturing another viral animal moment"

    title = f"When {obj.title()} Goes Completely Wrong"
    logline = (
        f"In {setting}, {character} captures {conflict}, centered on {obj}. "
        f"The clip delivers one hilarious surprise for {topic_label}."
    )
    emotional_hook = f"{mood or 'surprised laughter'} builds as {obj} steals the scene"
    twist = f"{obj} pulls an unexpected move that flips the whole moment"
    tags = [archetype, setting.split(" ", 1)[0], obj.split(" ", 1)[0], style or "cinematic", diversity_mode]

    idea = ChannelStoryIdea(
        unique_story_id=f"story_{hashlib.sha256(f'{channel_topic}:{attempt}:{seed}'.encode()).hexdigest()[:12]}",
        title=title,
        logline=logline,
        main_character=character,
        setting=setting,
        conflict=conflict,
        visual_hook=visual_hook,
        emotional_hook=emotional_hook,
        twist_or_reveal=twist,
        ending_beat=ending,
        novelty_tags=tags,
        banned_similarity_terms=list(banned_terms),
        continuity_anchors={
            "character": character,
            "location": setting,
            "lighting": "bright natural daylight with crisp mobile-friendly contrast",
            "camera": "handheld phone cam, quick zooms, reaction close-ups",
            "palette": "vivid everyday colors, clean highlights, meme-ready framing",
            "wardrobe": "casual everyday clothes suited to viral comedy clips",
        },
        clip_beat_outline=[],
        channel_topic=channel_topic,
        niche=niche,
        diversity_mode=diversity_mode,
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count, beauty_mode=False)
    idea.story_hash = _story_hash(idea)
    idea.prompt_hash = _prompt_hash(idea.rich_story_text())
    return idea


def check_story_similarity(
    idea: ChannelStoryIdea,
    history: list[dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    """Return (ok, reason, metrics)."""
    metrics: dict[str, Any] = {"checks": []}
    if not history:
        return True, "", metrics

    archetype = _extract_archetype(idea.main_character)
    recent_archetypes = [_extract_archetype(str(row.get("main_character") or "")) for row in history[-ARCHETYPE_STREAK_REJECT:]]
    if len(recent_archetypes) >= ARCHETYPE_STREAK_REJECT and all(item == archetype for item in recent_archetypes):
        return False, "same_character_archetype_streak", metrics

    for row in history:
        prior_title = _normalize(str(row.get("title") or ""))
        if prior_title and prior_title.lower() == _normalize(idea.title).lower():
            return False, "exact_repeated_title", metrics

        prior_setting = _normalize(str(row.get("setting") or ""))
        prior_object = " ".join(sorted(list(_tokens(str(row.get("visual_hook") or "")))[:3]))
        new_object = " ".join(sorted(list(_tokens(idea.visual_hook))[:3]))
        if prior_setting and prior_setting.lower() == idea.setting.lower() and prior_object == new_object:
            return False, "same_core_object_and_setting", metrics

        logline_sim = token_jaccard_similarity(idea.logline, str(row.get("logline") or ""))
        metrics["checks"].append({"logline_similarity": logline_sim, "story_id": row.get("unique_story_id")})
        if logline_sim > LOGLINE_SIMILARITY_REJECT:
            return False, "logline_similarity_above_threshold", metrics

        prompt_sim = token_jaccard_similarity(
            idea.rich_story_text(),
            str(row.get("logline") or "") + " " + str(row.get("setting") or ""),
        )
        if prompt_sim > PROMPT_SIMILARITY_REJECT:
            return False, "prompt_similarity_above_threshold", metrics

    return True, "", metrics


def generate_channel_story_idea(
    *,
    channel_topic: str,
    niche: str = "",
    target_platform: str = "youtube_shorts",
    style: str = "cinematic",
    mood: str = "surprised laughter",
    duration_seconds: int = 30,
    clip_count: int = 2,
    diversity_mode: str = DEFAULT_DIVERSITY_MODE,
    previous_story_memory: list[dict[str, Any]] | None = None,
    attempt_offset: int = 0,
) -> ChannelStoryIdea:
    history = list(previous_story_memory or [])
    banned = _banned_terms_from_history(history)
    used_recipes = _used_recipe_names_from_history(history)
    topic = _normalize(channel_topic) or _normalize(niche) or DEFAULT_CHANNEL_TOPIC

    for attempt in range(MAX_IDEATION_ATTEMPTS):
        candidate = _build_candidate(
            channel_topic=topic,
            niche=niche,
            style=style,
            mood=mood,
            clip_count=max(1, int(clip_count)),
            diversity_mode=diversity_mode or DEFAULT_DIVERSITY_MODE,
            banned_terms=banned,
            attempt=attempt + attempt_offset,
            target_platform=target_platform,
            used_recipes=used_recipes,
        )
        ok, reason, _metrics = check_story_similarity(candidate, history)
        if ok:
            return candidate
        history = history + [candidate.to_dict()]
        used_recipes.add(candidate.title.strip().lower())

    fallback = _build_candidate(
        channel_topic=topic,
        niche=niche,
        style=style,
        mood=mood,
        clip_count=max(1, int(clip_count)),
        diversity_mode=DIVERSITY_HIGH_VARIETY,
        banned_terms=banned,
        attempt=MAX_IDEATION_ATTEMPTS + attempt_offset + secrets.randbelow(99),
        target_platform=target_platform,
        used_recipes=used_recipes,
    )
    fallback.title = f"{fallback.title} — Variant {secrets.token_hex(3)}"
    fallback.story_hash = _story_hash(fallback)
    fallback.prompt_hash = _prompt_hash(fallback.rich_story_text())
    return fallback


def channel_story_idea_to_runway_brief(idea: ChannelStoryIdea, *, clip_count: int, duration_seconds: int) -> RunwayStoryBrief:
    anchors = StoryBriefAnchors(
        character=idea.continuity_anchors.get("character") or idea.main_character,
        location=idea.continuity_anchors.get("location") or idea.setting,
        lighting=idea.continuity_anchors.get("lighting") or "bright natural daylight",
        camera=idea.continuity_anchors.get("camera") or "handheld viral comedy framing",
        palette=idea.continuity_anchors.get("palette") or "vivid everyday colors",
        wardrobe=idea.continuity_anchors.get("wardrobe") or "",
    )
    return RunwayStoryBrief(
        title=idea.title,
        logline=idea.logline,
        subject=idea.title,
        main_character=idea.main_character,
        environment=idea.setting,
        setting=idea.setting,
        conflict=idea.conflict,
        conflict_tension=idea.conflict,
        stakes=idea.emotional_hook,
        emotional_arc=idea.emotional_hook,
        visual_hook=idea.visual_hook,
        opening_hook=idea.visual_hook,
        escalation=idea.twist_or_reveal,
        payoff=idea.ending_beat,
        ending_beat=idea.ending_beat,
        style_direction=idea.niche or "Science That Feels Impossible",
        continuity_anchors=anchors,
        clip_beats=list(idea.clip_beat_outline),
        scene_progression=list(idea.clip_beat_outline),
        source_topic=idea.channel_topic,
        target_platform="youtube_shorts",
        niche_style="cinematic science documentary",
        mood="intellectual wonder",
        clip_count=max(1, int(clip_count)),
        duration_seconds=max(1, int(duration_seconds)),
        builder_version=IDEATION_VERSION,
        warnings=[],
        topic_label=idea.title,
    )


def channel_story_idea_to_story_package(idea: ChannelStoryIdea) -> dict[str, Any]:
    return {
        "topic": idea.channel_topic,
        "story_blueprint": {
            "hook": idea.visual_hook,
            "setup": idea.logline,
            "genre": idea.niche or "skincare education",
            "scene_progression": list(idea.clip_beat_outline),
            "opening_hook": idea.visual_hook,
            "escalation": idea.twist_or_reveal,
            "payoff": idea.ending_beat,
        },
        "environment_plan": {
            "primary_setting": idea.setting,
            "setting": idea.setting,
            "environment": idea.setting,
        },
        "emotion_plan": {"dominant_emotion": idea.emotional_hook},
        "characters": [{"name": idea.main_character, "role": "protagonist"}],
    }


def ideate_and_persist_channel_story(
    *,
    project_root: str | Path,
    channel_topic: str,
    niche: str = "",
    target_platform: str = "youtube_shorts",
    style: str = "cinematic",
    mood: str = "surprised laughter",
    duration_seconds: int = 30,
    clip_count: int = 2,
    diversity_mode: str = DEFAULT_DIVERSITY_MODE,
    persist: bool = True,
) -> dict[str, Any]:
    memory = load_story_memory(project_root)
    idea = generate_channel_story_idea(
        channel_topic=channel_topic,
        niche=niche,
        target_platform=target_platform,
        style=style,
        mood=mood,
        duration_seconds=duration_seconds,
        clip_count=clip_count,
        diversity_mode=diversity_mode,
        previous_story_memory=memory,
    )
    ok, reason, metrics = check_story_similarity(idea, memory)
    entry = {
        "channel_topic": channel_topic,
        "unique_story_id": idea.unique_story_id,
        "title": idea.title,
        "recipe_name": idea.title,
        "logline": idea.logline,
        "main_character": idea.main_character,
        "setting": idea.setting,
        "conflict": idea.conflict,
        "visual_hook": idea.visual_hook,
        "ending_beat": idea.ending_beat,
        "novelty_tags": list(idea.novelty_tags),
        "prompt_hash": idea.prompt_hash,
        "story_hash": idea.story_hash,
        "diversity_mode": diversity_mode,
    }
    memory_path = ""
    if persist:
        memory_path = str(append_story_memory(project_root, entry))
    brief = channel_story_idea_to_runway_brief(idea, clip_count=clip_count, duration_seconds=duration_seconds)
    return {
        "channel_story_idea": idea.to_dict(),
        "runway_story_brief": brief.to_dict(),
        "story_package": channel_story_idea_to_story_package(idea),
        "story_summary": idea.logline,
        "authoritative_topic": idea.rich_story_text(),
        "story_title": idea.title,
        "similarity_ok": ok,
        "similarity_reason": reason,
        "similarity_metrics": metrics,
        "story_memory_path": memory_path,
    }


def apply_channel_story_ideation(
    *,
    project_root: str | Path,
    payload: dict[str, Any],
    channel_topic: str,
    niche: str,
    target_platform: str,
    style: str,
    mood: str,
    duration_seconds: int,
    clip_count: int,
) -> dict[str, Any]:
    """Resolve channel topic vs override and return preflight story fields."""
    topic_mode = str(payload.get("topic_mode") or payload.get("topic_source") or "channel")
    custom_topic = _normalize(str(payload.get("custom_topic") or ""))
    if (
        topic_mode == "custom"
        and custom_topic
        and not bool(payload.get("automation_mode"))
        and not _normalize(str(payload.get("specific_story_override") or payload.get("story_override") or ""))
    ):
        payload = {**payload, "specific_story_override": custom_topic}

    override = _normalize(
        str(payload.get("specific_story_override") or payload.get("story_override") or "")
    )
    diversity_mode = str(payload.get("story_diversity_mode") or DEFAULT_DIVERSITY_MODE)
    persist = not bool(payload.get("skip_story_memory_persist"))

    if override:
        idea = ChannelStoryIdea(
            unique_story_id=f"override_{hashlib.sha256(override.encode()).hexdigest()[:12]}",
            title=override.split(".", 1)[0][:120],
            logline=override,
            main_character="the protagonist",
            setting="a location implied by the override story",
            conflict="the central tension of the override story",
            visual_hook="the opening visual incident of the override story",
            emotional_hook=mood or "surprised laughter",
            twist_or_reveal="the override story's turn",
            ending_beat="the override story's final beat",
            clip_beat_outline=_clip_beats_for_idea(
                ChannelStoryIdea(
                    unique_story_id="tmp",
                    title="tmp",
                    logline=override,
                    main_character="protagonist",
                    setting="setting",
                    conflict="conflict",
                    visual_hook="hook",
                    emotional_hook="emotion",
                    twist_or_reveal="twist",
                    ending_beat="ending",
                ),
                max(1, int(clip_count)),
            ),
            channel_topic=channel_topic,
            niche=niche,
            diversity_mode="story_override",
        )
        idea.story_hash = _story_hash(idea)
        idea.prompt_hash = _prompt_hash(override)
        memory = load_story_memory(project_root)
        ok, reason, metrics = check_story_similarity(idea, memory)
        brief = channel_story_idea_to_runway_brief(idea, clip_count=clip_count, duration_seconds=duration_seconds)
        return {
            "channel_topic": channel_topic,
            "specific_story_override": override,
            "story_override_active": True,
            "channel_story_idea": idea.to_dict(),
            "runway_story_brief": brief.to_dict(),
            "story_package": channel_story_idea_to_story_package(idea),
            "story_summary": override,
            "authoritative_topic": override,
            "story_title": idea.title,
            "story_diversity_mode": "story_override",
            "story_repetition_warning": "" if ok else reason,
            "story_similarity_metrics": metrics,
            "story_ideation_version": IDEATION_VERSION,
        }

    ideation = ideate_and_persist_channel_story(
        project_root=project_root,
        channel_topic=channel_topic,
        niche=niche,
        target_platform=target_platform,
        style=style,
        mood=mood,
        duration_seconds=duration_seconds,
        clip_count=clip_count,
        diversity_mode=diversity_mode,
        persist=persist,
    )
    ideation.update(
        {
            "channel_topic": channel_topic,
            "specific_story_override": "",
            "story_override_active": False,
            "story_diversity_mode": diversity_mode,
            "story_repetition_warning": "",
            "story_ideation_version": IDEATION_VERSION,
        }
    )
    return ideation


__all__ = [
    "ARCHETYPE_STREAK_REJECT",
    "ChannelStoryIdea",
    "DEFAULT_CHANNEL_TOPIC",
    "DEFAULT_DIVERSITY_MODE",
    "IDEATION_VERSION",
    "LOGLINE_SIMILARITY_REJECT",
    "PROMPT_SIMILARITY_REJECT",
    "append_story_memory",
    "apply_channel_story_ideation",
    "channel_story_idea_to_runway_brief",
    "channel_story_idea_to_story_package",
    "check_story_similarity",
    "generate_channel_story_idea",
    "ideate_and_persist_channel_story",
    "load_story_memory",
    "story_memory_path",
    "token_jaccard_similarity",
]
