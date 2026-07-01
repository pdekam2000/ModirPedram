"""Validate Kling Frame-to-Video live dry-run P2 — map, guards, CDP checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_to_video_config import (  # noqa: E402
    BLOCKED_KLING_FRAME_CLICK_LABELS,
    BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS,
    KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS,
    KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS,
    KLING_FRAME_LIVE_DRY_RUN_P2_LABELS,
    KLING_FRAME_LIVE_DRY_RUN_P2_VERSION,
    KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
)
from content_brain.execution.kling_frame_to_video_live_dry_run import (  # noqa: E402
    DEFAULT_CDP_URL,
    run_kling_frame_live_dry_run_p2,
)
from content_brain.execution.kling_frame_to_video_map_loader import (  # noqa: E402
    resolve_kling_frame_to_video_controls,
    verify_generate_approval_gate,
    load_kling_frame_ui_map,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_p2_config() -> None:
    _pass("p2_version", KLING_FRAME_LIVE_DRY_RUN_P2_VERSION.endswith("_p2_v2"))
    _pass("p2_eight_checks", len(KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS) == 8)
    _pass("p2_three_duration_checks", len(KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS) == 3)
    for check_id in KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS:
        _pass(f"p2_check_{check_id}", check_id in KLING_FRAME_LIVE_DRY_RUN_P2_LABELS)


def test_blocked_actions() -> None:
    _pass("blocked_generate_click", "generate_click" in BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS)
    _pass("blocked_download", "download" in BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS)
    _pass("blocked_credit_spend", "credit_spend" in BLOCKED_KLING_FRAME_LIVE_DRY_RUN_ACTIONS)
    _pass("generate_in_click_blocklist", "generate_button" in BLOCKED_KLING_FRAME_CLICK_LABELS)


def test_map_supports_p2_labels() -> None:
    snapshot = resolve_kling_frame_to_video_controls(map_path=DEFAULT_MAP_PATH)
    _pass("map_snapshot_ok", snapshot.ok)
    for check_id, label in KLING_FRAME_LIVE_DRY_RUN_P2_LABELS.items():
        _pass(f"map_label_{check_id}", label in snapshot.controls, label)


def test_generate_requires_approval() -> None:
    ui_map = load_kling_frame_ui_map(map_path=DEFAULT_MAP_PATH)
    ok, reason = verify_generate_approval_gate(ui_map)
    _pass("generate_requires_approval", ok, reason)


def test_engine_dry_run_guards() -> None:
    src = (ROOT / "content_brain" / "execution" / "kling_frame_to_video_live_dry_run.py").read_text(
        encoding="utf-8"
    )
    _pass("engine_no_generate_click", "generate_clicked=False" in src)
    _pass("engine_no_download", "download_clicked=False" in src)
    _pass("engine_no_credits", "credits_spent=False" in src)
    _pass("engine_dry_run_only", "dry_run=True only" in src)
    _pass("engine_dismiss_popover", "_dismiss_duration_popover" in src)
    _pass("engine_duration_stable", "duration_stable_after_dismiss" in src)
    _pass("engine_audio_after_duration", "_run_duration_sequence" in src)


def test_map_only_run() -> None:
    result = run_kling_frame_live_dry_run_p2(dry_run=True, connect_browser=False, map_path=DEFAULT_MAP_PATH)
    _pass("map_only_ok", result.ok)
    _pass("map_only_no_generate", result.generate_clicked is False)
    _pass("map_only_no_download", result.download_clicked is False)
    _pass("map_only_no_credits", result.credits_spent is False)


def test_live_cdp(*, cdp_url: str) -> None:
    result = run_kling_frame_live_dry_run_p2(
        cdp_url=cdp_url,
        map_path=DEFAULT_MAP_PATH,
        dry_run=True,
        connect_browser=True,
    )
    summary_path = ROOT / "project_brain" / "kling_frame_live_dry_run_p2_summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

    _pass("live_connect", result.connect_browser)
    _pass("live_no_generate", result.generate_clicked is False)
    _pass("live_no_download", result.download_clicked is False)
    _pass("live_no_credits", result.credits_spent is False)
    _pass("live_all_checks", result.ok, str(result.checks))
    for check_id in KLING_FRAME_LIVE_DRY_RUN_P2_CHECKS:
        _pass(f"live_{check_id}", result.checks.get(check_id) is True, str(result.locator_strategies.get(check_id, "")))
    for check_id in KLING_FRAME_LIVE_DRY_RUN_P2_DURATION_CHECKS:
        _pass(f"live_duration_sub_{check_id}", result.checks.get(check_id) is True)
    if result.duration_seconds_after_dismiss is not None:
        _pass(
            "live_duration_stable_15s",
            result.duration_seconds_after_dismiss == KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
            result.duration_after_dismiss,
        )
    _pass("live_popover_closed", result.checks.get("duration_popover_closed") is True, str(result.popover_open_after_dismiss))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Kling Frame live dry-run P2")
    parser.add_argument("--live", action="store_true", help="Run live CDP validation")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    args = parser.parse_args()

    print("validate_kling_frame_live_dry_run_p2")
    test_p2_config()
    test_blocked_actions()
    test_map_supports_p2_labels()
    test_generate_requires_approval()
    test_engine_dry_run_guards()
    test_map_only_run()

    if args.live:
        print("\n--- live CDP ---")
        test_live_cdp(cdp_url=args.cdp_url)
    else:
        print("\n(static — pass --live for CDP)")

    print("All Kling Frame live dry-run P2 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
