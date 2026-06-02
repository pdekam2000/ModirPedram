"""
Phase 11G — multi-category runtime shell validation.
"""

from __future__ import annotations

import json
from pathlib import Path

from content_brain.execution.category_runtime_compat import (
    FUTURE_CATEGORY_ROUTERS,
    STATUS_PLANNED,
    build_category_runtime_view,
    default_category_runtime_slots,
    ensure_multi_category_shell,
    get_category_slot,
    normalize_category_runtime,
)
from content_brain.execution.provider_categories import (
    CATEGORY_ASSEMBLY,
    CATEGORY_MUSIC,
    CATEGORY_SUBTITLES,
    CATEGORY_VIDEO,
    CATEGORY_VOICE,
    MEDIA_CATEGORIES as PC_MEDIA,
)
from content_brain.execution.provider_runtime_engine import ProviderRuntimeEngine, RuntimePolicy
from content_brain.execution.session_store import ExecutionSessionStore
from ui.api.services.panel_extractor import PanelExtractor
from ui.api.services.runtime_service import RuntimeService


def _pass(name: str, ok: bool, detail: str = "") -> dict:
    return {"test": name, "pass": ok, "detail": detail}


def run_matrix(project_root: str | Path = ".") -> dict:
    root = Path(project_root).resolve()
    results: list[dict] = []

    results.append(
        _pass(
            "media_categories_defined",
            PC_MEDIA
            == (
                CATEGORY_VIDEO,
                CATEGORY_VOICE,
                CATEGORY_MUSIC,
                CATEGORY_SUBTITLES,
                CATEGORY_ASSEMBLY,
            ),
            ",".join(PC_MEDIA),
        )
    )

    slots = default_category_runtime_slots()
    results.append(_pass("default_slots_count", len(slots) == 5, str(list(slots.keys()))))
    results.append(
        _pass(
            "video_slot_pending",
            slots[CATEGORY_VIDEO].get("status") == "pending",
            str(slots[CATEGORY_VIDEO].get("status")),
        )
    )
    results.append(
        _pass(
            "voice_slot_planned",
            slots[CATEGORY_VOICE].get("status") == STATUS_PLANNED,
            str(slots[CATEGORY_VOICE].get("status")),
        )
    )
    results.append(
        _pass(
            "slot_schema_fields",
            all(
                key in slots[CATEGORY_VOICE]
                for key in (
                    "category_name",
                    "status",
                    "provider",
                    "artifacts",
                    "error",
                    "started_at",
                    "completed_at",
                    "duration_seconds",
                    "cost_estimate",
                    "runtime_notes",
                )
            ),
        )
    )

    legacy_path = root / "storage/content_brain/execution/sessions/exec_10i_completed_demo.json"
    legacy_session = json.loads(legacy_path.read_text(encoding="utf-8"))
    normalized = normalize_category_runtime(legacy_session.get("execution_runtime"))
    results.append(_pass("legacy_session_normalizes", len(normalized) >= 5))
    results.append(
        _pass(
            "legacy_video_state_preserved",
            normalized[CATEGORY_VIDEO].get("state") == "COMPLETED",
            str(normalized[CATEGORY_VIDEO].get("state")),
        )
    )
    results.append(
        _pass(
            "legacy_missing_slot_safe",
            get_category_slot({}, CATEGORY_SUBTITLES).get("status") == STATUS_PLANNED,
        )
    )

    runtime = ensure_multi_category_shell({"category_runtime": {}, "artifacts_by_category": {}})
    results.append(_pass("shell_block_added", "multi_category_shell" in runtime))
    results.append(
        _pass(
            "shell_executable_video_only",
            runtime.get("multi_category_shell", {}).get("executable_categories_11g") == [CATEGORY_VIDEO],
        )
    )

    view = build_category_runtime_view(legacy_session.get("execution_runtime"))
    results.append(_pass("category_view_ordered", len(view) == 5))
    results.append(
        _pass(
            "category_view_video_executable",
            view[0].get("category_key") == CATEGORY_VIDEO and view[0].get("executable") is True,
        )
    )

    for category in (CATEGORY_VOICE, CATEGORY_MUSIC, CATEGORY_SUBTITLES, CATEGORY_ASSEMBLY):
        results.append(_pass(f"future_router_{category}", category in FUTURE_CATEGORY_ROUTERS))

    store = ExecutionSessionStore(root)
    engine = ProviderRuntimeEngine(store)
    policy = RuntimePolicy(provider_category="voice_generation")
    ok, reasons, code = engine.validate_dispatch_eligibility({"state": "DEQUEUED"}, policy)
    results.append(
        _pass(
            "non_video_dispatch_rejected",
            ok is False and code == "CATEGORY_NOT_SUPPORTED",
            code or "",
        )
    )

    panel = PanelExtractor().extract_provider_runtime(legacy_session)
    panel_slots = panel.get("data", {}).get("category_runtime_slots") or []
    results.append(_pass("panel_extractor_slots", len(panel_slots) == 5))

    service = RuntimeService(store)
    status = service.status(ExecutionSessionStore.extract_session_id(legacy_session))
    results.append(
        _pass(
            "runtime_status_slots",
            len(status.get("category_runtime_slots") or []) == 5,
        )
    )

    policy = RuntimePolicy()
    snapshot = policy.snapshot()
    results.append(
        _pass(
            "policy_11g_shell_categories",
            "supported_categories_11g_shell" in snapshot
            and snapshot.get("supported_categories_11g_shell") == list(PC_MEDIA),
        )
    )

    passed = sum(1 for item in results if item["pass"])
    return {
        "phase": "11G",
        "label": "multi_category_runtime_shell",
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def main() -> int:
    report = run_matrix()
    print(json.dumps(report, indent=2))
    for item in report["results"]:
        mark = "PASS" if item["pass"] else "FAIL"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{mark}] {item['test']}{detail}")
    print(f"\n{report['passed']}/{report['total']} PASS")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
