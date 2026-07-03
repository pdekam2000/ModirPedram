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

IDEATION_VERSION = "channel_story_ideation_v1"
MEMORY_RELATIVE_PATH = Path("data") / "story_memory" / "channel_story_history.jsonl"

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
        "dark",
        "story",
        "stories",
        "fantasy",
        "horror",
        "analog",
    }
)

SETTING_POOL_SAFE: tuple[dict[str, str], ...] = (
    {"setting": "abandoned coastal radio tower at midnight", "object": "magnetic broadcast tape", "archetype": "night technician"},
    {"setting": "flooded subway archive with flickering fluorescents", "object": "waterlogged VHS case", "archetype": "maintenance archivist"},
    {"setting": "derelict rental store after closing", "object": "mislabeled horror tape", "archetype": "closing clerk"},
    {"setting": "root cellar beneath a shuttered farmhouse", "object": "cracked reel-to-reel spool", "object_alt": "static portrait", "archetype": "relative searcher"},
    {"setting": "misty pine ridge above a sleeping town", "object": "emergency flare cache", "archetype": "lost courier"},
    {"setting": "empty bus depot during a power outage", "object": "looping departure board", "archetype": "stranded commuter"},
    {"setting": "salt-stained lighthouse stairwell", "object": "storm-damaged logbook", "archetype": "keeper apprentice"},
    {"setting": "collapsed mine adit behind a thrift shop", "object": "handheld field recorder", "archetype": "urban explorer"},
)

SETTING_POOL_HIGH: tuple[dict[str, str], ...] = SETTING_POOL_SAFE + (
    {"setting": "floating scrap barge in industrial fog", "object": "sonar printout", "archetype": "salvage diver"},
    {"setting": "deserted planetarium with broken star projector", "object": "glass plate negative", "archetype": "night guard"},
    {"setting": "overgrown rail switching yard", "object": "rusted signal lantern", "archetype": "track inspector"},
    {"setting": "condemned hotel ice room", "object": "frosted security mirror", "archetype": "paranormal researcher"},
)

CONFLICT_POOL: tuple[str, ...] = (
    "a repeating signal suggests someone is still broadcasting from inside",
    "a timestamp on the artifact does not match any known recording",
    "the environment reacts as if the protagonist has been here before",
    "a familiar voice appears on a channel that should be dead",
    "the object shows a scene that has not happened yet",
    "every exit route loops back to the same impossible detail",
)

VISUAL_HOOK_POOL: tuple[str, ...] = (
    "a single practical light source cuts through particulate haze",
    "an analog screen flickers with a frame that should not exist",
    "a reflective surface reveals a figure just outside the lens",
    "a handheld object pulses with heat though nothing powers it",
    "wind moves debris in a pattern too deliberate to be natural",
)

ENDING_POOL: tuple[str, ...] = (
    "the protagonist chooses to document the anomaly instead of fleeing",
    "the reveal reframes the channel niche as a warning, not a legend",
    "the final beat leaves one sensory detail unresolved on purpose",
    "the character seals the discovery away, knowing curiosity will return",
)


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
            payload = json.loads(text)
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
    for token in ("technician", "archivist", "clerk", "courier", "keeper", "explorer", "guard", "researcher", "inspector", "diver"):
        if token in lowered:
            return token
    return lowered.split(" ", 1)[0] if lowered else "unknown"


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


def _clip_beats_for_idea(idea: ChannelStoryIdea, clip_count: int) -> list[str]:
    beats = [
        f"{idea.main_character} discovers {idea.visual_hook.lower()} in {idea.setting}",
        f"{idea.main_character} pursues {idea.conflict.lower()} as the space closes in",
        f"{idea.twist_or_reveal} reframes the scene before {idea.ending_beat.lower()}",
        f"The episode resolves with {idea.ending_beat.lower()} while staying inside the channel niche",
    ]
    if clip_count <= 1:
        return [beats[0]]
    if clip_count == 2:
        return [beats[0], beats[2]]
    return beats[:clip_count]


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
) -> ChannelStoryIdea:
    pool = SETTING_POOL_HIGH if diversity_mode == DIVERSITY_HIGH_VARIETY else SETTING_POOL_SAFE
    if diversity_mode == DIVERSITY_EPISODIC_SERIES:
        pool = SETTING_POOL_SAFE

    seed = secrets.randbelow(len(pool))
    bundle = dict(pool[(seed + attempt) % len(pool)])
    conflict = CONFLICT_POOL[(seed + attempt) % len(CONFLICT_POOL)]
    visual_hook = VISUAL_HOOK_POOL[(seed + attempt * 2) % len(VISUAL_HOOK_POOL)]
    ending = ENDING_POOL[(seed + attempt * 3) % len(ENDING_POOL)]

    archetype = bundle.get("archetype") or "witness"
    setting = bundle["setting"]
    obj = bundle.get("object") or bundle.get("object_alt") or "anomalous artifact"
    character = f"a cautious {archetype} investigating the channel's latest unease"
    if diversity_mode == DIVERSITY_EPISODIC_SERIES:
        character = f"the returning {archetype} facing a new episode in the same unsettling world"

    title = f"The {obj.replace(' ', ' ').title()} at {setting.split(' ')[0].title()} {setting.split(' ')[1].title()}"
    logline = (
        f"In {setting}, {character} confronts {conflict} after encountering {obj}. "
        f"The incident fits the channel's unsettling niche without repeating a prior episode."
    )
    emotional_hook = f"{mood or 'uneasy curiosity'} sharpens as the {obj} refuses to behave normally"
    twist = f"The {obj} implicates a detail nobody in town admits remembering"
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
            "lighting": "motivated practicals with heavy particulate haze",
            "camera": "slow push-ins and observational handheld drift",
            "palette": "desaturated greens, sodium amber, and crushed blacks",
            "wardrobe": "weathered layers suited to the location",
        },
        clip_beat_outline=[],
        channel_topic=channel_topic,
        niche=niche,
        diversity_mode=diversity_mode,
    )
    idea.clip_beat_outline = _clip_beats_for_idea(idea, clip_count)
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

        dragon_egg_pattern = all(
            token in _normalize(idea.logline + idea.setting + idea.title).lower()
            for token in ("boy", "dragon")
        )
        if dragon_egg_pattern and any(
            all(token in _normalize(str(row.get("logline") or "") + str(row.get("setting") or "")).lower() for token in ("boy", "dragon"))
            for row in history
        ):
            return False, "repeated_dragon_egg_pattern", metrics

    return True, "", metrics


def generate_channel_story_idea(
    *,
    channel_topic: str,
    niche: str = "",
    target_platform: str = "youtube_shorts",
    style: str = "cinematic",
    mood: str = "tense hopeful",
    duration_seconds: int = 30,
    clip_count: int = 2,
    diversity_mode: str = DEFAULT_DIVERSITY_MODE,
    previous_story_memory: list[dict[str, Any]] | None = None,
    attempt_offset: int = 0,
) -> ChannelStoryIdea:
    history = list(previous_story_memory or [])
    banned = _banned_terms_from_history(history)
    topic = _normalize(channel_topic) or _normalize(niche) or "dark fantasy analog horror stories"

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
        )
        ok, reason, _metrics = check_story_similarity(candidate, history)
        if ok:
            return candidate
        history = history + [candidate.to_dict()]

    # Fail closed into high-variety attempt with unique suffix
    fallback = _build_candidate(
        channel_topic=topic,
        niche=niche,
        style=style,
        mood=mood,
        clip_count=max(1, int(clip_count)),
        diversity_mode=DIVERSITY_HIGH_VARIETY,
        banned_terms=banned,
        attempt=MAX_IDEATION_ATTEMPTS + attempt_offset + secrets.randbelow(99),
    )
    fallback.title = f"{fallback.title} — Variant {secrets.token_hex(3)}"
    fallback.story_hash = _story_hash(fallback)
    fallback.prompt_hash = _prompt_hash(fallback.rich_story_text())
    return fallback


def channel_story_idea_to_runway_brief(idea: ChannelStoryIdea, *, clip_count: int, duration_seconds: int) -> RunwayStoryBrief:
    anchors = StoryBriefAnchors(
        character=idea.continuity_anchors.get("character") or idea.main_character,
        location=idea.continuity_anchors.get("location") or idea.setting,
        lighting=idea.continuity_anchors.get("lighting") or "motivated practical lighting",
        camera=idea.continuity_anchors.get("camera") or "cinematic continuity framing",
        palette=idea.continuity_anchors.get("palette") or "desaturated cinematic grade",
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
        style_direction=idea.niche or "cinematic dark mystery",
        continuity_anchors=anchors,
        clip_beats=list(idea.clip_beat_outline),
        scene_progression=list(idea.clip_beat_outline),
        source_topic=idea.channel_topic,
        target_platform="youtube_shorts",
        niche_style="cinematic",
        mood="tense hopeful",
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
            "genre": idea.niche or "dark fantasy analog horror",
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
    mood: str = "tense hopeful",
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
            emotional_hook=mood or "uneasy curiosity",
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
