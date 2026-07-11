"""
Phase 11X — end-to-end topic → voice slot dry run (no paid TTS).

Run: python -m project_brain.run_11x_end_to_end_topic_to_voice_dry_run
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from content_brain.execution.approval_budget_governance_engine import (
    ApprovalBudgetGovernanceEngine,
    GovernancePolicy,
)
from content_brain.execution.execution_queue_engine import ExecutionQueueEngine
from content_brain.execution.execution_readiness_gate import ExecutionReadinessGate
from content_brain.execution.provider_categories import CATEGORY_VIDEO, CATEGORY_VOICE
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine, RuntimePolicy
from content_brain.execution.session_narration_adapter import (
    SessionNarrationAdapter,
    _parse_narration_from_description,
)
from content_brain.execution.session_population_builder import SessionPopulationBuilder
from content_brain.execution.session_store import ExecutionSessionStore
from content_brain.execution.simulation_report_builder import SimulationReportBuilder
from content_brain.execution.voice_approval_guard import can_run_live_voice_tts
from content_brain.execution.voice_live_tts_action_policy import (
    PROVIDER_MODE_LIVE,
    evaluate_voice_live_tts_run,
    evaluate_voice_run_mode_request,
)
from content_brain.orchestrators.content_brief_orchestrator import (
    ContentBriefOrchestrator,
    ContentBriefRunRequest,
)
from content_brain.schemas.content_brief import Platform
from ui.api.voice_run_service import VoiceRunService
from core.env_bootstrap import bootstrap_project_env

TOPIC = "cat in the streets of Los Angeles"
NICHE = "general"
REPORT_PATH = Path(__file__).resolve().parent / "PHASE_11X_END_TO_END_TOPIC_TO_VOICE_DRY_RUN_REPORT.md"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pipeline_session(session: dict[str, Any]) -> dict[str, Any]:
    session = SimulationReportBuilder().enrich_session(session)
    session = ApprovalBudgetGovernanceEngine().enrich_session(session, policy=GovernancePolicy())
    return ExecutionReadinessGate().enrich_session(session)


def _extract_beats(brief_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    run_context = _dict(brief_snapshot.get("run_context"))
    story_intel = _dict(run_context.get("story_intelligence"))
    arch = _dict(story_intel.get("story_architecture"))
    beats = arch.get("beat_plans") or []
    if beats:
        return [dict(b) for b in beats if isinstance(b, dict)]

    blueprint = _dict(brief_snapshot.get("story_blueprint"))
    raw_beats = blueprint.get("beats") or []
    normalized: list[dict[str, Any]] = []
    for beat in raw_beats:
        if not isinstance(beat, dict):
            continue
        row = dict(beat)
        narration = str(row.get("narration") or "").strip()
        if not narration:
            narration = _parse_narration_from_description(str(row.get("description") or ""))
        row["narration"] = narration
        normalized.append(row)
    return normalized


def _beat_narration_summary(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for beat in beats:
        narration = str(beat.get("narration") or "").strip()
        rows.append(
            {
                "beat_id": beat.get("beat_id"),
                "narration_preview": narration[:120] + ("..." if len(narration) > 120 else ""),
                "narration_length": len(narration),
                "has_narration": bool(narration),
            }
        )
    return rows


def run_dry_run(project_root: str | Path = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with tempfile.TemporaryDirectory() as tmp:
        memory_path = Path(tmp) / "content_history_11x.json"
        orchestrator = ContentBriefOrchestrator(project_root=root, memory_path=memory_path)
        brief_result = orchestrator.run(
            ContentBriefRunRequest(
                niche=NICHE,
                topic=TOPIC,
                platform=Platform.TIKTOK,
                user_duration_seconds=30,
                provider_name="hailuo",
                record_uniqueness_on_success=False,
                record_story_memory_on_success=False,
            )
        )

    run_context = dict(brief_result.run_context or {})
    trend_signal = brief_result.trend_signal
    brief_snapshot = brief_result.to_dict()
    beats = _extract_beats(brief_snapshot)
    beat_summary = _beat_narration_summary(beats)
    beats_with_narration = sum(1 for row in beat_summary if row["has_narration"])

    session = SessionPopulationBuilder().build(brief_result)
    exec_id = session["execution_session_id"]

    if session.get("execution_confidence_score") is None:
        session["execution_confidence_score"] = 78.0
    if session.get("provider_selection"):
        session["provider_selection"]["expected_retry_risk"] = "low"

    session = _pipeline_session(session)
    store = ExecutionSessionStore(root)
    store.save_session(session, overwrite=True)

    queue = ExecutionQueueEngine(store)
    enqueue_result = queue.enqueue_by_id(exec_id, actor="phase_11x")
    if not enqueue_result.success:
        raise RuntimeError(f"Enqueue failed: {enqueue_result.reject_reasons}")
    dequeue_result = queue.dequeue_by_id(exec_id, actor="phase_11x")
    if not dequeue_result.success:
        raise RuntimeError(f"Dequeue failed: {dequeue_result.reject_reasons}")

    runtime_engine = ProviderRuntimeEngine(store)
    dispatch_policy = RuntimePolicy(skip_provider_execution=True)
    dispatch_result = runtime_engine.dispatch_by_id(
        exec_id,
        actor="phase_11x",
        policy=dispatch_policy,
    )

    session_after = store.load_session(exec_id)
    runtime = _dict(session_after.get("execution_runtime"))
    category_runtime = _dict(runtime.get("category_runtime"))
    voice_slot = dict(_dict(category_runtime.get(CATEGORY_VOICE)))
    video_slot = dict(_dict(category_runtime.get(CATEGORY_VIDEO)))

    narration_bundle = SessionNarrationAdapter().build(session_after)
    narration_segments = [
        {
            "segment_index": seg.segment_index,
            "beat_id": seg.beat_id,
            "text_preview": seg.text[:100] + ("..." if len(seg.text) > 100 else ""),
            "character_count": len(seg.text),
        }
        for seg in narration_bundle.segments
    ]
    schema_shots = _dict(
        _dict(brief_snapshot.get("run_context")).get("story_intelligence")
    ).get("schema_director_shots") or []
    guard = can_run_live_voice_tts(voice_slot, session_after, project_root=root)
    live_mode_block = evaluate_voice_run_mode_request(PROVIDER_MODE_LIVE, confirm_live_tts=True)
    live_run_block = evaluate_voice_live_tts_run(
        session_after,
        voice_slot,
        provider_mode=PROVIDER_MODE_LIVE,
        confirm_live_tts=True,
        project_root=str(root),
    )
    voice_service_block = VoiceRunService(store).run(
        exec_id,
        provider_mode=PROVIDER_MODE_LIVE,
        confirm_live_tts=True,
    )

    has_elevenlabs_key = bool(os.getenv("ELEVENLABS_API_KEY", "").strip())
    preflight = _dict(voice_slot.get("voice_preflight"))
    approval = _dict(voice_slot.get("approval"))
    ops_preflight = _dict(runtime.get("operations")).get("voice_preflight_dry_run")

    video_before = dict(_dict(session.get("execution_runtime")).get("category_runtime", {}).get(CATEGORY_VIDEO, {}))

    return {
        "timestamp": timestamp,
        "topic": TOPIC,
        "niche": NICHE,
        "session_id": exec_id,
        "brief_id": brief_result.brief_id,
        "user_topic_authoritative": bool(run_context.get("user_topic_authoritative")),
        "user_topic_in_run_context": run_context.get("user_topic"),
        "pipeline_topic": run_context.get("topic"),
        "trend_signal_topic": trend_signal.topic,
        "trend_signal_source": trend_signal.source,
        "production_ready": brief_result.production_ready,
        "decision": brief_result.decision_package.decision.value,
        "clip_count": brief_result.video_format_plan.clip_count,
        "beats": beat_summary,
        "beats_total": len(beat_summary),
        "beats_with_narration": beats_with_narration,
        "narration_segment_count": narration_bundle.segment_count,
        "narration_total_chars": narration_bundle.total_text_length,
        "narration_source_path": narration_bundle.source_path,
        "narration_segments": narration_segments,
        "schema_director_shot_count": len(schema_shots) if isinstance(schema_shots, list) else 0,
        "governance_state": session_after.get("state"),
        "readiness_decision": _dict(session_after.get("execution_readiness")).get("decision"),
        "dispatch_success": dispatch_result.success,
        "dispatch_reject_code": dispatch_result.reject_code,
        "dispatch_runtime_state": runtime.get("state"),
        "video_slot": {
            "status": video_slot.get("status"),
            "state": video_slot.get("state"),
            "provider": video_slot.get("provider"),
            "executed": video_slot.get("executed"),
        },
        "video_artifacts": len(_dict(runtime.get("artifacts_by_category")).get(CATEGORY_VIDEO) or []),
        "voice_slot": {
            "status": voice_slot.get("status"),
            "state": voice_slot.get("state"),
            "provider": voice_slot.get("provider"),
            "executed": voice_slot.get("executed"),
            "dry_run": voice_slot.get("dry_run"),
            "live_tts": voice_slot.get("live_tts"),
            "segment_count": voice_slot.get("segment_count"),
            "preflight_ready": preflight.get("ready"),
            "preflight_code": preflight.get("code"),
        },
        "approval_gate": {
            "approval_state": approval.get("approval_state"),
            "approval_required": approval.get("approval_required"),
            "live_tts_eligible": approval.get("live_tts_eligible"),
            "live_tts_blocked_reasons": approval.get("live_tts_blocked_reasons"),
            "estimated_segment_count": approval.get("estimated_segment_count"),
            "estimated_character_count": approval.get("estimated_character_count"),
        },
        "guard_result": guard.to_dict(),
        "live_tts_blocked": {
            "mode_request": live_mode_block.to_dict(),
            "run_policy": live_run_block.to_dict(),
            "voice_service": {
                "success": voice_service_block.get("success"),
                "code": voice_service_block.get("code"),
            },
        },
        "elevenlabs_key_present": has_elevenlabs_key,
        "preflight_ops_mirror": ops_preflight,
        "no_real_tts": voice_slot.get("live_tts_executed") is not True,
        "skip_provider_execution": True,
        "video_slot_preserved_fields": all(
            video_slot.get(k) == video_before.get(k)
            for k in ("state", "provider", "started_at", "completed_at")
            if video_before.get(k) is not None
        )
        or not video_before,
    }


def write_report(data: dict[str, Any]) -> Path:
    lines = [
        "# Phase 11X — End-to-End Topic → Voice Slot Dry Run Report",
        "",
        f"**Date:** {data['timestamp']}",
        f"**Status:** {'PASS' if data['dispatch_success'] and data['narration_segment_count'] > 0 else 'PARTIAL'}",
        "",
        "## Test Topic",
        "",
        f"`{data['topic']}`",
        "",
        "## Session",
        "",
        f"- **Session ID:** `{data['session_id']}`",
        f"- **Brief ID:** `{data['brief_id']}`",
        f"- **Niche:** `{data['niche']}`",
        "",
        "## User Topic Authority",
        "",
        f"- **user_topic_authoritative:** `{data['user_topic_authoritative']}`",
        f"- **user_topic (run_context):** `{data['user_topic_in_run_context']}`",
        f"- **pipeline topic:** `{data['pipeline_topic']}`",
        f"- **trend signal topic:** `{data['trend_signal_topic']}`",
        f"- **trend signal source:** `{data['trend_signal_source']}`",
        "",
        "User topic was preserved as authoritative (no trend override)." if data["user_topic_authoritative"] and data["pipeline_topic"] == TOPIC else "User topic authority check failed.",
        "",
        "## Content Brief",
        "",
        f"- **Decision:** {data['decision']}",
        f"- **Production ready:** {data['production_ready']}",
        f"- **Clip count:** {data['clip_count']}",
        "",
        "## Story Beats / Narration",
        "",
        f"- **Beat count:** {data['beats_total']}",
        f"- **Beats with narration:** {data['beats_with_narration']}",
        f"- **Narration segment count (adapter):** {data['narration_segment_count']}",
        f"- **Narration source:** `{data['narration_source_path']}`",
        f"- **Schema director shots:** {data['schema_director_shot_count']}",
        "",
        "### Narration segments (adapter)",
        "",
        "```json",
        json.dumps(data["narration_segments"], indent=2, ensure_ascii=False),
        "```",
        "",
        "### Beat summary",
        "",
        "```json",
        json.dumps(data["beats"], indent=2, ensure_ascii=False),
        "```",
        "",
        f"- **Total narration characters:** {data['narration_total_chars']}",
        "",
        "## Governance & Dispatch",
        "",
        f"- **Governance state:** `{data['governance_state']}`",
        f"- **Readiness:** `{data['readiness_decision']}`",
        f"- **Video dispatch success:** `{data['dispatch_success']}`",
        f"- **Dispatch reject code:** `{data['dispatch_reject_code']}`",
        f"- **Runtime state:** `{data['dispatch_runtime_state']}`",
        f"- **skip_provider_execution:** `{data['skip_provider_execution']}` (no Runway/Hailuo paid execution)",
        "",
        "## Video Runtime",
        "",
        "```json",
        json.dumps(data["video_slot"], indent=2, ensure_ascii=False),
        "```",
        "",
        f"- **Video artifacts (dry-run):** {data['video_artifacts']}",
        "",
        "## Voice Generation Slot",
        "",
        "```json",
        json.dumps(data["voice_slot"], indent=2, ensure_ascii=False),
        "```",
        "",
        f"- **ElevenLabs API key present:** `{data['elevenlabs_key_present']}`",
        f"- **Preflight ready (if key exists):** `{data['voice_slot'].get('preflight_ready')}`",
        "",
        "## Voice Approval Gate",
        "",
        "```json",
        json.dumps(data["approval_gate"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Live TTS Blocked (Expected)",
        "",
        "```json",
        json.dumps(data["live_tts_blocked"], indent=2, ensure_ascii=False),
        "```",
        "",
        f"- **Guard allowed:** `{data['guard_result'].get('allowed')}`",
        "",
        "## Safety Confirmations",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| No real ElevenLabs TTS executed | `{data['no_real_tts']}` |",
        f"| No paid video provider execution | `{data['skip_provider_execution']}` |",
        f"| Live mode blocked at service layer | `{not data['live_tts_blocked']['voice_service'].get('success')}` |",
        f"| Video slot critical fields preserved | `{data['video_slot_preserved_fields']}` |",
        "",
        "## Preflight Operations Mirror",
        "",
        "```json",
        json.dumps(data.get("preflight_ops_mirror"), indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


def main() -> int:
    env_summary = bootstrap_project_env()
    root = Path(env_summary["project_root"])
    data = run_dry_run(root)
    path = write_report(data)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nReport written: {path}")
    ok = (
        data["user_topic_authoritative"]
        and data["narration_segment_count"] > 0
        and data["beats_with_narration"] > 0
        and data["voice_slot"].get("provider") == "elevenlabs"
        and data["no_real_tts"]
        and not data["live_tts_blocked"]["voice_service"].get("success")
    )
    print(f"\n{'PASS' if ok else 'PARTIAL'} — Phase 11X dry run")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
