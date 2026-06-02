"""
Phase 12J-C2A-OBS validator — Runway browser execution observability.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_browser_observability import (
    RUNWAY_BROWSER_STEPS,
    RunwayBrowserObservability,
    build_runway_browser_observability,
    extract_runway_browser_obs_from_session,
    _is_runway_url,
    _safe_url,
)
from content_brain.execution.session_store import ExecutionSessionStore
from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator
from providers.runway_browser_provider import RunwayBrowserProvider
from core.video_provider_router import VideoProviderRouter


def _check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return ok


def main() -> int:
    passed = 0
    total = 0

    def record(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, total
        total += 1
        if _check(name, ok, detail):
            passed += 1

    required_steps = {
        "browser_connecting",
        "browser_connected",
        "page_selected",
        "preparing_gen45_page",
        "filling_prompt",
        "generate_clicked",
        "waiting_for_generation",
        "video_url_detected",
        "download_started",
        "download_completed",
        "failed",
    }
    record("runway steps defined", required_steps.issubset(set(RUNWAY_BROWSER_STEPS)))

    record("safe url strips query", _safe_url("https://app.runwayml.com/foo?token=secret") == "https://app.runwayml.com/foo")
    record("runway host detect", _is_runway_url("https://app.runwayml.com/"))

    noop = RunwayBrowserObservability(None, None)
    record("noop observability disabled", not noop.enabled)
    noop.set_step("filling_prompt")
    record("noop set_step no crash", True)

    store = ExecutionSessionStore(ROOT)
    session_id = "validate_12j_c2a_obs_session"
    session = {
        "execution_session_id": session_id,
        "execution_runtime": {
            "operations": {},
            "category_runtime": {"video_generation": {"state": "RUNNING", "provider": "runway_browser"}},
            "state": "RUNNING",
        },
    }
    store.save_session(session, overwrite=True)

    obs = build_runway_browser_observability(store, session_id, provider="runway_browser")
    record("obs factory for runway_browser", obs is not None and obs.enabled)
    record("obs factory skips hailuo", build_runway_browser_observability(store, session_id, provider="hailuo_browser") is None)

    if obs is not None:
        obs.set_step("preparing_gen45_page")
        class _FakePage:
            url = "https://app.runwayml.com/video?x=1"

            def title(self) -> str:
                return "Generative Session | Runway AI"

        obs.record_controlled_page(_FakePage(), type("BM", (), {"browser": type("B", (), {"contexts": []})()})())
        loaded = store.load_session(session_id)
        extracted = extract_runway_browser_obs_from_session(loaded)
        record(
            "persisted to operations + category_runtime",
            extracted["runway_browser_obs"].get("step") == "page_selected"
            and extracted["video_runtime"].get("runway_step") == "page_selected",
        )
        record(
            "controlled tab in video_runtime",
            "runwayml.com" in str(extracted["video_runtime"].get("controlled_tab_url") or ""),
        )
        cp = extracted["runway_browser_obs"].get("controlled_page") or {}
        record("no query in stored url", "?" not in str(cp.get("page_url") or ""))

    orch_sig = inspect.signature(RunwayBrowserOrchestrator.__init__)
    record("orchestrator accepts runway_obs", "runway_obs" in orch_sig.parameters)

    prov_sig = inspect.signature(RunwayBrowserProvider.__init__)
    record("provider accepts runway_obs", "runway_obs" in prov_sig.parameters)

    router_sig = inspect.signature(VideoProviderRouter.generate_clips)
    record("router passes runway_obs", "runway_obs" in router_sig.parameters)

    wait_sig = inspect.signature(RunwayBrowserOrchestrator.wait_for_generated_video_url)
    record("wait accepts runway_obs kwarg", "runway_obs" in wait_sig.parameters)

    from content_brain.execution import uat_runtime_engine as uat_mod

    uat_session = {
        "execution_session_id": session_id,
        "execution_runtime": {
            "operations": {
                "uat_run": {"status": "running", "session_id": session_id},
                "runway_browser_obs": {"step": "filling_prompt"},
            },
            "category_runtime": {"video_generation": {"state": "RUNNING"}},
            "state": "RUNNING",
        },
    }
    payload = uat_mod.build_uat_status_payload(uat_session)
    record("uat status exposes runway_browser_obs", "runway_browser_obs" in payload)
    record("uat status exposes video_runtime", payload.get("video_runtime", {}).get("runway_step") == "filling_prompt")

    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
