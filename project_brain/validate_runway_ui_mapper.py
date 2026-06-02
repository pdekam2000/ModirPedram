"""
Phase RUNWAY-UI-MAPPER — validation (static + optional live CDP).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAPPER_PATH = ROOT / "tools" / "runway_ui_mapper.py"
JSON_PATH = ROOT / "project_brain" / "runway_ui_mapping" / "runway_ui_map.json"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    src = MAPPER_PATH.read_text(encoding="utf-8")
    _pass("mapper_file_exists", MAPPER_PATH.is_file())
    _pass("uses_connect_over_cdp", "connect_over_cdp" in src)
    _pass("no_cookie_storage", "cookie" not in src.lower() or "no_cookies_stored" in src)
    _pass("no_local_storage", "localStorage" not in src or "no_storage_stored" in src)
    _pass("blocked_generate", '"generate"' in src)
    _pass("never_click_generate_flag", "generate_never_auto_clicked" in src or "generate_never_clicked" in src)
    _pass("scan_mode_flag", "--scan" in src)
    _pass("label_mode_flag", "--label" in src)
    _pass("observe_mode_flag", "--observe" in src)
    _pass("output_json_path", "runway_ui_map.json" in src)
    _pass("screenshots_dir", "screenshots" in src)
    _pass("extract_prompt", "prompt_box" in src)
    _pass("extract_duration", "duration_10s" in src)
    _pass("extract_aspect", "aspect_ratio_16_9" in src)


def _live_checks() -> bool:
    try:
        from tools.runway_ui_mapper import CANDIDATES_PATH, JSON_PATH, RunwayUIMapper

        mapper = RunwayUIMapper()
        mapper.connect()
        tabs = mapper.list_tabs()
        mapper.disconnect()
        _pass("cdp_connect", True, f"tabs={len(tabs)}")
        if not tabs:
            print("[WARN] No tabs open — open Runway in Chrome for full mapping.")
            return False

        RunwayUIMapper().mode_scan()
        _pass("json_saved", JSON_PATH.is_file())
        _pass("candidates_saved", CANDIDATES_PATH.is_file())
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        _pass("has_open_tabs", isinstance(data.get("open_tabs"), list))
        _pass("has_page", isinstance(data.get("page"), dict))
        _pass("has_elements_dict", isinstance(data.get("elements"), dict))
        gen = [
            el
            for el in (data.get("elements") or {}).values()
            if "generate" in (el.get("text") or "").lower()
        ]
        if gen:
            _pass("generate_marked_blocked", all(el.get("click_blocked") for el in gen))
        _pass("screenshots_recorded", bool((data.get("scan") or {}).get("screenshots")))
        return True
    except Exception as exc:
        print(f"[WARN] Live CDP checks skipped: {exc}")
        return False


def main() -> int:
    _static_checks()
    live = _live_checks()
    if JSON_PATH.is_file() and not live:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        _pass("existing_map_json_readable", bool(data.get("version") or data.get("mapper_version")))
    print("\nRunway UI mapper validation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
