"""
Phase RUNWAY-STARTER-TO-VIDEO-D — Runway starter-to-video dry-run orchestrator.

Simulation only: no browser, no Generate/Download clicks, no credits, no provider calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_brain.execution.runway_image_generation_config import (
    image_aspect_control_key,
    image_count_control_key,
    image_quality_control_key,
)
from content_brain.execution.runway_continuity_models import (
    COMPLETION_RULE_EXPRESSION,
    DEFAULT_IMAGE_COUNT,
    DEFAULT_IMAGE_QUALITY,
    RunwayContinuityPlan,
    RunwayContinuityStep,
    RunwayDryRunResult,
    StarterImagePlan,
)
from content_brain.execution.runway_ui_map_loader import (
    STARTER_TO_VIDEO_CANONICAL_CONTROLS,
    RunwayUIMapSnapshot,
    load_runway_ui_map,
    resolve_runway_ui_controls,
)

DRY_RUN_VERSION = "runway_starter_to_video_d_v1"

APPROVAL_GATED_CONTROLS = frozenset(
    {
        "image_generate_button",
        "generate_button",
        "download_mp4_button",
    }
)

MANDATORY_FOR_DRY_RUN = frozenset(
    {
        "image_prompt_input",
        "image_aspect_ratio_9_16",
        "image_generate_button",
        "image_app_menu_button",
        "image_use_to_video_option",
        "prompt_input",
        "duration_10s",
        "generate_button",
        "download_mp4_button",
        "use_frame_button",
        "remove_image",
    }
)

SAFETY_GATES: tuple[str, ...] = (
    "no_browser_launch",
    "no_generate_click",
    "no_download_click",
    "no_credit_spend",
    "no_provider_execution",
    "no_runway_browser_provider_mutation",
    "simulated_steps_only",
    "dangerous_steps_require_operator_approval",
)


def _step(
    step_id: str,
    *,
    phase: str,
    action: str,
    control_key: str | None = None,
    simulated: bool = True,
    manual_required: bool = False,
    requires_operator_approval: bool = False,
    notes: str = "",
) -> RunwayContinuityStep:
    return RunwayContinuityStep(
        step_id=step_id,
        phase=phase,
        action=action,
        control_key=control_key,
        simulated=simulated,
        manual_required=manual_required,
        requires_operator_approval=requires_operator_approval,
        notes=notes,
    )


def build_continuity_plan(
    *,
    project_id: str,
    starter_image_prompt: str,
    clip_prompts: list[str],
    target_platform: str = "shorts",
    aspect_ratio: str = "9:16",
    duration_seconds: int = 10,
    image_quality: str = DEFAULT_IMAGE_QUALITY,
    image_count: int = DEFAULT_IMAGE_COUNT,
    max_wait_minutes_per_clip: int = 20,
) -> RunwayContinuityPlan:
    if not starter_image_prompt.strip():
        raise ValueError("starter_image_prompt is required")
    if not clip_prompts:
        raise ValueError("clip_prompts must contain at least one clip")
    return RunwayContinuityPlan(
        project_id=project_id,
        starter_image=StarterImagePlan(
            prompt=starter_image_prompt.strip(),
            aspect_ratio=aspect_ratio,
            image_quality=image_quality,
            image_count=image_count,
        ),
        clip_prompts=tuple(str(p).strip() for p in clip_prompts),
        target_platform=target_platform,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds,
        image_quality=image_quality,
        image_count=image_count,
        max_wait_minutes_per_clip=max_wait_minutes_per_clip,
        completion_rule=COMPLETION_RULE_EXPRESSION,
    )


def build_dry_run_steps(plan: RunwayContinuityPlan) -> list[RunwayContinuityStep]:
    """Ordered simulated workflow — Image Gen starter -> Use to Video -> multi-clip continuity."""
    steps: list[RunwayContinuityStep] = []
    order = 0

    def add(
        step_id: str,
        *,
        phase: str,
        action: str,
        control_key: str | None = None,
        manual_required: bool = False,
        requires_operator_approval: bool = False,
        notes: str = "",
    ) -> None:
        nonlocal order
        order += 1
        steps.append(
            _step(
                f"{order:03d}_{step_id}",
                phase=phase,
                action=action,
                control_key=control_key,
                manual_required=manual_required,
                requires_operator_approval=requires_operator_approval or (
                    control_key in APPROVAL_GATED_CONTROLS
                ),
                notes=notes,
            )
        )

    add(
        "image_generation_open",
        phase="starter_image",
        action="Open Runway Image Generation (mode=tools&tool=image)",
        control_key="image_prompt_input",
        notes="Do not use Multi-Shot Video workflow",
    )
    add(
        "fill_image_prompt",
        phase="starter_image",
        action="Simulate fill starter image prompt",
        control_key="image_prompt_input",
        notes=f"prompt_chars={len(plan.starter_image_prompt)}",
    )
    add(
        "select_image_9_16",
        phase="starter_image",
        action="Simulate open aspect menu and select 9:16",
        control_key=image_aspect_control_key(plan.aspect_ratio),
        notes=f"default_aspect={plan.aspect_ratio}",
    )
    add(
        "select_image_count",
        phase="starter_image",
        action="Simulate open image count menu and select default count",
        control_key=image_count_control_key(plan.image_count),
        notes=f"default_count={plan.image_count}",
    )
    add(
        "select_image_quality",
        phase="starter_image",
        action="Simulate open quality menu and select configured quality",
        control_key=image_quality_control_key(plan.image_quality),
        notes=f"default_quality={plan.image_quality}",
    )
    add(
        "verify_starter_image_settings",
        phase="starter_image",
        action="Verify/enforce starter image settings before Generate approval",
        control_key=image_quality_control_key(plan.image_quality),
        notes=(
            f"aspect={plan.aspect_ratio}; count={plan.image_count}; quality={plan.image_quality}; "
            "must pass before image_generate_button approval"
        ),
    )
    add(
        "preclean_starter_image_workspace",
        phase="starter_image",
        action="Close stale image previews/modals before Generate",
        notes="Safe close only — no destructive account/project controls",
    )
    add(
        "image_generate_manual_required",
        phase="starter_image",
        action="STOP — operator must click Generate manually (image)",
        control_key="image_generate_button",
        manual_required=True,
        requires_operator_approval=True,
        notes="Dry-run does not click Generate",
    )
    add(
        "wait_for_image_ready_manual",
        phase="starter_image",
        action="STOP — operator waits for generated image output",
        manual_required=True,
        notes="Use image_download_button or visual confirmation when mapped",
    )
    add(
        "clear_image_prompt_after_generation",
        phase="starter_image",
        action="Clear image prompt input after image is ready",
        control_key="image_prompt_input",
        notes="Verify prompt box empty before routing starter image to video",
    )
    add(
        "use_starter_image_for_video",
        phase="starter_image",
        action=(
            "Route starter image to video via Apply / Use for Video / Use to Video "
            "on latest result card"
        ),
        control_key="image_use_to_video_option",
        notes="Direct result action preferred; app menu fallback; wait for video UI",
    )
    add(
        "cleanup_used_image_card_after_use_to_video",
        phase="starter_image",
        action="Remove used latest image card or mark fingerprint consumed",
        control_key="image_card_remove_button",
        notes=(
            "Only the selected latest card after video transition verified; "
            "image_card_remove_button is optional — marks consumed if remove fails"
        ),
    )

    for clip in plan.clips:
        if clip.clip_index > 1:
            add(
                f"use_frame_for_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action=(
                    f"Seek clip {clip.clip_index - 1} video to last safe frame, "
                    f"then Use Frame scoped to that card for clip {clip.clip_index}"
                ),
                control_key="use_frame_button",
                notes=(
                    "Continuity chain — never starter image; "
                    f"source_clip={clip.clip_index - 1}; last_safe_frame"
                ),
            )
            add(
                f"settle_after_use_frame_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action=(
                    "Logical settle after Use Frame — wait for composer remount "
                    "(no real wait in dry-run)"
                ),
                notes="Verify prompt editor interactable before clip prompt fill",
            )
            add(
                f"verify_use_frame_handoff_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action=(
                    "Verify Use Frame composer handoff — composer ready OR "
                    "generation already started (not card-only selection)"
                ),
                notes="Paths: composer_ready | generation_already_started; invalid card-only fails",
            )

        add(
            f"video_prompt_clip_{clip.clip_index}",
            phase=f"clip_{clip.clip_index}",
            action=f"Simulate fill video prompt for clip {clip.clip_index}",
            control_key="prompt_input",
            notes=f"prompt_chars={len(clip.prompt)}",
        )

        if clip.clip_index == 1:
            add(
                f"select_video_aspect_9_16_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action="Verify/simulate 9:16 video aspect (inherited from starter)",
                control_key="aspect_ratio_9_16",
                notes="Reference image from Use to Video should preserve 9:16",
            )

        add(
            f"select_duration_10s_clip_{clip.clip_index}",
            phase=f"clip_{clip.clip_index}",
            action="Simulate open duration menu and select 10s",
            control_key="duration_10s",
            notes=f"default_duration={plan.duration_seconds}s",
        )
        add(
            f"video_generate_manual_required_clip_{clip.clip_index}",
            phase=f"clip_{clip.clip_index}",
            action="STOP — operator must click Generate manually (video)",
            control_key="generate_button",
            manual_required=True,
            requires_operator_approval=True,
        )
        add(
            f"wait_until_completion_signal_clip_{clip.clip_index}",
            phase=f"clip_{clip.clip_index}",
            action="Simulate poll every 30-60s until completion signal",
            notes=(
                f"completion_rule={plan.completion_rule}; "
                f"max_wait_minutes={plan.max_wait_minutes_per_clip}"
            ),
        )

        if clip.is_final:
            add(
                f"final_download_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action="STOP — operator/future phase downloads final MP4",
                control_key="download_mp4_button",
                manual_required=True,
                requires_operator_approval=True,
                notes="Do not click use_frame_button on final clip",
            )
            add(
                f"remove_image_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action="Simulate remove reference image after final clip",
                control_key="remove_image",
                notes="Clears Use Frame residue for next project",
            )
        else:
            add(
                f"download_mp4_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action="STOP — operator/future phase downloads clip MP4",
                control_key="download_mp4_button",
                manual_required=True,
                requires_operator_approval=True,
            )
            add(
                f"settle_after_download_clip_{clip.clip_index}",
                phase=f"clip_{clip.clip_index}",
                action=(
                    "Logical settle after Download MP4 — browser/download UI "
                    "(no real wait in dry-run)"
                ),
                notes="Dismiss save/download overlay; do not assume prompt ready",
            )

    return steps


def run_dry_run(
    plan: RunwayContinuityPlan,
    *,
    map_path: Path | str | None = None,
    ui_map: dict[str, Any] | None = None,
    required_controls: tuple[str, ...] | None = None,
) -> RunwayDryRunResult:
    """Build dry-run plan, validate mapped controls, return simulated steps only."""
    snapshot = resolve_runway_ui_controls(
        ui_map=ui_map,
        map_path=map_path,
        required=required_controls or STARTER_TO_VIDEO_CANONICAL_CONTROLS,
    )

    result = RunwayDryRunResult(
        ok=False,
        plan=plan,
        safety_gates=list(SAFETY_GATES),
    )

    for key, ctrl in snapshot.controls.items():
        result.controls_present[key] = ctrl.source_label or key
        if ctrl.weak_selector and key in snapshot.controls:
            result.controls_weak.append(
                {"control": key, "selector": ctrl.css_selector, "source": ctrl.source_label}
            )

    result.controls_missing = list(snapshot.missing)
    result.controls_invalid = list(snapshot.invalid)
    result.warnings.extend(snapshot.warnings)

    for mandatory in sorted(MANDATORY_FOR_DRY_RUN):
        if mandatory in snapshot.missing:
            result.errors.append(f"missing mandatory control: {mandatory}")
        elif mandatory in snapshot.controls and not snapshot.controls[mandatory].valid:
            result.errors.append(
                f"invalid mandatory control: {mandatory} "
                f"({snapshot.controls[mandatory].invalid_reason})"
            )

    if snapshot.missing:
        result.errors.append(f"missing mapped controls: {', '.join(snapshot.missing)}")
    if snapshot.invalid:
        invalid_names = ", ".join(item["control"] for item in snapshot.invalid)
        result.errors.append(f"invalid mapped controls: {invalid_names}")

    result.steps = build_dry_run_steps(plan)

    approval_steps = [s for s in result.steps if s.requires_operator_approval]
    if not approval_steps:
        result.warnings.append("no approval-gated steps generated")

    result.ok = not result.errors
    return result


def run_default_dry_run_demo(
    *,
    map_path: Path | str | None = None,
    clip_count: int = 3,
) -> RunwayDryRunResult:
    plan = build_continuity_plan(
        project_id="dry_run_demo",
        starter_image_prompt="Cinematic neon rain portrait, vertical framing, moody lighting.",
        clip_prompts=[f"Clip {index} motion beat for continuity chain." for index in range(1, clip_count + 1)],
    )
    return run_dry_run(plan, map_path=map_path)


def load_and_dry_run_from_map(
    *,
    project_id: str,
    starter_image_prompt: str,
    clip_prompts: list[str],
    map_path: Path | str | None = None,
) -> RunwayDryRunResult:
    _ = load_runway_ui_map(map_path=map_path)
    plan = build_continuity_plan(
        project_id=project_id,
        starter_image_prompt=starter_image_prompt,
        clip_prompts=clip_prompts,
    )
    return run_dry_run(plan, map_path=map_path)
