"""Expandable panel DTOs for Execution Center V2."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PanelDTO(BaseModel):
    """
    Base panel envelope — supports partial and future fields without UI breaks.

    Known values render from `data`; unknown future writer fields remain in
    `data` and `metadata` for forward compatibility.
    """

    status: str = "missing"  # available | partial | missing | unavailable
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class StoryQualityPanel(PanelDTO):
    panel: str = "story_quality"


class ApprovalPanel(PanelDTO):
    panel: str = "approval"


class BudgetPanel(PanelDTO):
    panel: str = "budget"


class PriorityPanel(PanelDTO):
    panel: str = "priority"


class ProviderSelectionPanel(PanelDTO):
    panel: str = "provider_selection"


class SimulationPanel(PanelDTO):
    panel: str = "simulation"


class ReadinessPanel(PanelDTO):
    panel: str = "readiness"


class QueuePanel(PanelDTO):
    panel: str = "queue"


class ProviderRuntimePanel(PanelDTO):
    panel: str = "provider_runtime"


class DataCompletenessDTO(BaseModel):
    story_quality: float = 0.0
    approval: float = 0.0
    budget: float = 0.0
    priority: float = 0.0
    provider_selection: float = 0.0
    simulation: float = 0.0
    readiness: float = 0.0
    queue: float = 0.0
    provider_runtime: float = 0.0


class SessionOverviewResponse(BaseModel):
    total_sessions: int = 0
    active_sessions_count: int = 0
    archived_sessions_count: int = 0
    simulated_count: int = 0
    approved_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    queued_count: int = 0
    runtime_active_count: int = 0
    runtime_completed_count: int = 0
    avg_story_quality_score: Optional[float] = None
    avg_execution_confidence: Optional[float] = None
    generated_at: str
