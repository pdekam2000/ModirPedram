"""Validate KLING-POST-GENERATION-MODE-RECOVERY — Image→Video recovery before Clip 2."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.kling_frame_continuity_runtime import (  # noqa: E402
    run_kling_frame_continuity_chain,
)
from content_brain.execution.kling_frame_to_video_models import KLING_FRAME_TO_VIDEO_MODE  # noqa: E402
from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content  # noqa: E402
from content_brain.execution.kling_post_generation_mode_recovery import (  # noqa: E402
    RUNTIME_VERSION,
    detect_active_runway_tool_tab,
    recover_video_kling_mode_after_generation,
)
from content_brain.execution.kling_use_frame_runtime import (  # noqa: E402
    CONTINUITY_METHOD_USE_FRAME,
    apply_continuity_for_next_clip,
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


def test_image_mode_detected_after_clip1() -> None:
    page = MagicMock()
    page.evaluate.return_value = "image"
    page.url = "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=image"
    tab = detect_active_runway_tool_tab(page)
    _pass("image_active", tab.get("image_active") is True)
    _pass("active_tab_image", tab.get("active_tab") == "image")


def test_video_tab_recovery_works() -> None:
    page = MagicMock()
    page.evaluate.side_effect = ["image", "video"]
    page.url = "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=image"
    video_tab = _mock_locator(text="Video")
    page.get_by_role.return_value.first = video_tab

    with patch(
        "content_brain.execution.kling_post_generation_mode_recovery.wait_for_video_composer_ready",
        return_value={"ready": True, "generate_visible": True, "prompt_editor_ready": True},
    ), patch(
        "content_brain.execution.kling_post_generation_mode_recovery.resolve_kling_3_pro_provider",
        return_value=(MagicMock(strategy="model_already_selected:text_kling_3_pro"), {"model_already_selected": True}),
    ):
        result = recover_video_kling_mode_after_generation(page)

    _pass("video_tab_clicked", result.get("video_tab_clicked") is True)
    _pass("recovered", result.get("recovered") is True)
    _pass("composer_ready", result.get("composer_ready") is True)


def test_current_model_detection_reused_after_recovery() -> None:
    src = (ROOT / "content_brain/execution/kling_post_generation_mode_recovery.py").read_text(encoding="utf-8")
    _pass("uses_resolve_kling_3_pro_provider", "resolve_kling_3_pro_provider" in src)
    _pass("uses_detect_kling_3_pro_current_model", "detect_kling_3_pro_current_model" in src)
    block = src.split("def recover_video_kling_mode_after_generation", 1)[1].split("\ndef ", 1)[0]
    _pass("recovery_calls_provider_resolver", "resolve_kling_3_pro_provider" in block)


def test_use_frame_sets_continuity_frame_in_ui() -> None:
    page = MagicMock()
    recovery = {
        "recovered": True,
        "provider_strategy": "model_already_selected:text_kling_3_pro",
        "model_already_selected": True,
        "active_tab_before": "image",
        "active_tab_after": "video",
    }
    frame_wait = {"continuity_frame_in_ui": True, "detail": "first frame slot ready"}

    with patch(
        "content_brain.execution.kling_use_frame_runtime.validate_use_frame_availability",
        return_value={"available": True},
    ), patch(
        "content_brain.execution.kling_use_frame_runtime.activate_use_frame",
        return_value={"ok": True, "activated": True, "from_clip_index": 1},
    ), patch(
        "content_brain.execution.kling_post_generation_mode_recovery.recover_video_kling_mode_after_generation",
        return_value=recovery,
    ), patch(
        "content_brain.execution.kling_post_generation_mode_recovery.wait_for_continuity_frame_populated",
        return_value=frame_wait,
    ), patch(
        "content_brain.execution.kling_use_frame_runtime.verify_reference_transferred",
        return_value={"ok": True, "reference_transferred": True},
    ):
        handoff = apply_continuity_for_next_clip(
            page,
            run_dir=tempfile.gettempdir(),
            from_clip_index=1,
            to_clip_index=2,
            video_path="",
        )

    _pass("handoff_ok", handoff.get("ok") is True)
    _pass("continuity_frame_in_ui", handoff.get("continuity_frame_in_ui") is True)
    _pass("use_frame_method", handoff.get("continuity_method") == CONTINUITY_METHOD_USE_FRAME)
    _pass("mode_recovery_attached", bool(handoff.get("mode_recovery")))


def test_clip2_prompt_after_recovery() -> None:
    src = (ROOT / "content_brain/execution/kling_frame_to_video_live_engine.py").read_text(encoding="utf-8")
    _pass("live_engine_post_recovery_step", "post_generation_mode_recovery" in src)
    _pass("clip2_clear_prompt", "clear_first=clip_index > 1" in src)
    block = src.split("if clip_index > 1 or continuity_frame_in_ui:", 1)[1].split("def entry", 1)[0]
    _pass("clip2_recovery_before_provider", "recover_video_kling_mode_after_generation" in block)


def test_generate_not_clicked_in_recovery_modules() -> None:
    recovery_src = (ROOT / "content_brain/execution/kling_post_generation_mode_recovery.py").read_text(encoding="utf-8")
    _pass("recovery_no_generate_click", "generate.locator.click" not in recovery_src)
    _pass("recovery_no_generate_button_click", 'name=re.compile(r"^Generate$"' not in recovery_src)

    use_frame_src = (ROOT / "content_brain/execution/kling_use_frame_runtime.py").read_text(encoding="utf-8")
    handoff_block = use_frame_src.split("def apply_continuity_for_next_clip", 1)[1].split("\ndef record_clip", 1)[0]
    activate_block = use_frame_src.split("def activate_use_frame", 1)[1].split("\ndef verify_reference", 1)[0]
    _pass("handoff_no_generate_click", "generate.locator.click" not in handoff_block)
    _pass("handoff_no_generate_button", 'name=re.compile(r"^Generate$"' not in handoff_block)
    _pass("activate_allows_use_frame_click", ".click" in activate_block)
    _pass("activate_no_generate_button", 'name=re.compile(r"^Generate$"' not in activate_block)


def test_max_generate_clicks_remains_two() -> None:
    chain_src = (ROOT / "content_brain/execution/kling_frame_continuity_runtime.py").read_text(encoding="utf-8")
    _pass("chain_single_live_call_per_clip", chain_src.count("run_kling_frame_to_video_live(") == 1)
    recovery_src = (ROOT / "content_brain/execution/kling_post_generation_mode_recovery.py").read_text(encoding="utf-8")
    _pass("recovery_no_generate_click", "generate.locator.click" not in recovery_src)
    _pass("recovery_no_credit_spend", "credits_spent" not in recovery_src)

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "kling_post_gen_test"
        run_dir.mkdir(parents=True)
        plan = plan_kling_frame_to_video_content(topic="post gen recovery", planned_duration_seconds=30, clip_count=2)
        live_calls: list[dict[str, object]] = []

        def _fake_live(**kwargs: object):
            live_calls.append(dict(kwargs))
            clip_index = int(kwargs.get("clip_index") or 1)
            from content_brain.execution.kling_frame_to_video_live_engine import (
                KlingFrameLiveResult,
                STATUS_COMPLETED,
            )

            return KlingFrameLiveResult(
                ok=True,
                status=STATUS_COMPLETED,
                run_id="kling_post_gen_test",
                provider_mode=KLING_FRAME_TO_VIDEO_MODE,
                dry_run_prepare=False,
                generate_clicked=True,
                credits_spent=True,
                approved_by="validator",
                approved_at="2026-06-03T00:00:00+00:00",
                generation_completed=True,
            )

        handoff_calls = 0

        def _fake_handoff(*args: object, **kwargs: object):
            nonlocal handoff_calls
            handoff_calls += 1
            return {
                "ok": True,
                "used_for_next_clip": True,
                "continuity_method": CONTINUITY_METHOD_USE_FRAME,
                "continuity_frame_in_ui": True,
                "to_clip_index": 2,
                "mode_recovery": {"recovered": True},
            }

        with patch(
            "content_brain.execution.kling_frame_continuity_runtime.run_kling_frame_to_video_live",
            side_effect=_fake_live,
        ), patch(
            "content_brain.execution.kling_frame_continuity_runtime._ensure_frame_mp4",
            side_effect=lambda **kw: ("", dict(kw.get("live_payload") or {})),
        ), patch(
            "content_brain.execution.kling_frame_continuity_runtime._browser_output_ready",
            return_value=(True, "download_button_visible"),
        ), patch(
            "content_brain.execution.kling_frame_continuity_runtime.evaluate_clip_download_gate",
            return_value={
                "generation_success": True,
                "download_success": False,
                "continuity_source_available": True,
                "recovery_needed": True,
                "recovery_available": True,
                "clip_generation_status": "completed",
                "download_status": "failed",
                "browser_output_ready": True,
                "browser_output_detail": "ok",
            },
        ), patch("playwright.sync_api.sync_playwright") as mock_pw:
            browser = MagicMock()
            page = MagicMock()
            browser.contexts = [MagicMock(pages=[page])]
            mock_pw.return_value.start.return_value.chromium.connect_over_cdp.return_value = browser
            with patch(
                "content_brain.execution.kling_frame_continuity_runtime.apply_continuity_for_next_clip",
                side_effect=_fake_handoff,
            ):
                clip_results, _, _, _, _, _ = run_kling_frame_continuity_chain(
                    project_root=tmp,
                    run_id="kling_post_gen_test",
                    run_dir=run_dir,
                    plan=plan,
                    approved_by="validator",
                    confirm_credit_spend=True,
                    starter_frame_path=None,
                    cdp_url="http://127.0.0.1:9222",
                    payload={"approve_all_clips": True},
                )

        generate_clicks = sum(1 for item in clip_results if item.get("generate_clicked"))
        _pass("two_clips_attempted", len(live_calls) == 2)
        _pass("max_two_generate_clicks", generate_clicks <= 2, f"clicks={generate_clicks}")
        _pass("clip2_continuity_flag", live_calls[1].get("continuity_frame_in_ui") is True)
        _pass("handoff_once", handoff_calls == 1)


def main() -> None:
    print("KLING post-generation mode recovery validation")
    print(f"runtime: {RUNTIME_VERSION}")
    test_image_mode_detected_after_clip1()
    test_video_tab_recovery_works()
    test_current_model_detection_reused_after_recovery()
    test_use_frame_sets_continuity_frame_in_ui()
    test_clip2_prompt_after_recovery()
    test_generate_not_clicked_in_recovery_modules()
    test_max_generate_clicks_remains_two()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
