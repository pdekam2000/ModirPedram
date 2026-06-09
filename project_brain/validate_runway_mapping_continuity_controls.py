"""
Phase RUNWAY-BROWSER-CONTINUITY-B/C — continuity control mapping validator.

Read-only: loads runway_ui_map.json and checks required Gen-4.5 labels.
Completion rule: download_mp4_button OR use_frame_button (generation_status optional).
No browser, no clicks, no generation.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import runway_ui_mapper as mapper_mod

MAP_PATH = ROOT / "project_brain" / "runway_ui_mapping" / "runway_ui_map.json"


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    src = (ROOT / "tools" / "runway_ui_mapper.py").read_text(encoding="utf-8")
    _pass("continuity_checklist_flag", "--continuity-checklist" in src)
    _pass("validate_continuity_flag", "--validate-continuity" in src)
    _pass("normalize_continuity_flag", "--normalize-continuity" in src)
    _pass("hover_label_flag", "--hover-label" in src)
    _pass("validate_label_capture", "def validate_label_capture" in src)
    _pass("validate_continuity_mapping", "def validate_continuity_mapping" in src)
    _pass("completion_rule", "GENERATION_COMPLETE_RULE" in src)
    _pass("remove_image_required", "remove_image" in mapper_mod.CONTINUITY_CRITICAL_LABELS)
    _pass("generation_status_not_required", "generation_status" not in mapper_mod.CONTINUITY_CRITICAL_LABELS)
    _pass("download_mp4_in_semantic_labels", "download_mp4_button" in mapper_mod.VALID_SEMANTIC_LABELS)
    _pass("use_frame_in_semantic_labels", "use_frame_button" in mapper_mod.VALID_SEMANTIC_LABELS)
    _pass("remove_image_in_semantic_labels", "remove_image" in mapper_mod.VALID_SEMANTIC_LABELS)


def _unit_forbidden_body_warning() -> None:
    warnings = mapper_mod.validate_label_capture(
        "DOWNLOAD MP4",
        {
            "tag": "body",
            "text": "Apps Custom Agent",
            "selector_candidates": {"css": "body"},
            "url": "https://app.runwayml.com/video-tools/teams/x/ai-tools/generate?mode=tools&tool=video",
        },
    )
    codes = {w.get("code") for w in warnings}
    _pass("body_tag_warns", "FORBIDDEN_TAG" in codes)
    _pass("download_body_warns", "DOWNLOAD_NOT_BODY" in codes)


def _unit_use_frame_wrong_page_warning_only() -> None:
    warnings = mapper_mod.validate_label_capture(
        "USE FRAME",
        {
            "tag": "span",
            "text": "Use frame",
            "selector_candidates": {"css": "span"},
            "url": "https://app.runwayml.com/video-tools/teams/x/ai-tools/generate?mode=apps&sessionId=abc",
        },
    )
    codes = {w.get("code") for w in warnings}
    severities = {w.get("code"): w.get("severity") for w in warnings}
    _pass("use_frame_apps_warns", "USE_FRAME_WRONG_PAGE" in codes)
    _pass("use_frame_apps_not_error", severities.get("USE_FRAME_WRONG_PAGE") == "warning")


def _unit_completion_rule() -> None:
    rule = mapper_mod.continuity_completion_rule()
    _pass("completion_expression", "download_mp4_button" in rule["expression"])
    _pass("completion_or_use_frame", "use_frame_button" in rule["expression"])
    _pass("status_not_required", rule.get("generation_status_required") is False)


def _unit_normalization_suggestion() -> None:
    suggested = mapper_mod.suggest_normalized_label_name("aspect_ratio_menu 9: 16")
    _pass("normalize_9_16", suggested == "aspect_ratio_9_16", str(suggested))
    _pass("normalize_remove_image", mapper_mod.suggest_normalized_label_name("REMOVE IMAGE") == "remove_image")


def _unit_valid_minimal_map(tmp: Path) -> None:
    good_labels = {
        "prompt_input": {
            "tag": "div",
            "selector_candidates": {"css": "div[aria-label=\"Prompt\"]"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "gen45_model_button": {
            "tag": "div",
            "selector_candidates": {"css": "[id$='-tab-gen45']"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "try_it_now_button": {
            "tag": "button",
            "text": "Try it now",
            "selector_candidates": {"css": "button.try-it"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "generate_button": {
            "tag": "button",
            "text": "Generate",
            "selector_candidates": {"css": "#generate-btn"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "duration_menu": {
            "tag": "button",
            "text": "5s",
            "selector_candidates": {"css": "button[aria-label=\"Duration\"]"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "duration_10s": {
            "tag": "span",
            "text": "10 seconds",
            "selector_candidates": {"css": "[role=\"menuitem\"]:has-text(\"10\")"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "aspect_ratio_menu": {
            "tag": "button",
            "text": "16:9",
            "selector_candidates": {"css": "button[aria-label=\"Aspect ratio\"]"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "aspect_ratio_16_9": {
            "tag": "span",
            "text": "16:9",
            "selector_candidates": {"css": "[role=\"menuitem\"]:has-text(\"16:9\")"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "aspect_ratio_9_16": {
            "tag": "span",
            "text": "9:16",
            "selector_candidates": {"css": "[role=\"menuitem\"]:has-text(\"9:16\")"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video",
        },
        "download_mp4_button": {
            "tag": "button",
            "text": "Download",
            "aria_label": "Download",
            "selector_candidates": {"css": "button[aria-label=\"Download\"]"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video&sessionId=x",
        },
        "use_frame_button": {
            "tag": "span",
            "text": "Use frame",
            "selector_candidates": {"css": "span"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video&sessionId=x",
        },
        "remove_image": {
            "tag": "button",
            "text": "Remove",
            "aria_label": "Remove image",
            "selector_candidates": {"css": "button[aria-label=\"Remove image\"]"},
            "url": "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video&sessionId=x",
        },
    }
    ui_map = {"labels": good_labels, "version": "runway_ui_mapper_v2"}
    report = mapper_mod.validate_continuity_mapping(ui_map)
    _pass("minimal_map_ok", report["ok"] is True, f"missing={report.get('missing')}")
    _pass("completion_signals_ready", report["completion_signals_ready"] is True)


def validate_live_map() -> int:
    if not MAP_PATH.is_file():
        print(f"[validate_runway_mapping_continuity_controls] Missing map: {MAP_PATH}")
        return 1

    ui_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    report = mapper_mod.validate_continuity_mapping(ui_map)
    rule = mapper_mod.continuity_completion_rule()

    print("\n[validate_runway_mapping_continuity_controls] Live map report")
    print(f"  Path: {MAP_PATH}")
    print(f"  OK: {report['ok']}")
    print(f"  Completion rule: {rule['expression']}")
    print(f"  Completion signals ready: {report['completion_signals_ready']}")

    if report["present"]:
        print("\n  Present (canonical <- alias):")
        for canonical, alias in sorted(report["present"].items()):
            print(f"    {canonical} <- '{alias}'")

    if report["missing"]:
        print("\n  Missing required labels:")
        for name in report["missing"]:
            print(f"    - {name}")

    if report["invalid"]:
        print("\n  Invalid captures:")
        for item in report["invalid"]:
            print(f"    - {item['label']}: {item['reason']}")

    if report["warnings"]:
        print("\n  Warnings:")
        for item in report["warnings"]:
            print(f"    - {item['label']}: {item['message']}")

    if report.get("optional_present"):
        print("\n  Optional labels present:")
        for name, alias in sorted(report["optional_present"].items()):
            print(f"    {name} <- '{alias}'")

    if not report["ok"]:
        print("\n  Run: python tools/runway_ui_mapper.py --continuity-checklist")
        print("  Guide: project_brain/PHASE_RUNWAY_BROWSER_CONTINUITY_B_RELABELING_GUIDE.md")
        print("  Report: project_brain/RUNWAY_COMPLETION_DETECTION_REPORT.md")
        return 1

    print("\n  All continuity controls validated.")
    return 0


def main() -> int:
    print("[validate_runway_mapping_continuity_controls] Unit checks")
    _static_checks()
    _unit_forbidden_body_warning()
    _unit_use_frame_wrong_page_warning_only()
    _unit_completion_rule()
    _unit_normalization_suggestion()
    with tempfile.TemporaryDirectory() as tmpdir:
        _unit_valid_minimal_map(Path(tmpdir))

    print("\n[validate_runway_mapping_continuity_controls] Live map")
    return validate_live_map()


if __name__ == "__main__":
    raise SystemExit(main())
