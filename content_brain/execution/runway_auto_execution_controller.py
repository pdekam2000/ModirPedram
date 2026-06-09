"""
Automatic execution bridge for Runway Live Smoke — safety validators + timeline logs.

Replaces manual approval gates in FULL_AUTO / partial SEMI_AUTO modes.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from content_brain.execution.runway_execution_mode import (
    EXECUTION_MODE_FULL_AUTO,
    EXECUTION_MODE_SEMI_AUTO,
    normalize_execution_mode,
    requires_manual_image_ready_hold,
    requires_operator_approval,
)

AUTO_BRIDGE_VERSION = "runway_auto_execution_v2"
DEFAULT_GENERATE_WAIT_SECONDS = 120.0
DEFAULT_DOWNLOAD_WAIT_SECONDS = 1500.0
PROMPT_MATCH_MIN_OVERLAP = 0.28


@dataclass
class AutoValidationResult:
    ok: bool
    action: str
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass
class AutoExecutionTimelineEntry:
    timestamp: str
    step_id: str
    action: str
    reason: str
    validation: dict[str, Any]
    runtime_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "step_id": self.step_id,
            "action": self.action,
            "reason": self.reason,
            "validation": dict(self.validation),
            "runtime_state": self.runtime_state,
        }


class RunwayAutoExecutionController:
    """Validate and auto-progress dangerous Runway actions."""

    def __init__(
        self,
        *,
        navigator: Any,
        simulate: bool = False,
        execution_mode: str = EXECUTION_MODE_FULL_AUTO,
        now_fn: Callable[[], str] | None = None,
    ) -> None:
        self.navigator = navigator
        self.simulate = bool(simulate)
        self.execution_mode = normalize_execution_mode(execution_mode)
        self._now_fn = now_fn or (lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
        self.timeline: list[AutoExecutionTimelineEntry] = []

    def should_auto_approve(self, control_key: str) -> bool:
        return not requires_operator_approval(self.execution_mode, control_key)

    def should_auto_image_ready(self) -> bool:
        return not requires_manual_image_ready_hold(self.execution_mode)

    def validate_before_action(
        self,
        *,
        control_key: str,
        step_id: str,
        clip_index: int = 0,
    ) -> AutoValidationResult:
        if self.navigator is None:
            return AutoValidationResult(False, control_key, "navigator_unavailable")

        if control_key == "image_generate_button":
            state = getattr(self.navigator, "last_starter_settings", None)
            ok = bool(state and state.settings_verified)
            return AutoValidationResult(
                ok,
                control_key,
                "" if ok else "starter_settings_not_verified",
                details={
                    "settings_verified": ok,
                    "detected_aspect_ratio": getattr(state, "detected_aspect_ratio", ""),
                    "detected_image_count": getattr(state, "detected_image_count", ""),
                },
            )

        if control_key == "generate_button":
            if clip_index <= 0:
                clip_index = self._clip_index_from_step_id(step_id)
            clip_index = max(1, clip_index)
            try:
                video_state = self.navigator.prepare_video_generate_settings()
            except Exception as exc:
                return AutoValidationResult(
                    False,
                    control_key,
                    f"video_settings_prepare_failed:{exc}",
                )

            gen = self.navigator.detect_video_generation_in_progress(clip_index)
            actionable = bool(self.navigator.is_generate_button_actionable())
            real_gen = self.navigator.is_real_video_generation_in_progress(gen)

            if real_gen and not actionable:
                return AutoValidationResult(
                    True,
                    control_key,
                    "generation_already_started",
                    details={
                        "signals": list(gen.signals),
                        "generate_button_actionable": actionable,
                    },
                )

            settings_ok = bool(video_state.video_settings_verified)
            if actionable and settings_ok:
                return AutoValidationResult(
                    True,
                    control_key,
                    "generate_ready",
                    details={
                        "video_settings_verified": settings_ok,
                        "detected_aspect_ratio": video_state.detected_aspect_ratio,
                        "detected_duration": video_state.detected_duration,
                        "generate_button_actionable": actionable,
                        "button_probe": self.navigator._probe_video_generate_button_state(),
                    },
                )

            if not real_gen and settings_ok:
                return AutoValidationResult(
                    True,
                    control_key,
                    "proceed_despite_ui_noise",
                    details={
                        "video_settings_verified": settings_ok,
                        "generate_button_actionable": actionable,
                        "signals": list(gen.signals),
                        "button_probe": self.navigator._probe_video_generate_button_state(),
                    },
                )

            if not settings_ok:
                return AutoValidationResult(
                    False,
                    control_key,
                    "video_settings_not_verified",
                    details={
                        "video_settings_verified": settings_ok,
                        "detected_aspect_ratio": video_state.detected_aspect_ratio,
                        "detected_duration": video_state.detected_duration,
                    },
                )

            return AutoValidationResult(
                False,
                control_key,
                "generate_button_not_actionable",
                details={
                    "generate_button_actionable": actionable,
                    "signals": list(gen.signals),
                    "button_probe": self.navigator._probe_video_generate_button_state(),
                },
            )

        if control_key == "download_mp4_button":
            if clip_index <= 0:
                clip_index = self._clip_index_from_step_id(step_id)
            if clip_index <= 0:
                return AutoValidationResult(False, control_key, "clip_index_unknown")
            self.navigator.ensure_clip_video_card_assigned(clip_index)
            strict = self.navigator.evaluate_strict_clip_completion(clip_index)
            return AutoValidationResult(
                bool(strict.complete),
                control_key,
                "" if strict.complete else str(strict.reason or "clip_not_complete"),
                details=strict.to_dict() if hasattr(strict, "to_dict") else {"complete": strict.complete},
            )

        return AutoValidationResult(True, control_key, "no_specific_validator")

    def ensure_ready_for_action(
        self,
        *,
        control_key: str,
        step_id: str,
        clip_index: int = 0,
        expected_prompt: str = "",
        max_wait_seconds: float | None = None,
    ) -> AutoValidationResult:
        """Poll validators until ready, or return a hard failure."""
        if max_wait_seconds is None:
            if control_key == "download_mp4_button":
                max_wait_seconds = DEFAULT_DOWNLOAD_WAIT_SECONDS
            elif control_key == "generate_button":
                max_wait_seconds = DEFAULT_GENERATE_WAIT_SECONDS
            else:
                max_wait_seconds = 120.0

        deadline = time.monotonic() + max(5.0, float(max_wait_seconds))
        poll = 2.0 if not self.simulate else 0.05
        last = AutoValidationResult(False, control_key, "not_checked")
        prompt_refilled = False
        prompt_refill_attempts = 0
        max_prompt_refills = 3

        while time.monotonic() < deadline:
            last = self.validate_before_action(
                control_key=control_key,
                step_id=step_id,
                clip_index=clip_index,
            )
            if last.ok and control_key == "generate_button" and expected_prompt.strip():
                prompt_check = self._validate_clip_prompt(expected_prompt, clip_index)
                if not prompt_check.ok and prompt_refill_attempts < max_prompt_refills:
                    refill = self._refill_clip_prompt(expected_prompt, clip_index)
                    prompt_refill_attempts += 1
                    prompt_refilled = prompt_refilled or refill.ok
                    if refill.ok:
                        prompt_check = self._validate_clip_prompt(expected_prompt, clip_index)
                if not prompt_check.ok:
                    last = prompt_check
                else:
                    return prompt_check

            if last.ok:
                return last

            if last.reason == "video_settings_not_verified" and self.navigator is not None:
                try:
                    self.navigator.prepare_video_generate_settings()
                except Exception:
                    pass

            if last.reason in {
                "clip_not_complete",
                "video_settings_not_verified",
                "starter_settings_not_verified",
                "generate_button_not_actionable",
                "prompt_content_mismatch",
                "wrong_clip_prompt_marker",
                "prompt_empty",
            }:
                time.sleep(poll)
                continue

            if last.reason in {"generation_already_started", "proceed_despite_ui_noise", "generate_ready"}:
                return last

            return last

        return AutoValidationResult(
            False,
            control_key,
            f"timeout_waiting_for_{last.reason or 'ready_state'}",
            details=last.details,
        )

    def _validate_clip_prompt(self, expected_prompt: str, clip_index: int) -> AutoValidationResult:
        expected = str(expected_prompt or "").strip()
        if not expected:
            return AutoValidationResult(True, "prompt_input", "no_expected_prompt")

        actual = ""
        if self.navigator is not None:
            actual = str(self.navigator.read_prompt_control_text("prompt_input") or "").strip()
        if not actual:
            return AutoValidationResult(False, "prompt_input", "prompt_empty")

        marker = f"clip {max(1, clip_index)} of"
        if marker in expected.lower() and marker not in actual.lower():
            return AutoValidationResult(
                False,
                "prompt_input",
                "wrong_clip_prompt_marker",
                details={"expected_marker": marker, "actual_preview": actual[:120]},
            )

        expected_tokens = _prompt_tokens(expected)
        actual_tokens = _prompt_tokens(actual)
        if not expected_tokens:
            return AutoValidationResult(True, "prompt_input", "prompt_non_empty")
        overlap = len(expected_tokens & actual_tokens) / max(1, len(expected_tokens))
        if overlap < PROMPT_MATCH_MIN_OVERLAP:
            return AutoValidationResult(
                False,
                "prompt_input",
                "prompt_content_mismatch",
                details={
                    "overlap": round(overlap, 4),
                    "expected_preview": expected[:120],
                    "actual_preview": actual[:120],
                },
            )
        return AutoValidationResult(
            True,
            "prompt_input",
            "prompt_verified",
            details={"overlap": round(overlap, 4)},
        )

    def _refill_clip_prompt(self, expected_prompt: str, clip_index: int) -> AutoValidationResult:
        if self.navigator is None:
            return AutoValidationResult(False, "prompt_input", "navigator_unavailable")
        selector = ""
        try:
            selector = self.navigator.resolve_prompt_editor_selector()
        except Exception:
            selector = ""
        try:
            self.navigator.clear_prompt_control("prompt_input")
        except Exception:
            pass
        try:
            applied = self.navigator.ensure_clip_prompt_applied(
                clip_index,
                expected_prompt,
                selector_override=selector,
                max_attempts=2,
            )
        except Exception as exc:
            return AutoValidationResult(False, "prompt_input", f"prompt_refill_failed:{exc}")
        if not applied:
            return AutoValidationResult(
                False,
                "prompt_input",
                f"prompt_refill_marker_missing_clip_{clip_index}",
            )
        return AutoValidationResult(
            True,
            "prompt_input",
            f"prompt_refilled_clip_{clip_index}",
            details={"selector": selector},
        )

    def wait_for_image_ready_auto(
        self,
        *,
        step_id: str,
        max_wait_seconds: float = 900.0,
        poll_seconds: float = 3.0,
    ) -> AutoValidationResult:
        if self.simulate:
            return AutoValidationResult(True, "image_ready", "simulate_image_ready")

        deadline = time.monotonic() + max(5.0, float(max_wait_seconds))
        poll = max(1.0, float(poll_seconds))
        while time.monotonic() < deadline:
            latest = getattr(self.navigator, "last_latest_image_card", None)
            if latest is not None and bool(getattr(latest, "latest_image_card_found", False)):
                return AutoValidationResult(
                    True,
                    "image_ready",
                    "latest_image_card_detected",
                    details={
                        "card_index": getattr(latest, "latest_image_card_index", -1),
                        "step_id": step_id,
                    },
                )
            try:
                self.navigator.select_latest_generated_image_card()
                latest = getattr(self.navigator, "last_latest_image_card", None)
                if latest is not None and bool(getattr(latest, "latest_image_card_found", False)):
                    return AutoValidationResult(
                        True,
                        "image_ready",
                        "latest_image_card_detected_after_scan",
                        details={
                            "card_index": getattr(latest, "latest_image_card_index", -1),
                            "step_id": step_id,
                        },
                    )
            except Exception as exc:
                return AutoValidationResult(False, "image_ready", f"scan_failed:{exc}")
            time.sleep(poll)
        return AutoValidationResult(False, "image_ready", "image_ready_timeout")

    def record(
        self,
        *,
        step_id: str,
        action: str,
        reason: str,
        validation: AutoValidationResult,
        runtime_state: str,
    ) -> None:
        self.timeline.append(
            AutoExecutionTimelineEntry(
                timestamp=self._now_fn(),
                step_id=step_id,
                action=action,
                reason=reason,
                validation=validation.to_dict(),
                runtime_state=runtime_state,
            )
        )

    def timeline_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.timeline]

    @staticmethod
    def _clip_index_from_step_id(step_id: str) -> int:
        import re

        match = re.search(r"clip_(\d+)", str(step_id or ""), flags=re.I)
        if not match:
            match = re.search(r"_(\d+)$", str(step_id or ""))
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0


def _prompt_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", str(text or "").lower())
        if token not in {"clip", "with", "from", "that", "this", "into", "about"}
    }


def build_auto_execution_controller(
    *,
    navigator: Any,
    simulate: bool,
    execution_mode: str,
) -> RunwayAutoExecutionController | None:
    mode = normalize_execution_mode(execution_mode)
    if mode == EXECUTION_MODE_FULL_AUTO or mode == EXECUTION_MODE_SEMI_AUTO:
        return RunwayAutoExecutionController(
            navigator=navigator,
            simulate=simulate,
            execution_mode=mode,
        )
    return None


__all__ = [
    "AUTO_BRIDGE_VERSION",
    "AutoExecutionTimelineEntry",
    "AutoValidationResult",
    "RunwayAutoExecutionController",
    "build_auto_execution_controller",
]
