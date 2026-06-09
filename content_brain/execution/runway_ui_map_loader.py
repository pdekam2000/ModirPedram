"""
Phase RUNWAY-STARTER-TO-VIDEO-D — Runway UI map loader (read-only, no browser).

Loads operator-mapped controls from runway_ui_map.json for dry-run / future orchestration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_PATH = ROOT / "project_brain" / "runway_ui_mapping" / "runway_ui_map.json"

FORBIDDEN_TAGS = frozenset({"body", "html"})
GENERIC_SELECTORS = frozenset(
    {"body", "html", "span", "div", "svg", "a", "button", "label", "video", "input", "select", "textarea"}
)
QUALIFIED_SELECTOR_MARKERS = ("[", "#", ":", "data-testid", "aria-label", "role=", "nth-", "-option-")

WEAK_SELECTOR_TOLERANCE = frozenset(
    {
        "use_frame_button",
        "image_use_to_video_option",
    }
)

CRITICAL_NO_BODY_CONTROLS = frozenset(
    {
        "image_generate_button",
        "generate_button",
        "download_mp4_button",
        "image_prompt_input",
        "prompt_input",
        "image_use_to_video_option",
        "remove_image",
    }
)

STARTER_TO_VIDEO_CANONICAL_CONTROLS: tuple[str, ...] = (
    "image_prompt_input",
    "image_aspect_ratio_menu",
    "image_aspect_ratio_9_16",
    "image_count_menu",
    "image_count_1",
    "image_count_4",
    "image_quality_menu",
    "image_quality_1k",
    "image_quality_2k",
    "image_quality_4k",
    "image_generate_button",
    "image_app_menu_button",
    "image_use_to_video_option",
    "gen45_model_button",
    "try_it_now_button",
    "prompt_input",
    "aspect_ratio_menu",
    "aspect_ratio_9_16",
    "duration_menu",
    "duration_10s",
    "generate_button",
    "download_mp4_button",
    "use_frame_button",
    "remove_image",
)

OPTIONAL_RUNWAY_UI_CONTROLS: tuple[str, ...] = (
    "image_card_remove_button",
)

LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "image_prompt_input": (
        "image_prompt_input",
        "Text to Image box",
        "Text to image box",
    ),
    "image_aspect_ratio_menu": ("image_aspect_ratio_menu", "image_aspect_ratio"),
    "image_aspect_ratio_9_16": ("image_aspect_ratio_9_16", "aspect_ratio_9_16"),
    "image_count_menu": ("image_count_menu", "image_count"),
    "image_count_1": ("image_count_1", "1"),
    "image_count_4": ("image_count_4", "4"),
    "image_quality_menu": ("image_quality_menu", "image_quality", "Quality"),
    "image_quality_1k": ("image_quality_1k", "1K", "1k", "image_quality_1K"),
    "image_quality_2k": ("image_quality_2k", "2K", "2k", "image_quality_2K"),
    "image_quality_4k": ("image_quality_4k", "4K", "4k", "image_quality_4K"),
    "image_generate_button": ("image_generate_button", "Generate Image"),
    "image_app_menu_button": ("image_app_menu_button", "APPS VIEDO ART MODUS ZU WÄHLEN VIEDO ART"),
    "image_use_to_video_option": (
        "image_use_to_video_option",
        "sed_to_video1",
        "sed_To_video2",
        "Use to Video",
        "Use in video",
    ),
    "gen45_model_button": ("gen45_model_button", "gen45_option", "Gen-4.5", "Ge-4.5"),
    "try_it_now_button": ("try_it_now_button", "Try it now"),
    "prompt_input": ("prompt_input", "prompt_box", "Prompt Box"),
    "aspect_ratio_menu": ("aspect_ratio_menu",),
    "aspect_ratio_9_16": (
        "aspect_ratio_9_16",
        "aspect_ratio_menu 9: 16",
        "aspect_ratio_menu 9:16",
    ),
    "duration_menu": ("duration_menu", "VIEDO DURATION KONOPF"),
    "duration_10s": ("duration_10s", "10s duration", "10S"),
    "generate_button": ("generate_button", "Geerate", "Generate"),
    "download_mp4_button": ("download_mp4_button", "download_button", "DOWNLOAD MP4"),
    "use_frame_button": ("use_frame_button", "USE FRAME"),
    "remove_image": (
        "remove_image",
        "remove image",
        "REMOVE IMAGE",
        "Remove image",
    ),
    "image_card_remove_button": (
        "image_card_remove_button",
        "Hide output",
        "hide output",
    ),
}


@dataclass(frozen=True)
class ResolvedControl:
    canonical_key: str
    source_label: str
    tag: str
    css_selector: str
    page_url: str
    text: str
    aria_label: str
    valid: bool
    invalid_reason: str = ""
    weak_selector: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_key": self.canonical_key,
            "source_label": self.source_label,
            "tag": self.tag,
            "css_selector": self.css_selector,
            "page_url": self.page_url,
            "text": self.text,
            "aria_label": self.aria_label,
            "valid": self.valid,
            "invalid_reason": self.invalid_reason,
            "weak_selector": self.weak_selector,
        }


@dataclass
class RunwayUIMapSnapshot:
    map_path: str
    version: str
    labels_raw: dict[str, Any]
    controls: dict[str, ResolvedControl] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    invalid: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_path": self.map_path,
            "version": self.version,
            "ok": self.ok,
            "controls": {key: ctrl.to_dict() for key, ctrl in self.controls.items()},
            "missing": list(self.missing),
            "invalid": list(self.invalid),
            "warnings": list(self.warnings),
        }


def _entry_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    meta = dict(entry.get("metadata") or {})
    for field_name in ("tag", "text", "aria_label", "role", "css_selector", "page_url"):
        if field_name not in meta and entry.get(field_name) is not None:
            meta[field_name] = entry.get(field_name)
    if "page_url" not in meta and entry.get("url"):
        meta["page_url"] = entry.get("url")
    selector_candidates = entry.get("selector_candidates") or {}
    if "css_selector" not in meta and selector_candidates.get("css"):
        meta["css_selector"] = selector_candidates.get("css")
    return meta


def _css_selector(entry: dict[str, Any], meta: dict[str, Any]) -> str:
    css = str(meta.get("css_selector") or "").strip()
    if css:
        return css
    selector_candidates = entry.get("selector_candidates") or {}
    return str(selector_candidates.get("css") or "").strip()


def _selector_is_weak(css: str) -> bool:
    normalized = str(css or "").strip().lower()
    if not normalized:
        return True
    if normalized in GENERIC_SELECTORS:
        return True
    if any(marker in normalized for marker in QUALIFIED_SELECTOR_MARKERS):
        return False
    root = normalized.split()[0] if normalized else ""
    return root in GENERIC_SELECTORS


def _find_label_entry(labels: dict[str, Any], canonical: str) -> tuple[str, dict[str, Any]] | None:
    for alias in LABEL_ALIASES.get(canonical, (canonical,)):
        entry = labels.get(alias)
        if isinstance(entry, dict):
            return alias, entry
    return None


def _validate_control(canonical: str, entry: dict[str, Any]) -> ResolvedControl:
    meta = _entry_metadata(entry)
    tag = str(meta.get("tag") or entry.get("tag") or "").lower()
    css = _css_selector(entry, meta)
    text = str(meta.get("text") or entry.get("text") or "")
    aria = str(meta.get("aria_label") or entry.get("aria_label") or "")
    page_url = str(meta.get("page_url") or entry.get("url") or "")
    source_label = str(entry.get("label") or "")

    invalid_reason = ""
    if not css:
        invalid_reason = "empty css selector"
    elif tag in FORBIDDEN_TAGS or css.lower() in {"body", "html"}:
        invalid_reason = f"forbidden tag/selector ({tag or css})"
    elif canonical in CRITICAL_NO_BODY_CONTROLS and tag in FORBIDDEN_TAGS:
        invalid_reason = "critical control mapped to body/html"

    weak = _selector_is_weak(css)
    valid = not invalid_reason

    return ResolvedControl(
        canonical_key=canonical,
        source_label=source_label,
        tag=tag,
        css_selector=css,
        page_url=page_url,
        text=text,
        aria_label=aria,
        valid=valid,
        invalid_reason=invalid_reason,
        weak_selector=weak,
    )


def load_runway_ui_map(*, map_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Runway UI map not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_runway_ui_controls(
    ui_map: dict[str, Any] | None = None,
    *,
    map_path: Path | str | None = None,
    required: tuple[str, ...] | None = None,
) -> RunwayUIMapSnapshot:
    """Resolve canonical controls; fail only on missing/invalid critical selectors."""
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH
    data = ui_map if ui_map is not None else load_runway_ui_map(map_path=path)
    labels: dict[str, Any] = dict(data.get("labels") or {})
    required_keys = required or STARTER_TO_VIDEO_CANONICAL_CONTROLS

    snapshot = RunwayUIMapSnapshot(
        map_path=str(path),
        version=str(data.get("version") or "unknown"),
        labels_raw=labels,
    )

    for canonical in required_keys:
        found = _find_label_entry(labels, canonical)
        if not found:
            snapshot.missing.append(canonical)
            continue
        alias, entry = found
        resolved = _validate_control(canonical, entry)
        if alias != canonical:
            snapshot.warnings.append(
                f"{canonical}: normalized from legacy label '{alias}'"
            )
        if not resolved.valid:
            snapshot.invalid.append(
                {"control": canonical, "reason": resolved.invalid_reason or "invalid"}
            )
        elif resolved.weak_selector:
            msg = f"{canonical}: weak selector '{resolved.css_selector}'"
            if canonical in WEAK_SELECTOR_TOLERANCE:
                snapshot.warnings.append(msg + " (tolerated)")
            else:
                snapshot.warnings.append(msg)
        snapshot.controls[canonical] = resolved

    for optional in OPTIONAL_RUNWAY_UI_CONTROLS:
        if optional in snapshot.controls:
            continue
        found = _find_label_entry(labels, optional)
        if not found:
            continue
        alias, entry = found
        resolved = _validate_control(optional, entry)
        if alias != optional:
            snapshot.warnings.append(
                f"{optional}: normalized from legacy label '{alias}'"
            )
        if not resolved.valid:
            snapshot.warnings.append(
                f"{optional}: optional control invalid ({resolved.invalid_reason or 'invalid'})"
            )
            continue
        if resolved.weak_selector:
            snapshot.warnings.append(
                f"{optional}: weak selector '{resolved.css_selector}' (optional, tolerated)"
            )
        snapshot.controls[optional] = resolved

    snapshot.ok = not snapshot.missing and not snapshot.invalid
    return snapshot


def controls_ready_for_dry_run(snapshot: RunwayUIMapSnapshot) -> bool:
    return snapshot.ok


def selector_is_weak(css: str) -> bool:
    """Public alias for weak selector detection."""
    return _selector_is_weak(css)
