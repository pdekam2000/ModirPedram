"""
Content Brain V8.3 — Prompt Cleanup Pass.

Removes duplicate concepts, entities, facts, and sentences from Runway prompts
after concept distribution without losing clip-specific information.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

CLEANUP_LAYER_VERSION = "prompt_cleanup_v1"
DEFAULT_MODEL = "gpt-4.1-mini"
PROMPT_NOISE_MAX = 0.20
PROMPT_NOISE_TARGET = 0.10
PROMPT_EFFICIENCY_TARGET = 0.85
MAX_CONCEPT_REPEATS = 2
MAX_DUPLICATE_ENTITY_RATIO = 0.20
OPENAI_CLEANUP_MIN_CHARS = 3500

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CACHE_DIR = os.path.join(ROOT, "project_brain", "content_brain_prompt_cleanup_cache")

SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "clip_focus_concepts": re.compile(r"Clip focus concepts:\s*([^.]+)\.", re.I),
    "key_entities": re.compile(r"Key entities:\s*([^.]+)\.", re.I),
    "visible_objects": re.compile(r"Visible objects:\s*([^.]+)\.", re.I),
    "historical_facts": re.compile(r"Historical facts:\s*([^.]+)\.", re.I),
    "topic_facts": re.compile(r"Topic facts and evidence:\s*([^.]+)\.", re.I),
    "setting_details": re.compile(r"Setting details:\s*([^.]+)\.", re.I),
}

HISTORICAL_DETAIL_PATTERN = re.compile(r"Historical detail:\s*([^.]+)\.", re.I)

CONTINUITY_DEDUPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bMaintain same character, wardrobe, and location\.?", re.I),
        "Maintain same character, wardrobe, and location.",
    ),
    (re.compile(r"\bsame character\b", re.I), ""),
    (re.compile(r"\bsame wardrobe\b", re.I), ""),
    (re.compile(r"\bsame location\b", re.I), ""),
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _item_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _split_list_items(text: str) -> list[str]:
    return [_normalize(item) for item in re.split(r"[;]", str(text or "")) if _normalize(item)]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = _item_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _normalize_sentence(text: str) -> str:
    return _item_key(re.sub(r"[^\w\s]", " ", str(text or "")))


def _replace_section(text: str, label: str, items: list[str]) -> str:
    if not items:
        return re.sub(rf"{label}:\s*[^.]+\.\s*", "", text, flags=re.I)
    replacement = f"{label}: {'; '.join(items)}."
    pattern = re.compile(rf"{label}:\s*[^.]+\.", re.I)
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text


def _dedupe_historical_details(text: str) -> str:
    seen: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
        content = _normalize(match.group(1))
        key = _item_key(content)
        if not key or key in seen:
            return ""
        seen.add(key)
        return match.group(0)

    cleaned = HISTORICAL_DETAIL_PATTERN.sub(_replace, text)
    return _normalize(cleaned)


def _compress_labeled_sections(text: str) -> str:
    section_items: dict[str, list[str]] = {}
    for name, pattern in SECTION_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            section_items[name] = []
            continue
        section_items[name] = _split_list_items(match.group(1))

    seen_global: set[str] = set()
    compressed: dict[str, list[str]] = {}

    focus = _dedupe_preserve_order(section_items.get("clip_focus_concepts") or [])
    for item in focus:
        seen_global.add(_item_key(item))
    compressed["clip_focus_concepts"] = focus[:4]

    entities: list[str] = []
    for item in _dedupe_preserve_order(
        (section_items.get("key_entities") or [])
        + (section_items.get("clip_focus_concepts") or [])
    ):
        key = _item_key(item)
        if key in seen_global and item not in focus:
            continue
        if key in {_item_key(existing) for existing in entities}:
            continue
        entities.append(item)
        seen_global.add(key)
    compressed["key_entities"] = entities[:4]

    visible: list[str] = []
    for item in _dedupe_preserve_order(section_items.get("visible_objects") or []):
        key = _item_key(item)
        if key in seen_global:
            continue
        visible.append(item)
        seen_global.add(key)
    if not visible:
        for item in _dedupe_preserve_order(section_items.get("setting_details") or []):
            key = _item_key(item)
            if key in seen_global:
                continue
            visible.append(item)
            seen_global.add(key)
            if len(visible) >= 2:
                break
    compressed["visible_objects"] = visible[:3]

    facts: list[str] = []
    for item in _dedupe_preserve_order(
        (section_items.get("historical_facts") or []) + (section_items.get("topic_facts") or [])
    ):
        key = _item_key(item)
        if key in seen_global:
            continue
        facts.append(item)
        seen_global.add(key)
        if len(facts) >= 2:
            break
    compressed["historical_facts"] = facts[:2]

    working = text
    working = _replace_section(working, "Clip focus concepts", compressed["clip_focus_concepts"])
    working = _replace_section(working, "Key entities", compressed["key_entities"])
    working = _replace_section(working, "Visible objects", compressed["visible_objects"])
    working = _replace_section(working, "Historical facts", compressed["historical_facts"])
    if section_items.get("topic_facts"):
        working = re.sub(r"Topic facts and evidence:\s*[^.]+\.\s*", "", working, flags=re.I)
    if section_items.get("setting_details") and compressed["visible_objects"]:
        working = re.sub(r"Setting details:\s*[^.]+\.\s*", "", working, flags=re.I)
    return _normalize(working)


def _dedupe_sentences(text: str) -> str:
    parts = re.split(r"(?<=\.)\s+", text)
    seen: set[str] = set()
    kept: list[str] = []
    for part in parts:
        cleaned = _normalize(part)
        if not cleaned:
            continue
        norm = _normalize_sentence(cleaned)
        if len(norm) >= 12 and norm in seen:
            continue
        if norm:
            seen.add(norm)
        kept.append(cleaned if cleaned.endswith(".") else f"{cleaned}.")
    return _normalize(" ".join(kept))


def _dedupe_continuity_phrases(text: str) -> str:
    pattern, replacement = CONTINUITY_DEDUPE_PATTERNS[0]
    matches = list(pattern.finditer(text))
    if not matches:
        return _normalize(text)
    working = text
    for match in matches[1:]:
        working = working.replace(match.group(0), " ", 1)
    working = pattern.sub(replacement, working, count=1)
    return _normalize(working)


def clean_prompt_text(text: str) -> tuple[str, dict[str, Any]]:
    original = str(text or "")
    stats: dict[str, Any] = {
        "original_length": len(original),
        "historical_details_removed": 0,
        "sections_compressed": False,
    }
    if not original.strip():
        stats["cleaned_length"] = 0
        stats["characters_saved"] = 0
        stats["reduction_percent"] = 0.0
        return original, stats

    historical_before = len(HISTORICAL_DETAIL_PATTERN.findall(original))
    working = _dedupe_historical_details(original)
    historical_after = len(HISTORICAL_DETAIL_PATTERN.findall(working))
    stats["historical_details_removed"] = max(0, historical_before - historical_after)

    before_sections = sum(1 for pattern in SECTION_PATTERNS.values() if pattern.search(working))
    working = _compress_labeled_sections(working)
    stats["sections_compressed"] = before_sections > 0

    entity_match = SECTION_PATTERNS["key_entities"].search(working)
    entity_keys = {
        _item_key(item) for item in _split_list_items(entity_match.group(1))
    } if entity_match else set()
    focus_match = SECTION_PATTERNS["clip_focus_concepts"].search(working)
    focus_keys = {
        _item_key(item) for item in _split_list_items(focus_match.group(1))
    } if focus_match else set()
    if focus_keys and focus_keys == entity_keys:
        working = re.sub(r"Clip focus concepts:\s*[^.]+\.\s*", "", working, flags=re.I)

    known_items = entity_keys | focus_keys

    def _strip_redundant_historical(match: re.Match[str]) -> str:
        key = _item_key(match.group(1))
        if key in known_items:
            stats["historical_details_removed"] = int(stats.get("historical_details_removed") or 0) + 1
            return ""
        return match.group(0)

    working = HISTORICAL_DETAIL_PATTERN.sub(_strip_redundant_historical, working)

    working = _dedupe_sentences(working)
    working = _dedupe_continuity_phrases(working)
    working = _normalize(working)

    stats["cleaned_length"] = len(working)
    stats["characters_saved"] = max(0, stats["original_length"] - stats["cleaned_length"])
    stats["reduction_percent"] = round(
        (stats["characters_saved"] / stats["original_length"]) * 100.0,
        2,
    ) if stats["original_length"] else 0.0
    return working, stats


def _extract_labeled_items(text: str) -> list[str]:
    items: list[str] = []
    for pattern in SECTION_PATTERNS.values():
        for match in pattern.finditer(text):
            items.extend(_split_list_items(match.group(1)))
    for match in HISTORICAL_DETAIL_PATTERN.finditer(text):
        items.append(_normalize(match.group(1)))
    return items


def _extract_information_units(text: str) -> list[str]:
    units: list[str] = []
    units.extend(_extract_labeled_items(text))
    for sentence in re.split(r"(?<=\.)\s+", text):
        norm = _normalize_sentence(sentence)
        if len(norm) >= 10:
            units.append(norm)
    return _dedupe_preserve_order(units)


def score_prompt_noise(text: str) -> float:
    labeled_items = _extract_labeled_items(text)
    item_dup_ratio = 0.0
    if labeled_items:
        keys = [_item_key(item) for item in labeled_items]
        item_dup_ratio = 1.0 - (len(set(keys)) / len(keys))

    sentences = [_normalize_sentence(part) for part in re.split(r"(?<=\.)\s+", text) if _normalize(part)]
    sent_dup_ratio = 0.0
    if sentences:
        sent_dup_ratio = 1.0 - (len(set(sentences)) / len(sentences))

    historical = HISTORICAL_DETAIL_PATTERN.findall(text)
    hist_dup_ratio = 0.0
    if historical:
        keys = [_item_key(item) for item in historical]
        hist_dup_ratio = 1.0 - (len(set(keys)) / len(keys))

    section_dup_ratio = 0.0
    entity_items = _split_list_items(SECTION_PATTERNS["key_entities"].search(text).group(1)) if SECTION_PATTERNS["key_entities"].search(text) else []
    object_items = _split_list_items(SECTION_PATTERNS["visible_objects"].search(text).group(1)) if SECTION_PATTERNS["visible_objects"].search(text) else []
    if entity_items and object_items:
        entity_keys = {_item_key(item) for item in entity_items}
        object_keys = [_item_key(item) for item in object_items]
        overlap = sum(1 for key in object_keys if key in entity_keys)
        section_dup_ratio = overlap / max(len(object_keys), 1)

    score = (
        item_dup_ratio * 0.30
        + sent_dup_ratio * 0.20
        + hist_dup_ratio * 0.35
        + section_dup_ratio * 0.15
    )
    return round(min(1.0, max(0.0, score)), 4)


def score_prompt_efficiency(text: str, *, original_length: int | None = None) -> float:
    noise = score_prompt_noise(text)
    units = _extract_information_units(text)
    unique_units = len({_item_key(unit) for unit in units if _item_key(unit)})
    length = max(len(text), 1)
    density = min(1.0, (unique_units * 95.0) / length)
    compression_bonus = 0.0
    if original_length and original_length > length:
        saved_ratio = (original_length - length) / original_length
        compression_bonus = min(0.12, saved_ratio * 0.35)
    efficiency = min(1.0, density * (1.0 - noise * 0.65) + compression_bonus)
    return round(max(0.0, efficiency), 4)


def _duplicate_entity_ratio(text: str) -> float:
    items = _extract_labeled_items(text)
    if len(items) < 2:
        return 0.0
    keys = [_item_key(item) for item in items]
    duplicates = len(keys) - len(set(keys))
    return round(duplicates / len(keys), 4)


def _concept_repeat_violations(text: str, *, max_repeats: int = MAX_CONCEPT_REPEATS) -> list[str]:
    violations: list[str] = []
    concepts = _dedupe_preserve_order(_extract_labeled_items(text))
    section_counts: dict[str, int] = {}
    for concept in concepts:
        key = _item_key(concept)
        if not key:
            continue
        section_counts[key] = section_counts.get(key, 0) + 1
    for concept in concepts:
        key = _item_key(concept)
        if not key:
            continue
        phrase_count = len(re.findall(re.escape(key), str(text or "").lower()))
        count = max(section_counts.get(key, 0), phrase_count)
        if count > max_repeats:
            violations.append(f"{concept}:{count}")
    return violations


def validate_prompt_cleanup_gates(
    *,
    prompt_texts: list[str],
    prompt_noise_score: float,
    prompt_efficiency_score: float,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    noise_values = [score_prompt_noise(text) for text in prompt_texts if str(text or "").strip()]
    avg_noise = sum(noise_values) / len(noise_values) if noise_values else prompt_noise_score
    if avg_noise > PROMPT_NOISE_MAX:
        failures.append(f"prompt_noise_score>{PROMPT_NOISE_MAX}:{avg_noise:.4f}")
    for index, text in enumerate(prompt_texts, start=1):
        violations = _concept_repeat_violations(text)
        if violations:
            failures.append(f"clip_{index}_concept_repeat:{','.join(violations[:3])}")
        dup_ratio = _duplicate_entity_ratio(text)
        if dup_ratio > MAX_DUPLICATE_ENTITY_RATIO:
            failures.append(f"clip_{index}_duplicate_entity_ratio>{MAX_DUPLICATE_ENTITY_RATIO}:{dup_ratio:.2f}")
    return not failures, failures


@dataclass
class PromptCleanupResult:
    topic: str = ""
    starter_image_prompt: str = ""
    starter_image_prompt_original: str = ""
    clip_prompts: list[dict[str, Any]] = field(default_factory=list)
    original_total_chars: int = 0
    cleaned_total_chars: int = 0
    characters_saved: int = 0
    reduction_percent: float = 0.0
    prompt_noise_score: float = 0.0
    prompt_efficiency_score: float = 0.0
    cleanup_applied: bool = False
    openai_cleanup_used: bool = False
    cache_hit: bool = False
    estimated_cost_usd: float = 0.0
    source: str = "local_rules"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "starter_image_prompt": self.starter_image_prompt,
            "starter_image_prompt_original": self.starter_image_prompt_original,
            "clip_prompts": list(self.clip_prompts),
            "original_total_chars": self.original_total_chars,
            "cleaned_total_chars": self.cleaned_total_chars,
            "original_length": self.original_total_chars,
            "cleaned_length": self.cleaned_total_chars,
            "characters_saved": self.characters_saved,
            "reduction_percent": round(self.reduction_percent, 2),
            "prompt_noise_score": round(self.prompt_noise_score, 4),
            "prompt_efficiency_score": round(self.prompt_efficiency_score, 4),
            "cleanup_applied": self.cleanup_applied,
            "openai_cleanup_used": self.openai_cleanup_used,
            "cache_hit": self.cache_hit,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "source": self.source,
            "warnings": list(self.warnings),
            "layer_version": CLEANUP_LAYER_VERSION,
        }


def should_use_openai_cleanup(*, prompt_texts: list[str], prompt_noise_score: float) -> bool:
    joined = " ".join(str(text or "") for text in prompt_texts)
    if len(joined) > OPENAI_CLEANUP_MIN_CHARS:
        return True
    return float(prompt_noise_score) > PROMPT_NOISE_MAX


def _build_local_cleanup(
    *,
    topic: str,
    starter_image_prompt: str,
    clip_prompts: list[dict[str, Any]],
) -> PromptCleanupResult:
    cleaned_clips: list[dict[str, Any]] = []
    original_total = len(str(starter_image_prompt or ""))
    cleaned_total = original_total

    starter_cleaned, _ = clean_prompt_text(str(starter_image_prompt or ""))

    for clip in clip_prompts:
        payload = dict(clip or {})
        original = str(payload.get("video_prompt_original") or payload.get("video_prompt") or "")
        original_total += len(original)
        cleaned, stats = clean_prompt_text(original)
        cleaned_total += len(cleaned)
        cleaned_clips.append(
            {
                **payload,
                "video_prompt": cleaned,
                "video_prompt_original": original,
                "video_prompt_chars": len(cleaned),
                "cleanup_stats": stats,
            }
        )

    noise_values = [score_prompt_noise(str(item.get("video_prompt") or "")) for item in cleaned_clips]
    avg_noise = sum(noise_values) / len(noise_values) if noise_values else score_prompt_noise(starter_cleaned)
    avg_efficiency_values = [
        score_prompt_efficiency(
            str(item.get("video_prompt") or ""),
            original_length=len(str(item.get("video_prompt_original") or "")),
        )
        for item in cleaned_clips
    ]
    avg_efficiency = (
        sum(avg_efficiency_values) / len(avg_efficiency_values)
        if avg_efficiency_values
        else score_prompt_efficiency(starter_cleaned, original_length=len(starter_image_prompt or ""))
    )
    characters_saved = max(0, original_total - cleaned_total)
    return PromptCleanupResult(
        topic=topic,
        starter_image_prompt=starter_cleaned,
        starter_image_prompt_original=str(starter_image_prompt or ""),
        clip_prompts=cleaned_clips,
        original_total_chars=original_total,
        cleaned_total_chars=cleaned_total,
        characters_saved=characters_saved,
        reduction_percent=(characters_saved / original_total * 100.0) if original_total else 0.0,
        prompt_noise_score=avg_noise,
        prompt_efficiency_score=avg_efficiency,
        cleanup_applied=characters_saved > 0 or avg_noise < 1.0,
        source="local_rules",
    )


@dataclass
class OpenAIPromptCleanupEnricher:
    model: str = DEFAULT_MODEL
    dry_run: bool = False
    cache_dir: str = DEFAULT_CACHE_DIR

    def maybe_enrich(
        self,
        *,
        topic: str,
        local_result: PromptCleanupResult,
        prompt_noise_score: float,
    ) -> PromptCleanupResult | None:
        prompt_texts = [str(item.get("video_prompt") or "") for item in local_result.clip_prompts]
        if not should_use_openai_cleanup(prompt_texts=prompt_texts, prompt_noise_score=prompt_noise_score):
            return None

        if self.dry_run:
            enriched = PromptCleanupResult(
                topic=topic,
                starter_image_prompt=local_result.starter_image_prompt,
                starter_image_prompt_original=local_result.starter_image_prompt_original,
                clip_prompts=list(local_result.clip_prompts),
                original_total_chars=local_result.original_total_chars,
                cleaned_total_chars=local_result.cleaned_total_chars,
                characters_saved=local_result.characters_saved,
                reduction_percent=local_result.reduction_percent,
                prompt_noise_score=local_result.prompt_noise_score,
                prompt_efficiency_score=local_result.prompt_efficiency_score,
                cleanup_applied=local_result.cleanup_applied,
                openai_cleanup_used=True,
                source="openai_prompt_cleanup_dry_run",
                warnings=list(local_result.warnings),
            )
            return enriched

        cache_key = self._cache_key(topic, prompt_texts)
        cached = self._read_cache(cache_key)
        if cached is not None:
            parsed = _parse_cleanup_payload(cached, topic=topic, base=local_result)
            parsed.cache_hit = True
            parsed.openai_cleanup_used = True
            parsed.source = "openai_prompt_cleanup_cache"
            return parsed
        return None

    def _cache_key(self, topic: str, prompt_texts: list[str]) -> str:
        digest = hashlib.sha256(
            f"{CLEANUP_LAYER_VERSION}|{topic}|{'|'.join(prompt_texts)}".encode("utf-8")
        ).hexdigest()
        return digest

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None


def _parse_cleanup_payload(
    payload: dict[str, Any],
    *,
    topic: str,
    base: PromptCleanupResult,
) -> PromptCleanupResult:
    clip_prompts = list(payload.get("clip_prompts") or base.clip_prompts)
    starter = str(payload.get("starter_image_prompt") or base.starter_image_prompt)
    original_total = int(payload.get("original_total_chars") or base.original_total_chars)
    cleaned_total = int(payload.get("cleaned_total_chars") or base.cleaned_total_chars)
    return PromptCleanupResult(
        topic=topic,
        starter_image_prompt=starter,
        starter_image_prompt_original=base.starter_image_prompt_original,
        clip_prompts=clip_prompts,
        original_total_chars=original_total,
        cleaned_total_chars=cleaned_total,
        characters_saved=max(0, original_total - cleaned_total),
        reduction_percent=float(payload.get("reduction_percent") or base.reduction_percent),
        prompt_noise_score=float(payload.get("prompt_noise_score") or base.prompt_noise_score),
        prompt_efficiency_score=float(payload.get("prompt_efficiency_score") or base.prompt_efficiency_score),
        cleanup_applied=True,
        openai_cleanup_used=True,
        source=str(payload.get("source") or "openai_prompt_cleanup"),
    )


def resolve_prompt_cleanup(
    *,
    topic: str,
    starter_image_prompt: str,
    clip_prompts: list[dict[str, Any]],
    language_code: str = "en",
) -> PromptCleanupResult:
    del language_code
    local = _build_local_cleanup(
        topic=topic,
        starter_image_prompt=starter_image_prompt,
        clip_prompts=clip_prompts,
    )
    enricher = OpenAIPromptCleanupEnricher(
        dry_run=os.getenv("OPENAI_PROMPT_CLEANUP_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        or os.getenv("OPENAI_QUALITY_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    )
    enriched = enricher.maybe_enrich(
        topic=topic,
        local_result=local,
        prompt_noise_score=local.prompt_noise_score,
    )
    if enriched:
        return enriched
    return local


__all__ = [
    "CLEANUP_LAYER_VERSION",
    "PromptCleanupResult",
    "clean_prompt_text",
    "resolve_prompt_cleanup",
    "score_prompt_efficiency",
    "score_prompt_noise",
    "should_use_openai_cleanup",
    "validate_prompt_cleanup_gates",
]
