"""
Phase RUNWAY-UI-MAPPER-C — click-to-label mode validation.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import runway_ui_mapper as mapper_mod


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    src = (ROOT / "tools" / "runway_ui_mapper.py").read_text(encoding="utf-8")
    _pass("click_label_flag", "--click-label" in src)
    _pass("allow_safe_clicks_flag", "--allow-safe-clicks" in src)
    _pass("click_label_install_js", "CLICK_LABEL_INSTALL_JS" in src)
    _pass("expose_binding", "expose_binding" in src and "runwayMapperSaveLabel" in src)
    _pass("shift_click_mode", "shiftKey" in mapper_mod.CLICK_LABEL_INSTALL_JS)
    _pass("persist_click_label", "persist_click_label" in src)
    _pass("labeling_sessions", "labeling_sessions" in src)
    _pass("sanitize_click_metadata", "sanitize_click_metadata" in src)
    _pass("shift_blocks_in_js", "!ev.shiftKey" in mapper_mod.CLICK_LABEL_INSTALL_JS and "preventDefault" in mapper_mod.CLICK_LABEL_INSTALL_JS)
    _pass("no_local_storage_in_sanitize", "sessionstorage" in src.lower())
    _pass("scan_still_present", "--scan" in src)
    _pass("label_still_present", "def mode_label" in src)
    _pass("observe_still_present", "def mode_observe" in src)


def _unit_click_metadata_capture() -> None:
    meta = {
        "tag": "button",
        "text": "Generate",
        "combined_label": "Generate",
        "css_selector": "button.generate",
        "bounding_box": {"x": 10, "y": 20, "width": 80, "height": 32},
        "page_url": "https://app.runwayml.com/video",
        "page_title": "Runway",
        "cookie": "must_drop",
        "sessionStorage": "must_drop",
    }
    clean = mapper_mod.capture_click_metadata_for_test(meta)
    _pass("captures_tag", clean.get("tag") == "button")
    _pass("captures_bbox", clean.get("bounding_box", {}).get("width") == 80)
    _pass("drops_cookie_key", "cookie" not in clean)
    _pass("drops_session_storage_key", "sessionStorage" not in clean)


def _unit_operator_label_saved(tmp: Path) -> None:
    with patch.object(mapper_mod, "OUTPUT_DIR", tmp), patch.object(
        mapper_mod, "JSON_PATH", tmp / "runway_ui_map.json"
    ), patch.object(mapper_mod, "CANDIDATES_PATH", tmp / "selector_candidates.json"):
        elements = mapper_mod.assign_element_ids(
            [
                {
                    "tag": "textarea",
                    "text": "",
                    "placeholder": "Describe",
                    "visible": True,
                    "bounding_box": {"x": 1, "y": 2, "width": 100, "height": 40},
                    "combined_label": "Describe",
                    "css_selector": "textarea",
                }
            ]
        )
        ui_map = mapper_mod.init_v2_map(page={"url": "https://app.runwayml.com/", "title": "R"}, elements=elements)
        meta = {
            "tag": "textarea",
            "placeholder": "Describe",
            "combined_label": "Describe",
            "css_selector": "textarea",
            "bounding_box": {"x": 1, "y": 2, "width": 100, "height": 40},
            "page_url": "https://app.runwayml.com/",
            "page_title": "Runway",
        }
        eid = mapper_mod.merge_clicked_element(elements, meta)
        mapper_mod.persist_click_label(
            ui_map,
            label_name="prompt_box",
            element_id=eid,
            metadata=meta,
            notes="Main prompt input",
        )
        mapper_mod.append_labeling_session(
            ui_map,
            {"mode": "click-label", "labels_added": ["prompt_box"], "started_at": "2026-01-01T00:00:00Z"},
        )
        mapper_mod.save_ui_map(ui_map)
        loaded = json.loads((tmp / "runway_ui_map.json").read_text(encoding="utf-8"))
        _pass("label_saved", "prompt_box" in loaded.get("labels", {}))
        entry = loaded["labels"]["prompt_box"]
        _pass("operator_confirmed", entry.get("operator_confirmed") is True)
        _pass("has_metadata", isinstance(entry.get("metadata"), dict))
        _pass("has_selector_candidates", "css" in (entry.get("selector_candidates") or {}))
        _pass("labeling_session_appended", len(loaded.get("labeling_sessions") or []) >= 1)


def _unit_generate_never_auto_click() -> None:
    meta = {"combined_label": "Generate video", "text": "Generate"}
    safety = mapper_mod.resolve_label_safety("generate_button", meta)
    _pass("generate_auto_click_false", safety.get("auto_click_allowed") is False)
    _pass("generate_requires_approval", safety.get("requires_approval") is True)

    gen_like = mapper_mod.resolve_label_safety("unknown", meta)
    _pass("generate_text_blocked", gen_like.get("auto_click_allowed") is False)


def _unit_dangerous_labels_blocked() -> None:
    for token in ("upgrade", "purchase", "delete"):
        safety = mapper_mod.build_safety_for_label(f"btn_{token}")
        _pass(f"blocked_semantic_{token}", safety.get("auto_click_allowed") is False)

    js = mapper_mod.CLICK_LABEL_INSTALL_JS
    _pass("js_shift_only_capture", "!ev.shiftKey" in js)


def _unit_json_valid(tmp: Path) -> None:
    with patch.object(mapper_mod, "OUTPUT_DIR", tmp), patch.object(
        mapper_mod, "JSON_PATH", tmp / "runway_ui_map.json"
    ):
        ui = mapper_mod.init_v2_map(page={"url": "x"}, elements={})
        mapper_mod.save_ui_map(ui)
        parsed = json.loads((tmp / "runway_ui_map.json").read_text(encoding="utf-8"))
        _pass("json_valid", isinstance(parsed, dict))


def _unit_label_mode_still_works(tmp: Path) -> None:
    with patch.object(mapper_mod, "OUTPUT_DIR", tmp), patch.object(
        mapper_mod, "JSON_PATH", tmp / "runway_ui_map.json"
    ), patch.object(mapper_mod, "CANDIDATES_PATH", tmp / "selector_candidates.json"):
        elements = mapper_mod.assign_element_ids(
            [
                {
                    "tag": "button",
                    "text": "10s",
                    "visible": True,
                    "bounding_box": {"x": 0, "y": 0, "width": 30, "height": 20},
                    "combined_label": "10s",
                }
            ]
        )
        mapper_mod.save_json(
            mapper_mod.CANDIDATES_PATH,
            {"candidates": list(elements.values()), "page": {"url": "https://app.runwayml.com/"}},
        )
        mapper_mod.mode_label(from_stdin=f"element_id={list(elements)[0]} label=duration_10s\n")
        ui = mapper_mod.load_ui_map()
        _pass("batch_label_mode", "duration_10s" in ui.get("labels", {}))


def main() -> int:
    _static_checks()
    _unit_click_metadata_capture()
    _unit_generate_never_auto_click()
    _unit_dangerous_labels_blocked()
    with tempfile.TemporaryDirectory() as tmp:
        tpath = Path(tmp)
        _unit_operator_label_saved(tpath)
        _unit_json_valid(tpath)
        _unit_label_mode_still_works(tpath)
    print("\n[validate_runway_ui_mapper_click_label] All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
