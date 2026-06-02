"""
Phase 12J-E0 — Runway interaction order: prompt before ratio/duration, verified before Generate.
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
from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator
from providers.runway_browser_provider import RunwayBrowserProvider
from providers.runway_browser_support import PROMPT_INJECTION_INCOMPLETE


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> int:
    provider_src = (ROOT / "providers/runway_browser_provider.py").read_text(encoding="utf-8")
    orch_src = (ROOT / "orchestrators/runway_browser_orchestrator.py").read_text(encoding="utf-8")

    prep_src = inspect.getsource(RunwayBrowserProvider.prepare_gen45_page)
    clip_src = inspect.getsource(RunwayBrowserProvider.prepare_clip_for_generate)
    click_src = inspect.getsource(RunwayBrowserProvider.click_generate)

    _pass("prep_no_ratio_on_page_prep", "set_ratio_16_9" not in prep_src)
    _pass("prep_no_duration_on_page_prep", "set_duration_10s" not in prep_src)
    _pass("prep_enters_editor", "enter_generate_editor" in prep_src)

    _pass("clip_uses_set_prompt_verified", "set_prompt_verified" in clip_src)
    _pass(
        "clip_prompt_before_ratio",
        clip_src.index("set_prompt_verified") < clip_src.index("set_ratio_16_9"),
    )
    _pass(
        "clip_ratio_before_duration",
        clip_src.index("set_ratio_16_9") < clip_src.index("set_duration_10s"),
    )
    _pass("clip_ready_log", "[RUNWAY_READY_TO_GENERATE]" in clip_src)

    _pass("orchestrator_uses_prepare_clip", "prepare_clip_for_generate" in orch_src)
    _pass(
        "orchestrator_clip_before_generate",
        orch_src.index("prepare_clip_for_generate") < orch_src.index("click_generate"),
    )

    _pass("log_prompt_set_start", "[RUNWAY_PROMPT_SET_START]" in provider_src)
    _pass("log_prompt_set_done", "[RUNWAY_PROMPT_SET_DONE]" in provider_src)
    _pass("log_prompt_verify", "[RUNWAY_PROMPT_VERIFY]" in provider_src)
    _pass("log_ratio_set", "[RUNWAY_RATIO_SET]" in provider_src)
    _pass("log_duration_set", "[RUNWAY_DURATION_SET]" in provider_src)
    _pass("log_ready_to_generate", "[RUNWAY_READY_TO_GENERATE]" in provider_src)

    _pass("uses_fill_not_slow_type", "keyboard.type(prompt, delay=5)" not in provider_src)
    _pass("no_focus_steal_mouse_click", "mouse.click(1200, 700)" not in provider_src)
    _pass("prefers_box_fill", ".fill(prompt" in provider_src)
    _pass("prompt_verify_prefix_suffix", "PROMPT_EDGE_COMPARE_CHARS" in provider_src)
    _pass("prompt_incomplete_code", PROMPT_INJECTION_INCOMPLETE in provider_src)
    _pass("verify_before_generate_click", "_verify_prompt_injection" in click_src)
    _pass("retry_once_on_prompt_fail", "retrying clear + paste once" in provider_src)

    _pass(
        "orch_still_calls_prepare_page_once",
        "prepare_gen45_page" in inspect.getsource(RunwayBrowserOrchestrator.run),
    )

    obs_src = (ROOT / "content_brain/execution/runway_browser_observability.py").read_text(
        encoding="utf-8"
    )
    _pass("obs_record_clip_prep", "def record_clip_prep" in obs_src)
    for field in (
        "prompt_expected_length",
        "prompt_actual_length",
        "prompt_verified",
        "ratio_verified",
        "duration_verified",
    ):
        _pass(f"obs_field_{field}", field in obs_src)

    store = ExecutionSessionStore(ROOT)
    session_id = "validate_12j_e0_obs_session"
    store.save_session(
        {
            "execution_session_id": session_id,
            "execution_runtime": {
                "operations": {},
                "category_runtime": {"video_generation": {"state": "RUNNING"}},
            },
        },
        overwrite=True,
    )
    obs = RunwayBrowserObservability(store, session_id, clip_index=1)
    obs.record_clip_prep(
        prompt_expected_length=500,
        prompt_actual_length=498,
        prompt_verified=True,
        ratio_verified=True,
        duration_verified=True,
    )
    loaded = store.load_session(session_id)
    runway_obs = loaded["execution_runtime"]["operations"]["runway_browser_obs"]
    _pass("obs_persist_prompt_expected", runway_obs.get("prompt_expected_length") == 500)
    _pass("obs_persist_prompt_verified", runway_obs.get("prompt_verified") is True)
    _pass("obs_persist_duration_verified", runway_obs.get("duration_verified") is True)

    _pass(
        "wait_logic_unchanged_in_orchestrator",
        "wait_for_generated_video_url" in orch_src,
        "download detection not modified in 12J-E0",
    )

    print("\n12J-E0 Runway interaction order checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
