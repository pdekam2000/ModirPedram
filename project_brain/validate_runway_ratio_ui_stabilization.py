"""
Runway ratio/duration UI stabilization — validation (static + observability round-trip).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.runway_browser_observability import RunwayBrowserObservability
from content_brain.execution.session_store import ExecutionSessionStore
from providers.runway_browser_provider import RunwayBrowserProvider
from providers.runway_browser_support import (
    browser_ratio_duration_post_settle_seconds,
    browser_ratio_duration_stable_polls,
    browser_ratio_duration_stabilize_timeout_seconds,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> int:
    provider_src = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    obs_src = (ROOT / "content_brain/execution/runway_browser_observability.py").read_text(
        encoding="utf-8"
    )
    support_src = (ROOT / "providers/runway_browser_support.py").read_text(encoding="utf-8")
    clip_src = inspect.getsource(RunwayBrowserProvider.prepare_clip_for_generate)

    _pass("stabilize_wait_helper", "_wait_for_ratio_duration_ui_stable" in provider_src)
    _pass("before_generate_gate", "_stabilize_and_verify_before_generate" in provider_src)
    _pass("prepare_calls_stabilize", "_stabilize_and_verify_before_generate" in clip_src)
    _pass("ratio_retry_once", "[RUNWAY_RATIO_RETRY]" in provider_src)
    _pass("ui_stabilize_log", "[RUNWAY_UI_STABILIZE]" in provider_src)
    _pass("prep_before_generate_log", "[RUNWAY_PREP_BEFORE_GENERATE]" in provider_src)

    for field in (
        "ratio_selected_before_generate",
        "duration_selected_before_generate",
        "prompt_still_verified_before_generate",
        "ui_stabilized_after_ratio",
    ):
        _pass(f"obs_field_{field}", field in obs_src)

    _pass("support_post_settle", "browser_ratio_duration_post_settle_seconds" in support_src)
    _pass("support_stable_polls", "browser_ratio_duration_stable_polls" in support_src)
    _pass(
        "defaults_sane",
        browser_ratio_duration_post_settle_seconds() >= 0.25
        and browser_ratio_duration_stable_polls() >= 1
        and browser_ratio_duration_stabilize_timeout_seconds() >= 1.0,
    )

    _pass("download_logic_untouched", "wait_for_generated_video_url" not in provider_src)

    store = ExecutionSessionStore(ROOT)
    session_id = "validate_ratio_ui_stabilization_session"
    store.save_session(
        {
            "execution_session_id": session_id,
            "execution_runtime": {"operations": {}},
        },
        overwrite=True,
    )
    obs = RunwayBrowserObservability(store, session_id, clip_index=1)
    obs.record_clip_prep(
        ratio_selected_before_generate=True,
        duration_selected_before_generate=True,
        prompt_still_verified_before_generate=True,
        ui_stabilized_after_ratio=True,
    )
    loaded = store.load_session(session_id)
    runway_obs = loaded["execution_runtime"]["operations"]["runway_browser_obs"]
    _pass("obs_persist_ratio_before_generate", runway_obs.get("ratio_selected_before_generate") is True)
    _pass("obs_persist_ui_stabilized", runway_obs.get("ui_stabilized_after_ratio") is True)

    print("\nRunway ratio UI stabilization checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
