"""Validate RUNWAY-FOCUS-DEPENDENCY-FORENSIC probe helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_focus_dependency_probe import (  # noqa: E402
    PROBE_VERSION,
    _focus_blocker_heuristic,
    build_forensic_conclusion,
    execute_generate_click_with_focus_probe,
    snapshot_page_focus_state,
    static_code_forensic,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_static_code_shows_no_activation() -> None:
    static = static_code_forensic()
    _pass("no_bring_to_front", static.get("bring_to_front_used") is False)
    _pass("cdp_attach", static.get("connect_over_cdp") is True)
    _pass("generate_click_instrumented", static.get("generate_click_instrumented") is True)


def test_focus_blocker_heuristic() -> None:
    blocked, notes = _focus_blocker_heuristic(
        {"visibility_state": "hidden", "has_focus": False, "overlay_count": 0}
    )
    _pass("hidden_is_blocker", blocked)
    _pass("notes_present", bool(notes))
    clear, _ = _focus_blocker_heuristic(
        {"visibility_state": "visible", "has_focus": True, "overlay_count": 0}
    )
    _pass("visible_not_blocker", not clear)


def test_snapshot_reads_page_state() -> None:
    page = MagicMock()
    page.url = "https://app.runwayml.com/video-tools/teams/x/ai-tools/generate?mode=tools"
    page.evaluate.return_value = {
        "pageUrl": page.url,
        "visibilityState": "visible",
        "documentHidden": False,
        "hasFocus": True,
        "readyState": "complete",
        "overlayCount": 0,
        "overlays": [],
        "generateButton": {"label": "Generate", "disabled": False, "visible": True},
    }
    snap = snapshot_page_focus_state(page)
    _pass("visibility", snap.get("visibility_state") == "visible")
    _pass("has_focus", snap.get("has_focus") is True)


def test_generate_probe_logs_timestamps() -> None:
    page = MagicMock()
    page.url = "https://app.runwayml.com/ai-tools/generate"
    page.evaluate.side_effect = [
        {
            "pageUrl": page.url,
            "visibilityState": "hidden",
            "documentHidden": True,
            "hasFocus": False,
            "readyState": "complete",
            "overlayCount": 0,
            "overlays": [],
            "generateButton": {"label": "Generate", "disabled": False, "visible": True, "pointerEvents": "auto"},
        },
        False,
        {
            "pageUrl": page.url,
            "visibilityState": "visible",
            "documentHidden": False,
            "hasFocus": True,
            "readyState": "complete",
            "overlayCount": 0,
            "overlays": [],
            "generateButton": {"label": "Generate", "disabled": True, "visible": True, "pointerEvents": "auto"},
        },
        True,
    ]
    locator = MagicMock()
    probe = execute_generate_click_with_focus_probe(page, locator, activate_before_click=False)
    _pass("probe_version", probe.before.get("visibility_state") == "hidden")
    _pass("focus_blocker_flag", probe.focus_likely_blocker is True)
    _pass("queued_timestamp", bool(probe.queued_at))
    _pass("click_finished_timestamp", bool(probe.click_finished_at))
    _pass("locator_clicked", locator.click.called)


def test_forensic_conclusion() -> None:
    static = static_code_forensic()
    conclusion = build_forensic_conclusion(
        static=static,
        artifact_findings=[],
        live_snapshot={"visibility_state": "hidden", "has_focus": False},
    )
    _pass("focus_dependent_yes", conclusion.get("focus_dependent") == "yes")
    _pass("recommended_fix", "bring_to_front" in str(conclusion.get("recommended_fix")))


def test_probe_version() -> None:
    _pass("version", PROBE_VERSION == "runway_focus_dependency_probe_v2")


def main() -> None:
    test_static_code_shows_no_activation()
    test_focus_blocker_heuristic()
    test_snapshot_reads_page_state()
    test_generate_probe_logs_timestamps()
    test_forensic_conclusion()
    test_probe_version()
    print("validate_runway_focus_dependency_forensic: all checks passed")


if __name__ == "__main__":
    main()
