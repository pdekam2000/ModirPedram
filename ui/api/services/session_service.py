"""Thin API service over ExecutionSessionStore — no UI, no provider logic."""

from __future__ import annotations

from typing import Any, Literal

from content_brain.execution.session_store import ExecutionSessionStore
from ui.api.services.panel_extractor import PanelExtractor, overview_timestamp

ArchiveFilter = Literal["active", "archived", "all"]


def parse_archived_query(value: str | None) -> ArchiveFilter:
    if value is None or value.strip() == "":
        return "all"
    normalized = value.strip().lower()
    if normalized in {"false", "0", "active"}:
        return "active"
    if normalized in {"true", "1", "archived"}:
        return "archived"
    if normalized == "all":
        return "all"
    raise ValueError(
        "Invalid archived filter. Use archived=false, archived=true, or archived=all."
    )


class SessionService:
    def __init__(self, store: ExecutionSessionStore):
        self._store = store
        self._panels = PanelExtractor()

    def list_sessions(self, *, archived: ArchiveFilter = "all") -> list[dict[str, Any]]:
        summaries = self._store.list_summaries()
        public = [self._public_summary(item) for item in summaries]
        return self._filter_by_archive(public, archived)

    def get_overview(self) -> dict[str, Any]:
        sessions = [self._public_summary(item) for item in self._store.list_summaries()]
        active_sessions = [item for item in sessions if not item.get("archived")]
        archived_sessions = [item for item in sessions if item.get("archived")]

        scores = [
            item["story_quality_score"]
            for item in active_sessions
            if item.get("story_quality_score") is not None
        ]
        confidences = [
            item["execution_confidence"]
            for item in active_sessions
            if item.get("execution_confidence") is not None
        ]

        approved_states = {"approve", "approved"}
        blocked_states = {"blocked"}

        return {
            "total_sessions": len(sessions),
            "active_sessions_count": len(active_sessions),
            "archived_sessions_count": len(archived_sessions),
            "simulated_count": sum(
                1
                for item in active_sessions
                if str(item.get("status", "")).upper() == "SIMULATED"
            ),
            "approved_count": sum(
                1
                for item in active_sessions
                if str(item.get("approval_state", "")).lower() in approved_states
                or str(item.get("status", "")).upper()
                in {"APPROVED_FOR_EXECUTION", "GOVERNED", "READY", "READY_WITH_WARNINGS"}
            ),
            "blocked_count": sum(
                1
                for item in active_sessions
                if str(item.get("budget_state", "")).lower() in blocked_states
                or str(item.get("status", "")).upper() == "BUDGET_BLOCKED"
            ),
            "failed_count": sum(
                1 for item in active_sessions if str(item.get("status", "")).upper() == "FAILED"
            ),
            "cancelled_count": sum(
                1 for item in active_sessions if str(item.get("status", "")).upper() == "CANCELLED"
            ),
            "queued_count": sum(
                1 for item in active_sessions if str(item.get("status", "")).upper() == "QUEUED"
            ),
            "runtime_active_count": sum(
                1
                for item in active_sessions
                if str(item.get("status", "")).upper() in {"DISPATCHED", "RUNNING"}
            ),
            "runtime_completed_count": sum(
                1 for item in active_sessions if str(item.get("status", "")).upper() == "COMPLETED"
            ),
            "avg_story_quality_score": (
                round(sum(scores) / len(scores), 2) if scores else None
            ),
            "avg_execution_confidence": (
                round(sum(confidences) / len(confidences), 2) if confidences else None
            ),
            "generated_at": overview_timestamp(),
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        data = self._store.load_session(session_id)
        summary = self._public_summary(self._store.summarize(data))
        simulation_report = self._store.resolve_simulation_report(data)
        panels = self._panels.extract_all(data)
        panels["simulation_panel"] = self._panels.extract_simulation(data, simulation_report)

        completeness = panels.pop("data_completeness")

        return {
            **summary,
            "session_uuid": data.get("session_uuid"),
            "session_schema_version": data.get("session_schema_version"),
            "source_session_uuid": data.get("source_session_uuid"),
            "execution_readiness": data.get("execution_readiness"),
            "queue_item": data.get("queue_item"),
            "execution_runtime": data.get("execution_runtime"),
            "timeline": self._store.build_timeline_events(data),
            "simulation_report": simulation_report,
            "approval_decision": self._store.resolve_approval_decision(data),
            **panels,
            "data_completeness": completeness,
            "session": data,
        }

    @staticmethod
    def _filter_by_archive(
        sessions: list[dict[str, Any]],
        archived: ArchiveFilter,
    ) -> list[dict[str, Any]]:
        if archived == "all":
            return sessions
        if archived == "active":
            return [item for item in sessions if not item.get("archived")]
        return [item for item in sessions if item.get("archived")]

    @staticmethod
    def _public_summary(summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": summary.get("session_id"),
            "session_uuid": summary.get("session_uuid") or None,
            "session_schema_version": summary.get("session_schema_version") or None,
            "brief_id": summary.get("brief_id"),
            "status": summary.get("status"),
            "provider": summary.get("provider"),
            "story_quality_score": summary.get("story_quality_score"),
            "approval_state": summary.get("approval_state"),
            "budget_state": summary.get("budget_state"),
            "priority_band": summary.get("priority_band"),
            "execution_confidence": summary.get("execution_confidence"),
            "created_at": summary.get("created_at"),
            "archived": bool(summary.get("archived")),
            "archived_at": summary.get("archived_at"),
            "archived_by": summary.get("archived_by"),
            "archive_reason": summary.get("archive_reason"),
        }
