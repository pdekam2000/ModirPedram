"""
Phase RUNWAY-BROWSER-CONTINUITY — hover-label mode validation (no browser).
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
    _pass("hover_label_flag", "--hover-label" in src)
    _pass("hover_install_js", "HOVER_LABEL_INSTALL_JS" in src)
    _pass("mode_hover_label", "def mode_hover_label" in src)
    _pass("l_key_trigger", "function isLKey" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("mapper_keydown_log", "MAPPER_KEYDOWN" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("mapper_l_detected_log", "MAPPER_L_DETECTED" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("hover_capture_start_log", "MAPPER_HOVER_CAPTURE_START" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("hover_popup_open_log", "MAPPER_HOVER_POPUP_OPEN" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("hover_badge_text", "HOVER MODE ACTIVE" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("l_detected_flash", "L DETECTED" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("window_keydown_listener", "window.addEventListener('keydown', onKeyDown" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("document_keydown_listener", "document.addEventListener('keydown', onKeyDown" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("no_document_click_capture", "document.addEventListener('click', onClick" not in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("capture_mode_hover", "capture_mode: 'hover_label'" in mapper_mod.HOVER_LABEL_INSTALL_JS)
    _pass("click_label_unchanged", "def mode_click_label" in src and "CLICK_LABEL_INSTALL_JS" in src)


def _unit_hover_save_payload(tmp: Path) -> None:
    with patch.object(mapper_mod, "OUTPUT_DIR", tmp), patch.object(
        mapper_mod, "JSON_PATH", tmp / "runway_ui_map.json"
    ):
        ui_map = mapper_mod.init_v2_map(
            page={"url": "https://app.runwayml.com/", "title": "Runway"},
            elements={},
        )
        payload = {
            "label_name": "download_mp4_button",
            "capture_mode": "hover_label",
            "metadata": {
                "tag": "button",
                "text": "Download",
                "aria_label": "Download",
                "css_selector": "button[aria-label=\"Download\"]",
                "bounding_box": {"x": 100, "y": 200, "width": 80, "height": 32},
                "page_url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
                "page_title": "Runway",
                "capture_mode": "hover_label",
            },
        }
        label_name = mapper_mod.process_popup_save_payload(ui_map, ui_map["elements"], payload)
        mapper_mod.save_ui_map(ui_map)
        loaded = json.loads((tmp / "runway_ui_map.json").read_text(encoding="utf-8"))
        entry = loaded["labels"][label_name]
        _pass("hover_label_saved", label_name == "download_mp4_button")
        _pass("capture_mode_stored", entry.get("capture_mode") == "hover_label")
        _pass("confirmed_by_hover", entry.get("confirmed_by") == "hover_label_l_key")
        _pass("not_body_tag", entry.get("tag") == "button")
        report = mapper_mod.validate_continuity_mapping(loaded)
        _pass("download_valid_after_hover", "download_mp4_button" not in str(report.get("invalid")))


def main() -> int:
    print("[validate_runway_ui_mapper_hover_label] Static + unit checks")
    _static_checks()
    with tempfile.TemporaryDirectory() as tmpdir:
        _unit_hover_save_payload(Path(tmpdir))
    print("\n[validate_runway_ui_mapper_hover_label] All checks passed.")
    print("\nOperator flow:")
    print("  1. python tools/runway_ui_mapper.py --hover-label")
    print("  2. Confirm badge: HOVER MODE ACTIVE")
    print("  3. Open DevTools Console - press any key -> MAPPER_KEYDOWN")
    print("  4. Hover Download MP4 button, click page background (not prompt box)")
    print("  5. Press L -> MAPPER_L_DETECTED + green 'L DETECTED' flash")
    print("  4. Save label: download_mp4_button")
    print("  5. python tools/runway_ui_mapper.py --validate-continuity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
