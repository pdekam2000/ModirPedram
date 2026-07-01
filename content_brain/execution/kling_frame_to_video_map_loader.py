"""Load and validate Kling Frame-to-Video UI map labels (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.kling_frame_to_video_config import (
    DOWNLOAD_BUTTON_ALIASES,
    OPTIONAL_KLING_FRAME_LABELS,
    REQUIRED_KLING_FRAME_LABELS,
)
from content_brain.execution.kling_multishot_map_loader import (
    FORBIDDEN_TAGS,
    KlingMultishotMapSnapshot,
    _validate_kling_control,
    verify_generate_approval_gate,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, ResolvedControl, _selector_is_weak

KLING_FRAME_MAP_LOADER_VERSION = "kling_frame_to_video_map_loader_v1"


@dataclass
class KlingFrameToVideoMapSnapshot:
    map_path: str
    version: str
    controls: dict[str, ResolvedControl] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    invalid: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": KLING_FRAME_MAP_LOADER_VERSION,
            "map_path": self.map_path,
            "ok": self.ok,
            "controls": {key: ctrl.to_dict() for key, ctrl in self.controls.items()},
            "missing": list(self.missing),
            "invalid": list(self.invalid),
            "warnings": list(self.warnings),
            "aliases": dict(self.aliases),
            "safety": dict(self.safety),
        }


def load_kling_frame_ui_map(*, map_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Runway UI map not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_label_entry(labels: dict[str, Any], label: str) -> tuple[dict[str, Any] | None, str]:
    entry = labels.get(label)
    if isinstance(entry, dict):
        return entry, label
    if label == "download_button":
        for alias in DOWNLOAD_BUTTON_ALIASES:
            if alias == label:
                continue
            alt = labels.get(alias)
            if isinstance(alt, dict):
                return alt, alias
    return None, label


def _accept_frame_locator_backed_control(
    label: str,
    entry: dict[str, Any],
    resolved: ResolvedControl,
) -> tuple[ResolvedControl, str | None]:
    """Operator-captured or role-backed controls may have weak map CSS; locators are primary."""
    if resolved.valid:
        return resolved, None

    reason = resolved.invalid_reason or ""
    role_backed = label.startswith("duration_") or label == "download_button"
    operator_backed = bool(entry.get("operator_confirmed") or entry.get("confirmed_by"))
    refresh = str((entry.get("selector_candidates") or {}).get("refresh_strategy") or "")

    if role_backed or operator_backed or refresh:
        if any(
            token in reason
            for token in ("weak selector", "forbidden tag", "generic or weak")
        ):
            warning = f"{label}: map css weak ({resolved.css_selector or 'none'}) — using role/text locator"
            return ResolvedControl(
                canonical_key=resolved.canonical_key,
                source_label=resolved.source_label,
                tag=resolved.tag,
                css_selector=resolved.css_selector,
                page_url=resolved.page_url,
                text=resolved.text,
                aria_label=resolved.aria_label,
                valid=True,
                invalid_reason="",
                weak_selector=True,
            ), warning

    return resolved, None


def resolve_kling_frame_to_video_controls(
    ui_map: dict[str, Any] | None = None,
    *,
    map_path: Path | str | None = None,
) -> KlingFrameToVideoMapSnapshot:
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH
    data = ui_map if ui_map is not None else load_kling_frame_ui_map(map_path=path)
    labels: dict[str, Any] = dict(data.get("labels") or {})
    snapshot = KlingFrameToVideoMapSnapshot(
        map_path=str(path.resolve()),
        version=str(data.get("version") or "unknown"),
        safety=dict(data.get("safety") or {}),
    )

    for label in REQUIRED_KLING_FRAME_LABELS:
        entry, source = _resolve_label_entry(labels, label)
        if entry is None:
            snapshot.missing.append(label)
            continue
        if source != label:
            snapshot.aliases[label] = source
        resolved = _validate_kling_control(label, entry)
        resolved, warn = _accept_frame_locator_backed_control(label, entry, resolved)
        if warn:
            snapshot.warnings.append(warn)
        if not resolved.valid and label.startswith("duration_slider"):
            # Role/class strategies are primary; weak css alone is acceptable with warning.
            css = str(resolved.css_selector or "")
            if css in {"[role=\"slider\"]", "[class*=\"Slider__Root\"]", "button[aria-label=\"Duration\"]"}:
                resolved = ResolvedControl(
                    canonical_key=label,
                    source_label=resolved.source_label,
                    tag=resolved.tag,
                    css_selector=css,
                    page_url=resolved.page_url,
                    text=resolved.text,
                    aria_label=resolved.aria_label,
                    valid=True,
                    invalid_reason="",
                    weak_selector=False,
                )
        if not resolved.valid:
            snapshot.invalid.append({"label": label, "reason": resolved.invalid_reason or "invalid"})
        snapshot.controls[label] = resolved

    for label in OPTIONAL_KLING_FRAME_LABELS:
        entry = labels.get(label)
        if not isinstance(entry, dict):
            continue
        resolved = _validate_kling_control(label, entry)
        if resolved.valid:
            snapshot.controls[label] = resolved
        else:
            snapshot.warnings.append(f"optional {label}: {resolved.invalid_reason}")

    snapshot.ok = not snapshot.missing and not snapshot.invalid
    return snapshot


__all__ = [
    "KlingFrameToVideoMapSnapshot",
    "load_kling_frame_ui_map",
    "resolve_kling_frame_to_video_controls",
    "verify_generate_approval_gate",
]
