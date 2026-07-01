"""Validate KLING-CURRENT-MODE-DETECTION — skip model picker when Kling 3.0 Pro already active."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_locator import (  # noqa: E402
    LocatedControl,
    detect_kling_3_pro_current_model,
    resolve_kling_3_pro_provider,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_locator(*, count: int = 1, visible: bool = True, text: str = "") -> MagicMock:
    loc = MagicMock()
    loc.count.return_value = count
    loc.is_visible.return_value = visible
    loc.inner_text.return_value = text
    loc.text_content.return_value = text
    loc.first = loc
    return loc


def test_case_a_kling_already_selected_skips_picker() -> None:
    page = MagicMock()
    page.get_by_role.return_value.first = _mock_locator(text="Generate")
    page.locator.return_value.first = _mock_locator(text="Describe your shot")
    kling_btn = _mock_locator(text="Kling 3.0 Pro")
    page.get_by_text.return_value.first = kling_btn

    with patch(
        "content_brain.execution.kling_multishot_locator.try_locate_kling_3_pro_active",
        return_value=LocatedControl(label="provider_kling_3_pro", strategy="text_kling_3_pro", locator=kling_btn),
    ), patch("content_brain.execution.kling_multishot_locator.locate_control") as mock_locate:
        detection = detect_kling_3_pro_current_model(page)
        provider, model_detection = resolve_kling_3_pro_provider(page, {})

    _pass("case_a_model_already_selected", detection["model_already_selected"] is True)
    _pass("case_a_detected_text", "Kling" in detection["detected_text"])
    _pass("case_a_skip_locate_control", mock_locate.call_count == 0)
    _pass("case_a_strategy_prefix", provider.strategy.startswith("model_already_selected"))
    _pass("case_a_resolution_flag", model_detection["model_already_selected"] is True)


def test_case_b_not_in_kling_opens_picker() -> None:
    page = MagicMock()
    picker_btn = _mock_locator(text="Video models")
    located = LocatedControl(label="provider_kling_3_pro", strategy="role_button_video_models", locator=picker_btn)

    with patch(
        "content_brain.execution.kling_multishot_locator.detect_kling_3_pro_current_model",
        return_value={
            "model_already_selected": False,
            "detected_text": "",
            "detection_method": "",
            "generate_visible": True,
            "prompt_editor_ready": True,
        },
    ), patch(
        "content_brain.execution.kling_multishot_locator.locate_control",
        return_value=located,
    ) as mock_locate:
        provider, model_detection = resolve_kling_3_pro_provider(page, {"label": "provider_kling_3_pro"})

    _pass("case_b_not_already_selected", model_detection["model_already_selected"] is False)
    _pass("case_b_locate_control_called", mock_locate.call_count == 1)
    _pass("case_b_picker_strategy", provider.strategy == "role_button_video_models")


def test_case_c_picker_unavailable_but_kling_visible_passes() -> None:
    page = MagicMock()

    def _role_side_effect(role: str, **kwargs: object) -> MagicMock:
        loc = _mock_locator(visible=True, text="Generate" if role == "button" else "")
        if role == "button":
            loc.inner_text.return_value = "Generate"
        return loc

    def _locator_side_effect(selector: str) -> MagicMock:
        if selector == "body":
            loc = _mock_locator(visible=True, text="")
            loc.inner_text.return_value = "Kling 3.0 Pro\nDescribe your shot\n15s\nGenerate"
            return loc
        if '[contenteditable="true"]' in selector:
            return _mock_locator(visible=True, text="Describe your shot")
        return _mock_locator(count=0, visible=False)

    page.get_by_role.side_effect = _role_side_effect
    page.locator.side_effect = _locator_side_effect
    text_probe = _mock_locator(text="Kling 3.0 Pro")
    page.get_by_text.return_value.first = text_probe

    with patch(
        "content_brain.execution.kling_multishot_locator.try_locate_kling_3_pro_active",
        return_value=None,
    ), patch("content_brain.execution.kling_multishot_locator.locate_control") as mock_locate:
        detection = detect_kling_3_pro_current_model(page)
        provider, model_detection = resolve_kling_3_pro_provider(page, {})

    _pass("case_c_model_already_selected", detection["model_already_selected"] is True)
    _pass("case_c_body_detection", detection["detection_method"] == "body_text_generate_prompt_ready")
    _pass("case_c_skip_picker", mock_locate.call_count == 0)
    _pass("case_c_text_probe_strategy", provider.strategy == "model_already_selected:text_probe")
    _pass("case_c_resolution_pass", model_detection["model_already_selected"] is True)


def test_frame_engine_uses_resolve_helper() -> None:
    src = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    _pass("frame_engine_resolve_helper", "resolve_kling_3_pro_provider" in src)
    _pass("frame_engine_model_flag", "model_already_selected" in src)
    block = src.split("resolve_kling_3_pro_provider", 1)[1].split("_record_step(result, \"02\"", 1)[0]
    _pass("frame_engine_skip_click_when_selected", "if checklist.model_already_selected" in block)


def test_multishot_engine_uses_resolve_helper() -> None:
    src = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    _pass("multishot_engine_resolve_helper", "resolve_kling_3_pro_provider" in src)
    block = src.split("resolve_kling_3_pro_provider", 1)[1].split("step_pass(\"01\"", 1)[0]
    _pass("multishot_engine_skip_click_when_selected", "if checklist.model_already_selected" in block)


def main() -> None:
    print("KLING current model detection validation")
    test_case_a_kling_already_selected_skips_picker()
    test_case_b_not_in_kling_opens_picker()
    test_case_c_picker_unavailable_but_kling_visible_passes()
    test_frame_engine_uses_resolve_helper()
    test_multishot_engine_uses_resolve_helper()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
