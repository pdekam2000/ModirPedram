"""
Phase RUNWAY-STARTER-TO-VIDEO-H — live smoke test validation.

Structural / simulate checks by default. Does not require live browser for PASS.
Optional --live flag runs real CDP smoke (operator must approve gates).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.browser_connectivity_probe import BrowserProbeResult
from content_brain.execution.runway_continuity_approval_guard import APPROVAL_GATED_CONTROLS
from content_brain.execution.runway_continuity_dry_run import run_dry_run
from content_brain.execution.runway_continuity_models import (
    SEMI_AUTO_STATUS_AWAITING_APPROVAL,
    SEMI_AUTO_STATUS_COMPLETED,
    SEMI_AUTO_STATUS_FAILED,
    SEMI_AUTO_STATUS_MANUAL_HOLD,
    RunwaySemiAutoStepResult,
)
from content_brain.execution.runway_continuity_dry_run import build_continuity_plan
from content_brain.execution.runway_continuity_semi_auto import (
    RunwayContinuitySemiAutoEngine,
    build_semi_auto_session,
    run_semi_auto_prepare,
)
from content_brain.execution.runway_live_smoke_test import (
    LIVE_SMOKE_VERSION,
    MAX_COMPLETION_WAIT_MINUTES,
    SMOKE_CLIP_COUNT,
    RunwayLiveSmokeRunner,
    browser_probe_is_ok,
    browser_probe_to_dict,
    render_live_smoke_report_md,
)
from content_brain.execution.runway_live_smoke_approval_runtime import (
    GATE_APPROVAL,
    GATE_MANUAL_HOLD,
    RUN_STATUS_WAITING_APPROVAL,
    RUN_STATUS_WAITING_IMAGE_READY,
    RunwayLiveSmokeApprovalRuntime,
    build_ui_approval_callbacks,
)
from content_brain.execution.runway_prompt_builder import build_continuity_prompts
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH, resolve_runway_ui_controls
from content_brain.execution.runway_ui_navigator import (
    BUTTON_CLICK_TEXTS,
    CHIP_AFTER_CLICK_VERIFY_DELAY_MS,
    CHIP_OPTION_HOVER_DELAY_MS,
    CHIP_POPOVER_OPEN_DELAY_MS,
    MENU_OPTION_TEXTS,
    LatestGeneratedImageCardState,
    MappedRunwayUINavigator,
    click_control_texts_for,
    select_menu_option_texts_for,
)
from project_brain.validate_runway_starter_to_video_dry_run import _good_control, _mock_ui_map

SAMPLE_STORY = (
    "A lone astronaut on a rain-soaked platform above a neon cyberpunk city at night. "
    "She turns toward the skyline as rain intensifies."
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _static_checks() -> None:
    smoke_path = ROOT / "content_brain/execution/runway_live_smoke_test.py"
    runner_path = ROOT / "project_brain/run_runway_live_smoke_test.py"
    semi_auto = (ROOT / "content_brain/execution/runway_continuity_semi_auto.py").read_text(
        encoding="utf-8"
    )
    smoke = smoke_path.read_text(encoding="utf-8")
    navigator = (ROOT / "content_brain/execution/runway_ui_navigator.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")

    _pass("smoke_module_exists", smoke_path.is_file())
    _pass("runner_exists", runner_path.is_file())
    _pass("no_provider_mutation", "runway_live_smoke_test" not in provider)
    _pass("no_provider_import_in_smoke", "from providers.runway_browser_provider" not in smoke)
    _pass("simulate_false_default", "simulate: bool = False" in smoke)
    _pass("clip_count_one", f"SMOKE_CLIP_COUNT = {SMOKE_CLIP_COUNT}" in smoke and SMOKE_CLIP_COUNT == 1)
    _pass("max_wait_25", f"MAX_COMPLETION_WAIT_MINUTES = {MAX_COMPLETION_WAIT_MINUTES}" in smoke)
    _pass("acknowledge_manual_hold", "def acknowledge_manual_hold" in semi_auto)
    _pass("browser_probe_helper", "def browser_probe_is_ok" in smoke)
    _pass("select_menu_option_helper", "def select_menu_option" in navigator)
    _pass("click_control_text_fallbacks", "def _try_click_mapped_control" in navigator)
    _pass("button_click_texts", "BUTTON_CLICK_TEXTS" in navigator)
    _pass("approval_runtime_module", (ROOT / "content_brain/execution/runway_live_smoke_approval_runtime.py").is_file())
    _pass("runway_live_smoke_api_service", (ROOT / "ui/api/runway_live_smoke_service.py").is_file())
    _pass("runway_live_smoke_ui_panel", (ROOT / "ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx").is_file())
    _pass("ensure_starter_image_settings", "def ensure_starter_image_settings" in navigator)
    _pass("read_toolbar_chip_row", "def read_toolbar_chip_row" in navigator)
    _pass("select_toolbar_chip_option", "def _select_toolbar_chip_option" in navigator)
    _pass("image_toolbar_chip_keys", "IMAGE_TOOLBAR_CHIP_MENU_KEYS" in navigator)
    _pass("video_toolbar_chip_keys", "VIDEO_TOOLBAR_CHIP_MENU_KEYS" in navigator)
    _pass("ensure_video_toolbar_settings", "def ensure_video_toolbar_settings_verified" in navigator)
    _pass("semi_auto_video_chip_verify", "ensure_menu_setting" in semi_auto and "aspect_ratio_menu" in semi_auto)
    _pass("chip_detect_action", '"chip_detect"' in navigator)
    _pass("chip_popover_open_delay", "CHIP_POPOVER_OPEN_DELAY_MS = 1000" in navigator)
    _pass("chip_option_hover_delay", "CHIP_OPTION_HOVER_DELAY_MS = 400" in navigator)
    _pass("chip_after_click_delay", "CHIP_AFTER_CLICK_VERIFY_DELAY_MS = 700" in navigator)
    _pass("chip_popover_wait_action", '"chip_popover_wait"' in navigator)
    _pass("chip_mouse_hover_click", "_human_like_locator_click" in navigator and "mouse.move" in navigator)
    _pass("latest_image_card_select", "def select_latest_generated_image_card" in navigator)
    _pass("latest_image_card_locate", "def locate_and_prepare_latest_image_card" in navigator)
    _pass("latest_image_transition_verify", "def verify_video_generation_transition" in navigator)
    _pass("image_cards_snapshot_before_generate", "def snapshot_generation_image_cards_before_generate" in navigator)
    _pass("semi_auto_snapshot_before_generate", "snapshot_generation_image_cards_before_generate" in semi_auto)
    _pass("semi_auto_latest_image_flow", "use_starter_image_for_video" in semi_auto)
    _pass("semi_auto_preclean_step", "preclean_starter_image_workspace" in semi_auto)
    _pass("cleanup_used_image_card", "def cleanup_used_image_card_after_use_to_video" in navigator)
    _pass("consumed_image_card_filter", "_consumed_image_card_fingerprints" in navigator)
    _pass("image_card_remove_optional_loader", "OPTIONAL_RUNWAY_UI_CONTROLS" in (ROOT / "content_brain/execution/runway_ui_map_loader.py").read_text(encoding="utf-8"))
    _pass("video_generation_started_field", "video_generation_started" in smoke)
    _pass("browser_state_field", "browser_state" in smoke)
    _pass("semi_auto_cleanup_step", "cleanup_used_image_card_after_use_to_video" in semi_auto)
    _pass("clear_prompt_control", "def clear_prompt_control" in navigator)
    _pass("verify_starter_image_step", "verify_starter_image_settings" in semi_auto)
    _pass("no_probe_ok_attribute", "probe.ok" not in smoke)


def _unit_browser_probe_schema() -> None:
    passed = BrowserProbeResult(True, [{"id": "BROWSER_AVAILABLE", "passed": True, "message": "ok"}])
    failed = BrowserProbeResult(
        False,
        [{"id": "BROWSER_AVAILABLE", "passed": False, "message": "CDP not reachable"}],
        "BROWSER_UNAVAILABLE",
        "CDP not reachable at 127.0.0.1:9222",
    )

    class LegacyProbe:
        success = True
        message = "legacy attach ok"

    _pass("probe_passed_field_ok", browser_probe_is_ok(passed))
    _pass("probe_failed_field_not_ok", not browser_probe_is_ok(failed))
    _pass("probe_legacy_success_ok", browser_probe_is_ok(LegacyProbe()))
    _pass("probe_to_dict_passed", browser_probe_to_dict(passed).get("passed") is True)
    _pass("probe_to_dict_no_ok_attr", "ok" not in BrowserProbeResult.__dataclass_fields__)
    _pass("probe_to_dict_includes_ok_compat", browser_probe_to_dict(passed).get("ok") is True)


def _unit_failed_probe_safe_fail_report() -> None:
    failed = BrowserProbeResult(
        False,
        [{"id": "BROWSER_AVAILABLE", "passed": False, "message": "CDP not reachable"}],
        "BROWSER_UNAVAILABLE",
        "CDP not reachable at 127.0.0.1:9222",
    )
    with patch(
        "content_brain.execution.runway_live_smoke_test.run_browser_probes",
        return_value=failed,
    ):
        report = RunwayLiveSmokeRunner(
            story_idea=SAMPLE_STORY,
            project_id="h_probe_fail",
            simulate=False,
        ).run()

    _pass("failed_probe_no_attribute_error", report.ok is False)
    _pass("failed_probe_stopped_reason", "browser probe failed" in report.stopped_reason.lower())
    _pass("failed_probe_message", bool(report.browser_probe_message))
    _pass("failed_probe_dict", report.browser_probe.get("passed") is False)
    _pass("failed_probe_not_connected", report.browser_connected is False)
    _pass("failed_probe_has_errors", len(report.errors) >= 1)


def _unit_single_clip_plan() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, project_id="h_test", clip_count=1)
    plan = bundle.to_continuity_plan(max_wait_minutes_per_clip=MAX_COMPLETION_WAIT_MINUTES)
    _pass("plan_one_clip", len(plan.clip_prompts) == 1)
    _pass("plan_max_wait_25", plan.max_wait_minutes_per_clip == 25)

    dry = run_dry_run(plan, map_path=DEFAULT_MAP_PATH)
    _pass("dry_run_ok", dry.ok is True, str(dry.errors))
    gated = [s for s in dry.steps if s.control_key in APPROVAL_GATED_CONTROLS]
    _pass("three_approval_gates", len(gated) == 3, str([s.control_key for s in gated]))
    _pass("no_use_frame_step", not any("use_frame_for_clip" in s.step_id for s in dry.steps))
    _pass("has_remove_image", any(s.control_key == "remove_image" for s in dry.steps))
    _pass("has_use_to_video", any(s.control_key == "image_use_to_video_option" for s in dry.steps))
    _pass("has_cleanup_used_image_card", any("cleanup_used_image_card_after_use_to_video" in s.step_id for s in dry.steps))


def _unit_simulated_smoke_rehearsal() -> None:
    approvals: list[tuple[str, str]] = []

    def auto_approve(control_key: str, step_id: str, label: str) -> bool:
        approvals.append((control_key, step_id))
        return True

    def auto_manual(step_id: str, action: str) -> bool:
        return True

    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="h_sim_rehearsal",
        operator="validator",
        simulate=True,
        approval_callback=auto_approve,
        manual_ack_callback=auto_manual,
    ).run()

    _pass("sim_rehearsal_completed", report.final_status == SEMI_AUTO_STATUS_COMPLETED, report.final_status)
    _pass("sim_three_approvals", len(approvals) == 3, str(approvals))
    _pass("sim_remove_image", report.remove_image_executed is True)
    _pass("sim_completion", report.video_completion_detected is True)
    _pass("sim_download_attempted", report.download_attempted is True)
    _pass("sim_report_md_nonempty", len(render_live_smoke_report_md(report)) > 500)


def _unit_prepare_pauses_live_path() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=1)
    plan = bundle.to_continuity_plan()
    prep = run_semi_auto_prepare(plan, map_path=DEFAULT_MAP_PATH, simulate=True)
    _pass("prepare_pauses_generate", prep.session.awaiting_control_key == "image_generate_button")


def _unit_manual_ack_engine() -> None:
    bundle = build_continuity_prompts(SAMPLE_STORY, clip_count=1)
    plan = bundle.to_continuity_plan()
    nav = MappedRunwayUINavigator.from_map(map_path=DEFAULT_MAP_PATH, simulate=True)
    engine = RunwayContinuitySemiAutoEngine(nav, simulate=True)
    session = build_semi_auto_session(plan, map_path=DEFAULT_MAP_PATH)

    for _ in range(6):
        engine.advance(session)
        if session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL:
            engine.approve(
                session,
                control_key=str(session.awaiting_control_key),
                step_id=str(session.awaiting_step_id),
                approved_by="validator",
            )
        if session.status == SEMI_AUTO_STATUS_MANUAL_HOLD:
            engine.acknowledge_manual_hold(session)
        if session.status == SEMI_AUTO_STATUS_COMPLETED:
            break

    _pass("manual_ack_engine_completed", session.status == SEMI_AUTO_STATUS_COMPLETED, session.status)


class _FakeLocator:
    def __init__(
        self,
        *,
        visible: bool = True,
        click_raises: Exception | None = None,
        bounding_box: dict[str, float] | None = None,
    ) -> None:
        self._visible = visible
        self._click_raises = click_raises
        self._bounding_box = bounding_box
        self.clicked = False

    @property
    def first(self):
        return self

    def nth(self, index: int):
        return self

    def count(self) -> int:
        return 1 if self._visible else 0

    def is_visible(self) -> bool:
        return self._visible

    def wait_for(self, **kwargs: Any) -> None:
        if not self._visible:
            raise TimeoutError("not visible")

    def scroll_into_view_if_needed(self, **kwargs: Any) -> None:
        if not self._visible:
            raise TimeoutError("not visible")

    def bounding_box(self) -> dict[str, float] | None:
        return self._bounding_box

    def click(self, **kwargs: Any) -> None:
        if self._click_raises is not None:
            raise self._click_raises
        self.clicked = True


class _FakeMouse:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float]] = []
        self.clicks: list[tuple[float, float]] = []

    def move(self, x: float, y: float) -> None:
        self.moves.append((x, y))

    def click(self, x: float, y: float) -> None:
        self.clicks.append((x, y))


class _FakePage:
    def __init__(self) -> None:
        self.menu_opener = _FakeLocator(visible=True)
        self.stale_option = _FakeLocator(visible=True, click_raises=TimeoutError("stale id"))
        self.text_option = _FakeLocator(
            visible=True,
            bounding_box={"x": 120.0, "y": 220.0, "width": 36.0, "height": 28.0},
        )
        self.listbox = _FakeLocator(visible=True)
        self.evaluate_results: list[Any] = [False]
        self.evaluate_calls: list[tuple[str, Any]] = []
        self.locator_calls: list[str] = []
        self.text_calls: list[tuple[str, bool]] = []
        self.mouse = _FakeMouse()

    def locator(self, selector: str):
        self.locator_calls.append(selector)
        if "listbox" in selector or "menu" in selector or "popper" in selector or "dialog" in selector:
            return self.listbox
        if "stale-option" in selector:
            return self.stale_option
        if selector == "span":
            return self.menu_opener
        return self.stale_option

    def get_by_text(self, text: str, *, exact: bool = False):
        self.text_calls.append((text, exact))
        if text in {"9:16", "2K", "10s", "1", "5s", "Generate", "Generate Image", "Download MP4"}:
            return self.text_option
        return _FakeLocator(visible=False)

    def get_by_role(self, role: str, name: str | None = None, *, exact: bool = False):
        if role == "option" and name in {"9:16", "2K", "10s", "1", "5s"}:
            return self.text_option
        if role == "button" and name in {"Generate", "Generate Image", "Download MP4", "Actions"}:
            return self.text_option
        return _FakeLocator(visible=False)

    def evaluate(self, script: str, arg: Any = None):
        self.evaluate_calls.append((script, arg))
        if isinstance(arg, dict) and arg.get("chipKind"):
            return True
        if self.evaluate_results:
            return self.evaluate_results.pop(0)
        return False


def _menu_navigator(page: _FakePage) -> MappedRunwayUINavigator:
    ui = _mock_ui_map()
    ui["labels"]["image_aspect_ratio_menu"] = _good_control(
        "image_aspect_ratio_menu", tag="span", css="span", text="Auto"
    )
    ui["labels"]["image_aspect_ratio_9_16"] = _good_control(
        "image_aspect_ratio_9_16",
        tag="div",
        css="#stale-option-9-16",
        text="9:16",
    )
    ui["labels"]["image_quality_menu"] = _good_control(
        "image_quality_menu", tag="span", css="span", text="1K"
    )
    ui["labels"]["image_quality_2k"] = _good_control(
        "image_quality_2k", tag="div", css="#stale-option-2k", text="2K"
    )
    ui["labels"]["image_count_menu"] = _good_control(
        "image_count_menu", tag="span", css="span", text="4"
    )
    ui["labels"]["image_count_1"] = _good_control(
        "image_count_1", tag="div", css="#stale-option-count-1", text="1"
    )
    ui["labels"]["duration_menu"] = _good_control(
        "duration_menu", tag="span", css="span", text="5s"
    )
    ui["labels"]["duration_10s"] = _good_control(
        "duration_10s", tag="span", css="#stale-option-10s", text="10s"
    )
    snap = resolve_runway_ui_controls(ui)
    return MappedRunwayUINavigator(snapshot=snap, page=page, simulate=False)


def _unit_menu_selection_fallbacks() -> None:
    sleep_calls: list[float] = []
    original_sleep = time.sleep

    def tracked_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    page = _FakePage()
    nav = _menu_navigator(page)
    screenshots: list[str] = []
    nav.screenshot_fn = lambda label: screenshots.append(label)

    with patch("content_brain.execution.runway_ui_navigator.time.sleep", tracked_sleep):
        nav.select_menu_option(
            "image_aspect_ratio_menu",
            "image_aspect_ratio_9_16",
            select_menu_option_texts_for("image_aspect_ratio_menu", "image_aspect_ratio_9_16"),
        )
    _pass(
        "chip_opener_clicked",
        any(call[1].get("chipKind") == "aspect" for call in page.evaluate_calls if isinstance(call[1], dict)),
    )
    _pass("chip_popover_open_delay_applied", CHIP_POPOVER_OPEN_DELAY_MS / 1000.0 in sleep_calls)
    _pass("chip_mouse_move_used", len(page.mouse.moves) >= 1)
    _pass("chip_mouse_click_used", len(page.mouse.clicks) >= 1)
    _pass("chip_option_box_logged", any(log.action == "chip_option_box" for log in nav.action_log))
    _pass(
        "image_9_16_option_targeted",
        any("9:16" in log.detail for log in nav.action_log if log.action in {"chip_hover", "chip_option_box"}),
    )

    page = _FakePage()
    nav = _menu_navigator(page)
    sleep_calls.clear()
    with patch("content_brain.execution.runway_ui_navigator.time.sleep", tracked_sleep):
        nav.select_menu_option(
            "image_quality_menu",
            "image_quality_2k",
            select_menu_option_texts_for("image_quality_menu", "image_quality_2k"),
        )
    _pass(
        "quality_chip_opened",
        any(call[1].get("chipKind") == "quality" for call in page.evaluate_calls if isinstance(call[1], dict)),
    )
    _pass("quality_chip_hover_delay_applied", CHIP_OPTION_HOVER_DELAY_MS / 1000.0 in sleep_calls)
    _pass("quality_2k_mouse_click", len(page.mouse.clicks) >= 1)

    page = _FakePage()
    nav = _menu_navigator(page)
    sleep_calls.clear()
    with patch("content_brain.execution.runway_ui_navigator.time.sleep", tracked_sleep):
        nav.select_menu_option(
            "image_count_menu",
            "image_count_1",
            select_menu_option_texts_for("image_count_menu", "image_count_1"),
        )
    _pass("count_chip_opened", any(call[1].get("chipKind") == "count" for call in page.evaluate_calls if isinstance(call[1], dict)))
    _pass("count_1_mouse_click", len(page.mouse.clicks) >= 1)
    _pass("chip_popover_wait_logged", any(log.action == "chip_popover_wait" for log in nav.action_log))

    page = _FakePage()
    nav = _menu_navigator(page)
    sleep_calls.clear()
    with patch("content_brain.execution.runway_ui_navigator.time.sleep", tracked_sleep):
        nav.select_menu_option(
            "duration_menu",
            "duration_10s",
            select_menu_option_texts_for("duration_menu", "duration_10s"),
        )
    _pass(
        "duration_chip_opened",
        any(call[1].get("chipKind") == "duration" for call in page.evaluate_calls if isinstance(call[1], dict)),
    )
    _pass("duration_10s_mouse_click", len(page.mouse.clicks) >= 1)


def _unit_menu_selection_safe_fail() -> None:
    page = _FakePage()
    page.text_option = _FakeLocator(visible=False, bounding_box=None)
    nav = _menu_navigator(page)
    screenshots: list[str] = []
    nav.screenshot_fn = lambda label: screenshots.append(label)
    failed = False
    try:
        nav.select_menu_option("image_aspect_ratio_menu", "image_aspect_ratio_9_16", ("9:16",))
    except RuntimeError as exc:
        failed = True
        _pass("safe_fail_runtime_error", "toolbar chip selection failed" in str(exc).lower())
    _pass("safe_fail_no_crash", failed)
    _pass("safe_fail_screenshot", any("chip_select_fail" in label for label in screenshots))


def _button_navigator(page: _FakePage) -> MappedRunwayUINavigator:
    ui = _mock_ui_map()
    ui["labels"]["image_generate_button"] = _good_control(
        "image_generate_button",
        tag="button",
        css="#react-aria-stale-generate",
        text="Generate",
    )
    snap = resolve_runway_ui_controls(ui)
    return MappedRunwayUINavigator(snapshot=snap, page=page, simulate=False)


def _unit_approval_gated_button_fallbacks() -> None:
    page = _FakePage()
    page.stale_option = _FakeLocator(visible=True, click_raises=TimeoutError("stale id"))
    nav = _button_navigator(page)
    nav.click_control("image_generate_button", step_id="005_image_generate_manual_required", approved=True)
    _pass("generate_stale_selector_tried", "#react-aria-stale-generate" in page.locator_calls)
    _pass("generate_text_fallback", page.text_option.clicked is True)
    _pass(
        "generate_texts_include_generate",
        "Generate" in click_control_texts_for("image_generate_button"),
    )
    _pass(
        "button_click_texts_keys",
        all(key in BUTTON_CLICK_TEXTS for key in ("image_generate_button", "generate_button", "download_mp4_button")),
    )


def _unit_app_menu_aria_fallback() -> None:
    page = _FakePage()
    page.stale_option = _FakeLocator(visible=True, click_raises=TimeoutError("stale id"))
    ui = _mock_ui_map()
    ui["labels"]["image_app_menu_button"] = _good_control(
        "image_app_menu_button",
        tag="button",
        css="#react-aria-stale-actions",
        text="",
    )
    ui["labels"]["image_app_menu_button"]["aria_label"] = "Actions"
    ui["labels"]["image_app_menu_button"]["metadata"]["aria_label"] = "Actions"
    snap = resolve_runway_ui_controls(ui)
    nav = MappedRunwayUINavigator(snapshot=snap, page=page, simulate=False)
    nav.click_control("image_app_menu_button")
    _pass("app_menu_stale_selector_tried", "#react-aria-stale-actions" in page.locator_calls)
    _pass("app_menu_aria_fallback", page.text_option.clicked is True)


def _unit_button_click_safe_fail() -> None:
    page = _FakePage()
    page.text_option = _FakeLocator(visible=False)
    page.stale_option = _FakeLocator(visible=True, click_raises=TimeoutError("stale id"))
    nav = _button_navigator(page)
    screenshots: list[str] = []
    nav.screenshot_fn = lambda label: screenshots.append(label)
    failed = False
    try:
        nav.click_control("image_generate_button", approved=True)
    except RuntimeError as exc:
        failed = True
        _pass("button_click_safe_fail_runtime_error", "click failed" in str(exc).lower())
    _pass("button_click_safe_fail_no_crash", failed)
    _pass("button_click_safe_fail_screenshot", len(screenshots) == 1)


def _unit_ui_approval_runtime_bridge() -> None:
    runtime = RunwayLiveSmokeApprovalRuntime(
        operator="validator",
        project_id="h5_ui",
        fallback_to_terminal=False,
        ui_poll_seconds=0.05,
    )
    runtime.mark_ui_connected(True)
    approval_cb, manual_cb = build_ui_approval_callbacks(runtime)
    results: dict[str, bool | None] = {"approval": None, "manual": None}

    def approval_worker() -> None:
        results["approval"] = approval_cb("image_generate_button", "005_image_generate_manual_required", "Generate")

    def manual_worker() -> None:
        results["manual"] = manual_cb("006_wait_for_image_ready_manual", "wait for image")

    import threading

    t1 = threading.Thread(target=approval_worker, daemon=True)
    t1.start()
    for _ in range(40):
        snap = runtime.snapshot()
        if snap.waiting and snap.gate_type == GATE_APPROVAL:
            break
        threading.Event().wait(0.05)
    snap = runtime.snapshot()
    _pass("ui_bridge_waiting_approval", snap.run_status == RUN_STATUS_WAITING_APPROVAL)
    _pass("ui_bridge_control_visible", snap.current_control_key == "image_generate_button")
    runtime.submit_approve(operator="validator")
    t1.join(timeout=2)
    _pass("ui_bridge_approval_reaches_runtime", results["approval"] is True)

    t2 = threading.Thread(target=manual_worker, daemon=True)
    t2.start()
    for _ in range(40):
        snap = runtime.snapshot()
        if snap.waiting and snap.gate_type == GATE_MANUAL_HOLD:
            break
        threading.Event().wait(0.05)
    _pass("ui_bridge_waiting_image_ready", runtime.snapshot().run_status == RUN_STATUS_WAITING_IMAGE_READY)
    runtime.submit_image_ready(operator="validator")
    t2.join(timeout=2)
    _pass("ui_bridge_image_ready_reaches_runtime", results["manual"] is True)
    _pass("ui_bridge_history_nonempty", len(runtime.snapshot().approval_history) >= 4)


def _unit_ui_approval_terminal_fallback() -> None:
    runtime = RunwayLiveSmokeApprovalRuntime(
        fallback_to_terminal=True,
        ui_poll_seconds=0.05,
        terminal_approval=lambda _c, _s, _l: True,
        terminal_manual_ack=lambda _s, _a: True,
    )

    granted = runtime.approval_callback("generate_button", "012_video_generate_manual_required_clip_1", "Generate")
    ready = runtime.manual_ack_callback("006_wait_for_image_ready_manual", "wait")
    _pass("terminal_fallback_approve", granted is True)
    _pass("terminal_fallback_ready", ready is True)


def _unit_starter_image_settings_enforcement() -> None:
    from content_brain.execution.runway_continuity_models import (
        SEMI_AUTO_STATUS_AWAITING_APPROVAL,
        SEMI_AUTO_STATUS_FAILED,
        SEMI_AUTO_STATUS_PREPARING,
    )

    ui = _mock_ui_map()
    snap = resolve_runway_ui_controls(ui)
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    plan = build_continuity_plan(
        project_id="h6_settings",
        starter_image_prompt="test starter",
        clip_prompts=["clip"],
        image_quality="2K",
        image_count=1,
    )

    nav._simulated_menu_values = {
        "image_aspect_ratio_menu": "9:16",
        "image_count_menu": "1",
        "image_quality_menu": "2K",
    }
    state = nav.ensure_starter_image_settings(plan)
    _pass("settings_skip_already_correct", state.settings_verified is True)
    _pass("settings_skip_action_logged", any(
        log.action in {"menu_verify_skip", "chip_verify_skip"} for log in nav.action_log
    ))

    nav2 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav2._simulated_menu_values = {
        "image_aspect_ratio_menu": "9:16",
        "image_count_menu": "4",
        "image_quality_menu": "1K",
    }
    state2 = nav2.ensure_starter_image_settings(plan)
    _pass("settings_corrected_from_wrong_defaults", state2.detected_image_quality == "2K")
    _pass("settings_count_corrected", state2.detected_image_count == "1")
    _pass("settings_correction_uses_chip_flow", any(log.action == "chip_open" for log in nav2.action_log))
    chip_row = nav2.read_toolbar_chip_row()
    _pass("chip_row_reads_count", chip_row.get("count") == "1")
    _pass("chip_row_reads_quality", chip_row.get("quality") == "2K")

    nav3 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav3._simulated_menu_values = {"image_quality_menu": "1K"}

    def _always_1k(menu_key: str) -> str:
        return "1K" if menu_key == "image_quality_menu" else "2K"

    nav3.read_menu_display_value = _always_1k  # type: ignore[method-assign]
    failed = False
    try:
        nav3.ensure_menu_setting("image_quality_menu", "image_quality_2k", ("2K",))
    except RuntimeError as exc:
        failed = True
        _pass("quality_stays_1k_fails", "verification failed" in str(exc).lower())
    _pass("quality_stays_1k_no_silent_pass", failed)

    nav4 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav4._simulated_menu_values = {"image_count_menu": "4"}

    def _always_4(menu_key: str) -> str:
        return "4" if menu_key == "image_count_menu" else "1"

    nav4.read_menu_display_value = _always_4  # type: ignore[method-assign]
    count_failed = False
    try:
        nav4.ensure_menu_setting("image_count_menu", "image_count_1", ("1",))
    except RuntimeError as exc:
        count_failed = True
        _pass("count_stays_4_fails", "verification failed" in str(exc).lower())
    _pass("count_stays_4_no_silent_pass", count_failed)

    session = build_semi_auto_session(plan, ui_map=ui)
    engine = RunwayContinuitySemiAutoEngine(nav, simulate=True)
    for _ in range(12):
        if session.status in {SEMI_AUTO_STATUS_AWAITING_APPROVAL, SEMI_AUTO_STATUS_FAILED}:
            break
        engine.advance(session)
    _pass("generate_gate_requires_verified_settings", session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL)
    _pass("settings_verified_before_generate", bool(nav.last_starter_settings and nav.last_starter_settings.settings_verified))

    bad_nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    bad_session = build_semi_auto_session(plan, ui_map=ui)
    bad_engine = RunwayContinuitySemiAutoEngine(bad_nav, simulate=True)
    generate_index = next(
        index
        for index, step in enumerate(bad_session.steps)
        if step.control_key == "image_generate_button"
    )
    bad_session.current_step_index = generate_index
    bad_session.status = SEMI_AUTO_STATUS_PREPARING
    bad_engine.advance(bad_session)
    _pass("unverified_settings_block_generate", bad_session.status == SEMI_AUTO_STATUS_FAILED)


def _unit_image_prompt_clearing() -> None:
    ui = _mock_ui_map()
    snap = resolve_runway_ui_controls(ui)
    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_prompt_text["image_prompt_input"] = "leftover prompt text"
    clear_result = nav.clear_prompt_control("image_prompt_input")
    _pass("prompt_clear_success", clear_result.image_prompt_cleared is True)
    _pass("prompt_clear_after_empty", clear_result.prompt_text_after_clear == "")

    nav2 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    empty_result = nav2.ensure_prompt_control_empty("image_prompt_input")
    _pass("prompt_already_empty_skip", empty_result.image_prompt_cleared is True)

    nav3 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav3.ensure_prompt_control_empty("image_prompt_input")
    nav3.fill_prompt_control("image_prompt_input", "fresh prompt")
    _pass("prompt_fill_after_empty", nav3.read_prompt_control_text("image_prompt_input") == "fresh prompt")


def _unit_stale_selector_prefers_text() -> None:
    page = _FakePage()
    nav = _menu_navigator(page)
    nav.select_menu_option("image_aspect_ratio_menu", "image_aspect_ratio_9_16", ("9:16",))
    _pass("chip_prefers_visible_text", len(page.mouse.clicks) >= 1)
    _pass("chip_text_before_mapped_stale", "#stale-option-9-16" not in page.locator_calls)

    page2 = _FakePage()
    page2.text_option = _FakeLocator(visible=False, bounding_box=None)
    page2.stale_option = _FakeLocator(
        visible=True,
        bounding_box={"x": 80.0, "y": 180.0, "width": 30.0, "height": 24.0},
    )
    nav2 = _menu_navigator(page2)
    nav2.select_menu_option("image_aspect_ratio_menu", "image_aspect_ratio_9_16", ("9:16",))
    _pass("stale_selector_mapped_fallback", "#stale-option-9-16" in page2.locator_calls)
    _pass("stale_selector_mapped_mouse_recovered", len(page2.mouse.clicks) >= 1)


def _unit_latest_image_card_selection() -> None:
    ui = _mock_ui_map()
    snap = resolve_runway_ui_controls(ui)
    prompt = "neon astronaut starter prompt"
    old_card = {
        "cardTop": 80.0,
        "cardBottom": 360.0,
        "cardLeft": 20.0,
        "cardWidth": 260.0,
        "cardHeight": 280.0,
        "cardPromptText": "older image output",
        "hasAppMenu": True,
    }

    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_generation_cards = [dict(old_card)]
    before = nav.snapshot_generation_image_cards_before_generate()
    _pass("snapshot_before_generate_count", before.card_count == 1)
    _pass("snapshot_before_generate_fingerprints", len(before.fingerprints) == 1)

    state = nav.select_latest_generated_image_card(prompt)
    _pass("latest_card_found", state.latest_image_card_found is True)
    _pass("latest_card_selected_by_diff", "new_card_diff" in state.selection_reason)
    _pass("latest_card_prompt_match", prompt in state.card_prompt_text)
    _pass("old_card_not_selected", "older image output" not in state.card_prompt_text)
    _pass("new_card_candidates_count", state.new_card_candidates_count >= 1)

    scroll_labels: list[str] = []
    nav.screenshot_fn = lambda label: scroll_labels.append(label)
    nav.locate_and_prepare_latest_image_card(prompt)
    _pass("scroll_before_latest_image", "latest_image_before_scroll" in scroll_labels)
    _pass("scroll_after_latest_image", "latest_image_after_scroll" in scroll_labels)
    _pass("scroll_logged_before_app_menu", any(log.action == "latest_image_scroll" for log in nav.action_log))

    nav.open_app_menu_on_latest_image_card()
    _pass("app_menu_open_on_latest_card", any(log.action == "latest_image_app_menu_open" for log in nav.action_log))
    nav.click_use_to_video_on_latest_image_card()
    _pass("use_to_video_on_latest_card", any(log.action == "latest_image_use_to_video" for log in nav.action_log))
    _pass("transition_verified_after_use_to_video", nav.verify_video_generation_transition() is True)

    nav_stale = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav_stale._simulated_generation_cards = [dict(old_card)]
    nav_stale.snapshot_generation_image_cards_before_generate()
    nav_stale._ensure_simulated_post_generate_cards = lambda prompt_text=None: None  # type: ignore[method-assign]
    stale = nav_stale.select_latest_generated_image_card(prompt)
    stale_failed = False
    try:
        nav_stale.locate_and_prepare_latest_image_card(prompt)
    except RuntimeError as exc:
        stale_failed = True
        _pass("old_only_after_generate_fail_safe", "newly added" in str(exc).lower())
    _pass("old_only_after_generate_raises", stale_failed)
    _pass("old_only_has_no_new_candidates", not stale.latest_image_card_found)

    nav_empty = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav_empty._simulated_generation_cards = []
    missing = False
    try:
        nav_empty.locate_and_prepare_latest_image_card(prompt)
    except RuntimeError as exc:
        missing = True
        _pass("no_latest_card_fail_safe", "not found" in str(exc).lower() or "newly added" in str(exc).lower())
    _pass("no_latest_card_raises", missing)

    nav_no_menu = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav_no_menu._simulated_generation_cards = [dict(old_card)]
    nav_no_menu.snapshot_generation_image_cards_before_generate()
    nav_no_menu._simulated_generation_cards.append(
        {
            "cardTop": 480.0,
            "cardBottom": 880.0,
            "cardLeft": 20.0,
            "cardWidth": 260.0,
            "cardHeight": 400.0,
            "cardPromptText": prompt,
            "hasAppMenu": False,
        }
    )
    no_menu = False
    try:
        nav_no_menu.locate_and_prepare_latest_image_card(prompt)
    except RuntimeError as exc:
        no_menu = True
        _pass("latest_card_no_app_menu_fail_safe", "app menu" in str(exc).lower())
    _pass("latest_card_no_app_menu_raises", no_menu)

    plan = build_continuity_plan(
        project_id="latest_image_guard",
        starter_image_prompt=prompt,
        clip_prompts=["clip one"],
    )
    nav_guard = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav_guard.last_latest_image_card = LatestGeneratedImageCardState(
        latest_image_card_found=True,
        video_transition_verified=True,
    )

    def _prompt_not_ready(clip_index: int, **_kwargs: Any) -> Any:
        from content_brain.execution.runway_ui_navigator import PromptEditorReadyState

        return PromptEditorReadyState(
            clip_index=clip_index,
            checked=True,
            ready=False,
            notes=["test_guard"],
        )

    nav_guard.wait_for_prompt_editor_ready = _prompt_not_ready  # type: ignore[method-assign]
    engine = RunwayContinuitySemiAutoEngine(nav_guard, simulate=True)
    session = build_semi_auto_session(plan, ui_map=ui)
    step = next(item for item in session.steps if item.step_id.endswith("video_prompt_clip_1"))
    result = RunwaySemiAutoStepResult(
        step_id=step.step_id,
        action=step.action,
        control_key=step.control_key,
    )
    blocked = False
    try:
        engine._execute_step(session, step, result, gate_approved=False)
    except RuntimeError as exc:
        blocked = True
        _pass(
            "video_prompt_blocked_without_readiness",
            "prompt editor not ready" in str(exc).lower(),
        )
    _pass("video_prompt_guard_raises", blocked)


def _unit_used_image_card_cleanup_and_consumed() -> None:
    ui = _mock_ui_map()
    snap = resolve_runway_ui_controls(ui)
    prompt = "neon astronaut starter prompt"
    old_card = {
        "cardTop": 80.0,
        "cardBottom": 360.0,
        "cardLeft": 20.0,
        "cardWidth": 260.0,
        "cardHeight": 280.0,
        "cardPromptText": "older image output",
        "hasAppMenu": True,
    }

    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_generation_cards = [dict(old_card)]
    nav.snapshot_generation_image_cards_before_generate()
    nav.select_latest_generated_image_card(prompt)
    nav.last_latest_image_card = nav.last_latest_image_card or LatestGeneratedImageCardState()
    nav.last_latest_image_card.video_transition_verified = True

    cleanup = nav.cleanup_used_image_card_after_use_to_video()
    _pass("cleanup_marks_or_removes", cleanup.used_image_card_removed or cleanup.used_image_card_marked_consumed)
    _pass("cleanup_has_fingerprint", bool(cleanup.selected_image_card_fingerprint))
    _pass("consumed_tracked", len(nav._consumed_image_card_fingerprints) >= 1 or cleanup.used_image_card_removed)

    nav.snapshot_generation_image_cards_before_generate()
    nav._ensure_simulated_post_generate_cards("second run prompt")
    second = nav.select_latest_generated_image_card("second run prompt")
    _pass("consumed_old_not_reselected", "older image output" not in second.card_prompt_text)
    _pass("second_run_selects_new", "second run prompt" in second.card_prompt_text)

    nav2 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav2._simulated_generation_cards = [dict(old_card)]
    nav2.snapshot_generation_image_cards_before_generate()
    nav2._ensure_simulated_post_generate_cards(prompt)
    nav2.select_latest_generated_image_card(prompt)
    nav2.last_latest_image_card = nav2.last_latest_image_card or LatestGeneratedImageCardState()
    nav2.last_latest_image_card.video_transition_verified = True
    nav2._click_remove_button_on_used_image_card = lambda **kwargs: False  # type: ignore[method-assign]
    marked = nav2.cleanup_used_image_card_after_use_to_video()
    _pass("fallback_mark_consumed", marked.used_image_card_marked_consumed is True)
    _pass("fallback_not_removed", marked.used_image_card_removed is False)

    stale = nav2.select_latest_generated_image_card("another prompt")
    _pass("consumed_card_ignored_on_rescan", stale.latest_image_card_found is False or "older image output" not in stale.card_prompt_text)


def _unit_video_generation_started_reporting() -> None:
    report = RunwayLiveSmokeRunner(
        story_idea=SAMPLE_STORY,
        project_id="h_video_started_diag",
        operator="validator",
        simulate=True,
        approval_callback=lambda *_args: True,
        manual_ack_callback=lambda *_args: True,
    ).report
    report.video_generation_started = True
    report.ok = False
    report.browser_state = "video_generation_started"
    md = render_live_smoke_report_md(report)
    _pass("report_video_generation_started_field", report.video_generation_started is True)
    _pass("report_browser_state_video_started", report.browser_state == "video_generation_started")
    _pass("md_shows_partial_video_started", "video generation started" in md.lower())


def _unit_video_toolbar_chip_verification() -> None:
    ui = _mock_ui_map()
    snap = resolve_runway_ui_controls(ui)
    prompt_aspect = ("9:16", "9 : 16", "9: 16", "9 / 16")
    prompt_duration = ("10s", "10S", "10 s", "10 seconds")

    nav = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav._simulated_menu_values = {
        "aspect_ratio_menu": "9:16",
        "duration_menu": "5s",
    }
    detected_aspect = nav.ensure_menu_setting(
        "aspect_ratio_menu",
        "aspect_ratio_9_16",
        prompt_aspect,
    )
    _pass("video_aspect_skip_when_correct", detected_aspect == "9:16")
    _pass(
        "video_aspect_skip_logged",
        any(
            log.action == "chip_verify_skip" and log.control_key == "aspect_ratio_menu"
            for log in nav.action_log
        ),
    )
    _pass(
        "video_aspect_no_unnecessary_open",
        not any(
            log.action == "chip_open" and log.control_key == "aspect_ratio_menu"
            for log in nav.action_log
        ),
    )

    nav2 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav2._simulated_menu_values = {
        "aspect_ratio_menu": "9:16",
        "duration_menu": "5s",
    }
    nav2.ensure_menu_setting("duration_menu", "duration_10s", prompt_duration)
    state = nav2.ensure_video_toolbar_settings_verified()
    _pass("video_duration_changed_to_10s", state.detected_duration == "10s")
    _pass("video_aspect_still_9_16", state.detected_aspect_ratio == "9:16")
    _pass("video_settings_verified", state.video_settings_verified is True)
    _pass(
        "video_duration_chip_open_logged",
        any(log.action == "chip_open" and log.control_key == "duration_menu" for log in nav2.action_log),
    )

    nav3 = MappedRunwayUINavigator(snapshot=snap, simulate=True)
    nav3._simulated_menu_values = {
        "aspect_ratio_menu": "9:16",
        "duration_menu": "10s",
    }
    nav3.ensure_menu_setting("aspect_ratio_menu", "aspect_ratio_9_16", prompt_aspect)
    nav3.ensure_menu_setting("duration_menu", "duration_10s", prompt_duration)
    _pass(
        "video_duration_skip_when_already_10s",
        any(
            log.action == "chip_verify_skip" and log.control_key == "duration_menu"
            for log in nav3.action_log
        ),
    )


def main() -> int:
    print(f"[validate_runway_live_smoke_test] {LIVE_SMOKE_VERSION}")
    print("[validate_runway_live_smoke_test] Static")
    _static_checks()
    print("\n[validate_runway_live_smoke_test] Unit")
    _unit_browser_probe_schema()
    _unit_failed_probe_safe_fail_report()
    _unit_menu_selection_fallbacks()
    _unit_stale_selector_prefers_text()
    _unit_menu_selection_safe_fail()
    _unit_approval_gated_button_fallbacks()
    _unit_app_menu_aria_fallback()
    _unit_button_click_safe_fail()
    _unit_ui_approval_runtime_bridge()
    _unit_ui_approval_terminal_fallback()
    _unit_starter_image_settings_enforcement()
    _unit_image_prompt_clearing()
    _unit_latest_image_card_selection()
    _unit_used_image_card_cleanup_and_consumed()
    _unit_video_generation_started_reporting()
    _unit_video_toolbar_chip_verification()
    _unit_single_clip_plan()
    _unit_prepare_pauses_live_path()
    _unit_simulated_smoke_rehearsal()
    _unit_manual_ack_engine()
    print("\n[validate_runway_live_smoke_test] All structural checks PASS")
    print("Live CDP smoke: python project_brain/run_runway_live_smoke_test.py --story \"...\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
