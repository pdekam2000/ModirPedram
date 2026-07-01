"""Extract structured visual subject memory from story brief and director context."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from content_brain.director.visual_memory_store import VisualSubjectMemory
from content_brain.director.visual_subject_lock import (
    SUBJECT_TYPE_ANIMAL,
    SUBJECT_TYPE_OBJECT,
    SUBJECT_TYPE_PERSON,
    VISUAL_SUBJECT_CATALOG,
    VisualSubjectLock,
    extract_visual_subject_lock,
)

EXTRACTOR_VERSION = "subject_memory_extractor_v1"

SUBJECT_MEMORY_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "patterns": ("lion", "male lion", "lioness"),
        "subject_name": "lion",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "fur_color": "golden tawny fur with sunlit amber highlights",
        "markings": "dark mane framing the face, scar above left eye",
        "body_shape": "powerful muscular feline build, broad chest, heavy mane",
        "eye_color": "amber",
        "eye_shape": "narrow predatory feline eyes",
        "face_shape": "broad leonine muzzle with defined whisker pads",
    },
    {
        "patterns": ("scorpion", "black scorpion", "emperor scorpion"),
        "subject_name": "black scorpion",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "scale_color": "glossy black exoskeleton with subtle blue undertones",
        "markings": "segmented tail with raised stinger, large curved pincers",
        "body_shape": "low arachnid profile, eight legs, segmented tail arch",
        "eye_shape": "small clustered lateral eyes",
    },
    {
        "patterns": ("cat", "orange cat", "tabby cat"),
        "subject_name": "orange cat",
        "subject_type": SUBJECT_TYPE_ANIMAL,
        "fur_color": "warm orange tabby fur with cream underbelly",
        "markings": "subtle tabby stripes along flanks and tail",
        "eye_color": "green",
        "eye_shape": "almond feline eyes",
        "body_shape": "domestic feline proportions, compact agile frame",
        "face_shape": "soft triangular feline face with pink nose",
    },
    {
        "patterns": ("gpu", "graphics card", "rtx", "geforce", "nvidia"),
        "subject_name": "RTX-style graphics card",
        "subject_type": SUBJECT_TYPE_OBJECT,
        "body_shape": "full-length PCIe GPU with triple-fan shroud",
        "scale_color": "matte black metal housing with brushed accents",
        "markings": "three axial fans in a row, RGB accent strip along edge",
        "accessories": "dual 8-pin power connectors, backplate visible",
    },
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _brief_value(story_brief: Any | None, key: str, fallback: str = "") -> str:
    if story_brief is None:
        return fallback
    if isinstance(story_brief, dict):
        return _normalize(str(story_brief.get(key) or fallback))
    return _normalize(str(getattr(story_brief, key, "") or fallback))


def _context_blob(
    *,
    topic: str,
    story_brief: Any | None,
    director_layer: Any | None,
) -> str:
    parts = [_normalize(topic)]
    parts.extend(
        _brief_value(story_brief, key)
        for key in ("logline", "subject", "main_character", "environment", "visual_hook")
    )
    if director_layer is not None:
        if hasattr(director_layer, "storyboard"):
            board = director_layer.storyboard
            parts.extend([_normalize(getattr(board, "main_character", "")), _normalize(getattr(board, "setting", ""))])
        if hasattr(director_layer, "to_dict"):
            layer_dict = director_layer.to_dict()
            board_dict = dict(layer_dict.get("storyboard") or {})
            parts.extend(
                str(board_dict.get(key) or "")
                for key in ("main_character", "setting", "logline")
            )
    return " ".join(part for part in parts if part).lower()


def _match_profile(blob: str) -> dict[str, Any] | None:
    for profile in SUBJECT_MEMORY_PROFILES:
        for pattern in profile.get("patterns") or ():
            if re.search(rf"\b{re.escape(str(pattern))}\b", blob, re.I):
                return profile
    for entry in VISUAL_SUBJECT_CATALOG:
        for pattern in entry.get("patterns") or ():
            if re.search(rf"\b{re.escape(str(pattern))}\b", blob, re.I):
                features = ", ".join(str(item) for item in list(entry.get("required_visible_features") or [])[:4])
                return {
                    "subject_name": str(entry.get("primary_visual_subject") or pattern),
                    "subject_type": str(entry.get("subject_type") or SUBJECT_TYPE_ANIMAL),
                    "markings": features,
                    "body_shape": features,
                }
    return None


def _resolve_lock(
    *,
    topic: str,
    story_brief: Any | None,
    director_layer: Any | None,
    visual_subject_lock: VisualSubjectLock | dict[str, Any] | None,
) -> VisualSubjectLock:
    if visual_subject_lock is not None:
        if isinstance(visual_subject_lock, VisualSubjectLock):
            return visual_subject_lock
        parsed = VisualSubjectLock.from_dict(dict(visual_subject_lock))
        if parsed and parsed.primary_visual_subject:
            return parsed
    story_dict = story_brief.to_dict() if hasattr(story_brief, "to_dict") else dict(story_brief or {})
    board_dict = {}
    if director_layer is not None and hasattr(director_layer, "storyboard"):
        board_dict = director_layer.storyboard.to_dict()
    return extract_visual_subject_lock(topic=topic, story_brief=story_dict, storyboard=board_dict)


def derive_run_id(*, run_id: str = "", topic: str = "", project_id: str = "") -> str:
    explicit = _normalize(run_id)
    if explicit:
        return explicit
    if _normalize(project_id) and project_id != "continuity_project":
        return project_id
    digest = hashlib.sha256(_normalize(topic).encode("utf-8")).hexdigest()[:12]
    return f"memory_{digest}"


def extract_subject_memory(
    *,
    run_id: str,
    topic: str = "",
    story_brief: Any | None = None,
    director_layer: Any | None = None,
    visual_subject_lock: VisualSubjectLock | dict[str, Any] | None = None,
) -> VisualSubjectMemory:
    lock = _resolve_lock(
        topic=topic,
        story_brief=story_brief,
        director_layer=director_layer,
        visual_subject_lock=visual_subject_lock,
    )
    blob = _context_blob(topic=topic, story_brief=story_brief, director_layer=director_layer)
    profile = _match_profile(blob)

    subject_name = str((profile or {}).get("subject_name") or lock.primary_visual_subject or _brief_value(story_brief, "subject") or topic)
    subject_type = str((profile or {}).get("subject_type") or lock.subject_type or "concept")

    anchor_palette = ""
    anchor_lighting = ""
    anchor_camera = ""
    anchor_location = _brief_value(story_brief, "environment") or _brief_value(story_brief, "setting")
    if story_brief is not None:
        anchors = getattr(story_brief, "continuity_anchors", None)
        if anchors is not None and hasattr(anchors, "to_dict"):
            anchor_dict = anchors.to_dict()
            anchor_palette = str(anchor_dict.get("palette") or "")
            anchor_lighting = str(anchor_dict.get("lighting") or "")
            anchor_camera = str(anchor_dict.get("camera") or "")
            anchor_location = anchor_location or str(anchor_dict.get("location") or "")

    features = ", ".join(lock.required_visible_features[:5]) if lock.required_visible_features else ""
    markings = str((profile or {}).get("markings") or features or lock.identity_lock_sentence)

    memory = VisualSubjectMemory(
        run_id=run_id,
        subject_name=_normalize(subject_name),
        subject_type=subject_type,
        face_shape=str((profile or {}).get("face_shape") or ""),
        eye_shape=str((profile or {}).get("eye_shape") or ""),
        eye_color=str((profile or {}).get("eye_color") or ""),
        skin_color=str((profile or {}).get("skin_color") or ""),
        fur_color=str((profile or {}).get("fur_color") or ""),
        scale_color=str((profile or {}).get("scale_color") or ""),
        markings=_normalize(markings),
        body_shape=str((profile or {}).get("body_shape") or features),
        clothing=str((profile or {}).get("clothing") or ""),
        accessories=str((profile or {}).get("accessories") or ""),
        location=anchor_location or _brief_value(story_brief, "environment"),
        weather=str((profile or {}).get("weather") or "consistent atmospheric conditions"),
        lighting=anchor_lighting or "motivated key light with stable direction",
        color_palette=anchor_palette or _brief_value(story_brief, "style_direction", "cinematic natural palette"),
        camera_style=anchor_camera or "documentary cinematic tracking",
        lens=str((profile or {}).get("lens") or "50mm equivalent vertical hero lens"),
        framing=str((profile or {}).get("framing") or "vertical 9:16 subject-dominant lower two-thirds"),
        frame_analysis_hooks={
            "extractor_version": EXTRACTOR_VERSION,
            "director_4_vision_verifier": "ready",
            "openai_vision_frame_analysis": "pending_clip_frames",
            "character_recognition": "pending_clip_frames",
        },
    )
    return memory


__all__ = [
    "EXTRACTOR_VERSION",
    "derive_run_id",
    "extract_subject_memory",
]
