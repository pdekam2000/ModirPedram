"""Validate RUNWAY auto-generate — page activation before Generate, no stuck click."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_focus_dependency_probe import (  # noqa: E402
    PROBE_VERSION,
    execute_generate_click_with_focus_probe,
    is_page_ready_for_generate_click,
    prepare_page_for_auto_generate_click,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_probe_version_bumped() -> None:
    _pass("probe_v2", PROBE_VERSION == "runway_focus_dependency_probe_v2")


def test_default_auto_activate() -> None:
    src = (ROOT / "content_brain/execution/runway_focus_dependency_probe.py").read_text(encoding="utf-8")
    _pass("activate_default_true", "activate_before_click: bool = True" in src)


def test_live_engines_use_default_probe() -> None:
    frame = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    multi = (ROOT / "content_brain/execution/kling_multishot_live_engine.py").read_text(encoding="utf-8")
    _pass("frame_no_activate_false", "activate_before_click=False" not in frame)
    _pass("multishot_no_activate_false", "activate_before_click=False" not in multi)
    _pass("frame_ensure_page_activates", "activate_page_for_interaction" in frame)


def test_prepare_makes_page_ready() -> None:
    page = MagicMock()
    ready = {
        "visibility_state": "visible",
        "document_hidden": False,
        "generate_button": {"visible": True, "disabled": False},
    }
    with patch(
        "content_brain.execution.runway_focus_dependency_probe.activate_page_for_interaction",
        return_value=True,
    ), patch(
        "content_brain.execution.runway_focus_dependency_probe.wait_for_page_ready_for_generate",
        return_value=ready,
    ):
        snap = prepare_page_for_auto_generate_click(page)
    _pass("prepare_returns_ready", is_page_ready_for_generate_click(snap))


def test_auto_generate_no_stuck_click_note() -> None:
    page = MagicMock()
    page.url = "https://app.runwayml.com/ai-tools/generate?mode=tools"
    ready = {
        "visibility_state": "visible",
        "document_hidden": False,
        "has_focus": True,
        "overlay_count": 0,
        "generate_button": {"label": "Generate", "disabled": False, "visible": True, "pointerEvents": "auto"},
    }
    page.evaluate.side_effect = [
        ready,
        True,
        ready,
        True,
        {
            **ready,
            "generate_button": {"label": "Generate", "disabled": True, "visible": True, "pointerEvents": "auto"},
        },
        True,
    ]
    locator = MagicMock()
    with patch(
        "content_brain.execution.runway_focus_dependency_probe.prepare_page_for_auto_generate_click",
        return_value=ready,
    ):
        probe = execute_generate_click_with_focus_probe(page, locator)
    _pass("page_activated", probe.page_activated is True)
    _pass("no_stuck_click_note", "auto_generate_no_stuck_click" in probe.notes)
    _pass("click_executed", locator.click.called)
    _pass("not_focus_blocked", probe.focus_likely_blocker is False)


def test_hidden_page_gets_prepared_before_click() -> None:
    page = MagicMock()
    hidden = {
        "visibility_state": "hidden",
        "document_hidden": True,
        "has_focus": False,
        "overlay_count": 0,
        "generate_button": {"label": "Generate", "disabled": False, "visible": True},
    }
    ready = {
        "visibility_state": "visible",
        "document_hidden": False,
        "has_focus": True,
        "overlay_count": 0,
        "generate_button": {"label": "Generate", "disabled": False, "visible": True, "pointerEvents": "auto"},
    }
    locator = MagicMock()
    with patch(
        "content_brain.execution.runway_focus_dependency_probe.prepare_page_for_auto_generate_click",
        return_value=ready,
    ) as prep:
        probe = execute_generate_click_with_focus_probe(page, locator, activate_before_click=True)
    prep.assert_called_once_with(page)
    _pass("prepare_called_for_hidden", probe.before.get("visibility_state") == "visible")


def test_is_page_ready_helper() -> None:
    _pass("ready_visible", is_page_ready_for_generate_click({"visibility_state": "visible", "document_hidden": False}))
    _pass("not_ready_hidden", not is_page_ready_for_generate_click({"visibility_state": "hidden", "document_hidden": True}))


def main() -> None:
    test_probe_version_bumped()
    test_default_auto_activate()
    test_live_engines_use_default_probe()
    test_prepare_makes_page_ready()
    test_auto_generate_no_stuck_click_note()
    test_hidden_page_gets_prepared_before_click()
    test_is_page_ready_helper()
    print("validate_runway_auto_generate_no_stuck_click: all checks passed")


if __name__ == "__main__":
    main()
