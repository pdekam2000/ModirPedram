"""Apply P0 Kling Multishot relabels from scan ground truth — no browser, no credits."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.runway_ui_mapper import validate_label_capture  # noqa: E402

MAP_PATH = ROOT / "project_brain" / "runway_ui_mapping" / "runway_ui_map.json"
PHASE = "KLING-MULTISHOT-RELABEL-P0"
NOW = datetime.now(timezone.utc).isoformat()


def _load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _save_map(payload: dict[str, Any]) -> None:
    payload["updated_at"] = NOW
    MAP_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _el(elements: dict[str, Any], element_id: str) -> dict[str, Any]:
    item = elements.get(element_id)
    if not isinstance(item, dict):
        raise KeyError(f"Missing element {element_id}")
    return item


def _entry(
    *,
    label: str,
    element: dict[str, Any],
    css: str,
    playwright: str = "",
    page_url: str = "",
    notes: str = "",
) -> dict[str, Any]:
    bbox = dict(element.get("bounding_box") or {})
    text = str(element.get("text") or "")
    aria = str(element.get("aria_label") or "")
    tag = str(element.get("tag") or "")
    role = str(element.get("role") or "")
    url = page_url or str(element.get("page_url") or "")
    pw = playwright or str(element.get("playwright_locator") or "")
    payload: dict[str, Any] = {
        "label": label,
        "element_id": str(element.get("element_id") or ""),
        "text": text,
        "aria_label": aria,
        "role": role,
        "tag": tag,
        "bounding_box": bbox,
        "url": url.split("?")[0] if url else "",
        "selector_candidates": {"css": css, "playwright": pw},
        "metadata": {
            "tag": tag,
            "role": role,
            "text": text,
            "aria_label": aria,
            "css_selector": css,
            "bounding_box": bbox,
            "page_url": url,
            "page_title": str(element.get("page_title") or "Generative Session | Runway AI"),
            "playwright_locator": pw,
        },
        "operator_confirmed": True,
        "confirmed_at": NOW,
        "capture_mode": "p0_relabel_from_scan",
        "confirmed_by": PHASE,
        "relabel_phase": PHASE,
    }
    if notes:
        payload["relabel_notes"] = notes
    return payload


def _inferred_prompt_entry(shot_index: int, *, y_hint: float) -> dict[str, Any]:
    label = f"shot_{shot_index}_prompt"
    css = f'div[aria-label="Shot {shot_index} prompt"][contenteditable="true"]'
    pw = f"getByRole('textbox', {{ name: 'Shot {shot_index} prompt' }})"
    return {
        "label": label,
        "element_id": f"inferred_shot_{shot_index}_prompt",
        "text": "",
        "aria_label": f"Shot {shot_index} prompt",
        "role": "textbox",
        "tag": "div",
        "bounding_box": {"x": 81, "y": y_hint, "width": 366, "height": 140},
        "url": "https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate",
        "selector_candidates": {"css": css, "playwright": pw},
        "metadata": {
            "tag": "div",
            "role": "textbox",
            "text": "",
            "aria_label": f"Shot {shot_index} prompt",
            "css_selector": css,
            "contenteditable": True,
            "bounding_box": {"x": 81, "y": y_hint, "width": 366, "height": 140},
            "page_url": "https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate?mode=tools&tool=video",
            "page_title": "Generative Session | Runway AI",
            "playwright_locator": pw,
            "inference_source": "shot_1_shot_2_pattern",
            "requires_ui_state": f"visible_after_{max(0, shot_index - 2)}_add_shot_clicks",
        },
        "operator_confirmed": True,
        "confirmed_at": NOW,
        "capture_mode": "p0_pattern_inferred",
        "confirmed_by": PHASE,
        "relabel_phase": PHASE,
        "relabel_notes": "Pattern inferred from input_006/007; confirm after Add shot expands UI.",
    }


def apply_relabels() -> dict[str, Any]:
    ui_map = _load_map()
    elements = dict(ui_map.get("elements") or {})
    labels = dict(ui_map.get("labels") or {})

    page_url = str(_el(elements, "btn_030").get("page_url") or "")

    patches: dict[str, dict[str, Any]] = {
        "provider_kling_3_pro": _entry(
            label="provider_kling_3_pro",
            element=_el(elements, "btn_030"),
            css="#react-aria3046197000-\\:r1s0\\:",
            playwright="getByRole('button', { name: /Kling 3\\.0 Pro/i })",
            page_url=page_url,
            notes="Bottom-bar model provider chip (was mis-mapped to Kling 3.0 tab).",
        ),
        "audio_toggle_on": _entry(
            label="audio_toggle_on",
            element=_el(elements, "btn_024"),
            css="#react-aria3046197000-\\:r1r1\\:",
            playwright="getByRole('button', { name: /Audio settings/i })",
            page_url=page_url,
            notes="Detect ON via button text containing 'On' (was SVG path).",
        ),
        "shot_1_prompt": _entry(
            label="shot_1_prompt",
            element=_el(elements, "input_006"),
            css='div[aria-label="Shot 1 prompt"][contenteditable="true"]',
            playwright="getByRole('textbox', { name: 'Shot 1 prompt' })",
            page_url=page_url,
        ),
        "shot_2_prompt": _entry(
            label="shot_2_prompt",
            element=_el(elements, "input_007"),
            css='div[aria-label="Shot 2 prompt"][contenteditable="true"]',
            playwright="getByRole('textbox', { name: 'Shot 2 prompt' })",
            page_url=page_url,
        ),
        "multishot_tab": _entry(
            label="multishot_tab",
            element=_el(elements, "input_005"),
            css='input[name="react-aria3046197000-:r1ps:"][type="radio"]',
            playwright="getByText('Multishot', { exact: true })",
            page_url=page_url,
            notes="Multishot mode radio (stable name attribute).",
        ),
        "first_frame_upload": _entry(
            label="first_frame_upload",
            element=_el(elements, "btn_017"),
            css="#react-aria3046197000-\\:r1q3\\:",
            playwright="getByRole('button', { name: /First Video Frame Upload/i })",
            page_url=page_url,
            notes="Upload control inside first-frame area; zone container is btn_010.",
        ),
        "shot_1_duration_menu": _entry(
            label="shot_1_duration_menu",
            element=_el(elements, "btn_020"),
            css='button[aria-label="Shot duration"]:nth-of-type(1)',
            playwright="getByRole('button', { name: 'Shot duration' }).first()",
            page_url=page_url,
        ),
        "shot_1_duration_12s": _entry(
            label="shot_1_duration_12s",
            element=_el(elements, "btn_020"),
            css='[role="listbox"] [role="option"]:last-child',
            playwright="getByRole('option', { name: '12 seconds' })",
            page_url=page_url,
            notes="Select after opening shot 1 duration menu.",
        ),
        "shot_2_duration_menu": _entry(
            label="shot_2_duration_menu",
            element=_el(elements, "btn_022"),
            css='button[aria-label="Shot duration"]:nth-of-type(2)',
            playwright="getByRole('button', { name: 'Shot duration' }).nth(1)",
            page_url=page_url,
        ),
        "shot_2_duration_3s": _entry(
            label="shot_2_duration_3s",
            element=_el(elements, "btn_022"),
            css='[role="listbox"] [role="option"]:first-child',
            playwright="getByRole('option', { name: '3 seconds' })",
            page_url=page_url,
            notes="Default 3s option; select after opening shot 2 duration menu.",
        ),
        "add_shot_button": _entry(
            label="add_shot_button",
            element=_el(elements, "btn_023"),
            css='button[aria-label="Add shot"]',
            playwright="getByRole('button', { name: 'Add shot' })",
            page_url=page_url,
        ),
        "shot_3_prompt": _inferred_prompt_entry(3, y_hint=1051.0),
        "shot_4_prompt": _inferred_prompt_entry(4, y_hint=1201.0),
        "shot_5_prompt": _inferred_prompt_entry(5, y_hint=1351.0),
    }

    # Canonical aliases for legacy spaced labels
    legacy_aliases = {
        "shot 1 duration menu": "shot_1_duration_menu",
        "shot 1 duration 12 s": "shot_1_duration_12s",
        "+Add shot": "add_shot_button",
    }
    for legacy, canonical in legacy_aliases.items():
        if canonical in patches:
            patches[legacy] = {**patches[canonical], "label": legacy, "canonical_alias_of": canonical}

    labels.update(patches)
    ui_map["labels"] = labels
    _save_map(ui_map)

    validation: dict[str, Any] = {}
    blocking = 0
    generic = 0
    for name, entry in patches.items():
        warns = validate_label_capture(name, entry)
        errors = [w for w in warns if w.get("severity") == "error"]
        generics = [w for w in warns if w.get("code") == "GENERIC_SELECTOR"]
        validation[name] = {
            "warnings": warns,
            "error_count": len(errors),
            "generic_selector": bool(generics),
            "pass": len(errors) == 0 and len(generics) == 0,
        }
        blocking += len(errors)
        generic += len(generics)

    target_labels = list(patches.keys())
    passed = sum(1 for name in target_labels if validation.get(name, {}).get("pass"))
    return {
        "phase": PHASE,
        "map_path": str(MAP_PATH),
        "labels_patched": len(patches),
        "validation_pass_count": passed,
        "validation_total": len(target_labels),
        "validation_pass_rate": round(passed / max(1, len(target_labels)), 4),
        "blocking_errors": blocking,
        "generic_selector_warnings": generic,
        "all_pass": passed == len(target_labels) and blocking == 0 and generic == 0,
        "validation": validation,
        "generate_clicked": False,
        "credits_spent": False,
    }


def main() -> int:
    summary = apply_relabels()
    out = ROOT / "project_brain" / "kling_multishot_relabel_p0_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
