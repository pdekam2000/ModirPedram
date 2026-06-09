"""
Topic-Specific Story Detail Layer — facts, entities, settings, and objects per topic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_locale import extract_topic_anchor_tokens, pick_title_anchor
from content_brain.execution.domain_knowledge_layer import (
    filter_prompt_entity_concepts,
    get_domain_profile,
    resolve_domain,
)

GENERIC_RUNTIME_SETTING_MARKERS: tuple[str, ...] = (
    "single continuous environment",
    "readable vertical framing",
    "strong depth",
    "frame-ready end pose",
    "continuity lock",
)


@dataclass
class TopicStoryDetail:
    topic: str
    subject: str
    facts: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    settings: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    narrative_beats: tuple[str, ...] = ()
    source: str = "generic"
    match_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "subject": self.subject,
            "facts": list(self.facts),
            "entities": list(self.entities),
            "settings": list(self.settings),
            "objects": list(self.objects),
            "narrative_beats": list(self.narrative_beats),
            "source": self.source,
            "match_key": self.match_key,
        }

    def all_concepts(self) -> tuple[str, ...]:
        items: list[str] = []
        for group in (self.entities, self.settings, self.objects, self.facts):
            items.extend(group)
        return tuple(dict.fromkeys(item for item in items if item))

    def narrative_summary(self, *, limit: int = 4) -> str:
        parts = list(self.facts[:2]) + list(self.entities[:2]) + list(self.objects[:2])
        return "; ".join(parts[:limit])


TOPIC_DETAIL_PACKS: tuple[dict[str, Any], ...] = (
    {
        "match_key": "dyatlov",
        "patterns": ("dyatlov", "dyatlov pass"),
        "subject": "Dyatlov Pass",
        "facts": (
            "Nine hikers died under unexplained circumstances in the Ural Mountains in 1959.",
            "Their tent was found torn open from the inside in freezing wilderness.",
            "Some victims were found without adequate clothing in deep snow.",
            "Investigators noted unusual injuries and conflicting evidence at the site.",
        ),
        "entities": (
            "Ural Mountains",
            "1959 expedition",
            "nine hikers",
            "Kholat Syakhl",
            "Soviet investigation files",
        ),
        "settings": (
            "snow-covered mountain pass in the Ural Mountains",
            "abandoned expedition tent torn from the inside",
            "freezing wilderness at night with wind-scoured snow",
        ),
        "objects": (
            "expedition tent",
            "footprints leading downhill in deep snow",
            "scattered clothing and gear",
            "investigation map and case notes",
        ),
        "narrative_beats": (
            "An investigator reaches the snow-covered Dyatlov Pass and studies the torn expedition tent.",
            "Footprints in the snow and scattered gear reveal conflicting evidence about the hikers' final movements.",
            "Case notes and an unexplained detail reopen the central question: what forced them out into the freezing wilderness?",
        ),
    },
    {
        "match_key": "roanoke",
        "patterns": ("roanoke", "roanoke colony", "lost colony"),
        "subject": "Roanoke Colony",
        "facts": (
            "English settlers vanished from Roanoke Island in the late 1580s without a clear explanation.",
            "The word Croatoan was carved at the abandoned settlement, hinting at a relocation or fate unknown.",
            "Archaeological digs and colonial records still produce conflicting theories about the disappearance.",
            "Historians debate starvation, conflict, assimilation, and relocation as competing explanations.",
        ),
        "entities": (
            "Roanoke Island",
            "English settlers",
            "Croatoan",
            "colonial settlement",
            "archaeological evidence",
            "historical records",
            "disappearance theories",
        ),
        "settings": (
            "Roanoke Island coastal wilderness",
            "abandoned colonial settlement with weathered timber structures",
            "historical expedition camp near archaeological dig site",
        ),
        "objects": (
            "carved Croatoan marker",
            "colonial map and expedition journal",
            "excavated pottery shards",
            "settlement fort palisade remains",
        ),
        "narrative_beats": (
            "A historian arrives at Roanoke Island and surveys the abandoned colonial settlement.",
            "Archival records and carved clues contradict the official story of what happened to the settlers.",
            "Archaeological evidence and competing disappearance theories leave the case unresolved.",
        ),
    },
    {
        "match_key": "bermuda_triangle",
        "patterns": ("bermuda triangle",),
        "subject": "Bermuda Triangle",
        "facts": (
            "Ships and aircraft have vanished without conventional explanation in this region.",
            "Reports mix weather anomalies, navigation errors, and unexplained disappearances.",
        ),
        "entities": ("Atlantic Ocean", "missing vessels", "flight records", "rescue logs"),
        "settings": (
            "storm-lashed open ocean under low cloud cover",
            "empty radar room tracking a vanished signal",
            "archival map room with plotted disappearance routes",
        ),
        "objects": ("navigation chart", "distress log", "radar blip", "life vest on empty deck"),
        "narrative_beats": (
            "A researcher opens disappearance records tied to the Bermuda Triangle.",
            "Radar logs and witness accounts contradict the official explanation.",
            "One unresolved detail keeps the case open.",
        ),
    },
)


def build_topic_story_detail(
    topic: str,
    *,
    topic_category: str = "",
    content_strategy: str = "",
    language_code: str = "en",
    openai_enrichment: dict[str, Any] | None = None,
) -> TopicStoryDetail:
    cleaned = re.sub(r"\s+", " ", str(topic or "").strip())
    if openai_enrichment and openai_enrichment.get("domain_concepts"):
        from content_brain.execution.content_brain_openai_classification_enricher import (
            OpenAIClassificationPayload,
            build_topic_detail_from_enrichment,
        )

        payload = OpenAIClassificationPayload(
            category=str(openai_enrichment.get("category") or topic_category or "general"),
            strategy=str(openai_enrichment.get("strategy") or content_strategy or "documentary"),
            domain_role=str(openai_enrichment.get("domain_role") or ""),
            domain_concepts=tuple(str(item) for item in openai_enrichment.get("domain_concepts") or ()),
            setting=str(openai_enrichment.get("setting") or ""),
            story_angles=tuple(str(item) for item in openai_enrichment.get("story_angles") or ()),
            seo_title_candidates=tuple(str(item) for item in openai_enrichment.get("seo_title_candidates") or ()),
            confidence=float(openai_enrichment.get("confidence") or 0.0),
            language_code=language_code,
        )
        detail_dict = build_topic_detail_from_enrichment(cleaned, payload)
        return TopicStoryDetail(
            topic=cleaned,
            subject=str(detail_dict.get("subject") or ""),
            facts=tuple(str(item) for item in detail_dict.get("facts") or ()),
            entities=tuple(str(item) for item in detail_dict.get("entities") or ()),
            settings=tuple(str(item) for item in detail_dict.get("settings") or ()),
            objects=tuple(str(item) for item in detail_dict.get("objects") or ()),
            narrative_beats=tuple(str(item) for item in detail_dict.get("narrative_beats") or ()),
            source="openai_classification",
            match_key=str(detail_dict.get("match_key") or ""),
        )
    pack = _match_detail_pack(cleaned)
    if pack is not None:
        return _detail_from_pack(cleaned, pack)

    domain = resolve_domain(cleaned, topic_category=topic_category)
    profile = get_domain_profile(cleaned, topic_category=topic_category, openai_enrichment=openai_enrichment)
    subject = _extract_subject_phrase(cleaned)
    enrichment_concepts = filter_prompt_entity_concepts(
        list((openai_enrichment or {}).get("domain_concepts") or []),
        topic=cleaned,
    )
    profile_concepts = filter_prompt_entity_concepts(list(profile.concepts[:10]), topic=cleaned)
    entities = tuple(
        list(
            dict.fromkeys(
                enrichment_concepts
                + profile_concepts
            )
        )[:8]
    ) or (subject,)
    settings = _infer_settings_from_signals(cleaned, domain, profile)
    objects = _infer_objects_from_domain(domain, profile)
    facts = _infer_facts_from_topic(cleaned, subject, domain, content_strategy, profile=profile)
    beats = _infer_beats_from_detail(subject, settings, objects, facts, content_strategy)
    return TopicStoryDetail(
        topic=cleaned,
        subject=subject,
        facts=facts,
        entities=entities,
        settings=settings,
        objects=objects,
        narrative_beats=beats,
        source="domain_profile_extractor",
    )


def score_narrative_detail(text: str, detail: TopicStoryDetail | None) -> float:
    if not detail:
        return 0.0
    lowered = str(text or "").lower()
    if not lowered:
        return 0.0
    concepts = detail.all_concepts()
    if not concepts:
        return 0.0
    hits = 0
    for concept in concepts:
        concept_lower = concept.lower()
        if len(concept_lower) >= 4 and concept_lower in lowered:
            hits += 1
            continue
        for token in concept_lower.split():
            if len(token) >= 4 and token in lowered:
                hits += 0.35
                break
    target = max(3, min(len(concepts), 10))
    score = min(1.0, hits / target)
    generic_hits = sum(1 for marker in GENERIC_RUNTIME_SETTING_MARKERS if marker in lowered)
    score = max(0.0, score - 0.08 * generic_hits)
    if detail.source not in {"generic_extractor", "domain_profile_extractor"} and hits >= 2:
        score = min(1.0, score + 0.1)
    return round(score, 4)


def _match_detail_pack(topic: str) -> dict[str, Any] | None:
    lowered = topic.lower()
    for pack in TOPIC_DETAIL_PACKS:
        patterns = pack.get("patterns") or ()
        if any(pattern in lowered for pattern in patterns):
            return pack
    return None


def _detail_from_pack(topic: str, pack: dict[str, Any]) -> TopicStoryDetail:
    return TopicStoryDetail(
        topic=topic,
        subject=str(pack.get("subject") or _extract_subject_phrase(topic)),
        facts=tuple(str(item) for item in pack.get("facts") or ()),
        entities=tuple(str(item) for item in pack.get("entities") or ()),
        settings=tuple(str(item) for item in pack.get("settings") or ()),
        objects=tuple(str(item) for item in pack.get("objects") or ()),
        narrative_beats=tuple(str(item) for item in pack.get("narrative_beats") or ()),
        source="topic_pack",
        match_key=str(pack.get("match_key") or ""),
    )


def _extract_subject_phrase(topic: str) -> str:
    pack = _match_detail_pack(topic)
    if pack and pack.get("subject"):
        return str(pack["subject"])
    try:
        from content_brain.execution.content_brain_topic_label_generator import (
            generate_topic_label,
            is_malformed_topic_label,
        )

        generated = generate_topic_label(topic).label
        if generated and not is_malformed_topic_label(generated, topic=topic):
            return generated
    except ImportError:  # pragma: no cover
        pass
    cleaned = re.sub(r"\s+", " ", str(topic or "").strip())
    stripped = re.sub(
        r"^(?:the|a|an)\s+(?:mystery|story|truth|history|case|legend)\s+of\s+",
        "",
        cleaned,
        flags=re.I,
    )
    stripped = re.sub(r"^(?:how to|how-to|best|why|what is)\s+", "", stripped, flags=re.I)
    stripped = re.sub(r"\s+", " ", stripped).strip(" .")
    if stripped and len(stripped.split()) <= 8:
        return _title_case(stripped)
    anchor = pick_title_anchor(cleaned)
    return _title_case(anchor)


def _infer_settings_from_signals(topic: str, domain: str, profile: Any) -> tuple[str, ...]:
    lowered = topic.lower()
    settings: list[str] = []
    if profile.setting_en and not _is_generic_runtime_setting(profile.setting_en):
        settings.append(profile.setting_en)
    if re.search(r"\b(pass|mountain|snow|wilderness|forest|desert|ocean|city|kitchen|lab|beach)\b", lowered):
        if "pass" in lowered or "mountain" in lowered:
            settings.append("remote mountain terrain with visible weather and terrain texture")
        if "snow" in lowered or "freez" in lowered or "winter" in lowered:
            settings.append("snow-covered landscape with cold atmospheric haze")
        if "ocean" in lowered or "sea" in lowered:
            settings.append("open water environment with horizon depth and weather cues")
        if "kitchen" in lowered or domain == "cooking":
            settings.append("working kitchen with ingredients and prep surfaces in frame")
    if domain == "mystery" or domain == "history_mystery":
        settings.append("documentary investigation space with evidence boards and archival material")
    if domain == "history_mystery":
        settings.append("Roanoke Island coastal wilderness with colonial settlement ruins")
    if domain == "fishing":
        settings.append("lakeside or riverbank with readable water and shoreline detail")
    return tuple(dict.fromkeys(item for item in settings if item))


def _infer_objects_from_domain(domain: str, profile: Any) -> tuple[str, ...]:
    if domain == "mystery" or domain == "history_mystery":
        return ("case file", "photograph evidence", "marked map", "archival note")
    if domain == "fishing":
        return ("fishing rod", "lure", "tackle box", "line tension")
    if domain == "cooking":
        return ("mixing bowl", "dough", "measuring tools", "oven")
    if domain == "perfume":
        return ("evaluation strip", "raw material bottles", "blending tools")
    concepts = list(profile.concepts[:4]) if profile and profile.concepts else ()
    return tuple(concepts) or ("key prop tied to the topic",)


def _infer_facts_from_topic(
    topic: str,
    subject: str,
    domain: str,
    content_strategy: str,
    *,
    profile: Any | None = None,
) -> tuple[str, ...]:
    if content_strategy == "scientific_explanation" and domain == "perfume":
        return (
            "Top notes evaporate quickly while base notes and fixatives drive longevity.",
            "Projection and maceration influence how long a fragrance lasts on skin.",
            "Concentration and volatility determine whether a scent fades or lingers.",
        )
    if content_strategy == "scientific_explanation" and profile and profile.concepts:
        core = ", ".join(list(profile.concepts[:3]))
        return (
            f"The explanation focuses on {core} behind {subject}.",
            f"Visible evidence should demonstrate how {subject} works in practice.",
        )
    if content_strategy in {
        "narrative_mystery",
        "horror_storytelling",
        "documentary",
        "historical_investigation",
    }:
        return (
            f"The story investigates unresolved questions about {subject}.",
            f"Evidence and context around {subject} do not fully align.",
        )
    if content_strategy.startswith("instructional") or content_strategy.endswith("_tutorial"):
        return (f"The viewer learns a practical method related to {subject}.",)
    return (f"The narrative stays anchored to {subject}.",)


def _infer_beats_from_detail(
    subject: str,
    settings: tuple[str, ...],
    objects: tuple[str, ...],
    facts: tuple[str, ...],
    content_strategy: str,
) -> tuple[str, ...]:
    setting = settings[0] if settings else f"the environment tied to {subject}"
    obj = objects[0] if objects else f"a key detail about {subject}"
    fact = facts[0] if facts else f"the central question about {subject}"
    if content_strategy in {"narrative_mystery", "horror_storytelling", "historical_investigation"}:
        return (
            f"Open on {setting}; {obj} introduces the mystery of {subject}.",
            f"Compare conflicting evidence about {subject} while staying in {setting}.",
            f"Close on the unresolved detail: {fact}",
        )
    return (
        f"Establish {subject} in {setting}.",
        f"Demonstrate the core action using {obj}.",
        f"Deliver the takeaway tied to {subject}.",
    )


def _is_generic_runtime_setting(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in GENERIC_RUNTIME_SETTING_MARKERS)


def _title_case(text: str) -> str:
    parts = str(text or "").split()
    if not parts:
        return ""
    small = {"to", "for", "and", "in", "on", "of", "a", "an", "the", "at", "by"}
    result: list[str] = []
    for index, part in enumerate(parts):
        if index > 0 and part.lower() in small:
            result.append(part.lower())
        else:
            result.append(part[:1].upper() + part[1:])
    return " ".join(result)


__all__ = [
    "TopicStoryDetail",
    "build_topic_story_detail",
    "score_narrative_detail",
    "_extract_subject_phrase",
    "_is_generic_runtime_setting",
]
