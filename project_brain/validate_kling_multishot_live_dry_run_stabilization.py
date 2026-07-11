"""Validate Kling Multishot live dry-run stabilization — locators, refresh, safety."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_multishot_config import (  # noqa: E402
    BLOCKED_CLICK_LABELS,
    REQUIRED_KLING_LABELS,
    SHOT_1_DURATION_SECONDS,
    SHOT_2_DURATION_SECONDS,
)
from content_brain.execution.kling_multishot_locator import (  # noqa: E402
    css_selector_is_unstable,
    locate_control,
)
from content_brain.execution.kling_multishot_map_loader import (  # noqa: E402
    load_kling_ui_map,
    resolve_kling_multishot_controls,
    verify_generate_approval_gate,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402
from project_brain.refresh_kling_multishot_selectors_from_cdp import (  # noqa: E402
    REFRESH_LABELS,
    STABLE_CSS_OVERRIDES,
)
from tools.kling_multishot_shadow_runner import (  # noqa: E402
    RUNNER_VERSION,
    SCREENSHOT_DIR,
    run_kling_multishot_shadow,
    validate_map_preconditions,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_locator_module_has_provider_stable_strategies() -> None:
    src = (ROOT / "content_brain" / "execution" / "kling_multishot_locator.py").read_text(encoding="utf-8")
    _pass("locator_module_exists", src.strip() != "")
    _pass("provider_role_button_strategy", "role_button_kling_3_pro" in src)
    _pass("provider_text_strategy", 'button:has-text("Kling 3.0 Pro")' in src)
    _pass("react_aria_unstable_detection", "css_selector_is_unstable" in src)


def test_refresh_module_stable_overrides() -> None:
    _pass("refresh_labels_include_provider", "provider_kling_3_pro" in REFRESH_LABELS)
    _pass("stable_override_provider", "provider_kling_3_pro" in STABLE_CSS_OVERRIDES)
    override = STABLE_CSS_OVERRIDES["provider_kling_3_pro"]
    _pass("provider_override_not_react_id", not css_selector_is_unstable(override), override)


def test_ui_map_loads_and_required_labels() -> None:
    snapshot = resolve_kling_multishot_controls(map_path=DEFAULT_MAP_PATH)
    _pass("ui_map_resolves", snapshot.ok, f"missing={snapshot.missing}")
    for label in REQUIRED_KLING_LABELS:
        _pass(f"label_{label}", label in snapshot.controls)


def test_generate_requires_approval() -> None:
    ui_map = load_kling_ui_map(map_path=DEFAULT_MAP_PATH)
    ok, reason = verify_generate_approval_gate(ui_map)
    _pass("generate_requires_approval", ok, reason)


def test_runner_v2_uses_locator_module() -> None:
    src = (ROOT / "tools" / "kling_multishot_shadow_runner.py").read_text(encoding="utf-8")
    _pass("runner_version_v2", RUNNER_VERSION.endswith("_v2"))
    _pass("runner_imports_locator", "kling_multishot_locator" in src)
    _pass("runner_uses_locate_control", "locate_control" in src)
    _pass("runner_screenshot_dir", "kling_multishot_live_dry_run" in src)
    _pass("runner_no_raw_css_only_provider", 'css("provider_kling_3_pro")' not in src)


def test_runner_dry_run_guards() -> None:
    src = (ROOT / "tools" / "kling_multishot_shadow_runner.py").read_text(encoding="utf-8")
    _pass("dry_run_default_true", "dry_run: bool = True" in src)
    _pass("blocked_generate", "generate_button" in BLOCKED_CLICK_LABELS)
    _pass("generate_not_clicked_blocked_step", '"blocked"' in src and "not clicked" in src.lower())


def test_map_only_run_passes() -> None:
    result = run_kling_multishot_shadow(
        shot_1_prompt="Main action twelve seconds.",
        shot_2_prompt="Bridge transition three seconds.",
        dry_run=True,
        connect_browser=False,
        map_path=DEFAULT_MAP_PATH,
    )
    _pass("map_only_ok", result.ok)
    _pass("map_only_generate_not_clicked", result.generate_clicked is False)
    _pass("map_only_no_credits", result.credits_spent is False)


def test_shot_durations_config() -> None:
    result = run_kling_multishot_shadow(
        shot_1_prompt="Shot one",
        shot_2_prompt="Shot two",
        dry_run=True,
        connect_browser=False,
        map_path=DEFAULT_MAP_PATH,
    )
    _pass("shot_1_12s", result.shot_1_duration_seconds == SHOT_1_DURATION_SECONDS == 12)
    _pass("shot_2_3s", result.shot_2_duration_seconds == SHOT_2_DURATION_SECONDS == 3)


def test_runner_never_clicks_generate_mock_cdp() -> None:
    pre, _, _ = validate_map_preconditions(map_path=DEFAULT_MAP_PATH)
    _pass("preconditions_ok", pre.ok)

    mock_page = MagicMock()
    mock_page.url = "https://app.runwayml.com/video-tools/generate?mode=tools&tool=video"
    mock_loc = MagicMock()
    mock_loc.count.return_value = 1
    mock_loc.inner_text.return_value = "12s"
    mock_loc.text_content.return_value = "12s"
    mock_page.locator.return_value.first = mock_loc

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]

    mock_playwright_instance = MagicMock()
    mock_playwright_instance.chromium.connect_over_cdp.return_value = mock_browser
    mock_pw = MagicMock()
    mock_pw.start.return_value = mock_playwright_instance

    located = MagicMock()
    located.strategy = "role_button_kling_3_pro"
    located.locator = mock_loc

    import tools.kling_multishot_shadow_runner as runner_mod

    with patch.object(runner_mod, "sync_playwright", mock_pw, create=True):
        with patch.object(runner_mod, "locate_control", return_value=located):
            with patch.object(runner_mod, "try_locate_control", return_value=located):
                with patch.object(runner_mod, "_capture_step_screenshot", return_value="mock.png"):
                    result = runner_mod.run_kling_multishot_shadow(
                        shot_1_prompt="Main action test prompt.",
                        shot_2_prompt="Bridge transition prompt.",
                        dry_run=True,
                        connect_browser=True,
                        map_path=DEFAULT_MAP_PATH,
                    )

    _pass("mock_generate_not_clicked", result.generate_clicked is False)
    _pass("mock_no_credits", result.credits_spent is False)


def test_live_dry_run_summary_if_present() -> None:
    summary_path = ROOT / "project_brain" / "kling_multishot_shadow_run_summary.json"
    if not summary_path.is_file():
        _pass("live_summary_optional_skip", True, "no live summary yet")
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    _pass("live_summary_dry_run_true", summary.get("dry_run") is True)
    _pass("live_summary_generate_not_clicked", summary.get("generate_clicked") is False)
    _pass("live_summary_no_credits", summary.get("credits_spent") is False)
    if summary.get("connect_browser"):
        _pass("live_summary_ok", summary.get("ok") is True, json.dumps(summary.get("errors", []), ensure_ascii=False))


def test_relabel_validation_still_passes() -> None:
    summary_path = ROOT / "project_brain" / "kling_multishot_relabel_p0_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    _pass("relabel_all_pass", summary.get("all_pass") is True)


def main() -> int:
    print("validate_kling_multishot_live_dry_run_stabilization")
    test_locator_module_has_provider_stable_strategies()
    test_refresh_module_stable_overrides()
    test_ui_map_loads_and_required_labels()
    test_generate_requires_approval()
    test_runner_v2_uses_locator_module()
    test_runner_dry_run_guards()
    test_map_only_run_passes()
    test_shot_durations_config()
    test_runner_never_clicks_generate_mock_cdp()
    test_live_dry_run_summary_if_present()
    test_relabel_validation_still_passes()
    print("All Kling Multishot live dry-run stabilization checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
