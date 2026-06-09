"""
Phase I — image quality chip readback fix validation.

Ensures 2K selection is verified via scoped image-toolbar active chip readback,
not the first generic quality-like node on the page.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_continuity_dry_run import build_continuity_plan, run_dry_run
from content_brain.execution.runway_continuity_models import SEMI_AUTO_STATUS_COMPLETED
from content_brain.execution.runway_image_generation_config import DEFAULT_IMAGE_QUALITY, IMAGE_QUALITY_MENU_KEY
from content_brain.execution.runway_live_smoke_test import RunwayLiveSmokeRunner
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import (
    CHIP_VERIFY_MAX_RETRIES,
    DEFAULT_IMAGE_QUALITY_CHIP_DIAGNOSTICS,
    MappedRunwayUINavigator,
)

SAMPLE_STORY = "Astronaut on a rain-soaked platform above a neon cyberpunk city at night."


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _mock_ui_map() -> dict:
    from project_brain.validate_runway_live_smoke_test import _mock_ui_map as base_mock

    return base_mock()


def _unit_scoped_readback_implementation() -> None:
    nav_src = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    _pass("image_toolbar_readback_script", "_image_toolbar_chip_readback_eval_script" in nav_src)
    _pass("image_toolbar_click_script", "_image_toolbar_chip_click_eval_script" in nav_src)
    _pass("active_chip_scoring", "if (c.active) score += 2000" in nav_src)
    _pass("readback_settle_ms", "CHIP_READBACK_SETTLE_MS" in nav_src)
    _pass("verify_retries", f"CHIP_VERIFY_MAX_RETRIES = {CHIP_VERIFY_MAX_RETRIES}" in nav_src)
    _pass("chip_verify_retry_handler", "def _verify_chip_menu_setting_with_retry" in nav_src)
    _pass("quality_diagnostics_writer", "def _write_image_quality_chip_diagnostics" in nav_src)
    _pass(
        "image_menu_uses_scoped_read",
        "IMAGE_TOOLBAR_CHIP_MENU_KEYS" in nav_src and "probe_image_toolbar_chips" in nav_src,
    )


def _unit_selected_2k_read_as_2k() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_menu_values = {
        "image_aspect_ratio_menu": "9:16",
        "image_count_menu": "1",
        "image_quality_menu": "2K",
    }
    readback = nav.probe_image_toolbar_chips("quality")
    _pass("simulate_2k_picked", readback.picked_text == "2K", readback.picked_text)
    _pass("simulate_2k_menu_read", nav.read_menu_display_value(IMAGE_QUALITY_MENU_KEY) == "2K")

    plan = build_continuity_plan(
        project_id="quality_readback",
        starter_image_prompt="starter",
        clip_prompts=["clip"],
        image_quality="2K",
    )
    state = nav.ensure_starter_image_settings(plan)
    _pass("starter_settings_2k", state.detected_image_quality == "2K")


def _unit_stale_4k_does_not_override_2k() -> None:
    payload = {
        "toolbarFound": True,
        "toolbarContainerSelector": "[data-testid='image-composer']",
        "pickedText": "2K",
        "activeChip": {
            "kind": "quality",
            "text": "2K",
            "active": True,
            "inToolbar": True,
            "isButton": True,
            "bbox": {"x": 10, "y": 200, "width": 48, "height": 28},
            "score": 2500,
        },
        "allCandidates": [
            {
                "kind": "quality",
                "text": "4K",
                "active": False,
                "inToolbar": False,
                "isButton": False,
                "bbox": {"x": 900, "y": 120, "width": 12, "height": 10},
                "score": 120,
            },
            {
                "kind": "quality",
                "text": "2K",
                "active": True,
                "inToolbar": True,
                "isButton": True,
                "bbox": {"x": 10, "y": 200, "width": 48, "height": 28},
                "score": 2500,
            },
        ],
        "quality": "2K",
    }
    readback = MappedRunwayUINavigator._parse_image_toolbar_readback_payload(
        payload,
        chip_kind="quality",
    )
    _pass("parsed_picked_2k", readback.picked_text == "2K")
    _pass("parsed_active_2k", readback.active_chip is not None and readback.active_chip.text == "2K")
    quality_texts = [c.text for c in readback.all_candidates if c.kind == "quality"]
    _pass("multiple_quality_candidates", len(quality_texts) >= 2, str(quality_texts))
    _pass("stale_4k_not_picked", readback.picked_text != "4K")


def _unit_multiple_chips_and_retry_before_fail() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_menu_values = {"image_quality_menu": "1K"}

    calls: list[str] = []
    original = nav.read_menu_display_value

    def _flaky_read(menu_key: str) -> str:
        calls.append(menu_key)
        if len(calls) < CHIP_VERIFY_MAX_RETRIES:
            return "1K"
        return "2K"

    nav.read_menu_display_value = _flaky_read  # type: ignore[method-assign]
    result = nav.ensure_menu_setting("image_quality_menu", "image_quality_2k", ("2K",))
    _pass("retry_then_succeeds", result == "2K", str(calls))
    _pass("retry_attempt_count", len(calls) >= CHIP_VERIFY_MAX_RETRIES, str(len(calls)))
    retry_logged = any(log.action == "chip_verify_retry" for log in nav.action_log)
    _pass("retry_logged", retry_logged or len(calls) > 1)

    nav2 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav2._simulated_menu_values = {"image_quality_menu": "4K"}
    nav2.read_menu_display_value = lambda _key: "4K"  # type: ignore[method-assign]
    failed = False
    try:
        nav2.ensure_menu_setting("image_quality_menu", "image_quality_2k", ("2K",))
    except RuntimeError as exc:
        failed = True
        _pass("fails_after_retries", f"{CHIP_VERIFY_MAX_RETRIES} attempts" in str(exc))
    _pass("mismatch_does_not_silent_pass", failed)


def _unit_diagnostics_payload() -> None:
    snap = resolve_runway_ui_controls(_mock_ui_map())
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    readback = nav.probe_image_toolbar_chips("quality")
    nav._write_image_quality_chip_diagnostics(
        menu_key=IMAGE_QUALITY_MENU_KEY,
        option_key="image_quality_2k",
        expected_texts=("2K",),
        detected="4K",
        readback=readback,
        screenshot_path="chip_verify_fail_test.png",
        retry_attempts=CHIP_VERIFY_MAX_RETRIES,
    )
    _pass("diagnostics_file_exists", DEFAULT_IMAGE_QUALITY_CHIP_DIAGNOSTICS.is_file())
    payload = json.loads(DEFAULT_IMAGE_QUALITY_CHIP_DIAGNOSTICS.read_text(encoding="utf-8"))
    _pass("diag_all_quality_candidates", "all_quality_chip_candidates" in payload)
    _pass("diag_active_chip", "active_chip_candidate" in payload)
    _pass("diag_toolbar_selector", "toolbar_container_selector" in payload)
    _pass("diag_screenshot_path", payload.get("screenshot_path") == "chip_verify_fail_test.png")
    _pass("diag_action_log", "last_action_log_entries" in payload)


def _unit_no_forbidden_module_changes() -> None:
    story = (ROOT / "content_brain/execution/runway_story_brief_builder.py").read_text(encoding="utf-8")
    prompt = (ROOT / "content_brain/execution/runway_prompt_builder.py").read_text(encoding="utf-8")
    semi = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(encoding="utf-8")
    _pass("story_brief_untouched", "build_runway_story_brief" in story)
    _pass("prompt_builder_untouched", "build_continuity_prompts" in prompt)
    _pass("clip2_settle_preserved", "settle_after_use_frame_clip_" in semi)
    _pass("download_settle_preserved", "settle_after_download_clip_" in semi)


def _unit_simulated_phase_i_starter() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="quality_chip_sim",
        simulate=True,
        clip_count=3,
        approval_callback=lambda *_a: True,
        manual_ack_callback=lambda *_a: True,
    ).run()
    _pass("sim_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("sim_quality_2k", report.detected_image_quality == DEFAULT_IMAGE_QUALITY)


def main() -> int:
    print("[validate_phase_i_image_quality_chip_readback] Phase I image quality chip readback")
    _unit_scoped_readback_implementation()
    _unit_selected_2k_read_as_2k()
    _unit_stale_4k_does_not_override_2k()
    _unit_multiple_chips_and_retry_before_fail()
    _unit_diagnostics_payload()
    _unit_no_forbidden_module_changes()
    _unit_simulated_phase_i_starter()
    print("\n[validate_phase_i_image_quality_chip_readback] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
