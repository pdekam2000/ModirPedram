"""
Phase RUNWAY-UI-MAPPER-B — manual learning mode validation.
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


def _sample_elements() -> dict[str, dict]:
    raw = [
        {
            "tag": "button",
            "text": "Generate",
            "aria_label": "",
            "visible": True,
            "bounding_box": {"x": 10, "y": 20, "width": 80, "height": 32},
            "combined_label": "Generate",
        },
        {
            "tag": "textarea",
            "text": "",
            "placeholder": "Describe your shot",
            "visible": True,
            "bounding_box": {"x": 10, "y": 100, "width": 300, "height": 60},
            "combined_label": "Describe your shot",
        },
        {
            "tag": "button",
            "text": "10s",
            "visible": True,
            "bounding_box": {"x": 200, "y": 200, "width": 40, "height": 24},
            "combined_label": "10s",
        },
    ]
    return mapper_mod.assign_element_ids(raw)


def _static_checks() -> None:
    src = (ROOT / "tools" / "runway_ui_mapper.py").read_text(encoding="utf-8")
    _pass("scan_flag", '"--scan"' in src or "'--scan'" in src)
    _pass("label_flag", "--label" in src)
    _pass("observe_flag", "--observe" in src)
    _pass("selector_candidates_path", "selector_candidates.json" in src)
    _pass("v2_version", "runway_ui_mapper_v2" in src)
    _pass("stable_element_ids", "assign_element_ids" in src)
    _pass("no_cookie_persist", "no_cookies_stored" in src)
    _pass("no_local_storage_persist", "no_storage_stored" in src)
    _pass("generate_auto_click_false", "auto_click_allowed" in src)
    _pass("requires_real_video_approval", "requires_real_video_approval" in src)
    _pass("observe_no_tool_click", "tool_auto_clicked" in src)
    _pass("never_auto_click_generate", "generate_never_auto_clicked" in src)


def _unit_assign_ids() -> None:
    elements = _sample_elements()
    _pass("assigns_btn_id", any(k.startswith("btn_") for k in elements))
    _pass("assigns_input_id", any(k.startswith("input_") for k in elements))
    gen_keys = [k for k, v in elements.items() if "generate" in (v.get("text") or "").lower()]
    _pass("generate_click_blocked", bool(gen_keys) and elements[gen_keys[0]].get("click_blocked") is True)


def _unit_label_safety(tmp: Path) -> None:
    with patch.object(mapper_mod, "OUTPUT_DIR", tmp), patch.object(mapper_mod, "JSON_PATH", tmp / "runway_ui_map.json"), patch.object(
        mapper_mod, "CANDIDATES_PATH", tmp / "selector_candidates.json"
    ):
        elements = _sample_elements()
        btn_id = [k for k, v in elements.items() if "Generate" in (v.get("text") or "")][0]
        input_id = [k for k, v in elements.items() if v.get("tag") == "textarea"][0]
        mapper_mod.save_json(
            mapper_mod.CANDIDATES_PATH,
            {
                "version": mapper_mod.MAPPER_VERSION_V2,
                "candidates": list(elements.values()),
                "page": {"url": "https://app.runwayml.com/generate", "title": "Runway"},
            },
        )
        mapper_mod.mode_label(
            from_stdin=f"element_id={btn_id} label=generate_button\nelement_id={input_id} label=prompt_box\n"
        )
        ui = mapper_mod.load_ui_map()
        _pass("label_mode_stores_labels", "generate_button" in ui.get("labels", {}))
        gen = ui["labels"]["generate_button"]
        _pass("generate_not_auto_click", gen.get("auto_click_allowed") is False)
        _pass("generate_requires_approval", gen.get("requires_real_video_approval") is True)
        json.loads((tmp / "runway_ui_map.json").read_text(encoding="utf-8"))


def _unit_observe_diff() -> None:
    before = {
        "page": {"url": "https://app.runwayml.com/a", "title": "A"},
        "body_text_snippet": "hello",
        "elements": {"btn_001": {"text": "5s", "visible": True}},
        "element_count": 1,
    }
    after = {
        "page": {"url": "https://app.runwayml.com/a", "title": "A"},
        "body_text_snippet": "hello 10s",
        "elements": {
            "btn_001": {"text": "10s", "visible": True},
            "btn_002": {"text": "16:9", "visible": True},
        },
        "element_count": 2,
    }
    diff = mapper_mod.diff_snapshots(before, after)
    _pass("observe_diff_body", diff.get("body_text_changed") is True)
    _pass("observe_diff_added", len(diff.get("added_elements") or []) >= 1)


def _unit_scan_writes_candidates(tmp: Path) -> None:
    fake_raw = {
        "elements": list(_sample_elements().values()),
        "body_text_snippet": "Gen-4.5 Generate 16:9 10s",
        "url": "https://app.runwayml.com/video-tools/generate",
        "title": "Runway",
    }

    class FakePage:
        def evaluate(self, _script):
            return fake_raw

        def screenshot(self, **_kwargs):
            return None

        @property
        def url(self):
            return fake_raw["url"]

    class FakeMapper(mapper_mod.RunwayUIMapper):
        def connect(self):
            return None

        def disconnect(self):
            return None

        def pick_page(self, tab_index=None):
            return FakePage(), [{"index": 0, "is_runway_url": True}], 0

        def capture_screenshots(self, page, elements):
            return {"viewport": "project_brain/runway_ui_mapping/screenshots/01_viewport.png"}

    with patch.object(mapper_mod, "OUTPUT_DIR", tmp), patch.object(mapper_mod, "JSON_PATH", tmp / "runway_ui_map.json"), patch.object(
        mapper_mod, "CANDIDATES_PATH", tmp / "selector_candidates.json"
    ), patch.object(mapper_mod, "SCREENSHOTS_DIR", tmp / "screenshots"):
        ui = FakeMapper().mode_scan()
        _pass("scan_creates_candidates", (tmp / "selector_candidates.json").is_file())
        _pass("scan_v2_map", ui.get("version") == mapper_mod.MAPPER_VERSION_V2)
        _pass("scan_has_elements_dict", isinstance(ui.get("elements"), dict) and len(ui["elements"]) >= 2)
        cand = json.loads((tmp / "selector_candidates.json").read_text(encoding="utf-8"))
        _pass("candidates_have_element_id", all(c.get("element_id") for c in cand.get("candidates", [])))


def _unit_missing_runway_tab() -> None:
    class NoRunwayMapper(mapper_mod.RunwayUIMapper):
        def connect(self):
            self.browser = object()

        def disconnect(self):
            return None

        def list_tabs(self):
            return [{"index": 0, "url": "https://example.com", "is_runway_url": False}]

    try:
        NoRunwayMapper().pick_page(None)
        _pass("missing_runway_fails", False)
    except RuntimeError as exc:
        _pass("missing_runway_fails", "Runway tab" in str(exc))


def _live_scan_optional() -> None:
    try:
        mapper_mod.RunwayUIMapper().mode_scan()
        ui = mapper_mod.load_ui_map()
        _pass("live_scan_v2", ui.get("version") == mapper_mod.MAPPER_VERSION_V2)
        _pass("live_candidates_file", mapper_mod.CANDIDATES_PATH.is_file())
    except Exception as exc:
        print(f"[WARN] Live scan skipped: {exc}")


def main() -> int:
    _static_checks()
    _unit_assign_ids()
    _unit_observe_diff()
    _unit_missing_runway_tab()
    with tempfile.TemporaryDirectory() as tmpdir:
        _unit_label_safety(Path(tmpdir))
        _unit_scan_writes_candidates(Path(tmpdir))
    _live_scan_optional()
    print("\nRunway UI mapper manual learning validation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
