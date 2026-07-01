"""Director Layer — Visual Subject Lock for animal/object topic continuity."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

VISUAL_SUBJECT_LOCK_VERSION = "visual_subject_lock_v1"

SUBJECT_TYPE_ANIMAL = "animal"
SUBJECT_TYPE_OBJECT = "object"
SUBJECT_TYPE_PERSON = "person"
SUBJECT_TYPE_PLACE = "place"
SUBJECT_TYPE_CONCEPT = "concept"

HUMAN_ROLE_MARKERS: tuple[str, ...] = (
    "arachnologist",
    "biologist",
    "scientist",
    "researcher",
    "doctor",
    "expert",
    "presenter",
    "narrator",
    "observer",
    "host",
    "angler",
    "fisherman",
    "guide",
    "handler",
    "keeper",
)

VISUAL_SUBJECT_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "patterns": ("scorpion", "black scorpion", "emperor scorpion"),
        "primary_visual_subject": "black scorpion",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "required_visible_features": (
            "curved segmented tail",
            "raised stinger",
            "pincers",
            "segmented exoskeleton",
            "eight legs",
            "low crawling posture",
        ),
        "forbidden_confusions": ("spider", "crab", "lobster", "generic insect", "beetle"),
    },
    {
        "patterns": ("snake", "python", "cobra", "viper", "rattlesnake"),
        "primary_visual_subject": "snake",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "required_visible_features": (
            "elongated serpentine body",
            "distinct head shape",
            "visible scales",
            "coiled or slithering posture",
        ),
        "forbidden_confusions": ("lizard", "worm", "eel", "caterpillar"),
    },
    {
        "patterns": ("ant", "ants", "fire ant", "army ant", "leafcutter ant"),
        "primary_visual_subject": "ant",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "required_visible_features": (
            "three body segments",
            "bent antennae",
            "six legs",
            "narrow waist",
            "mandibles",
        ),
        "forbidden_confusions": ("termite", "beetle", "spider", "wasp"),
    },
    {
        "patterns": ("zander", "zander fish", "sander lucioperca"),
        "primary_visual_subject": "zander fish",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "required_visible_features": (
            "predatory freshwater fish silhouette",
            "sharp teeth",
            "spiny dorsal fin",
            "greenish-brown scales",
            "elongated body",
        ),
        "forbidden_confusions": ("trout", "salmon", "shark", "pike confusion with unrelated species"),
    },
    {
        "patterns": ("spider", "tarantula", "black widow"),
        "primary_visual_subject": "spider",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "required_visible_features": (
            "eight legs",
            "two body segments",
            "visible fangs or chelicerae",
            "web or hunting posture",
        ),
        "forbidden_confusions": ("scorpion", "crab", "insect", "beetle"),
    },
)


@dataclass(frozen=True)
class VisualSubjectLock:
    primary_visual_subject: str
    subject_type: str = SUBJECT_TYPE_CONCEPT
    required_visible_features: tuple[str, ...] = ()
    forbidden_confusions: tuple[str, ...] = ()
    continuity_phrase: str = ""
    negative_prompt_terms: tuple[str, ...] = ()
    identity_lock_sentence: str = ""
    human_presenter_role: str = ""
    version: str = VISUAL_SUBJECT_LOCK_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "primary_visual_subject": self.primary_visual_subject,
            "subject_type": self.subject_type,
            "required_visible_features": list(self.required_visible_features),
            "forbidden_confusions": list(self.forbidden_confusions),
            "continuity_phrase": self.continuity_phrase,
            "negative_prompt_terms": list(self.negative_prompt_terms),
            "identity_lock_sentence": self.identity_lock_sentence,
            "human_presenter_role": self.human_presenter_role,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> VisualSubjectLock | None:
        if not payload:
            return None
        return cls(
            primary_visual_subject=str(payload.get("primary_visual_subject") or ""),
            subject_type=str(payload.get("subject_type") or SUBJECT_TYPE_CONCEPT),
            required_visible_features=tuple(str(item) for item in payload.get("required_visible_features") or ()),
            forbidden_confusions=tuple(str(item) for item in payload.get("forbidden_confusions") or ()),
            continuity_phrase=str(payload.get("continuity_phrase") or ""),
            negative_prompt_terms=tuple(str(item) for item in payload.get("negative_prompt_terms") or ()),
            identity_lock_sentence=str(payload.get("identity_lock_sentence") or ""),
            human_presenter_role=str(payload.get("human_presenter_role") or ""),
            version=str(payload.get("version") or VISUAL_SUBJECT_LOCK_VERSION),
        )

    def subject_identity_line(self) -> str:
        if self.identity_lock_sentence:
            return self.identity_lock_sentence
        features = ", ".join(self.required_visible_features[:4])
        base = self.primary_visual_subject
        if features:
            return f"The same {base} specimen remains the main on-screen subject in every clip, always showing {features}."
        return f"The same {base} remains the main on-screen subject in every clip."

    def starter_subject_line(self, *, human_presenter: str = "") -> str:
        subject = self.primary_visual_subject
        if human_presenter and self.subject_type != SUBJECT_TYPE_PERSON:
            role = self.human_presenter_role or f"{human_presenter} observer"
            return (
                f"a {subject} in the foreground as the primary visual subject, "
                f"with {role} only as an optional background observer"
            )
        return f"a {subject} as the primary visual subject in the foreground"

    def continuity_lock_fragment(self) -> str:
        parts = [
            f"same primary visual subject ({self.primary_visual_subject})",
            "same species or object identity",
        ]
        if self.required_visible_features:
            parts.append(f"same key anatomy ({', '.join(self.required_visible_features[:3])})")
        parts.extend(("same scale", "same visual silhouette", "same environment continuity"))
        return ", ".join(parts)

    def strict_negative_fragment(self) -> str:
        terms = list(self.negative_prompt_terms or self.forbidden_confusions)
        if not terms:
            return ""
        cleaned = [f"no {term}" if not str(term).lower().startswith("no ") else str(term) for term in terms[:6]]
        return ", ".join(cleaned)


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _topic_blob(*, topic: str, story_brief: dict[str, Any] | None, storyboard: dict[str, Any] | None,
                scene_breakdown: dict[str, Any] | None) -> str:
    parts = [_norm(topic)]
    if story_brief:
        parts.extend(
            str(story_brief.get(key) or "")
            for key in ("logline", "main_character", "subject", "visual_hook")
        )
        topic_detail = dict(story_brief.get("topic_story_detail") or {})
        parts.append(str(topic_detail.get("subject") or ""))
        parts.extend(str(item) for item in list(topic_detail.get("objects") or [])[:4])
    if storyboard:
        parts.extend(
            str(storyboard.get(key) or "")
            for key in ("title", "logline", "main_character")
        )
        for clip in list(storyboard.get("clips") or [])[:4]:
            if isinstance(clip, dict):
                parts.extend(str(clip.get(key) or "") for key in ("summary", "key_visual"))
    if scene_breakdown:
        for clip in list(scene_breakdown.get("clips") or [])[:4]:
            if not isinstance(clip, dict):
                continue
            for scene in list(clip.get("scenes") or [])[:2]:
                if isinstance(scene, dict):
                    parts.append(str(scene.get("subject_action") or ""))
    return " ".join(part for part in parts if part).lower()


def _match_catalog(topic_blob: str) -> dict[str, Any] | None:
    for entry in VISUAL_SUBJECT_CATALOG:
        for pattern in entry.get("patterns") or ():
            if re.search(rf"\b{re.escape(str(pattern))}\b", topic_blob, re.I):
                return entry
    return None


def _infer_human_presenter(*, topic: str, story_brief: dict[str, Any] | None, storyboard: dict[str, Any] | None) -> str:
    candidates: list[str] = []
    if story_brief:
        candidates.append(str(story_brief.get("main_character") or ""))
    if storyboard:
        candidates.append(str(storyboard.get("main_character") or ""))
    blob = _topic_blob(topic=topic, story_brief=story_brief, storyboard=storyboard, scene_breakdown=None)
    for candidate in candidates:
        cleaned = _norm(candidate)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if any(marker in lowered for marker in HUMAN_ROLE_MARKERS):
            return cleaned
        if cleaned.lower() not in blob and any(ch.isalpha() for ch in cleaned):
            return cleaned
    return ""


def _build_lock_from_catalog(
    entry: dict[str, Any],
    *,
    topic: str,
    human_presenter: str,
) -> VisualSubjectLock:
    primary = str(entry.get("primary_visual_subject") or topic)
    features = tuple(str(item) for item in entry.get("required_visible_features") or ())
    forbidden = tuple(str(item) for item in entry.get("forbidden_confusions") or ())
    subject_type = str(entry.get("subject_type") or SUBJECT_TYPE_ANIMAL)
    feature_text = ", ".join(features[:5])
    identity = (
        f"The same {primary} specimen remains the main on-screen subject in every clip"
        + (f", always showing {feature_text}." if feature_text else ".")
    )
    continuity = (
        f"Lock the same {primary} as the hero visual subject across starter and all clips"
        + (f" with {feature_text}." if feature_text else ".")
    )
    negatives = tuple(f"no {item}" for item in forbidden)
    human_role = ""
    if human_presenter and subject_type != SUBJECT_TYPE_PERSON:
        human_role = f"{human_presenter} observer / presenter"
    return VisualSubjectLock(
        primary_visual_subject=primary,
        subject_type=subject_type,
        required_visible_features=features,
        forbidden_confusions=forbidden,
        continuity_phrase=continuity,
        negative_prompt_terms=negatives,
        identity_lock_sentence=identity,
        human_presenter_role=human_role,
    )


def _generic_lock(
    *,
    topic: str,
    story_brief: dict[str, Any] | None,
    human_presenter: str,
    topic_blob: str,
) -> VisualSubjectLock:
    topic_detail = dict((story_brief or {}).get("topic_story_detail") or {})
    subject = _norm(str(topic_detail.get("subject") or topic))
    objects = [str(item) for item in list(topic_detail.get("objects") or [])[:3] if str(item).strip()]
    primary = objects[0] if objects else subject
    if human_presenter and (
        _looks_like_person_topic(topic, human_presenter, primary)
        or not _looks_like_animal_or_object_topic(topic_blob)
    ):
        return VisualSubjectLock(
            primary_visual_subject=human_presenter,
            subject_type=SUBJECT_TYPE_PERSON,
            continuity_phrase=f"Maintain the same {human_presenter} visual identity across all clips.",
            identity_lock_sentence=f"The same {human_presenter} remains the main on-screen subject in every clip.",
        )
    identity = f"The same {primary} remains the main on-screen subject in every clip."
    human_role = ""
    if human_presenter:
        human_role = f"{human_presenter} observer / presenter"
    return VisualSubjectLock(
        primary_visual_subject=primary,
        subject_type=SUBJECT_TYPE_CONCEPT,
        continuity_phrase=f"Maintain the same {primary} visual identity across all clips.",
        identity_lock_sentence=identity,
        human_presenter_role=human_role,
    )


def _looks_like_person_topic(topic: str, human_presenter: str, primary: str) -> bool:
    lowered = _norm(topic).lower()
    if re.search(r"\b(biography|interview|founder|ceo|athlete|celebrity|person|human)\b", lowered):
        return True
    if re.search(
        r"\b(astronaut|detective|survivor|mercenary|artist|hacker|soldier|doctor|pilot|presenter|narrator)\b",
        lowered,
    ):
        return True
    if human_presenter and primary.lower() == human_presenter.lower():
        return True
    return False


def _looks_like_animal_or_object_topic(topic_blob: str) -> bool:
    return _match_catalog(topic_blob) is not None


def extract_visual_subject_lock(
    *,
    topic: str,
    story_brief: dict[str, Any] | None = None,
    storyboard: dict[str, Any] | None = None,
    scene_breakdown: dict[str, Any] | None = None,
) -> VisualSubjectLock:
    """Derive the primary on-screen visual subject lock from topic and director context."""
    brief_dict = dict(story_brief or {})
    board_dict = dict(storyboard or {})
    scene_dict = dict(scene_breakdown or {})
    blob = _topic_blob(
        topic=topic,
        story_brief=brief_dict,
        storyboard=board_dict,
        scene_breakdown=scene_dict,
    )
    human_presenter = _infer_human_presenter(topic=topic, story_brief=brief_dict, storyboard=board_dict)
    matched = _match_catalog(blob)
    if matched:
        return _build_lock_from_catalog(matched, topic=topic, human_presenter=human_presenter)
    return _generic_lock(
        topic=topic,
        story_brief=brief_dict,
        human_presenter=human_presenter,
        topic_blob=blob,
    )
