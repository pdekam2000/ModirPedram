"""Pre-generated SEO title banks for automation (one OpenAI call → many titles)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TITLE_BANK_VERSION = "title_bank_v2_lifetime_dedup"
REQUEST_TIMEOUT_SECONDS = 90.0
REFILL_THRESHOLD = 5
DEFAULT_BANK_COUNT = 30
MODEL_NAME = "gpt-4o"
MAX_BANK_PICK_ATTEMPTS = 40


def normalize_platform_for_bank(platform: str) -> str:
    key = str(platform or "").strip().lower()
    if key in {"youtube", "youtube_shorts"}:
        return "youtube_shorts"
    if key in {"instagram", "instagram_reels"}:
        return "instagram_reels"
    return key


def _bank_path(project_root: Path, platform: str) -> Path:
    key = normalize_platform_for_bank(platform)
    return Path(project_root) / "project_brain" / "story" / f"title_bank_{key}.json"


def _used_path(project_root: Path, platform: str) -> Path:
    key = normalize_platform_for_bank(platform)
    return Path(project_root) / "project_brain" / "story" / f"title_bank_{key}_used.json"


def _load_json_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("title_bank load failed (%s): %s", path, exc)
        return []
    if isinstance(raw, dict):
        raw = raw.get("titles") or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _write_json_list(path: Path, titles: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(titles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize_title_key(title: str) -> str:
    return str(title or "").strip().lower()


def _memory_blocked_titles(project_root: Path, platform: str) -> set[str]:
    """Load every prior story-memory title for this platform (lifetime)."""
    try:
        from content_brain.execution.channel_story_ideation import (
            all_used_titles,
            load_story_memory,
        )

        memory = load_story_memory(project_root)
        return all_used_titles(memory, target_platform=platform)
    except Exception as exc:
        logger.debug("title_bank memory blocked load failed: %s", exc)
        return set()


def scrub_title_bank_against_memory(platform: str, project_root: Path) -> dict[str, Any]:
    """Remove bank titles already present in story memory. Returns scrub stats."""
    root = Path(project_root)
    key = normalize_platform_for_bank(platform)
    path = _bank_path(root, key)
    titles = _load_json_list(path)
    blocked = _memory_blocked_titles(root, key)
    clean = [t for t in titles if _normalize_title_key(t) not in blocked]
    removed = [t for t in titles if _normalize_title_key(t) in blocked]
    if removed:
        _write_json_list(path, clean)
    return {
        "platform": key,
        "before": len(titles),
        "after": len(clean),
        "removed": removed,
    }


def _prompt_for_platform(platform: str, count: int) -> str:
    key = normalize_platform_for_bank(platform)
    if key == "youtube_shorts":
        return f"""Generate {count} completely unique YouTube Shorts titles
for a science channel called "Science That Feels Impossible".

Rules:
- Each title must be about a DIFFERENT science fact
- Topics: space, physics, biology, chemistry, earth, animals, human body
- Each title starts with a different power word
- Under 60 characters each
- Creates curiosity gap
- NO duplicates or similar titles
- Power words to rotate: Why, How, What Happens When, Never,
  The Truth About, Scientists Discovered, This Is Why,
  Nobody Talks About, The Real Reason, Shocking

Return JSON: {{"titles": ["title1", "title2", ...]}}"""

    if key == "instagram_reels":
        return f"""Generate exactly {count} viral Instagram Reel titles for a perfumery education channel.

CRITICAL: Every title must feel like clickbait education — shock, price shock, weird animal source, rarity, or famous-perfume reveal.

COPY THIS ENERGY (do not reuse these exact lines):
- Why Rose Absolute Costs More Than Gold
- The $50,000/kg Ingredient in Your Perfume
- This Whale Secretion Made Chanel No.5 Famous
- The Flower That Only Blooms at Night
- Why Real Oud Costs More Than a Car
- The Chemical That Makes Perfume Last 3 Days
- They Extract This From Cat Glands for Perfume
- The Rarest Ingredient: Only 1kg Per Year

Topics to cover: rose absolute, jasmine, oud, ambergris,
civet, musk, bergamot, sandalwood, vetiver, patchouli,
neroli, iris/orris, oakmoss, labdanum, frankincense,
hedione, ambroxan, iso e super, linalool, coumarin,
ylang ylang, tuberose, violet leaf, angelica, castoreum,
benzoin, tonka bean, peru balsam, steam distillation, enfleurage

Hard rules:
- Each title covers a DIFFERENT ingredient/technique
- Under 60 characters
- NO poetic/generic titles ("Beauty of…", "Enigmatic…", "Unlocking…")
- Must include a hook: $, cost, rare, secret, animal source, famous perfume, or weird fact
- Must make a scroller STOP
- NO duplicates

Return JSON: {{"titles": ["title1", "title2", ...]}}"""

    raise ValueError(f"unsupported_title_bank_platform:{platform}")


def generate_title_bank(platform: str, count: int = DEFAULT_BANK_COUNT) -> list[str]:
    """Generate count unique SEO titles in one OpenAI call."""
    key = normalize_platform_for_bank(platform)
    n = max(1, int(count or DEFAULT_BANK_COUNT))
    prompt = _prompt_for_platform(key, n)

    from content_brain.story.kling_story_first_openai_writer import get_openai_client

    client = get_openai_client(project_root=None)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    content = str(response.choices[0].message.content or "").strip()
    payload: dict[str, Any] = json.loads(content) if content else {}
    titles_raw = payload.get("titles") if isinstance(payload, dict) else None
    if not isinstance(titles_raw, list):
        raise ValueError("title_bank_openai_missing_titles")
    titles = [str(item).strip() for item in titles_raw if str(item).strip()]
    # Preserve order while deduping within this batch
    return list(dict.fromkeys(titles))[:n] if len(titles) > n else list(dict.fromkeys(titles))


def save_title_bank(platform: str, titles: list[str], project_root: Path) -> list[str]:
    path = _bank_path(Path(project_root), platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_json_list(path)
    incoming = [str(t).strip() for t in (titles or []) if str(t).strip()]
    all_titles = list(dict.fromkeys(existing + incoming))
    _write_json_list(path, all_titles)
    return all_titles


def get_next_title(
    platform: str,
    project_root: Path,
    *,
    blocked_titles: set[str] | None = None,
) -> str | None:
    """Return the next unused bank title, or None to fall back to per-video generation.

    Before returning, verifies the title is NOT in:
      - title_bank_*_used.json
      - story memory (lifetime, platform-scoped)
      - optional caller blocked_titles
    """
    root = Path(project_root)
    key = normalize_platform_for_bank(platform)
    path = _bank_path(root, key)
    used_path = _used_path(root, key)

    if not path.exists():
        return None

    # Always re-read story memory at pick time (never trust stale blocked set alone).
    memory_titles = _memory_blocked_titles(root, key)
    titles = _load_json_list(path)
    used = _load_json_list(used_path)
    used_lower = {_normalize_title_key(t) for t in used}

    blocked = {_normalize_title_key(t) for t in (blocked_titles or set()) if str(t).strip()}
    blocked |= memory_titles
    blocked |= used_lower

    available = [
        t
        for t in titles
        if t not in used
        and _normalize_title_key(t) not in used_lower
        and _normalize_title_key(t) not in memory_titles
        and _normalize_title_key(t) not in blocked
    ]

    if len(available) < REFILL_THRESHOLD:
        try:
            new_titles = generate_title_bank(key, DEFAULT_BANK_COUNT)
            filtered = [
                t
                for t in new_titles
                if _normalize_title_key(t) not in blocked
                and _normalize_title_key(t) not in memory_titles
            ]
            save_title_bank(key, filtered or new_titles, root)
            # Drop any remaining memory collisions from the on-disk bank.
            scrub_title_bank_against_memory(key, root)
            titles = _load_json_list(path)
            available = [
                t
                for t in titles
                if t not in used
                and _normalize_title_key(t) not in used_lower
                and _normalize_title_key(t) not in memory_titles
                and _normalize_title_key(t) not in blocked
            ]
        except Exception as exc:
            logger.warning("title_bank refill failed for %s: %s", key, exc)

    if not available:
        return None

    title = available[0]
    # Final guard: never return a memory collision.
    if _normalize_title_key(title) in memory_titles:
        used.append(title)
        _write_json_list(used_path, list(dict.fromkeys(used)))
        logger.warning("title_bank skipped memory collision: %s", title[:80])
        return get_next_title(platform, root, blocked_titles=blocked | {_normalize_title_key(title)})

    used.append(title)
    _write_json_list(used_path, list(dict.fromkeys(used)))
    return title


__all__ = [
    "TITLE_BANK_VERSION",
    "generate_title_bank",
    "get_next_title",
    "normalize_platform_for_bank",
    "save_title_bank",
    "scrub_title_bank_against_memory",
]
