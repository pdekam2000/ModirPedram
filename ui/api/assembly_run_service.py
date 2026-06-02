"""Assembly runtime run API service (Phase 11J-19)."""

from __future__ import annotations

from typing import Any

from content_brain.execution.assembly_runtime_engine import AssemblyRuntimeEngine
from content_brain.execution.session_store import ExecutionSessionStore

API_VERSION = "0.7.5"


class AssemblyRunService:
    """Thin wrapper for POST /sessions/{id}/assembly/run."""

    def __init__(
        self,
        store: ExecutionSessionStore,
        *,
        engine: AssemblyRuntimeEngine | None = None,
    ):
        self._store = store
        self._engine = engine or AssemblyRuntimeEngine(store, project_root=store.project_root)

    def run(
        self,
        session_id: str,
        *,
        dry_run: bool = True,
        confirm_real_assembly: bool = False,
        overwrite: bool = False,
        timeout_seconds: int = 120,
        triggered_by: str = "operator",
        reason: str = "",
        max_output_bytes: int | None = None,
    ) -> dict[str, Any]:
        result = self._engine.run(
            session_id,
            dry_run=dry_run,
            confirm_real_assembly=confirm_real_assembly,
            overwrite=overwrite,
            timeout_seconds=timeout_seconds,
            triggered_by=triggered_by,
            reason=reason,
            max_output_bytes=max_output_bytes,
        )
        payload = result.to_dict()
        payload["api_version"] = API_VERSION
        return payload
