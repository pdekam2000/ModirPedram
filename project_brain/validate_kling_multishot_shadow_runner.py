"""Validate Kling Multishot shadow runner — map, safety, 2-shot continuity."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import (  # noqa: E402
    MULTISHOT_STRATEGY,
    OPTIONAL_KLING_LABELS,
    REQUIRED_KLING_LABELS,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_multishot_map_loader import (  # noqa: E402
    load_kling_ui_map,
    resolve_kling_multishot_controls,
    verify_generate_approval_gate,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402
from tools.kling_multishot_shadow_runner import (  # noqa: E402
    BLOCKED_CLICK_LABELS,
    run_kling_multishot_shadow,
    validate_map_preconditions,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_ui_map_loads() -> None:
    ui_map = load_kling_ui_map(map_path=DEFAULT_MAP_PATH)
    _pass("ui_map_loads", isinstance(ui_map, dict) and bool(ui_map.get("labels")))


def test_required_labels_exist() -> None:
    snapshot = resolve_kling_multishot_controls(map_path=DEFAULT_MAP_PATH)
    _pass("required_labels_resolved", snapshot.ok, f"missing={snapshot.missing} invalid={snapshot.invalid}")
    for label in REQUIRED_KLING_LABELS:
        _pass(f"label_{label}", label in snapshot.controls)


def test_optional_labels_not_required() -> None:
    snapshot = resolve_kling_multishot_controls(map_path=DEFAULT_MAP_PATH)
    _pass("snapshot_ok_without_optional", snapshot.ok)
    for label in OPTIONAL_KLING_LABELS:
        if label not in snapshot.controls:
            _pass(f"optional_{label}_absent_ok", True)
        else:
            _pass(f"optional_{label}_present_ok", True, "present but not required")


def test_generate_requires_approval() -> None:
    ui_map = load_kling_ui_map(map_path=DEFAULT_MAP_PATH)
    ok, reason = verify_generate_approval_gate(ui_map)
    _pass("generate_requires_approval", ok, reason)
    requires = list((ui_map.get("safety") or {}).get("requires_approval") or [])
    _pass("generate_in_requires_approval", "generate_button" in requires)


def test_runner_dry_run_guard_source() -> None:
    src = (ROOT / "tools" / "kling_multishot_shadow_runner.py").read_text(encoding="utf-8")
    _pass("dry_run_default_true", "dry_run: bool = True" in src)
    _pass("blocked_generate_labels", "generate_button" in BLOCKED_CLICK_LABELS)
    _pass("never_click_generate_comment", "not clicked" in src.lower() or "NOT clicked" in src)
    _pass("only_dry_run_supported", "Only dry_run=True is supported" in src)


def test_runner_never_clicks_generate_in_dry_run() -> None:
    pre, ui_map, snapshot = validate_map_preconditions(map_path=DEFAULT_MAP_PATH)
    _pass("preconditions_for_mock", pre.ok)

    mock_page = MagicMock()
    mock_page.url = "https://app.runwayml.com/video-tools/generate?mode=tools&tool=video"
    mock_loc = MagicMock()
    mock_loc.count.return_value = 1
    mock_loc.inner_text.return_value = "· On"
    mock_loc.text_content.return_value = "· On"
    mock_page.locator.return_value.first = mock_loc

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]

    mock_playwright_instance = MagicMock()
    mock_playwright_instance.chromium.connect_over_cdp.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.start.return_value = mock_playwright_instance

    with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
        with patch("tools.kling_multishot_shadow_runner.sync_playwright", mock_pw, create=True):
            # Patch import inside function
            import importlib
            import tools.kling_multishot_shadow_runner as runner_mod

            with patch.object(runner_mod, "sync_playwright", mock_pw):
                result = runner_mod.run_kling_multishot_shadow(
                    shot_1_prompt="Main action test prompt for shot one.",
                    shot_2_prompt="Bridge transition prompt for shot two.",
                    dry_run=True,
                    connect_browser=True,
                    map_path=DEFAULT_MAP_PATH,
                )

    _pass("mock_run_generate_not_clicked", result.generate_clicked is False)
    _pass("mock_run_no_credits", result.credits_spent is False)
    _pass("mock_run_add_shot_not_used", result.add_shot_used is False)


def test_two_shot_continuity_config() -> None:
    _pass("strategy_two_shot", MULTISHOT_STRATEGY == "two_shot_continuity")
    result = run_kling_multishot_shadow(
        shot_1_prompt="Setup action",
        shot_2_prompt="Bridge hold",
        dry_run=True,
        connect_browser=False,
        map_path=DEFAULT_MAP_PATH,
    )
    _pass("map_only_run_ok", result.ok)
    _pass("multishot_strategy", result.multishot_strategy == "two_shot_continuity")


def test_shot_durations() -> None:
    result = run_kling_multishot_shadow(
        shot_1_prompt="Shot one",
        shot_2_prompt="Shot two",
        dry_run=True,
        connect_browser=False,
        map_path=DEFAULT_MAP_PATH,
    )
    _pass("shot_1_12s", result.shot_1_duration_seconds == SHOT_1_DURATION_SECONDS == 12)
    _pass("shot_2_3s", result.shot_2_duration_seconds == SHOT_2_DURATION_SECONDS == 3)


def test_relabel_validation_still_passes() -> None:
    summary_path = ROOT / "project_brain" / "kling_multishot_relabel_p0_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        _pass("relabel_summary_all_pass", summary.get("all_pass") is True)
    else:
        import project_brain.apply_kling_multishot_relabel_p0 as relabel

        summary = relabel.apply_relabels()
        _pass("relabel_validation", summary.get("all_pass") is True)


def main() -> int:
    print("validate_kling_multishot_shadow_runner")
    test_ui_map_loads()
    test_required_labels_exist()
    test_optional_labels_not_required()
    test_generate_requires_approval()
    test_runner_dry_run_guard_source()
    test_runner_never_clicks_generate_in_dry_run()
    test_two_shot_continuity_config()
    test_shot_durations()
    test_relabel_validation_still_passes()
    print("All Kling Multishot shadow runner checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
