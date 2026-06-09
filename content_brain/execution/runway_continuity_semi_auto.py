"""
Phase RUNWAY-STARTER-TO-VIDEO-E — operator-approved Runway continuity semi-automation.

Auto-prepares mapped controls (prompts, settings, waits). Generate and Download remain
approval-gated. Does not modify RunwayBrowserProvider or spend credits without approval.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.runway_image_generation_config import (
    image_aspect_control_key,
    image_count_control_key,
    image_quality_control_key,
    menu_option_texts_for_image_count,
    menu_option_texts_for_image_quality,
)
from content_brain.execution.runway_continuity_approval_guard import (
    BLOCK_APPROVAL_REQUIRED,
    STATE_APPROVED,
    STATE_REQUIRED,
    can_execute_dangerous_action,
    evaluate_runway_continuity_approval_gate,
    grant_continuity_approval,
)
from content_brain.execution.runway_continuity_dry_run import (
    APPROVAL_GATED_CONTROLS,
    build_continuity_plan,
    run_dry_run,
)
from content_brain.execution.runway_continuity_models import (
    RunwayContinuityPlan,
    RunwayContinuityStep,
    RunwaySemiAutoResult,
    RunwaySemiAutoSession,
    RunwaySemiAutoStepResult,
    SEMI_AUTO_STATUS_AWAITING_APPROVAL,
    SEMI_AUTO_STATUS_COMPLETED,
    SEMI_AUTO_STATUS_FAILED,
    SEMI_AUTO_STATUS_IDLE,
    SEMI_AUTO_STATUS_MANUAL_HOLD,
    SEMI_AUTO_STATUS_PREPARING,
    SEMI_AUTO_STATUS_WAITING_COMPLETION,
    SEMI_AUTO_STEP_BLOCKED,
    SEMI_AUTO_STEP_DONE,
    SEMI_AUTO_STEP_RUNNING,
    SEMI_AUTO_STEP_SKIPPED,
)
from content_brain.execution.runway_ui_map_loader import DEFAULT_MAP_PATH
from content_brain.execution.runway_ui_navigator import (
    MENU_OPTION_TEXTS,
    MappedRunwayUINavigator,
    image_generation_url,
)

try:
    from content_brain.execution.runway_auto_execution_controller import RunwayAutoExecutionController
except ImportError:  # pragma: no cover
    RunwayAutoExecutionController = None  # type: ignore[misc, assignment]

SEMI_AUTO_VERSION = "runway_starter_to_video_e_v2"

SAFETY_GATES: tuple[str, ...] = (
    "no_autonomous_generate",
    "no_autonomous_download",
    "dangerous_steps_require_operator_approval",
    "no_runway_browser_provider_mutation",
    "no_provider_router_execution",
    "mapped_selectors_only",
    "completion_via_download_or_use_frame",
    "semi_auto_preparation_allowed",
)


def _step_result_from_plan_step(step: RunwayContinuityStep) -> RunwaySemiAutoStepResult:
    return RunwaySemiAutoStepResult(
        step_id=step.step_id,
        action=step.action,
        control_key=step.control_key,
        requires_operator_approval=step.requires_operator_approval,
    )


def build_semi_auto_session(
    plan: RunwayContinuityPlan,
    *,
    map_path: Path | str | None = None,
    ui_map: dict[str, Any] | None = None,
) -> RunwaySemiAutoSession:
    dry = run_dry_run(plan, map_path=map_path, ui_map=ui_map)
    if not dry.ok:
        raise ValueError("; ".join(dry.errors) or "dry-run map validation failed")
    return RunwaySemiAutoSession(
        plan=plan,
        steps=dry.steps,
        step_results=[_step_result_from_plan_step(step) for step in dry.steps],
        status=SEMI_AUTO_STATUS_IDLE,
    )


class RunwayContinuitySemiAutoEngine:
    """Step executor with operator approval pause points."""

    def __init__(
        self,
        navigator: MappedRunwayUINavigator,
        *,
        simulate: bool | None = None,
        auto_controller: RunwayAutoExecutionController | None = None,
    ) -> None:
        self.navigator = navigator
        self.simulate = navigator.simulate if simulate is None else simulate
        self.auto_controller = auto_controller

    @staticmethod
    def _clip_index_from_step_id(step_id: str) -> int:
        import re

        match = re.search(r"clip_(\d+)", str(step_id or ""), re.I)
        if match:
            return int(match.group(1))
        tokens = [token for token in str(step_id or "").split("_") if token.isdigit()]
        if tokens:
            return int(tokens[-1])
        return 0

    def _try_auto_approve_gate(
        self,
        session: RunwaySemiAutoSession,
        step: RunwayContinuityStep,
        result: RunwaySemiAutoStepResult,
    ) -> bool:
        """Return True when auto path handled (success or failure). False → manual pause."""
        controller = self.auto_controller
        if controller is None or not controller.should_auto_approve(step.control_key):
            return False

        clip_index = self._clip_index_from_step_id(step.step_id)
        expected_prompt = ""
        if step.control_key == "generate_button" and clip_index > 0:
            clip_pos = clip_index - 1
            if 0 <= clip_pos < len(session.plan.clips):
                expected_prompt = session.plan.clips[clip_pos].prompt

        validation = controller.ensure_ready_for_action(
            control_key=step.control_key,
            step_id=step.step_id,
            clip_index=clip_index,
            expected_prompt=expected_prompt,
        )
        controller.record(
            step_id=step.step_id,
            action=f"auto_{step.control_key}",
            reason=validation.reason or "validated",
            validation=validation,
            runtime_state=str(session.status),
        )
        if not validation.ok:
            session.status = SEMI_AUTO_STATUS_FAILED
            result.status = SEMI_AUTO_STEP_BLOCKED
            result.error = validation.reason or "auto_validation_failed"
            return True

        self.approve(
            session,
            control_key=step.control_key,
            step_id=step.step_id,
            approved_by="auto_execution",
            reason=validation.reason or "auto_validated",
        )
        result.notes = validation.reason or "auto_approved"
        return True

    def _try_auto_manual_hold(
        self,
        session: RunwaySemiAutoSession,
        step: RunwayContinuityStep,
        result: RunwaySemiAutoStepResult,
    ) -> bool:
        controller = self.auto_controller
        if controller is None or not controller.should_auto_image_ready():
            return False

        if self.simulate:
            result.status = SEMI_AUTO_STEP_DONE
            result.executed = True
            result.simulated = True
            result.notes = "simulate: auto image ready"
            return True

        validation = controller.wait_for_image_ready_auto(step_id=step.step_id)
        controller.record(
            step_id=step.step_id,
            action="auto_image_ready",
            reason=validation.reason or "validated",
            validation=validation,
            runtime_state=str(session.status),
        )
        if not validation.ok:
            session.status = SEMI_AUTO_STATUS_FAILED
            result.status = SEMI_AUTO_STEP_BLOCKED
            result.error = validation.reason or "auto_image_ready_failed"
            return True

        result.status = SEMI_AUTO_STEP_DONE
        result.executed = True
        result.notes = validation.reason or "auto_image_ready"
        return True

    def approve(
        self,
        session: RunwaySemiAutoSession,
        *,
        control_key: str,
        step_id: str,
        approved_by: str,
        reason: str = "",
    ) -> RunwaySemiAutoSession:
        session.approvals = grant_continuity_approval(
            control_key=control_key,
            step_id=step_id,
            approved_by=approved_by,
            reason=reason,
            approvals=session.approvals,
        )
        self.navigator.approvals = dict(session.approvals)
        return session

    def acknowledge_manual_hold(self, session: RunwaySemiAutoSession) -> RunwaySemiAutoSession:
        """Mark the current manual-hold step done after operator confirmation (live smoke)."""
        if session.status != SEMI_AUTO_STATUS_MANUAL_HOLD:
            return session
        if session.current_step_index >= len(session.steps):
            return session
        result = session.step_results[session.current_step_index]
        result.status = SEMI_AUTO_STEP_DONE
        result.executed = True
        result.simulated = self.simulate
        result.notes = "operator acknowledged manual hold"
        session.current_step_index += 1
        session.status = SEMI_AUTO_STATUS_PREPARING
        session.awaiting_step_id = None
        return session

    def advance(
        self,
        session: RunwaySemiAutoSession,
        *,
        max_steps: int | None = None,
    ) -> RunwaySemiAutoSession:
        """Run automatic prep steps until approval/manual/completion pause or completion."""
        if session.status in {SEMI_AUTO_STATUS_COMPLETED, SEMI_AUTO_STATUS_FAILED}:
            return session

        session.status = SEMI_AUTO_STATUS_PREPARING
        session.awaiting_control_key = None
        session.awaiting_step_id = None

        steps_run = 0
        while session.current_step_index < len(session.steps):
            if max_steps is not None and steps_run >= max_steps:
                break

            step = session.steps[session.current_step_index]
            result = session.step_results[session.current_step_index]
            if result.status == SEMI_AUTO_STEP_DONE:
                session.current_step_index += 1
                continue

            gate = evaluate_runway_continuity_approval_gate(
                control_key=step.control_key,
                step_id=step.step_id,
                approvals=session.approvals,
            )

            if step.requires_operator_approval and gate.approval_state == STATE_REQUIRED:
                if step.control_key == "image_generate_button" and not self._starter_settings_verified():
                    session.status = SEMI_AUTO_STATUS_FAILED
                    result.status = SEMI_AUTO_STEP_BLOCKED
                    result.error = "starter image settings not verified before Generate approval"
                    return session
                if self._try_auto_approve_gate(session, step, result):
                    if session.status == SEMI_AUTO_STATUS_FAILED:
                        return session
                else:
                    session.status = SEMI_AUTO_STATUS_AWAITING_APPROVAL
                    session.awaiting_control_key = step.control_key
                    session.awaiting_step_id = step.step_id
                    result.status = SEMI_AUTO_STEP_BLOCKED
                    result.requires_operator_approval = True
                    result.notes = BLOCK_APPROVAL_REQUIRED
                    return session
                gate = evaluate_runway_continuity_approval_gate(
                    control_key=step.control_key,
                    step_id=step.step_id,
                    approvals=session.approvals,
                )
                if gate.approval_state != STATE_APPROVED:
                    session.status = SEMI_AUTO_STATUS_FAILED
                    result.status = SEMI_AUTO_STEP_BLOCKED
                    result.error = "approval gate not granted after auto path"
                    return session

            if step.manual_required and not step.requires_operator_approval:
                if self._try_auto_manual_hold(session, step, result):
                    if session.status == SEMI_AUTO_STATUS_FAILED:
                        return session
                    session.current_step_index += 1
                    steps_run += 1
                    continue
                if self.simulate:
                    result.status = SEMI_AUTO_STEP_DONE
                    result.executed = True
                    result.simulated = True
                    result.notes = "simulate: manual hold acknowledged"
                    session.current_step_index += 1
                    steps_run += 1
                    continue
                session.status = SEMI_AUTO_STATUS_MANUAL_HOLD
                session.awaiting_step_id = step.step_id
                result.status = SEMI_AUTO_STEP_BLOCKED
                result.notes = "manual operator action required"
                return session

            result.status = SEMI_AUTO_STEP_RUNNING
            try:
                self._execute_step(session, step, result, gate_approved=gate.approval_state == STATE_APPROVED)
            except Exception as exc:
                session.status = SEMI_AUTO_STATUS_FAILED
                result.status = SEMI_AUTO_STEP_BLOCKED
                result.error = str(exc)
                return session

            result.executed = True
            result.simulated = self.simulate
            result.status = SEMI_AUTO_STEP_DONE
            if step.requires_operator_approval:
                result.approval_granted = True
            session.current_step_index += 1
            steps_run += 1

        if session.current_step_index >= len(session.steps):
            session.status = SEMI_AUTO_STATUS_COMPLETED
        return session

    def _execute_step(
        self,
        session: RunwaySemiAutoSession,
        step: RunwayContinuityStep,
        result: RunwaySemiAutoStepResult,
        *,
        gate_approved: bool,
    ) -> None:
        nav = self.navigator
        plan = session.plan
        step_key = step.step_id.split("_", 1)[-1] if "_" in step.step_id else step.step_id

        if step_key == "image_generation_open":
            url = image_generation_url(nav.snapshot)
            nav._record("navigate", control_key="image_prompt_input", detail=url)
            if not nav.simulate:
                nav.navigate_to_control_page("image_prompt_input")
            return

        if step_key == "fill_image_prompt":
            nav.ensure_prompt_control_empty("image_prompt_input")
            nav.fill_prompt_control("image_prompt_input", plan.starter_image_prompt)
            return

        if step_key == "select_image_9_16":
            nav.ensure_menu_setting(
                "image_aspect_ratio_menu",
                image_aspect_control_key(plan.aspect_ratio),
                MENU_OPTION_TEXTS.get(
                    ("image_aspect_ratio_menu", image_aspect_control_key(plan.aspect_ratio)),
                    ("9:16",),
                ),
            )
            return

        if step_key == "select_image_count":
            nav.ensure_menu_setting(
                "image_count_menu",
                image_count_control_key(plan.image_count),
                menu_option_texts_for_image_count(plan.image_count),
            )
            return

        if step_key in ("select_image_2k", "select_image_quality"):
            nav.ensure_menu_setting(
                "image_quality_menu",
                image_quality_control_key(plan.image_quality),
                menu_option_texts_for_image_quality(plan.image_quality),
            )
            return

        if step_key == "verify_starter_image_settings":
            state = nav.ensure_starter_image_settings(plan)
            result.notes = (
                f"settings_verified={state.settings_verified}; "
                f"aspect={state.detected_aspect_ratio}; "
                f"count={state.detected_image_count}; "
                f"quality={state.detected_image_quality}"
            )
            return

        if step_key == "clear_image_prompt_after_generation":
            clear_result = nav.clear_prompt_control("image_prompt_input")
            result.notes = (
                f"image_prompt_cleared={clear_result.image_prompt_cleared}; "
                f"before_chars={len(clear_result.prompt_text_before_clear)}"
            )
            return

        if step_key == "preclean_starter_image_workspace":
            preclean = nav.preclean_starter_image_workspace()
            result.notes = (
                f"preclean_attempted={preclean.preclean_attempted}; "
                f"stale_image_preview_detected={preclean.stale_image_preview_detected}; "
                f"stale_preview_closed={preclean.stale_preview_closed}; "
                f"preclean_notes={preclean.preclean_notes}"
            )
            return

        if step_key == "image_generate_manual_required":
            nav.configure_phase_i_artifact_tracking(
                project_id=plan.project_id,
                session_id="",
            )
            nav.snapshot_generation_image_cards_before_generate()
            nav.click_control(
                "image_generate_button",
                step_id=step.step_id,
                approved=gate_approved,
            )
            return

        if step_key == "use_starter_image_for_video":
            latest = nav.use_starter_image_for_video(plan.starter_image_prompt)
            result.notes = (
                f"video_transition_verified={latest.video_transition_verified}; "
                f"use_for_video_action_used={latest.use_for_video_action_used!r}; "
                f"candidates={latest.use_for_video_candidates}; "
                f"current_url_after_transition={latest.current_url_after_transition}"
            )
            return

        if step_key == "cleanup_used_image_card_after_use_to_video":
            cleanup = nav.cleanup_used_image_card_after_use_to_video()
            result.notes = (
                f"selected_image_card_fingerprint={cleanup.selected_image_card_fingerprint}; "
                f"used_image_card_removed={cleanup.used_image_card_removed}; "
                f"used_image_card_marked_consumed={cleanup.used_image_card_marked_consumed}"
            )
            return

        if step_key.startswith("use_frame_for_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            nav.ensure_clip_video_card_assigned(clip_index - 1)
            last_frame = nav.prepare_last_frame_use_frame_for_clip(clip_index)
            if not last_frame.strict_previous_complete:
                raise RuntimeError(
                    f"use_frame_for_clip_{clip_index}: previous clip not strictly complete"
                )
            if (
                not last_frame.previous_clip_seeked_to_last_frame
                and not last_frame.first_frame_fallback_used
            ):
                raise RuntimeError(
                    f"use_frame_for_clip_{clip_index}: last-frame seek failed "
                    f"({'; '.join(last_frame.notes)})"
                )
            if not last_frame.use_frame_clicked:
                raise RuntimeError(f"use_frame_for_clip_{clip_index}: Use Frame click failed")
            result.notes = (
                f"use_frame_source_clip={last_frame.use_frame_source_clip}; "
                f"use_frame_source={last_frame.use_frame_source}; "
                f"seeked={last_frame.previous_clip_seeked_to_last_frame}; "
                f"seek_time={last_frame.seek_time_used}; "
                f"strategy={last_frame.seek_strategy}"
            )
            return

        if step_key.startswith("settle_after_download_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            payload = nav.settle_after_download_clip(clip_index)
            result.notes = (
                f"settled={payload.get('settled')}; "
                f"overlay_notes={payload.get('overlay_notes')}"
            )
            return

        if step_key.startswith("settle_after_use_frame_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            payload = nav.settle_after_use_frame_clip(clip_index)
            result.notes = (
                f"settled={payload.get('settled')}; "
                f"prompt_partially_ready={payload.get('prompt_partially_ready')}"
            )
            return

        if step_key.startswith("verify_use_frame_handoff_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            handoff = nav.verify_use_frame_composer_handoff(clip_index)
            if handoff.handoff_result in {
                "composer_ready",
                "generation_already_started",
            }:
                result.notes = (
                    f"clip_{clip_index}_use_frame_handoff={handoff.handoff_result}; "
                    f"prompt_interactable={handoff.prompt_interactable}; "
                    f"reference_thumbnail={handoff.reference_thumbnail_detected}; "
                    f"retries={handoff.retry_attempts}"
                )
                return
            raise RuntimeError(
                f"use frame composer handoff failed for clip {clip_index}: "
                f"{handoff.handoff_result}; "
                f"card_only={handoff.output_card_selected_only}; "
                f"prompt_interactable={handoff.prompt_interactable}; "
                f"{'; '.join(handoff.notes) or 'unknown'}"
            )

        if step_key.startswith("video_prompt_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            if clip_index >= 2:
                nav.clear_stale_video_transition_for_clip(clip_index)
            ready = nav.wait_for_prompt_editor_ready(clip_index)
            ready_result = ready.ready_result or ("ready" if ready.ready else "")
            if not ready.ready and ready_result != "skipped_because_generation_started":
                if clip_index >= 2:
                    gen = nav.detect_video_generation_in_progress(clip_index)
                    if gen.in_progress:
                        ready_result = "skipped_because_generation_started"
                        ready.ready_result = ready_result
                        ready.generation_in_progress = True
                        ready.generation_state = gen.to_dict()
                        nav.last_prompt_ready_by_clip[clip_index] = ready
                    else:
                        raise RuntimeError(
                            f"prompt editor not ready for clip {clip_index}: "
                            f"{ready.ready_result or 'not_ready_fatal'}; "
                            f"{'; '.join(ready.notes) or 'unknown'}"
                        )
                else:
                    raise RuntimeError(
                        f"prompt editor not ready for clip {clip_index}: "
                        f"{ready.ready_result or 'not_ready_fatal'}; "
                        f"{'; '.join(ready.notes) or 'unknown'}"
                    )
            clip = plan.clips[clip_index - 1]
            selector = ready.selector_used or nav.resolve_prompt_editor_selector()
            if not nav.ensure_clip_prompt_applied(
                clip_index,
                clip.prompt,
                selector_override=selector,
            ):
                raise RuntimeError(
                    f"clip {clip_index} prompt not applied in composer; "
                    f"expected marker 'clip {clip_index} of'"
                )
            if ready_result == "skipped_because_generation_started":
                gen = nav.last_generation_progress_by_clip.get(clip_index)
                signals = ",".join(gen.signals) if gen else ""
                result.notes = (
                    f"clip_{clip_index}_prompt_filled_despite_generation; "
                    f"ready=skipped_because_generation_started; "
                    f"signals={signals}; selector={selector!r}"
                )
            else:
                result.notes = (
                    f"clip_{clip_index}_prompt_ready=ready; selector={selector!r}"
                )
            return

        if step_key.startswith("select_video_aspect_9_16_clip_"):
            aspect_texts = MENU_OPTION_TEXTS.get(
                ("aspect_ratio_menu", "aspect_ratio_9_16"),
                ("9:16", "9 : 16", "9: 16", "9 / 16"),
            )
            detected_aspect = nav.ensure_menu_setting(
                "aspect_ratio_menu",
                "aspect_ratio_9_16",
                aspect_texts,
            )
            result.notes = f"detected_video_aspect_ratio={detected_aspect}"
            return

        if step_key.startswith("select_duration_10s_clip_"):
            duration_texts = MENU_OPTION_TEXTS.get(
                ("duration_menu", "duration_10s"),
                ("10s", "10S", "10 s", "10 seconds"),
            )
            detected_duration = nav.ensure_menu_setting(
                "duration_menu",
                "duration_10s",
                duration_texts,
            )
            video_state = nav.ensure_video_toolbar_settings_verified()
            result.notes = (
                f"detected_video_duration={detected_duration}; "
                f"detected_video_aspect_ratio={video_state.detected_aspect_ratio}; "
                f"video_settings_verified={video_state.video_settings_verified}"
            )
            return

        if step_key.startswith("video_generate_manual_required_clip_"):
            clip_index = 1
            try:
                clip_index = int(step_key.rsplit("_", 1)[-1])
                nav.phase_i_artifact_tracker().snapshot_before_generation(
                    phase=f"clip_{clip_index}_video"
                )
                if nav.simulate:
                    nav.mark_clip_generating(clip_index)
            except ValueError:
                pass
            if nav._is_video_generate_submitted(clip_index):
                result.notes = f"clip_{clip_index}_generate_already_submitted"
                return
            gen = nav.detect_video_generation_in_progress(clip_index)
            if nav.is_real_video_generation_in_progress(gen) and not nav.is_generate_button_actionable():
                nav._mark_video_generate_submitted(clip_index)
                result.notes = (
                    f"clip_{clip_index}_generation_already_started; "
                    f"signals={','.join(gen.signals)}"
                )
                return
            clip_pos = clip_index - 1
            if 0 <= clip_pos < len(session.plan.clips):
                expected_prompt = session.plan.clips[clip_pos].prompt
                actual = nav.read_prompt_control_text("prompt_input")
                marker = f"clip {clip_index} of"
                if marker.lower() not in actual.lower():
                    selector = nav.resolve_prompt_editor_selector()
                    if not nav.ensure_clip_prompt_applied(
                        clip_index,
                        expected_prompt,
                        selector_override=selector,
                    ):
                        raise RuntimeError(
                            f"clip {clip_index} prompt mismatch before generate; "
                            f"expected marker 'clip {clip_index} of'"
                        )
            nav.click_generate_when_ready(
                step_id=step.step_id,
                approved=gate_approved,
                clip_index=clip_index,
            )
            return

        if step_key.startswith("wait_until_completion_signal_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            signals = nav.wait_for_strict_clip_completion(
                clip_index,
                max_wait_minutes=plan.max_wait_minutes_per_clip,
            )
            session.completion_signals = signals
            session.status = SEMI_AUTO_STATUS_WAITING_COMPLETION
            try:
                nav.ensure_clip_video_card_assigned(clip_index)
                assigned = nav.assign_clip_video_artifact(clip_index)
                if assigned is not None:
                    result.notes = (
                        f"signals={','.join(signals)}; "
                        f"assigned_fp={assigned.card_fingerprint}"
                    )
                else:
                    result.notes = f"signals={','.join(signals)}; artifact_assign_failed"
            except ValueError:
                result.notes = f"signals={','.join(signals)}"
            return

        if step_key.startswith("download_mp4_clip_") or step_key.startswith("final_download_clip_"):
            clip_index = int(step_key.rsplit("_", 1)[-1])
            nav.ensure_clip_video_card_assigned(clip_index)
            strict = nav.evaluate_strict_clip_completion(clip_index)
            if not strict.complete:
                raise RuntimeError(
                    f"download gate blocked: clip {clip_index} not strictly complete "
                    f"({strict.reason})"
                )
            attempt = nav.download_assigned_clip_video(
                clip_index,
                approved=gate_approved,
                step_id=step.step_id,
            )
            if not attempt.downloaded or attempt.file_size_bytes <= 0:
                raise RuntimeError(
                    f"clip {clip_index} download failed: strategy={attempt.strategy}; "
                    f"scoped={attempt.scoped_to_card}; notes={'; '.join(attempt.notes)}"
                )
            result.notes = (
                f"clip_{clip_index}_download_strategy={attempt.strategy}; "
                f"scoped_to_card={attempt.scoped_to_card}; path={attempt.file_path}"
            )
            return

        if step_key.startswith("remove_image_clip_"):
            nav.click_control("remove_image")
            if nav.read_prompt_control_text("image_prompt_input").strip():
                nav.clear_prompt_control("image_prompt_input")
            return

        result.status = SEMI_AUTO_STEP_SKIPPED
        result.notes = f"unhandled step key: {step_key}"

    def _starter_settings_verified(self) -> bool:
        state = self.navigator.last_starter_settings
        return bool(state and state.settings_verified)


def run_semi_auto_prepare(
    plan: RunwayContinuityPlan,
    *,
    map_path: Path | str | None = None,
    ui_map: dict[str, Any] | None = None,
    simulate: bool = True,
    approved_by: str | None = None,
    auto_approve: bool = False,
) -> RunwaySemiAutoResult:
    """
    Build session and advance until first approval gate (default simulate=True).
    Operator must approve dangerous controls before advance continues.
    """
    result = RunwaySemiAutoResult(
        ok=False,
        session=build_semi_auto_session(plan, map_path=map_path, ui_map=ui_map),
        safety_gates=list(SAFETY_GATES),
    )
    try:
        navigator = MappedRunwayUINavigator.from_map(
            map_path=map_path,
            ui_map=ui_map,
            simulate=simulate,
        )
    except Exception as exc:
        result.errors.append(str(exc))
        result.session.status = SEMI_AUTO_STATUS_FAILED
        return result

    engine = RunwayContinuitySemiAutoEngine(navigator, simulate=simulate)

    if auto_approve and approved_by:
        for step in result.session.steps:
            if step.control_key in APPROVAL_GATED_CONTROLS:
                engine.approve(
                    result.session,
                    control_key=str(step.control_key),
                    step_id=step.step_id,
                    approved_by=approved_by,
                    reason="auto_approve_test_only",
                )

    engine.advance(result.session)
    result.ok = result.session.status not in {SEMI_AUTO_STATUS_FAILED}
    if result.session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL:
        result.warnings.append(
            f"paused before {result.session.awaiting_control_key} — operator approval required"
        )
    return result


def run_semi_auto_with_approval(
    plan: RunwayContinuityPlan,
    *,
    approvals: list[dict[str, str]],
    map_path: Path | str | None = None,
    ui_map: dict[str, Any] | None = None,
    simulate: bool = True,
) -> RunwaySemiAutoResult:
    """Advance through workflow granting listed approvals (simulate by default)."""
    result = run_semi_auto_prepare(
        plan,
        map_path=map_path,
        ui_map=ui_map,
        simulate=simulate,
    )
    if not result.ok and result.errors:
        return result

    navigator = MappedRunwayUINavigator.from_map(
        map_path=map_path,
        ui_map=ui_map,
        simulate=simulate,
    )
    engine = RunwayContinuitySemiAutoEngine(navigator, simulate=simulate)
    session = result.session
    navigator.approvals = dict(session.approvals)

    approval_index = 0
    max_iterations = len(session.steps) * 3
    iterations = 0
    while session.status not in {
        SEMI_AUTO_STATUS_COMPLETED,
        SEMI_AUTO_STATUS_FAILED,
        SEMI_AUTO_STATUS_MANUAL_HOLD,
    } and iterations < max_iterations:
        iterations += 1
        if session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL:
            if approval_index >= len(approvals):
                result.warnings.append("ran out of supplied approvals")
                break
            item = approvals[approval_index]
            engine.approve(
                session,
                control_key=item["control_key"],
                step_id=item.get("step_id") or str(session.awaiting_step_id or ""),
                approved_by=item.get("approved_by") or "operator",
                reason=item.get("reason") or "",
            )
            approval_index += 1
        engine.advance(session)

    result.ok = session.status == SEMI_AUTO_STATUS_COMPLETED
    if session.status == SEMI_AUTO_STATUS_MANUAL_HOLD:
        result.warnings.append(f"manual hold at step {session.awaiting_step_id}")
    return result


__all__ = [
    "APPROVAL_GATED_CONTROLS",
    "DEFAULT_MAP_PATH",
    "RunwayContinuitySemiAutoEngine",
    "SAFETY_GATES",
    "SEMI_AUTO_VERSION",
    "build_continuity_plan",
    "build_semi_auto_session",
    "can_execute_dangerous_action",
    "grant_continuity_approval",
    "run_semi_auto_prepare",
    "run_semi_auto_with_approval",
]
