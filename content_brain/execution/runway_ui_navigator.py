"""
Phase RUNWAY-STARTER-TO-VIDEO-E — mapped Runway UI navigator (no provider mutation).

Uses operator-mapped selectors from runway_ui_map.json. Dangerous controls require approval.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from content_brain.execution.runway_image_generation_config import (
    IMAGE_ASPECT_MENU_KEY,
    IMAGE_COUNT_MENU_KEY,
    IMAGE_QUALITY_MENU_KEY,
    image_aspect_control_key,
    image_count_control_key,
    image_quality_control_key,
    menu_option_texts_for_image_count,
    menu_option_texts_for_image_quality,
)
from content_brain.execution.runway_continuity_approval_guard import (
    can_execute_dangerous_action,
    dangerous_action_block_reason,
    is_approval_gated_control,
)
from content_brain.execution.runway_continuity_models import RunwayContinuityApprovalRecord, RunwayContinuityPlan
from content_brain.execution.runway_phase_i_artifact_tracker import (
    DOWNLOAD_LABELS,
    PhaseIArtifactCard,
    PhaseIArtifactTracker,
    ROLE_STARTER_IMAGE,
    USE_FRAME_LABELS,
)
from content_brain.execution.runway_phase_i_cdp_download import (
    ClipDownloadAttempt,
    RunwayPhaseICdpDownloadConfig,
    RunwayPhaseICdpDownloader,
    default_runway_download_dir,
)
from content_brain.execution.runway_ui_map_loader import (
    DEFAULT_MAP_PATH,
    ResolvedControl,
    RunwayUIMapSnapshot,
    resolve_runway_ui_controls,
    selector_is_weak,
)

DEFAULT_PREP_TIMEOUT_MS = 30_000
DEFAULT_COMPLETION_POLL_SECONDS = 45.0
DEFAULT_MENU_OPEN_SETTLE_SECONDS = 0.45
DEFAULT_MENU_OPTION_TIMEOUT_MS = 8_000
CHIP_POPOVER_OPEN_DELAY_MS = 1000
CHIP_OPTION_HOVER_DELAY_MS = 400
CHIP_AFTER_CLICK_VERIFY_DELAY_MS = 700
CHIP_READBACK_SETTLE_MS = 650
CHIP_VERIFY_RETRY_DELAY_MS = 500
CHIP_VERIFY_MAX_RETRIES = 3

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE_QUALITY_CHIP_DIAGNOSTICS = (
    ROOT / "project_brain" / "runway_phase_i_image_quality_chip_diagnostics.json"
)

ScreenshotFn = Callable[[str], None]

BUTTON_CLICK_TEXTS: dict[str, tuple[str, ...]] = {
    "image_generate_button": ("Generate", "Generate Image"),
    "generate_button": ("Generate",),
    "download_mp4_button": ("Download MP4", "Download", "DOWNLOAD MP4", "MP4"),
    "image_app_menu_button": ("Actions",),
    "image_use_to_video_option": ("Use to Video", "Use in video"),
    "use_frame_button": ("Use Frame", "USE FRAME"),
    "remove_image": ("Remove image", "Remove Image", "REMOVE IMAGE"),
    "image_card_remove_button": ("Hide output", "Hide Output"),
}

USE_FOR_VIDEO_ACTION_LABELS: tuple[str, ...] = (
    "Use for Video",
    "Use to Video",
    "Use in video",
    "Use image",
    "Image to Video",
    "Apply",
    "Create Video",
    "Video",
)

UNSAFE_UI_TEXT_PATTERN = (
    "delete account",
    "remove account",
    "sign out",
    "log out",
    "logout",
    "billing",
    "upgrade plan",
    "delete project",
    "discard project",
)

MENU_OPTION_TEXTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("image_aspect_ratio_menu", "image_aspect_ratio_9_16"): (
        "9:16",
        "9 : 16",
        "9: 16",
        "9 / 16",
    ),
    ("image_quality_menu", "image_quality_1k"): ("1K", "1k", "1 K"),
    ("image_quality_menu", "image_quality_2k"): ("2K", "2k", "2 K"),
    ("image_quality_menu", "image_quality_4k"): ("4K", "4k", "4 K"),
    ("image_count_menu", "image_count_1"): ("1",),
    ("image_count_menu", "image_count_4"): ("4",),
    ("duration_menu", "duration_10s"): ("10s", "10S", "10 s", "10 seconds"),
    ("aspect_ratio_menu", "aspect_ratio_9_16"): (
        "9:16",
        "9 : 16",
        "9: 16",
        "9 / 16",
    ),
}

TOOLBAR_MENU_PATTERNS: dict[str, tuple[str, ...]] = {
    "image_aspect_ratio_menu": ("9:16", "16:9", "1:1", "4:3", "3:4"),
    "image_quality_menu": ("4K", "2K", "1K", "4k", "2k", "1k"),
    "image_count_menu": ("4", "1"),
    "aspect_ratio_menu": ("9:16", "16:9", "1:1", "4:3", "3:4"),
    "duration_menu": ("10s", "5s", "10S", "5S", "10 s", "5 s", "10 seconds", "5 seconds"),
}

VIDEO_ASPECT_MENU_KEY = "aspect_ratio_menu"
VIDEO_DURATION_MENU_KEY = "duration_menu"

IMAGE_TOOLBAR_CHIP_MENU_KEYS: frozenset[str] = frozenset(
    {
        IMAGE_COUNT_MENU_KEY,
        IMAGE_ASPECT_MENU_KEY,
        IMAGE_QUALITY_MENU_KEY,
    }
)

VIDEO_TOOLBAR_CHIP_MENU_KEYS: frozenset[str] = frozenset(
    {
        VIDEO_ASPECT_MENU_KEY,
        VIDEO_DURATION_MENU_KEY,
    }
)

TOOLBAR_CHIP_MENU_KEYS: frozenset[str] = IMAGE_TOOLBAR_CHIP_MENU_KEYS | VIDEO_TOOLBAR_CHIP_MENU_KEYS

TOOLBAR_CHIP_KIND_BY_MENU: dict[str, str] = {
    IMAGE_COUNT_MENU_KEY: "count",
    IMAGE_ASPECT_MENU_KEY: "aspect",
    IMAGE_QUALITY_MENU_KEY: "quality",
    VIDEO_ASPECT_MENU_KEY: "aspect",
    VIDEO_DURATION_MENU_KEY: "duration",
}

MENU_KEY_BY_CHIP_KIND: dict[str, str] = {
    value: key for key, value in TOOLBAR_CHIP_KIND_BY_MENU.items()
}


@dataclass
class StarterImagePrecleanState:
    preclean_attempted: bool = False
    stale_image_preview_detected: bool = False
    stale_preview_closed: bool = False
    preclean_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preclean_attempted": self.preclean_attempted,
            "stale_image_preview_detected": self.stale_image_preview_detected,
            "stale_preview_closed": self.stale_preview_closed,
            "preclean_notes": list(self.preclean_notes),
        }


@dataclass
class StarterImageSettingsState:
    detected_aspect_ratio: str = ""
    detected_image_count: str = ""
    detected_image_quality: str = ""
    settings_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected_aspect_ratio": self.detected_aspect_ratio,
            "detected_image_count": self.detected_image_count,
            "detected_image_quality": self.detected_image_quality,
            "settings_verified": self.settings_verified,
        }


@dataclass
class ImageToolbarChipCandidate:
    kind: str = ""
    text: str = ""
    active: bool = False
    in_toolbar: bool = False
    is_button: bool = False
    bbox: dict[str, float] = field(default_factory=dict)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "active": self.active,
            "in_toolbar": self.in_toolbar,
            "is_button": self.is_button,
            "bbox": dict(self.bbox),
            "score": self.score,
        }


@dataclass
class ImageToolbarChipReadback:
    chip_kind: str = ""
    toolbar_container_selector: str = ""
    toolbar_found: bool = False
    active_chip: ImageToolbarChipCandidate | None = None
    picked_text: str = ""
    all_candidates: list[ImageToolbarChipCandidate] = field(default_factory=list)
    screenshot_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chip_kind": self.chip_kind,
            "toolbar_container_selector": self.toolbar_container_selector,
            "toolbar_found": self.toolbar_found,
            "active_chip": self.active_chip.to_dict() if self.active_chip else {},
            "picked_text": self.picked_text,
            "all_candidates": [item.to_dict() for item in self.all_candidates],
            "screenshot_path": self.screenshot_path,
        }


@dataclass
class PromptClearResult:
    image_prompt_cleared: bool = False
    prompt_text_before_clear: str = ""
    prompt_text_after_clear: str = ""
    control_key: str = "image_prompt_input"

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_prompt_cleared": self.image_prompt_cleared,
            "prompt_text_before_clear": self.prompt_text_before_clear,
            "prompt_text_after_clear": self.prompt_text_after_clear,
            "control_key": self.control_key,
        }


@dataclass
class VideoToolbarSettingsState:
    detected_aspect_ratio: str = ""
    detected_duration: str = ""
    video_settings_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected_aspect_ratio": self.detected_aspect_ratio,
            "detected_duration": self.detected_duration,
            "video_settings_verified": self.video_settings_verified,
        }


@dataclass
class GenerationImageCardSnapshot:
    card_count: int = 0
    fingerprints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_count": self.card_count,
            "fingerprints": list(self.fingerprints),
        }


@dataclass
class LatestGeneratedImageCardState:
    latest_image_card_found: bool = False
    latest_image_card_index: int = -1
    selected_image_card_fingerprint: str = ""
    card_prompt_text: str = ""
    card_bounding_box: dict[str, float] = field(default_factory=dict)
    app_menu_available: bool = False
    use_to_video_available: bool = False
    use_for_video_action_used: str = ""
    use_for_video_candidates: list[str] = field(default_factory=list)
    video_transition_verified: bool = False
    current_url_after_transition: str = ""
    selection_reason: str = ""
    pre_generate_card_count: int = 0
    new_card_candidates_count: int = 0
    used_image_card_removed: bool = False
    used_image_card_marked_consumed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest_image_card_found": self.latest_image_card_found,
            "latest_image_card_index": self.latest_image_card_index,
            "selected_image_card_fingerprint": self.selected_image_card_fingerprint,
            "selected_image_card_index": self.latest_image_card_index,
            "card_prompt_text": self.card_prompt_text,
            "card_bounding_box": dict(self.card_bounding_box),
            "app_menu_available": self.app_menu_available,
            "use_to_video_available": self.use_to_video_available,
            "use_for_video_action_used": self.use_for_video_action_used,
            "use_for_video_candidates": list(self.use_for_video_candidates),
            "video_transition_verified": self.video_transition_verified,
            "current_url_after_transition": self.current_url_after_transition,
            "selection_reason": self.selection_reason,
            "pre_generate_card_count": self.pre_generate_card_count,
            "new_card_candidates_count": self.new_card_candidates_count,
            "used_image_card_removed": self.used_image_card_removed,
            "used_image_card_marked_consumed": self.used_image_card_marked_consumed,
        }


@dataclass
class VideoGenerationProgressState:
    in_progress: bool = False
    spinner_visible: bool = False
    stop_cancel_visible: bool = False
    progress_text: str = ""
    output_cards_detected: int = 0
    output_loading: bool = False
    generate_button_disabled: bool = False
    pending_output_slot: bool = False
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "in_progress": self.in_progress,
            "spinner_visible": self.spinner_visible,
            "stop_cancel_visible": self.stop_cancel_visible,
            "progress_text": self.progress_text,
            "output_cards_detected": self.output_cards_detected,
            "output_loading": self.output_loading,
            "generate_button_disabled": self.generate_button_disabled,
            "pending_output_slot": self.pending_output_slot,
            "signals": list(self.signals),
        }


@dataclass
class PromptEditorReadyState:
    clip_index: int = 0
    checked: bool = False
    ready: bool = False
    ready_result: str = ""
    selector_used: str = ""
    prompt_candidates: list[dict[str, Any]] = field(default_factory=list)
    modal_detected: bool = False
    generate_button_visible: bool = False
    use_frame_button_visible: bool = False
    download_button_visible: bool = False
    generation_in_progress: bool = False
    generation_state: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_index": self.clip_index,
            "checked": self.checked,
            "ready": self.ready,
            "ready_result": self.ready_result,
            "selector_used": self.selector_used,
            "prompt_candidates": list(self.prompt_candidates),
            "modal_detected": self.modal_detected,
            "generate_button_visible": self.generate_button_visible,
            "use_frame_button_visible": self.use_frame_button_visible,
            "download_button_visible": self.download_button_visible,
            "generation_in_progress": self.generation_in_progress,
            "generation_state": dict(self.generation_state),
            "notes": list(self.notes),
        }


@dataclass
class UseFrameComposerHandoffState:
    clip_number: int = 0
    checked: bool = False
    handoff_result: str = ""
    prompt_interactable: bool = False
    reference_thumbnail_detected: bool = False
    output_card_selected_only: bool = False
    generate_button_visible: bool = False
    generate_button_disabled: bool = False
    generation_in_progress: bool = False
    modal_detected: bool = False
    output_card_candidates: list[dict[str, Any]] = field(default_factory=list)
    reference_thumbnail_candidates: list[dict[str, Any]] = field(default_factory=list)
    prompt_candidates: list[dict[str, Any]] = field(default_factory=list)
    retry_attempts: int = 0
    use_frame_reclicked: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_number": self.clip_number,
            "checked": self.checked,
            "handoff_result": self.handoff_result,
            "prompt_interactable": self.prompt_interactable,
            "reference_thumbnail_detected": self.reference_thumbnail_detected,
            "output_card_selected_only": self.output_card_selected_only,
            "generate_button_visible": self.generate_button_visible,
            "generate_button_disabled": self.generate_button_disabled,
            "generation_in_progress": self.generation_in_progress,
            "modal_detected": self.modal_detected,
            "output_card_candidates": list(self.output_card_candidates),
            "reference_thumbnail_candidates": list(self.reference_thumbnail_candidates),
            "prompt_candidates": list(self.prompt_candidates),
            "retry_attempts": self.retry_attempts,
            "use_frame_reclicked": self.use_frame_reclicked,
            "notes": list(self.notes),
        }


PROMPT_EDITOR_FALLBACK_SELECTORS: tuple[str, ...] = (
    'div[aria-label="Prompt"]',
    '[aria-label="Prompt"]',
    '[role="textbox"][aria-label*="rompt" i]',
    'div[contenteditable="true"]',
)

POST_DOWNLOAD_SETTLE_MS = 1500
POST_USE_FRAME_INITIAL_SETTLE_MS = 1500
PROMPT_EDITOR_READY_POLL_SECONDS = 0.5
PROMPT_EDITOR_READY_MAX_SECONDS = 25.0

USE_FRAME_HANDOFF_MAX_RETRIES = 3
USE_FRAME_HANDOFF_RETRY_DELAY_MS = 800
USE_FRAME_HANDOFF_POLL_SECONDS = 0.5
USE_FRAME_HANDOFF_MAX_WAIT_SECONDS = 30.0

USE_FRAME_HANDOFF_COMPOSER_READY = "composer_ready"
USE_FRAME_HANDOFF_GENERATION_STARTED = "generation_already_started"
USE_FRAME_HANDOFF_INVALID_CARD_ONLY = "invalid_card_only"
USE_FRAME_HANDOFF_TIMEOUT = "timeout"


class PageLike(Protocol):
    def goto(self, url: str, **kwargs: Any) -> Any: ...
    def locator(self, selector: str) -> Any: ...
    def get_by_text(self, text: str, *, exact: bool = False) -> Any: ...
    def wait_for_load_state(self, state: str, *, timeout: float | None = None) -> Any: ...


@dataclass
class NavigatorActionLog:
    action: str
    control_key: str | None = None
    detail: str = ""
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "control_key": self.control_key,
            "detail": self.detail,
            "approved": self.approved,
        }


@dataclass
class MappedRunwayUINavigator:
    """Navigate Runway using mapped selectors; never clicks dangerous controls without approval."""

    snapshot: RunwayUIMapSnapshot
    page: PageLike | None = None
    simulate: bool = False
    action_log: list[NavigatorActionLog] = field(default_factory=list)
    approvals: dict[str, RunwayContinuityApprovalRecord] = field(default_factory=dict)
    prep_timeout_ms: int = DEFAULT_PREP_TIMEOUT_MS
    menu_open_settle_seconds: float = DEFAULT_MENU_OPEN_SETTLE_SECONDS
    menu_option_timeout_ms: int = DEFAULT_MENU_OPTION_TIMEOUT_MS
    screenshot_fn: ScreenshotFn | None = None
    last_starter_settings: StarterImageSettingsState | None = None
    last_preclean: StarterImagePrecleanState | None = None
    last_prompt_clear: PromptClearResult | None = None
    last_latest_image_card: LatestGeneratedImageCardState | None = None
    last_video_settings: VideoToolbarSettingsState | None = None
    _pre_generate_card_snapshot: GenerationImageCardSnapshot | None = None
    _simulated_menu_values: dict[str, str] = field(default_factory=dict)
    _simulated_prompt_text: dict[str, str] = field(default_factory=dict)
    _simulated_chip_row: dict[str, str] = field(default_factory=dict)
    _simulated_generation_cards: list[dict[str, Any]] | None = None
    _simulated_stale_preview_open: bool = False
    _simulated_video_mode: bool = False
    _simulated_page_url: str = ""
    _consumed_image_card_fingerprints: set[str] = field(default_factory=set)
    last_prompt_ready_by_clip: dict[int, PromptEditorReadyState] = field(default_factory=dict)
    last_generation_progress_by_clip: dict[int, VideoGenerationProgressState] = field(
        default_factory=dict
    )
    last_use_frame_handoff_by_clip: dict[int, UseFrameComposerHandoffState] = field(
        default_factory=dict
    )
    _use_frame_reclick_used: set[int] = field(default_factory=set)
    _simulated_use_frame_handoff: dict[int, str] = field(default_factory=dict)
    last_image_quality_readback: ImageToolbarChipReadback | None = None
    _phase_i_artifact_tracker: PhaseIArtifactTracker | None = None
    _phase_i_cdp_downloader: RunwayPhaseICdpDownloader | None = None
    _phase_i_project_id: str = "phase_i"
    last_clip_download_attempts: dict[int, ClipDownloadAttempt] = field(default_factory=dict)
    last_strict_completion_by_clip: dict[int, Any] = field(default_factory=dict)
    last_last_frame_use_frame_by_clip: dict[int, Any] = field(default_factory=dict)
    _simulate_clip_generating: dict[int, bool] = field(default_factory=dict)
    _video_generate_click_sent_by_clip: dict[int, float] = field(default_factory=dict)
    _video_generate_submitted_clips: set[int] = field(default_factory=set)
    _strict_completion_test_override: dict[str, Any] | None = None

    @classmethod
    def from_map(
        cls,
        *,
        map_path: Path | str | None = None,
        ui_map: dict[str, Any] | None = None,
        page: PageLike | None = None,
        simulate: bool = False,
    ) -> MappedRunwayUINavigator:
        snapshot = resolve_runway_ui_controls(ui_map=ui_map, map_path=map_path)
        if not snapshot.ok:
            missing = ", ".join(snapshot.missing) or "none"
            invalid = ", ".join(item["control"] for item in snapshot.invalid) or "none"
            raise ValueError(
                f"Runway UI map not ready for semi-automation "
                f"(missing={missing}; invalid={invalid})"
            )
        return cls(snapshot=snapshot, page=page, simulate=simulate)

    def control(self, key: str) -> ResolvedControl:
        resolved = self.snapshot.controls.get(key)
        if resolved is None:
            raise KeyError(f"mapped control not found: {key}")
        if not resolved.valid:
            raise ValueError(f"mapped control invalid: {key} ({resolved.invalid_reason})")
        return resolved

    def has_control(self, key: str) -> bool:
        resolved = self.snapshot.controls.get(key)
        return bool(resolved and resolved.valid)

    def _record(self, action: str, *, control_key: str | None = None, detail: str = "", approved: bool = False) -> None:
        self.action_log.append(
            NavigatorActionLog(
                action=action,
                control_key=control_key,
                detail=detail,
                approved=approved,
            )
        )

    def _require_page(self) -> PageLike:
        if self.page is None:
            raise RuntimeError("browser page not attached; use simulate=True or attach page")
        return self.page

    def _locator_for(self, ctrl: ResolvedControl):
        page = self._require_page()
        css = ctrl.css_selector
        if selector_is_weak(css) and ctrl.text.strip():
            text = ctrl.text.strip()
            try:
                exact = page.get_by_text(text, exact=True)
                if exact.count() > 0:
                    return exact.first
            except Exception:
                pass
            try:
                fuzzy = page.get_by_text(text, exact=False)
                if fuzzy.count() > 0:
                    return fuzzy.first
            except Exception:
                pass
        return page.locator(css).first

    def is_control_visible(self, control_key: str) -> bool:
        if self.simulate:
            return control_key in self.snapshot.controls
        ctrl = self.control(control_key)
        try:
            locator = self._locator_for(ctrl)
            return bool(locator.is_visible())
        except Exception:
            return False

    def navigate_to_control_page(self, control_key: str) -> None:
        ctrl = self.control(control_key)
        url = (ctrl.page_url or "").strip()
        if not url:
            raise ValueError(f"no page_url for control: {control_key}")
        self._record("navigate", control_key=control_key, detail=url)
        if self.simulate:
            return
        page = self._require_page()
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=self.prep_timeout_ms)
        except Exception:
            pass
        time.sleep(0.5)

    def click_control(
        self,
        control_key: str,
        *,
        step_id: str | None = None,
        approved: bool = False,
    ) -> None:
        if is_approval_gated_control(control_key):
            if not approved and not can_execute_dangerous_action(
                control_key, step_id=step_id, approvals=self.approvals
            ):
                raise PermissionError(dangerous_action_block_reason(control_key))
        ctrl = self.control(control_key)
        if self.simulate:
            self._record("click", control_key=control_key, detail=ctrl.css_selector, approved=approved)
            return
        errors: list[str] = []
        if self._try_click_mapped_control(ctrl, control_key, errors, approved=approved):
            time.sleep(0.35)
            return
        for text in click_control_texts_for(control_key, ctrl):
            try:
                if self._click_button_by_text(text):
                    self._record(
                        "click",
                        control_key=control_key,
                        detail=f"text={text}",
                        approved=approved,
                    )
                    time.sleep(0.35)
                    return
            except Exception as exc:
                errors.append(f"text '{text}': {exc}")
        self._capture_failure_screenshot(f"click_fail_{control_key}")
        raise RuntimeError(
            f"click failed for {control_key}: "
            + ("; ".join(errors) if errors else "no selector or text match")
        )

    def _try_click_mapped_control(
        self,
        ctrl: ResolvedControl,
        control_key: str,
        errors: list[str],
        *,
        approved: bool,
    ) -> bool:
        page = self._require_page()
        css = ctrl.css_selector
        try:
            locator = page.locator(css).first
            if locator.count() > 0:
                locator.wait_for(state="visible", timeout=self.prep_timeout_ms)
                locator.click(timeout=self.prep_timeout_ms, force=True)
                self._record(
                    "click",
                    control_key=control_key,
                    detail=f"mapped css={css}",
                    approved=approved,
                )
                return True
        except Exception as exc:
            errors.append(f"mapped selector '{css}': {exc}")

        if selector_is_weak(css) and ctrl.text.strip():
            try:
                if self._click_button_by_text(ctrl.text.strip()):
                    self._record(
                        "click",
                        control_key=control_key,
                        detail=f"mapped_text={ctrl.text.strip()}",
                        approved=approved,
                    )
                    return True
            except Exception as exc:
                errors.append(f"mapped control text '{ctrl.text.strip()}': {exc}")

        if ctrl.aria_label.strip():
            try:
                if self._click_by_aria_label(ctrl.aria_label.strip()):
                    self._record(
                        "click",
                        control_key=control_key,
                        detail=f"aria_label={ctrl.aria_label.strip()}",
                        approved=approved,
                    )
                    return True
            except Exception as exc:
                errors.append(f"aria_label '{ctrl.aria_label.strip()}': {exc}")
        return False

    def _click_by_aria_label(self, label: str) -> bool:
        page = self._require_page()
        try:
            role_locator = page.get_by_role("button", name=label)
            if role_locator.count() > 0 and role_locator.first.is_visible():
                role_locator.first.click(timeout=self.menu_option_timeout_ms, force=True)
                return True
        except Exception:
            pass
        get_by_label = getattr(page, "get_by_label", None)
        if callable(get_by_label):
            try:
                label_locator = get_by_label(label)
                if label_locator.count() > 0 and label_locator.first.is_visible():
                    label_locator.first.click(timeout=self.menu_option_timeout_ms, force=True)
                    return True
            except Exception:
                pass
        try:
            aria_locator = page.locator(f'[aria-label="{label}"]').first
            if aria_locator.count() > 0 and aria_locator.is_visible():
                aria_locator.click(timeout=self.menu_option_timeout_ms, force=True)
                return True
        except Exception:
            pass
        return False

    def _click_button_by_text(self, text: str) -> bool:
        page = self._require_page()
        if self._click_visible_text(text, prefer_exact=True):
            return True
        if self._click_visible_text(text, prefer_exact=False):
            return True
        try:
            role_locator = page.get_by_role("button", name=text)
            if role_locator.count() > 0 and role_locator.first.is_visible():
                role_locator.first.click(timeout=self.menu_option_timeout_ms, force=True)
                return True
        except Exception:
            pass
        try:
            clicked = page.evaluate(
                """(label) => {
                    const normalized = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const target = normalized(label).toLowerCase();
                    const nodes = Array.from(
                        document.querySelectorAll('button, [role=\"button\"], a[href]')
                    );
                    for (const node of nodes) {
                        const text = normalized(node.innerText || node.textContent || '');
                        if (!text) continue;
                        if (text.toLowerCase() === target || text.toLowerCase().includes(target)) {
                            const rect = node.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                node.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }""",
                text,
            )
            return bool(clicked)
        except Exception:
            return False

    def fill_prompt_control(
        self,
        control_key: str,
        text: str,
        *,
        selector_override: str = "",
    ) -> None:
        prompt = str(text or "").strip()
        if not prompt:
            raise ValueError("prompt text is empty")
        ctrl = self.control(control_key)
        selector_note = selector_override or "mapped"
        self._record(
            "fill_prompt",
            control_key=control_key,
            detail=f"chars={len(prompt)}; selector={selector_note}",
        )
        if self.simulate:
            self._simulated_prompt_text[control_key] = prompt
            return
        page = self._require_page()
        if selector_override.strip():
            locator = page.locator(selector_override.strip()).first
        else:
            locator = self._locator_for(ctrl)
        locator.click(force=True, timeout=self.prep_timeout_ms)
        time.sleep(0.2)
        try:
            locator.fill(prompt, timeout=self.prep_timeout_ms)
            self._simulated_prompt_text[control_key] = prompt
            return
        except Exception:
            pass
        page = self._require_page()
        keyboard = getattr(page, "keyboard", None)
        try:
            if keyboard is not None:
                keyboard.press("Control+A")
                keyboard.press("Backspace")
        except Exception:
            pass
        try:
            locator.evaluate(
                """(el, value) => {
                    el.focus();
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                        el.value = value;
                    } else {
                        el.textContent = value;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                prompt,
            )
        except Exception:
            keyboard = getattr(page, "keyboard", None)
            if keyboard is not None:
                keyboard.type(prompt, delay=0)
            else:
                raise
        self._simulated_prompt_text[control_key] = prompt

    def ensure_clip_prompt_applied(
        self,
        clip_index: int,
        expected_prompt: str,
        *,
        selector_override: str = "",
        max_attempts: int = 3,
    ) -> bool:
        """Clear and refill composer prompt until clip N marker is present."""
        expected = str(expected_prompt or "").strip()
        if not expected:
            return True
        marker = f"clip {max(1, clip_index)} of"
        selector = selector_override.strip()
        for attempt in range(1, max(1, max_attempts) + 1):
            actual = self.read_prompt_control_text("prompt_input")
            if marker.lower() in actual.lower():
                self._record(
                    "clip_prompt_verified",
                    control_key="prompt_input",
                    detail=f"clip={clip_index}; attempt={attempt}; marker={marker!r}",
                )
                return True
            try:
                self.clear_prompt_control("prompt_input")
            except Exception:
                pass
            self.fill_prompt_control(
                "prompt_input",
                expected,
                selector_override=selector,
            )
            time.sleep(0.35)
        actual = self.read_prompt_control_text("prompt_input")
        ok = marker.lower() in actual.lower()
        self._record(
            "clip_prompt_verify_fail" if not ok else "clip_prompt_verified",
            control_key="prompt_input",
            detail=(
                f"clip={clip_index}; marker={marker!r}; "
                f"actual_preview={actual[:120]!r}"
            ),
        )
        return ok

    def open_menu_and_select(
        self,
        menu_key: str,
        option_key: str,
        option_texts: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        texts = tuple(option_texts or MENU_OPTION_TEXTS.get((menu_key, option_key), ()))
        if not texts:
            option_ctrl = self.control(option_key)
            if option_ctrl.text.strip():
                texts = (option_ctrl.text.strip(),)
        self.ensure_menu_setting(menu_key, option_key, texts)

    @staticmethod
    def _normalize_display_value(value: str) -> str:
        return " ".join(str(value or "").split()).strip()

    @staticmethod
    def _display_matches_expected(detected: str, expected_texts: tuple[str, ...] | list[str]) -> bool:
        detected_norm = MappedRunwayUINavigator._normalize_display_value(detected).lower()
        if not detected_norm:
            return False
        for expected in expected_texts:
            expected_norm = MappedRunwayUINavigator._normalize_display_value(expected).lower()
            if not expected_norm:
                continue
            if detected_norm == expected_norm:
                return True
            if expected_norm in {"1", "4"} and detected_norm == expected_norm:
                return True
            if expected_norm.endswith("k") and detected_norm.replace(" ", "") == expected_norm.replace(" ", ""):
                return True
            if ":" in expected_norm and expected_norm in detected_norm.replace(" ", ""):
                return True
            if expected_norm.endswith("s") and not expected_norm.endswith("ks"):
                det = detected_norm.replace(" ", "")
                exp = expected_norm.replace(" ", "")
                if det == exp:
                    return True
        return False

    def _capture_failure_screenshot(self, label: str) -> None:
        if self.screenshot_fn is None:
            return
        try:
            self.screenshot_fn(label)
        except Exception:
            pass

    def _capture_chip_diagnostic_screenshot(self, label: str, *, chip_row: dict[str, str] | None = None) -> None:
        row = chip_row or self.read_toolbar_chip_row()
        detail = (
            f"count={row.get('count', '')}; "
            f"aspect={row.get('aspect', '')}; "
            f"quality={row.get('quality', '')}; "
            f"duration={row.get('duration', '')}"
        )
        self._record("chip_detect", detail=detail)
        self._capture_failure_screenshot(label)

    @staticmethod
    def _toolbar_chip_row_eval_script() -> str:
        """Legacy fallback row read (video toolbar / unstructured page)."""
        return """() => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const compact = (value) => normalize(value).replace(/\\s/g, '');
            const classify = (text) => {
                const t = normalize(text);
                const c = compact(t);
                if (t === '1' || t === '4') return 'count';
                if (/^\\d:\\d+$/.test(c) || /^\\d\\s*:\\s*\\d+$/.test(t)) return 'aspect';
                if (/^[124]K$/i.test(c)) return 'quality';
                if (/^\\d+\\s*s$/i.test(c) || /^\\d+s$/i.test(c)) return 'duration';
                return '';
            };
            const candidates = [];
            for (const node of document.querySelectorAll(
                'button, [role=\"button\"], span, div, svg'
            )) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                if (rect.top < window.innerHeight * 0.42) continue;
                const text = normalize(node.innerText || node.textContent || '');
                if (!text || text.length > 12 || text.includes('\\n')) continue;
                const kind = classify(text);
                if (!kind) continue;
                candidates.push({
                    kind,
                    text,
                    top: rect.top,
                    left: rect.left,
                    area: rect.width * rect.height,
                });
            }
            const pick = (kind) => {
                const matches = candidates.filter((item) => item.kind === kind);
                if (!matches.length) return '';
                matches.sort((a, b) => b.area - a.area || a.top - b.top || a.left - b.left);
                return matches[0].text;
            };
            return {
                count: pick('count'),
                aspect: pick('aspect'),
                quality: pick('quality'),
                duration: pick('duration'),
            };
        }"""

    @staticmethod
    def _image_toolbar_chip_readback_eval_script() -> str:
        return """({ chipKind }) => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const compact = (value) => normalize(value).replace(/\\s/g, '');
            const classify = (text) => {
                const t = normalize(text);
                const c = compact(t);
                if (t === '1' || t === '4') return 'count';
                if (/^\\d:\\d+$/.test(c) || /^\\d\\s*:\\s*\\d+$/.test(t)) return 'aspect';
                if (/^[124]K$/i.test(c)) return 'quality';
                if (/^\\d+\\s*s$/i.test(c) || /^\\d+s$/i.test(c)) return 'duration';
                return '';
            };
            const isActiveNode = (node) => {
                if (!node) return false;
                const pressed = node.getAttribute('aria-pressed');
                const selected = node.getAttribute('aria-selected');
                const state = normalize(node.getAttribute('data-state') || '');
                if (pressed === 'true' || selected === 'true') return true;
                if (state === 'active' || state === 'on' || state === 'checked') return true;
                const cls = String(node.className || '').toLowerCase();
                if (cls.includes('active') || cls.includes('selected') || cls.includes('pressed')) {
                    return true;
                }
                const button = node.closest('button,[role=\"button\"]');
                if (button && button !== node) return isActiveNode(button);
                return false;
            };
            const isButtonLike = (node) => {
                if (!node) return false;
                const tag = String(node.tagName || '').toLowerCase();
                if (tag === 'button') return true;
                const role = normalize(node.getAttribute('role') || '');
                return role === 'button';
            };
            const collectChips = (root) => {
                const items = [];
                const scope = root || document;
                for (const node of scope.querySelectorAll(
                    'button, [role=\"button\"], span, div'
                )) {
                    const rect = node.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    const text = normalize(node.innerText || node.textContent || '');
                    if (!text || text.length > 12 || text.includes('\\n')) continue;
                    const kind = classify(text);
                    if (!kind) continue;
                    const area = rect.width * rect.height;
                    items.push({
                        kind,
                        text,
                        active: isActiveNode(node),
                        isButton: isButtonLike(node),
                        bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        top: rect.top,
                        left: rect.left,
                        area,
                    });
                }
                return items;
            };
            const toolbarScore = (chips) => {
                const kinds = new Set(chips.map((c) => c.kind));
                let score = kinds.size * 10;
                if (kinds.has('count') && kinds.has('aspect') && kinds.has('quality')) score += 50;
                return score;
            };
            let toolbarRoot = null;
            let toolbarSelector = '';
            const anchors = Array.from(document.querySelectorAll(
                '[aria-label*=\"Prompt\" i], textarea, [contenteditable=\"true\"], '
                + '[data-testid*=\"prompt\" i], [class*=\"prompt\" i]'
            ));
            for (const anchor of anchors) {
                let node = anchor;
                for (let depth = 0; depth < 14 && node; depth++) {
                    const chips = collectChips(node);
                    if (toolbarScore(chips) >= 60) {
                        toolbarRoot = node;
                        const testId = node.getAttribute('data-testid');
                        const id = node.id;
                        toolbarSelector = testId
                            ? `[data-testid=\"${testId}\"]`
                            : (id ? `#${id}` : node.tagName.toLowerCase());
                        break;
                    }
                    node = node.parentElement;
                }
                if (toolbarRoot) break;
            }
            if (!toolbarRoot) {
                const bands = new Map();
                const loose = collectChips(document).filter((c) => c.top >= window.innerHeight * 0.45);
                for (const chip of loose) {
                    const bandKey = Math.round(chip.top / 36);
                    if (!bands.has(bandKey)) bands.set(bandKey, []);
                    bands.get(bandKey).push(chip);
                }
                let bestBand = [];
                let bestScore = -1;
                for (const band of bands.values()) {
                    const score = toolbarScore(band);
                    if (score > bestScore) {
                        bestScore = score;
                        bestBand = band;
                    }
                }
                if (bestScore >= 60) {
                    toolbarRoot = document.body;
                    toolbarSelector = 'body:image-toolbar-band-fallback';
                }
            }
            const inToolbar = (chip) => {
                if (!toolbarRoot || toolbarRoot === document.body) {
                    return chip.top >= window.innerHeight * 0.45;
                }
                return true;
            };
            const all = collectChips(toolbarRoot || document).map((chip) => ({
                ...chip,
                inToolbar: inToolbar(chip),
            }));
            const pickKind = (kind) => {
                const matches = all.filter((c) => c.kind === kind && c.inToolbar);
                if (!matches.length) return { picked: '', active: null };
                const scored = matches.map((c) => {
                    let score = c.area;
                    if (c.isButton) score += 500;
                    if (c.active) score += 2000;
                    return { ...c, score };
                });
                scored.sort((a, b) => b.score - a.score || b.top - a.top || a.left - b.left);
                const active = scored.find((c) => c.active) || null;
                const picked = (active || scored[0]).text;
                return { picked, active };
            };
            const rows = {
                count: pickKind('count'),
                aspect: pickKind('aspect'),
                quality: pickKind('quality'),
                duration: pickKind('duration'),
            };
            const target = chipKind ? rows[chipKind] : rows.quality;
            return {
                toolbarFound: Boolean(toolbarRoot),
                toolbarContainerSelector: toolbarSelector,
                chipKind: chipKind || 'quality',
                pickedText: target ? target.picked : '',
                activeChip: target ? target.active : null,
                allCandidates: all,
                count: rows.count.picked,
                aspect: rows.aspect.picked,
                quality: rows.quality.picked,
                duration: rows.duration.picked,
            };
        }"""

    @staticmethod
    def _parse_image_toolbar_readback_payload(
        payload: dict[str, Any],
        *,
        chip_kind: str,
    ) -> ImageToolbarChipReadback:
        readback = ImageToolbarChipReadback(
            chip_kind=chip_kind,
            toolbar_container_selector=str(payload.get("toolbarContainerSelector") or ""),
            toolbar_found=bool(payload.get("toolbarFound")),
            picked_text=MappedRunwayUINavigator._normalize_display_value(
                str(payload.get("pickedText") or "")
            ),
        )
        active_raw = payload.get("activeChip")
        if isinstance(active_raw, dict) and active_raw.get("text"):
            bbox = active_raw.get("bbox") if isinstance(active_raw.get("bbox"), dict) else {}
            readback.active_chip = ImageToolbarChipCandidate(
                kind=str(active_raw.get("kind") or chip_kind),
                text=MappedRunwayUINavigator._normalize_display_value(str(active_raw.get("text") or "")),
                active=bool(active_raw.get("active")),
                in_toolbar=bool(active_raw.get("inToolbar")),
                is_button=bool(active_raw.get("isButton")),
                bbox={
                    "x": float(bbox.get("x") or 0),
                    "y": float(bbox.get("y") or 0),
                    "width": float(bbox.get("width") or 0),
                    "height": float(bbox.get("height") or 0),
                },
                score=float(active_raw.get("score") or 0),
            )
        raw_candidates = payload.get("allCandidates") or []
        if isinstance(raw_candidates, list):
            for item in raw_candidates:
                if not isinstance(item, dict):
                    continue
                bbox = item.get("bbox") if isinstance(item.get("bbox"), dict) else {}
                readback.all_candidates.append(
                    ImageToolbarChipCandidate(
                        kind=str(item.get("kind") or ""),
                        text=MappedRunwayUINavigator._normalize_display_value(str(item.get("text") or "")),
                        active=bool(item.get("active")),
                        in_toolbar=bool(item.get("inToolbar")),
                        is_button=bool(item.get("isButton")),
                        bbox={
                            "x": float(bbox.get("x") or 0),
                            "y": float(bbox.get("y") or 0),
                            "width": float(bbox.get("width") or 0),
                            "height": float(bbox.get("height") or 0),
                        },
                        score=float(item.get("score") or 0),
                    )
                )
        if chip_kind == "quality" and not readback.picked_text:
            readback.picked_text = MappedRunwayUINavigator._normalize_display_value(
                str(payload.get("quality") or "")
            )
        return readback

    def _on_image_generation_page(self) -> bool:
        if self.simulate:
            return True
        url = self._current_page_url().lower()
        return "tool=image" in url or "mode=tools" in url

    def probe_image_toolbar_chips(self, chip_kind: str) -> ImageToolbarChipReadback:
        kind = str(chip_kind or "quality").strip() or "quality"
        if self.simulate:
            row = self.read_toolbar_chip_row()
            text = self._normalize_display_value(row.get(kind, ""))
            readback = ImageToolbarChipReadback(
                chip_kind=kind,
                toolbar_found=True,
                toolbar_container_selector="simulate",
                picked_text=text,
                active_chip=ImageToolbarChipCandidate(
                    kind=kind,
                    text=text,
                    active=True,
                    in_toolbar=True,
                    is_button=True,
                ),
            )
            if kind == "quality":
                self.last_image_quality_readback = readback
            return readback

        page = self._require_page()
        try:
            payload = page.evaluate(
                self._image_toolbar_chip_readback_eval_script(),
                {"chipKind": kind},
            )
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        readback = self._parse_image_toolbar_readback_payload(payload, chip_kind=kind)
        if kind == "quality":
            self.last_image_quality_readback = readback
        return readback

    def _write_image_quality_chip_diagnostics(
        self,
        *,
        menu_key: str,
        option_key: str,
        expected_texts: tuple[str, ...],
        detected: str,
        readback: ImageToolbarChipReadback | None,
        screenshot_path: str = "",
        retry_attempts: int = 0,
    ) -> None:
        quality_candidates = [
            item.to_dict()
            for item in (readback.all_candidates if readback else [])
            if item.kind == "quality"
        ]
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "menu_key": menu_key,
            "option_key": option_key,
            "expected_texts": list(expected_texts),
            "detected": detected,
            "retry_attempts": retry_attempts,
            "toolbar_container_selector": (
                readback.toolbar_container_selector if readback else ""
            ),
            "toolbar_found": readback.toolbar_found if readback else False,
            "active_chip_candidate": (
                readback.active_chip.to_dict()
                if readback and readback.active_chip
                else {}
            ),
            "all_quality_chip_candidates": quality_candidates,
            "picked_text": readback.picked_text if readback else "",
            "screenshot_path": screenshot_path,
            "current_url": self._current_page_url(),
            "last_action_log_entries": [log.to_dict() for log in self.action_log[-10:]],
        }
        DEFAULT_IMAGE_QUALITY_CHIP_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_IMAGE_QUALITY_CHIP_DIAGNOSTICS.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _read_image_toolbar_chip_row(self) -> dict[str, str]:
        if self.simulate:
            return self.read_toolbar_chip_row()
        page = self._require_page()
        try:
            payload = page.evaluate(
                self._image_toolbar_chip_readback_eval_script(),
                {"chipKind": ""},
            )
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            return {"count": "", "aspect": "", "quality": "", "duration": ""}
        return {
            "count": self._normalize_display_value(str(payload.get("count") or "")),
            "aspect": self._normalize_display_value(str(payload.get("aspect") or "")),
            "quality": self._normalize_display_value(str(payload.get("quality") or "")),
            "duration": self._normalize_display_value(str(payload.get("duration") or "")),
        }

    def _wait_for_chip_readback_settle(self, menu_key: str) -> None:
        self._sleep_ms(CHIP_READBACK_SETTLE_MS)
        if menu_key == IMAGE_QUALITY_MENU_KEY:
            self.probe_image_toolbar_chips("quality")

    @staticmethod
    def _toolbar_chip_click_eval_script() -> str:
        return """({ chipKind }) => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const compact = (value) => normalize(value).replace(/\\s/g, '');
            const classify = (text) => {
                const t = normalize(text);
                const c = compact(t);
                if (t === '1' || t === '4') return 'count';
                if (/^\\d:\\d+$/.test(c) || /^\\d\\s*:\\s*\\d+$/.test(t)) return 'aspect';
                if (/^[124]K$/i.test(c)) return 'quality';
                if (/^\\d+\\s*s$/i.test(c) || /^\\d+s$/i.test(c)) return 'duration';
                return '';
            };
            const candidates = [];
            for (const node of document.querySelectorAll(
                'button, [role=\"button\"], span, div, svg'
            )) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                if (rect.top < window.innerHeight * 0.42) continue;
                const text = normalize(node.innerText || node.textContent || '');
                if (!text || text.length > 12 || text.includes('\\n')) continue;
                const kind = classify(text);
                if (kind !== chipKind) continue;
                candidates.push({ node, top: rect.top, left: rect.left, area: rect.width * rect.height });
            }
            if (!candidates.length) return false;
            candidates.sort((a, b) => a.area - b.area || a.top - b.top || a.left - b.left);
            candidates[0].node.click();
            return true;
        }"""

    def read_toolbar_chip_row(self) -> dict[str, str]:
        if self.simulate:
            row = {
                "count": self._simulated_menu_values.get(IMAGE_COUNT_MENU_KEY, ""),
                "aspect": (
                    self._simulated_menu_values.get(IMAGE_ASPECT_MENU_KEY, "")
                    or self._simulated_menu_values.get(VIDEO_ASPECT_MENU_KEY, "")
                ),
                "quality": self._simulated_menu_values.get(IMAGE_QUALITY_MENU_KEY, ""),
                "duration": self._simulated_menu_values.get(VIDEO_DURATION_MENU_KEY, ""),
            }
            for kind, value in self._simulated_chip_row.items():
                cleaned = self._normalize_display_value(value)
                if cleaned:
                    row[kind] = cleaned
            return {
                "count": self._normalize_display_value(row.get("count", "")),
                "aspect": self._normalize_display_value(row.get("aspect", "")),
                "quality": self._normalize_display_value(row.get("quality", "")),
                "duration": self._normalize_display_value(row.get("duration", "")),
            }

        if self._on_image_generation_page():
            return self._read_image_toolbar_chip_row()

        page = self._require_page()
        try:
            payload = page.evaluate(self._toolbar_chip_row_eval_script())
            if isinstance(payload, dict):
                return {
                    "count": self._normalize_display_value(str(payload.get("count") or "")),
                    "aspect": self._normalize_display_value(str(payload.get("aspect") or "")),
                    "quality": self._normalize_display_value(str(payload.get("quality") or "")),
                    "duration": self._normalize_display_value(str(payload.get("duration") or "")),
                }
        except Exception:
            pass
        return {"count": "", "aspect": "", "quality": "", "duration": ""}

    def _sync_simulated_chip_row(self, *, menu_key: str, value: str) -> None:
        kind = TOOLBAR_CHIP_KIND_BY_MENU.get(menu_key)
        if kind is None:
            return
        cleaned = self._normalize_display_value(value)
        self._simulated_menu_values[menu_key] = cleaned
        self._simulated_chip_row[kind] = cleaned

    def read_menu_display_value(self, menu_key: str) -> str:
        if menu_key in IMAGE_TOOLBAR_CHIP_MENU_KEYS and (
            self.simulate or self._on_image_generation_page()
        ):
            kind = TOOLBAR_CHIP_KIND_BY_MENU[menu_key]
            readback = self.probe_image_toolbar_chips(kind)
            if readback.picked_text:
                return readback.picked_text
            return self._read_image_toolbar_chip_row().get(kind, "")
        if menu_key in TOOLBAR_CHIP_MENU_KEYS:
            kind = TOOLBAR_CHIP_KIND_BY_MENU[menu_key]
            return self.read_toolbar_chip_row().get(kind, "")

        if self.simulate:
            return self._simulated_menu_values.get(menu_key, "")

        page = self._require_page()
        patterns = TOOLBAR_MENU_PATTERNS.get(menu_key, ())
        try:
            value = page.evaluate(
                """({ menuKey, patterns }) => {
                    const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const lower = (value) => normalize(value).toLowerCase();
                    const patternMatches = (text) => {
                        const target = lower(text);
                        if (!target) return false;
                        for (const pattern of patterns) {
                            const p = String(pattern || '').toLowerCase();
                            if (!p) continue;
                            if (target === p) return true;
                            if (p.includes(':') && target.replace(/\\s/g, '') === p.replace(/\\s/g, '')) return true;
                            if (p.endsWith('k') && target.replace(/\\s/g, '') === p.replace(/\\s/g, '')) return true;
                        }
                        return false;
                    };
                    const candidates = Array.from(
                        document.querySelectorAll('button, span, div, svg, [role=\"button\"]')
                    );
                    let best = '';
                    let bestScore = -1;
                    for (const node of candidates) {
                        const rect = node.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) continue;
                        if (rect.top < window.innerHeight * 0.45) continue;
                        const text = normalize(node.innerText || node.textContent || '');
                        const aria = normalize(node.getAttribute?.('aria-label') || '');
                        const probe = text || aria;
                        if (!probe) continue;
                        if (!patternMatches(probe)) continue;
                        const score = rect.top + rect.left / 10000;
                        if (score > bestScore) {
                            bestScore = score;
                            best = probe;
                        }
                    }
                    return best;
                }""",
                {"menuKey": menu_key, "patterns": list(patterns)},
            )
            return self._normalize_display_value(str(value or ""))
        except Exception:
            pass

        menu_ctrl = self.control(menu_key)
        if menu_ctrl.text.strip():
            return self._normalize_display_value(menu_ctrl.text)
        return ""

    def ensure_menu_setting(
        self,
        menu_key: str,
        option_key: str,
        expected_texts: tuple[str, ...] | list[str],
    ) -> str:
        texts = tuple(str(text).strip() for text in expected_texts if str(text).strip())
        is_chip = menu_key in TOOLBAR_CHIP_MENU_KEYS
        if is_chip:
            self._capture_chip_diagnostic_screenshot(f"chip_detect_before_{menu_key}")

        detected = self.read_menu_display_value(menu_key)
        if self._display_matches_expected(detected, texts):
            self._record(
                "chip_verify_skip" if is_chip else "menu_verify_skip",
                control_key=menu_key,
                detail=f"already={detected}",
            )
            if self.simulate:
                if is_chip:
                    self._sync_simulated_chip_row(menu_key=menu_key, value=texts[0])
                else:
                    self._simulated_menu_values[menu_key] = texts[0]
            return detected

        if is_chip:
            self._select_toolbar_chip_option(menu_key, option_key, texts)
        else:
            self.select_menu_option(menu_key, option_key, texts)

        self._sleep_ms(CHIP_AFTER_CLICK_VERIFY_DELAY_MS)
        if self.simulate:
            if is_chip:
                self._sync_simulated_chip_row(menu_key=menu_key, value=texts[0])
            else:
                self._simulated_menu_values[menu_key] = texts[0]

        if is_chip:
            detected_after = self._verify_chip_menu_setting_with_retry(
                menu_key,
                option_key,
                texts,
                selection_attempted=True,
            )
        else:
            self._wait_for_chip_readback_settle(menu_key)
            detected_after = self.read_menu_display_value(menu_key)
            if not self._display_matches_expected(detected_after, texts):
                self._capture_failure_screenshot(f"menu_verify_fail_{menu_key}_{option_key}")
                raise RuntimeError(
                    f"setting verification failed for {menu_key} -> {option_key}: "
                    f"expected one of {texts}, detected {detected_after!r}"
                )

        self._record(
            "chip_verify_ok" if is_chip else "menu_verify_ok",
            control_key=menu_key,
            detail=f"value={detected_after}",
        )
        return detected_after

    def _verify_chip_menu_setting_with_retry(
        self,
        menu_key: str,
        option_key: str,
        expected_texts: tuple[str, ...],
        *,
        selection_attempted: bool = False,
    ) -> str:
        texts = tuple(str(text).strip() for text in expected_texts if str(text).strip())
        last_detected = ""
        readback: ImageToolbarChipReadback | None = None
        screenshot_path = ""

        for attempt in range(1, CHIP_VERIFY_MAX_RETRIES + 1):
            self._wait_for_chip_readback_settle(menu_key)
            last_detected = self.read_menu_display_value(menu_key)
            if menu_key == IMAGE_QUALITY_MENU_KEY:
                readback = self.last_image_quality_readback or self.probe_image_toolbar_chips("quality")
            else:
                readback = self.probe_image_toolbar_chips(TOOLBAR_CHIP_KIND_BY_MENU[menu_key])

            self._capture_chip_diagnostic_screenshot(
                f"chip_detect_after_{menu_key}_attempt_{attempt}",
                chip_row=self.read_toolbar_chip_row(),
            )

            if self._display_matches_expected(last_detected, texts):
                self._record(
                    "chip_verify_ok",
                    control_key=menu_key,
                    detail=f"value={last_detected}; attempt={attempt}",
                )
                return last_detected

            if attempt < CHIP_VERIFY_MAX_RETRIES:
                self._record(
                    "chip_verify_retry",
                    control_key=menu_key,
                    detail=(
                        f"attempt={attempt}; expected={texts}; detected={last_detected!r}; "
                        f"reopen_menu={selection_attempted}"
                    ),
                )
                self._sleep_ms(CHIP_VERIFY_RETRY_DELAY_MS)
                if selection_attempted:
                    try:
                        self._select_toolbar_chip_option(menu_key, option_key, texts)
                    except Exception as exc:
                        self._record(
                            "chip_verify_retry_select_failed",
                            control_key=menu_key,
                            detail=str(exc),
                        )
                continue

        self._capture_chip_diagnostic_screenshot(
            f"chip_verify_fail_{menu_key}_{option_key}",
            chip_row=self.read_toolbar_chip_row(),
        )
        screenshot_path = self._capture_failure_screenshot_return_path(
            f"chip_verify_fail_{menu_key}_{option_key}"
        )
        if menu_key == IMAGE_QUALITY_MENU_KEY:
            self._write_image_quality_chip_diagnostics(
                menu_key=menu_key,
                option_key=option_key,
                expected_texts=texts,
                detected=last_detected,
                readback=readback,
                screenshot_path=screenshot_path,
                retry_attempts=CHIP_VERIFY_MAX_RETRIES,
            )
        raise RuntimeError(
            f"toolbar chip verification failed for {menu_key} -> {option_key}: "
            f"expected one of {texts}, detected {last_detected!r} "
            f"(after {CHIP_VERIFY_MAX_RETRIES} attempts)"
        )

    def _capture_failure_screenshot_return_path(self, label: str) -> str:
        if self.screenshot_fn is None:
            return ""
        try:
            self.screenshot_fn(label)
        except Exception:
            return ""
        return label

    def ensure_starter_image_settings(self, plan: RunwayContinuityPlan) -> StarterImageSettingsState:
        aspect_key = image_aspect_control_key(plan.aspect_ratio)
        count_key = image_count_control_key(plan.image_count)
        quality_key = image_quality_control_key(plan.image_quality)

        aspect_texts = MENU_OPTION_TEXTS.get((IMAGE_ASPECT_MENU_KEY, aspect_key), ("9:16",))
        count_texts = menu_option_texts_for_image_count(plan.image_count)
        quality_texts = menu_option_texts_for_image_quality(plan.image_quality)

        initial_row = self.read_toolbar_chip_row()
        self._capture_chip_diagnostic_screenshot("starter_chips_initial", chip_row=initial_row)

        detected_aspect = self.ensure_menu_setting(IMAGE_ASPECT_MENU_KEY, aspect_key, aspect_texts)
        detected_count = self.ensure_menu_setting(IMAGE_COUNT_MENU_KEY, count_key, count_texts)
        detected_quality = self.ensure_menu_setting(IMAGE_QUALITY_MENU_KEY, quality_key, quality_texts)

        final_row = self.read_toolbar_chip_row()
        self._capture_chip_diagnostic_screenshot("starter_chips_verified", chip_row=final_row)

        state = StarterImageSettingsState(
            detected_aspect_ratio=detected_aspect,
            detected_image_count=detected_count,
            detected_image_quality=detected_quality,
            settings_verified=True,
        )
        self.last_starter_settings = state
        return state

    def _probe_video_generate_button_state(self) -> dict[str, Any]:
        """Resolve video Generate button via mapped selector, then text fallback."""
        if self.simulate:
            visible = self.is_control_visible("generate_button")
            return {
                "actionable": visible,
                "visible": visible,
                "source": "simulate",
            }
        mapped_css = ""
        try:
            mapped_css = self.control("generate_button").css_selector
        except Exception:
            mapped_css = ""
        page = self._require_page()
        try:
            payload = page.evaluate(
                """(mappedCss) => {
                    const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                    const isDisabled = (el) => Boolean(
                        el.disabled || el.getAttribute('aria-disabled') === 'true'
                    );
                    const tryMapped = () => {
                        if (!mappedCss) return null;
                        const el = document.querySelector(mappedCss);
                        if (!el) return null;
                        const rect = el.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) return null;
                        return {
                            actionable: !isDisabled(el),
                            visible: true,
                            source: 'mapped',
                            y: rect.y,
                        };
                    };
                    const mapped = tryMapped();
                    if (mapped && mapped.actionable) {
                        return mapped;
                    }
                    const buttons = Array.from(
                        document.querySelectorAll('button, [role=\"button\"]')
                    );
                    let best = null;
                    for (const btn of buttons) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) continue;
                        const text = normalize(
                            btn.innerText || btn.textContent || ''
                        ).toLowerCase();
                        if (text !== 'generate' && !text.startsWith('generate ')) {
                            continue;
                        }
                        const candidate = {
                            actionable: !isDisabled(btn),
                            visible: true,
                            source: 'text',
                            y: rect.y,
                            text,
                        };
                        if (!best || rect.y > best.y) {
                            best = candidate;
                        }
                    }
                    return best || {
                        actionable: false,
                        visible: false,
                        source: mapped ? 'mapped_disabled' : 'none',
                    };
                }""",
                mapped_css,
            )
            return payload if isinstance(payload, dict) else {"actionable": False}
        except Exception as exc:
            return {"actionable": False, "error": str(exc)}

    def is_generate_button_actionable(self) -> bool:
        """True when the video Generate control is visible and enabled."""
        return bool(self._probe_video_generate_button_state().get("actionable"))

    def _generation_started_after_click(
        self,
        clip_index: int,
        before: VideoGenerationProgressState,
    ) -> bool:
        after = self.detect_video_generation_in_progress(max(1, clip_index))
        if self.is_real_video_generation_in_progress(after):
            return True
        if not self.is_generate_button_actionable():
            return True
        if after.output_loading and not before.output_loading:
            return True
        if after.output_cards_detected > before.output_cards_detected:
            return True
        if after.spinner_visible and not before.spinner_visible:
            return True
        return False

    def _count_feed_video_cards(self) -> int:
        if self.simulate:
            cards = self._simulated_generation_cards or []
            return sum(1 for card in cards if str(card.get("cardType") or "") == "video")
        try:
            cards = self.phase_i_artifact_tracker().scan_artifact_cards()
        except Exception:
            return 0
        tracker = self.phase_i_artifact_tracker()
        return sum(
            1
            for card in cards
            if str(card.get("cardType") or "") == "video"
            and not tracker._raw_card_is_stale(card)
        )

    def _is_video_generate_submitted(self, clip_index: int) -> bool:
        clip = max(1, int(clip_index))
        if clip in self._video_generate_submitted_clips:
            return True
        sent_at = self._video_generate_click_sent_by_clip.get(clip)
        return sent_at is not None and (time.monotonic() - sent_at) < 300.0

    def _mark_video_generate_submitted(self, clip_index: int) -> None:
        clip = max(1, int(clip_index))
        self._video_generate_submitted_clips.add(clip)
        self._video_generate_click_sent_by_clip[clip] = time.monotonic()

    @staticmethod
    def _composer_generate_click_eval_script() -> str:
        return """() => {
            const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
            const isDisabled = (el) => Boolean(
                el.disabled || el.getAttribute('aria-disabled') === 'true'
            );
            const promptSelectors = [
                '[aria-label=\"Prompt\"]',
                'textarea',
                'div[contenteditable=\"true\"]',
            ];
            let promptEl = null;
            for (const sel of promptSelectors) {
                const nodes = document.querySelectorAll(sel);
                for (const node of nodes) {
                    const rect = node.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    const aria = String(node.getAttribute('aria-label') || '').toLowerCase();
                    const ph = String(node.getAttribute('placeholder') || '').toLowerCase();
                    if (aria.includes('prompt') || ph.includes('prompt') || sel.includes('Prompt')) {
                        promptEl = node;
                        break;
                    }
                }
                if (promptEl) break;
            }
            let scope = promptEl;
            for (let depth = 0; depth < 12 && scope; depth++) {
                const rect = scope.getBoundingClientRect();
                const buttons = scope.querySelectorAll('button, [role=\"button\"]');
                let hasGenerate = false;
                for (const btn of buttons) {
                    const text = normalize(btn.innerText || btn.textContent || '').toLowerCase();
                    if (text === 'generate' || text.startsWith('generate ')) {
                        hasGenerate = true;
                        break;
                    }
                }
                if (hasGenerate && rect.width >= 240) break;
                scope = scope.parentElement;
            }
            const searchRoot = scope || document.body;
            const buttons = Array.from(searchRoot.querySelectorAll('button, [role=\"button\"]'));
            let best = null;
            for (const btn of buttons) {
                const rect = btn.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const text = normalize(btn.innerText || btn.textContent || '').toLowerCase();
                if (text !== 'generate' && !text.startsWith('generate ')) continue;
                if (isDisabled(btn)) continue;
                if (!best || rect.y > best.y) {
                    best = { el: btn, y: rect.y, text };
                }
            }
            if (!best) {
                return { clicked: false, reason: 'composer_generate_not_found' };
            }
            best.el.click();
            return {
                clicked: true,
                source: 'composer_scope',
                text: best.text,
                y: best.y,
            };
        }"""

    def click_video_generate_button_once(
        self,
        *,
        step_id: str | None = None,
        approved: bool = False,
    ) -> None:
        """Click the composer Generate button exactly once (no global fallback click)."""
        if is_approval_gated_control("generate_button"):
            if not approved and not can_execute_dangerous_action(
                "generate_button",
                step_id=step_id,
                approvals=self.approvals,
            ):
                raise PermissionError(dangerous_action_block_reason("generate_button"))

        if self.simulate:
            self.click_control(
                "generate_button",
                step_id=step_id,
                approved=approved,
            )
            return

        page = self._require_page()
        try:
            payload = page.evaluate(self._composer_generate_click_eval_script())
        except Exception as exc:
            raise RuntimeError(f"composer generate click failed: {exc}") from exc

        if not isinstance(payload, dict) or not payload.get("clicked"):
            reason = ""
            if isinstance(payload, dict):
                reason = str(payload.get("reason") or payload.get("error") or "")
            raise RuntimeError(
                f"composer generate click failed: {reason or 'button_not_found'}"
            )

        self._record(
            "click",
            control_key="generate_button",
            detail=(
                f"composer_once source={payload.get('source')}; "
                f"y={payload.get('y')}; text={payload.get('text')}"
            ),
            approved=approved,
        )
        time.sleep(0.35)

    def clear_video_generate_click_lock(self, clip_index: int | None = None) -> None:
        if clip_index is None:
            self._video_generate_click_sent_by_clip.clear()
            self._video_generate_submitted_clips.clear()
            return
        clip = max(1, int(clip_index))
        self._video_generate_click_sent_by_clip.pop(clip, None)
        self._video_generate_submitted_clips.discard(clip)

    @staticmethod
    def is_real_video_generation_in_progress(
        state: VideoGenerationProgressState,
        *,
        progress_text: str | None = None,
    ) -> bool:
        """Strong generation signals only — ignores notification banners and image cards."""
        text = str(progress_text if progress_text is not None else state.progress_text or "")
        lowered = text.lower()
        noise_markers = (
            "notification",
            "don't show",
            "show again",
            "get notifications",
            " later",
            " enable",
        )
        if lowered and any(marker in lowered for marker in noise_markers):
            text = ""
        if state.spinner_visible or state.output_loading:
            return True
        if state.stop_cancel_visible:
            return True
        if text:
            strong_markers = (
                "generating",
                "processing",
                "rendering",
                "queued",
                "in progress",
                "%",
            )
            if any(marker in lowered for marker in strong_markers):
                return True
        if (
            state.generate_button_disabled
            and state.pending_output_slot
            and (state.spinner_visible or state.stop_cancel_visible or state.output_loading)
        ):
            return True
        return False

    def prepare_video_generate_settings(self) -> VideoToolbarSettingsState:
        """Apply video toolbar chips when needed; never raises on mismatch."""
        aspect_texts = MENU_OPTION_TEXTS.get(
            (VIDEO_ASPECT_MENU_KEY, "aspect_ratio_9_16"),
            ("9:16", "9 : 16", "9: 16", "9 / 16"),
        )
        duration_texts = MENU_OPTION_TEXTS.get(
            (VIDEO_DURATION_MENU_KEY, "duration_10s"),
            ("10s", "10S", "10 s", "10 seconds"),
        )

        initial_row = self.read_toolbar_chip_row()
        self._capture_chip_diagnostic_screenshot("video_chips_initial", chip_row=initial_row)

        try:
            detected_aspect = self.ensure_menu_setting(
                VIDEO_ASPECT_MENU_KEY,
                "aspect_ratio_9_16",
                aspect_texts,
            )
        except Exception:
            detected_aspect = self.read_menu_display_value(VIDEO_ASPECT_MENU_KEY)

        try:
            detected_duration = self.ensure_menu_setting(
                VIDEO_DURATION_MENU_KEY,
                "duration_10s",
                duration_texts,
            )
        except Exception:
            detected_duration = self.read_menu_display_value(VIDEO_DURATION_MENU_KEY)

        aspect_ok = self._display_matches_expected(detected_aspect, aspect_texts)
        duration_ok = self._display_matches_expected(detected_duration, duration_texts)
        verified = aspect_ok and duration_ok

        final_row = self.read_toolbar_chip_row()
        self._capture_chip_diagnostic_screenshot(
            "video_chips_prepared" if verified else "video_chips_prepare_mismatch",
            chip_row=final_row,
        )

        state = VideoToolbarSettingsState(
            detected_aspect_ratio=detected_aspect,
            detected_duration=detected_duration,
            video_settings_verified=verified,
        )
        self.last_video_settings = state
        self._record(
            "video_settings_prepare",
            detail=(
                f"aspect={detected_aspect}; duration={detected_duration}; "
                f"verified={verified}"
            ),
        )
        return state

    def ensure_video_toolbar_settings_verified(self) -> VideoToolbarSettingsState:
        state = self.prepare_video_generate_settings()
        aspect_texts = MENU_OPTION_TEXTS.get(
            (VIDEO_ASPECT_MENU_KEY, "aspect_ratio_9_16"),
            ("9:16", "9 : 16", "9: 16", "9 / 16"),
        )
        duration_texts = MENU_OPTION_TEXTS.get(
            (VIDEO_DURATION_MENU_KEY, "duration_10s"),
            ("10s", "10S", "10 s", "10 seconds"),
        )
        if not self._display_matches_expected(state.detected_aspect_ratio, aspect_texts):
            raise RuntimeError(
                f"video aspect verification failed: expected one of {aspect_texts}, "
                f"detected {state.detected_aspect_ratio!r}"
            )
        if not self._display_matches_expected(state.detected_duration, duration_texts):
            raise RuntimeError(
                f"video duration verification failed: expected one of {duration_texts}, "
                f"detected {state.detected_duration!r}"
            )
        state.video_settings_verified = True
        self.last_video_settings = state
        self._record(
            "video_settings_verify_ok",
            detail=(
                f"aspect={state.detected_aspect_ratio}; "
                f"duration={state.detected_duration}"
            ),
        )
        return state

    def click_generate_when_ready(
        self,
        *,
        step_id: str | None = None,
        approved: bool = False,
        clip_index: int = 1,
        max_wait_seconds: float = 45.0,
    ) -> None:
        """Wait for composer Generate, submit exactly one clip generation job."""
        clip = max(1, clip_index)
        if self.simulate:
            self.click_control(
                "generate_button",
                step_id=step_id,
                approved=approved,
            )
            self.mark_clip_generating(clip)
            self._mark_video_generate_submitted(clip)
            return

        if self._is_video_generate_submitted(clip):
            gen = self.detect_video_generation_in_progress(clip)
            self._record(
                "generate_click_dedup_skip",
                control_key="generate_button",
                detail=(
                    f"clip={clip}; already_submitted; "
                    f"signals={','.join(gen.signals)}"
                ),
                approved=approved,
            )
            return

        gen = self.detect_video_generation_in_progress(clip)
        if self.is_real_video_generation_in_progress(gen) and not self.is_generate_button_actionable():
            self._mark_video_generate_submitted(clip)
            self._record(
                "generate_click_skipped_already_running",
                control_key="generate_button",
                detail=f"clip={clip}; signals={','.join(gen.signals)}",
                approved=approved,
            )
            return

        deadline = time.monotonic() + max(5.0, float(max_wait_seconds))
        poll_seconds = 0.75
        last_error = ""

        while time.monotonic() < deadline:
            self.prepare_video_generate_settings()
            if self.is_generate_button_actionable():
                break
            gen = self.detect_video_generation_in_progress(clip)
            if self.is_real_video_generation_in_progress(gen):
                self._mark_video_generate_submitted(clip)
                self._record(
                    "generate_click_skipped_already_running",
                    control_key="generate_button",
                    detail=f"clip={clip}; signals={','.join(gen.signals)}",
                    approved=approved,
                )
                return
            time.sleep(poll_seconds)
        else:
            raise RuntimeError(
                f"generate click timeout for clip {clip}: "
                f"{last_error or 'button_never_actionable'}"
            )

        before_cards = self._count_feed_video_cards()
        before = self.detect_video_generation_in_progress(clip)
        self._mark_video_generate_submitted(clip)

        try:
            self.click_video_generate_button_once(
                step_id=step_id,
                approved=approved,
            )
        except Exception as exc:
            self.clear_video_generate_click_lock(clip)
            raise RuntimeError(
                f"generate click failed for clip {clip}: {exc}"
            ) from exc

        confirm_deadline = time.monotonic() + 20.0
        while time.monotonic() < confirm_deadline:
            if self._generation_started_after_click(clip, before):
                after = self.detect_video_generation_in_progress(clip)
                self._record(
                    "generate_click_confirmed",
                    control_key="generate_button",
                    detail=(
                        f"clip={clip}; feed_cards={self._count_feed_video_cards()}; "
                        f"signals={','.join(after.signals)}"
                    ),
                    approved=approved,
                )
                return
            if self._count_feed_video_cards() > before_cards:
                self._record(
                    "generate_click_confirmed",
                    control_key="generate_button",
                    detail=(
                        f"clip={clip}; feed_cards={self._count_feed_video_cards()}; "
                        f"reason=new_feed_video_card"
                    ),
                    approved=approved,
                )
                return
            time.sleep(0.5)

        self._record(
            "generate_click_assumed",
            control_key="generate_button",
            detail=(
                f"clip={clip}; confirm_timeout; "
                f"feed_cards={self._count_feed_video_cards()}; "
                f"single_submit_policy"
            ),
            approved=approved,
        )

    def _sleep_ms(self, ms: int) -> None:
        if ms > 0:
            time.sleep(ms / 1000.0)

    def _select_toolbar_chip_option(
        self,
        menu_key: str,
        option_key: str,
        option_texts: tuple[str, ...],
    ) -> None:
        """Click a toolbar chip, wait for popover animation, hover, then click the target option."""
        texts = tuple(str(text).strip() for text in option_texts if str(text).strip())
        option_ctrl = self.control(option_key)
        chip_kind = TOOLBAR_CHIP_KIND_BY_MENU[menu_key]
        before_value = self.read_menu_display_value(menu_key)

        self._record(
            "chip_open",
            control_key=menu_key,
            detail=f"kind={chip_kind}; before={before_value}; target={texts}",
        )
        if self.simulate:
            self._record(
                "chip_select",
                control_key=option_key,
                detail=f"simulate texts={texts}; before={before_value}",
            )
            return

        if not self._click_toolbar_chip(menu_key):
            self._capture_chip_diagnostic_screenshot(f"chip_open_fail_{menu_key}")
            raise RuntimeError(f"toolbar chip click failed for {menu_key} ({chip_kind})")

        self._wait_for_chip_popover()
        self._record(
            "chip_popover_wait",
            control_key=menu_key,
            detail=f"delay_ms={CHIP_POPOVER_OPEN_DELAY_MS}",
        )
        self._sleep_ms(CHIP_POPOVER_OPEN_DELAY_MS)
        self._capture_chip_diagnostic_screenshot(f"chip_popover_open_{menu_key}")

        errors: list[str] = []
        for text in texts:
            try:
                locator = self._locate_popover_option_locator(text)
                if locator is None:
                    errors.append(f"text '{text}': option not visible in popover")
                    continue
                if self._human_like_locator_click(
                    locator,
                    menu_key=menu_key,
                    option_key=option_key,
                    option_text=text,
                    label_prefix="chip_option",
                ):
                    after_value = self.read_menu_display_value(menu_key)
                    self._record(
                        "chip_select",
                        control_key=option_key,
                        detail=f"text={text}; before={before_value}; after={after_value}",
                    )
                    return
                errors.append(f"text '{text}': human-like click failed")
            except Exception as exc:
                errors.append(f"text '{text}': {exc}")

        try:
            mapped_locator = self._locator_for(option_ctrl)
            mapped_text = texts[0] if texts else option_key
            if self._human_like_locator_click(
                mapped_locator,
                menu_key=menu_key,
                option_key=option_key,
                option_text=mapped_text,
                label_prefix="chip_option_mapped",
            ):
                after_value = self.read_menu_display_value(menu_key)
                self._record(
                    "chip_select",
                    control_key=option_key,
                    detail=f"mapped={option_key}; before={before_value}; after={after_value}",
                )
                return
            errors.append(f"mapped {option_key}: human-like click failed")
        except Exception as exc:
            errors.append(f"mapped {option_key}: {exc}")

        self._capture_chip_diagnostic_screenshot(f"chip_select_fail_{menu_key}_{option_key}")
        raise RuntimeError(
            f"toolbar chip selection failed for {menu_key} -> {option_key}: "
            + ("; ".join(errors) if errors else "no selector or text match in popover")
        )

    @staticmethod
    def _image_toolbar_chip_click_eval_script() -> str:
        return """({ chipKind }) => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const compact = (value) => normalize(value).replace(/\\s/g, '');
            const classify = (text) => {
                const t = normalize(text);
                const c = compact(t);
                if (t === '1' || t === '4') return 'count';
                if (/^\\d:\\d+$/.test(c) || /^\\d\\s*:\\s*\\d+$/.test(t)) return 'aspect';
                if (/^[124]K$/i.test(c)) return 'quality';
                if (/^\\d+\\s*s$/i.test(c) || /^\\d+s$/i.test(c)) return 'duration';
                return '';
            };
            const isButtonLike = (node) => {
                const tag = String(node.tagName || '').toLowerCase();
                if (tag === 'button') return true;
                return normalize(node.getAttribute('role') || '') === 'button';
            };
            const anchors = Array.from(document.querySelectorAll(
                '[aria-label*=\"Prompt\" i], textarea, [contenteditable=\"true\"]'
            ));
            let toolbarRoot = null;
            for (const anchor of anchors) {
                let node = anchor;
                for (let depth = 0; depth < 14 && node; depth++) {
                    const chips = [];
                    for (const child of node.querySelectorAll('button, [role=\"button\"]')) {
                        const rect = child.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) continue;
                        const text = normalize(child.innerText || child.textContent || '');
                        const kind = classify(text);
                        if (kind) chips.push({ child, kind, area: rect.width * rect.height });
                    }
                    const kinds = new Set(chips.map((c) => c.kind));
                    if (kinds.has('count') && kinds.has('aspect') && kinds.has('quality')) {
                        toolbarRoot = node;
                        break;
                    }
                    node = node.parentElement;
                }
                if (toolbarRoot) break;
            }
            const scope = toolbarRoot || document;
            const matches = [];
            for (const node of scope.querySelectorAll('button, [role=\"button\"]')) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const text = normalize(node.innerText || node.textContent || '');
                const kind = classify(text);
                if (kind !== chipKind) continue;
                let score = rect.width * rect.height;
                if (isButtonLike(node)) score += 500;
                matches.push({ node, score });
            }
            if (!matches.length) return false;
            matches.sort((a, b) => b.score - a.score);
            matches[0].node.click();
            return true;
        }"""

    def _click_toolbar_chip(self, menu_key: str) -> bool:
        page = self._require_page()
        chip_kind = TOOLBAR_CHIP_KIND_BY_MENU.get(menu_key)
        if not chip_kind:
            return False
        script = (
            self._image_toolbar_chip_click_eval_script()
            if menu_key in IMAGE_TOOLBAR_CHIP_MENU_KEYS
            and (self.simulate or self._on_image_generation_page())
            else self._toolbar_chip_click_eval_script()
        )
        try:
            clicked = page.evaluate(script, {"chipKind": chip_kind})
            return bool(clicked)
        except Exception:
            return False

    def _wait_for_chip_popover(self) -> None:
        if self.simulate:
            return
        page = self._require_page()
        deadline = time.monotonic() + 2.5
        selectors = (
            "[role='listbox'], [role='menu'], [role='dialog'], "
            "[data-radix-popper-content-wrapper], [data-radix-dialog-content], "
            "[data-state='open'][role='dialog']"
        )
        while time.monotonic() < deadline:
            try:
                surface = page.locator(selectors)
                if surface.count() > 0 and surface.first.is_visible():
                    return
            except Exception:
                pass
            time.sleep(0.15)
        time.sleep(0.2)

    def _locate_popover_option_locator(self, text: str):
        page = self._require_page()
        for exact in (True, False):
            try:
                role_locator = page.get_by_role("option", name=text, exact=exact)
                count = role_locator.count()
                for index in range(min(count, 6)):
                    candidate = role_locator.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                pass
        for exact in (True, False):
            try:
                text_locator = page.get_by_text(text, exact=exact)
                count = text_locator.count()
                for index in range(min(count, 8)):
                    candidate = text_locator.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                pass
        return None

    def _human_like_locator_click(
        self,
        locator,
        *,
        menu_key: str,
        option_key: str,
        option_text: str,
        label_prefix: str,
    ) -> bool:
        page = self._require_page()
        try:
            if not locator.is_visible():
                return False
        except Exception:
            return False

        try:
            locator.scroll_into_view_if_needed(timeout=self.menu_option_timeout_ms)
        except Exception:
            pass

        box: dict[str, float] | None = None
        try:
            box = locator.bounding_box()
        except Exception:
            box = None

        if box:
            center_x = box["x"] + (box["width"] / 2.0)
            center_y = box["y"] + (box["height"] / 2.0)
            self._record(
                "chip_option_box",
                control_key=option_key,
                detail=(
                    f"text={option_text}; "
                    f"x={box['x']:.1f}; y={box['y']:.1f}; "
                    f"w={box['width']:.1f}; h={box['height']:.1f}; "
                    f"center=({center_x:.1f},{center_y:.1f})"
                ),
            )
            self._capture_chip_diagnostic_screenshot(f"{label_prefix}_before_{menu_key}_{option_key}")

            mouse = getattr(page, "mouse", None)
            if mouse is not None:
                try:
                    mouse.move(center_x, center_y)
                    self._record(
                        "chip_hover",
                        control_key=option_key,
                        detail=(
                            f"text={option_text}; "
                            f"hover_ms={CHIP_OPTION_HOVER_DELAY_MS}; "
                            f"x={center_x:.1f}; y={center_y:.1f}"
                        ),
                    )
                    self._sleep_ms(CHIP_OPTION_HOVER_DELAY_MS)
                    mouse.click(center_x, center_y)
                    self._record(
                        "chip_mouse_click",
                        control_key=option_key,
                        detail=f"text={option_text}; after_click_ms={CHIP_AFTER_CLICK_VERIFY_DELAY_MS}",
                    )
                    self._capture_chip_diagnostic_screenshot(f"{label_prefix}_after_{menu_key}_{option_key}")
                    self._sleep_ms(CHIP_AFTER_CLICK_VERIFY_DELAY_MS)
                    return True
                except Exception:
                    pass

        try:
            locator.click(timeout=self.menu_option_timeout_ms, force=True)
            self._record(
                "chip_force_click",
                control_key=option_key,
                detail=f"text={option_text}; after_click_ms={CHIP_AFTER_CLICK_VERIFY_DELAY_MS}",
            )
            self._capture_chip_diagnostic_screenshot(f"{label_prefix}_after_force_{menu_key}_{option_key}")
            self._sleep_ms(CHIP_AFTER_CLICK_VERIFY_DELAY_MS)
            return True
        except Exception:
            return False

    def read_prompt_control_text(self, control_key: str) -> str:
        if self.simulate:
            return str(self._simulated_prompt_text.get(control_key, "") or "")

        page = self._require_page()
        ctrl = self.control(control_key)
        locator = self._locator_for(ctrl)
        try:
            value = locator.evaluate(
                """(el) => {
                    if (!el) return '';
                    if ('value' in el && el.value != null) return String(el.value);
                    return String(el.innerText || el.textContent || '');
                }"""
            )
            return self._normalize_display_value(str(value or ""))
        except Exception:
            return ""

    def clear_prompt_control(self, control_key: str) -> PromptClearResult:
        before = self.read_prompt_control_text(control_key)
        result = PromptClearResult(
            prompt_text_before_clear=before,
            prompt_text_after_clear=before,
            control_key=control_key,
            image_prompt_cleared=not bool(before.strip()),
        )
        if not before.strip():
            self._record("prompt_clear_skip", control_key=control_key, detail="already empty")
            self.last_prompt_clear = result
            return result

        self._record("prompt_clear", control_key=control_key, detail=f"chars={len(before)}")
        if self.simulate:
            self._simulated_prompt_text[control_key] = ""
            result.prompt_text_after_clear = ""
            result.image_prompt_cleared = True
            self.last_prompt_clear = result
            return result

        ctrl = self.control(control_key)
        locator = self._locator_for(ctrl)
        locator.click(force=True, timeout=self.prep_timeout_ms)
        time.sleep(0.15)
        page = self._require_page()
        keyboard = getattr(page, "keyboard", None)
        try:
            if keyboard is not None:
                keyboard.press("Control+A")
                keyboard.press("Backspace")
        except Exception:
            pass
        try:
            locator.fill("", timeout=self.prep_timeout_ms)
        except Exception:
            pass
        try:
            locator.evaluate(
                """(el) => {
                    el.focus();
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                        el.value = '';
                    } else {
                        el.textContent = '';
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }"""
            )
        except Exception:
            pass

        after = self.read_prompt_control_text(control_key)
        result.prompt_text_after_clear = after
        result.image_prompt_cleared = not bool(after.strip())
        if not result.image_prompt_cleared:
            self._capture_failure_screenshot(f"prompt_clear_fail_{control_key}")
            raise RuntimeError(
                f"prompt clear failed for {control_key}: still has {len(after)} chars after clear"
            )
        self.last_prompt_clear = result
        return result

    def ensure_prompt_control_empty(self, control_key: str) -> PromptClearResult:
        current = self.read_prompt_control_text(control_key)
        if current.strip():
            return self.clear_prompt_control(control_key)
        result = PromptClearResult(
            image_prompt_cleared=True,
            prompt_text_before_clear=current,
            prompt_text_after_clear=current,
            control_key=control_key,
        )
        self.last_prompt_clear = result
        return result

    def select_menu_option(
        self,
        menu_key: str,
        option_key: str,
        option_texts: tuple[str, ...] | list[str],
    ) -> None:
        """Open mapped control, then select option by mapped selector or visible text."""
        texts = tuple(str(text).strip() for text in option_texts if str(text).strip())
        if menu_key in TOOLBAR_CHIP_MENU_KEYS:
            self._select_toolbar_chip_option(menu_key, option_key, texts)
            return

        menu_ctrl = self.control(menu_key)
        option_ctrl = self.control(option_key)

        self._record(
            "menu_open",
            control_key=menu_key,
            detail=menu_ctrl.css_selector,
        )
        if self.simulate:
            self._record(
                "menu_select",
                control_key=option_key,
                detail=f"simulate texts={texts}",
            )
            return

        self._click_menu_opener(menu_key, menu_ctrl)
        self._wait_for_menu_surface()

        errors: list[str] = []

        if self._try_click_mapped_option(option_ctrl, option_key, errors):
            return

        for text in texts:
            try:
                if self._click_option_by_text(text):
                    self._record(
                        "menu_select",
                        control_key=option_key,
                        detail=f"text={text}",
                    )
                    time.sleep(0.25)
                    return
            except Exception as exc:
                errors.append(f"text '{text}': {exc}")

        self._capture_failure_screenshot(f"menu_select_fail_{menu_key}_{option_key}")
        raise RuntimeError(
            f"menu selection failed for {menu_key} -> {option_key}: "
            + ("; ".join(errors) if errors else "no selector or text match")
        )

    def _click_menu_opener(self, menu_key: str, menu_ctrl: ResolvedControl) -> None:
        if self.simulate:
            return
        page = self._require_page()
        self._record("click", control_key=menu_key, detail=menu_ctrl.css_selector)
        if menu_key in TOOLBAR_CHIP_MENU_KEYS and self._click_toolbar_chip(menu_key):
            time.sleep(self.menu_open_settle_seconds)
            return
        if self._click_toolbar_menu_opener(menu_key):
            time.sleep(self.menu_open_settle_seconds)
            return
        if selector_is_weak(menu_ctrl.css_selector) and menu_ctrl.text.strip():
            if self._click_visible_text(menu_ctrl.text.strip(), prefer_exact=False):
                time.sleep(self.menu_open_settle_seconds)
                return
        locator = self._locator_for(menu_ctrl)
        locator.click(timeout=self.prep_timeout_ms, force=True)
        time.sleep(self.menu_open_settle_seconds)

    def _click_toolbar_menu_opener(self, menu_key: str) -> bool:
        page = self._require_page()
        patterns = TOOLBAR_MENU_PATTERNS.get(menu_key, ())
        if not patterns:
            return False
        try:
            clicked = page.evaluate(
                """({ menuKey, patterns }) => {
                    const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const lower = (value) => normalize(value).toLowerCase();
                    const patternMatches = (text) => {
                        const target = lower(text);
                        if (!target) return false;
                        for (const pattern of patterns) {
                            const p = String(pattern || '').toLowerCase();
                            if (!p) continue;
                            if (target === p) return true;
                            if (p.includes(':') && target.replace(/\\s/g, '') === p.replace(/\\s/g, '')) return true;
                            if (p.endsWith('k') && target.replace(/\\s/g, '') === p.replace(/\\s/g, '')) return true;
                        }
                        return false;
                    };
                    const nodes = Array.from(
                        document.querySelectorAll('button, span, div, svg, [role=\"button\"]')
                    );
                    let best = null;
                    let bestScore = -1;
                    for (const node of nodes) {
                        const rect = node.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) continue;
                        if (rect.top < window.innerHeight * 0.45) continue;
                        const text = normalize(node.innerText || node.textContent || '');
                        const aria = normalize(node.getAttribute?.('aria-label') || '');
                        const probe = text || aria;
                        if (!patternMatches(probe)) continue;
                        const score = rect.top + rect.left / 10000;
                        if (score > bestScore) {
                            bestScore = score;
                            best = node;
                        }
                    }
                    if (!best) return false;
                    best.click();
                    return true;
                }""",
                {"menuKey": menu_key, "patterns": list(patterns)},
            )
            return bool(clicked)
        except Exception:
            return False

    def _wait_for_menu_surface(self) -> None:
        if self.simulate:
            return
        page = self._require_page()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                listbox = page.locator("[role='listbox'], [role='menu'], [data-radix-popper-content-wrapper]")
                if listbox.count() > 0 and listbox.first.is_visible():
                    return
            except Exception:
                pass
            time.sleep(0.15)
        time.sleep(0.2)

    def _try_click_mapped_option(
        self,
        option_ctrl: ResolvedControl,
        option_key: str,
        errors: list[str],
    ) -> bool:
        if self.simulate:
            return True
        page = self._require_page()
        css = option_ctrl.css_selector
        try:
            locator = page.locator(css).first
            if locator.count() > 0:
                locator.wait_for(state="visible", timeout=self.menu_option_timeout_ms)
                locator.click(timeout=self.menu_option_timeout_ms, force=True)
                self._record("menu_select", control_key=option_key, detail=f"mapped css={css}")
                time.sleep(0.25)
                return True
        except Exception as exc:
            errors.append(f"mapped selector '{css}': {exc}")

        if option_ctrl.text.strip():
            try:
                if self._click_option_by_text(option_ctrl.text.strip()):
                    self._record(
                        "menu_select",
                        control_key=option_key,
                        detail=f"mapped_text={option_ctrl.text.strip()}",
                    )
                    time.sleep(0.25)
                    return True
            except Exception as exc:
                errors.append(f"mapped control text '{option_ctrl.text.strip()}': {exc}")
        return False

    def _click_visible_text(self, text: str, *, prefer_exact: bool) -> bool:
        page = self._require_page()
        attempts = [prefer_exact, not prefer_exact] if prefer_exact else [False, True]
        for exact in attempts:
            try:
                locator = page.get_by_text(text, exact=exact)
                if locator.count() > 0 and locator.first.is_visible():
                    locator.first.click(timeout=self.menu_option_timeout_ms, force=True)
                    return True
            except Exception:
                continue
        return False

    def _click_option_by_text(self, text: str) -> bool:
        page = self._require_page()
        if self._click_visible_text(text, prefer_exact=True):
            return True
        if self._click_visible_text(text, prefer_exact=False):
            return True
        try:
            role_locator = page.get_by_role("option", name=text)
            if role_locator.count() > 0 and role_locator.first.is_visible():
                role_locator.first.click(timeout=self.menu_option_timeout_ms, force=True)
                return True
        except Exception:
            pass
        try:
            clicked = page.evaluate(
                """(label) => {
                    const normalized = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const target = normalized(label).toLowerCase();
                    const nodes = Array.from(document.querySelectorAll('[role=\"option\"], button, div, span, li'));
                    for (const node of nodes) {
                        const text = normalized(node.innerText || node.textContent || '');
                        if (!text) continue;
                        if (text.toLowerCase() === target || text.toLowerCase().includes(target)) {
                            const rect = node.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                node.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }""",
                text,
            )
            return bool(clicked)
        except Exception:
            return False

    @staticmethod
    def _generation_image_cards_eval_script() -> str:
        return """() => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const cards = [];
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            for (const btn of actionButtons) {
                const btnRect = btn.getBoundingClientRect();
                if (btnRect.width <= 0 || btnRect.height <= 0) continue;
                let card = btn;
                for (let depth = 0; depth < 10 && card; depth++) {
                    if (card.querySelector && card.querySelector(
                        'img, canvas, video, picture, [data-testid*=\"image\"], [data-testid*=\"Image\"]'
                    )) {
                        break;
                    }
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                const cardRect = card.getBoundingClientRect();
                if (cardRect.width <= 0 || cardRect.height <= 0) continue;
                const cardText = normalize(card.innerText || card.textContent || '');
                const cardFingerprint = [
                    Math.round(cardRect.left + window.scrollX),
                    Math.round(cardRect.top + window.scrollY),
                    Math.round(cardRect.width),
                    Math.round(cardRect.height),
                    cardText.slice(0, 120).toLowerCase(),
                ].join('|');
                cards.push({
                    cardTop: cardRect.top + window.scrollY,
                    cardBottom: cardRect.bottom + window.scrollY,
                    cardLeft: cardRect.left + window.scrollX,
                    cardWidth: cardRect.width,
                    cardHeight: cardRect.height,
                    cardPromptText: cardText.slice(0, 500),
                    cardFingerprint,
                    hasAppMenu: true,
                    actionsCenterX: btnRect.x + (btnRect.width / 2),
                    actionsCenterY: btnRect.y + (btnRect.height / 2),
                });
            }
            cards.sort((a, b) => b.cardBottom - a.cardBottom || b.cardTop - a.cardTop);
            return cards.map((card, index) => ({ ...card, cardIndex: index }));
        }"""

    @staticmethod
    def _generation_card_actions_click_eval_script() -> str:
        return """({ cardIndex }) => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const cards = [];
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            for (const btn of actionButtons) {
                const btnRect = btn.getBoundingClientRect();
                if (btnRect.width <= 0 || btnRect.height <= 0) continue;
                let card = btn;
                for (let depth = 0; depth < 10 && card; depth++) {
                    if (card.querySelector && card.querySelector(
                        'img, canvas, video, picture, [data-testid*=\"image\"], [data-testid*=\"Image\"]'
                    )) {
                        break;
                    }
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                const cardRect = card.getBoundingClientRect();
                if (cardRect.width <= 0 || cardRect.height <= 0) continue;
                cards.push({ btn, cardBottom: cardRect.bottom + window.scrollY, cardTop: cardRect.top + window.scrollY });
            }
            cards.sort((a, b) => b.cardBottom - a.cardBottom || b.cardTop - a.cardTop);
            const target = cards[cardIndex];
            if (!target || !target.btn) return false;
            target.btn.scrollIntoView({ block: 'center', inline: 'nearest' });
            target.btn.click();
            return true;
        }"""

    @staticmethod
    def _generation_card_scroll_eval_script() -> str:
        return """({ cardIndex }) => {
            const cards = [];
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            for (const btn of actionButtons) {
                const btnRect = btn.getBoundingClientRect();
                if (btnRect.width <= 0 || btnRect.height <= 0) continue;
                let card = btn;
                for (let depth = 0; depth < 10 && card; depth++) {
                    if (card.querySelector && card.querySelector(
                        'img, canvas, video, picture, [data-testid*=\"image\"], [data-testid*=\"Image\"]'
                    )) {
                        break;
                    }
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                const cardRect = card.getBoundingClientRect();
                if (cardRect.width <= 0 || cardRect.height <= 0) continue;
                cards.push({ card, cardBottom: cardRect.bottom + window.scrollY, cardTop: cardRect.top + window.scrollY });
            }
            cards.sort((a, b) => b.cardBottom - a.cardBottom || b.cardTop - a.cardTop);
            const target = cards[cardIndex];
            if (!target || !target.card) return false;
            target.card.scrollIntoView({ block: 'center', inline: 'nearest' });
            return true;
        }"""

    @staticmethod
    def _generation_card_remove_click_eval_script() -> str:
        return """({ cardFingerprint, cardIndex, hideLabels }) => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const normLabels = (hideLabels || []).map((label) => normalize(label).toLowerCase()).filter(Boolean);
            const cards = [];
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            for (const btn of actionButtons) {
                const btnRect = btn.getBoundingClientRect();
                if (btnRect.width <= 0 || btnRect.height <= 0) continue;
                let card = btn;
                for (let depth = 0; depth < 10 && card; depth++) {
                    if (card.querySelector && card.querySelector(
                        'img, canvas, video, picture, [data-testid*=\"image\"], [data-testid*=\"Image\"]'
                    )) {
                        break;
                    }
                    card = card.parentElement;
                }
                if (!card) card = btn.parentElement || btn;
                const cardRect = card.getBoundingClientRect();
                if (cardRect.width <= 0 || cardRect.height <= 0) continue;
                const cardText = normalize(card.innerText || card.textContent || '');
                cards.push({
                    card,
                    cardBottom: cardRect.bottom + window.scrollY,
                    cardTop: cardRect.top + window.scrollY,
                    cardFingerprint: [
                        Math.round(cardRect.left + window.scrollX),
                        Math.round(cardRect.top + window.scrollY),
                        Math.round(cardRect.width),
                        Math.round(cardRect.height),
                        cardText.slice(0, 120).toLowerCase(),
                    ].join('|'),
                });
            }
            cards.sort((a, b) => b.cardBottom - a.cardBottom || b.cardTop - a.cardTop);
            let target = null;
            if (cardFingerprint) {
                target = cards.find((item) => item.cardFingerprint === cardFingerprint) || null;
            }
            if (!target && typeof cardIndex === 'number' && cardIndex >= 0 && cardIndex < cards.length) {
                target = cards[cardIndex];
            }
            if (!target || !target.card) return false;
            target.card.scrollIntoView({ block: 'center', inline: 'nearest' });
            const buttons = Array.from(target.card.querySelectorAll('button, [role=\"button\"]'));
            for (const button of buttons) {
                const aria = normalize(button.getAttribute('aria-label') || '').toLowerCase();
                const title = normalize(button.getAttribute('title') || '').toLowerCase();
                const text = normalize(button.innerText || button.textContent || '').toLowerCase();
                for (const label of normLabels) {
                    if (
                        (aria && (aria === label || aria.includes(label)))
                        || (title && (title === label || title.includes(label)))
                        || (text && text === label)
                    ) {
                        button.click();
                        return true;
                    }
                }
            }
            return false;
        }"""

    def _current_page_url(self) -> str:
        if self.simulate:
            return self._simulated_page_url
        page = self.page
        if page is None:
            return ""
        url = getattr(page, "url", "")
        return str(url or "")

    def _ensure_simulated_generation_cards(self, prompt_text: str | None = None) -> None:
        if not self.simulate or self._simulated_generation_cards is not None:
            return
        prompt = str(prompt_text or "simulated starter prompt").strip()
        self._simulated_generation_cards = [
            {
                "cardIndex": 0,
                "cardTop": 120.0,
                "cardBottom": 420.0,
                "cardLeft": 40.0,
                "cardWidth": 280.0,
                "cardHeight": 300.0,
                "cardPromptText": "older generated image",
                "hasAppMenu": True,
            },
            {
                "cardIndex": 1,
                "cardTop": 520.0,
                "cardBottom": 920.0,
                "cardLeft": 40.0,
                "cardWidth": 280.0,
                "cardHeight": 400.0,
                "cardPromptText": prompt,
                "hasAppMenu": True,
            },
        ]
        self._simulated_page_url = (
            "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=image"
        )

    def _fingerprint_for_card(self, card: dict[str, Any]) -> str:
        existing = str(card.get("cardFingerprint") or "").strip()
        if existing:
            return existing
        text = self._normalize_display_value(str(card.get("cardPromptText") or "")).lower()[:120]
        return "|".join(
            [
                str(int(round(float(card.get("cardLeft") or 0)))),
                str(int(round(float(card.get("cardTop") or 0)))),
                str(int(round(float(card.get("cardWidth") or 0)))),
                str(int(round(float(card.get("cardHeight") or 0)))),
                text,
            ]
        )

    def _mark_image_card_consumed(self, fingerprint: str) -> None:
        cleaned = str(fingerprint or "").strip()
        if not cleaned:
            return
        self._consumed_image_card_fingerprints.add(cleaned)
        self._record(
            "image_card_mark_consumed",
            control_key="image_card_remove_button",
            detail=f"fingerprint={cleaned}",
        )

    def _filter_unconsumed_cards(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._consumed_image_card_fingerprints:
            return list(cards)
        return [
            card
            for card in cards
            if self._fingerprint_for_card(card) not in self._consumed_image_card_fingerprints
        ]

    def _normalize_scanned_generation_cards(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [dict(card) for card in cards]
        normalized.sort(
            key=lambda card: (
                -float(card.get("cardBottom") or 0),
                -float(card.get("cardTop") or 0),
            )
        )
        for index, card in enumerate(normalized):
            card["cardIndex"] = index
            card["cardFingerprint"] = self._fingerprint_for_card(card)
        return normalized

    def configure_phase_i_artifact_tracking(
        self,
        *,
        project_id: str,
        session_id: str = "",
        download_strategy: str = "cdp_preferred",
        fallback_to_ui_download: bool = True,
        clip_count: int = 3,
    ) -> PhaseIArtifactTracker:
        self._phase_i_project_id = str(project_id or "phase_i")
        self._phase_i_clip_count = max(1, int(clip_count or 1))
        tracker = self.phase_i_artifact_tracker()
        tracker._phase_i_clip_count = self._phase_i_clip_count
        if self.simulate and not tracker._simulated_cards:
            tracker.simulate_add_card(card_type="image", prompt_text="starter image")
        self._phase_i_cdp_downloader = None
        self._phase_i_session_id = str(session_id or "")
        self._phase_i_download_strategy = download_strategy
        self._phase_i_fallback_ui = fallback_to_ui_download
        return tracker

    def clip_prompt_match_tokens(self, clip_index: int) -> list[str]:
        from content_brain.execution.runway_phase_i_strict_completion_gate import (
            build_clip_match_tokens,
        )

        clip_count = int(getattr(self, "_phase_i_clip_count", 3) or 3)
        return build_clip_match_tokens(clip_index, clip_count)

    def phase_i_artifact_tracker(self) -> PhaseIArtifactTracker:
        if self._phase_i_artifact_tracker is None:
            self._phase_i_artifact_tracker = PhaseIArtifactTracker(
                simulate=self.simulate,
                page=self.page,
                project_id=self._phase_i_project_id,
            )
        return self._phase_i_artifact_tracker

    def _register_starter_image_assignment(self) -> None:
        tracker = self.phase_i_artifact_tracker()
        latest = self.last_latest_image_card
        if latest is None or not latest.latest_image_card_found:
            return
        tracker.assignments[ROLE_STARTER_IMAGE] = PhaseIArtifactCard(
            card_index=latest.latest_image_card_index,
            card_fingerprint=latest.selected_image_card_fingerprint,
            card_type="image",
            card_prompt_text=latest.card_prompt_text,
            bounding_box=dict(latest.card_bounding_box),
            role=ROLE_STARTER_IMAGE,
        )
        if latest.selected_image_card_fingerprint:
            tracker._snapshot_fps.add(latest.selected_image_card_fingerprint)

    def ensure_clip_video_card_assigned(self, clip_index: int) -> PhaseIArtifactCard | None:
        """Detect/assign latest video card for clip N before any in-card control use."""
        card = self.phase_i_artifact_tracker().assign_latest_video_card_for_clip(clip_index)
        if card is not None:
            self._record(
                "latest_video_card_assigned",
                detail=f"clip={clip_index}; fp={card.card_fingerprint}",
            )
        return card

    def is_label_visible_in_clip_video_card(
        self,
        clip_index: int,
        labels: tuple[str, ...],
    ) -> bool:
        """Detect/assign latest video card, then check labels only inside that card."""
        if self.ensure_clip_video_card_assigned(clip_index) is None:
            return False
        return self.phase_i_artifact_tracker().label_visible_on_latest_video_card(labels)

    def assign_clip_video_artifact(self, clip_index: int) -> PhaseIArtifactCard | None:
        card = self.ensure_clip_video_card_assigned(clip_index)
        tracker = self.phase_i_artifact_tracker()
        role = PhaseIArtifactTracker.clip_video_role(clip_index)
        if card is None:
            tracker.write_diagnostics(
                context=f"assign_clip_{clip_index}_failed",
                extra={"clip_index": clip_index},
            )
        else:
            self._record(
                "artifact_assign_clip_video",
                detail=f"clip={clip_index}; fp={card.card_fingerprint}; type={card.card_type}",
            )
        return card

    def click_use_frame_for_next_clip(self, clip_index: int) -> bool:
        """Use Frame inside the prior clip video card only (clip 2 uses clip 1 card)."""
        import time as _time

        tracker = self.phase_i_artifact_tracker()
        source_index = max(1, int(clip_index) - 1)
        source_role = PhaseIArtifactTracker.clip_video_role(source_index)
        tracker.ensure_starter_not_used_for_clip_ops(clip_index)
        max_attempts = 5 if not self.simulate else 1
        for attempt in range(1, max_attempts + 1):
            self.ensure_clip_video_card_assigned(source_index)
            tracker.refresh_assigned_card_from_scan(source_index)
            if tracker.click_label_on_assigned_card(source_role, USE_FRAME_LABELS):
                self._record(
                    "use_frame_scoped",
                    detail=(
                        f"target_clip={clip_index}; source_clip={source_index}; "
                        f"role={source_role}; scope=source_clip_card; attempt={attempt}"
                    ),
                )
                return True
            if tracker.click_label_on_latest_video_card(USE_FRAME_LABELS):
                self._record(
                    "use_frame_scoped",
                    detail=(
                        f"target_clip={clip_index}; source_clip={source_index}; "
                        f"role=latest_video_card; scope=expanded_below_video; attempt={attempt}"
                    ),
                )
                return True
            if attempt < max_attempts:
                self._sleep_ms(700)
                _time.sleep(0.25)
        self._record(
            "use_frame_scoped_failed",
            detail=(
                f"target_clip={clip_index}; source_clip={source_index}; "
                f"no_in_card_use_frame; global_disabled; attempts={max_attempts}"
            ),
        )
        return False

    def prepare_last_frame_use_frame_for_clip(
        self,
        target_clip_index: int,
        *,
        allow_first_frame_fallback: bool = False,
    ) -> Any:
        """Seek previous clip video to last safe frame, then scoped Use Frame for target clip."""
        from content_brain.execution.runway_phase_i_last_frame_use_frame import (
            LastFrameUseFrameResult,
            prepare_last_frame_use_frame_for_clip,
        )

        target = max(2, int(target_clip_index))
        payload = prepare_last_frame_use_frame_for_clip(
            self,
            target,
            allow_first_frame_fallback=allow_first_frame_fallback,
        )
        self.last_last_frame_use_frame_by_clip[target] = payload
        self._record(
            "last_frame_use_frame_prepare",
            detail=(
                f"target={target}; source={payload.use_frame_source_clip}; "
                f"seeked={payload.previous_clip_seeked_to_last_frame}; "
                f"seek={payload.seek_time_used}; strategy={payload.seek_strategy}; "
                f"source={payload.use_frame_source}"
            ),
        )
        return payload

    def download_assigned_clip_video(
        self,
        clip_index: int,
        *,
        approved: bool = False,
        step_id: str | None = None,
    ) -> ClipDownloadAttempt:
        if self._phase_i_cdp_downloader is None:
            session_id = getattr(self, "_phase_i_session_id", "")
            config = RunwayPhaseICdpDownloadConfig(
                download_strategy=getattr(self, "_phase_i_download_strategy", "cdp_preferred"),
                fallback_to_ui_download=getattr(self, "_phase_i_fallback_ui", True),
                session_id=session_id,
            )

            clip_role = PhaseIArtifactTracker.clip_video_role(clip_index)

            def _ui_click() -> None:
                self.ensure_clip_video_card_assigned(clip_index)
                self.phase_i_artifact_tracker().click_label_on_latest_video_card(
                    DOWNLOAD_LABELS,
                )

            self._phase_i_cdp_downloader = RunwayPhaseICdpDownloader(
                download_dir=default_runway_download_dir(ROOT),
                tracker=self.phase_i_artifact_tracker(),
                simulate=self.simulate,
                project_id=self._phase_i_project_id,
                config=config,
                page=self.page,
                ui_download_click=_ui_click,
            )
        attempt = self._phase_i_cdp_downloader.download_clip(clip_index)
        self.last_clip_download_attempts[clip_index] = attempt
        self._record(
            "clip_download_attempt",
            detail=(
                f"clip={clip_index}; strategy={attempt.strategy}; "
                f"scoped={attempt.scoped_to_card}; ok={attempt.downloaded}"
            ),
        )
        return attempt

    def snapshot_generation_image_cards_before_generate(self) -> GenerationImageCardSnapshot:
        """Capture visible generation cards immediately before image_generate_button."""
        if self.simulate and self._simulated_generation_cards is None:
            self._simulated_generation_cards = [
                {
                    "cardTop": 80.0,
                    "cardBottom": 360.0,
                    "cardLeft": 20.0,
                    "cardWidth": 260.0,
                    "cardHeight": 280.0,
                    "cardPromptText": "older image output",
                    "hasAppMenu": True,
                }
            ]
        cards = self.scan_generation_image_cards()
        fingerprints = tuple(card["cardFingerprint"] for card in cards)
        snapshot = GenerationImageCardSnapshot(
            card_count=len(cards),
            fingerprints=fingerprints,
        )
        self._pre_generate_card_snapshot = snapshot
        self.phase_i_artifact_tracker().snapshot_before_generation(phase="starter_image")
        self._record(
            "image_cards_snapshot_before_generate",
            control_key="image_generate_button",
            detail=f"count={snapshot.card_count}; fingerprints={list(fingerprints)}",
        )
        return snapshot

    @staticmethod
    def _preclean_starter_image_workspace_eval_script() -> str:
        return """() => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const unsafe = /(delete account|remove account|sign out|log out|logout|billing|upgrade plan|delete project|discard project)/i;
            const notes = [];
            let staleDetected = false;
            let closed = false;

            const tryCloseButton = (button, reason) => {
                const label = normalize(
                    button.getAttribute('aria-label') || button.innerText || button.textContent || ''
                );
                if (!label || unsafe.test(label)) return false;
                if (
                    label === 'close'
                    || label.includes('close')
                    || label === 'dismiss'
                    || label === '×'
                    || label === 'x'
                ) {
                    const rect = button.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        button.click();
                        notes.push(reason);
                        return true;
                    }
                }
                return false;
            };

            const overlays = Array.from(document.querySelectorAll(
                '[role=\"dialog\"], [aria-modal=\"true\"], [data-state=\"open\"]'
            ));
            for (const overlay of overlays) {
                const overlayText = normalize(overlay.innerText || overlay.textContent || '');
                if (unsafe.test(overlayText)) {
                    notes.push('skipped_unsafe_overlay');
                    continue;
                }
                staleDetected = true;
                const buttons = Array.from(overlay.querySelectorAll('button, [role=\"button\"]'));
                for (const button of buttons) {
                    if (tryCloseButton(button, 'closed_overlay')) {
                        closed = true;
                        break;
                    }
                }
            }

            const previewCloseButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Close\"], button[aria-label*=\"Close\"], button[aria-label*=\"close\"]'
            ));
            for (const button of previewCloseButtons) {
                staleDetected = true;
                if (tryCloseButton(button, 'closed_preview_close_button')) {
                    closed = true;
                    break;
                }
            }

            return { staleDetected, closed, notes };
        }"""

    def preclean_starter_image_workspace(self) -> StarterImagePrecleanState:
        """Close safe stale image previews/modals before starter image Generate."""
        state = StarterImagePrecleanState(preclean_attempted=True)
        if self.simulate:
            if self._simulated_stale_preview_open:
                state.stale_image_preview_detected = True
                state.stale_preview_closed = True
                state.preclean_notes.append("simulate: closed stale preview overlay")
                self._simulated_stale_preview_open = False
            else:
                state.preclean_notes.append("simulate: no stale preview detected")
            self.last_preclean = state
            self._record(
                "starter_image_preclean",
                detail=(
                    f"stale={state.stale_image_preview_detected}; "
                    f"closed={state.stale_preview_closed}; "
                    f"notes={state.preclean_notes}"
                ),
            )
            return state

        page = self._require_page()
        try:
            result = page.evaluate(self._preclean_starter_image_workspace_eval_script())
        except Exception as exc:
            state.preclean_notes.append(f"preclean_eval_failed: {exc}")
            self.last_preclean = state
            self._record("starter_image_preclean", detail=str(exc))
            return state

        payload = result if isinstance(result, dict) else {}
        state.stale_image_preview_detected = bool(payload.get("staleDetected"))
        state.stale_preview_closed = bool(payload.get("closed"))
        notes = payload.get("notes") or []
        if isinstance(notes, list):
            state.preclean_notes.extend(str(item) for item in notes)
        elif notes:
            state.preclean_notes.append(str(notes))
        if not state.stale_image_preview_detected:
            state.preclean_notes.append("no stale preview detected")
        elif not state.stale_preview_closed:
            state.preclean_notes.append("stale preview detected but no safe close clicked")

        self.last_preclean = state
        self._record(
            "starter_image_preclean",
            detail=(
                f"stale={state.stale_image_preview_detected}; "
                f"closed={state.stale_preview_closed}; "
                f"notes={state.preclean_notes}"
            ),
        )
        self._capture_chip_diagnostic_screenshot("starter_image_preclean")
        return state

    def _diff_new_generation_cards(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        snapshot = self._pre_generate_card_snapshot
        cards = self._filter_unconsumed_cards(cards)
        if snapshot is None:
            return list(cards)

        before_fps = set(snapshot.fingerprints)
        new_cards = [
            card
            for card in cards
            if self._fingerprint_for_card(card) not in before_fps
        ]
        if new_cards:
            return new_cards

        if len(cards) > snapshot.card_count:
            return cards[: len(cards) - snapshot.card_count]

        return []

    def _pick_best_generation_card(
        self,
        candidates: list[dict[str, Any]],
        prompt_text: str | None,
        *,
        reason_prefix: str,
    ) -> tuple[dict[str, Any] | None, str]:
        if not candidates:
            return None, f"{reason_prefix}_none"

        prompt_norm = self._normalize_display_value(prompt_text or "").lower()
        prompt_matches = [
            card
            for card in candidates
            if prompt_norm
            and (
                prompt_norm in str(card.get("cardPromptText") or "").lower()
                or (
                    len(prompt_norm) > 24
                    and prompt_norm[:40] in str(card.get("cardPromptText") or "").lower()
                )
            )
        ]

        if len(prompt_matches) == 1:
            return prompt_matches[0], f"{reason_prefix}_prompt_match"
        if len(prompt_matches) > 1:
            best = max(prompt_matches, key=lambda card: float(card.get("cardBottom") or 0))
            return best, f"{reason_prefix}_prompt_match_bottom_most"

        best = max(candidates, key=lambda card: float(card.get("cardBottom") or 0))
        if len(candidates) > 1:
            return best, f"{reason_prefix}_bottom_most"
        return best, f"{reason_prefix}_single_candidate"

    def _ensure_simulated_post_generate_cards(self, prompt_text: str | None = None) -> None:
        if not self.simulate or self._pre_generate_card_snapshot is None:
            return
        if self._simulated_generation_cards is None:
            self._simulated_generation_cards = []
        if len(self._simulated_generation_cards) > self._pre_generate_card_snapshot.card_count:
            return

        prompt = str(prompt_text or "simulated starter prompt").strip()
        self._simulated_generation_cards.append(
            {
                "cardTop": 480.0,
                "cardBottom": 880.0,
                "cardLeft": 20.0,
                "cardWidth": 260.0,
                "cardHeight": 400.0,
                "cardPromptText": prompt,
                "hasAppMenu": True,
            }
        )

    def scan_generation_image_cards(self) -> list[dict[str, Any]]:
        if self.simulate:
            if self._simulated_generation_cards is None:
                return []
            cards = [dict(card) for card in self._simulated_generation_cards]
            return self._normalize_scanned_generation_cards(cards)

        page = self._require_page()
        try:
            payload = page.evaluate(self._generation_image_cards_eval_script())
            if isinstance(payload, list):
                cards = [dict(item) for item in payload if isinstance(item, dict)]
                return self._normalize_scanned_generation_cards(cards)
        except Exception:
            pass
        return []

    def select_latest_generated_image_card(
        self,
        prompt_text: str | None = None,
    ) -> LatestGeneratedImageCardState:
        if self.simulate and self._pre_generate_card_snapshot is not None:
            self._ensure_simulated_post_generate_cards(prompt_text)
        elif self.simulate and self._simulated_generation_cards is None and self._pre_generate_card_snapshot is None:
            self._ensure_simulated_generation_cards(prompt_text)

        cards = self.scan_generation_image_cards()
        pre_count = self._pre_generate_card_snapshot.card_count if self._pre_generate_card_snapshot else 0
        self._record(
            "latest_image_card_scan",
            detail=f"count={len(cards)}; pre_count={pre_count}",
        )
        if not cards:
            state = LatestGeneratedImageCardState(
                latest_image_card_found=False,
                pre_generate_card_count=pre_count,
                selection_reason="no_cards_visible",
            )
            self.last_latest_image_card = state
            return state

        if self._pre_generate_card_snapshot is not None:
            candidates = self._diff_new_generation_cards(cards)
            reason_prefix = "new_card_diff"
        else:
            candidates = self._filter_unconsumed_cards(list(cards))
            reason_prefix = "bottom_most_fallback"

        best, reason = self._pick_best_generation_card(candidates, prompt_text, reason_prefix=reason_prefix)
        if best is None:
            state = LatestGeneratedImageCardState(
                latest_image_card_found=False,
                pre_generate_card_count=pre_count,
                new_card_candidates_count=len(candidates),
                selection_reason="no_new_card_after_generate" if self._pre_generate_card_snapshot else "no_candidate",
            )
            self.last_latest_image_card = state
            return state

        card_fingerprint = self._fingerprint_for_card(best)
        state = LatestGeneratedImageCardState(
            latest_image_card_found=True,
            latest_image_card_index=int(best.get("cardIndex", -1)),
            selected_image_card_fingerprint=card_fingerprint,
            card_prompt_text=str(best.get("cardPromptText") or "")[:500],
            card_bounding_box={
                "x": float(best.get("cardLeft") or 0),
                "y": float(best.get("cardTop") or 0),
                "width": float(best.get("cardWidth") or 0),
                "height": float(best.get("cardHeight") or 0),
            },
            app_menu_available=bool(best.get("hasAppMenu", True)),
            selection_reason=reason,
            pre_generate_card_count=pre_count,
            new_card_candidates_count=len(candidates),
        )
        self._record(
            "latest_image_card_select",
            detail=(
                f"index={state.latest_image_card_index}; "
                f"fingerprint={card_fingerprint}; "
                f"reason={reason}; "
                f"pre_count={pre_count}; "
                f"candidates={len(candidates)}; "
                f"prompt={state.card_prompt_text[:120]!r}; "
                f"box={state.card_bounding_box}"
            ),
        )
        self.last_latest_image_card = state
        return state

    def scroll_latest_image_card_into_view(self) -> None:
        state = self.last_latest_image_card
        if state is None or not state.latest_image_card_found:
            raise RuntimeError("latest generated image card not selected")

        self._capture_chip_diagnostic_screenshot("latest_image_before_scroll")
        if self.simulate:
            self._record(
                "latest_image_scroll",
                detail=f"index={state.latest_image_card_index}",
            )
            self._capture_chip_diagnostic_screenshot("latest_image_after_scroll")
            return

        page = self._require_page()
        scrolled = page.evaluate(
            self._generation_card_scroll_eval_script(),
            {"cardIndex": state.latest_image_card_index},
        )
        if not scrolled:
            self._capture_chip_diagnostic_screenshot("latest_image_scroll_fail")
            raise RuntimeError(
                f"failed to scroll latest image card into view (index={state.latest_image_card_index})"
            )
        self._sleep_ms(500)
        self._record(
            "latest_image_scroll",
            detail=f"index={state.latest_image_card_index}",
        )
        self._capture_chip_diagnostic_screenshot("latest_image_after_scroll")

    def locate_and_prepare_latest_image_card(
        self,
        prompt_text: str | None = None,
    ) -> LatestGeneratedImageCardState:
        state = self.select_latest_generated_image_card(prompt_text)
        if not state.latest_image_card_found:
            self._capture_chip_diagnostic_screenshot("latest_image_not_found")
            if self._pre_generate_card_snapshot is not None:
                raise RuntimeError(
                    "no newly added image card detected after generation "
                    f"(pre_count={state.pre_generate_card_count}; "
                    f"candidates={state.new_card_candidates_count})"
                )
            raise RuntimeError("latest generated image card not found")

        self.scroll_latest_image_card_into_view()
        if not state.app_menu_available:
            self._capture_chip_diagnostic_screenshot("latest_image_no_app_menu")
            raise RuntimeError("latest image card has no app menu button")
        return state

    def _popover_has_use_to_video_option(self) -> bool:
        texts = click_control_texts_for(
            "image_use_to_video_option",
            self.control("image_use_to_video_option"),
        )
        for text in texts:
            locator = self._locate_popover_option_locator(text)
            if locator is not None:
                try:
                    if locator.is_visible():
                        return True
                except Exception:
                    continue
        return False

    def open_app_menu_on_latest_image_card(self) -> None:
        state = self.last_latest_image_card
        if state is None or not state.latest_image_card_found:
            raise RuntimeError("latest image card not located before opening app menu")

        if self.simulate:
            state.use_to_video_available = True
            self.last_latest_image_card = state
            self._record(
                "latest_image_app_menu_open",
                detail=f"index={state.latest_image_card_index}; simulate=true",
            )
            self._capture_chip_diagnostic_screenshot("latest_image_app_menu_open")
            return

        if not self._click_actions_button_on_card(state.latest_image_card_index):
            self._capture_chip_diagnostic_screenshot("latest_image_app_menu_open_fail")
            raise RuntimeError(
                f"failed to open app menu on latest image card (index={state.latest_image_card_index})"
            )

        self._sleep_ms(CHIP_POPOVER_OPEN_DELAY_MS)
        self._capture_chip_diagnostic_screenshot("latest_image_app_menu_open")
        if not self._popover_has_use_to_video_option():
            self._capture_chip_diagnostic_screenshot("latest_image_no_use_to_video")
            raise RuntimeError("latest image card app menu missing Use to Video option")

        state.use_to_video_available = True
        self.last_latest_image_card = state
        self._record(
            "latest_image_app_menu_open",
            detail=f"index={state.latest_image_card_index}; use_to_video=true",
        )

    def _click_actions_button_on_card(self, card_index: int) -> bool:
        page = self._require_page()
        try:
            clicked = page.evaluate(
                self._generation_card_actions_click_eval_script(),
                {"cardIndex": card_index},
            )
            return bool(clicked)
        except Exception:
            return False

    def click_use_to_video_on_latest_image_card(self) -> None:
        state = self.last_latest_image_card
        if state is None or not state.latest_image_card_found:
            raise RuntimeError("latest image card not located before Use to Video")

        if self.simulate:
            self._simulated_video_mode = True
            self._simulated_page_url = (
                "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video"
            )
            state.use_to_video_available = True
            self.last_latest_image_card = state
            self._record(
                "latest_image_use_to_video",
                detail=f"index={state.latest_image_card_index}; simulate=true",
            )
            self._capture_chip_diagnostic_screenshot("latest_image_after_use_to_video")
            return

        if not state.use_to_video_available and not self._popover_has_use_to_video_option():
            if not self._click_actions_button_on_card(state.latest_image_card_index):
                raise RuntimeError("failed to reopen app menu before Use to Video")
            self._sleep_ms(CHIP_POPOVER_OPEN_DELAY_MS)

        texts = click_control_texts_for(
            "image_use_to_video_option",
            self.control("image_use_to_video_option"),
        )
        errors: list[str] = []
        for text in texts:
            locator = self._locate_popover_option_locator(text)
            if locator is None:
                errors.append(f"text '{text}': option not visible")
                continue
            if self._human_like_locator_click(
                locator,
                menu_key="image_use_to_video_option",
                option_key="image_use_to_video_option",
                option_text=text,
                label_prefix="latest_image_use_to_video",
            ):
                self._record(
                    "latest_image_use_to_video",
                    detail=f"index={state.latest_image_card_index}; text={text}",
                )
                self._capture_chip_diagnostic_screenshot("latest_image_after_use_to_video")
                return
            errors.append(f"text '{text}': click failed")

        self._capture_chip_diagnostic_screenshot("latest_image_use_to_video_fail")
        raise RuntimeError(
            "Use to Video click failed on latest image card: "
            + ("; ".join(errors) if errors else "no visible option")
        )

    @staticmethod
    def _use_for_video_candidates_eval_script() -> str:
        labels_json = json.dumps(list(USE_FOR_VIDEO_ACTION_LABELS))
        return f"""(payload) => {{
            const labels = {labels_json}.map((value) => String(value || '').toLowerCase());
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const cardIndex = typeof payload.cardIndex === 'number' ? payload.cardIndex : -1;
            const actionButtons = Array.from(document.querySelectorAll(
                'button[aria-label=\"Actions\"], button[aria-label*=\"Actions\"], [aria-label=\"Actions\"]'
            ));
            const cards = [];
            for (const btn of actionButtons) {{
                const btnRect = btn.getBoundingClientRect();
                if (btnRect.width <= 0 || btnRect.height <= 0) continue;
                let card = btn;
                for (let depth = 0; depth < 10 && card; depth++) {{
                    if (card.querySelector && card.querySelector(
                        'img, canvas, video, picture, [data-testid*=\"image\"], [data-testid*=\"Image\"]'
                    )) {{
                        break;
                    }}
                    card = card.parentElement;
                }}
                if (!card) card = btn.parentElement || btn;
                const cardRect = card.getBoundingClientRect();
                if (cardRect.width <= 0 || cardRect.height <= 0) continue;
                cards.push({{ card, cardBottom: cardRect.bottom }});
            }}
            cards.sort((a, b) => b.cardBottom - a.cardBottom);
            const target = cardIndex >= 0 && cardIndex < cards.length ? cards[cardIndex].card : (cards[0] && cards[0].card);
            if (!target) return {{ candidates: [], clicked: false, clickedLabel: '' }};

            const candidates = [];
            const buttons = Array.from(target.querySelectorAll('button, [role=\"button\"], a'));
            for (const button of buttons) {{
                const aria = normalize(button.getAttribute('aria-label') || '');
                const title = normalize(button.getAttribute('title') || '');
                const text = normalize(button.innerText || button.textContent || '');
                const disabled = button.disabled || button.getAttribute('aria-disabled') === 'true';
                const rect = button.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                for (const label of labels) {{
                    const fields = [aria, title, text].filter(Boolean);
                    const matched = fields.some((field) => field === label || field.includes(label));
                    if (!matched) continue;
                    const display = text || aria || title || label;
                    candidates.push({{
                        label: display,
                        aria,
                        text,
                        enabled: !disabled,
                        inLatestCard: true,
                    }});
                    break;
                }}
            }}

            candidates.sort((a, b) => Number(b.enabled) - Number(a.enabled));
            for (const candidate of candidates) {{
                if (!candidate.enabled) continue;
                for (const button of buttons) {{
                    const aria = normalize(button.getAttribute('aria-label') || '');
                    const text = normalize(button.innerText || button.textContent || '');
                    const display = text || aria;
                    if (display !== candidate.label && aria !== candidate.label && text !== candidate.label) {{
                        continue;
                    }}
                    button.click();
                    return {{
                        candidates,
                        clicked: true,
                        clickedLabel: candidate.label,
                    }};
                }}
            }}
            return {{ candidates, clicked: false, clickedLabel: '' }};
        }}"""

    def _scan_use_for_video_candidates_on_card(self, card_index: int) -> list[str]:
        if self.simulate:
            return ["Use for Video", "Use to Video"]
        page = self._require_page()
        try:
            result = page.evaluate(
                self._use_for_video_candidates_eval_script(),
                {"cardIndex": card_index},
            )
        except Exception:
            return []
        payload = result if isinstance(result, dict) else {}
        candidates = payload.get("candidates") or []
        labels: list[str] = []
        for item in candidates:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("text") or "").strip()
                if label:
                    labels.append(label)
        return labels

    def _click_direct_use_for_video_on_card(self, card_index: int) -> str:
        if self.simulate:
            return "Use for Video"
        page = self._require_page()
        result = page.evaluate(
            self._use_for_video_candidates_eval_script(),
            {"cardIndex": card_index},
        )
        payload = result if isinstance(result, dict) else {}
        candidates = payload.get("candidates") or []
        labels = [
            str(item.get("label") or item.get("text") or "")
            for item in candidates
            if isinstance(item, dict)
        ]
        state = self.last_latest_image_card
        if state is not None:
            state.use_for_video_candidates = [label for label in labels if label]
            self.last_latest_image_card = state
        if payload.get("clicked"):
            return str(payload.get("clickedLabel") or labels[0] if labels else "")
        return ""

    def _wait_for_video_generation_ui(self, *, max_seconds: float = 20.0) -> bool:
        deadline = time.monotonic() + max(1.0, max_seconds)
        while time.monotonic() < deadline:
            if self.verify_video_generation_transition():
                return True
            if not self.simulate:
                self._sleep_ms(500)
            else:
                return self._simulated_video_mode
        return self.verify_video_generation_transition()

    def use_starter_image_for_video(self, prompt_text: str | None = None) -> LatestGeneratedImageCardState:
        """Route the newest starter image into video generation via direct action or app menu."""
        state = self.locate_and_prepare_latest_image_card(prompt_text)
        action_used = ""
        candidates: list[str] = []

        direct_label = self._click_direct_use_for_video_on_card(state.latest_image_card_index)
        if direct_label:
            action_used = direct_label
            candidates = list(state.use_for_video_candidates or [direct_label])
            if self.simulate:
                self._simulated_video_mode = True
                self._simulated_page_url = (
                    "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video"
                )
            self._record(
                "use_starter_image_for_video_direct",
                control_key="image_use_to_video_option",
                detail=f"index={state.latest_image_card_index}; action={direct_label}; candidates={candidates}",
            )
            self._capture_chip_diagnostic_screenshot("use_starter_image_for_video_direct")
            self._sleep_ms(CHIP_AFTER_CLICK_VERIFY_DELAY_MS)
            if self._wait_for_video_generation_ui():
                state.use_for_video_action_used = action_used
                state.use_for_video_candidates = candidates
                state.video_transition_verified = True
                state.current_url_after_transition = self._current_page_url()
                self.last_latest_image_card = state
                self._register_starter_image_assignment()
                self.phase_i_artifact_tracker().mark_consumed(ROLE_STARTER_IMAGE)
                return state

        candidates = self._scan_use_for_video_candidates_on_card(state.latest_image_card_index)
        state.use_for_video_candidates = candidates
        self._record(
            "use_starter_image_for_video_direct_miss",
            detail=f"index={state.latest_image_card_index}; candidates={candidates}",
        )

        self.open_app_menu_on_latest_image_card()
        self.click_use_to_video_on_latest_image_card()
        action_used = "Use to Video (app menu)"
        self._sleep_ms(CHIP_AFTER_CLICK_VERIFY_DELAY_MS)
        if not self._wait_for_video_generation_ui():
            self._capture_chip_diagnostic_screenshot("use_starter_image_for_video_fail")
            raise RuntimeError(
                "video generation UI not visible after Use for Video / Use to Video routing "
                f"(candidates={candidates}; action={action_used})"
            )

        state.use_for_video_action_used = action_used
        state.use_for_video_candidates = candidates
        state.use_to_video_available = True
        state.video_transition_verified = True
        state.current_url_after_transition = self._current_page_url()
        self.last_latest_image_card = state
        self._record(
            "use_starter_image_for_video",
            control_key="image_use_to_video_option",
            detail=(
                f"index={state.latest_image_card_index}; "
                f"action={action_used}; "
                f"candidates={candidates}; "
                f"url={state.current_url_after_transition}"
            ),
        )
        self._capture_chip_diagnostic_screenshot("use_starter_image_for_video_ok")
        self._register_starter_image_assignment()
        self.phase_i_artifact_tracker().mark_consumed(ROLE_STARTER_IMAGE)
        return state

    def clear_stale_video_transition_for_clip(self, clip_index: int) -> None:
        """Clip >= 2 must not reuse starter Use-to-Video transition readiness."""
        if clip_index < 2:
            return
        state = self.last_latest_image_card or LatestGeneratedImageCardState()
        state.video_transition_verified = False
        self.last_latest_image_card = state
        self._record(
            "clear_stale_video_transition",
            detail=f"clip={clip_index}; url={self._current_page_url()}",
        )

    @staticmethod
    def _probe_prompt_editor_candidates_eval_script() -> str:
        return """() => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const selectors = [
                'div[aria-label=\"Prompt\"]',
                '[aria-label=\"Prompt\"]',
                '[role=\"textbox\"]',
                'div[contenteditable=\"true\"]',
                'textarea',
            ];
            const modals = Array.from(document.querySelectorAll(
                '[role=\"dialog\"], [aria-modal=\"true\"], [data-state=\"open\"]'
            )).filter((node) => {
                const rect = node.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            });
            const modalDetected = modals.length > 0;
            const centerX = window.innerWidth / 2;
            const centerY = window.innerHeight / 2;
            const topElement = document.elementFromPoint(centerX, centerY);
            const candidates = [];
            const seen = new Set();
            for (const selector of selectors) {
                const nodes = Array.from(document.querySelectorAll(selector));
                for (const node of nodes) {
                    if (seen.has(node)) continue;
                    seen.add(node);
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    const visible = rect.width > 0 && rect.height > 0
                        && style.visibility !== 'hidden'
                        && style.display !== 'none';
                    const disabled = node.disabled === true
                        || node.getAttribute('aria-disabled') === 'true'
                        || node.getAttribute('contenteditable') === 'false';
                    let coveredByModal = false;
                    if (visible && topElement) {
                        for (const modal of modals) {
                            if (modal.contains(node) && modal !== node) {
                                coveredByModal = true;
                                break;
                            }
                        }
                        if (!coveredByModal && topElement !== node && !node.contains(topElement)) {
                            const probe = document.elementFromPoint(
                                rect.left + rect.width / 2,
                                rect.top + rect.height / 2
                            );
                            if (probe && probe !== node && !node.contains(probe)) {
                                coveredByModal = true;
                            }
                        }
                    }
                    const label = normalize(
                        node.getAttribute('aria-label')
                        || node.getAttribute('placeholder')
                        || node.innerText
                        || ''
                    ).slice(0, 80);
                    candidates.push({
                        selector,
                        label,
                        visible,
                        enabled: visible && !disabled,
                        bbox: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                        },
                        coveredByModal,
                    });
                }
            }
            return { modalDetected, candidates: candidates.slice(0, 20) };
        }"""

    def _probe_prompt_editor_candidates(self) -> list[dict[str, Any]]:
        if self.simulate:
            return [
                {
                    "selector": "simulate",
                    "label": "Prompt",
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x": 0, "y": 0, "width": 100, "height": 40},
                    "coveredByModal": False,
                }
            ]
        page = self._require_page()
        try:
            payload = page.evaluate(self._probe_prompt_editor_candidates_eval_script())
        except Exception:
            return []
        if not isinstance(payload, dict):
            return []
        raw = payload.get("candidates") or []
        return [item for item in raw if isinstance(item, dict)]

    def _dismiss_blocking_overlays_for_workspace(self) -> list[str]:
        """Close safe download/save/preview overlays after download or use-frame."""
        notes: list[str] = []
        if self.simulate:
            return notes
        page = self._require_page()
        try:
            result = page.evaluate(self._preclean_starter_image_workspace_eval_script())
        except Exception as exc:
            notes.append(f"overlay_dismiss_failed: {exc}")
            return notes
        payload = result if isinstance(result, dict) else {}
        raw_notes = payload.get("notes") or []
        if isinstance(raw_notes, list):
            notes.extend(str(item) for item in raw_notes)
        elif raw_notes:
            notes.append(str(raw_notes))
        if payload.get("closed"):
            self._record("workspace_overlay_dismissed", detail="; ".join(notes) or "closed")
        return notes

    def settle_after_download_clip(self, clip_index: int) -> dict[str, Any]:
        """Wait for browser/download UI to settle; do not require prompt ready."""
        notes: list[str] = [f"clip={clip_index}"]
        self._sleep_ms(POST_DOWNLOAD_SETTLE_MS)
        dismiss_notes = self._dismiss_blocking_overlays_for_workspace()
        notes.extend(dismiss_notes)
        self._sleep_ms(400)
        payload = {
            "clip_index": clip_index,
            "settled": True,
            "overlay_notes": dismiss_notes,
            "current_url": self._current_page_url(),
        }
        self._record("settle_after_download", detail=f"clip={clip_index}; notes={notes}")
        return payload

    def settle_after_use_frame_clip(self, clip_index: int) -> dict[str, Any]:
        """Wait for Use Frame apply + composer remount before next clip prompt."""
        self.clear_stale_video_transition_for_clip(clip_index)
        notes: list[str] = [f"clip={clip_index}"]
        self._sleep_ms(POST_USE_FRAME_INITIAL_SETTLE_MS)
        notes.extend(self._dismiss_blocking_overlays_for_workspace())
        self._try_focus_composer_workspace_safe()
        self._sleep_ms(400)
        partial = self.wait_for_prompt_editor_ready(
            clip_index,
            max_wait_seconds=min(15.0, PROMPT_EDITOR_READY_MAX_SECONDS),
            record_on_success=False,
        )
        notes.extend(partial.notes)
        payload = {
            "clip_index": clip_index,
            "settled": True,
            "prompt_partially_ready": partial.ready,
            "prompt_candidates_count": len(partial.prompt_candidates),
            "overlay_notes": notes,
            "current_url": self._current_page_url(),
        }
        self._record(
            "settle_after_use_frame",
            detail=f"clip={clip_index}; partial_ready={partial.ready}",
        )
        return payload

    @staticmethod
    def _use_frame_handoff_probe_eval_script() -> str:
        return """() => {
            const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
            const lower = (v) => String(v || '').toLowerCase();
            const isSelected = (node) => {
                if (!node) return false;
                if (node.getAttribute('aria-selected') === 'true') return true;
                if (node.getAttribute('aria-current') === 'true') return true;
                const state = lower(node.getAttribute('data-state') || '');
                if (state === 'active' || state === 'selected' || state === 'checked') return true;
                const cls = lower(String(node.className || ''));
                return (
                    cls.includes('selected')
                    || cls.includes('active')
                    || cls.includes('highlight')
                    || cls.includes('ring')
                );
            };
            const modals = Array.from(document.querySelectorAll(
                '[role=\"dialog\"], [aria-modal=\"true\"], [data-state=\"open\"]'
            )).filter((n) => {
                const r = n.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            });
            const modalDetected = modals.length > 0;
            const outputCards = [];
            const mediaNodes = Array.from(document.querySelectorAll(
                'video, canvas, picture, img, [class*=\"output\" i], [class*=\"result\" i], [class*=\"clip\" i]'
            ));
            for (const node of mediaNodes) {
                const rect = node.getBoundingClientRect();
                if (rect.width < 40 || rect.height < 40) continue;
                const tag = String(node.tagName || '').toLowerCase();
                let cardRoot = node;
                for (let d = 0; d < 6 && cardRoot; d++) {
                    if (isSelected(cardRoot)) break;
                    cardRoot = cardRoot.parentElement;
                }
                const selected = isSelected(cardRoot || node);
                outputCards.push({
                    tag,
                    selected,
                    bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                });
            }
            const referenceThumbnails = [];
            const refNodes = Array.from(document.querySelectorAll(
                'img, [class*=\"reference\" i], [class*=\"frame\" i], [aria-label*=\"frame\" i], '
                + '[aria-label*=\"reference\" i]'
            ));
            for (const node of refNodes) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                if (rect.width > 320 || rect.height > 320) continue;
                const tag = String(node.tagName || '').toLowerCase();
                const aria = normalize(node.getAttribute('aria-label') || '');
                const cls = lower(String(node.className || ''));
                const nearComposer = rect.top > window.innerHeight * 0.35;
                if (
                    nearComposer
                    && (
                        aria.includes('frame')
                        || aria.includes('reference')
                        || cls.includes('reference')
                        || cls.includes('frame')
                        || (tag === 'img' && rect.width >= 32 && rect.height >= 32)
                    )
                ) {
                    referenceThumbnails.push({
                        aria,
                        bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                    });
                }
            }
            const selectedOutputCards = outputCards.filter((c) => c.selected);
            return {
                modalDetected,
                outputCards: outputCards.slice(0, 20),
                selectedOutputCards: selectedOutputCards.slice(0, 8),
                referenceThumbnails: referenceThumbnails.slice(0, 12),
                hasSelectedOutputCard: selectedOutputCards.length > 0,
            };
        }"""

    def probe_use_frame_handoff_workspace(self, clip_number: int) -> dict[str, Any]:
        if self.simulate:
            mode = self._simulated_use_frame_handoff.get(clip_number, USE_FRAME_HANDOFF_COMPOSER_READY)
            return {
                "modalDetected": False,
                "outputCards": [],
                "selectedOutputCards": (
                    [{"selected": True, "tag": "video"}]
                    if mode == USE_FRAME_HANDOFF_INVALID_CARD_ONLY
                    else []
                ),
                "referenceThumbnails": (
                    [{"aria": "frame-ref"}]
                    if mode in {USE_FRAME_HANDOFF_COMPOSER_READY, USE_FRAME_HANDOFF_GENERATION_STARTED}
                    else []
                ),
                "hasSelectedOutputCard": mode == USE_FRAME_HANDOFF_INVALID_CARD_ONLY,
                "simulateMode": mode,
            }
        page = self._require_page()
        try:
            payload = page.evaluate(self._use_frame_handoff_probe_eval_script())
        except Exception as exc:
            return {"error": str(exc)}
        return payload if isinstance(payload, dict) else {}

    def _evaluate_use_frame_handoff_once(self, clip_number: int) -> UseFrameComposerHandoffState:
        state = UseFrameComposerHandoffState(clip_number=clip_number, checked=True)
        probe = self.probe_use_frame_handoff_workspace(clip_number)
        state.modal_detected = bool(probe.get("modalDetected"))
        state.output_card_candidates = list(probe.get("outputCards") or [])
        selected_cards = list(probe.get("selectedOutputCards") or [])
        state.reference_thumbnail_candidates = list(probe.get("referenceThumbnails") or [])
        state.reference_thumbnail_detected = len(state.reference_thumbnail_candidates) > 0
        has_selected_output = bool(probe.get("hasSelectedOutputCard")) or len(selected_cards) > 0

        prompt_ready = self.wait_for_prompt_editor_ready(
            clip_number,
            max_wait_seconds=2.5,
            record_on_success=False,
        )
        state.prompt_candidates = list(prompt_ready.prompt_candidates)
        state.prompt_interactable = bool(prompt_ready.ready)

        gen = self.detect_video_generation_in_progress(clip_number)
        state.generation_in_progress = self.is_real_video_generation_in_progress(gen)
        state.generate_button_visible = self.is_control_visible("generate_button") or bool(
            self._probe_video_generate_button_state().get("visible")
        )
        state.generate_button_disabled = not self.is_generate_button_actionable()

        if self.simulate:
            mode = str(probe.get("simulateMode") or USE_FRAME_HANDOFF_COMPOSER_READY)
            if mode == USE_FRAME_HANDOFF_GENERATION_STARTED:
                state.handoff_result = USE_FRAME_HANDOFF_GENERATION_STARTED
                state.generation_in_progress = True
            elif mode == USE_FRAME_HANDOFF_INVALID_CARD_ONLY:
                state.handoff_result = USE_FRAME_HANDOFF_INVALID_CARD_ONLY
                state.output_card_selected_only = True
                state.prompt_interactable = False
            else:
                state.handoff_result = USE_FRAME_HANDOFF_COMPOSER_READY
                state.prompt_interactable = True
                state.reference_thumbnail_detected = True
            self.last_use_frame_handoff_by_clip[clip_number] = state
            return state

        if state.modal_detected:
            self._dismiss_blocking_overlays_for_workspace()

        if state.generation_in_progress:
            state.handoff_result = USE_FRAME_HANDOFF_GENERATION_STARTED
            state.notes.append("path_b_generation_in_progress")
            self.last_use_frame_handoff_by_clip[clip_number] = state
            return state

        composer_controls_ok = (
            state.generate_button_visible
            or state.reference_thumbnail_detected
            or self.is_generate_button_actionable()
        )
        if state.prompt_interactable and composer_controls_ok and not state.modal_detected:
            state.handoff_result = USE_FRAME_HANDOFF_COMPOSER_READY
            state.notes.append("path_a_composer_ready")
            self.last_use_frame_handoff_by_clip[clip_number] = state
            return state

        if (
            has_selected_output
            and not state.prompt_interactable
            and not state.reference_thumbnail_detected
            and not state.generation_in_progress
        ):
            self._try_focus_composer_workspace_safe()
            self._sleep_ms(500)
            prompt_retry = self.wait_for_prompt_editor_ready(
                clip_number,
                max_wait_seconds=4.0,
                record_on_success=False,
            )
            state.prompt_candidates = list(prompt_retry.prompt_candidates)
            state.prompt_interactable = bool(prompt_retry.ready)
            composer_controls_ok = (
                self.is_generate_button_actionable()
                or state.reference_thumbnail_detected
                or self._probe_video_generate_button_state().get("visible")
            )
            if state.prompt_interactable and composer_controls_ok:
                state.handoff_result = USE_FRAME_HANDOFF_COMPOSER_READY
                state.notes.append("composer_ready_after_focus")
                self.last_use_frame_handoff_by_clip[clip_number] = state
                return state
            state.output_card_selected_only = True
            state.handoff_result = USE_FRAME_HANDOFF_INVALID_CARD_ONLY
            state.notes.append("invalid_card_only_selection")
            self.last_use_frame_handoff_by_clip[clip_number] = state
            return state

        state.handoff_result = USE_FRAME_HANDOFF_INVALID_CARD_ONLY
        state.notes.append("invalid_no_composer_no_generation")
        self.last_use_frame_handoff_by_clip[clip_number] = state
        return state

    def _try_focus_composer_workspace_safe(self) -> bool:
        if self.simulate:
            return True
        page = self._require_page()
        selectors = (
            'div[aria-label="Prompt"]',
            '[aria-label="Prompt"]',
            '[data-testid*="composer"]',
            '[class*="composer"]',
            'main',
        )
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() <= 0:
                    continue
                locator.click(timeout=800, force=True)
                self._record("use_frame_handoff_focus_composer", detail=selector)
                self._sleep_ms(300)
                return True
            except Exception:
                continue
        return False

    def verify_use_frame_composer_handoff(self, clip_number: int) -> UseFrameComposerHandoffState:
        """Verify Use Frame applied to next-clip composer, not card-only selection."""
        self._record("use_frame_handoff_verify_start", detail=f"clip={clip_number}")
        final_state = UseFrameComposerHandoffState(clip_number=clip_number, checked=True)
        deadline = time.monotonic() + USE_FRAME_HANDOFF_MAX_WAIT_SECONDS

        for attempt in range(1, USE_FRAME_HANDOFF_MAX_RETRIES + 1):
            if time.monotonic() > deadline:
                break
            state = self._evaluate_use_frame_handoff_once(clip_number)
            state.retry_attempts = attempt
            final_state = state
            if state.handoff_result in {
                USE_FRAME_HANDOFF_COMPOSER_READY,
                USE_FRAME_HANDOFF_GENERATION_STARTED,
            }:
                self._capture_chip_diagnostic_screenshot(
                    f"use_frame_handoff_ok_clip_{clip_number}"
                )
                self._record(
                    "use_frame_handoff_verify_ok",
                    detail=(
                        f"clip={clip_number}; result={state.handoff_result}; "
                        f"prompt={state.prompt_interactable}; ref={state.reference_thumbnail_detected}"
                    ),
                )
                return state

            if attempt < USE_FRAME_HANDOFF_MAX_RETRIES:
                self._record(
                    "use_frame_handoff_retry",
                    detail=f"clip={clip_number}; attempt={attempt}; result={state.handoff_result}",
                )
                self._sleep_ms(USE_FRAME_HANDOFF_RETRY_DELAY_MS)
                self._try_focus_composer_workspace_safe()
                if clip_number not in self._use_frame_reclick_used:
                    source_index = max(1, clip_number - 1)
                    source_role = PhaseIArtifactTracker.clip_video_role(source_index)
                    self.ensure_clip_video_card_assigned(source_index)
                    clicked = self.phase_i_artifact_tracker().click_label_on_assigned_card(
                        source_role,
                        USE_FRAME_LABELS,
                    )
                    if not clicked:
                        clicked = self.phase_i_artifact_tracker().click_label_on_latest_video_card(
                            USE_FRAME_LABELS,
                        )
                    if clicked:
                        self._use_frame_reclick_used.add(clip_number)
                        state.use_frame_reclicked = True
                        final_state.use_frame_reclicked = True
                    else:
                        state.notes.append("use_frame_reclick_in_card_failed")
                time.sleep(USE_FRAME_HANDOFF_POLL_SECONDS)

        final_state.handoff_result = USE_FRAME_HANDOFF_TIMEOUT
        if final_state.output_card_selected_only:
            final_state.handoff_result = USE_FRAME_HANDOFF_INVALID_CARD_ONLY
        final_state.notes.append(f"timeout_after_{USE_FRAME_HANDOFF_MAX_RETRIES}_retries")
        self.last_use_frame_handoff_by_clip[clip_number] = final_state
        self._capture_chip_diagnostic_screenshot(f"use_frame_handoff_fail_clip_{clip_number}")
        self._record(
            "use_frame_handoff_verify_fail",
            detail=f"clip={clip_number}; result={final_state.handoff_result}",
        )
        return final_state

    @staticmethod
    def _video_generation_progress_eval_script() -> str:
        return """() => {
            const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
            const lower = (value) => normalize(value).toLowerCase();
            const signals = [];
            let spinnerVisible = false;
            let stopCancelVisible = false;
            let progressText = '';
            let outputCards = 0;
            let outputLoading = false;
            let generateDisabled = false;
            let pendingOutputSlot = false;

            const spinnerSelectors = [
                '[role=\"progressbar\"]',
                '[aria-busy=\"true\"]',
                '[class*=\"spinner\" i]',
                '[class*=\"loading\" i]',
                'svg animate, svg [class*=\"spin\" i]',
            ];
            for (const selector of spinnerSelectors) {
                const nodes = document.querySelectorAll(selector);
                for (const node of nodes) {
                    const rect = node.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        spinnerVisible = true;
                        signals.push('spinner_visible');
                        break;
                    }
                }
                if (spinnerVisible) break;
            }

            const buttons = Array.from(document.querySelectorAll('button, [role=\"button\"]'));
            for (const button of buttons) {
                const rect = button.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const text = lower(button.innerText || button.textContent || '');
                const aria = lower(button.getAttribute('aria-label') || '');
                const label = text || aria;
                if (
                    (
                        label.includes('cancel generation')
                        || label.includes('stop generation')
                        || label.includes('abort generation')
                        || label === 'cancel'
                        || label === 'stop'
                    )
                    && (
                        label.includes('generat')
                        || label.includes('render')
                        || label.includes('queue')
                    )
                ) {
                    stopCancelVisible = true;
                    signals.push('stop_cancel_visible');
                }
                if (
                    (label === 'generate' || label.includes('generate'))
                    && (button.disabled || button.getAttribute('aria-disabled') === 'true')
                ) {
                    generateDisabled = true;
                    signals.push('generate_button_disabled');
                }
            }

            const textNodes = Array.from(document.querySelectorAll(
                'span, div, p, [role=\"status\"], [aria-live]'
            ));
            const progressNoisePatterns = [
                /notification/i,
                /don't show/i,
                /show again/i,
                /\\blater\\b/i,
                /\\benable\\b/i,
                /get notifications/i,
            ];
            const progressStrongPatterns = [
                /generating\\b/i,
                /processing/i,
                /rendering/i,
                /queued/i,
                /in progress/i,
                /\\d+\\s*%/,
            ];
            for (const node of textNodes) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                const text = normalize(node.innerText || node.textContent || '');
                if (!text || text.length > 120) continue;
                if (progressNoisePatterns.some((re) => re.test(text))) continue;
                if (progressStrongPatterns.some((re) => re.test(text))) {
                    progressText = text.slice(0, 120);
                    signals.push('progress_text');
                    break;
                }
            }

            const media = Array.from(document.querySelectorAll(
                'video, canvas, picture, [class*=\"output\" i], [class*=\"result\" i]'
            ));
            for (const node of media) {
                const rect = node.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                outputCards += 1;
                const cls = String(node.className || '').toLowerCase();
                const state = normalize(node.getAttribute('data-state') || '');
                if (
                    cls.includes('loading')
                    || cls.includes('pending')
                    || cls.includes('skeleton')
                    || state === 'loading'
                    || state === 'pending'
                ) {
                    outputLoading = true;
                    signals.push('output_loading');
                }
            }
            if (outputCards > 0) {
                signals.push('output_cards_detected');
                pendingOutputSlot = true;
            }

            const inProgress = (
                spinnerVisible
                || stopCancelVisible
                || outputLoading
                || (
                    Boolean(progressText)
                    && (spinnerVisible || stopCancelVisible || outputLoading)
                )
                || (generateDisabled && pendingOutputSlot && spinnerVisible)
                || (generateDisabled && spinnerVisible)
            );
            return {
                inProgress,
                spinnerVisible,
                stopCancelVisible,
                progressText,
                outputCardsDetected: outputCards,
                outputLoading,
                generateButtonDisabled: generateDisabled,
                pendingOutputSlot,
                signals: Array.from(new Set(signals)),
            };
        }"""

    @staticmethod
    def _parse_video_generation_progress_payload(payload: dict[str, Any]) -> VideoGenerationProgressState:
        signals = payload.get("signals") or []
        if not isinstance(signals, list):
            signals = []
        return VideoGenerationProgressState(
            in_progress=bool(payload.get("inProgress")),
            spinner_visible=bool(payload.get("spinnerVisible")),
            stop_cancel_visible=bool(payload.get("stopCancelVisible")),
            progress_text=str(payload.get("progressText") or ""),
            output_cards_detected=int(payload.get("outputCardsDetected") or 0),
            output_loading=bool(payload.get("outputLoading")),
            generate_button_disabled=bool(payload.get("generateButtonDisabled")),
            pending_output_slot=bool(payload.get("pendingOutputSlot")),
            signals=[str(item) for item in signals],
        )

    def detect_video_generation_in_progress(
        self,
        clip_index: int,
        *,
        simulate_in_progress: bool | None = None,
    ) -> VideoGenerationProgressState:
        if self.simulate:
            in_progress = bool(simulate_in_progress)
            state = VideoGenerationProgressState(
                in_progress=in_progress,
                signals=["simulate_generation"] if in_progress else [],
            )
            self.last_generation_progress_by_clip[clip_index] = state
            return state

        page = self._require_page()
        try:
            payload = page.evaluate(self._video_generation_progress_eval_script())
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        state = self._parse_video_generation_progress_payload(payload)
        if (
            not state.in_progress
            and state.generate_button_disabled
            and state.output_cards_detected > 0
            and not self.is_generate_button_actionable()
        ):
            state.in_progress = True
            if "generate_disabled_with_output" not in state.signals:
                state.signals.append("generate_disabled_with_output")

        if self.is_generate_button_actionable():
            if state.in_progress:
                state.signals.append("generate_button_actionable_override")
            state.in_progress = False
        elif not self.is_real_video_generation_in_progress(state):
            if state.in_progress:
                state.signals.append("weak_generation_signal_override")
            state.in_progress = False

        self.last_generation_progress_by_clip[clip_index] = state
        return state

    def _apply_generation_skip_to_prompt_ready(
        self,
        state: PromptEditorReadyState,
        *,
        clip_index: int,
        record: bool = True,
    ) -> PromptEditorReadyState:
        gen = self.detect_video_generation_in_progress(clip_index)
        state.generation_in_progress = gen.in_progress
        state.generation_state = gen.to_dict()
        if gen.in_progress:
            state.ready = False
            state.ready_result = "skipped_because_generation_started"
            state.notes.append("skipped_because_generation_started")
            self.last_prompt_ready_by_clip[clip_index] = state
            if record:
                self._record(
                    "prompt_ready_skipped_generation",
                    detail=f"clip={clip_index}; signals={','.join(gen.signals)}",
                )
        return state

    def wait_for_prompt_editor_ready(
        self,
        clip_index: int,
        *,
        max_wait_seconds: float = PROMPT_EDITOR_READY_MAX_SECONDS,
        record_on_success: bool = True,
    ) -> PromptEditorReadyState:
        state = PromptEditorReadyState(clip_index=clip_index, checked=True)
        state.generate_button_visible = self.is_control_visible("generate_button")
        if clip_index >= 1:
            prior = max(1, clip_index - 1) if clip_index >= 2 else clip_index
            self.ensure_clip_video_card_assigned(prior)
            tracker = self.phase_i_artifact_tracker()
            state.use_frame_button_visible = tracker.label_visible_on_latest_video_card(
                USE_FRAME_LABELS,
            )
            state.download_button_visible = tracker.label_visible_on_latest_video_card(
                DOWNLOAD_LABELS,
            )
        else:
            state.use_frame_button_visible = False
            state.download_button_visible = False

        if clip_index >= 2:
            self.clear_stale_video_transition_for_clip(clip_index)

        if self.simulate:
            state.ready = True
            state.ready_result = "ready"
            state.selector_used = "simulate"
            self.last_prompt_ready_by_clip[clip_index] = state
            if record_on_success:
                self._record("prompt_editor_ready", detail=f"clip={clip_index}; simulate")
            return state

        page = self._require_page()
        mapped_selector = ""
        try:
            mapped_selector = self.control("prompt_input").css_selector
        except Exception:
            mapped_selector = ""

        selectors: list[str] = []
        if mapped_selector.strip():
            selectors.append(mapped_selector.strip())
        for item in PROMPT_EDITOR_FALLBACK_SELECTORS:
            if item not in selectors:
                selectors.append(item)

        deadline = time.monotonic() + max(1.0, float(max_wait_seconds))
        while time.monotonic() < deadline:
            probe = self._probe_prompt_editor_candidates()
            state.prompt_candidates = probe
            try:
                payload = page.evaluate(self._probe_prompt_editor_candidates_eval_script())
                if isinstance(payload, dict):
                    state.modal_detected = bool(payload.get("modalDetected"))
            except Exception:
                pass

            state.generate_button_visible = self.is_control_visible("generate_button")
            if clip_index >= 1:
                card_index = max(1, clip_index - 1) if clip_index >= 2 else clip_index
                self.ensure_clip_video_card_assigned(card_index)
                tracker = self.phase_i_artifact_tracker()
                state.use_frame_button_visible = tracker.label_visible_on_latest_video_card(
                    USE_FRAME_LABELS,
                )
                state.download_button_visible = tracker.label_visible_on_latest_video_card(
                    DOWNLOAD_LABELS,
                )
            else:
                state.use_frame_button_visible = False
                state.download_button_visible = False

            if clip_index >= 2:
                gen = self.detect_video_generation_in_progress(clip_index)
                if gen.in_progress:
                    ready_selector = self.resolve_prompt_editor_selector()
                    if ready_selector:
                        state.selector_used = ready_selector
                    return self._apply_generation_skip_to_prompt_ready(
                        state,
                        clip_index=clip_index,
                        record=record_on_success,
                    )

            if state.modal_detected:
                state.notes.append("modal_detected_retry_dismiss")
                self._dismiss_blocking_overlays_for_workspace()

            ready_selector = ""
            for candidate in probe:
                if not candidate.get("visible") or not candidate.get("enabled"):
                    continue
                if candidate.get("coveredByModal"):
                    continue
                bbox = candidate.get("bbox") or {}
                if float(bbox.get("width") or 0) <= 0 or float(bbox.get("height") or 0) <= 0:
                    continue
                sel = str(candidate.get("selector") or "").strip()
                if sel and self._try_focus_prompt_selector(sel):
                    ready_selector = sel
                    break

            if not ready_selector:
                for sel in selectors:
                    if self._try_focus_prompt_selector(sel):
                        ready_selector = sel
                        break

            if ready_selector:
                state.ready = True
                state.ready_result = "ready"
                state.selector_used = ready_selector
                self.last_prompt_ready_by_clip[clip_index] = state
                latest = self.last_latest_image_card or LatestGeneratedImageCardState()
                latest.video_transition_verified = True
                latest.current_url_after_transition = self._current_page_url()
                self.last_latest_image_card = latest
                if record_on_success:
                    self._record(
                        "prompt_editor_ready",
                        detail=f"clip={clip_index}; selector={ready_selector}",
                    )
                return state

            state.notes.append("prompt_not_ready_yet")
            time.sleep(PROMPT_EDITOR_READY_POLL_SECONDS)

        state.notes.append(f"timeout_after_{max_wait_seconds}s")
        if clip_index >= 2:
            state = self._apply_generation_skip_to_prompt_ready(
                state,
                clip_index=clip_index,
                record=True,
            )
            if state.ready_result == "skipped_because_generation_started":
                return state

        state.ready_result = "not_ready_fatal"
        self.last_prompt_ready_by_clip[clip_index] = state
        self._record(
            "prompt_editor_not_ready",
            detail=f"clip={clip_index}; candidates={len(state.prompt_candidates)}",
        )
        return state

    def _try_focus_prompt_selector(self, selector: str) -> bool:
        if self.simulate:
            return True
        if not selector.strip():
            return False
        page = self._require_page()
        locator = page.locator(selector).first
        try:
            if locator.count() <= 0:
                return False
            locator.wait_for(state="visible", timeout=int(self.prep_timeout_ms / 2))
            box = locator.bounding_box()
            if not box or float(box.get("width") or 0) <= 0 or float(box.get("height") or 0) <= 0:
                return False
            locator.click(timeout=int(self.prep_timeout_ms / 2), trial=True)
            return True
        except Exception:
            try:
                locator.click(timeout=int(self.prep_timeout_ms / 2), force=True)
                return True
            except Exception:
                pass
        try:
            composer = page.locator(
                '[data-testid*="composer"], [class*="composer"], main'
            ).first
            if composer.count() > 0:
                composer.click(timeout=800, force=True)
                time.sleep(0.15)
                locator.click(timeout=int(self.prep_timeout_ms / 2), force=True)
                return True
        except Exception:
            return False
        return False

    def resolve_prompt_editor_selector(self) -> str:
        """Best-effort prompt editor selector when readiness was skipped."""
        if self.simulate:
            return "simulate"
        for clip_idx in sorted(self.last_prompt_ready_by_clip.keys(), reverse=True):
            prior = self.last_prompt_ready_by_clip.get(clip_idx)
            if prior is None:
                continue
            selector = str(prior.selector_used or "").strip()
            if selector:
                return selector
        probe = self._probe_prompt_editor_candidates()
        for candidate in probe:
            if not candidate.get("visible") or not candidate.get("enabled"):
                continue
            if candidate.get("coveredByModal"):
                continue
            selector = str(candidate.get("selector") or "").strip()
            if selector:
                return selector
        try:
            return str(self.control("prompt_input").css_selector or "").strip()
        except Exception:
            return ""

    def collect_phase_i_failure_diagnostics(
        self,
        *,
        step_id: str,
        selector_attempted: str = "",
        error: str = "",
        screenshot_path: str = "",
        clip_number: int = 0,
    ) -> dict[str, Any]:
        preclean = self.last_preclean or StarterImagePrecleanState()
        latest = self.last_latest_image_card
        visible_buttons: list[str] = []
        image_result_text = ""
        page_title = ""
        current_url = self._current_page_url()

        if not self.simulate and self.page is not None:
            try:
                page_title = str(getattr(self.page, "title", lambda: "")() or "")
            except Exception:
                page_title = ""
            try:
                payload = self.page.evaluate(
                    """() => {
                        const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                        const buttons = Array.from(document.querySelectorAll('button, [role=\"button\"]'));
                        const visible = [];
                        for (const button of buttons) {
                            const rect = button.getBoundingClientRect();
                            if (rect.width <= 0 || rect.height <= 0) continue;
                            const text = normalize(button.innerText || button.textContent || '');
                            const aria = normalize(button.getAttribute('aria-label') || '');
                            const label = text || aria;
                            if (label) visible.push(label.slice(0, 120));
                        }
                        const cards = Array.from(document.querySelectorAll('img, canvas, video, picture'));
                        let cardText = '';
                        if (cards.length > 0) {
                            let node = cards[cards.length - 1];
                            for (let depth = 0; depth < 8 && node; depth++) {
                                const text = normalize(node.innerText || node.textContent || '');
                                if (text.length > 40) {
                                    cardText = text.slice(0, 500);
                                    break;
                                }
                                node = node.parentElement;
                            }
                        }
                        return { visibleButtons: visible.slice(0, 40), imageResultText: cardText };
                    }"""
                )
                if isinstance(payload, dict):
                    visible_buttons = list(payload.get("visibleButtons") or [])
                    image_result_text = str(payload.get("imageResultText") or "")
            except Exception:
                pass

        use_for_video_candidates = list(latest.use_for_video_candidates if latest else [])
        if not use_for_video_candidates and latest and latest.latest_image_card_found:
            use_for_video_candidates = self._scan_use_for_video_candidates_on_card(
                latest.latest_image_card_index
            )

        prompt_probe = self._probe_prompt_editor_candidates()
        prompt_ready = self.last_prompt_ready_by_clip.get(clip_number)
        visible_dialogs: list[str] = []
        if not self.simulate and self.page is not None:
            try:
                dialog_payload = self.page.evaluate(
                    """() => {
                        const normalize = (v) => String(v || '').replace(/\\s+/g, ' ').trim();
                        const nodes = Array.from(document.querySelectorAll(
                            '[role=\"dialog\"], [aria-modal=\"true\"], [data-state=\"open\"]'
                        ));
                        const labels = [];
                        for (const node of nodes) {
                            const rect = node.getBoundingClientRect();
                            if (rect.width <= 0 || rect.height <= 0) continue;
                            const text = normalize(node.innerText || node.textContent || '');
                            if (text) labels.push(text.slice(0, 200));
                        }
                        return labels.slice(0, 8);
                    }"""
                )
                if isinstance(dialog_payload, list):
                    visible_dialogs = [str(item) for item in dialog_payload]
            except Exception:
                pass

        log_tail = 15 if "use_frame_handoff" in step_id else 10
        last_actions = [log.to_dict() for log in self.action_log[-log_tail:]]
        generation_diag: dict[str, Any] = {}
        handoff_state = self.last_use_frame_handoff_by_clip.get(clip_number)
        handoff_probe = self.probe_use_frame_handoff_workspace(clip_number) if clip_number > 0 else {}
        if clip_number > 0:
            gen_state = self.last_generation_progress_by_clip.get(clip_number)
            if gen_state is not None:
                generation_diag = gen_state.to_dict()
            else:
                generation_diag = self.detect_video_generation_in_progress(clip_number).to_dict()

        generate_state = {
            "visible": self.is_control_visible("generate_button"),
            "disabled": bool(generation_diag.get("generate_button_disabled")),
        }

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "step_id": step_id,
            "clip_number": clip_number,
            "error": error,
            "screenshot_path": screenshot_path,
            "current_url": current_url,
            "page_title": page_title,
            "visible_buttons": visible_buttons,
            "visible_dialogs_modals": visible_dialogs,
            "image_result_area_text": image_result_text,
            "selector_attempted": selector_attempted,
            "prompt_candidates_found": prompt_probe,
            "prompt_editor_ready_state": (
                prompt_ready.to_dict() if prompt_ready is not None else {}
            ),
            "generation_state_candidates": generation_diag,
            "use_frame_handoff_state": (
                handoff_state.to_dict() if handoff_state is not None else {}
            ),
            "output_card_candidates": list(handoff_probe.get("outputCards") or []),
            "reference_thumbnail_candidates": list(
                handoff_probe.get("referenceThumbnails") or []
            ),
            "generate_button_state": generate_state,
            "spinner_visible": bool(generation_diag.get("spinner_visible")),
            "stop_cancel_button_visible": bool(generation_diag.get("stop_cancel_visible")),
            "output_cards_detected": int(generation_diag.get("output_cards_detected") or 0),
            "generate_button_disabled": bool(generation_diag.get("generate_button_disabled")),
            "progress_text_detected": str(generation_diag.get("progress_text") or ""),
            "generate_button_visible": self.is_control_visible("generate_button"),
            "use_frame_button_visible": self.is_label_visible_in_clip_video_card(
                max(1, clip_number),
                USE_FRAME_LABELS,
            ),
            "download_button_visible": self.is_label_visible_in_clip_video_card(
                max(1, clip_number),
                DOWNLOAD_LABELS,
            ),
            "latest_video_card_fingerprint": (
                self.phase_i_artifact_tracker()
                .get_latest_video_card()
                .card_fingerprint
                if self.phase_i_artifact_tracker().get_latest_video_card()
                else ""
            ),
            "stale_image_preview_detected": preclean.stale_image_preview_detected,
            "stale_preview_closed": preclean.stale_preview_closed,
            "preclean_notes": list(preclean.preclean_notes),
            "use_for_video_candidates_visible": use_for_video_candidates,
            "use_for_video_action_used": latest.use_for_video_action_used if latest else "",
            "latest_image_card_index": latest.latest_image_card_index if latest else -1,
            "video_transition_verified": (
                latest.video_transition_verified if latest else False
            ),
            "last_action_log_entries": last_actions,
        }

    def _remove_button_labels(self) -> tuple[str, ...]:
        if self.has_control("image_card_remove_button"):
            return click_control_texts_for(
                "image_card_remove_button",
                self.snapshot.controls["image_card_remove_button"],
            )
        return BUTTON_CLICK_TEXTS.get("image_card_remove_button", ("Hide output",))

    def _return_to_image_generation_board(self) -> bool:
        if self.simulate:
            self._simulated_page_url = (
                "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=image"
            )
            return True
        current = self._current_page_url().lower()
        if "tool=image" in current:
            return True
        try:
            url = image_generation_url(self.snapshot)
            page = self._require_page()
            page.goto(url, wait_until="domcontentloaded")
            self._sleep_ms(800)
            return True
        except Exception:
            return False

    def _click_remove_button_on_used_image_card(
        self,
        *,
        card_index: int,
        fingerprint: str,
    ) -> bool:
        if self.simulate:
            if self._simulated_generation_cards is None:
                return False
            before = len(self._simulated_generation_cards)
            self._simulated_generation_cards = [
                card
                for card in self._simulated_generation_cards
                if self._fingerprint_for_card(card) != fingerprint
            ]
            return len(self._simulated_generation_cards) < before

        page = self._require_page()
        hide_labels = list(self._remove_button_labels())
        try:
            removed = page.evaluate(
                self._generation_card_remove_click_eval_script(),
                {
                    "cardFingerprint": fingerprint,
                    "cardIndex": card_index,
                    "hideLabels": hide_labels,
                },
            )
            if removed:
                self._sleep_ms(500)
                return True
        except Exception:
            pass
        return False

    def cleanup_used_image_card_after_use_to_video(self) -> LatestGeneratedImageCardState:
        """Remove the selected latest card or mark its fingerprint consumed in runtime state."""
        state = self.last_latest_image_card
        if state is None or not state.latest_image_card_found:
            raise RuntimeError("no selected image card for cleanup")
        if not state.video_transition_verified:
            raise RuntimeError(
                "cannot remove used image card before Use to Video transition is verified"
            )

        fingerprint = str(state.selected_image_card_fingerprint or "").strip()
        if not fingerprint:
            raise RuntimeError("selected image card has no fingerprint for cleanup")

        on_video_page = self.verify_video_generation_transition()
        if on_video_page:
            self._mark_image_card_consumed(fingerprint)
            state.used_image_card_removed = False
            state.used_image_card_marked_consumed = True
            self.last_latest_image_card = state
            self._record(
                "used_image_card_cleanup",
                control_key="image_card_remove_button",
                detail=(
                    f"fingerprint={fingerprint}; "
                    f"index={state.latest_image_card_index}; "
                    "deferred_physical_remove_on_video_page=true; "
                    f"marked_consumed={state.used_image_card_marked_consumed}"
                ),
            )
            self._capture_chip_diagnostic_screenshot("used_image_card_cleanup_deferred")
            return state

        self._return_to_image_generation_board()
        removed = self._click_remove_button_on_used_image_card(
            card_index=state.latest_image_card_index,
            fingerprint=fingerprint,
        )

        state.used_image_card_removed = removed
        state.used_image_card_marked_consumed = False
        if not removed:
            self._mark_image_card_consumed(fingerprint)
            state.used_image_card_marked_consumed = True

        self.last_latest_image_card = state
        self._record(
            "used_image_card_cleanup",
            control_key="image_card_remove_button",
            detail=(
                f"fingerprint={fingerprint}; "
                f"index={state.latest_image_card_index}; "
                f"removed={removed}; "
                f"marked_consumed={state.used_image_card_marked_consumed}"
            ),
        )
        self._capture_chip_diagnostic_screenshot("used_image_card_cleanup")
        return state

    def verify_video_generation_transition(self) -> bool:
        url = self._current_page_url()
        verified = False
        if self.simulate:
            verified = self._simulated_video_mode
        else:
            lower = url.lower()
            if "tool=video" in lower:
                verified = True
            elif self.is_control_visible("prompt_input"):
                verified = True
            elif self.is_control_visible("generate_button"):
                verified = True

        state = self.last_latest_image_card or LatestGeneratedImageCardState()
        state.video_transition_verified = verified
        state.current_url_after_transition = url
        self.last_latest_image_card = state
        self._record(
            "latest_image_transition_verify",
            detail=f"verified={verified}; url={url}",
        )
        return verified

    def mark_clip_generating(self, clip_index: int) -> None:
        self._simulate_clip_generating[max(1, int(clip_index))] = True

    def clear_clip_generating(self, clip_index: int) -> None:
        self._simulate_clip_generating.pop(max(1, int(clip_index)), None)

    def evaluate_strict_clip_completion(self, clip_index: int) -> Any:
        self.ensure_clip_video_card_assigned(clip_index)
        from content_brain.execution.runway_phase_i_strict_completion_gate import (
            StrictClipCompletionResult,
            evaluate_strict_clip_completion,
        )

        override = self._strict_completion_test_override
        result = evaluate_strict_clip_completion(
            self,
            clip_index,
            test_override=override,
        )
        self.last_strict_completion_by_clip[max(1, int(clip_index))] = result
        return result

    def wait_for_strict_clip_completion(
        self,
        clip_index: int,
        *,
        max_wait_minutes: int = 20,
        poll_seconds: float = DEFAULT_COMPLETION_POLL_SECONDS,
    ) -> list[str]:
        """Poll until clip N is strictly complete (not global download / stale buttons)."""
        from content_brain.execution.runway_phase_i_strict_completion_gate import (
            write_strict_completion_diagnostics,
        )

        index = max(1, int(clip_index))
        deadline = time.monotonic() + max(1, max_wait_minutes) * 60
        self._record(
            "wait_strict_completion_start",
            detail=f"clip={index}; poll={poll_seconds}s",
        )
        last_reason = ""
        while time.monotonic() < deadline:
            if self.simulate:
                self.clear_clip_generating(index)
            result = self.evaluate_strict_clip_completion(index)
            if result.complete:
                role = PhaseIArtifactTracker.clip_video_role(index)
                tracker = self.phase_i_artifact_tracker()
                if result.completed_card_fingerprint:
                    cards = tracker.scan_artifact_cards()
                    match = next(
                        (
                            card
                            for card in cards
                            if str(card.get("cardFingerprint") or "")
                            == result.completed_card_fingerprint
                        ),
                        None,
                    )
                    if match is not None:
                        artifact = tracker._card_from_raw(match, role=role)
                        tracker.assignments[role] = artifact
                signals = ["strict_clip_complete"]
                if result.download_in_assigned_card:
                    signals.append("download_in_card")
                self._record(
                    "wait_strict_completion_done",
                    detail=f"clip={index}; reason={result.reason}; fp={result.completed_card_fingerprint}",
                )
                self.clear_video_generate_click_lock(index)
                return signals
            last_reason = result.reason
            callback = getattr(self, "phase_i_progress_callback", None)
            if callable(callback):
                try:
                    callback(
                        clip_index=index,
                        reason=last_reason,
                        complete=bool(result.complete),
                        step_kind="wait_strict_completion",
                    )
                except Exception:
                    pass
            if result.reason in {
                "generation_in_progress",
                "progress_not_complete",
                "spinner_visible",
                "stop_cancel_visible",
                "output_loading",
                "no_completed_video_card",
            }:
                screenshot = self._capture_chip_diagnostic_screenshot(
                    f"strict_completion_pending_clip_{index}"
                )
                write_strict_completion_diagnostics(
                    self,
                    result,
                    context=f"pending:{result.reason}",
                    screenshot_path=screenshot,
                )
            time.sleep(poll_seconds)

        result = self.evaluate_strict_clip_completion(index)
        screenshot = self._capture_chip_diagnostic_screenshot(
            f"strict_completion_timeout_clip_{index}"
        )
        write_strict_completion_diagnostics(
            self,
            result,
            context="timeout",
            screenshot_path=screenshot,
        )
        raise TimeoutError(
            "strict clip completion not detected within "
            f"{max_wait_minutes} minutes for clip {index} "
            f"(last_reason={last_reason})"
        )

    def wait_for_completion_signal(
        self,
        *,
        clip_index: int = 1,
        max_wait_minutes: int = 20,
        poll_seconds: float = DEFAULT_COMPLETION_POLL_SECONDS,
    ) -> list[str]:
        """Strict Phase I completion — delegates to wait_for_strict_clip_completion."""
        return self.wait_for_strict_clip_completion(
            clip_index,
            max_wait_minutes=max_wait_minutes,
            poll_seconds=poll_seconds,
        )


def image_generation_url(snapshot: RunwayUIMapSnapshot) -> str:
    for key in ("image_prompt_input", "image_generate_button", "image_aspect_ratio_9_16"):
        ctrl = snapshot.controls.get(key)
        if ctrl and ctrl.page_url:
            url = ctrl.page_url
            if "tool=image" in url:
                return url
    return "https://app.runwayml.com/ai-tools/generate?mode=tools&tool=image"


__all__ = [
    "BUTTON_CLICK_TEXTS",
    "DEFAULT_COMPLETION_POLL_SECONDS",
    "DEFAULT_MAP_PATH",
    "DEFAULT_MENU_OPTION_TIMEOUT_MS",
    "GenerationImageCardSnapshot",
    "LatestGeneratedImageCardState",
    "TOOLBAR_CHIP_MENU_KEYS",
    "VIDEO_ASPECT_MENU_KEY",
    "VIDEO_DURATION_MENU_KEY",
    "VIDEO_TOOLBAR_CHIP_MENU_KEYS",
    "VideoToolbarSettingsState",
    "MappedRunwayUINavigator",
    "MENU_OPTION_TEXTS",
    "NavigatorActionLog",
    "PromptClearResult",
    "ScreenshotFn",
    "StarterImagePrecleanState",
    "StarterImageSettingsState",
    "USE_FOR_VIDEO_ACTION_LABELS",
    "click_control_texts_for",
    "image_generation_url",
    "select_menu_option_texts_for",
]


def select_menu_option_texts_for(menu_key: str, option_key: str) -> tuple[str, ...]:
    return MENU_OPTION_TEXTS.get((menu_key, option_key), ())


def click_control_texts_for(control_key: str, ctrl: ResolvedControl | None = None) -> tuple[str, ...]:
    texts: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        cleaned = str(value or "").strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        texts.append(cleaned)

    if ctrl is not None and ctrl.text.strip():
        add(ctrl.text.strip())
    if ctrl is not None and ctrl.aria_label.strip():
        add(ctrl.aria_label.strip())
    for item in BUTTON_CLICK_TEXTS.get(control_key, ()):
        add(item)
    return tuple(texts)
