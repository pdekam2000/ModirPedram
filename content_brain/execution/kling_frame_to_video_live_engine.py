"""Kling Frame-to-Video live engine (P4) — approval-gated Generate + CDP download recovery."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_frame_to_video_config import KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS
from content_brain.execution.kling_frame_to_video_live_dry_run import (
    _dismiss_duration_popover,
    _duration_popover_open,
    _ensure_duration_panel,
    _find_runway_generate_page,
    _read_duration_display_value,
    _set_duration_slider_to_max,
)
from content_brain.execution.kling_frame_to_video_locator import locate_frame_control, try_locate_frame_control
from content_brain.execution.kling_multishot_locator import resolve_kling_3_pro_provider
from content_brain.execution.kling_post_generation_mode_recovery import (
    recover_video_kling_mode_after_generation,
)
from content_brain.execution.kling_frame_to_video_map_loader import load_kling_frame_ui_map
from content_brain.execution.kling_frame_to_video_models import (
    KLING_FRAME_PROMPT_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MAX_CHARS,
    KLING_FRAME_PROMPT_TARGET_MIN_CHARS,
    KLING_FRAME_TO_VIDEO_MODE,
)
from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content
from content_brain.execution.kling_real_mp4_download_extractor import verify_extracted_kling_mp4
from content_brain.execution.kling_multishot_live_engine import (
    DOWNLOAD_STATUS_FAILED,
    DOWNLOAD_STATUS_PASSED,
    DOWNLOAD_STATUS_PENDING,
    MIN_REAL_MP4_BYTES,
    PLACEHOLDER_MAX_BYTES,
    STATUS_AWAITING_APPROVAL,
    STATUS_COMPLETED,
    STATUS_DOWNLOAD_FAILED,
    STATUS_FAILED,
    STATUS_PREPARED,
    _detect_output_ready,
    _download_output,
    _probe_video_metadata,
    _wait_for_generation_complete,
    verify_recovered_mp4,
)
from content_brain.execution.kling_starter_frame_generator import (
    kling_frame_clip_dir,
    kling_frame_run_dir,
    load_starter_run_metadata,
    validate_starter_frame_for_upload,
)
from content_brain.execution.runway_continuity_approval_guard import (
    can_execute_dangerous_action,
    grant_continuity_approval,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH

ROOT = Path(__file__).resolve().parents[2]
LIVE_ENGINE_VERSION = "kling_frame_to_video_live_p4_v1"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
OUTPUT_ROOT = ROOT / "outputs" / "kling_frame_to_video"
SCREENSHOT_DIR = ROOT / "project_brain" / "runway_ui_mapping" / "screenshots" / "kling_frame_live_p4"

ESTIMATED_CREDIT_RISK = "Kling 3.0 Pro Frame-to-Video 15s native audio — Runway credits consumed on Generate"

DEFAULT_STARTER_RUN_ID = "kling_ft_20260617T202616_1e37f8a6"
DEFAULT_TOPIC = (
    "A young woman and a wounded robot dog escape through a neon city during heavy rain. "
    "The robot dog limps and makes soft mechanical whimpsers. "
    'The woman whispers: "Stay with me... we\'re almost safe." '
    "Cinematic emotional sci-fi. Native audio."
)


@dataclass
class KlingFrameApprovalChecklist:
    provider_selected: str = ""
    model_already_selected: bool = False
    frame_mode_selected: bool = False
    text_to_video_mode: bool = False
    video_mode_selected: bool = False
    aspect_ratio_applied: bool = False
    aspect_ratio: str = ""
    first_frame_uploaded: bool = False
    first_frame_path: str = ""
    prompt_filled: bool = False
    prompt_chars: int = 0
    duration_seconds: int = 0
    duration_stable_after_dismiss: bool = False
    audio_on: bool = False
    generate_visible: bool = False
    estimated_credit_risk: str = ESTIMATED_CREDIT_RISK

    def all_ready(self) -> bool:
        shared = (
            bool(self.provider_selected)
            and self.prompt_filled
            and self.duration_seconds == KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS
            and self.duration_stable_after_dismiss
            and self.audio_on
            and self.generate_visible
        )
        if self.text_to_video_mode:
            return shared and self.video_mode_selected and self.aspect_ratio_applied
        return shared and self.frame_mode_selected and self.first_frame_uploaded

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_selected": self.provider_selected,
            "model_already_selected": self.model_already_selected,
            "frame_mode_selected": self.frame_mode_selected,
            "text_to_video_mode": self.text_to_video_mode,
            "video_mode_selected": self.video_mode_selected,
            "aspect_ratio_applied": self.aspect_ratio_applied,
            "aspect_ratio": self.aspect_ratio,
            "first_frame_uploaded": self.first_frame_uploaded,
            "first_frame_path": self.first_frame_path,
            "prompt_filled": self.prompt_filled,
            "prompt_chars": self.prompt_chars,
            "duration_seconds": self.duration_seconds,
            "duration_stable_after_dismiss": self.duration_stable_after_dismiss,
            "audio_on": self.audio_on,
            "generate_visible": self.generate_visible,
            "estimated_credit_risk": self.estimated_credit_risk,
            "all_ready": self.all_ready(),
        }


@dataclass
class KlingFrameLiveStep:
    step_id: str
    label: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class KlingFrameLiveResult:
    ok: bool
    status: str
    run_id: str
    provider_mode: str
    dry_run_prepare: bool
    generate_clicked: bool
    credits_spent: bool
    approved_by: str | None
    approved_at: str | None
    generation_completed: bool = False
    output_ready: bool = False
    recovery_available: bool = False
    download_status: str = DOWNLOAD_STATUS_PENDING
    recovery_mode: bool = False
    download_strategies: list[str] = field(default_factory=list)
    approval_checklist: dict[str, Any] = field(default_factory=dict)
    starter_frame_path: str = ""
    frame_prompt: str = ""
    output_path: str = ""
    clip_output_path: str = ""
    root_output_path: str = ""
    duration_seconds: float | None = None
    audio_present: bool | None = None
    native_audio_notes: str = ""
    steps: list[KlingFrameLiveStep] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    locator_strategies: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    page_url: str = ""
    focus_probe: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": LIVE_ENGINE_VERSION,
            "ok": self.ok,
            "status": self.status,
            "run_id": self.run_id,
            "provider_mode": self.provider_mode,
            "dry_run_prepare": self.dry_run_prepare,
            "generate_clicked": self.generate_clicked,
            "credits_spent": self.credits_spent,
            "generation_completed": self.generation_completed,
            "output_ready": self.output_ready,
            "recovery_available": self.recovery_available,
            "download_status": self.download_status,
            "recovery_mode": self.recovery_mode,
            "download_strategies": list(self.download_strategies),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "approval_checklist": dict(self.approval_checklist),
            "starter_frame_path": self.starter_frame_path,
            "frame_prompt": self.frame_prompt,
            "output_path": self.output_path,
            "clip_output_path": self.clip_output_path,
            "root_output_path": self.root_output_path,
            "duration_seconds": self.duration_seconds,
            "audio_present": self.audio_present,
            "native_audio_notes": self.native_audio_notes,
            "steps": [step.to_dict() for step in self.steps],
            "screenshots": list(self.screenshots),
            "locator_strategies": dict(self.locator_strategies),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "page_url": self.page_url,
            "focus_probe": dict(self.focus_probe),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def _build_runway_generate_url(page_url: str) -> str:
    match = re.search(r"(https://app\.runwayml\.com/video-tools/teams/[^/]+)", page_url or "")
    if match:
        return f"{match.group(1)}/ai-tools/generate?tool=video&mode=tools"
    return "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video"


def _ensure_runway_generate_page(browser: Any) -> Any | None:
    page = _find_runway_generate_page(browser)
    if page is None:
        return None
    url = page.url or ""
    if "ai-tools/generate" in url and "mode=tools" in url:
        try:
            from content_brain.execution.runway_focus_dependency_probe import activate_page_for_interaction

            activate_page_for_interaction(page)
        except Exception:
            pass
        return page
    target = _build_runway_generate_url(url)
    page.goto(target, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    if "ai-tools/generate" not in (page.url or ""):
        return None
    try:
        from content_brain.execution.runway_focus_dependency_probe import activate_page_for_interaction

        activate_page_for_interaction(page)
    except Exception:
        pass
    return page


def _record_step(result: KlingFrameLiveResult, step_id: str, label: str, status: str, detail: str = "") -> None:
    result.steps.append(KlingFrameLiveStep(step_id=step_id, label=label, status=status, detail=detail))


def _fail(result: KlingFrameLiveResult, step_id: str, label: str, message: str) -> KlingFrameLiveResult:
    result.ok = False
    if result.status not in {STATUS_DOWNLOAD_FAILED, STATUS_AWAITING_APPROVAL}:
        result.status = STATUS_FAILED
    result.errors.append(message)
    _record_step(result, step_id, label, "failed", message)
    return result


def _capture_screenshot(page: Any, result: KlingFrameLiveResult, step_id: str, label: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = SCREENSHOT_DIR / f"{result.run_id}_{step_id}_{label}_{stamp}.png"
    try:
        session = page.context.new_cdp_session(page)
        shot = session.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        import base64

        path.write_bytes(base64.b64decode(shot["data"]))
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        result.screenshots.append(rel)
        return rel
    except Exception as exc:
        result.warnings.append(f"screenshot_failed:{label}:{exc}")
        return ""


def _locate_or_fail(
    page: Any,
    result: KlingFrameLiveResult,
    step_id: str,
    label: str,
    entry: dict[str, Any],
) -> Any | None:
    try:
        located = locate_frame_control(page, label, entry, timeout_ms=8000)
        result.locator_strategies[label] = located.strategy
        return located
    except RuntimeError as exc:
        return _fail(result, step_id, label, f"Unable to locate {label}: {exc}")


def _read_locator_text(located: Any) -> str:
    try:
        return str(located.locator.inner_text(timeout=3000) or "").strip()
    except Exception:
        return str(located.locator.text_content(timeout=3000) or "").strip()


def _ensure_video_mode(page: Any, result: KlingFrameLiveResult) -> bool:
    for clicker in (
        lambda: page.get_by_text("Video", exact=True).first,
        lambda: page.locator('label:has-text("Video")').first,
    ):
        try:
            clicker().click(timeout=4000, force=True)
            time.sleep(0.35)
            result.locator_strategies["kling_text_to_video_mode"] = "text_video_fallback"
            return True
        except Exception:
            continue
    return False


def _kling_left_panel_scope(page: Any) -> Any:
    for selector in ('[class*="leftPanel"]', '[class*="left-panel"]', '[class*="LeftPanel"]'):
        try:
            panel = page.locator(selector).first
            if panel.count() > 0 and panel.is_visible():
                return panel
        except Exception:
            continue
    for anchor_factory in (
        lambda: page.locator('[contenteditable="true"]').first,
        lambda: page.locator("textarea").first,
        lambda: page.get_by_text("Describe your shot", exact=False).first,
        lambda: page.get_by_text("Describe this shot", exact=False).first,
    ):
        try:
            anchor = anchor_factory()
            if anchor.count() <= 0 or not anchor.is_visible():
                continue
            panel = anchor.locator("xpath=ancestor::*[contains(@class,'panel') or contains(@class,'Panel')][1]")
            if panel.count() > 0 and panel.first.is_visible():
                return panel.first
        except Exception:
            continue
    return page.locator("body")


def _normalize_kling_aspect_display(raw: str) -> str:
    compact = re.sub(r"\s+", "", str(raw or "").strip())
    if compact in {"9:16", "9/16"} or re.search(r"9\s*:\s*16", str(raw or "")):
        return "9:16"
    if compact in {"16:9", "16/9"} or re.search(r"16\s*:\s*9", str(raw or "")):
        return "16:9"
    return ""


def _read_kling_aspect_button_value(locator: Any) -> str:
    text = ""
    try:
        text = str(locator.inner_text(timeout=2000) or "").strip()
    except Exception:
        try:
            text = str(locator.text_content(timeout=2000) or "").strip()
        except Exception:
            text = ""
    detected = _normalize_kling_aspect_display(text)
    if detected:
        return detected
    try:
        aria = str(locator.get_attribute("aria-label") or "").strip()
    except Exception:
        aria = ""
    return _normalize_kling_aspect_display(aria)


def _find_kling_left_panel_aspect_button(
    page: Any,
    result: KlingFrameLiveResult | None = None,
) -> tuple[Any | None, str]:
    panel = _kling_left_panel_scope(page)

    try:
        page_aria_button = page.get_by_role("button", name=re.compile(r"aspect\s*ratio", re.I)).first
        if page_aria_button.count() > 0 and page_aria_button.is_visible():
            panel_aria_visible = False
            try:
                panel_aria_button = panel.get_by_role("button", name=re.compile(r"aspect\s*ratio", re.I)).first
                panel_aria_visible = panel_aria_button.count() > 0 and panel_aria_button.is_visible()
            except Exception:
                panel_aria_visible = False
            if result is not None and not panel_aria_visible:
                result.warnings.append(
                    "aspect_ratio_page_aria_found_outside_left_panel_scope"
                )
            return page_aria_button, "page_aria_aspect_ratio"
    except Exception:
        pass

    try:
        aria_button = panel.get_by_role("button", name=re.compile(r"aspect\s*ratio", re.I)).first
        if aria_button.count() > 0 and aria_button.is_visible():
            return aria_button, "left_panel_aria_aspect_ratio"
    except Exception:
        pass

    for label in ("16:9", "9:16"):
        for scope, prefix in ((panel, "left_panel"), (page, "page")):
            try:
                text_node = scope.get_by_text(label, exact=True).first
                if text_node.count() <= 0 or not text_node.is_visible():
                    continue
                button = text_node.locator("xpath=ancestor-or-self::button[1]")
                if button.count() > 0 and button.first.is_visible():
                    return button.first, f"{prefix}_text_{label.replace(':', '_')}"
            except Exception:
                continue
    return None, ""


def _verify_kling_aspect_chip_text(aspect_button: Any, target: str) -> str:
    detected = _read_kling_aspect_button_value(aspect_button)
    if detected == target:
        return detected
    try:
        chip_text = aspect_button.locator('[class*="selectTriggerText"], span').first
        if chip_text.count() > 0:
            visible = str(chip_text.inner_text(timeout=1500) or "").strip()
            detected = _normalize_kling_aspect_display(visible)
            if detected:
                return detected
    except Exception:
        pass
    return detected


def _click_kling_aspect_option(page: Any, target: str) -> bool:
    option_labels = ("9:16", "9 : 16") if target == "9:16" else ("16:9", "16 : 9")
    scopes = (
        page.locator("[role='listbox']"),
        page.locator("[role='menu']"),
        page.locator("[data-radix-popper-content-wrapper]"),
        page.locator("body"),
    )
    for scope in scopes:
        for label in option_labels:
            for factory in (
                lambda text=label: scope.get_by_role("option", name=text, exact=True),
                lambda text=label: scope.get_by_role("menuitem", name=text, exact=True),
                lambda text=label: scope.get_by_text(text, exact=True),
            ):
                try:
                    option = factory().first
                    if option.count() <= 0 or not option.is_visible():
                        continue
                    option.click(timeout=4000, force=True)
                    return True
                except Exception:
                    continue
    return False


def _apply_video_aspect_ratio(page: Any, aspect_ratio: str, result: KlingFrameLiveResult) -> bool:
    target = str(aspect_ratio or "9:16").strip()
    if target not in {"9:16", "16:9"}:
        target = "9:16"
    try:
        aspect_button, strategy = _find_kling_left_panel_aspect_button(page, result)
        if aspect_button is None:
            raise RuntimeError("left-panel aspect ratio button not found")
        result.locator_strategies["aspect_ratio_menu"] = strategy

        try:
            aspect_button.scroll_into_view_if_needed(timeout=4000)
        except Exception:
            pass

        detected = _verify_kling_aspect_chip_text(aspect_button, target)
        if detected == target:
            result.locator_strategies["aspect_ratio_option"] = "already_set"
            return True

        aspect_button.click(timeout=4000, force=True)
        time.sleep(0.35)
        if not _click_kling_aspect_option(page, target):
            raise RuntimeError(f"aspect ratio option {target} not found in popover")

        time.sleep(0.35)
        verified = _verify_kling_aspect_chip_text(aspect_button, target)
        if verified != target:
            aspect_button, retry_strategy = _find_kling_left_panel_aspect_button(page, result)
            if aspect_button is not None:
                result.locator_strategies["aspect_ratio_menu"] = retry_strategy or strategy
                verified = _verify_kling_aspect_chip_text(aspect_button, target)
        if verified != target:
            raise RuntimeError(f"aspect ratio verification failed: expected {target}, detected {verified!r}")

        result.locator_strategies["aspect_ratio_option"] = target
        return True
    except Exception as exc:
        result.warnings.append(f"aspect_ratio_apply_failed:{exc}")
        return False


def _ensure_frames_mode(page: Any, labels: dict[str, Any], result: KlingFrameLiveResult) -> bool:
    entry = labels.get("kling_frame_to_video_mode") or {}
    located = try_locate_frame_control(page, "kling_frame_to_video_mode", entry, timeout_ms=3000)
    if located:
        try:
            located.locator.click(timeout=4000, force=True)
            time.sleep(0.35)
            result.locator_strategies["kling_frame_to_video_mode"] = located.strategy
            return True
        except Exception:
            pass
    for clicker in (
        lambda: page.get_by_text("Frames", exact=True).first,
        lambda: page.locator('label:has-text("Frames")').first,
    ):
        try:
            clicker().click(timeout=3000, force=True)
            time.sleep(0.35)
            result.locator_strategies["kling_frame_to_video_mode"] = "text_frames_fallback"
            return True
        except Exception:
            continue
    return False


def _upload_first_frame(page: Any, upload: Any, frame_path: Path) -> bool:
    try:
        file_input = page.locator('input[type="file"]').first
        if file_input.count() > 0:
            file_input.set_input_files(str(frame_path))
            return True
    except Exception:
        pass
    try:
        with page.expect_file_chooser(timeout=5000) as fc_info:
            upload.locator.click(timeout=5000)
        fc_info.value.set_files(str(frame_path))
        return True
    except Exception:
        return False


def _apply_duration_15s(page: Any, labels: dict[str, Any], checklist: KlingFrameApprovalChecklist) -> tuple[bool, str]:
    try:
        _set_duration_slider_to_max(page)
        before_text, before_seconds = _read_duration_display_value(page, labels)
        if before_seconds != KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS:
            return False, f"duration before dismiss {before_text}"
        _dismiss_duration_popover(page, labels)
        if _duration_popover_open(page):
            return False, "duration popover still open"
        after_text, after_seconds = _read_duration_display_value(page, labels)
        if after_seconds != KLING_FRAME_TO_VIDEO_TARGET_DURATION_SECONDS:
            return False, f"duration unstable after dismiss {after_text}"
        checklist.duration_seconds = after_seconds or 0
        checklist.duration_stable_after_dismiss = True
        return True, f"stable {after_text}"
    except Exception as exc:
        return False, str(exc)[:160]


def _fill_frame_prompt(
    page: Any,
    entry: dict[str, Any],
    prompt: str,
    *,
    clear_first: bool = False,
) -> bool:
    located = try_locate_frame_control(page, "frame_prompt_box", entry, timeout_ms=5000)
    if located is None:
        return False
    text = prompt.strip()[:KLING_FRAME_PROMPT_MAX_CHARS]
    located.locator.click(timeout=5000)
    if clear_first:
        try:
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.15)
        except Exception:
            pass
    try:
        located.locator.fill(text, timeout=8000)
        return True
    except Exception:
        pass
    try:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(text)
        return True
    except Exception:
        return False


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def resolve_frame_prompt(
    *,
    topic: str = "",
    story_summary: str = "",
    mood: str = "",
    style: str = "",
    characters: list[str] | None = None,
    environment: str = "",
    starter_run_dir: str | Path | None = None,
) -> str:
    meta = load_starter_run_metadata(starter_run_dir) if starter_run_dir else {}
    resolved_topic = _clean(topic or meta.get("topic") or DEFAULT_TOPIC)
    plan = plan_kling_frame_to_video_content(
        topic=resolved_topic,
        story_summary=story_summary or resolved_topic,
        mood=mood,
        style=style,
        characters=characters,
        environment=environment,
        planned_duration_seconds=15,
        clip_count=1,
    )
    prompt = plan.clips[0].prompt.strip()
    prompt = _enrich_frame_prompt_for_live(prompt, topic=resolved_topic)
    if len(prompt) > KLING_FRAME_PROMPT_MAX_CHARS:
        prompt = prompt[: KLING_FRAME_PROMPT_MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return prompt


def _enrich_frame_prompt_for_live(prompt: str, *, topic: str, text_to_video_only: bool = False) -> str:
    """Expand single-clip prompts toward the live target length."""
    enriched = _clean(prompt)
    if len(enriched) >= KLING_FRAME_PROMPT_TARGET_MIN_CHARS:
        return enriched[:KLING_FRAME_PROMPT_MAX_CHARS]

    if text_to_video_only:
        blocks = [
            (
                "Opening cinematic beat: rain streaks, neon reflections on wet pavement, "
                "subtle character micro-movements, emotional eye-line continuity."
            ),
            (
                "Lighting: cinematic teal-magenta neon contrast, volumetric rain, soft rim light, "
                "shallow depth of field, film grain, vertical 9:16 hero framing."
            ),
            (
                "In-scene native audio: heavy rain on metal and glass, distant city hum, "
                "robot dog mechanical whimpers and servo clicks, woman's breathy whispered dialogue intimate and close."
            ),
            (
                "No subtitles, logos, watermarks, or external narration — native Kling in-video audio only."
            ),
            f"Story anchor: {_clean(topic)[:320]}",
        ]
    else:
        blocks = [
            (
                "Motion from uploaded starter frame: rain streaks, neon reflections on wet pavement, "
                "subtle character micro-movements, limping robot dog gait, emotional eye-line continuity."
            ),
            (
                "Lighting: cinematic teal-magenta neon contrast, volumetric rain, soft rim light, "
                "shallow depth of field, film grain, anamorphic emotional sci-fi framing."
            ),
            (
                "In-scene native audio: heavy rain on metal and glass, distant city hum, "
                "robot dog mechanical whimpers and servo clicks, woman's breathy whispered dialogue intimate and close."
            ),
            (
                "Preserve exact wardrobe, scale, and spatial layout from the first-frame upload. "
                "No subtitles, logos, watermarks, or external narration — native Kling in-video audio only."
            ),
            f"Story anchor: {_clean(topic)[:320]}",
        ]
    for block in blocks:
        if len(enriched) >= KLING_FRAME_PROMPT_TARGET_MIN_CHARS:
            break
        candidate = _clean(f"{enriched} {block}")
        if len(candidate) <= KLING_FRAME_PROMPT_TARGET_MAX_CHARS:
            enriched = candidate
        elif len(candidate) <= KLING_FRAME_PROMPT_MAX_CHARS:
            enriched = candidate
    return enriched[:KLING_FRAME_PROMPT_MAX_CHARS]


def _write_outputs(downloaded: Path, run_dir: Path, clip_index: int = 1) -> tuple[Path, Path]:
    clip_dir = kling_frame_clip_dir(run_dir, clip_index)
    clip_dest = clip_dir / "video.mp4"
    root_dest = run_dir / "video.mp4"
    if downloaded.resolve() != clip_dest.resolve():
        shutil.copy2(downloaded, clip_dest)
    if clip_index == 1 and root_dest.resolve() != clip_dest.resolve():
        shutil.copy2(clip_dest, root_dest)
    return clip_dest, root_dest


def run_kling_frame_to_video_live(
    *,
    starter_frame_path: str | Path | None = None,
    frame_prompt: str = "",
    topic: str = "",
    run_id: str = "",
    clip_index: int = 1,
    aspect_ratio: str = "9:16",
    approve_generate: bool = False,
    approved_by: str = "",
    confirm_credit_spend: bool = False,
    cdp_url: str = DEFAULT_CDP_URL,
    map_path: Path | str | None = None,
    max_wait_minutes: int = 25,
    continuity_frame_in_ui: bool = False,
    prior_artifact_signatures: list[dict[str, Any]] | None = None,
    require_new_artifact: bool = False,
) -> KlingFrameLiveResult:
    clip_index = max(1, int(clip_index))
    text_to_video_only = clip_index <= 1 and not starter_frame_path and not continuity_frame_in_ui
    frame_path = Path(starter_frame_path).resolve() if starter_frame_path else None
    run_id = run_id or (
        frame_path.parent.parent.name
        if frame_path is not None and frame_path.parent.name == "starter_frame"
        else DEFAULT_STARTER_RUN_ID
    )
    run_dir = kling_frame_run_dir(ROOT, run_id)
    starter_run_dir = (
        frame_path.parent.parent
        if frame_path is not None and frame_path.parent.name == "starter_frame"
        else run_dir
    )
    meta = load_starter_run_metadata(starter_run_dir)
    resolved_topic = _clean(topic or meta.get("topic") or DEFAULT_TOPIC)
    starter_image_prompt = _clean(meta.get("starter_image_prompt") or "")
    prompt = _clean(frame_prompt) or resolve_frame_prompt(
        topic=resolved_topic,
        starter_run_dir=starter_run_dir,
    )
    prompt = _enrich_frame_prompt_for_live(prompt, topic=resolved_topic, text_to_video_only=text_to_video_only)

    if len(prompt) > KLING_FRAME_PROMPT_MAX_CHARS:
        raise ValueError(f"frame_prompt exceeds {KLING_FRAME_PROMPT_MAX_CHARS} chars")

    if not text_to_video_only and not continuity_frame_in_ui:
        if frame_path is None or not frame_path.is_file():
            raise ValueError("starter_frame_path required for clip 2+ frame continuity")
        frame_ok, _, frame_errors = validate_starter_frame_for_upload(
            frame_path=frame_path,
            topic=resolved_topic,
            starter_image_prompt=starter_image_prompt or prompt[:600],
        )
        if not frame_ok:
            raise ValueError("; ".join(frame_errors))

    resolved_aspect = str(aspect_ratio or "9:16").strip()
    if resolved_aspect not in {"9:16", "16:9"}:
        resolved_aspect = "9:16"

    result = KlingFrameLiveResult(
        ok=False,
        status=STATUS_PREPARED,
        run_id=run_id,
        provider_mode=KLING_FRAME_TO_VIDEO_MODE,
        dry_run_prepare=not approve_generate,
        generate_clicked=False,
        credits_spent=False,
        approved_by=None,
        approved_at=None,
        starter_frame_path=str(frame_path).replace("\\", "/") if frame_path else "",
        frame_prompt=prompt,
        native_audio_notes="Audio ON in UI; native audio verified post-download via ffprobe",
    )

    ui_map = load_kling_frame_ui_map(map_path=map_path or DEFAULT_MAP_PATH)
    labels = dict(ui_map.get("labels") or {})
    checklist = KlingFrameApprovalChecklist()
    playwright = None

    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        _record_step(result, "01", "cdp", "passed", cdp_url)

        page = _ensure_runway_generate_page(browser)
        if page is None:
            return _fail(result, "01", "runway_tab", "No Runway generate tab found")
        if "ai-tools/generate" not in (page.url or ""):
            return _fail(result, "01", "runway_tab", f"Not on generate page: {page.url[:120]}")

        result.page_url = page.url
        _record_step(result, "01", "runway_tab", "passed", page.url[:120])
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        except Exception:
            pass
        time.sleep(1.5)

        if clip_index > 1 or continuity_frame_in_ui:
            mode_recovery = recover_video_kling_mode_after_generation(page, map_path=map_path or DEFAULT_MAP_PATH)
            result.locator_strategies["post_generation_mode_recovery"] = str(
                mode_recovery.get("provider_strategy") or mode_recovery.get("detail") or ""
            )
            if not mode_recovery.get("recovered"):
                return _fail(
                    result,
                    "01",
                    "post_generation_mode_recovery",
                    str(mode_recovery.get("detail") or "Video/Kling mode recovery failed before clip 2"),
                )
            _record_step(
                result,
                "01",
                "post_generation_mode_recovery",
                "passed",
                (
                    f"tab={mode_recovery.get('active_tab_before')}→{mode_recovery.get('active_tab_after')}; "
                    f"model_already_selected={mode_recovery.get('model_already_selected')}"
                ),
            )

        def entry(label: str) -> dict[str, Any]:
            raw = labels.get(label)
            if not isinstance(raw, dict):
                raise RuntimeError(f"Missing map entry for {label}")
            return raw

        provider_entry = labels.get("provider_kling_3_pro") or {}
        try:
            provider, model_detection = resolve_kling_3_pro_provider(page, provider_entry)
            result.locator_strategies["provider_kling_3_pro"] = provider.strategy
            checklist.model_already_selected = bool(model_detection.get("model_already_selected"))
            if checklist.model_already_selected:
                provider_text = str(model_detection.get("detected_text") or "Kling 3.0 Pro")
                step_detail = f"model_already_selected={checklist.model_already_selected}; {provider_text[:48]}"
            else:
                provider_text = _read_locator_text(provider)
                if "kling 3" not in provider_text.lower():
                    provider.locator.click(timeout=8000, force=True)
                    time.sleep(0.35)
                    provider_text = _read_locator_text(provider) or "Kling 3.0 Pro"
                step_detail = provider_text[:60]
        except RuntimeError as exc:
            return _fail(result, "02", "provider_kling_3_pro", f"Kling 3.0 Pro not found: {exc}")
        checklist.provider_selected = provider_text
        _record_step(result, "02", "provider_kling_3_pro", "passed", step_detail)

        if text_to_video_only:
            checklist.text_to_video_mode = True
            checklist.video_mode_selected = _ensure_video_mode(page, result)
            if not checklist.video_mode_selected:
                return _fail(result, "03", "kling_text_to_video_mode", "Video mode not selected")
            _record_step(result, "03", "kling_text_to_video_mode", "passed", "Video mode active")
            _capture_screenshot(page, result, "03", "video_mode_selected")

            checklist.aspect_ratio = resolved_aspect
            checklist.aspect_ratio_applied = _apply_video_aspect_ratio(page, resolved_aspect, result)
            if not checklist.aspect_ratio_applied:
                return _fail(result, "04", "aspect_ratio_menu", f"Could not set aspect ratio {resolved_aspect}")
            _record_step(result, "04", "aspect_ratio_menu", "passed", resolved_aspect)
            _capture_screenshot(page, result, "04", "aspect_ratio_applied")
        else:
            checklist.frame_mode_selected = _ensure_frames_mode(page, labels, result)
            if not checklist.frame_mode_selected:
                return _fail(result, "03", "kling_frame_to_video_mode", "Frames mode not selected")
            _record_step(result, "03", "kling_frame_to_video_mode", "passed", "Frames mode active")
            _capture_screenshot(page, result, "03", "frame_mode_selected")

            if continuity_frame_in_ui:
                checklist.first_frame_uploaded = True
                checklist.first_frame_path = "browser_continuity"
                _record_step(result, "04", "first_frame_upload", "passed", "continuity_frame_in_ui")
                _capture_screenshot(page, result, "04", "continuity_frame_in_ui")
            else:
                upload = _locate_or_fail(page, result, "04", "first_frame_upload", entry("first_frame_upload"))
                if upload is None:
                    return result
                if frame_path is None or not _upload_first_frame(page, upload, frame_path):
                    return _fail(result, "04", "first_frame_upload", f"Could not upload {frame_path}")
                checklist.first_frame_uploaded = True
                checklist.first_frame_path = str(frame_path)
                _record_step(result, "04", "first_frame_upload", "passed", str(frame_path))
                _capture_screenshot(page, result, "04", "first_frame_uploaded")

            checklist.aspect_ratio = resolved_aspect
            checklist.aspect_ratio_applied = _apply_video_aspect_ratio(page, resolved_aspect, result)
            if not checklist.aspect_ratio_applied:
                result.warnings.append(f"aspect_ratio_preserve_failed:{resolved_aspect}")
            else:
                _record_step(result, "04b", "aspect_ratio_menu", "passed", resolved_aspect)

        if not _fill_frame_prompt(
            page,
            entry("frame_prompt_box"),
            prompt,
            clear_first=clip_index > 1,
        ):
            return _fail(result, "05", "frame_prompt_box", "Could not fill frame prompt")
        checklist.prompt_filled = True
        checklist.prompt_chars = len(prompt)
        _record_step(result, "05", "frame_prompt_box", "passed", f"{checklist.prompt_chars} chars")
        _capture_screenshot(page, result, "05", "prompt_filled")

        duration_ok, duration_detail = _apply_duration_15s(page, labels, checklist)
        if not duration_ok:
            return _fail(result, "06", "duration_slider_15s", duration_detail)
        _record_step(result, "06", "duration_slider_15s", "passed", duration_detail)
        _capture_screenshot(page, result, "06", "duration_after_15s")

        audio = _locate_or_fail(page, result, "07", "audio_toggle_on", entry("audio_toggle_on"))
        if audio is None:
            return result
        audio_text = _read_locator_text(audio).lower()
        panel_text = ""
        try:
            panel_text = page.locator('[class*="left-panel"]').first.inner_text(timeout=3000).lower()
        except Exception:
            pass
        checklist.audio_on = "on" in audio_text or ("on" in panel_text and "off" in panel_text)
        if not checklist.audio_on:
            return _fail(result, "07", "audio_toggle_on", f"Audio not ON ({audio_text!r})")
        _record_step(result, "07", "audio_toggle_on", "passed", "on")
        _capture_screenshot(page, result, "07", "audio_on")

        generate = _locate_or_fail(page, result, "08", "generate_button", entry("generate_button"))
        if generate is None:
            return result
        checklist.generate_visible = True
        _record_step(result, "08", "generate_button", "visible", "not clicked yet")

        result.approval_checklist = checklist.to_dict()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "approval_checklist.json").write_text(json.dumps(checklist.to_dict(), indent=2), encoding="utf-8")
        (run_dir / "frame_prompt.txt").write_text(prompt, encoding="utf-8")
        _capture_screenshot(page, result, "09", "approval_gate")

        if not checklist.all_ready():
            return _fail(result, "09", "approval_checklist", "Checklist incomplete")

        if not approve_generate:
            result.ok = True
            result.status = STATUS_AWAITING_APPROVAL
            result.recovery_available = False
            _record_step(result, "10", "generate_button", "blocked", "awaiting explicit approval flags")
            (run_dir / "live_run_prepare.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
            return result

        if not approved_by.strip():
            result.ok = True
            result.status = STATUS_AWAITING_APPROVAL
            result.recovery_available = False
            _record_step(result, "10", "generate_button", "blocked", "awaiting approved_by")
            (run_dir / "live_run_prepare.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
            return result
        if not confirm_credit_spend:
            result.ok = True
            result.status = STATUS_AWAITING_APPROVAL
            result.recovery_available = False
            _record_step(result, "10", "generate_button", "blocked", "awaiting confirm_credit_spend")
            (run_dir / "live_run_prepare.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
            return result

        approvals = grant_continuity_approval(
            control_key="generate_button",
            step_id="11_generate",
            approved_by=approved_by.strip(),
            reason="explicit operator approval — Kling frame-to-video live P4",
        )
        if not can_execute_dangerous_action("generate_button", step_id="11_generate", approvals=approvals):
            return _fail(result, "11", "generate_button", "Approval gate rejected Generate")

        result.approved_by = approved_by.strip()
        result.approved_at = approvals["generate_button"].approved_at
        from content_brain.execution.runway_focus_dependency_probe import execute_generate_click_with_focus_probe

        gate_context = None
        if require_new_artifact or (clip_index > 1 and prior_artifact_signatures):
            from content_brain.execution.kling_useframe_generation_completion_gate import (
                GenerationCompletionGateContext,
                capture_artifact_signatures,
                wait_for_generation_completion_gate,
            )

            prior_sigs = list(prior_artifact_signatures or [])
            _, baseline_meta = capture_artifact_signatures(page, run_id=run_id)
            gate_context = GenerationCompletionGateContext(
                require_new_artifact=True,
                generate_clicked_at="",
                prior_artifact_signatures=prior_sigs,
                baseline_video_card_count=int(baseline_meta.get("video_card_count") or 0),
                baseline_card_fingerprints=list(baseline_meta.get("fingerprints") or []),
            )
            (kling_frame_clip_dir(run_dir, clip_index) / "generation_completion_gate_context_pre.json").write_text(
                json.dumps(gate_context.to_dict(), indent=2),
                encoding="utf-8",
            )

        probe = execute_generate_click_with_focus_probe(page, generate.locator)
        result.focus_probe = probe.to_dict()
        if probe.click_error:
            return _fail(result, "11", "generate_button", probe.click_error)
        result.generate_clicked = True
        result.credits_spent = True
        _record_step(
            result,
            "11",
            "generate_button",
            "clicked",
            (
                f"approved_by={result.approved_by}; "
                f"visibility={probe.before.get('visibility_state')}; "
                f"hasFocus={probe.before.get('has_focus')}; "
                f"focus_blocker={probe.focus_likely_blocker}; "
                f"click_ms={probe.click_duration_ms}"
            ),
        )
        _capture_screenshot(page, result, "11", "generate_clicked")

        if gate_context is not None:
            from content_brain.execution.kling_useframe_generation_completion_gate import (
                wait_for_generation_completion_gate,
            )

            generate_clicked_at = str(
                (result.focus_probe or {}).get("click_finished_at") or datetime.now(timezone.utc).isoformat()
            )
            gate_context.generate_clicked_at = generate_clicked_at
            (kling_frame_clip_dir(run_dir, clip_index) / "generation_completion_gate_context.json").write_text(
                json.dumps(gate_context.to_dict(), indent=2),
                encoding="utf-8",
            )
            gate_result = wait_for_generation_completion_gate(
                page,
                generate_clicked_at=generate_clicked_at,
                prior_artifact_signatures=gate_context.prior_artifact_signatures,
                baseline_video_card_count=gate_context.baseline_video_card_count,
                baseline_card_fingerprints=gate_context.baseline_card_fingerprints,
                max_wait_seconds=max_wait_minutes * 60,
            )
            (kling_frame_clip_dir(run_dir, clip_index) / "generation_completion_gate_result.json").write_text(
                json.dumps(gate_result.to_dict(), indent=2),
                encoding="utf-8",
            )
            if not gate_result.gate_passed:
                result.generation_completed = False
                result.recovery_available = True
                return _fail(
                    result,
                    "12",
                    "generation_completion_gate",
                    f"New artifact gate failed: {gate_result.detail}",
                )
            result.generation_completed = True
            _record_step(result, "12", "generation_wait", "passed", gate_result.detail)
            _record_step(result, "12b", "generation_completion_gate", "passed", gate_result.detail)
            _capture_screenshot(page, result, "12", "generation_complete")
        else:
            complete, reason = _wait_for_generation_complete(page, max_wait_minutes=max_wait_minutes)
            if not complete:
                result.generation_completed = False
                result.recovery_available = True
                return _fail(result, "12", "generation_wait", f"Generation did not complete: {reason}")
            result.generation_completed = True
            _record_step(result, "12", "generation_wait", "passed", reason)
            _capture_screenshot(page, result, "12", "generation_complete")

        clip_dir = kling_frame_clip_dir(run_dir, clip_index)
        downloaded, download_strategies = _download_output(
            page,
            clip_dir,
            run_id,
            clip_index=clip_index,
            gate_context=gate_context,
        )
        result.download_strategies = list(download_strategies)
        if downloaded is None:
            result.generation_completed = True
            result.output_ready = False
            result.recovery_available = True
            result.download_status = DOWNLOAD_STATUS_FAILED
            result.status = STATUS_DOWNLOAD_FAILED
            (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
            return _fail(result, "13", "download", "Could not download real MP4 after recovery polling")

        verify = verify_extracted_kling_mp4(downloaded)
        if not verify.get("is_real_mp4"):
            result.generation_completed = True
            result.output_ready = False
            result.recovery_available = True
            result.download_status = DOWNLOAD_STATUS_FAILED
            result.status = STATUS_DOWNLOAD_FAILED
            (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
            return _fail(result, "13", "download", "Downloaded file is not a real MP4 (>1MB, ffprobe)")

        clip_dest, root_dest = _write_outputs(downloaded, run_dir, clip_index)
        result.clip_output_path = str(clip_dest.resolve()).replace("\\", "/")
        result.root_output_path = str(root_dest.resolve()).replace("\\", "/")
        result.output_path = result.clip_output_path
        result.download_path = result.clip_output_path
        result.download_status = DOWNLOAD_STATUS_PASSED
        result.output_ready = True
        result.recovery_available = False

        duration, audio_present, notes = _probe_video_metadata(clip_dest)
        result.duration_seconds = duration
        result.audio_present = audio_present
        result.native_audio_notes = notes

        metadata = {
            "run_id": run_id,
            "approved_by": result.approved_by,
            "approved_at": result.approved_at,
            "starter_frame_path": result.starter_frame_path,
            "frame_prompt_chars": len(prompt),
            "generate_clicked": True,
            "clip_output_path": result.clip_output_path,
            "root_output_path": result.root_output_path,
            "duration_seconds": duration,
            "audio_present": audio_present,
            "verify": verify,
        }
        (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        result.ok = True
        result.status = STATUS_COMPLETED
        result.dry_run_prepare = False
        (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result

    except Exception as exc:
        result.ok = False
        result.status = STATUS_FAILED
        result.errors.append(str(exc))
        _record_step(result, "99", "runtime", "failed", str(exc)[:300])
        return result
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


def recover_kling_frame_output(
    *,
    run_id: str,
    cdp_url: str = DEFAULT_CDP_URL,
    clip_index: int = 1,
    gate_context: Any | None = None,
) -> KlingFrameLiveResult:
    run_dir = kling_frame_run_dir(ROOT, run_id)
    clip_dir = kling_frame_clip_dir(run_dir, clip_index)
    result = KlingFrameLiveResult(
        ok=False,
        status=STATUS_FAILED,
        run_id=run_id,
        provider_mode=KLING_FRAME_TO_VIDEO_MODE,
        dry_run_prepare=False,
        generate_clicked=False,
        credits_spent=False,
        recovery_mode=True,
        generation_completed=False,
        output_ready=False,
        recovery_available=True,
        download_status=DOWNLOAD_STATUS_PENDING,
        approved_by=None,
        approved_at=None,
        native_audio_notes="Recovery mode — no new credits spent",
    )
    playwright = None
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10000)
        page = _ensure_runway_generate_page(browser)
        if page is None:
            return _fail(result, "recover", "runway_tab", "No Runway tab found")
        ready, reason = _detect_output_ready(page)
        result.generation_completed = ready
        from content_brain.execution.kling_real_mp4_download_extractor import (
            poll_extract_real_kling_mp4,
            verify_extracted_kling_mp4,
        )

        clip_dest_path = clip_dir / f"clip_{clip_index}.mp4"
        extracted = poll_extract_real_kling_mp4(
            page,
            clip_dest_path,
            run_id=run_id,
            clip_index=clip_index,
            clip_dir=clip_dir,
            recovery_mode=True,
            gate_context=gate_context,
        )
        result.download_strategies = list(extracted.attempted_methods)
        if not ready:
            result.warnings.append(f"output_detect_before_poll:{reason}")
        if not extracted.ok:
            result.status = STATUS_DOWNLOAD_FAILED
            result.download_status = DOWNLOAD_STATUS_FAILED
            return _fail(result, "recover", "download", "Recovery polling exhausted — no valid MP4")
        downloaded = Path(extracted.output_path)
        verify = verify_extracted_kling_mp4(downloaded)
        if not verify.get("is_real_mp4"):
            result.status = STATUS_DOWNLOAD_FAILED
            result.download_status = DOWNLOAD_STATUS_FAILED
            return _fail(result, "recover", "verify", "Recovered file is not a real MP4")
        result.generation_completed = True
        clip_dest = clip_dir / "video.mp4"
        if downloaded.resolve() != clip_dest.resolve():
            shutil.copy2(downloaded, clip_dest)
        root_dest = run_dir / "video.mp4"
        if root_dest.resolve() != clip_dest.resolve():
            shutil.copy2(clip_dest, root_dest)
        result.clip_output_path = str(clip_dest).replace("\\", "/")
        result.root_output_path = str(root_dest).replace("\\", "/")
        result.output_path = result.clip_output_path
        duration, audio_present, notes = _probe_video_metadata(clip_dest)
        result.duration_seconds = duration
        result.audio_present = audio_present
        result.native_audio_notes = notes
        result.ok = True
        result.status = STATUS_COMPLETED
        result.output_ready = True
        result.recovery_available = False
        result.download_status = DOWNLOAD_STATUS_PASSED
        (run_dir / "live_run_result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result
    except Exception as exc:
        return _fail(result, "recover", "runtime", str(exc)[:200])
    finally:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass


__all__ = [
    "DEFAULT_STARTER_RUN_ID",
    "KlingFrameLiveResult",
    "LIVE_ENGINE_VERSION",
    "recover_kling_frame_output",
    "resolve_frame_prompt",
    "run_kling_frame_to_video_live",
    "verify_recovered_mp4",
]
