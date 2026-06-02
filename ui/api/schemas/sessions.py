from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ui.api.schemas.panels import (
    ApprovalPanel,
    BudgetPanel,
    DataCompletenessDTO,
    PanelDTO,
    PriorityPanel,
    ProviderSelectionPanel,
    QueuePanel,
    ProviderRuntimePanel,
    SessionOverviewResponse,
    ReadinessPanel,
    SimulationPanel,
    StoryQualityPanel,
)


class SessionSummaryDTO(BaseModel):
    session_id: str
    session_uuid: Optional[str] = None
    session_schema_version: Optional[str] = None
    brief_id: str = ""
    status: str
    provider: str = "—"
    story_quality_score: Optional[float] = None
    approval_state: str = "—"
    budget_state: str = "—"
    priority_band: str = "—"
    execution_confidence: Optional[float] = None
    created_at: str = "—"
    archived: bool = False
    archived_at: Optional[str] = None
    archived_by: Optional[str] = None
    archive_reason: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionSummaryDTO]
    count: int


class SessionDetailResponse(SessionSummaryDTO):
    source_session_uuid: Optional[str] = None
    timeline: list[dict[str, str]] = Field(default_factory=list)
    story_quality_panel: StoryQualityPanel
    approval_panel: ApprovalPanel
    budget_panel: BudgetPanel
    priority_panel: PriorityPanel
    provider_selection_panel: ProviderSelectionPanel
    simulation_panel: SimulationPanel
    readiness_panel: ReadinessPanel
    queue_panel: QueuePanel
    provider_runtime_panel: ProviderRuntimePanel
    data_completeness: DataCompletenessDTO
    execution_readiness: Optional[dict[str, Any]] = None
    queue_item: Optional[dict[str, Any]] = None
    execution_runtime: Optional[dict[str, Any]] = None
    session: dict[str, Any] = Field(default_factory=dict)
    approval_decision: Optional[dict[str, Any]] = None
    simulation_report: Optional[dict[str, Any]] = None
