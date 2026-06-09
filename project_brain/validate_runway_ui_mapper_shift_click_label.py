"""
Phase RUNWAY-UI-MAPPER — Alt+Click + Mapper force mode validation.
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
    js = mapper_mod.CLICK_LABEL_INSTALL_JS
    _pass("alt_key_gate", "altKey" in js and "__runwayMapperAltDown" in js)
    _pass("force_mode_flag", "__runwayMapperForceMode" in js)
    _pass("capture_active_fn", "isCaptureActive" in js)
    _pass("capture_prevents_default", "ev.preventDefault()" in js)
    _pass("popup_id", 'runway-mapper-popup' in js)
    _pass("popup_save_button", "#rm-save" in js and "MAPPER_POPUP_SAVE_CLICKED" in js)
    _pass("popup_cancel_button", "#rm-cancel" in js and "MAPPER_POPUP_CANCEL_CLICKED" in js)
    _pass("popup_contains_guard", "popup.contains(ev.target)" in js)
    _pass("popup_save_debug", "MAPPER_POPUP_SAVE_CLICKED" in js)
    _pass("popup_cancel_debug", "MAPPER_POPUP_CANCEL_CLICKED" in js)
    _pass("toggle_id", "runway-mapper-toggle" in js)
    _pass("dom_save_bridge", "data-runway-mapper-pending-save" in js)
    _pass("python_dom_poll", "_poll_dom_save_bridge" in src)
    _pass("popup_label_only", "rm-label-input" in js and "rm-notes" not in js)
    _pass("console_save_bridge", mapper_mod.CLICK_LABEL_SAVE_PREFIX in js)
    _pass("escape_closes_popup", "Escape" in js)
    _pass("save_binding", "runwayMapperSaveLabel" in src)
    _pass("expose_save_binding", "expose_binding" in src and "runwayMapperSaveLabel" in src)
    _pass("process_popup_save", "process_popup_save_payload" in src)
    _pass("console_handler", "page.on(\"console\"" in src or "page.on('console'" in src)
    _pass("any_tab_click_label", "require_runway=False" in src)
    _pass("no_report_click_binding", "runwayMapperReportClick" not in src)
    _pass("scan_still_present", "--scan" in src)
    _pass("label_still_present", "def mode_label" in src)
    _pass("observe_still_present", "def mode_observe" in src)
    _pass("uses_ev_target", "ev.target" in js)
    _pass("mapper_click_debug", "MAPPER_CLICK" in js)
    _pass("mapper_toggle_button", "Mapper: OFF" in js and "runway-mapper-toggle" in js)
    _pass("passive_false_capture", "passive: false" in js)
    _pass("inject_all_frames", "_inject_click_label_frames" in src or "page.frames" in src)
    _pass("save_prefix_constant", hasattr(mapper_mod, "CLICK_LABEL_SAVE_PREFIX"))


def _unit_popup_save() -> None:
    meta = {
        "tag": "button",
        "text": "10s",
        "aria_label": "",
        "role": "button",
        "css_selector": "button",
        "bounding_box": {"x": 1, "y": 2, "width": 40, "height": 24},
        "page_url": "https://app.runwayml.com/",
        "page_title": "Runway",
    }
    payload = {"label_name": "duration_10s", "metadata": meta}
    with tempfile.TemporaryDirectory() as tmp:
        tpath = Path(tmp)
        with patch.object(mapper_mod, "OUTPUT_DIR", tpath), patch.object(
            mapper_mod, "JSON_PATH", tpath / "runway_ui_map.json"
        ):
            ui_map = mapper_mod.init_v2_map(
                page={"url": "https://app.runwayml.com/", "title": "R"},
                elements={},
            )
            mapper_mod.process_popup_save_payload(ui_map, ui_map["elements"], payload)
            mapper_mod.save_ui_map(ui_map)
            loaded = json.loads((tpath / "runway_ui_map.json").read_text(encoding="utf-8"))
            entry = loaded["labels"]["duration_10s"]
            _pass("label_saved", entry.get("operator_confirmed") is True)
            _pass("has_text", entry.get("text") == "10s")
            _pass("has_tag", entry.get("tag") == "button")
            _pass("has_bbox", entry.get("bounding_box", {}).get("width") == 40)
            _pass("has_url", "runwayml.com" in entry.get("url", ""))
            _pass("has_selector", entry.get("selector_candidates", {}).get("css") == "button")


def _unit_generate_safety() -> None:
    meta = {"text": "Generate", "combined_label": "Generate"}
    safety = mapper_mod.resolve_label_safety("generate_button", meta)
    _pass("generate_not_auto", safety.get("auto_click_allowed") is False)
    _pass("generate_requires_approval", safety.get("requires_approval") is True)


def _unit_sanitize_storage() -> None:
    meta = {"text": "Go", "localStorage": "x", "cookie": "y"}
    clean = mapper_mod.sanitize_click_metadata(meta)
    _pass("no_local_storage", "localStorage" not in clean)
    _pass("no_cookie", "cookie" not in clean)


def _unit_parse_save_line() -> None:
    line = mapper_mod.CLICK_LABEL_SAVE_PREFIX + json.dumps(
        {"label_name": "test_button", "metadata": {"tag": "button"}, "_save_id": "1"}
    )
    payload = mapper_mod._parse_save_line(line)
    _pass("parse_save_line", payload and payload.get("label_name") == "test_button")


def _unit_json_valid() -> None:
    ui = mapper_mod.init_v2_map(page={"url": "x"}, elements={})
    json.dumps(ui)


def main() -> int:
    _static_checks()
    _unit_popup_save()
    _unit_generate_safety()
    _unit_sanitize_storage()
    _unit_parse_save_line()
    _unit_json_valid()
    print("\n[validate_runway_ui_mapper_shift_click_label] All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
