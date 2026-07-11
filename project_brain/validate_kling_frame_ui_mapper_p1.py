"""Validate Kling Frame-to-Video UI mapper P1 — map, slider, dry-run safety."""

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
    KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
    REQUIRED_KLING_FRAME_LABELS,
)
from content_brain.execution.kling_frame_to_video_map_loader import (  # noqa: E402
    load_kling_frame_ui_map,
    resolve_kling_frame_to_video_controls,
    verify_generate_approval_gate,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH  # noqa: E402
from tools.kling_frame_to_video_shadow_runner import (  # noqa: E402
    SCREENSHOT_DIR,
    run_kling_frame_to_video_shadow,
)

SLIDER_LABELS = ("duration_slider_handle", "duration_slider_track", "duration_display_value")
REQUIRED_SCREENSHOTS = (
    "frame_mode_selected",
    "duration_before",
    "duration_after_15s",
    "audio_on",
    "generate_visible",
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_ui_map_loads() -> None:
    ui_map = load_kling_frame_ui_map(map_path=DEFAULT_MAP_PATH)
    _pass("ui_map_loads", isinstance(ui_map, dict) and bool(ui_map.get("labels")))


def test_all_required_labels_exist() -> None:
    snapshot = resolve_kling_frame_to_video_controls(map_path=DEFAULT_MAP_PATH)
    _pass("required_labels_resolved", snapshot.ok, f"missing={snapshot.missing} invalid={snapshot.invalid}")
    for label in REQUIRED_KLING_FRAME_LABELS:
        _pass(f"label_{label}", label in snapshot.controls)


def test_slider_labels_exist() -> None:
    labels = load_kling_frame_ui_map(map_path=DEFAULT_MAP_PATH).get("labels") or {}
    for label in SLIDER_LABELS:
        entry = labels.get(label)
        _pass(f"slider_map_{label}", isinstance(entry, dict), str(entry is None))
        if isinstance(entry, dict):
            _pass(
                f"slider_{label}_confirmed",
                entry.get("operator_confirmed") is True or entry.get("confirmed_by"),
            )


def test_slider_labels_resolvable_in_snapshot() -> None:
    snapshot = resolve_kling_frame_to_video_controls(map_path=DEFAULT_MAP_PATH)
    for label in SLIDER_LABELS:
        ctrl = snapshot.controls.get(label)
        _pass(f"slider_resolved_{label}", ctrl is not None and ctrl.valid, ctrl.invalid_reason if ctrl else "missing")


def test_prompt_and_upload_controls_resolvable() -> None:
    snapshot = resolve_kling_frame_to_video_controls(map_path=DEFAULT_MAP_PATH)
    for label in ("frame_prompt_box", "first_frame_upload", "end_frame_upload"):
        ctrl = snapshot.controls.get(label)
        _pass(f"control_{label}", ctrl is not None and ctrl.valid)


def test_generate_requires_approval() -> None:
    ui_map = load_kling_frame_ui_map(map_path=DEFAULT_MAP_PATH)
    ok, reason = verify_generate_approval_gate(ui_map)
    _pass("generate_requires_approval", ok, reason)
    requires = list((ui_map.get("safety") or {}).get("requires_approval") or [])
    _pass("generate_in_requires_approval", "generate_button" in requires)


def test_runner_dry_run_guard_source() -> None:
    src = (ROOT / "tools" / "kling_frame_to_video_shadow_runner.py").read_text(encoding="utf-8")
    _pass("dry_run_default_true", "dry_run: bool = True" in src)
    _pass("blocked_generate_labels", "generate_button" in BLOCKED_KLING_FRAME_CLICK_LABELS)
    _pass("generate_not_clicked", "not clicked" in src.lower() or "never clicked" in src.lower())
    _pass("only_dry_run_supported", "Only dry_run=True is supported" in src)


def test_runner_never_clicks_generate_in_dry_run() -> None:
    result = run_kling_frame_to_video_shadow(
        dry_run=True,
        connect_browser=False,
        map_path=DEFAULT_MAP_PATH,
    )
    _pass("mock_run_generate_not_clicked", result.generate_clicked is False)
    _pass("mock_run_no_credits", result.credits_spent is False)
    _pass("mock_run_dry_run", result.dry_run is True)
    _pass("map_only_ok", result.ok is True)


def test_map_only_shadow_run() -> None:
    snapshot = resolve_kling_frame_to_video_controls(map_path=DEFAULT_MAP_PATH)
    _pass("map_snapshot_ok", snapshot.ok)


def test_live_cdp_validation(*, cdp_url: str) -> dict:
    result = run_kling_frame_to_video_shadow(cdp_url=cdp_url, map_path=DEFAULT_MAP_PATH, dry_run=True)
    summary_path = ROOT / "project_brain" / "kling_frame_to_video_shadow_summary.json"
    summary_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    _pass("live_cdp_ok", result.ok, str(result.errors[:3]))
    _pass("live_no_generate_click", result.generate_clicked is False)
    _pass("live_no_credits", result.credits_spent is False)
    _pass("live_duration_before", bool(result.duration_before))
    _pass(
        "live_duration_max_15s",
        result.duration_seconds_max == KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS,
        f"got {result.duration_seconds_max}",
    )
    for label in REQUIRED_KLING_FRAME_LABELS:
        if label in {"download_button", "use_frame_button"}:
            continue
        _pass(f"live_locate_{label}", label in result.locator_strategies, result.locator_strategies.get(label, ""))

    for shot in REQUIRED_SCREENSHOTS:
        path = result.screenshots.get(shot) or str(SCREENSHOT_DIR / f"{shot}.png")
        _pass(f"screenshot_{shot}", Path(path).is_file(), str(path))

    return result.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Kling Frame-to-Video UI mapper P1")
    parser.add_argument("--live", action="store_true", help="Run live CDP shadow validation")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    args = parser.parse_args()

    print("validate_kling_frame_ui_mapper_p1")
    test_ui_map_loads()
    test_all_required_labels_exist()
    test_slider_labels_exist()
    test_slider_labels_resolvable_in_snapshot()
    test_prompt_and_upload_controls_resolvable()
    test_generate_requires_approval()
    test_runner_dry_run_guard_source()
    test_runner_never_clicks_generate_in_dry_run()
    test_map_only_shadow_run()

    if args.live:
        print("\n--- live CDP validation ---")
        test_live_cdp_validation(cdp_url=args.cdp_url)
    else:
        print("\n(static checks only — pass --live for CDP slider + screenshots)")

    print("All Kling Frame-to-Video UI mapper P1 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
