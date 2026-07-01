"""
Phase RUNWAY-STARTER-TO-VIDEO-H — first live operator-approved smoke test.

Single starter image + single video clip. simulate=False, CDP browser required.
Generate and Download remain approval-gated. Stops on selector/page/approval/timeout errors.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from automation.browser_manager import BrowserManager
from content_brain.execution.browser_connectivity_probe import BrowserProbeResult, run_browser_probes
from content_brain.execution.provider_mode_catalog import ProviderModeCatalog
from content_brain.execution.runway_continuity_approval_guard import (
    APPROVAL_GATED_CONTROLS,
    DANGEROUS_CONTROL_LABELS,
)
from content_brain.execution.runway_continuity_dry_run import run_dry_run
from content_brain.execution.runway_continuity_models import (
    SEMI_AUTO_STATUS_AWAITING_APPROVAL,
    SEMI_AUTO_STATUS_COMPLETED,
    SEMI_AUTO_STATUS_FAILED,
    SEMI_AUTO_STATUS_MANUAL_HOLD,
    RunwaySemiAutoSession,
)
from content_brain.execution.runway_continuity_semi_auto import (
    RunwayContinuitySemiAutoEngine,
    build_semi_auto_session,
)
from content_brain.execution.runway_phase_i_download_tracker import (
    RunwayPhaseIDownloadTracker,
    default_runway_download_dir,
)
from content_brain.platform.run_isolation import record_latest_run_attempt
from content_brain.execution.content_brain_live_smoke_handoff import resolve_live_smoke_prompts
from content_brain.execution.runway_auto_execution_controller import (
    AUTO_BRIDGE_VERSION,
    build_auto_execution_controller,
)
from content_brain.execution.runway_execution_mode import (
    DEFAULT_LIVE_SMOKE_EXECUTION_MODE,
    EXECUTION_MODE_FULL_AUTO,
    normalize_execution_mode,
)
from content_brain.execution.runway_story_progression_validator import validate_story_progression
from content_brain.execution.runway_ui_map_loader import (
    DEFAULT_MAP_PATH,
    STARTER_TO_VIDEO_CANONICAL_CONTROLS,
    resolve_runway_ui_controls,
)
from content_brain.execution.runway_live_post_processor import (
    evaluate_post_processing_eligibility,
    run_live_post_processing,
)
from content_brain.execution.runway_ui_navigator import MappedRunwayUINavigator

LIVE_SMOKE_VERSION = "runway_starter_to_video_h_v1"
PHASE_I_VERSION = "runway_starter_to_video_i_3clip_v1"
SMOKE_CLIP_COUNT = 1
PHASE_I_CLIP_COUNT = 3
RUNTIME_NAME_PHASE_H = "Phase H 1-Clip Smoke Runtime"
RUNTIME_NAME_PHASE_I = "Phase I 3-Clip Continuity Runtime"
ROUTE_NAME_PHASE_H = "runway_live_smoke_phase_h_1clip"
ROUTE_NAME_PHASE_I = "runway_live_smoke_phase_i_3clip"
PHASE_I_APPROVAL_PLAN = "phase_i_7_gate"
MAX_COMPLETION_WAIT_MINUTES = 25
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = ROOT / "project_brain" / "runway_live_smoke_artifacts"
DEFAULT_REPORT_JSON = ROOT / "project_brain" / "runway_live_smoke_last_report.json"
DEFAULT_REPORT_MD = ROOT / "project_brain" / "PHASE_RUNWAY_STARTER_TO_VIDEO_H_LIVE_SMOKE_REPORT.md"
DEFAULT_PHASE_I_REPORT_JSON = ROOT / "project_brain" / "runway_phase_i_3clip_last_report.json"
DEFAULT_PHASE_I_REPORT_MD = ROOT / "project_brain" / "PHASE_RUNWAY_STARTER_TO_VIDEO_I_3CLIP_LIVE_REPORT.md"
DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS = ROOT / "project_brain" / "runway_phase_i_last_failure_diagnostics.json"


def expected_approval_gate_count(clip_count: int) -> int:
    """Image generate + per-clip video generate + per-clip download."""
    clips = max(1, int(clip_count))
    return 1 + (2 * clips)


def flatten_use_frame_last_frame_report_fields(
    use_frame_last_frame_by_clip: dict[str, Any],
) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, entry in use_frame_last_frame_by_clip.items():
        if not isinstance(entry, dict):
            continue
        prefix = f"clip_{key}"
        flat[f"{prefix}_use_frame_source_clip"] = entry.get("use_frame_source_clip")
        flat[f"{prefix}_use_frame_source"] = entry.get("use_frame_source")
        flat[f"{prefix}_previous_clip_seeked_to_last_frame"] = entry.get(
            "previous_clip_seeked_to_last_frame"
        )
        flat[f"{prefix}_seek_time_used"] = entry.get("seek_time_used")
        flat[f"{prefix}_seek_strategy"] = entry.get("seek_strategy")
    return flat

ApprovalCallback = Callable[[str, str, str], bool]
ManualAckCallback = Callable[[str, str], bool]


def _now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "run")).strip("_")
    return cleaned[:48] or "run"


def browser_probe_is_ok(probe: Any) -> bool:
    return bool(
        getattr(probe, "ok", False)
        or getattr(probe, "success", False)
        or getattr(probe, "connected", False)
        or getattr(probe, "is_ok", False)
        or getattr(probe, "available", False)
        or getattr(probe, "passed", False)
    )


def browser_probe_message(probe: Any) -> str:
    message = str(getattr(probe, "message", "") or "").strip()
    if message:
        return message
    reject_code = str(getattr(probe, "reject_code", "") or "").strip()
    if reject_code:
        return reject_code
    checks = getattr(probe, "checks", None) or []
    for check in reversed(checks):
        if isinstance(check, dict) and not check.get("passed"):
            return str(check.get("message") or check.get("id") or "browser probe failed")
    return "browser probe failed"


def browser_probe_to_dict(probe: Any) -> dict[str, Any]:
    if probe is None:
        return {}
    if isinstance(probe, dict):
        return dict(probe)
    if isinstance(probe, BrowserProbeResult):
        return {
            "passed": probe.passed,
            "checks": list(probe.checks),
            "reject_code": probe.reject_code,
            "message": probe.message,
            "ok": browser_probe_is_ok(probe),
        }
    payload: dict[str, Any] = {}
    for key in ("passed", "ok", "success", "connected", "is_ok", "available", "message", "reject_code"):
        if hasattr(probe, key):
            payload[key] = getattr(probe, key)
    checks = getattr(probe, "checks", None)
    if checks is not None:
        payload["checks"] = list(checks)
    payload["ok"] = browser_probe_is_ok(probe)
    return payload


@dataclass
class ApprovalEvent:
    control_key: str
    step_id: str
    label: str
    granted: bool
    operator: str = ""
    timestamp: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_key": self.control_key,
            "step_id": self.step_id,
            "label": self.label,
            "granted": self.granted,
            "operator": self.operator,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }


@dataclass
class RunwayLiveSmokeReport:
    phase: str = LIVE_SMOKE_VERSION
    project_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    ok: bool = False
    simulate: bool = False
    browser_connected: bool = False
    browser_probe_message: str = ""
    browser_probe: dict[str, Any] = field(default_factory=dict)
    page_url: str = ""
    controls_resolved: int = 0
    controls_missing: list[str] = field(default_factory=list)
    dry_run_ok: bool = False
    step_count: int = 0
    clip_count: int = SMOKE_CLIP_COUNT
    approvals_requested: list[ApprovalEvent] = field(default_factory=list)
    approvals_granted: list[ApprovalEvent] = field(default_factory=list)
    manual_holds: list[dict[str, str]] = field(default_factory=list)
    image_generation_result: str = "not_started"
    video_completion_detected: bool = False
    completion_signals: list[str] = field(default_factory=list)
    download_attempted: bool = False
    download_confirmed: bool = False
    remove_image_executed: bool = False
    detected_aspect_ratio: str = ""
    detected_image_count: str = ""
    detected_image_quality: str = ""
    settings_verified: bool = False
    image_prompt_cleared: bool = False
    prompt_text_before_clear: str = ""
    prompt_text_after_clear: str = ""
    latest_image_card_found: bool = False
    latest_image_card_index: int = -1
    selected_image_card_fingerprint: str = ""
    selected_image_card_index: int = -1
    card_prompt_text: str = ""
    card_bounding_box: dict[str, float] = field(default_factory=dict)
    video_transition_verified: bool = False
    current_url_after_transition: str = ""
    used_image_card_removed: bool = False
    used_image_card_marked_consumed: bool = False
    video_generation_started: bool = False
    browser_state: str = ""
    detected_video_aspect_ratio: str = ""
    detected_video_duration: str = ""
    video_settings_verified: bool = False
    use_frame_after_clips: list[int] = field(default_factory=list)
    downloads_approved_count: int = 0
    video_generates_approved_count: int = 0
    clips_completed: int = 0
    story_brief_present: bool = False
    story_brief_title: str = ""
    story_brief_logline: str = ""
    story_brief_character: str = ""
    story_brief_setting: str = ""
    starter_prompt_chars: int = 0
    continuity_notes: list[str] = field(default_factory=list)
    runtime_name: str = ""
    route_name: str = ""
    is_phase_i_continuity: bool = False
    approval_plan: str = ""
    preclean_attempted: bool = False
    stale_image_preview_detected: bool = False
    stale_preview_closed: bool = False
    preclean_notes: list[str] = field(default_factory=list)
    clip_1_downloaded: bool = False
    clip_2_downloaded: bool = False
    clip_3_downloaded: bool = False
    clip_2_prompt_ready_checked: bool = False
    clip_2_prompt_ready_result: str = ""
    clip_2_generation_detected_after_prompt_timeout: bool = False
    clip_3_prompt_ready_checked: bool = False
    clip_3_prompt_ready_result: str = ""
    clip_3_generation_detected_after_prompt_timeout: bool = False
    clip_2_use_frame_handoff_checked: bool = False
    clip_2_use_frame_handoff_result: str = ""
    clip_2_reference_thumbnail_detected: bool = False
    clip_2_prompt_interactable_after_use_frame: bool = False
    clip_3_use_frame_handoff_checked: bool = False
    clip_3_use_frame_handoff_result: str = ""
    clip_3_reference_thumbnail_detected: bool = False
    clip_3_prompt_interactable_after_use_frame: bool = False
    clip_1_download_strategy: str = ""
    clip_2_download_strategy: str = ""
    clip_3_download_strategy: str = ""
    clip_1_download_scoped_to_card: bool = False
    clip_2_download_scoped_to_card: bool = False
    clip_3_download_scoped_to_card: bool = False
    artifact_card_assignments: dict[str, Any] = field(default_factory=dict)
    downloaded_file_paths: list[str] = field(default_factory=list)
    total_downloads_completed: int = 0
    download_dir: str = ""
    download_records: list[dict[str, Any]] = field(default_factory=list)
    clip_1_completion_verified: bool = False
    clip_2_completion_verified: bool = False
    clip_3_completion_verified: bool = False
    clip_1_completion_reason: str = ""
    clip_2_completion_reason: str = ""
    clip_3_completion_reason: str = ""
    clip_1_download_gate_released_after_completion: bool = False
    clip_2_download_gate_released_after_completion: bool = False
    clip_3_download_gate_released_after_completion: bool = False
    early_approval_rejections_count: int = 0
    approval_gate_safety_enabled: bool = True
    use_frame_last_frame_by_clip: dict[str, Any] = field(default_factory=dict)
    story_progression_audit: dict[str, Any] = field(default_factory=dict)
    final_status: str = ""
    stopped_reason: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    action_log: list[dict[str, Any]] = field(default_factory=list)
    prompt_source: str = ""
    content_brain_run_id: str = ""
    prompt_cleanup_used: bool = False
    prompt_noise_score: float = 0.0
    prompt_efficiency_score: float = 0.0
    handoff_loaded_from: str = ""
    handoff_version: str = ""
    content_brain_topic: str = ""
    topic_label: str = ""
    seo_title: str = ""
    story_summary: str = ""
    starter_prompt_preview: str = ""
    execution_mode: str = DEFAULT_LIVE_SMOKE_EXECUTION_MODE
    auto_execution_timeline: list[dict[str, Any]] = field(default_factory=list)
    auto_execution_bridge_version: str = AUTO_BRIDGE_VERSION
    current_step_id: str = ""
    last_auto_action: str = ""
    next_auto_action: str = ""
    auto_validation_state: str = ""
    post_processing_enabled: bool = False
    post_processing_status: str = ""
    assembly_status: str = ""
    final_video_path: str = ""
    publish_package_status: str = ""
    publish_package_folder: str = ""
    post_processing_warnings: list[str] = field(default_factory=list)
    visual_continuity_status: str = ""
    visual_continuity_report_path: str = ""
    visual_continuity_overall_pass: bool = False
    visual_continuity_overall_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "project_id": self.project_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "ok": self.ok,
            "simulate": self.simulate,
            "browser_connected": self.browser_connected,
            "browser_probe_message": self.browser_probe_message,
            "browser_probe": dict(self.browser_probe),
            "page_url": self.page_url,
            "controls_resolved": self.controls_resolved,
            "controls_missing": list(self.controls_missing),
            "dry_run_ok": self.dry_run_ok,
            "step_count": self.step_count,
            "clip_count": self.clip_count,
            "approvals_requested": [item.to_dict() for item in self.approvals_requested],
            "approvals_granted": [item.to_dict() for item in self.approvals_granted],
            "manual_holds": list(self.manual_holds),
            "image_generation_result": self.image_generation_result,
            "video_completion_detected": self.video_completion_detected,
            "completion_signals": list(self.completion_signals),
            "download_attempted": self.download_attempted,
            "download_confirmed": self.download_confirmed,
            "remove_image_executed": self.remove_image_executed,
            "detected_aspect_ratio": self.detected_aspect_ratio,
            "detected_image_count": self.detected_image_count,
            "detected_image_quality": self.detected_image_quality,
            "settings_verified": self.settings_verified,
            "image_prompt_cleared": self.image_prompt_cleared,
            "prompt_text_before_clear": self.prompt_text_before_clear,
            "prompt_text_after_clear": self.prompt_text_after_clear,
            "latest_image_card_found": self.latest_image_card_found,
            "latest_image_card_index": self.latest_image_card_index,
            "selected_image_card_fingerprint": self.selected_image_card_fingerprint,
            "selected_image_card_index": self.selected_image_card_index,
            "card_prompt_text": self.card_prompt_text,
            "card_bounding_box": dict(self.card_bounding_box),
            "video_transition_verified": self.video_transition_verified,
            "current_url_after_transition": self.current_url_after_transition,
            "used_image_card_removed": self.used_image_card_removed,
            "used_image_card_marked_consumed": self.used_image_card_marked_consumed,
            "video_generation_started": self.video_generation_started,
            "browser_state": self.browser_state,
            "detected_video_aspect_ratio": self.detected_video_aspect_ratio,
            "detected_video_duration": self.detected_video_duration,
            "video_settings_verified": self.video_settings_verified,
            "use_frame_after_clips": list(self.use_frame_after_clips),
            "downloads_approved_count": self.downloads_approved_count,
            "video_generates_approved_count": self.video_generates_approved_count,
            "clips_completed": self.clips_completed,
            "story_brief_present": self.story_brief_present,
            "story_brief_title": self.story_brief_title,
            "story_brief_logline": self.story_brief_logline,
            "story_brief_character": self.story_brief_character,
            "story_brief_setting": self.story_brief_setting,
            "starter_prompt_chars": self.starter_prompt_chars,
            "continuity_notes": list(self.continuity_notes),
            "runtime_name": self.runtime_name,
            "route_name": self.route_name,
            "is_phase_i_continuity": self.is_phase_i_continuity,
            "approval_plan": self.approval_plan,
            "preclean_attempted": self.preclean_attempted,
            "stale_image_preview_detected": self.stale_image_preview_detected,
            "stale_preview_closed": self.stale_preview_closed,
            "preclean_notes": list(self.preclean_notes),
            "clip_1_downloaded": self.clip_1_downloaded,
            "clip_2_downloaded": self.clip_2_downloaded,
            "clip_3_downloaded": self.clip_3_downloaded,
            "clip_2_prompt_ready_checked": self.clip_2_prompt_ready_checked,
            "clip_2_prompt_ready_result": self.clip_2_prompt_ready_result,
            "clip_2_generation_detected_after_prompt_timeout": (
                self.clip_2_generation_detected_after_prompt_timeout
            ),
            "clip_3_prompt_ready_checked": self.clip_3_prompt_ready_checked,
            "clip_3_prompt_ready_result": self.clip_3_prompt_ready_result,
            "clip_3_generation_detected_after_prompt_timeout": (
                self.clip_3_generation_detected_after_prompt_timeout
            ),
            "clip_2_use_frame_handoff_checked": self.clip_2_use_frame_handoff_checked,
            "clip_2_use_frame_handoff_result": self.clip_2_use_frame_handoff_result,
            "clip_2_reference_thumbnail_detected": self.clip_2_reference_thumbnail_detected,
            "clip_2_prompt_interactable_after_use_frame": (
                self.clip_2_prompt_interactable_after_use_frame
            ),
            "clip_3_use_frame_handoff_checked": self.clip_3_use_frame_handoff_checked,
            "clip_3_use_frame_handoff_result": self.clip_3_use_frame_handoff_result,
            "clip_3_reference_thumbnail_detected": self.clip_3_reference_thumbnail_detected,
            "clip_3_prompt_interactable_after_use_frame": (
                self.clip_3_prompt_interactable_after_use_frame
            ),
            "clip_1_download_strategy": self.clip_1_download_strategy,
            "clip_2_download_strategy": self.clip_2_download_strategy,
            "clip_3_download_strategy": self.clip_3_download_strategy,
            "clip_1_download_scoped_to_card": self.clip_1_download_scoped_to_card,
            "clip_2_download_scoped_to_card": self.clip_2_download_scoped_to_card,
            "clip_3_download_scoped_to_card": self.clip_3_download_scoped_to_card,
            "artifact_card_assignments": dict(self.artifact_card_assignments),
            "downloaded_file_paths": list(self.downloaded_file_paths),
            "total_downloads_completed": self.total_downloads_completed,
            "download_dir": self.download_dir,
            "download_records": list(self.download_records),
            "clip_1_completion_verified": self.clip_1_completion_verified,
            "clip_2_completion_verified": self.clip_2_completion_verified,
            "clip_3_completion_verified": self.clip_3_completion_verified,
            "clip_1_completion_reason": self.clip_1_completion_reason,
            "clip_2_completion_reason": self.clip_2_completion_reason,
            "clip_3_completion_reason": self.clip_3_completion_reason,
            "clip_1_download_gate_released_after_completion": (
                self.clip_1_download_gate_released_after_completion
            ),
            "clip_2_download_gate_released_after_completion": (
                self.clip_2_download_gate_released_after_completion
            ),
            "clip_3_download_gate_released_after_completion": (
                self.clip_3_download_gate_released_after_completion
            ),
            "early_approval_rejections_count": self.early_approval_rejections_count,
            "approval_gate_safety_enabled": self.approval_gate_safety_enabled,
            "use_frame_last_frame_by_clip": dict(self.use_frame_last_frame_by_clip),
            **flatten_use_frame_last_frame_report_fields(self.use_frame_last_frame_by_clip),
            "story_progression_audit": dict(self.story_progression_audit),
            "final_status": self.final_status,
            "stopped_reason": self.stopped_reason,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "screenshots": list(self.screenshots),
            "action_log": list(self.action_log),
            "prompt_source": self.prompt_source,
            "content_brain_run_id": self.content_brain_run_id,
            "prompt_cleanup_used": self.prompt_cleanup_used,
            "prompt_noise_score": self.prompt_noise_score,
            "prompt_efficiency_score": self.prompt_efficiency_score,
            "handoff_loaded_from": self.handoff_loaded_from,
            "handoff_version": self.handoff_version,
            "content_brain_topic": self.content_brain_topic,
            "topic_label": self.topic_label,
            "seo_title": self.seo_title,
            "story_summary": self.story_summary,
            "starter_prompt_preview": self.starter_prompt_preview,
            "execution_mode": self.execution_mode,
            "auto_execution_timeline": list(self.auto_execution_timeline),
            "auto_execution_bridge_version": self.auto_execution_bridge_version,
            "current_step_id": self.current_step_id,
            "last_auto_action": self.last_auto_action,
            "next_auto_action": self.next_auto_action,
            "auto_validation_state": self.auto_validation_state,
            "post_processing_enabled": self.post_processing_enabled,
            "post_processing_status": self.post_processing_status,
            "assembly_status": self.assembly_status,
            "final_video_path": self.final_video_path,
            "publish_package_status": self.publish_package_status,
            "publish_package_folder": self.publish_package_folder,
            "post_processing_warnings": list(self.post_processing_warnings),
            "visual_continuity_status": self.visual_continuity_status,
            "visual_continuity_report_path": self.visual_continuity_report_path,
            "visual_continuity_overall_pass": self.visual_continuity_overall_pass,
            "visual_continuity_overall_score": self.visual_continuity_overall_score,
        }


def default_interactive_approval(control_key: str, step_id: str, label: str) -> bool:
    print()
    print("=" * 72)
    print(f"OPERATOR APPROVAL REQUIRED: {label}")
    print(f"  control: {control_key}")
    print(f"  step:    {step_id}")
    print("Type APPROVE to continue (anything else cancels this gate).")
    print("=" * 72)
    answer = input("> ").strip().upper()
    return answer == "APPROVE"


def default_interactive_manual_ack(step_id: str, action: str) -> bool:
    print()
    print("-" * 72)
    print(f"MANUAL HOLD: {action}")
    print(f"  step: {step_id}")
    print("Confirm the on-screen condition is satisfied, then type READY.")
    print("-" * 72)
    answer = input("> ").strip().upper()
    return answer == "READY"


def render_live_smoke_report_md(report: RunwayLiveSmokeReport) -> str:
    lines = [
        "# Phase RUNWAY-STARTER-TO-VIDEO-H — Live Operator-Approved Smoke Test Report",
        "",
        f"**Phase:** `{report.phase}`",
        f"**Project:** `{report.project_id}`",
        f"**Mode:** {'Simulate rehearsal (no CDP)' if report.simulate else 'Live CDP smoke'}",
        f"**Started:** {report.started_at or '(not run)'}",
        f"**Finished:** {report.finished_at or '(not run)'}",
        f"**Result:** {'PASS' if report.ok else ('PARTIAL — video generation started' if report.browser_state == 'video_generation_started' else 'FAIL / INCOMPLETE')}",
        "",
        "## Scope (Phase H)",
        "",
        "- 1 starter image + 1 video clip only",
        "- `simulate=False` for real live smoke (CDP Chrome required)",
        "- Generate / Download require explicit operator `APPROVE`",
        "- Manual image-ready hold requires operator `READY`",
        "- No multi-clip loop; no autonomous Generate/Download",
        "",
        "### Expected flow",
        "",
        "1. Prompt Builder → plan (`clip_count=1`)",
        "2. Semi-auto prep (prompt, 9:16, 2K)",
        "3. Pause → `image_generate_button` → operator APPROVE",
        "4. Manual hold → image ready → operator READY",
        "5. App menu → Use to Video",
        "6. Fill video prompt + duration",
        "7. Pause → `generate_button` → operator APPROVE",
        "8. Wait completion (≤ 25 min)",
        "9. Pause → `download_mp4_button` → operator APPROVE",
        "10. `remove_image` → finish",
        "",
        "---",
        "",
        "## Browser & Map",
        "",
        "| Check | Value |",
        "|-------|-------|",
        f"| Browser connected | {'Yes' if report.browser_connected else 'No'} |",
        f"| Probe message | {report.browser_probe_message or '(none)'} |",
        f"| Probe passed | {report.browser_probe.get('passed', '(unknown)')} |",
        f"| Probe reject code | {report.browser_probe.get('reject_code') or '(none)'} |",
        f"| Page URL (last) | {report.page_url or '(none)'} |",
        f"| Controls resolved | {report.controls_resolved}/{len(STARTER_TO_VIDEO_CANONICAL_CONTROLS)} |",
        f"| Controls missing | {', '.join(report.controls_missing) or '(none)'} |",
        f"| Dry-run ok | {'Yes' if report.dry_run_ok else 'No'} |",
        f"| Steps in plan | {report.step_count} |",
        f"| Clip count | {report.clip_count} (single-clip smoke) |",
        "",
        "## Operator Approvals",
        "",
    ]
    if report.approvals_requested:
        lines.append("| Control | Step | Label | Granted | Operator | Time |")
        lines.append("|---------|------|-------|---------|----------|------|")
        for item in report.approvals_requested:
            lines.append(
                f"| `{item.control_key}` | `{item.step_id}` | {item.label} | "
                f"{'Yes' if item.granted else 'No'} | {item.operator or '-'} | {item.timestamp or '-'} |"
            )
    else:
        lines.append("_No approval events recorded._")

    lines.extend(
        [
            "",
            "## Manual Holds",
            "",
        ]
    )
    if report.manual_holds:
        for hold in report.manual_holds:
            lines.append(f"- `{hold.get('step_id', '')}`: {hold.get('action', '')} → {hold.get('result', '')}")
    else:
        lines.append("_None._")

    lines.extend(
        [
            "",
            "## Image Settings Diagnostics",
            "",
            "| Check | Value |",
            "|-------|-------|",
            f"| detected_aspect_ratio | {report.detected_aspect_ratio or '(none)'} |",
            f"| detected_image_count | {report.detected_image_count or '(none)'} |",
            f"| detected_image_quality | {report.detected_image_quality or '(none)'} |",
            f"| settings_verified | {'Yes' if report.settings_verified else 'No'} |",
            f"| image_prompt_cleared | {'Yes' if report.image_prompt_cleared else 'No'} |",
            f"| prompt_text_before_clear | {len(report.prompt_text_before_clear)} chars |",
            f"| prompt_text_after_clear | {len(report.prompt_text_after_clear)} chars |",
            "",
            "## Latest Image Card Diagnostics",
            "",
            "| Check | Value |",
            "|-------|-------|",
            f"| latest_image_card_found | {'Yes' if report.latest_image_card_found else 'No'} |",
            f"| latest_image_card_index | {report.latest_image_card_index} |",
            f"| selected_image_card_fingerprint | {report.selected_image_card_fingerprint or '(none)'} |",
            f"| selected_image_card_index | {report.selected_image_card_index} |",
            f"| card_prompt_text | {report.card_prompt_text[:120] or '(none)'} |",
            f"| card_bounding_box | {report.card_bounding_box or '(none)'} |",
            f"| video_transition_verified | {'Yes' if report.video_transition_verified else 'No'} |",
            f"| current_url_after_transition | {report.current_url_after_transition or '(none)'} |",
            f"| used_image_card_removed | {'Yes' if report.used_image_card_removed else 'No'} |",
            f"| used_image_card_marked_consumed | {'Yes' if report.used_image_card_marked_consumed else 'No'} |",
            f"| video_generation_started | {'Yes' if report.video_generation_started else 'No'} |",
            f"| browser_state | {report.browser_state or '(none)'} |",
            f"| detected_video_aspect_ratio | {report.detected_video_aspect_ratio or '(none)'} |",
            f"| detected_video_duration | {report.detected_video_duration or '(none)'} |",
            f"| video_settings_verified | {'Yes' if report.video_settings_verified else 'No'} |",
            "",
        ]
    )

    latest_shots = [shot for shot in report.screenshots if "latest_image" in shot.lower()]
    if latest_shots:
        lines.extend(
            [
                "### Latest Image Card Screenshots",
                "",
            ]
        )
        for shot in latest_shots:
            lines.append(f"- `{shot}`")
        lines.append("")

    chip_reads = [
        entry
        for entry in report.action_log
        if isinstance(entry, dict) and entry.get("action") == "chip_detect"
    ]
    chip_shots = [shot for shot in report.screenshots if "chip" in shot.lower()]
    if chip_reads or chip_shots:
        lines.extend(
            [
                "### Toolbar Chip Screenshots",
                "",
            ]
        )
        if chip_reads:
            lines.append("| When | Detected chips |")
            lines.append("|------|----------------|")
            for index, entry in enumerate(chip_reads, start=1):
                detail = str(entry.get("detail") or "(none)")
                lines.append(f"| read #{index} | {detail} |")
            lines.append("")
        if chip_shots:
            lines.append("Captured chip diagnostic screenshots:")
            lines.append("")
            for shot in chip_shots:
                lines.append(f"- `{shot}`")
            lines.append("")

    lines.extend(
        [
            "## Execution Results",
            "",
            "| Stage | Result |",
            "|-------|--------|",
            f"| Image generation | {report.image_generation_result} |",
            f"| Video completion detected | {'Yes' if report.video_completion_detected else 'No'} |",
            f"| Completion signals | {', '.join(report.completion_signals) or '(none)'} |",
            f"| Download attempted | {'Yes' if report.download_attempted else 'No'} |",
            f"| Download confirmed | {'Yes' if report.download_confirmed else 'No'} |",
            f"| remove_image executed | {'Yes' if report.remove_image_executed else 'No'} |",
            f"| Final session status | `{report.final_status or '(none)'}` |",
            "",
            "## Safety Stops",
            "",
            f"**Stopped reason:** {report.stopped_reason or '(completed normally)'}",
            "",
        ]
    )
    if report.errors:
        lines.append("### Errors")
        lines.append("")
        for err in report.errors:
            lines.append(f"- {err}")
        lines.append("")
    if report.warnings:
        lines.append("### Warnings")
        lines.append("")
        for warn in report.warnings:
            lines.append(f"- {warn}")
        lines.append("")
    if report.screenshots:
        lines.append("## Screenshots")
        lines.append("")
        for shot in report.screenshots:
            lines.append(f"- `{shot}`")
        lines.append("")

    lines.extend(
        [
            "## Safety Confirmation",
            "",
            "| Gate | Value |",
            "|------|-------|",
            f"| simulate | {report.simulate} |",
            "| Autonomous Generate | Blocked without APPROVE |",
            "| Autonomous Download | Blocked without APPROVE |",
            f"| Max completion wait | {MAX_COMPLETION_WAIT_MINUTES} minutes |",
            "",
            "## Run Command",
            "",
            "**Live CDP smoke (operator at keyboard):**",
            "",
            "```bash",
            "# 1. Open Chrome with CDP (app Open Browser or launcher)",
            "# 2. Log into Runway",
            "python project_brain/run_runway_live_smoke_test.py --story \"Your story idea...\"",
            "```",
            "",
            "**Structural rehearsal (no browser):**",
            "",
            "```bash",
            "python project_brain/run_runway_live_smoke_test.py --simulate --story \"...\"",
            "python project_brain/validate_runway_live_smoke_test.py",
            "```",
            "",
            "**Safety stops:** selector fail · unexpected page · missing approval · completion > 25 min",
            "",
        ]
    )
    return "\n".join(lines)


def _clip_index_from_download_step(step_key: str) -> int:
    if step_key.startswith("final_download_clip_"):
        return int(step_key.rsplit("_", 1)[-1])
    if step_key.startswith("download_mp4_clip_"):
        return int(step_key.rsplit("_", 1)[-1])
    return 0


def _clip_number_from_step_key(step_key: str) -> int:
    if not step_key:
        return 0
    suffix = step_key.rsplit("_", 1)[-1]
    try:
        return int(suffix)
    except ValueError:
        return 0


def _write_phase_i_failure_diagnostics(
    navigator: MappedRunwayUINavigator | None,
    *,
    step_id: str,
    error: str,
    selector_attempted: str = "",
    screenshot_path: str = "",
    clip_number: int = 0,
) -> None:
    if navigator is None:
        payload = {
            "timestamp": _now(),
            "step_id": step_id,
            "clip_number": clip_number,
            "error": error,
            "selector_attempted": selector_attempted,
            "screenshot_path": screenshot_path,
        }
    else:
        payload = navigator.collect_phase_i_failure_diagnostics(
            step_id=step_id,
            selector_attempted=selector_attempted,
            error=error,
            screenshot_path=screenshot_path,
            clip_number=clip_number,
        )
    DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PHASE_I_FAILURE_DIAGNOSTICS.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


class RunwayLiveSmokeRunner:
    """Live CDP continuity runner: 1 starter image + N video clips (Phase H=1, Phase I=3)."""

    def __init__(
        self,
        *,
        story_idea: str,
        project_id: str = "live_smoke_h",
        operator: str = "operator",
        map_path: Path | str | None = None,
        artifact_dir: Path | str | None = None,
        simulate: bool = False,
        clip_count: int = SMOKE_CLIP_COUNT,
        approval_callback: ApprovalCallback | None = None,
        manual_ack_callback: ManualAckCallback | None = None,
        download_confirm_callback: Callable[[], bool] | None = None,
        approval_runtime: Any | None = None,
        e2e_result: dict[str, Any] | None = None,
        execution_mode: str = DEFAULT_LIVE_SMOKE_EXECUTION_MODE,
        strict_topic_authority: bool = False,
        auto_director: bool = False,
        auto_prompt_critic: bool = False,
    ) -> None:
        self.story_idea = story_idea.strip()
        self.project_id = project_id
        self.operator = operator
        self.map_path = Path(map_path) if map_path else DEFAULT_MAP_PATH
        self.artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ARTIFACT_DIR
        self.simulate = simulate
        self.clip_count = max(1, int(clip_count))
        self.execution_mode = normalize_execution_mode(execution_mode)
        self.approval_callback = approval_callback or default_interactive_approval
        self.manual_ack_callback = manual_ack_callback or default_interactive_manual_ack
        self.download_confirm_callback = download_confirm_callback
        self._approval_runtime = approval_runtime
        self.e2e_result = e2e_result
        self.strict_topic_authority = bool(strict_topic_authority)
        self.auto_director = bool(auto_director)
        self.auto_prompt_critic = bool(auto_prompt_critic)
        phase = PHASE_I_VERSION if self.clip_count > 1 else LIVE_SMOKE_VERSION
        is_phase_i = self.clip_count == PHASE_I_CLIP_COUNT
        self.report = RunwayLiveSmokeReport(
            phase=phase,
            project_id=project_id,
            simulate=simulate,
            clip_count=self.clip_count,
            runtime_name=RUNTIME_NAME_PHASE_I if is_phase_i else RUNTIME_NAME_PHASE_H,
            route_name=ROUTE_NAME_PHASE_I if is_phase_i else ROUTE_NAME_PHASE_H,
            is_phase_i_continuity=is_phase_i,
            approval_plan=PHASE_I_APPROVAL_PLAN if is_phase_i else "phase_h_3_gate",
            execution_mode=self.execution_mode,
        )
        self._browser: BrowserManager | None = None
        self._page: Any = None
        self._navigator: MappedRunwayUINavigator | None = None
        self._auto_controller = None
        self._download_tracker: RunwayPhaseIDownloadTracker | None = None
        self._prompt_bundle: Any = None
        self._engine: RunwayContinuitySemiAutoEngine | None = None
        self._session: RunwaySemiAutoSession | None = None

    def run(self) -> RunwayLiveSmokeReport:
        self.report.started_at = _now()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not self.story_idea:
                raise ValueError("story_idea is required")
            self._preflight_map()
            if not self.simulate:
                if not self._connect_browser():
                    return self.report
            else:
                self.report.warnings.append("simulate=True: browser connection skipped")

            bundle, handoff = resolve_live_smoke_prompts(
                story_idea=self.story_idea,
                project_id=self.project_id,
                clip_count=self.clip_count,
                e2e_result=self.e2e_result,
                niche_style="cyberpunk" if self.clip_count > 1 else "cinematic",
                mood="tense hopeful",
                strict_topic_authority=self.strict_topic_authority,
                auto_director=self.auto_director,
                auto_prompt_critic=self.auto_prompt_critic,
            )
            self._apply_handoff_meta(handoff)
            self._capture_prompt_bundle_diagnostics(bundle)
            plan = bundle.to_continuity_plan(max_wait_minutes_per_clip=MAX_COMPLETION_WAIT_MINUTES)
            dry = run_dry_run(plan, map_path=self.map_path)
            self.report.dry_run_ok = dry.ok
            self.report.step_count = len(dry.steps)
            if not dry.ok:
                raise RuntimeError(f"dry-run failed: {'; '.join(dry.errors)}")

            self._assert_clip_plan(dry.steps)

            page = self._page
            self._navigator = MappedRunwayUINavigator.from_map(
                map_path=self.map_path,
                page=page,
                simulate=self.simulate,
            )
            self._navigator.screenshot_fn = lambda label: self._capture_screenshot(label)
            session_id = ""
            if page is not None:
                try:
                    session_id = str(getattr(page, "url", "") or "")
                except Exception:
                    session_id = ""
            self._navigator.configure_phase_i_artifact_tracking(
                project_id=self.project_id,
                session_id=session_id,
                download_strategy="cdp_preferred",
                fallback_to_ui_download=True,
                clip_count=self.clip_count,
            )
            self._navigator.phase_i_progress_callback = self._on_phase_i_progress
            self._download_tracker = RunwayPhaseIDownloadTracker(
                default_runway_download_dir(ROOT),
                simulate=self.simulate,
                project_id=self.project_id,
            )
            self.report.download_dir = str(self._download_tracker.download_dir)
            self._auto_controller = build_auto_execution_controller(
                navigator=self._navigator,
                simulate=self.simulate,
                execution_mode=self.execution_mode,
            )
            self._engine = RunwayContinuitySemiAutoEngine(
                self._navigator,
                simulate=self.simulate,
                auto_controller=self._auto_controller,
            )
            self._session = build_semi_auto_session(plan, map_path=self.map_path)
            if self._approval_runtime is not None:
                self._approval_runtime.set_execution_timeline(
                    execution_mode=self.execution_mode,
                    last_action="run_started",
                    next_action="starter_image_pipeline",
                    validation_state="full_auto" if self.execution_mode == "FULL_AUTO" else self.execution_mode,
                )

            self._drive_until_done()
            self.report.ok = self._session.status == SEMI_AUTO_STATUS_COMPLETED
            self.report.final_status = self._session.status
            if self._session.completion_signals:
                self.report.completion_signals = list(self._session.completion_signals)
                self.report.video_completion_detected = True
        except Exception as exc:
            self.report.ok = False
            self.report.errors.append(str(exc))
            failed_step_id = ""
            selector_attempted = ""
            if self._session is not None and 0 <= self._session.current_step_index < len(self._session.steps):
                failed_step = self._session.steps[self._session.current_step_index]
                failed_step_id = failed_step.step_id
                selector_attempted = str(failed_step.control_key or "")
            elif self.report.stopped_reason:
                failed_step_id = self.report.stopped_reason
            step_key = failed_step_id.split("_", 1)[-1] if failed_step_id else ""
            diagnostic_steps = (
                step_key in {
                    "use_starter_image_for_video",
                    "image_use_to_video",
                }
                or step_key.startswith("video_prompt_clip_")
                or step_key.startswith("settle_after_")
                or step_key.startswith("verify_use_frame_handoff_clip_")
            )
            if diagnostic_steps:
                clip_num = _clip_number_from_step_key(step_key)
                screenshot_path = self._capture_screenshot("phase_i_failure")
                _write_phase_i_failure_diagnostics(
                    self._navigator,
                    step_id=failed_step_id or "unknown",
                    error=str(exc),
                    selector_attempted=selector_attempted,
                    screenshot_path=screenshot_path,
                    clip_number=clip_num,
                )
            if self.report.video_generation_started:
                self.report.browser_state = "video_generation_started"
            if not self.report.stopped_reason:
                self.report.stopped_reason = str(exc)
            self._capture_screenshot("failure")
        finally:
            if self._auto_controller is not None:
                self.report.auto_execution_timeline = self._auto_controller.timeline_dict()
            self.report.finished_at = _now()
            if self._approval_runtime is not None:
                self.report.early_approval_rejections_count = (
                    self._approval_runtime._early_approval_rejections_count
                )
                self._approval_runtime.set_execution_timeline(
                    execution_mode=self.execution_mode,
                    current_step_id=self.report.current_step_id,
                    last_action=self.report.last_auto_action,
                    next_action=self.report.next_auto_action or (
                        "completed" if self.report.ok else "failed"
                    ),
                    validation_state=self.report.auto_validation_state
                    or ("pass" if self.report.ok else "fail"),
                    timeline=self.report.auto_execution_timeline,
                )
            if self.report.video_generation_started and not self.report.ok and not self.report.browser_state:
                self.report.browser_state = "video_generation_started"
            if self._navigator is not None:
                self.report.action_log = [log.to_dict() for log in self._navigator.action_log]
            if self._page is not None:
                try:
                    self.report.page_url = str(self._page.url or "")
                except Exception:
                    pass
            eligible, _reason, _context = evaluate_post_processing_eligibility(self.report)
            if eligible and not self.simulate:
                try:
                    run_live_post_processing(self.report, project_root=ROOT)
                except Exception as exc:
                    self.report.post_processing_enabled = True
                    self.report.post_processing_status = "failed"
                    self.report.post_processing_warnings.append(str(exc))
            elif not self.simulate and not eligible:
                self.report.post_processing_enabled = False
                self.report.post_processing_status = "skipped"
                self.report.post_processing_warnings.append(_reason)
            self._persist_report()
            if self._browser is not None:
                try:
                    self._browser.close()
                except Exception:
                    pass

        return self.report

    def _apply_handoff_meta(self, handoff: Any) -> None:
        self.report.prompt_source = str(getattr(handoff, "prompt_source", "") or "")
        self.report.content_brain_run_id = str(getattr(handoff, "content_brain_run_id", "") or "")
        self.report.prompt_cleanup_used = bool(getattr(handoff, "prompt_cleanup_used", False))
        self.report.prompt_noise_score = float(getattr(handoff, "prompt_noise_score", 0.0) or 0.0)
        self.report.prompt_efficiency_score = float(getattr(handoff, "prompt_efficiency_score", 0.0) or 0.0)
        self.report.handoff_loaded_from = str(getattr(handoff, "loaded_from", "") or "")
        self.report.handoff_version = str(getattr(handoff, "handoff_version", "") or "")
        self.report.content_brain_topic = str(getattr(handoff, "content_brain_topic", "") or "")
        self.report.topic_label = str(getattr(handoff, "topic_label", "") or "")
        self.report.seo_title = str(getattr(handoff, "seo_title", "") or "")
        self.report.story_summary = str(getattr(handoff, "story_summary", "") or "")
        self.report.starter_prompt_preview = str(getattr(handoff, "starter_prompt_preview", "") or "")
        for warning in list(getattr(handoff, "warnings", []) or []):
            if warning and warning not in self.report.warnings:
                self.report.warnings.append(str(warning))

    def _capture_prompt_bundle_diagnostics(self, bundle: Any) -> None:
        brief = getattr(bundle, "story_brief", None)
        self.report.starter_prompt_chars = len(str(getattr(bundle, "starter_image_prompt", "") or ""))
        if brief is None:
            self.report.warnings.append("story_brief missing from prompt bundle")
            return
        self.report.story_brief_present = True
        self.report.story_brief_title = str(getattr(brief, "title", "") or "")
        self.report.story_brief_logline = str(getattr(brief, "logline", "") or "")
        self.report.story_brief_character = str(getattr(brief, "main_character", "") or "")
        self.report.story_brief_setting = str(getattr(brief, "setting", "") or "")
        progression = validate_story_progression(brief, bundle)
        self.report.story_progression_audit = progression
        if not progression.get("all_pass"):
            self.report.warnings.append("story progression audit flagged weak discovery/escalation/payoff separation")
        character = self.report.story_brief_character.lower()
        anchors = getattr(bundle, "continuity_anchors", None)
        notes: list[str] = []
        if anchors is not None:
            notes.append(f"character={getattr(anchors, 'character', '')}")
            notes.append(f"location={getattr(anchors, 'location', '')}")
            notes.append(f"lighting={getattr(anchors, 'lighting', '')}")
            notes.append(f"palette={getattr(anchors, 'palette', '')}")
            notes.append(f"camera={getattr(anchors, 'camera', '')}")
        for index, prompt in enumerate(getattr(bundle, "clip_prompts", []) or [], start=1):
            lowered = str(prompt).lower()
            if "continuity lock" in lowered:
                notes.append(f"clip_{index}_continuity_lock=present")
            if index == 1 and ("use to video" in lowered or "starter reference" in lowered):
                notes.append("clip_1_use_to_video_language=present")
            if index > 1 and "use frame" in lowered:
                notes.append(f"clip_{index}_use_frame_language=present")
            if character and character.split()[0] in lowered:
                notes.append(f"clip_{index}_character_anchor=present")
        self.report.continuity_notes = notes

    def _preflight_map(self) -> None:
        snap = resolve_runway_ui_controls(map_path=self.map_path)
        self.report.controls_resolved = len(snap.controls)
        self.report.controls_missing = list(snap.missing)
        if not snap.ok:
            raise RuntimeError(
                f"UI map not ready: missing={snap.missing}, invalid={snap.invalid}"
            )

    def _connect_browser(self) -> bool:
        catalog = ProviderModeCatalog.load(ROOT)
        family = catalog.get_family("runway") or {}
        browser_config = dict(family.get("browser_config") or {})
        browser_config.setdefault("cdp_url", "http://127.0.0.1:9222")
        probe = run_browser_probes(browser_config, project_root=ROOT, require_playwright_attach=True)
        self.report.browser_probe = browser_probe_to_dict(probe)
        self.report.browser_probe_message = browser_probe_message(probe)
        if not browser_probe_is_ok(probe):
            reason = self.report.browser_probe_message or "browser probe failed"
            self.report.stopped_reason = f"browser probe failed: {reason}"
            self.report.errors.append(self.report.stopped_reason)
            return False
        try:
            self._browser = BrowserManager()
            self._page = self._browser.launch()
        except Exception as exc:
            self.report.stopped_reason = f"browser launch failed: {exc}"
            self.report.errors.append(self.report.stopped_reason)
            return False
        self.report.browser_connected = True
        self.report.page_url = str(getattr(self._page, "url", "") or "")
        return True

    def _assert_clip_plan(self, steps: list[Any]) -> None:
        clip_count = self.clip_count
        step_keys = [s.step_id.split("_", 1)[-1] for s in steps]
        use_frame_steps = [k for k in step_keys if k.startswith("use_frame_for_clip_")]

        if clip_count == 1:
            if use_frame_steps:
                raise RuntimeError("single-clip plan must not include use_frame_for_clip_* steps")
        else:
            expected_use_frame = [f"use_frame_for_clip_{index}" for index in range(2, clip_count + 1)]
            for key in expected_use_frame:
                if key not in step_keys:
                    raise RuntimeError(f"{clip_count}-clip plan missing {key}")
            if f"use_frame_for_clip_{clip_count + 1}" in step_keys:
                raise RuntimeError("plan must not use use_frame after final clip")

        gated = [s for s in steps if s.control_key in APPROVAL_GATED_CONTROLS]
        expected_gates = expected_approval_gate_count(clip_count)
        if len(gated) != expected_gates:
            raise RuntimeError(
                f"expected {expected_gates} approval gates for {clip_count}-clip run, got {len(gated)}"
            )

        remove_steps = [k for k in step_keys if k.startswith("remove_image_clip_")]
        if not remove_steps:
            raise RuntimeError("plan must include remove_image on final clip")
        final_remove = f"remove_image_clip_{clip_count}"
        if final_remove not in step_keys:
            raise RuntimeError(f"plan must end with {final_remove}")

    def _drive_until_done(self) -> None:
        assert self._engine is not None and self._session is not None
        engine = self._engine
        session = self._session
        max_iterations = len(session.steps) * 4
        iteration = 0

        while session.status not in {SEMI_AUTO_STATUS_COMPLETED, SEMI_AUTO_STATUS_FAILED}:
            iteration += 1
            if iteration > max_iterations:
                raise RuntimeError("smoke loop exceeded safe iteration limit")

            if session.status == SEMI_AUTO_STATUS_AWAITING_APPROVAL:
                self._handle_approval_gate(session, engine)
                continue

            if session.status == SEMI_AUTO_STATUS_MANUAL_HOLD:
                self._handle_manual_hold(session, engine)
                continue

            before_index = session.current_step_index
            self._verify_page_state_before_advance(session)
            engine.advance(session)
            if self._auto_controller is not None:
                self.report.auto_execution_timeline = self._auto_controller.timeline_dict()
                self._sync_execution_timeline(session, next_action="pipeline_running")
            self._update_progress_markers(session, before_index)

            if session.status == SEMI_AUTO_STATUS_FAILED:
                step = session.steps[session.current_step_index]
                result = session.step_results[session.current_step_index]
                raise RuntimeError(
                    f"step failed at {step.step_id}: {result.error or result.notes or 'unknown'}"
                )

    def _clip_index_from_step_id(self, step_id: str) -> int:
        import re

        match = re.search(r"clip_(\d+)", str(step_id or ""), re.I)
        if match:
            return int(match.group(1))
        tokens = [token for token in str(step_id or "").split("_") if token.isdigit()]
        if tokens:
            return int(tokens[-1])
        return 0

    def _expected_prompt_for_step(
        self,
        session: RunwaySemiAutoSession,
        step_id: str,
        control_key: str,
    ) -> str:
        if control_key != "generate_button" or self._session is None:
            return ""
        clip_index = self._clip_index_from_step_id(step_id)
        if clip_index <= 0:
            return ""
        clip_pos = clip_index - 1
        if clip_pos < 0 or clip_pos >= len(session.plan.clips):
            return ""
        return str(session.plan.clips[clip_pos].prompt or "")

    def _apply_last_frame_use_frame_report(self, target_clip_index: int) -> None:
        if self._navigator is None:
            return
        payload = self._navigator.last_last_frame_use_frame_by_clip.get(target_clip_index)
        if payload is None:
            return
        key = str(target_clip_index)
        self.report.use_frame_last_frame_by_clip[key] = payload.to_report_dict()

    def _apply_strict_completion_report(self, clip_index: int, *, gate_released: bool = False) -> None:
        if clip_index <= 0 or self._navigator is None:
            return
        strict = self._navigator.last_strict_completion_by_clip.get(clip_index)
        if strict is None:
            strict = self._navigator.evaluate_strict_clip_completion(clip_index)
        verified = bool(strict.complete)
        reason = str(strict.reason or "")
        if clip_index == 1:
            self.report.clip_1_completion_verified = verified
            self.report.clip_1_completion_reason = reason
            if gate_released:
                self.report.clip_1_download_gate_released_after_completion = verified
        elif clip_index == 2:
            self.report.clip_2_completion_verified = verified
            self.report.clip_2_completion_reason = reason
            if gate_released:
                self.report.clip_2_download_gate_released_after_completion = verified
        elif clip_index == 3:
            self.report.clip_3_completion_verified = verified
            self.report.clip_3_completion_reason = reason
            if gate_released:
                self.report.clip_3_download_gate_released_after_completion = verified

    def _wait_for_download_gate_enabled(
        self,
        *,
        control_key: str,
        step_id: str,
        clip_index: int,
    ) -> None:
        import time

        from content_brain.execution.runway_phase_i_strict_completion_gate import (
            write_strict_completion_diagnostics,
        )

        if self._navigator is None:
            return
        self._navigator.ensure_clip_video_card_assigned(clip_index)
        poll = 2.0 if not self.simulate else 0.05
        while True:
            strict = self._navigator.evaluate_strict_clip_completion(clip_index)
            self._apply_strict_completion_report(clip_index)
            ready = bool(strict.complete)
            enabled = ready
            reason = "" if ready else str(strict.reason or "awaiting_strict_clip_completion")
            if self._approval_runtime is not None:
                self._approval_runtime.set_gate_readiness(
                    ready=ready,
                    enabled=enabled,
                    reason=reason,
                    step_id=step_id,
                    control_key=control_key,
                )
                self.report.early_approval_rejections_count = (
                    self._approval_runtime._early_approval_rejections_count
                )
            if ready:
                self._apply_strict_completion_report(clip_index, gate_released=True)
                return
            if not self.simulate:
                screenshot = self._navigator._capture_chip_diagnostic_screenshot(
                    f"download_gate_wait_clip_{clip_index}"
                )
                write_strict_completion_diagnostics(
                    self._navigator,
                    strict,
                    context="download_gate_not_ready",
                    screenshot_path=screenshot,
                )
            time.sleep(poll)

    def _poll_generate_gate_readiness(
        self,
        *,
        control_key: str,
        step_id: str,
        clip_index: int,
        stop_event: threading.Event,
    ) -> None:
        if self._navigator is None or self._approval_runtime is None:
            return
        poll = 2.0 if not self.simulate else 0.05
        while not stop_event.is_set():
            gen = self._navigator.detect_video_generation_in_progress(clip_index)
            if gen.in_progress:
                enabled = False
                reason = "generation_already_in_progress"
            else:
                video_state = self._navigator.ensure_video_toolbar_settings_verified()
                settings_ok = bool(video_state.video_settings_verified)
                enabled = settings_ok
                reason = "" if settings_ok else "video_settings_not_verified"
            self._approval_runtime.set_gate_readiness(
                ready=enabled,
                enabled=enabled,
                reason=reason,
                step_id=step_id,
                control_key=control_key,
            )
            if stop_event.wait(timeout=poll):
                break

    def _sync_non_download_gate_readiness(self, control_key: str, step_id: str) -> None:
        if self._approval_runtime is None:
            return
        ready = True
        enabled = True
        reason = ""
        if control_key == "image_generate_button":
            state = self._navigator.last_starter_settings if self._navigator else None
            ready = bool(state and state.settings_verified)
            enabled = ready
            reason = "" if ready else "starter_settings_not_verified"
        self._approval_runtime.set_gate_readiness(
            ready=ready,
            enabled=enabled,
            reason=reason,
            step_id=step_id,
            control_key=control_key,
        )

    def _sync_execution_timeline(
        self,
        session: RunwaySemiAutoSession,
        *,
        last_action: str = "",
        next_action: str = "",
        validation_state: str = "",
    ) -> None:
        step_id = str(session.awaiting_step_id or "")
        if not step_id and session.current_step_index < len(session.steps):
            step_id = session.steps[session.current_step_index].step_id
        self.report.current_step_id = step_id
        if last_action:
            self.report.last_auto_action = last_action
        if next_action:
            self.report.next_auto_action = next_action
        if validation_state:
            self.report.auto_validation_state = validation_state
        if self._auto_controller is not None:
            self.report.auto_execution_timeline = self._auto_controller.timeline_dict()
        if self._approval_runtime is not None:
            from content_brain.execution.runway_live_smoke_approval_runtime import (
                RUN_STATUS_RUNNING,
            )

            self._approval_runtime.set_run_status(
                RUN_STATUS_RUNNING,
                detail=f"step={step_id or 'pipeline'}",
            )
            self._approval_runtime.set_execution_timeline(
                execution_mode=self.execution_mode,
                current_step_id=step_id,
                last_action=last_action or self.report.last_auto_action,
                next_action=next_action or self.report.next_auto_action,
                validation_state=validation_state or self.report.auto_validation_state,
                timeline=self.report.auto_execution_timeline,
            )

    def _on_phase_i_progress(
        self,
        *,
        clip_index: int = 0,
        reason: str = "",
        complete: bool = False,
        step_kind: str = "",
    ) -> None:
        if self._session is None:
            return
        step_id = self.report.current_step_id
        if not step_id and self._session.current_step_index < len(self._session.steps):
            step_id = self._session.steps[self._session.current_step_index].step_id
        validation = f"clip_{clip_index}_{reason or step_kind or 'generating'}"
        if complete:
            validation = f"clip_{clip_index}_complete"
        self._sync_execution_timeline(
            self._session,
            last_action=step_kind or f"clip_{clip_index}_progress",
            next_action="wait_strict_completion" if not complete else "advance_pipeline",
            validation_state=validation,
        )

    def _complete_auto_gate(
        self,
        session: RunwaySemiAutoSession,
        engine: RunwayContinuitySemiAutoEngine,
        *,
        control_key: str,
        step_id: str,
        label: str,
        event: ApprovalEvent,
        validation_reason: str,
    ) -> None:
        event.granted = True
        event.operator = "auto_execution"
        event.timestamp = _now()
        event.reason = validation_reason or "auto_validated"
        self.report.approvals_granted.append(
            ApprovalEvent(
                control_key=control_key,
                step_id=step_id,
                label=label,
                granted=True,
                operator="auto_execution",
                timestamp=_now(),
                reason=validation_reason or "auto_validated",
            )
        )
        engine.approve(
            session,
            control_key=control_key,
            step_id=step_id,
            approved_by="auto_execution",
            reason=validation_reason or "auto_validated",
        )
        before_index = session.current_step_index
        engine.advance(session)
        if session.status == SEMI_AUTO_STATUS_FAILED:
            step = session.steps[session.current_step_index]
            result = session.step_results[session.current_step_index]
            raise RuntimeError(
                f"step failed at {step.step_id}: {result.error or result.notes or 'unknown'}"
            )
        self._update_progress_markers(session, before_index)

    def _handle_approval_gate(
        self,
        session: RunwaySemiAutoSession,
        engine: RunwayContinuitySemiAutoEngine,
    ) -> None:
        control_key = str(session.awaiting_control_key or "")
        step_id = str(session.awaiting_step_id or "")
        label = DANGEROUS_CONTROL_LABELS.get(control_key, control_key)
        event = ApprovalEvent(
            control_key=control_key,
            step_id=step_id,
            label=label,
            granted=False,
        )
        self.report.approvals_requested.append(event)

        clip_index = self._clip_index_from_step_id(step_id)
        if (
            self._auto_controller is not None
            and self._auto_controller.should_auto_approve(control_key)
        ):
            validation = self._auto_controller.ensure_ready_for_action(
                control_key=control_key,
                step_id=step_id,
                clip_index=clip_index,
                expected_prompt=self._expected_prompt_for_step(session, step_id, control_key),
            )
            self._auto_controller.record(
                step_id=step_id,
                action=f"auto_{control_key}",
                reason=validation.reason or "validated",
                validation=validation,
                runtime_state=str(session.status),
            )
            self._sync_execution_timeline(
                session,
                last_action=f"auto_{control_key}",
                next_action="advance_pipeline",
                validation_state=validation.reason or ("ok" if validation.ok else "failed"),
            )
            if not validation.ok:
                self.report.stopped_reason = (
                    f"auto validation failed for {control_key}: {validation.reason}"
                )
                raise RuntimeError(self.report.stopped_reason)
            if control_key == "image_generate_button" and self._navigator is not None:
                state = self._navigator.last_starter_settings
                if state:
                    self.report.detected_aspect_ratio = state.detected_aspect_ratio
                    self.report.detected_image_count = state.detected_image_count
                    self.report.detected_image_quality = state.detected_image_quality
                    self.report.settings_verified = True
            self._complete_auto_gate(
                session,
                engine,
                control_key=control_key,
                step_id=step_id,
                label=label,
                event=event,
                validation_reason=validation.reason or "auto_validated",
            )
            return

        if control_key == "image_generate_button" and self._navigator is not None:
            state = self._navigator.last_starter_settings
            if not state or not state.settings_verified:
                self.report.stopped_reason = "starter image settings not verified before Generate approval"
                raise RuntimeError(self.report.stopped_reason)
            self.report.detected_aspect_ratio = state.detected_aspect_ratio
            self.report.detected_image_count = state.detected_image_count
            self.report.detected_image_quality = state.detected_image_quality
            self.report.settings_verified = True

        clip_index = self._clip_index_from_step_id(step_id)
        if control_key == "download_mp4_button":
            if clip_index <= 0:
                clip_index = max(1, self.report.clips_completed or 1)
            self._wait_for_download_gate_enabled(
                control_key=control_key,
                step_id=step_id,
                clip_index=clip_index,
            )
        elif control_key == "generate_button" and self._navigator is not None:
            if self._approval_runtime is not None:
                self._approval_runtime.set_gate_readiness(
                    ready=False,
                    enabled=False,
                    reason="checking_video_generate_readiness",
                    step_id=step_id,
                    control_key=control_key,
                )
        else:
            self._sync_non_download_gate_readiness(control_key, step_id)

        stop_event = threading.Event()
        generate_poller: threading.Thread | None = None
        if control_key == "generate_button" and self._navigator is not None:
            generate_index = clip_index if clip_index > 0 else max(1, self.report.clips_completed or 1)
            generate_poller = threading.Thread(
                target=self._poll_generate_gate_readiness,
                kwargs={
                    "control_key": control_key,
                    "step_id": step_id,
                    "clip_index": generate_index,
                    "stop_event": stop_event,
                },
                daemon=True,
            )
            generate_poller.start()

        try:
            granted = self.approval_callback(control_key, step_id, label)
        finally:
            if generate_poller is not None:
                stop_event.set()
                generate_poller.join(timeout=2.0)
        event.granted = granted
        event.operator = self.operator
        event.timestamp = _now()
        if not granted:
            self.report.stopped_reason = f"approval missing for {control_key}"
            raise RuntimeError(self.report.stopped_reason)

        engine.approve(
            session,
            control_key=control_key,
            step_id=step_id,
            approved_by=self.operator,
            reason="live_smoke_h",
        )
        self.report.approvals_granted.append(
            ApprovalEvent(
                control_key=control_key,
                step_id=step_id,
                label=label,
                granted=True,
                operator=self.operator,
                timestamp=_now(),
                reason="live_smoke_h",
            )
        )
        before_index = session.current_step_index
        engine.advance(session)
        if session.status == SEMI_AUTO_STATUS_FAILED:
            step = session.steps[session.current_step_index]
            result = session.step_results[session.current_step_index]
            raise RuntimeError(
                f"step failed at {step.step_id}: {result.error or result.notes or 'unknown'}"
            )
        self._update_progress_markers(session, before_index)

    def _handle_manual_hold(
        self,
        session: RunwaySemiAutoSession,
        engine: RunwayContinuitySemiAutoEngine,
    ) -> None:
        step = session.steps[session.current_step_index]
        if (
            self._auto_controller is not None
            and self._auto_controller.should_auto_image_ready()
        ):
            validation = self._auto_controller.wait_for_image_ready_auto(step_id=step.step_id)
            self._auto_controller.record(
                step_id=step.step_id,
                action="auto_image_ready",
                reason=validation.reason or "validated",
                validation=validation,
                runtime_state=str(session.status),
            )
            self._sync_execution_timeline(
                session,
                last_action="auto_image_ready",
                next_action="use_starter_image_for_video",
                validation_state=validation.reason or ("ok" if validation.ok else "failed"),
            )
            hold_record = {
                "step_id": step.step_id,
                "action": step.action,
                "result": "ready" if validation.ok else "failed",
            }
            self.report.manual_holds.append(hold_record)
            if not validation.ok:
                self.report.stopped_reason = f"auto image ready failed: {validation.reason}"
                raise RuntimeError(self.report.stopped_reason)
            self.report.image_generation_result = "auto_detected_ready"
            before_index = session.current_step_index
            engine.acknowledge_manual_hold(session)
            engine.advance(session)
            if session.status == SEMI_AUTO_STATUS_FAILED:
                failed = session.steps[session.current_step_index]
                result = session.step_results[session.current_step_index]
                raise RuntimeError(
                    f"step failed at {failed.step_id}: {result.error or result.notes or 'unknown'}"
                )
            self._update_progress_markers(session, before_index)
            return

        ack = self.manual_ack_callback(step.step_id, step.action)
        hold_record = {
            "step_id": step.step_id,
            "action": step.action,
            "result": "ready" if ack else "cancelled",
        }
        self.report.manual_holds.append(hold_record)
        if not ack:
            self.report.stopped_reason = f"manual hold not acknowledged: {step.step_id}"
            raise RuntimeError(self.report.stopped_reason)
        if "wait_for_image_ready" in step.step_id:
            self.report.image_generation_result = "operator_confirmed_ready"
        before_index = session.current_step_index
        engine.acknowledge_manual_hold(session)
        engine.advance(session)
        if session.status == SEMI_AUTO_STATUS_FAILED:
            step = session.steps[session.current_step_index]
            result = session.step_results[session.current_step_index]
            raise RuntimeError(
                f"step failed at {step.step_id}: {result.error or result.notes or 'unknown'}"
            )
        self._update_progress_markers(session, before_index)

    def _verify_page_state_before_advance(self, session: RunwaySemiAutoSession) -> None:
        if self.simulate or self._page is None or self._navigator is None:
            return
        step = session.steps[session.current_step_index]
        step_key = step.step_id.split("_", 1)[-1]
        if step_key in {
            "image_generation_open",
            "wait_for_image_ready_manual",
            "preclean_starter_image_workspace",
            "use_starter_image_for_video",
        }:
            return
        if step.requires_operator_approval:
            return

        control_key = step.control_key
        if not control_key:
            return
        ctrl = self._navigator.snapshot.controls.get(str(control_key))
        if ctrl is None or not ctrl.valid or ctrl.weak_selector:
            return
        if not self._navigator.is_control_visible(str(control_key)):
            self._capture_screenshot(f"missing_control_{control_key}")
            raise RuntimeError(
                f"selector not visible before step {step.step_id}: {control_key}"
            )

    def _update_progress_markers(self, session: RunwaySemiAutoSession, before_index: int) -> None:
        if session.current_step_index <= before_index:
            return
        for index in range(before_index, session.current_step_index):
            step = session.steps[index]
            result = session.step_results[index]
            if result.status != "done":
                continue
            step_key = step.step_id.split("_", 1)[-1]
            if step_key == "image_generate_manual_required":
                self.report.image_generation_result = "generate_clicked_with_approval"
            if step_key.startswith("video_generate_manual_required"):
                self.report.video_generation_started = True
                self.report.video_generates_approved_count += 1
            if step_key.startswith("wait_until_completion_signal"):
                self.report.video_generation_started = True
                self.report.video_completion_detected = True
                try:
                    clip_num = int(step_key.rsplit("_", 1)[-1])
                    self.report.clips_completed = max(self.report.clips_completed, clip_num)
                    self._apply_strict_completion_report(clip_num)
                except ValueError:
                    pass
                if session.completion_signals:
                    self.report.completion_signals = list(session.completion_signals)
            if step_key.startswith("use_frame_for_clip_"):
                try:
                    clip_num = int(step_key.rsplit("_", 1)[-1])
                    after_clip = clip_num - 1
                    if after_clip not in self.report.use_frame_after_clips:
                        self.report.use_frame_after_clips.append(after_clip)
                    self._apply_last_frame_use_frame_report(clip_num)
                except ValueError:
                    pass
            if step_key.startswith("verify_use_frame_handoff_clip_") and self._navigator is not None:
                try:
                    clip_num = int(step_key.rsplit("_", 1)[-1])
                except ValueError:
                    clip_num = 0
                handoff = self._navigator.last_use_frame_handoff_by_clip.get(clip_num)
                if clip_num == 2:
                    self.report.clip_2_use_frame_handoff_checked = True
                    if handoff is not None:
                        self.report.clip_2_use_frame_handoff_result = handoff.handoff_result
                        self.report.clip_2_reference_thumbnail_detected = (
                            handoff.reference_thumbnail_detected
                        )
                        self.report.clip_2_prompt_interactable_after_use_frame = (
                            handoff.prompt_interactable
                        )
                elif clip_num == 3:
                    self.report.clip_3_use_frame_handoff_checked = True
                    if handoff is not None:
                        self.report.clip_3_use_frame_handoff_result = handoff.handoff_result
                        self.report.clip_3_reference_thumbnail_detected = (
                            handoff.reference_thumbnail_detected
                        )
                        self.report.clip_3_prompt_interactable_after_use_frame = (
                            handoff.prompt_interactable
                        )
            if step_key.startswith("download_mp4") or step_key.startswith("final_download"):
                self.report.download_attempted = True
                self.report.downloads_approved_count += 1
                clip_index = _clip_index_from_download_step(step_key)
                if clip_index > 0 and self._navigator is not None:
                    attempt = self._navigator.last_clip_download_attempts.get(clip_index)
                    if attempt is not None:
                        self._apply_download_attempt(attempt)
                    elif self._download_tracker is not None:
                        record = self._download_tracker.verify_clip_download(clip_index)
                        self._apply_download_record(record)
                if self._navigator is not None:
                    self.report.artifact_card_assignments = (
                        self._navigator.phase_i_artifact_tracker().to_report_summary().get(
                            "assignments",
                            {},
                        )
                    )
                if self.download_confirm_callback is not None:
                    self.report.download_confirmed = bool(self.download_confirm_callback())
                else:
                    self.report.download_confirmed = self.report.total_downloads_completed > 0
            if step_key == "verify_starter_image_settings" and self._navigator is not None:
                state = self._navigator.last_starter_settings
                if state is not None:
                    self.report.detected_aspect_ratio = state.detected_aspect_ratio
                    self.report.detected_image_count = state.detected_image_count
                    self.report.detected_image_quality = state.detected_image_quality
                    self.report.settings_verified = state.settings_verified
            if step_key == "clear_image_prompt_after_generation" and self._navigator is not None:
                clear_result = self._navigator.last_prompt_clear
                if clear_result is not None:
                    self.report.image_prompt_cleared = clear_result.image_prompt_cleared
                    self.report.prompt_text_before_clear = clear_result.prompt_text_before_clear
                    self.report.prompt_text_after_clear = clear_result.prompt_text_after_clear
            if step_key == "preclean_starter_image_workspace" and self._navigator is not None:
                preclean = self._navigator.last_preclean
                if preclean is not None:
                    self.report.preclean_attempted = preclean.preclean_attempted
                    self.report.stale_image_preview_detected = preclean.stale_image_preview_detected
                    self.report.stale_preview_closed = preclean.stale_preview_closed
                    self.report.preclean_notes = list(preclean.preclean_notes)
            if step_key in {"use_starter_image_for_video", "image_use_to_video"} and self._navigator is not None:
                latest = self._navigator.last_latest_image_card
                if latest is not None:
                    self.report.latest_image_card_found = latest.latest_image_card_found
                    self.report.latest_image_card_index = latest.latest_image_card_index
                    self.report.selected_image_card_fingerprint = latest.selected_image_card_fingerprint
                    self.report.selected_image_card_index = latest.latest_image_card_index
                    self.report.card_prompt_text = latest.card_prompt_text
                    self.report.card_bounding_box = dict(latest.card_bounding_box)
                    self.report.video_transition_verified = latest.video_transition_verified
                    self.report.current_url_after_transition = latest.current_url_after_transition
            if step_key == "use_starter_image_for_video" and self._navigator is not None:
                latest = self._navigator.last_latest_image_card
                if latest is not None and latest.use_for_video_action_used:
                    self.report.continuity_notes.append(
                        f"use_for_video_action={latest.use_for_video_action_used}"
                    )
            if step_key == "cleanup_used_image_card_after_use_to_video" and self._navigator is not None:
                latest = self._navigator.last_latest_image_card
                if latest is not None:
                    self.report.selected_image_card_fingerprint = latest.selected_image_card_fingerprint
                    self.report.selected_image_card_index = latest.latest_image_card_index
                    self.report.used_image_card_removed = latest.used_image_card_removed
                    self.report.used_image_card_marked_consumed = latest.used_image_card_marked_consumed
            if step_key.startswith("select_duration_10s") and self._navigator is not None:
                video_state = self._navigator.last_video_settings
                if video_state is not None:
                    self.report.detected_video_aspect_ratio = video_state.detected_aspect_ratio
                    self.report.detected_video_duration = video_state.detected_duration
                    self.report.video_settings_verified = video_state.video_settings_verified
            if step_key.startswith("select_video_aspect") and self._navigator is not None:
                aspect = self._navigator.read_menu_display_value("aspect_ratio_menu")
                if aspect:
                    self.report.detected_video_aspect_ratio = aspect
            if step_key.startswith("remove_image"):
                self.report.remove_image_executed = True
            if step_key.startswith("video_prompt_clip_") and self._navigator is not None:
                try:
                    clip_num = int(step_key.rsplit("_", 1)[-1])
                except ValueError:
                    clip_num = 0
                ready = self._navigator.last_prompt_ready_by_clip.get(clip_num)
                result_label = "unknown"
                if ready is not None:
                    if ready.ready_result:
                        result_label = ready.ready_result
                    elif ready.ready:
                        result_label = "ready"
                    else:
                        result_label = "not_ready_fatal"
                    if (
                        ready.ready_result == "skipped_because_generation_started"
                        or ready.generation_in_progress
                    ):
                        if clip_num == 2:
                            self.report.clip_2_generation_detected_after_prompt_timeout = True
                        elif clip_num == 3:
                            self.report.clip_3_generation_detected_after_prompt_timeout = True
                if clip_num == 2:
                    self.report.clip_2_prompt_ready_checked = True
                    self.report.clip_2_prompt_ready_result = result_label
                elif clip_num == 3:
                    self.report.clip_3_prompt_ready_checked = True
                    self.report.clip_3_prompt_ready_result = result_label

    def _apply_download_attempt(self, attempt: Any) -> None:
        index = int(getattr(attempt, "clip_index", 0) or 0)
        downloaded = bool(getattr(attempt, "downloaded", False))
        path = str(getattr(attempt, "file_path", "") or "")
        strategy = str(getattr(attempt, "strategy", "") or "")
        scoped = bool(getattr(attempt, "scoped_to_card", False))
        if index == 1:
            self.report.clip_1_downloaded = downloaded
            self.report.clip_1_download_strategy = strategy
            self.report.clip_1_download_scoped_to_card = scoped
        elif index == 2:
            self.report.clip_2_downloaded = downloaded
            self.report.clip_2_download_strategy = strategy
            self.report.clip_2_download_scoped_to_card = scoped
        elif index == 3:
            self.report.clip_3_downloaded = downloaded
            self.report.clip_3_download_strategy = strategy
            self.report.clip_3_download_scoped_to_card = scoped
        if downloaded and path and path not in self.report.downloaded_file_paths:
            self.report.downloaded_file_paths.append(path)
        self.report.total_downloads_completed = len(
            [
                item
                for item in (
                    self.report.clip_1_downloaded,
                    self.report.clip_2_downloaded,
                    self.report.clip_3_downloaded,
                )
                if item
            ]
        )

    def _apply_download_record(self, record: Any) -> None:
        index = int(getattr(record, "clip_index", 0) or 0)
        downloaded = bool(getattr(record, "downloaded", False))
        path = str(getattr(record, "file_path", "") or "")
        if index == 1:
            self.report.clip_1_downloaded = downloaded
        elif index == 2:
            self.report.clip_2_downloaded = downloaded
        elif index == 3:
            self.report.clip_3_downloaded = downloaded
        if downloaded and path and path not in self.report.downloaded_file_paths:
            self.report.downloaded_file_paths.append(path)
        if self._download_tracker is not None:
            fields = self._download_tracker.report_fields(self.clip_count)
            self.report.total_downloads_completed = int(fields.get("total_downloads_completed") or 0)
            self.report.download_records = list(fields.get("download_records") or [])
            for key in ("clip_1_downloaded", "clip_2_downloaded", "clip_3_downloaded"):
                if key in fields:
                    setattr(self.report, key, bool(fields[key]))
            self.report.downloaded_file_paths = list(fields.get("downloaded_file_paths") or [])
        if downloaded and int(getattr(record, "file_size_bytes", 0) or 0) <= 0:
            self.report.warnings.append(f"clip {index} download path recorded but file size is zero")

    def _capture_screenshot(self, label: str) -> str:
        if self.simulate or self._page is None:
            return ""
        screenshot_fn = getattr(self._page, "screenshot", None)
        if screenshot_fn is None:
            return ""
        path = self.artifact_dir / f"{_slug(self.project_id)}_{_slug(label)}_{int(time.time())}.png"
        try:
            screenshot_fn(path=str(path), full_page=True)
            self.report.screenshots.append(str(path))
            return str(path)
        except Exception as exc:
            self.report.warnings.append(f"screenshot failed ({label}): {exc}")
            return ""

    def _persist_report(self) -> None:
        try:
            record_latest_run_attempt(ROOT, self.report.to_dict())
        except Exception:
            pass
        if self.clip_count > 1:
            json_path = DEFAULT_PHASE_I_REPORT_JSON
            md_path = DEFAULT_PHASE_I_REPORT_MD
            md_text = render_phase_i_3clip_report_md(self.report)
        else:
            json_path = DEFAULT_REPORT_JSON
            md_path = DEFAULT_REPORT_MD
            md_text = render_live_smoke_report_md(self.report)
        json_path.write_text(
            json.dumps(self.report.to_dict(), indent=2),
            encoding="utf-8",
        )
        md_path.write_text(md_text, encoding="utf-8")


def render_phase_i_3clip_report_md(report: RunwayLiveSmokeReport) -> str:
    """Phase I — 3-clip live continuity report."""
    base = render_live_smoke_report_md(report)
    extra = [
        "",
        "## Phase I — 3-Clip Continuity",
        "",
        "| Check | Value |",
        "|-------|-------|",
        f"| clip_count | {report.clip_count} |",
        f"| clips_completed | {report.clips_completed} |",
        f"| video_generates_approved | {report.video_generates_approved_count} |",
        f"| downloads_approved | {report.downloads_approved_count} |",
        f"| use_frame_after_clips | {report.use_frame_after_clips or '(none)'} |",
        f"| remove_image_executed | {'Yes' if report.remove_image_executed else 'No'} |",
        f"| story_brief_present | {'Yes' if report.story_brief_present else 'No'} |",
        f"| story_brief_title | {report.story_brief_title[:80] or '(none)'} |",
        f"| story_brief_character | {report.story_brief_character or '(none)'} |",
        f"| starter_prompt_chars | {report.starter_prompt_chars} |",
        f"| approvals_granted | {len(report.approvals_granted)} |",
        "",
        "### Story brief traceability",
        "",
        f"- logline: {report.story_brief_logline[:200] or '(none)'}",
        f"- setting: {report.story_brief_setting or '(none)'}",
        "",
        "### Continuity notes",
        "",
    ]
    if report.continuity_notes:
        for note in report.continuity_notes:
            extra.append(f"- {note}")
    else:
        extra.append("_None recorded._")
    extra.extend(
        [
        "",
        "### Expected approvals (live)",
        "",
        "- 1 × `image_generate_button`",
        "- 3 × `generate_button` (one per clip)",
        "- 3 × `download_mp4_button` (one per clip)",
        "",
        "### Continuity chain",
        "",
        "1. Starter image → Use to Video → clip 1",
        "2. After clip 1 download → `use_frame_button` → clip 2",
        "3. After clip 2 download → `use_frame_button` → clip 3",
        "4. After clip 3 download → `remove_image` (no use_frame on final clip)",
        "",
        ]
    )
    marker = "## Operator Approvals"
    if marker in base:
        return base.replace(marker, "\n".join(extra) + marker, 1)
    return base + "\n".join(extra)


def run_live_smoke_test(
    story_idea: str,
    *,
    project_id: str = "live_smoke_h",
    operator: str = "operator",
    simulate: bool = False,
    clip_count: int = SMOKE_CLIP_COUNT,
    **kwargs: Any,
) -> RunwayLiveSmokeReport:
    runner = RunwayLiveSmokeRunner(
        story_idea=story_idea,
        project_id=project_id,
        operator=operator,
        simulate=simulate,
        clip_count=clip_count,
        **kwargs,
    )
    return runner.run()


__all__ = [
    "DEFAULT_PHASE_I_REPORT_JSON",
    "DEFAULT_PHASE_I_REPORT_MD",
    "DEFAULT_REPORT_MD",
    "DEFAULT_REPORT_JSON",
    "LIVE_SMOKE_VERSION",
    "MAX_COMPLETION_WAIT_MINUTES",
    "PHASE_I_CLIP_COUNT",
    "PHASE_I_VERSION",
    "RunwayLiveSmokeReport",
    "RunwayLiveSmokeRunner",
    "SMOKE_CLIP_COUNT",
    "expected_approval_gate_count",
    "render_phase_i_3clip_report_md",
    "browser_probe_is_ok",
    "browser_probe_message",
    "browser_probe_to_dict",
    "default_interactive_approval",
    "default_interactive_manual_ack",
    "render_live_smoke_report_md",
    "run_live_smoke_test",
]
