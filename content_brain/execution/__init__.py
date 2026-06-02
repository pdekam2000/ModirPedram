"""Content execution runtime storage and session helpers (Phase 10A–10D)."""

from content_brain.execution.session_store import ExecutionSessionStore

__all__ = [
    "ExecutionSessionStore",
    "SessionPopulationBuilder",
    "build_session_from_brief",
    "ApprovalBudgetGovernanceEngine",
    "SimulationReportBuilder",
    "GovernancePolicy",
    "ExecutionReadinessGate",
    "ExecutionQueueEngine",
    "ProviderRuntimeEngine",
    "OperationsPolicy",
    "ProviderModeCatalog",
    "ProviderModeRouter",
    "ProviderPreflightValidator",
    "RuntimeWorkerEngine",
    "RuntimeJobRegistry",
    "ArtifactValidationEngine",
    "seed_operations_demo_sessions",
    "OperationsControlEngine",
]


def __getattr__(name: str):
    if name in {
        "SessionPopulationBuilder",
        "build_session_from_brief",
        "ApprovalBudgetGovernanceEngine",
        "SimulationReportBuilder",
        "ExecutionReadinessGate",
        "ExecutionQueueEngine",
        "GovernancePolicy",
        "QueuePolicy",
        "ProviderRuntimeEngine",
        "RuntimePolicy",
        "OperationsPolicy",
        "ProviderModeCatalog",
        "ModeResolution",
        "FailureTaxonomy",
        "ProviderModeRouter",
        "ProviderPreflightValidator",
        "PreflightResult",
        "RuntimeWorkerEngine",
        "WorkerSubmitResult",
        "RuntimeJobRegistry",
        "JobRecord",
        "ArtifactValidationEngine",
        "ArtifactValidationResult",
        "seed_operations_demo_sessions",
        "OperationsControlEngine",
    }:
        if name == "SessionPopulationBuilder":
            from content_brain.execution.session_population_builder import SessionPopulationBuilder
            return SessionPopulationBuilder
        if name == "build_session_from_brief":
            from content_brain.execution.session_population_builder import build_session_from_brief
            return build_session_from_brief
        if name == "ApprovalBudgetGovernanceEngine":
            from content_brain.execution.approval_budget_governance_engine import ApprovalBudgetGovernanceEngine
            return ApprovalBudgetGovernanceEngine
        if name == "SimulationReportBuilder":
            from content_brain.execution.simulation_report_builder import SimulationReportBuilder
            return SimulationReportBuilder
        if name == "GovernancePolicy":
            from content_brain.execution.approval_budget_governance_engine import GovernancePolicy
            return GovernancePolicy
        if name == "ExecutionReadinessGate":
            from content_brain.execution.execution_readiness_gate import ExecutionReadinessGate
            return ExecutionReadinessGate
        if name == "ExecutionQueueEngine":
            from content_brain.execution.execution_queue_engine import ExecutionQueueEngine
            return ExecutionQueueEngine
        if name == "QueuePolicy":
            from content_brain.execution.execution_queue_engine import QueuePolicy
            return QueuePolicy
        if name == "ProviderRuntimeEngine":
            from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine
            return ProviderRuntimeEngine
        if name == "RuntimePolicy":
            from content_brain.execution.provider_runtime_engine import RuntimePolicy
            return RuntimePolicy
        if name == "OperationsPolicy":
            from content_brain.execution.operations_policy import OperationsPolicy
            return OperationsPolicy
        if name == "ProviderModeCatalog":
            from content_brain.execution.provider_mode_catalog import ProviderModeCatalog
            return ProviderModeCatalog
        if name == "ModeResolution":
            from content_brain.execution.provider_mode_catalog import ModeResolution
            return ModeResolution
        if name == "FailureTaxonomy":
            import content_brain.execution.failure_taxonomy as failure_taxonomy
            return failure_taxonomy
        if name == "ProviderModeRouter":
            from content_brain.execution.provider_mode_router import ProviderModeRouter
            return ProviderModeRouter
        if name == "ProviderPreflightValidator":
            from content_brain.execution.provider_preflight_validator import ProviderPreflightValidator
            return ProviderPreflightValidator
        if name == "PreflightResult":
            from content_brain.execution.provider_preflight_validator import PreflightResult
            return PreflightResult
        if name == "RuntimeWorkerEngine":
            from content_brain.execution.runtime_worker_engine import RuntimeWorkerEngine
            return RuntimeWorkerEngine
        if name == "WorkerSubmitResult":
            from content_brain.execution.runtime_worker_engine import WorkerSubmitResult
            return WorkerSubmitResult
        if name == "RuntimeJobRegistry":
            from content_brain.execution.runtime_job_registry import RuntimeJobRegistry
            return RuntimeJobRegistry
        if name == "JobRecord":
            from content_brain.execution.runtime_job_registry import JobRecord
            return JobRecord
        if name == "ArtifactValidationEngine":
            from content_brain.execution.artifact_validation_engine import ArtifactValidationEngine
            return ArtifactValidationEngine
        if name == "ArtifactValidationResult":
            from content_brain.execution.artifact_validation_engine import ArtifactValidationResult
            return ArtifactValidationResult
        if name == "seed_operations_demo_sessions":
            from content_brain.execution.seed_operations_demo_sessions import seed_operations_demo_sessions
            return seed_operations_demo_sessions
        if name == "OperationsControlEngine":
            from content_brain.execution.operations_control_engine import OperationsControlEngine
            return OperationsControlEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
