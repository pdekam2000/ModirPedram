"""Channel topic → fresh story ideation with anti-repetition memory."""

from __future__ import annotations

import hashlib
import json
import logging
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
from content_brain.execution.instagram_perfumery_recipes import (
    INSTAGRAM_PERFUMERY_CTA,
    INSTAGRAM_PERFUMERY_POOL,
    INSTAGRAM_PERFUMERY_PRESENTER,
    INSTAGRAM_PERFUMERY_SETTINGS,
    famous_perfumes_text,
    format_ingredient_summary,
    ingredient_memory_key,
)
from content_brain.execution.youtube_science_channel import (
    PRESENTER_DIRECTIVE,
    SCIENCE_CTA_POOL,
    SCIENCE_ENDING_POOL,
    SCIENCE_FACT_POOL,
    SCIENCE_SETTING_POOL,
    SCIENCE_VISUAL_HOOK_POOL,
    TOPIC_SUMMARY,
    default_duration_for_platform,
    is_science_youtube_platform,
)

IDEATION_VERSION = "channel_story_ideation_v8_dedup_50_facts"
MEMORY_RELATIVE_PATH = Path("data") / "story_memory" / "channel_story_history.jsonl"
DEFAULT_CHANNEL_TOPIC = TOPIC_SUMMARY

logger = logging.getLogger(__name__)

MAX_WORDS_PER_CLIP = 35
MAX_WORDS_TOTAL = 70
TITLE_DEDUP_WINDOW = 50
SCIENCE_FACT_DEDUP_WINDOW = 50
SEO_TITLE_RETRY_ATTEMPTS = 5

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

PERFUMERY_TOPIC_MARKERS = (
    "perfume",
    "fragrance",
    "perfumery",
    "ingredient",
    "olfactive",
    "fragrance secrets",
)

BEAUTY_TOPIC_MARKERS = (
    "skincare",
    "beauty recipe",
    "face mask",
    "hair treatment",
    "beauty recipes",
)


def _platform_key(platform: str) -> str:
    normalized = str(platform or "").strip().lower()
    if normalized in {"instagram_reels", "instagram"}:
        return "instagram"
    if normalized in {"youtube_shorts", "youtube"}:
        return "youtube"
    return normalized or "youtube"


def _recent_memory_rows(
    history: list[dict[str, Any]],
    *,
    platform: str,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_platform = _platform_key(platform)
    rows: list[dict[str, Any]] = []
    for row in reversed(history):
        row_platform = _platform_key(str(row.get("target_platform") or row.get("platform") or ""))
        if row_platform and normalized_platform and row_platform != normalized_platform:
            continue
        rows.append(row)
        if len(rows) >= max(0, int(limit)):
            break
    rows.reverse()
    return rows


def get_last_n_titles(
    n: int,
    platform: str,
    *,
    history: list[dict[str, Any]] | None = None,
) -> list[str]:
    rows = _recent_memory_rows(list(history or []), platform=platform, limit=max(0, int(n)))
    return [_normalize(str(row.get("title") or "")) for row in rows if _normalize(str(row.get("title") or ""))]


def _title_is_duplicate(
    title: str,
    history: list[dict[str, Any]],
    *,
    target_platform: str,
    window: int = TITLE_DEDUP_WINDOW,
) -> bool:
    normalized = _normalize(title).lower()
    if not normalized:
        return False
    for row in _recent_memory_rows(history, platform=target_platform, limit=window):
        prior = _normalize(str(row.get("title") or "")).lower()
        if prior and prior == normalized:
            return True
    return False


def _science_fact_key_from_fact(fact: dict[str, Any]) -> str:
    return _normalize(str(fact.get("title") or fact.get("hook") or "")).lower()


def _science_fact_keys_from_row(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    stored = _normalize(str(row.get("science_fact_key") or ""))
    if stored:
        keys.add(stored.lower())
    title = _normalize(str(row.get("title") or ""))
    if title:
        keys.add(title.lower())
    for tag in row.get("novelty_tags") or []:
        token = str(tag or "").strip()
        if token.lower().startswith("fact:"):
            keys.add(token.split(":", 1)[1].strip().lower())
    logline = str(row.get("logline") or "").lower()
    for fact in SCIENCE_FACT_POOL:
        hook = str(fact.get("hook") or "").lower()
        fact_title = _science_fact_key_from_fact(fact)
        if hook and hook in logline:
            keys.add(fact_title)
        if fact_title and fact_title in title.lower():
            keys.add(fact_title)
    return {key for key in keys if key}


def get_last_n_science_facts(
    n: int,
    platform: str,
    *,
    history: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Return recent science-fact keys for a platform (chronological)."""
    if _platform_key(platform) != "youtube":
        return []
    facts: list[str] = []
    seen: set[str] = set()
    for row in reversed(list(history or [])):
        row_platform = _platform_key(str(row.get("target_platform") or row.get("platform") or ""))
        if row_platform != "youtube":
            continue
        for key in _science_fact_keys_from_row(row):
            if key in seen:
                continue
            seen.add(key)
            facts.append(key)
        if len(facts) >= max(0, int(n)):
            break
    facts.reverse()
    return facts


def _used_science_facts_from_history(
    history: list[dict[str, Any]],
    *,
    target_platform: str,
    limit: int = SCIENCE_FACT_DEDUP_WINDOW,
) -> set[str]:
    return set(get_last_n_science_facts(limit, target_platform, history=history))


def _select_science_fact(*, used_facts: set[str], attempt: int) -> dict[str, Any]:
    available = [
        dict(fact)
        for fact in SCIENCE_FACT_POOL
        if _science_fact_key_from_fact(fact) not in used_facts
    ]
    pool = available or [dict(fact) for fact in SCIENCE_FACT_POOL]
    index = (secrets.randbelow(len(pool)) + attempt) % len(pool)
    return pool[index]


def _is_instagram_platform(target_platform: str) -> bool:
    return str(target_platform or "").strip().lower() in {"instagram_reels", "instagram"}


def _is_perfumery_platform(target_platform: str, channel_topic: str) -> bool:
    """Instagram perfumery education lane (active channel default)."""
    if not _is_instagram_platform(target_platform):
        return False
    topic = str(channel_topic or "").lower()
    if any(marker in topic for marker in BEAUTY_TOPIC_MARKERS) and not any(
        marker in topic for marker in PERFUMERY_TOPIC_MARKERS
    ):
        return False
    if any(marker in topic for marker in PERFUMERY_TOPIC_MARKERS):
        return True
    # Instagram channel is currently perfumery education by default.
    return True


def _is_beauty_platform(target_platform: str, channel_topic: str) -> bool:
    """Instagram skincare/beauty lane — only when topic clearly requests beauty recipes."""
    if not _is_instagram_platform(target_platform):
        return False
    if _is_perfumery_platform(target_platform, channel_topic):
        return False
    topic = str(channel_topic or "").lower()
    return any(marker in topic for marker in BEAUTY_TOPIC_MARKERS)


def _is_science_platform(target_platform: str, channel_topic: str) -> bool:
    return is_science_youtube_platform(target_platform, channel_topic)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:'\w+)?\b", str(text or "")))


def _trim_narrator_line(text: str, *, max_words: int = MAX_WORDS_PER_CLIP) -> str:
    cleaned = _normalize(text)
    if not cleaned:
        return ""
    words = re.findall(r"\b\w+(?:'\w+)?\b", cleaned)
    if len(words) <= max_words:
        return cleaned

    trimmed_words = words[:max_words]
    candidate = " ".join(trimmed_words)
    sentence_end = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_end > len(candidate) * 0.45:
        return candidate[: sentence_end + 1].strip()

    partial = cleaned
    for _ in range(len(words) - max_words + 1):
        cut = partial.rfind(" ")
        if cut <= 0:
            break
        partial = partial[:cut].rstrip(" ,;:-")
        if _word_count(partial) <= max_words:
            sentence_end = max(partial.rfind("."), partial.rfind("!"), partial.rfind("?"))
            if sentence_end > 0:
                return partial[: sentence_end + 1].strip()
            return f"{partial}."
    return f"{candidate}."


def _validate_and_trim_narrator_lines(lines: list[str]) -> list[str]:
    trimmed: list[str] = []
    total_words = 0
    for raw in lines:
        line = _trim_narrator_line(raw, max_words=MAX_WORDS_PER_CLIP)
        if not line:
            continue
        words = _word_count(line)
        remaining = MAX_WORDS_TOTAL - total_words
        if remaining <= 0:
            break
        if words > remaining:
            line = _trim_narrator_line(line, max_words=remaining)
            words = _word_count(line)
        if line:
            trimmed.append(line)
            total_words += words
    return trimmed


def _science_narrator_lines(*, hook: str, setup: str, twist: str, cta: str) -> list[str]:
    clip1 = _trim_narrator_line(f"{hook} {setup}")
    clip2 = _trim_narrator_line(f"{twist} {cta}")
    return _validate_and_trim_narrator_lines([clip1, clip2])


def _beauty_narrator_lines(*, recipe_name: str, ingredients_text: str, skin_benefit: str) -> list[str]:
    short_ingredients = ingredients_text
    if _word_count(ingredients_text) > 12:
        parts = [part.strip() for part in re.split(r",| and ", ingredients_text) if part.strip()]
        short_ingredients = ", ".join(parts[:3])
    clip1 = _trim_narrator_line(
        f"Today I'm making {recipe_name}. You need {short_ingredients}."
    )
    clip2 = _trim_narrator_line(
        f"See the {skin_benefit} after application. {INSTAGRAM_RECIPE_CTA}."
    )
    return _validate_and_trim_narrator_lines([clip1, clip2])


def _perfumery_narrator_lines(
    *,
    ingredient_name: str,
    origin: str,
    scent_profile: str,
    perfume_role: str,
    famous_perfumes: str,
    fun_fact: str,
) -> list[str]:
    short_origin = origin.split(",")[0].strip() if origin else "around the world"
    short_scent = scent_profile
    if _word_count(scent_profile) > 8:
        parts = [part.strip() for part in scent_profile.split(",") if part.strip()]
        short_scent = ", ".join(parts[:3])
    clip1 = _trim_narrator_line(
        f"Today we explore {ingredient_name}. It comes from {short_origin} and smells {short_scent}."
    )
    perfume_example = famous_perfumes.split(",")[0].strip() if famous_perfumes else "iconic classics"
    fact = fun_fact.rstrip(".!?")
    clip2 = _trim_narrator_line(
        f"Perfumers use this as a {perfume_role}. Famous in {perfume_example}. "
        f"{fact}. {INSTAGRAM_PERFUMERY_CTA}"
    )
    return _validate_and_trim_narrator_lines([clip1, clip2])


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
        for key in ("recipe_name", "ingredient_name"):
            name = _normalize(str(row.get(key) or ""))
            if name:
                used.add(name.lower())
        title = _normalize(str(row.get("title") or ""))
        if title:
            used.add(title.lower())
        for tag in row.get("novelty_tags") or []:
            token = str(tag or "").strip()
            lowered = token.lower()
            if lowered.startswith("recipe:") or lowered.startswith("ingredient:"):
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


def _select_instagram_ingredient(*, used_ingredients: set[str], attempt: int) -> dict[str, Any]:
    available = [
        dict(item)
        for item in INSTAGRAM_PERFUMERY_POOL
        if str(item.get("ingredient_name") or "").strip().lower() not in used_ingredients
    ]
    pool = available or [dict(item) for item in INSTAGRAM_PERFUMERY_POOL]
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
    clip_narrator_lines: list[str] = field(default_factory=list)
    science_fact_key: str = ""
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
    perfumery_mode: bool = False,
) -> list[str]:
    if clip_count == 2:
        return _two_clip_story_beats(
            idea,
            beauty_mode=beauty_mode,
            science_mode=science_mode,
            perfumery_mode=perfumery_mode,
        )
    if science_mode:
        beats = [
            f"Open with hook (0-2s): {idea.visual_hook}",
            f"Setup (2-8s): {idea.conflict}",
            f"Visual explanation (8-22s): {idea.twist_or_reveal} with cinematic scientific visuals",
            f"Twist/payoff + CTA (22-30s): {idea.ending_beat}",
        ]
    elif perfumery_mode:
        beats = [
            f"Show raw ingredient macros — {idea.visual_hook}",
            f"Teach origin and scent profile in {idea.setting}",
            f"Show perfume role and famous fragrance examples — {idea.twist_or_reveal}",
            f"Deliver fun fact and close with {idea.ending_beat}",
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
    perfumery_mode: bool = False,
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
            "Presenter finishes speaking completely, then holds a 2-3 second silent reaction/pause shot (3s) — "
            f"{idea.ending_beat}. "
            "Visual resolution before cut. NEVER end mid-sentence."
        )
    elif perfumery_mode:
        clip1 = (
            "Clip 1 (15s) Ingredient + Origin + Scent: Presenter says "
            f'\"Today we explore {idea.title}.\" '
            f"Macro close-ups of the raw material in {idea.setting}. "
            f"Teach origin and scent: {idea.conflict}. Setup COMPLETE."
        )
        clip2 = (
            "Clip 2 (15s) Role + Famous Perfumes + Fun Fact: Show extraction or blending (8s). "
            f"Reveal perfume role and icons — {idea.twist_or_reveal} (4s). "
            "Presenter finishes speaking, then 2-3 second silent elegant pause (3s). "
            f'HARD ENDING: Presenter says \"{INSTAGRAM_PERFUMERY_CTA}\". '
            "Visual resolution before cut. Viewer learns one ingredient completely."
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
            "Presenter finishes speaking, then 2-3 second silent reaction/pause on the glow result (3s). "
            f'HARD ENDING: Presenter says \"{INSTAGRAM_RECIPE_CTA}\". '
            "Visual resolution before cut. Viewer knows the recipe and sees the payoff."
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
            "handoff": (
                "The presenter holds the finished mask mixture, ready to apply, final frame ready for handoff"
            ),
        },
        clip_beat_outline=[],
        channel_topic=channel_topic,
        niche=category,
        diversity_mode=diversity_mode,
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count, beauty_mode=True)
    idea.clip_narrator_lines = _beauty_narrator_lines(
        recipe_name=recipe_name,
        ingredients_text=ingredients_text,
        skin_benefit=skin_benefit,
    )
    idea.story_hash = _story_hash(idea)
    idea.prompt_hash = _prompt_hash(idea.rich_story_text())
    return idea


def _build_perfumery_candidate(
    *,
    channel_topic: str,
    niche: str,
    style: str,
    mood: str,
    clip_count: int,
    diversity_mode: str,
    banned_terms: list[str],
    used_ingredients: set[str],
    attempt: int,
) -> ChannelStoryIdea:
    ingredient = _select_instagram_ingredient(used_ingredients=used_ingredients, attempt=attempt)
    setting = INSTAGRAM_PERFUMERY_SETTINGS[
        (secrets.randbelow(len(INSTAGRAM_PERFUMERY_SETTINGS)) + attempt) % len(INSTAGRAM_PERFUMERY_SETTINGS)
    ]
    ingredient_name = str(ingredient.get("ingredient_name") or "Fragrance Ingredient")
    origin = str(ingredient.get("origin") or "perfume laboratories worldwide")
    scent_profile = str(ingredient.get("scent_profile") or "complex aromatic character")
    perfume_role = str(ingredient.get("perfume_role") or "heart note")
    famous = famous_perfumes_text(ingredient)
    fun_fact = str(ingredient.get("fun_fact") or "Perfumers guard this material like treasure.")
    category = str(ingredient.get("category") or "essential_oils")
    scientific_name = str(ingredient.get("scientific_name") or "")
    extraction_method = str(ingredient.get("extraction_method") or "")

    character = INSTAGRAM_PERFUMERY_PRESENTER
    title = ingredient_name
    summary = format_ingredient_summary(ingredient)
    logline = (
        f"In {setting}, the presenter teaches {ingredient_name} "
        f"({scientific_name}). Origin: {origin}. Scent: {scent_profile}. "
        f"Role: {perfume_role}. Famous in: {famous}. Fun fact: {fun_fact}."
    )
    conflict = f"from {origin}; smells {scent_profile}"
    visual_hook = f"macro close-up of {ingredient_name} texture, color, and aromatic detail"
    emotional_hook = f"{mood or 'elegant curiosity'} as the fragrance secret is revealed"
    twist = f"used as a {perfume_role} in {famous or 'iconic perfumes'}; {fun_fact}"
    ending = f"{INSTAGRAM_PERFUMERY_CTA} — {ingredient_name} fragrance secret"
    tags = [
        ingredient_memory_key(ingredient_name),
        category,
        perfume_role,
        extraction_method or "fragrance education",
        style or "elegant mysterious",
        diversity_mode,
    ]

    idea = ChannelStoryIdea(
        unique_story_id=f"story_{hashlib.sha256(f'{ingredient_name}:{attempt}'.encode()).hexdigest()[:12]}",
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
            "lighting": "warm golden rim light with soft amber highlights on bottles and botanicals",
            "camera": "macro ingredient textures, elegant product inserts, perfume blending close-ups",
            "palette": "amber, gold, deep greens, crystal glass, sophisticated dark wood",
            "wardrobe": "elegant dark or cream blouse suited to luxury fragrance education",
            "handoff": (
                f"The presenter holds {ingredient_name} beside a perfume bottle, final frame ready for handoff"
            ),
        },
        clip_beat_outline=[],
        channel_topic=channel_topic,
        niche=category or niche or "perfumery education",
        diversity_mode=diversity_mode,
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count, perfumery_mode=True)
    idea.clip_narrator_lines = _perfumery_narrator_lines(
        ingredient_name=ingredient_name,
        origin=origin,
        scent_profile=scent_profile,
        perfume_role=perfume_role,
        famous_perfumes=famous,
        fun_fact=fun_fact,
    )
    idea.story_hash = _story_hash(idea)
    idea.prompt_hash = _prompt_hash(idea.rich_story_text() + " " + summary)
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
    used_science_facts: set[str] | None = None,
) -> ChannelStoryIdea:
    setting_pool = SCIENCE_SETTING_POOL
    fact = _select_science_fact(used_facts=used_science_facts or set(), attempt=attempt)
    seed = secrets.randbelow(len(SCIENCE_FACT_POOL))
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
    tags = [
        pillar,
        setting.split(" ", 1)[0],
        "science",
        style or "cinematic documentary",
        diversity_mode,
        f"fact:{_science_fact_key_from_fact(fact)}",
    ]

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
        science_fact_key=_science_fact_key_from_fact(fact),
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count, science_mode=True)
    idea.clip_narrator_lines = _science_narrator_lines(
        hook=hook,
        setup=setup,
        twist=twist,
        cta=cta,
    )
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
    used_science_facts: set[str] | None = None,
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
            used_science_facts=used_science_facts,
        )
    if _is_perfumery_platform(target_platform, channel_topic):
        return _build_perfumery_candidate(
            channel_topic=channel_topic,
            niche=niche,
            style=style,
            mood=mood,
            clip_count=clip_count,
            diversity_mode=diversity_mode,
            banned_terms=banned_terms,
            used_ingredients=used_recipes or set(),
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
    *,
    target_platform: str = "youtube_shorts",
) -> tuple[bool, str, dict[str, Any]]:
    """Return (ok, reason, metrics)."""
    metrics: dict[str, Any] = {"checks": []}
    if not history:
        return True, "", metrics

    if _title_is_duplicate(idea.title, history, target_platform=target_platform):
        return False, "recent_duplicate_title", metrics

    if idea.science_fact_key:
        used_facts = _used_science_facts_from_history(
            history,
            target_platform=target_platform,
            limit=SCIENCE_FACT_DEDUP_WINDOW,
        )
        if idea.science_fact_key.lower() in used_facts:
            return False, "recent_duplicate_science_fact", metrics

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
    duration_seconds: int | None = None,
    clip_count: int = 2,
    diversity_mode: str = DEFAULT_DIVERSITY_MODE,
    previous_story_memory: list[dict[str, Any]] | None = None,
    attempt_offset: int = 0,
) -> ChannelStoryIdea:
    history = list(previous_story_memory or [])
    banned = _banned_terms_from_history(history)
    used_recipes = _used_recipe_names_from_history(history)
    used_science_facts = _used_science_facts_from_history(
        history,
        target_platform=target_platform,
        limit=SCIENCE_FACT_DEDUP_WINDOW,
    )
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
            used_science_facts=used_science_facts,
        )
        if _title_is_duplicate(candidate.title, history, target_platform=target_platform):
            used_science_facts.add(candidate.science_fact_key.lower())
            continue
        ok, reason, _metrics = check_story_similarity(
            candidate,
            history,
            target_platform=target_platform,
        )
        if ok:
            return candidate
        history = history + [candidate.to_dict()]
        used_recipes.add(candidate.title.strip().lower())
        if candidate.science_fact_key:
            used_science_facts.add(candidate.science_fact_key.lower())

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
        used_science_facts=used_science_facts,
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
    narrator_lines = list(idea.clip_narrator_lines or [])
    dialogue_lines = [
        {
            "speaker": "Presenter",
            "line": line,
            "clip_index": index + 1,
            "word_count": _word_count(line),
        }
        for index, line in enumerate(narrator_lines)
    ]
    return {
        "topic": idea.channel_topic,
        "story_blueprint": {
            "hook": idea.visual_hook,
            "setup": idea.logline,
            "genre": idea.niche or "perfumery education",
            "scene_progression": list(idea.clip_beat_outline),
            "opening_hook": idea.visual_hook,
            "escalation": idea.twist_or_reveal,
            "payoff": idea.ending_beat,
            "clip_narrator_lines": narrator_lines,
            "narrator_word_limits": {
                "max_words_per_clip": MAX_WORDS_PER_CLIP,
                "max_words_total": MAX_WORDS_TOTAL,
                "clip_word_counts": [_word_count(line) for line in narrator_lines],
                "total_word_count": sum(_word_count(line) for line in narrator_lines),
            },
        },
        "dialogue_plan": {
            "lines": dialogue_lines,
            "narrator_lines": narrator_lines,
        },
        "environment_plan": {
            "primary_setting": idea.setting,
            "setting": idea.setting,
            "environment": idea.setting,
        },
        "emotion_plan": {"dominant_emotion": idea.emotional_hook},
        "characters": [{"name": idea.main_character, "role": "protagonist"}],
        "continuity_anchors": dict(idea.continuity_anchors),
    }


def _apply_seo_title_to_idea(
    idea: ChannelStoryIdea,
    *,
    target_platform: str,
    project_root: str | Path | None = None,
    story_memory: list[dict[str, Any]] | None = None,
    exclude_power_words: list[str] | None = None,
) -> dict[str, Any]:
    from content_brain.story.seo_title_generator import generate_seo_title

    seo_meta = generate_seo_title(
        content_title=idea.title,
        logline=idea.logline,
        visual_hook=idea.visual_hook,
        target_platform=target_platform,
        niche=idea.niche,
        project_root=project_root,
        story_memory=story_memory,
        exclude_power_words=exclude_power_words,
    )
    seo_title = _normalize(str(seo_meta.get("seo_title") or ""))
    if seo_title:
        idea.title = seo_title[:120]
    if (
        _is_instagram_platform(target_platform)
        and not seo_meta.get("openai_applied")
    ):
        logger.error(
            "OpenAI SEO title failed for Instagram: %s",
            seo_meta.get("notes") or seo_meta.get("seo_title") or idea.title,
        )
    return seo_meta


def ideate_and_persist_channel_story(
    *,
    project_root: str | Path,
    channel_topic: str,
    niche: str = "",
    target_platform: str = "youtube_shorts",
    style: str = "cinematic",
    mood: str = "surprised laughter",
    duration_seconds: int | None = None,
    clip_count: int = 2,
    diversity_mode: str = DEFAULT_DIVERSITY_MODE,
    persist: bool = True,
    exclude_power_words: list[str] | None = None,
) -> dict[str, Any]:
    memory = load_story_memory(project_root)
    resolved_duration = int(duration_seconds or default_duration_for_platform(target_platform))
    idea: ChannelStoryIdea | None = None
    seo_title_meta: dict[str, Any] = {}
    for seo_attempt in range(SEO_TITLE_RETRY_ATTEMPTS):
        idea = generate_channel_story_idea(
            channel_topic=channel_topic,
            niche=niche,
            target_platform=target_platform,
            style=style,
            mood=mood,
            duration_seconds=resolved_duration,
            clip_count=clip_count,
            diversity_mode=diversity_mode,
            previous_story_memory=memory,
            attempt_offset=seo_attempt * MAX_IDEATION_ATTEMPTS,
        )
        seo_title_meta = _apply_seo_title_to_idea(
            idea,
            target_platform=target_platform,
            project_root=project_root,
            story_memory=memory,
            exclude_power_words=exclude_power_words,
        )
        if not _title_is_duplicate(idea.title, memory, target_platform=target_platform):
            break
    if idea is None:
        raise RuntimeError("channel_story_ideation_failed")
    if _title_is_duplicate(idea.title, memory, target_platform=target_platform):
        idea.title = f"{idea.title} — Variant {secrets.token_hex(3)}"
    ok, reason, metrics = check_story_similarity(idea, memory, target_platform=target_platform)
    entry = {
        "channel_topic": channel_topic,
        "target_platform": target_platform,
        "unique_story_id": idea.unique_story_id,
        "seo_power_word": str(seo_title_meta.get("power_word_used") or ""),
        "title": idea.title,
        "science_fact_key": idea.science_fact_key,
        "recipe_name": idea.title,
        "ingredient_name": idea.title if _is_instagram_platform(target_platform) else "",
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
    brief = channel_story_idea_to_runway_brief(idea, clip_count=clip_count, duration_seconds=resolved_duration)
    return {
        "channel_story_idea": idea.to_dict(),
        "runway_story_brief": brief.to_dict(),
        "story_package": channel_story_idea_to_story_package(idea),
        "story_summary": idea.logline,
        "authoritative_topic": idea.rich_story_text(),
        "story_title": idea.title,
        "title": idea.title,
        "hook": idea.visual_hook,
        "seo_title_meta": seo_title_meta,
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
    exclude_power_words = [
        str(word).strip()
        for word in (payload.get("exclude_seo_power_words") or [])
        if str(word).strip()
    ]

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
        ok, reason, metrics = check_story_similarity(idea, memory, target_platform=target_platform)
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
        exclude_power_words=exclude_power_words,
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
    "SCIENCE_FACT_DEDUP_WINDOW",
    "TITLE_DEDUP_WINDOW",
    "get_last_n_science_facts",
    "get_last_n_titles",
    "MAX_WORDS_PER_CLIP",
    "MAX_WORDS_TOTAL",
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
