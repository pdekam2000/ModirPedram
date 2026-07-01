"""Load and validate Kling Multishot UI map labels (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_brain.execution.kling_multishot_config import (
    OPTIONAL_KLING_LABELS,
    REQUIRED_KLING_LABELS,
)
from content_brain.execution.runway_ui_map_loader import (
    DEFAULT_MAP_PATH,
    ResolvedControl,
    _css_selector,
    _entry_metadata,
    _selector_is_weak,
)

KLING_MAP_LOADER_VERSION = "kling_multishot_map_loader_v1"

FORBIDDEN_TAGS = frozenset({"body", "html", "path"})


@dataclass
class KlingMultishotMapSnapshot:
    map_path: str
    version: str
    controls: dict[str, ResolvedControl] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    invalid: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safety: dict[str, Any] = field(default_factory=dict)
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": KLING_MAP_LOADER_VERSION,
            "map_path": self.map_path,
            "ok": self.ok,
            "controls": {key: ctrl.to_dict() for key, ctrl in self.controls.items()},
            "missing": list(self.missing),
            "invalid": list(self.invalid),
            "warnings": list(self.warnings),
            "safety": dict(self.safety),
        }


def load_kling_ui_map(*, map_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Runway UI map not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_kling_control(label: str, entry: dict[str, Any]) -> ResolvedControl:
    meta = _entry_metadata(entry)
    tag = str(meta.get("tag") or entry.get("tag") or "").lower()
    css = _css_selector(entry, meta)
    text = str(meta.get("text") or entry.get("text") or "")
    aria = str(meta.get("aria_label") or entry.get("aria_label") or "")
    page_url = str(meta.get("page_url") or entry.get("url") or "")

    invalid_reason = ""
    if not css:
        invalid_reason = "empty css selector"
    elif tag in FORBIDDEN_TAGS:
        invalid_reason = f"forbidden tag ({tag})"
    elif _selector_is_weak(css):
        invalid_reason = f"generic or weak selector ({css})"

    return ResolvedControl(
        canonical_key=label,
        source_label=str(entry.get("label") or label),
        tag=tag,
        css_selector=css,
        page_url=page_url,
        text=text,
        aria_label=aria,
        valid=not invalid_reason,
        invalid_reason=invalid_reason,
        weak_selector=_selector_is_weak(css),
    )


def resolve_kling_multishot_controls(
    ui_map: dict[str, Any] | None = None,
    *,
    map_path: Path | str | None = None,
) -> KlingMultishotMapSnapshot:
    path = Path(map_path) if map_path else DEFAULT_MAP_PATH
    data = ui_map if ui_map is not None else load_kling_ui_map(map_path=path)
    labels: dict[str, Any] = dict(data.get("labels") or {})
    snapshot = KlingMultishotMapSnapshot(
        map_path=str(path.resolve()),
        version=str(data.get("version") or "unknown"),
        safety=dict(data.get("safety") or {}),
    )

    for label in REQUIRED_KLING_LABELS:
        entry = labels.get(label)
        if not isinstance(entry, dict):
            snapshot.missing.append(label)
            continue
        resolved = _validate_kling_control(label, entry)
        if not resolved.valid:
            snapshot.invalid.append({"label": label, "reason": resolved.invalid_reason or "invalid"})
        snapshot.controls[label] = resolved

    for label in OPTIONAL_KLING_LABELS:
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


def verify_generate_approval_gate(ui_map: dict[str, Any]) -> tuple[bool, str]:
    safety = dict(ui_map.get("safety") or {})
    requires = list(safety.get("requires_approval") or [])
    if "generate_button" not in requires:
        return False, "generate_button not in safety.requires_approval"
    if not safety.get("generate_never_auto_clicked"):
        return False, "generate_never_auto_clicked is not true"
    return True, ""


def label_playwright_hint(entry: dict[str, Any]) -> str:
    candidates = entry.get("selector_candidates") or {}
    meta = _entry_metadata(entry)
    return str(
        candidates.get("playwright")
        or meta.get("playwright_locator")
        or ""
    ).strip()


__all__ = [
    "KlingMultishotMapSnapshot",
    "label_playwright_hint",
    "load_kling_ui_map",
    "resolve_kling_multishot_controls",
    "verify_generate_approval_gate",
]
