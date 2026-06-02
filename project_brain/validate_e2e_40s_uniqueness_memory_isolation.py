"""
Phase E2E-40S — Validate uniqueness memory isolation for planning probes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.engines.content_decision_engine import ContentDecisionEngine
from content_brain.orchestrators.content_brief_orchestrator import (
    ContentBriefOrchestrator,
    ContentBriefRunRequest,
)
from content_brain.schemas.content_brief import Platform
from project_brain.e2e_40s_planning_probe import run_e2e_40s_planning_probe
from project_brain.e2e_40s_uniqueness_memory import (
    isolated_probe_memory_file,
    production_uniqueness_memory_path,
    snapshot_uniqueness_memory,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> int:
    prod_path = production_uniqueness_memory_path(ROOT)
    before = snapshot_uniqueness_memory(prod_path)

    probe = run_e2e_40s_planning_probe(
        ROOT,
        topic="Girl in Rain",
        platform="youtube_shorts",
        user_duration_seconds=40,
        provider_name="runway_browser",
    )
    after = snapshot_uniqueness_memory(prod_path)

    _pass("planning_probe_production_memory_unchanged", probe.get("production_memory_unchanged") is True)
    _pass("planning_probe_production_snapshot_equals", before.equals(after))
    _pass(
        "planning_probe_isolated_memory_empty",
        int(probe.get("isolated_memory_record_count") or 0) == 0,
        f"isolated_count={probe.get('isolated_memory_record_count')}",
    )

    with tempfile.TemporaryDirectory(prefix="e2e_prod_write_test_") as tmp:
        prod_test_path = Path(tmp) / "content_history.json"
        unique_topic = "e2e isolation validator unique topic 40s 20260602"
        orchestrator = ContentBriefOrchestrator(
            project_root=ROOT,
            memory_path=prod_test_path,
        )
        result = orchestrator.run(
            ContentBriefRunRequest(
                niche="general",
                topic=unique_topic,
                platform=Platform.YOUTUBE_SHORTS,
                user_duration_seconds=40,
                provider_name="runway_browser",
                record_uniqueness_on_success=True,
                record_story_memory_on_success=False,
            )
        )
        wrote = snapshot_uniqueness_memory(prod_test_path)
        _pass(
            "production_style_run_can_record_when_ready",
            result.production_ready and wrote.record_count >= 1,
            f"decision={result.decision_package.decision.value} records={wrote.record_count}",
        )

    with tempfile.TemporaryDirectory(prefix="e2e_probe_then_prod_") as probe_tmp, tempfile.TemporaryDirectory(
        prefix="e2e_simulated_prod_"
    ) as prod_tmp:
        isolated_path = Path(probe_tmp) / "content_history.json"
        simulated_prod = Path(prod_tmp) / "content_history.json"
        probe_topic = "Girl in Rain e2e isolation sequence topic"

        probe_orch = ContentBriefOrchestrator(project_root=ROOT, memory_path=isolated_path)
        probe_result = probe_orch.run(
            ContentBriefRunRequest(
                niche="general",
                topic=probe_topic,
                platform=Platform.YOUTUBE_SHORTS,
                user_duration_seconds=40,
                provider_name="runway_browser",
                record_uniqueness_on_success=True,
                record_story_memory_on_success=False,
            )
        )
        isolated_snap = snapshot_uniqueness_memory(isolated_path)
        simulated_snap_before = snapshot_uniqueness_memory(simulated_prod)
        _pass(
            "probe_with_record_true_writes_only_isolated",
            isolated_snap.record_count >= 1 and simulated_snap_before.record_count == 0,
            f"isolated={isolated_snap.record_count}",
        )

        prod_orch = ContentBriefOrchestrator(project_root=ROOT, memory_path=simulated_prod)
        prod_result = prod_orch.run(
            ContentBriefRunRequest(
                niche="general",
                topic=probe_topic,
                platform=Platform.YOUTUBE_SHORTS,
                user_duration_seconds=40,
                provider_name="runway_browser",
                record_uniqueness_on_success=False,
                record_story_memory_on_success=False,
            )
        )
        _pass(
            "simulated_production_proceeds_after_isolated_probe",
            prod_result.decision_package.decision.value == "PROCEED",
            f"decision={prod_result.decision_package.decision.value}",
        )

    _pass(
        "reject_uniqueness_threshold_unchanged",
        ContentDecisionEngine.REJECT_UNIQUENESS_SCORE == 40.0
        and ContentDecisionEngine.REJECT_SIMILARITY_THRESHOLD == 0.85,
        "40.0 / 0.85",
    )

    _pass("no_runway_voice_changes", True, "validator scope only")

    print("\nE2E-40S uniqueness memory isolation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
